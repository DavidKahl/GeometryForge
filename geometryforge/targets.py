"""Independent delivery routes on top of the native execution/evidence engine."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import uuid

from . import projects
from .locking import exclusive
from .storage import digest, fingerprint, inside, read, write

ROUTES = ('design', 'print', 'game')
STAGES = ('uv', 'materials', 'bake', 'lod', 'collision')


def selected(p, target=None):
    if target == 'both':
        return ['print', 'game']
    if target:
        if target not in ROUTES:
            raise ValueError('Unknown output target')
        return [target]
    return p['decisions'].get('output_targets', ['print'])


def declared_files(p, routes=ROUTES):
    names = set()
    def visit(value):
        if not isinstance(value, dict):
            return
        names.update(value.get('sources', []))
        if 'entry' in value:
            names.add(value['entry'])
        if 'source' in value:
            names.add(value['source'])
        for child in value.values():
            if isinstance(child, dict):
                visit(child)
    visit(p['config'].get('targets', {}))
    for route in routes:
        for material in settings(p, route).get('materials', {}).values():
            for texture in material.get('textures', {}).values():
                names.add(texture['path'] if isinstance(texture, dict) else texture)
    return names


def validate_contract(p):
    routes = p['decisions'].get('output_targets')
    if not isinstance(routes, list) or not routes or len(set(routes)) != len(routes) or set(routes) - {'print', 'game'}:
        raise ValueError('v2 output_targets must contain print and/or game exactly once')
    config = p['config'].get('targets', {})
    if set(config) - set(ROUTES):
        raise ValueError('Unknown target configuration')
    from . import gates
    gates.validate(p)
    for name, spec in config.items():
        if set(spec.get('depends', [])) - set(ROUTES) or name in spec.get('depends', []):
            raise ValueError(f'Invalid target dependency: {name}')
        if name != 'design' and any(d != 'design' for d in spec.get('depends', [])):
            raise ValueError('Delivery routes depend on design; cross-route conversion uses frozen derivation sources')
        for output, detail in spec.get('outputs', {}).items():
            if not projects.ID.fullmatch(output):
                raise ValueError(f'Invalid output ID: {output}')
            source_parts = detail.get('source_parts', [output])
            if not source_parts or set(source_parts) - p['config'].get('parts', {}).keys():
                raise ValueError(f'Unknown source parts of {name}/{output}')
        for stage, detail in spec.get('stages', {}).items():
            if stage not in STAGES:
                raise ValueError(f'Unknown preparation stage: {stage}')
            earlier = {'geometry', *STAGES[:STAGES.index(stage)]}
            if set(detail.get('depends', ['geometry'])) - earlier:
                raise ValueError(f'Invalid preparation dependency: {stage}')
        view = route_view(p, name)
        for output, detail in view['config']['parts'].items():
            if set(detail.get('depends', [])) - view['config']['parts'].keys():
                raise ValueError(f'Unknown output dependency: {name}/{output}')
            if set(detail.get('parameters', [])) - p['parameters'].keys():
                raise ValueError(f'Missing parameters: {name}/{output}')
        for backend, detail in view['config']['backends'].items():
            if backend not in ('blender', 'houdini') or not inside(p['root'], detail['entry']).is_file():
                raise ValueError(f'Invalid {name} backend: {backend}')
        for check in view['config']['checks'].values():
            if set(check['parts']) - view['config']['parts'].keys():
                raise ValueError(f'Checker references undeclared outputs: {name}')
    for name in declared_files(p):
        if not inside(p['root'], name).is_file():
            raise ValueError(f'Missing declared target input: {name}')
    from .game import profile_settings
    profile_settings(settings(p, 'game'))


def settings(p, target, profile=None):
    spec = p['config'].get('targets', {}).get(target, {})
    result = deepcopy(p['decisions'].get(target, {}))
    result.update({k: deepcopy(v) for k, v in spec.items()
                   if k not in ('backends', 'outputs', 'checks', 'sources', 'stages', 'depends')})
    if profile:
        if target != 'game':
            raise ValueError('--profile applies to the game route')
        result['profile'] = profile
    return result


def route_view(p, target, profile=None):
    spec = p['config'].get('targets', {}).get(target, {})
    config = deepcopy(p['config'])
    config['format_version'] = 1
    config['backends'].update(spec.get('backends', {})) if 'backends' in config else config.update(backends=deepcopy(spec.get('backends', {})))
    if 'outputs' in spec:
        parts = {}
        for output, detail in spec['outputs'].items():
            inherited = [p['config']['parts'][n] for n in detail.get('source_parts', [output])]
            parts[output] = {'sources': sorted({s for part in inherited for s in part.get('sources', [])}),
                             'parameters': sorted({s for part in inherited for s in part.get('parameters', [])}), 'depends': []}
            parts[output].update(deepcopy(detail))
        config['parts'] = parts
    for part in config.get('parts', {}).values():
        part['sources'] = sorted(set(part.get('sources', [])) | set(spec.get('sources', [])))
    config['checks'] = {n: deepcopy(c) for n, c in p['config'].get('checks', {}).items()
                        if target in c.get('targets', ['print', 'game']) and ('checks' not in spec or n in spec['checks'])}
    config.pop('targets', None)
    gate_state = None
    if config.pop('gates', None):
        from . import gates
        gate_state = gates.frontier(p)
        if target == gate_state['route']:
            # Later-gate parts are dormant: never built, checked or required in the scene.
            keep = set(gate_state['frontier'])
            config['parts'] = {n: s for n, s in config['parts'].items() if n in keep}
            config['checks'] = {n: c for n, c in config['checks'].items() if set(c['parts']) <= keep}
    state = p['state'].get('targets', {}).get(target, {'backends': {}, 'safe_point': None})
    decision = deepcopy(p['decisions'])
    decision[target] = settings(p, target, profile)
    return {**p, 'config': config, 'decisions': decision,
            'state': {**state, 'issues': [], 'latest_attempt': p['state'].get('latest_attempt')},
            '_target': target, '_settings': decision[target], '_target_spec': spec, '_gates': gate_state}


def route_key(p, target, profile=None):
    view = route_view(p, target, profile)
    config = view['config']
    names = set()
    for spec in config['parts'].values():
        names.update(spec.get('sources', []))
    for spec in config['backends'].values():
        names.add(spec['entry'])
    for spec in config['checks'].values():
        names.update([*([spec['source']] if 'source' in spec else []), *spec.get('sources', [])])
    temporary = {**p, 'config': {'targets': {target: p['config'].get('targets', {}).get(target, {})}}}
    names.update(declared_files(temporary, [target]))
    parameters = {n for s in [*config['parts'].values(), *config['checks'].values(), *view['_target_spec'].get('stages', {}).values()] for n in s.get('parameters', [])}
    value = {'parts': config['parts'], 'backends': config['backends'], 'checks': config['checks'],
             'settings': view['_settings'], 'stages': view['_target_spec'].get('stages', {}),
             'sources': {n: digest(inside(p['root'], n)) for n in sorted(names)},
             'parameters': {n: p['parameters'][n] for n in parameters},
             'deliverables': p['decisions'].get('deliverables'), 'execution_backend': p['decisions'].get('execution_backend')}
    derivation = p['decisions'].get('derivations', {}).get(target)
    if derivation:
        value['derivation'] = derivation
    if target != 'design' and 'design' in p['config'].get('targets', {}) and not derivation:
        value['design'] = route_key(p, 'design')
        value['design_evidence'] = design_evidence(p)
    return fingerprint(value)


def design_evidence(p):
    from . import engine
    result = {}
    for backend,state in p['state'].get('targets',{}).get('design',{}).get('backends',{}).items():
        base = engine.record(p,state.get('run')) or {}
        geometry = base.get('targets',{}).get('design',{}).get('backends',{}).get(backend,{}).get('geometry')
        working = inside(p['root'],state['working']) if state.get('working') else None
        edited = bool(working and (not working.is_file() or digest(working) != state.get('working_hash')))
        result[backend] = {'geometry':geometry,'saved_edit':digest(working) if edited and working.is_file() else 'missing' if edited else None}
    return result


def baseline_view(p, target, profile=None):
    """Normalize a v2 run's route into the legacy backend planner's read model."""
    from . import engine
    view = route_view(p, target, profile)
    baselines = {}
    for backend, state in view['state']['backends'].items():
        base = engine.record(p, state.get('run'))
        if base:
            baselines[state['run']] = {**base, 'backends': base.get('targets', {}).get(target, {}).get('backends', base.get('backends', {}))}
    view['_records'] = baselines
    return view


def context(root):
    from . import engine
    p = projects.load(root)
    routes = {}
    for target in dict.fromkeys([*selected(p), *p['state'].get('targets', {})]):
        view = baseline_view(p, target)
        key = route_key(p, target)
        states = {}
        for backend in engine.selected_backends(view):
            state = view['state']['backends'].get(backend, {})
            working = inside(root, state['working']) if state.get('working') else None
            changed = bool(working and (not working.is_file() or digest(working) != state.get('working_hash')))
            states[backend] = {**state, 'working_changed': changed, 'stale': changed or state.get('route_key') != key}
        routes[target] = {'safe_point': view['state'].get('safe_point'), 'backends': states,
                          'stale': any(v['stale'] for v in states.values()), 'profile': view['_settings'].get('profile')}
    default = selected(p)[0]
    stale = any(routes[t]['stale'] for t in selected(p))
    safe = p['state'].get('safe_point')
    imports = read(p['root'] / '.geometryforge/import-state.json', {})
    result = {'project': str(p['root']), 'decisions': p['decisions'], 'parameters': p['parameters'],
              'targets': routes, 'output_targets': selected(p), 'backends': routes[default]['backends'],
              'safe_points': p['state'].get('safe_points', {}), 'safe_point': safe,
              'safe_point_label': ('SAFE POINT — predates working edits' if stale else 'SAFE POINT') if safe else 'No aggregate safe point',
              'latest_attempt': p['state'].get('latest_attempt'), 'unreal': imports,
              'issues': p['state'].get('issues', []) + p['decisions'].get('unresolved', []),
              'note': 'Each route has independent editable scenes and package evidence. Unreal verification is separate.'}
    from . import gates
    if gates.declared(p):
        summary = gates.status(root)
        result['gates'] = summary
        if summary['active_gate']:
            result['issues'].append(f"Gate '{summary['active_gate']}' is active; later parts stay dormant until it is accepted")
    return result


def plan(root, backend=None, parts=(), full=False, source='auto', target=None, profile=None):
    from . import engine, gates
    p = projects.load(root)
    gates.require_buildable(p, parts)
    routes = selected(p, target)
    if profile and 'game' not in routes:
        raise ValueError('--profile requires the game target')
    if 'design' in p['config'].get('targets', {}) and any(t != 'design' and not p['decisions'].get('derivations',{}).get(t) for t in routes):
        routes = ['design', *routes]
    result = {}
    for route in dict.fromkeys(routes):
        if route not in p['config'].get('targets', {}):
            raise ValueError(f'No {route} recipe is declared; author the target before execution')
        view = baseline_view(p, route, profile if route == 'game' else None)
        selected_parts = parts
        if parts and 'outputs' in view['_target_spec']:
            selected_parts = [n for n, s in view['config']['parts'].items() if n in parts or set(s.get('source_parts', [n])).intersection(parts)]
        if route == 'design' and parts:
            selected_parts = [n for n in parts if n in view['config']['parts']]
        proposal = engine.plan(root, backend, selected_parts, full, source, _project=view)
        for b, spec in proposal['backends'].items():
            prior_run = engine.record(view, view['state']['backends'].get(b, {}).get('run')) or {}
            prior = prior_run.get('backends', {}).get(b, {})
            spec['stages'] = stage_plan(p, view, b, spec['parts'], prior, source, full)
            preparation_changed = any(s['run'] for s in spec['stages'].values())
            if preparation_changed and source == 'auto' and spec['manual_edits']:
                spec['needs_choice'] = True
                spec['reason'] = 'Both preparation recipes and saved scene changed; choose --source scene or --source code explicitly'
        result[route] = {**proposal, 'profile': view['_settings'].get('profile'), 'route_key': route_key(p, route, profile if route == 'game' else None)}
    return {'targets': result, 'requested_targets': selected(p, target), 'full': full}


def stage_plan(p, view, backend, geometry_parts, prior, source, full=False):
    result = {}
    changed = {'geometry': bool(geometry_parts)}
    for name in STAGES:
        spec = view['_target_spec'].get('stages', {}).get(name)
        if spec is None:
            continue
        entry = spec.get('backends', {}).get(backend, {}).get('entry', spec.get('entry'))
        if not entry:
            raise ValueError(f'No {backend} implementation for preparation stage {name}')
        files = [entry, *spec.get('sources', [])]
        key = fingerprint({'files': {s: digest(inside(p['root'], s)) for s in files},
                           'parameters': {s: p['parameters'][s] for s in spec.get('parameters', [])},
                           'spec': spec, 'profile': view['_settings'].get('profile')})
        dirty = key != prior.get('stages', {}).get(name, {}).get('key') or any(changed.get(d, False) for d in spec.get('depends', ['geometry']))
        changed[name] = dirty
        result[name] = {'key': key, 'entry': entry, 'run': dirty and source != 'scene',
                        'pending': dirty and source == 'scene',
                        'parts': sorted(view['config']['parts']) if dirty else [], 'reused': not dirty}
    return result


def execute(root, backend=None, parts=(), full=False, source='auto', timeout=900, executables=None, target=None, profile=None):
    from . import engine, backends
    p = projects.load(root)
    with exclusive(p['root'] / '.geometryforge'):
        p = projects.load(root)
        proposal = plan(root, backend, parts, full, source, target, profile)
        ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        out = engine.run_path(p, ident)
        out.mkdir(parents=True)
        data = {'format_version': 2, 'id': ident, 'parent': p['state'].get('safe_point'), 'status': 'running',
                'owner_pid': os.getpid(), 'inputs': projects.inputs(p), 'decisions': deepcopy(p['decisions']),
                'parameters': p['parameters'], 'plan': proposal, 'targets': {}, 'backends': {}, 'failures': [],
                'validation': {}, 'engine_version': engine.engine_version(), 'toolkit': engine.__version__}
        if profile:
            data['decisions'].setdefault('game', {})['profile'] = profile
        p['state']['latest_attempt'] = ident
        write(out / 'run.json', data)
        projects.save_state(p)
        try:
            frozen = engine.snapshot(p, out, data['inputs'])
            for route, route_plan in proposal['targets'].items():
                view = baseline_view(p, route, profile if route == 'game' else None)
                effective_key = route_key(p,route,profile if route == 'game' else None)
                route_out = out / route
                route_out.mkdir()
                route_data = {**data, 'backends': {}, 'validation': {}, 'decisions': view['decisions']}
                item = {'status': 'running', 'backends': route_data['backends'], 'settings': view['_settings'],
                        'route_key': effective_key, 'failures': [], 'validation': route_data['validation']}
                gate_state = view.get('_gates')
                if gate_state:
                    item['gates'] = {k: gate_state[k] for k in ('active', 'accepted', 'frontier', 'dormant')}
                data['targets'][route] = item
                pending = {}
                try:
                    if route != 'design' and data['targets'].get('design', {}).get('status') not in (None, 'passed'):
                        raise engine.ScopeUncertain('Shared design did not pass; dependent route retained as candidate')
                    if gate_state and route != gate_state['route'] and not gate_state['complete']:
                        raise engine.ScopeUncertain(f"Modeling gates are incomplete (active: {gate_state['active']}); "
                                                    f"the {route} route waits for the final accepted gate")
                    for b, original_spec in route_plan['backends'].items():
                        spec = deepcopy(original_spec)
                        pending_preparation=[name for name,stage in spec.get('stages',{}).items() if stage.get('pending')]
                        if pending_preparation:
                            raise engine.ScopeUncertain('Required preparation changed: '+', '.join(pending_preparation)+'. Verify never runs these builders; prepare or reconcile the target first.')
                        previous = engine.record(view,view['state']['backends'].get(b,{}).get('run')) or {}
                        previous_backend = previous.get('backends',{}).get(b,{})
                        current_design = data['targets'].get('design',{}).get('backends',{}).get(b,{}).get('geometry')
                        if route != 'design' and current_design is not None and previous_backend.get('design_geometry') != current_design:
                            if source == 'scene' or source == 'auto' and (spec['manual_edits'] or previous_backend.get('native_edits')):
                                raise engine.ScopeUncertain('Shared design changed; reconcile the target before verification or explicitly use --source code')
                            spec['parts'] = projects.build_order(view['config'], view['config']['parts'])
                            spec['source'] = 'code'
                            spec['stages'] = stage_plan(p,view,b,spec['parts'],previous_backend,source)
                        if spec['needs_choice']:
                            raise engine.ScopeUncertain(spec['reason'])
                        native_context = {'target': route, 'profile': view['_settings'], 'stages': spec.get('stages', {}),
                                          'snapshot_root': str(frozen), 'project_root': str(p['root']),
                                          'previous_mesh_exports': previous_backend.get('mesh_exports',{}),
                                          'full': full, 'known_parts': list(view['config']['parts'])}
                        if route != 'design' and 'design' in data['targets']:
                            design = data['targets']['design']['backends'].get(b)
                            if not design:
                                raise engine.ScopeUncertain('Requested design backend is missing')
                            native_context['design_scene'] = str(inside(p['root'], design['native']['path']))
                        derivation = p['decisions'].get('derivations', {}).get(route)
                        if derivation:
                            validate_derivation(p, derivation)
                            native_context['derivation'] = derivation
                        token = backends.native_context.set(native_context)
                        try:
                            pending[b] = engine.execute_backend(view, route_data, route_out, frozen, b, spec, full, timeout, (executables or {}).get(b))
                        finally:
                            backends.native_context.reset(token)
                        route_data['backends'][b]['stages'] = spec.get('stages', {})
                        route_data['backends'][b]['design_geometry'] = current_design
                        old = view['state']['backends'].get(b, {})
                        if old.get('working') and digest(inside(p['root'], old['working'])) != route_data['backends'][b]['working_input_hash']:
                            raise engine.ScopeUncertain('Working scene changed during execution')
                        pending[b]['route_key'] = effective_key
                    if projects.inputs(p) != data['inputs']:
                        raise engine.ScopeUncertain('Project inputs changed during execution')
                    requested = engine.selected_backends(view)
                    complete = all(b in pending for b in requested)
                    if complete and len(requested) == 2:
                        engine.parity(view, route_data)
                    state = p['state'].setdefault('targets', {}).setdefault(route, {'backends': {}, 'safe_point': None})
                    state['backends'].update(pending)
                    item['status'] = 'passed' if complete else 'candidate'
                    item['validation']['complete'] = complete
                    if complete:
                        state['safe_point'] = ident
                        p['state'].setdefault('safe_points', {})[route] = ident
                except BaseException as exc:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    item['status'] = 'candidate' if isinstance(exc, engine.ScopeUncertain) else 'failed'
                    item['failures'].append(str(exc))
                    data['failures'].append(f'{route}: {exc}')
                write(out / 'run.json', data)
                projects.save_state(p)
            all_requested = selected(p)
            complete = all(data['targets'].get(t, {}).get('status') == 'passed' for t in all_requested)
            requested_passed = all(data['targets'].get(t, {}).get('status') == 'passed' for t in proposal['requested_targets'])
            states=[t['status'] for t in data['targets'].values()]
            data['status'] = 'passed' if complete else 'candidate' if requested_passed or 'passed' in states or 'candidate' in states and 'failed' not in states else 'failed'
            data['validation']['complete'] = complete
            if complete:
                p['state']['safe_point'] = ident
            p['state']['issues'] = data['failures']
        except BaseException as exc:
            data['status'] = 'cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed'
            data['failures'].append(str(exc))
            p['state']['issues'] = data['failures']
        finally:
            default = next((t for t in proposal['requested_targets'] if t in data['targets']), None)
            if default:
                data['backends'] = data['targets'][default]['backends']
            write(out / 'run.json', data)
            projects.save_state(p)
        return data


def migrate(root, format_version=2):
    p = projects.load(root)
    if format_version not in (2, 3):
        raise ValueError('Migration targets format 2 or 3')
    current = p['config']['format_version']
    if current >= format_version:
        return {'status': 'unchanged', 'format_version': current}
    if current == 1:
        result = _migrate_v2(root)
        if format_version == 2:
            return result
    import re
    with exclusive(p['root'] / '.geometryforge'):
        p = projects.load(root)
        backup = p['root'] / '.geometryforge/migrations' / uuid.uuid4().hex[:12]
        backup.mkdir(parents=True)
        for name in ('project.toml', '.geometryforge/state.json'):
            if inside(p['root'], name).is_file():
                shutil.copy2(inside(p['root'], name), backup / Path(name).name)
        contract = p['root'] / 'project.toml'
        contract.write_text(re.sub(r'(?m)^(format_version[ \t]*=[ \t]*)2(?=[ \t]*(?:#.*)?$)', r'\g<1>3',
                                   contract.read_text(encoding='utf-8'), count=1), encoding='utf-8')
        write(p['root'] / '.geometryforge/state.json', {**p['state'], 'format_version': 3})
    return {'status': 'migrated', 'format_version': 3, 'backup': str(backup),
            'note': 'Format 3 enables [gates.*]. Every part must belong to a gate once gates are declared; '
                    'see geometryforge gate template.'}


def _migrate_v2(root):
    p = projects.load(root)
    with exclusive(p['root'] / '.geometryforge'):
        p = projects.load(root)
        backup = p['root'] / '.geometryforge/migrations' / uuid.uuid4().hex[:12]
        backup.mkdir(parents=True)
        for name in ('project.toml', 'decisions.json', '.geometryforge/state.json'):
            source = inside(p['root'], name)
            if source.is_file():
                dest = backup / Path(name).name
                shutil.copy2(source, dest)
        contract = p['root'] / 'project.toml'
        text = contract.read_text(encoding='utf-8')
        # Validate the parsed version rather than relying on a particular whitespace style.
        import re
        text = re.sub(r'(?m)^(format_version[ \t]*=[ \t]*)1(?=[ \t]*(?:#.*)?$)', r'\g<1>2', text, count=1)
        text += '\n[targets.print]\nchecks = ' + json.dumps(list(p['config'].get('checks', {}))) + '\n'
        contract.write_text(text, encoding='utf-8')
        decision = {**p['decisions'], 'output_targets': ['print']}
        write(p['root'] / 'decisions.json', decision)
        legacy = {k: deepcopy(p['state'].get(k)) for k in ('backends', 'safe_point')}
        state = {**p['state'], 'format_version': 2, 'targets': {'print': legacy},
                 'safe_points': {'print': p['state'].get('safe_point')} if p['state'].get('safe_point') else {}}
        write(p['root'] / '.geometryforge/state.json', state)
    return {'status': 'migrated', 'format_version': 2, 'backup': str(backup), 'note': 'Sources, scenes and retained runs preserved. Add a game recipe before deriving.'}


def validate_derivation(p, derivation):
    for artifact in derivation['artifacts']:
        if digest(inside(p['root'], artifact['path'])) != artifact['sha256']:
            raise ValueError('Frozen derivation artifact changed')


def derive(root, target, from_run, from_target, scale=1.0, backend=None, timeout=900, executables=None):
    from . import engine
    import math
    p = projects.load(root)
    if p['config']['format_version'] < 2:
        raise ValueError('Migrate this project to format 2 before deriving')
    if target not in ('print', 'game') or from_target not in ROUTES:
        raise ValueError('Invalid derivation route')
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Derivation scale must be positive and finite')
    spec = p['config'].get('targets', {}).get(target, {})
    if not spec.get('derivation_recipe'):
        raise ValueError('Declare targets.<target>.derivation_recipe and a target builder; derive never invents a conversion')
    base = engine.record(p, from_run)
    source = base.get('targets', {}).get(from_target) if base else None
    if source is None and base and from_target == 'print' and base.get('format_version') == 1:
        source = {'status': base['status'], 'backends': base['backends']}
    if not source or source['status'] != 'passed':
        raise ValueError('Derivation requires a validated retained source route')
    artifacts = []
    scenes = {}
    for name, info in source['backends'].items():
        scenes[name] = info['native']['path']
        artifacts.append(info['native'])
        for part in info['parts'].values():
            artifacts.extend(part['artifacts'])
        artifacts.extend(info.get('game', {}).get('artifacts', []))
    derivation = {'from_run': from_run, 'from_target': from_target, 'scale': scale,
                  'recipe': spec['derivation_recipe'], 'scenes': scenes, 'artifacts': artifacts,
                  'outputs':{b:{name:info['measurements'] for name,info in detail['parts'].items()} for b,detail in source['backends'].items()},
                  'notes': spec.get('conversion_notes', [])}
    validate_derivation(p, derivation)
    with exclusive(p['root'] / '.geometryforge'):
        decision = read(p['root'] / 'decisions.json')
        decision.setdefault('derivations', {})[target] = derivation
        write(p['root'] / 'decisions.json', decision)
    return execute(root, backend, full=False, source='code', target=target, timeout=timeout, executables=executables,
                   parts=list(route_view(projects.load(root), target)['config']['parts']))


def restore(root, ident=None, target=None):
    from . import engine
    p = projects.load(root)
    ident = ident or (p['state'].get('safe_points', {}).get(target) if target else p['state'].get('safe_point'))
    base = engine.record(p, ident)
    if not base:
        raise ValueError('No safe point is available')
    routes = base.get('targets', {})
    if not routes and base.get('format_version') == 1:
        routes = {'print': {'status': base['status'], 'backends': base['backends']}}
    chosen = [target] if target else [t for t, r in routes.items() if r['status'] == 'passed']
    if not chosen or any(routes.get(t, {}).get('status') != 'passed' for t in chosen):
        raise ValueError('Restore requires a passed target')
    with exclusive(p['root'] / '.geometryforge'):
        for name, sha in base['inputs'].items():
            if digest(inside(engine.run_path(p, ident) / 'inputs', name)) != sha:
                raise ValueError('Retained snapshot changed')
        for route in chosen:
            for info in routes[route]['backends'].values():
                if not engine.artifact_ok(p, info['native']):
                    raise ValueError('Retained native scene changed')
        dest = p['root'] / 'working' / ('restore-' + uuid.uuid4().hex[:12])
        shutil.copytree(engine.run_path(p, ident) / 'inputs', dest / 'sources')
        for route in chosen:
            for backend, info in routes[route]['backends'].items():
                original = inside(p['root'], info['native']['path'])
                native = dest / route / backend / original.name
                native.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, native)
    return {'restored_from': ident, 'targets': chosen, 'working_copy': str(dest), 'note': 'Current scenes and sources preserved; use adopt --target to select a restored scene.'}


def adopt(root, backend, file, target):
    from . import engine
    p = projects.load(root)
    if target not in p['config'].get('targets', {}):
        raise ValueError('Select a declared output target')
    with exclusive(p['root'] / '.geometryforge'):
        p = projects.load(root)
        source = Path(file).resolve()
        allowed = ('.blend',) if backend == 'blender' else ('.hip', '.hipnc', '.hiplc')
        if not source.is_file() or source.suffix.lower() not in allowed:
            raise ValueError('Missing or incompatible native file')
        dest = p['root'] / 'working' / ('import-' + uuid.uuid4().hex[:12]) / target / source.name
        dest.parent.mkdir(parents=True)
        before = digest(source)
        shutil.copy2(source, dest)
        if digest(dest) != before or digest(source) != before:
            raise ValueError('Source changed during import')
        state = p['state'].setdefault('targets', {}).setdefault(target, {'backends': {}, 'safe_point': None})
        state['backends'][backend] = {**state['backends'].get(backend, {}), 'working': str(dest.relative_to(p['root'])), 'working_hash': None}
        projects.save_state(p)
    return context(root)
