"""Toolkit-enforced modeling gates (project format 3).

Gates are ordered stages: calibration, then geometry gates such as master hull, panels and
detail. Only accepted gates plus the active gate are buildable (the frontier); later parts
stay dormant. Accepting a gate records its evidence and locks its geometry.
"""
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid

from . import projects
from .locking import exclusive
from .storage import digest, inside, read, write
from .thresholds import resolve as thresholds

# run --rebuild-accepted: reproduce locked parts from code instead of refusing them.
rebuild_accepted = ContextVar('geometryforge_rebuild_accepted', default=False)

KINDS = ('calibration', 'geometry')
TEMPLATE = '''format_version = 3

[gates.calibration]
order = 0
kind = "calibration"
cameras = ["primary"]

[gates.master]
order = 1
parts = ["master_hull"]
checks = ["master_closed", "master_silhouette"]
[gates.master.review]
config = "reviews/master.json"
modes = ["zebra", "silhouette", "overlay"]
iou_views = ["primary"]

[gates.panels]
order = 2
parts = ["front_body", "cabin", "skirt", "roof"]
checks = ["seam_front_skirt", "recess_lamps", "coverage_hull"]
[gates.panels.review]
config = "reviews/panels.json"
modes = ["zebra", "glossy", "silhouette"]

[gates.detail]
order = 3
parts = ["engines", "pads", "chassis"]
checks = ["mating_engine_left"]
'''


def declared(p):
    return p['config'].get('gates', {})


def ordered(p):
    return sorted(declared(p).items(), key=lambda item: item[1]['order'])


def route(p):
    targets = p['config'].get('targets', {})
    return 'design' if 'design' in targets else p['decisions'].get('output_targets', ['print'])[0]


def validate(p):
    gates = declared(p)
    if not gates:
        return
    if not isinstance(gates, dict):
        raise ValueError('gates must be a table of named gates')
    parts = p['config'].get('parts', {})
    checks = p['config'].get('checks', {})
    if sorted(g.get('order') for g in gates.values() if isinstance(g, dict)) != list(range(len(gates))):
        raise ValueError('Gate orders must be the integers 0..n-1')
    gate_route = route(p)
    if gate_route not in p['config'].get('targets', {}):
        raise ValueError(f'Gates run on the {gate_route} route; declare [targets.{gate_route}]')
    owner = {}
    for name, gate in ordered(p):
        if not projects.ID.fullmatch(name):
            raise ValueError(f'Invalid gate ID: {name}')
        gate.setdefault('kind', 'geometry')
        if gate['kind'] not in KINDS:
            raise ValueError(f'Gate {name}: kind must be calibration or geometry')
        if gate['kind'] == 'calibration':
            if gate.get('parts') or not isinstance(gate.get('cameras'), list) or not gate['cameras']:
                raise ValueError(f'Calibration gate {name} needs cameras and no parts')
            continue
        members = gate.get('parts')
        if not isinstance(members, list) or not members or set(members) - parts.keys():
            raise ValueError(f'Gate {name} needs declared parts')
        for part in members:
            if part in owner:
                raise ValueError(f'Part {part} belongs to gates {owner[part]} and {name}')
            owner[part] = name
        gate.setdefault('lock', list(members))
        if set(gate['lock']) - set(members):
            raise ValueError(f'Gate {name} can only lock its own parts')
        if set(gate.get('checks', [])) - checks.keys():
            raise ValueError(f'Gate {name} references undeclared checks')
        for check in gate.get('checks', []):
            spec = checks[check]
            if spec.get('kind') and 'targets' not in spec:
                spec['targets'] = [gate_route]
            if gate_route not in spec.get('targets', ['print', 'game']):
                raise ValueError(f'Gate check {check} must run on the {gate_route} route (targets = ["{gate_route}"])')
        review = gate.get('review')
        if review is not None:
            from .review import MODES
            if not isinstance(review, dict) or set(review.get('modes', [])) - set(MODES) or not isinstance(review.get('iou_views', []), list):
                raise ValueError(f'Gate {name}: invalid review requirement')
            if 'config' in review and not inside(p['root'], review['config']).is_file():
                raise ValueError(f'Gate {name}: missing review config {review["config"]}')
            if 'min_views' in review and (type(review['min_views']) is not int or review['min_views'] < 1):
                raise ValueError(f'Gate {name}: min_views must be a positive integer')
            if 'iou_min' in review and (type(review['iou_min']) not in (int, float) or not 0 < review['iou_min'] <= 1):
                raise ValueError(f'Gate {name}: iou_min must be a number in (0, 1]')
    if set(parts) - owner.keys():
        raise ValueError(f'Every part needs a gate; unassigned: {sorted(set(parts) - owner.keys())}')
    order = {name: gate['order'] for name, gate in gates.items()}
    for part, spec in parts.items():
        for dependency in spec.get('depends', []):
            if order[owner[dependency]] > order[owner[part]]:
                raise ValueError(f'Part {part} cannot depend on {dependency} from the later gate {owner[dependency]}')


def acceptance(p, name, ident):
    return read(p['root'] / '.geometryforge/gates' / name / f'{ident}.json')


def frontier(p):
    """Active gate, buildable parts, dormant parts and locked geometry hashes."""
    states = p['state'].get('gates', {})
    active, accepted, buildable, dormant, locked, owner = None, [], set(), set(), {}, {}
    for name, gate in ordered(p):
        members = gate.get('parts', [])
        for part in members:
            owner[part] = name
        if active is None and states.get(name, {}).get('status') == 'accepted':
            accepted.append(name)
            buildable.update(members)
            record = acceptance(p, name, states[name]['acceptance'])
            for part in gate.get('lock', members):
                locked[part] = {b: info['geometry'][part] for b, info in record.get('backends', {}).items() if part in info.get('geometry', {})}
        elif active is None:
            active = name
            buildable.update(members)
        else:
            dormant.update(members)
    return {'route': route(p), 'active': active, 'accepted': accepted, 'frontier': sorted(buildable),
            'dormant': sorted(dormant), 'locked': locked, 'owner': owner, 'complete': active is None}


def require_buildable(p, parts):
    """Refuse explicit selections of dormant or locked parts before anything runs.

    With rebuild_accepted set, locked parts may be rebuilt from code: the engine's lock check then requires the
    accepted geometry hash exactly, so any difference leaves a candidate and the acceptance untouched."""
    if not declared(p) or not parts:
        return
    state = frontier(p)
    for part in parts:
        if part in state['dormant']:
            raise ValueError(f"Part {part} belongs to gate '{state['owner'][part]}'; accept gate '{state['active']}' first")
        if part in state['locked'] and not rebuild_accepted.get():
            raise ValueError(f"Part {part} is locked by accepted gate '{state['owner'][part]}'; "
                             f"run geometryforge gate reopen {state['owner'][part]} to change it deliberately")


def _review_evidence(p, gate, scene_sha):
    from .review import MODES
    requirement = gate.get('review')
    if requirement is None:
        return None, []
    limits = thresholds(p['parameters'], 'review')
    minimum = requirement.get('min_views', int(limits['min_views']))
    config_sha = digest(inside(p['root'], requirement['config'])) if 'config' in requirement else None
    candidates = []
    for path in sorted((p['root'] / 'review').glob('*/report.json'), reverse=True):
        report = read(path, {})
        if report.get('status') == 'complete' and report.get('scene_sha256') == scene_sha and \
                (config_sha is None or report.get('config_sha256') == config_sha):
            candidates.append((path, report))
    if not candidates:
        return None, ['No complete review of the safe-point scene' + (f' with {requirement["config"]}' if config_sha else '')]
    path, report = candidates[0]
    failures = []
    views = report.get('views', [])
    if len(views) < minimum:
        failures.append(f'Review {report["review_id"]} has {len(views)} views; the gate needs {minimum}')
    rendered = {mode for view in views for mode in view.get('artifacts', {})}
    missing = set(requirement.get('modes', [])) - rendered
    if missing:
        failures.append(f'Review {report["review_id"]} lacks modes {sorted(missing)}')
    # A gate may score its review below the project default, e.g. before later gates add parts the masks include.
    minimum_iou = requirement.get('iou_min', thresholds(p['parameters'], 'global')['silhouette_iou_min'])
    metrics = report.get('metrics', {})
    for view in requirement.get('iou_views', []):
        iou = metrics.get(view, {}).get('silhouette_iou')
        if iou is None:
            failures.append(f'Review view {view} has no calibrated silhouette IoU')
        elif iou < minimum_iou:
            failures.append(f'Review view {view} silhouette IoU {iou:.3f} below {minimum_iou}')
    evidence = {'review_id': report['review_id'], 'report': str(path.relative_to(p['root'])).replace('\\', '/'),
                'report_sha256': digest(path), 'scene_sha256': scene_sha, 'config_sha256': report.get('config_sha256'),
                'views': len(views), 'metrics': {v: metrics[v] for v in requirement.get('iou_views', []) if v in metrics}}
    return evidence, failures


def check(root, name):
    """Read-only readiness of one gate: evidence it would record and what still blocks it."""
    from . import camera, engine, targets
    p = projects.load(root)
    gates = declared(p)
    if name not in gates:
        raise ValueError(f'Unknown gate: {name}')
    gate = gates[name]
    state = frontier(p)
    failures = []
    earlier = [g for g, spec in ordered(p) if spec['order'] < gate['order'] and g not in state['accepted']]
    if earlier:
        failures.append(f'Earlier gates not accepted: {earlier}')
    if p['state'].get('gates', {}).get(name, {}).get('status') == 'accepted':
        failures.append(f'Gate {name} is already accepted; reopen it to accept new evidence')
    evidence = {'gate': name, 'order': gate['order'], 'kind': gate['kind']}
    if gate['kind'] == 'calibration':
        cameras = camera.load_cameras(p['root'])
        limit = thresholds(p['parameters'], 'calibration')['max_rms_px']
        recorded = {}
        for ident in gate['cameras']:
            entry = cameras.get(ident)
            if not entry:
                failures.append(f'Camera {ident} is not calibrated; run geometryforge calibrate')
                continue
            if entry.get('status') != 'calibrated' or entry.get('rms_px', float('inf')) > limit:
                failures.append(f'Camera {ident} is {entry.get("status")} (rms {entry.get("rms_px")} px, limit {limit})')
            if not camera.camera_current(p['root'], entry):
                failures.append(f'Camera {ident} is stale: its image, mask or correspondences changed')
            recorded[ident] = {k: entry.get(k) for k in ('rms_px', 'max_px', 'image', 'image_sha256', 'mask', 'mask_sha256', 'correspondences_sha256')}
        evidence['calibration'] = {'cameras': recorded, 'cameras_sha256': digest(p['root'] / 'references/cameras.json')
                                   if (p['root'] / 'references/cameras.json').is_file() else None, 'max_rms_px': limit}
        return {'gate': name, 'ready': not failures, 'failures': failures, 'evidence': evidence}
    final = max((spec['order'] for _, spec in ordered(p) if spec['kind'] == 'geometry'), default=None)
    if gate['order'] == final and not any(p['config'].get('checks', {}).get(c, {}).get('kind') == 'detail' for c in gate.get('checks', [])):
        # Surface checks alone let detail silently fall away; the last geometry gate must measure it.
        failures.append(f'Final geometry gate {name} declares no detail check; add a kind = "detail" check with the accepted '
                        'detail inventory (see the skill reference checks.md)')
    gate_route = route(p)
    view = targets.baseline_view(p, gate_route)
    safe = view['state'].get('safe_point')
    key = targets.route_key(p, gate_route)
    evidence.update(route=gate_route, run=safe, backends={}, checks={})
    if not safe:
        failures.append(f'No passed {gate_route} safe point; run geometryforge run --target {gate_route}')
        return {'gate': name, 'ready': False, 'failures': failures, 'evidence': evidence}
    run = engine.record(p, safe).get('targets', {}).get(gate_route, {})
    for backend in engine.selected_backends(view):
        current = view['state']['backends'].get(backend, {})
        info = run.get('backends', {}).get(backend)
        if not info or current.get('run') != safe:
            failures.append(f'{backend}: the safe point does not hold this backend\'s latest run')
            continue
        working = inside(p['root'], current['working']) if current.get('working') else None
        if working and (not working.is_file() or digest(working) != current.get('working_hash')):
            failures.append(f'{backend}: the working scene changed after the safe point; verify it first')
        if current.get('route_key') != key:
            failures.append(f'{backend}: project inputs changed after the safe point; run again')
        missing = set(gate['parts']) - info.get('geometry', {}).keys()
        if missing:
            failures.append(f'{backend}: safe point lacks parts {sorted(missing)}')
        evidence['backends'][backend] = {'native_sha256': info['native']['sha256'], 'native': info['native']['path'],
                                         'geometry': {part: info['geometry'][part] for part in gate['parts'] if part in info.get('geometry', {})}}
        for ident in gate.get('checks', []):
            result = info.get('checks', {}).get(ident)
            if not result or not result.get('passed'):
                failures.append(f'{backend}: check {ident} has not passed in the safe point')
                continue
            if not result.get('acceptance', {}).get('met', True):
                failures.append(f'{backend}: check {ident} misses its thresholds: ' + '; '.join(result['acceptance']['failures']))
            evidence['checks'][f'{backend}/{ident}'] = {k: result.get(k) for k in ('kind', 'mode', 'measurements', 'acceptance', 'thresholds', 'key')}
    if gate.get('review'):
        scene = evidence['backends'].get('blender', {}).get('native_sha256')
        if scene is None:
            failures.append('Gate reviews render the Blender safe-point scene; this route has no Blender output')
        else:
            review, problems = _review_evidence(p, gate, scene)
            failures += problems
            evidence['review'] = review
    return {'gate': name, 'ready': not failures, 'failures': failures, 'evidence': evidence}


def accept(root, name, by, note, critique=None):
    """Record an approved gate. Only run after the person explicitly approved the evidence."""
    if not by or not by.strip() or not note or not note.strip():
        raise ValueError('Gate acceptance needs --by and a --note quoting the approval')
    p = projects.load(root)
    with exclusive(p['root'] / '.geometryforge'):
        result = check(root, name)
        if not result['ready']:
            raise ValueError(f'Gate {name} is not ready: ' + '; '.join(result['failures']))
        p = projects.load(root)
        stamp = datetime.now(timezone.utc)
        ident = stamp.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        folder = p['root'] / '.geometryforge/gates' / name
        folder.mkdir(parents=True, exist_ok=True)
        record = {'version': 1, 'id': ident, **result['evidence'], 'accepted_by': by.strip(),
                  'accepted_at': stamp.isoformat(), 'note': note.strip(), 'toolkit': projects_version()}
        if critique:
            source = Path(critique).resolve()  # CLI path, relative to the calling directory
            if not source.is_file():
                raise ValueError(f'Missing critique file: {critique}')
            copy = folder / f'{ident}-critique{source.suffix or ".md"}'
            shutil.copy2(source, copy)
            record['critique'] = {'path': str(copy.relative_to(p['root'])).replace('\\', '/'), 'sha256': digest(copy)}
        write(folder / f'{ident}.json', record)
        gates = p['state'].setdefault('gates', {})
        history = gates.get(name, {}).get('history', [])
        gates[name] = {'status': 'accepted', 'acceptance': ident, 'accepted_by': record['accepted_by'],
                       'accepted_at': record['accepted_at'], 'history': history + [{'event': 'accepted', 'id': ident, 'at': record['accepted_at']}]}
        projects.save_state(p)
    return {'status': 'accepted', 'gate': name, 'acceptance': ident, 'record': str(folder / f'{ident}.json'),
            'next': frontier(projects.load(root))['active']}


def reopen(root, name, by, reason):
    """Reopen an accepted gate; it and every later accepted gate need acceptance again."""
    if not by or not reason:
        raise ValueError('Reopening a gate needs --by and --reason')
    p = projects.load(root)
    gates = declared(p)
    if name not in gates:
        raise ValueError(f'Unknown gate: {name}')
    with exclusive(p['root'] / '.geometryforge'):
        p = projects.load(root)
        states = p['state'].setdefault('gates', {})
        if states.get(name, {}).get('status') != 'accepted':
            raise ValueError(f'Gate {name} is not accepted')
        stamp = datetime.now(timezone.utc).isoformat()
        affected = []
        for gate, spec in ordered(p):
            if spec['order'] >= gates[name]['order'] and states.get(gate, {}).get('status') == 'accepted':
                entry = states[gate]
                event = {'event': 'reopened' if gate == name else 'superseded', 'id': entry['acceptance'], 'at': stamp,
                         'by': by, 'reason': reason}
                states[gate] = {'status': 'open' if gate == name else 'superseded', 'acceptance': None,
                                'history': entry.get('history', []) + [event]}
                affected.append(gate)
        projects.save_state(p)
    return {'status': 'reopened', 'gate': name, 'superseded': affected[1:],
            'note': 'Acceptance records are retained. Locks are released until the gates are accepted again.'}


def status(root):
    p = projects.load(root)
    if not declared(p):
        return {'gates': [], 'note': 'No gates declared (format 3 projects declare [gates.*])'}
    state = frontier(p)
    states = p['state'].get('gates', {})
    rows = [{'gate': name, 'order': gate['order'], 'kind': gate['kind'], 'parts': gate.get('parts', []),
             'status': 'active' if name == state['active'] else states.get(name, {}).get('status', 'pending'),
             'acceptance': states.get(name, {}).get('acceptance')} for name, gate in ordered(p)]
    return {'route': state['route'], 'active_gate': state['active'], 'gates': rows, 'dormant_parts': state['dormant'],
            'locked_parts': sorted(state['locked']), 'complete': state['complete']}


def template():
    return {'template': TEMPLATE, 'note': 'Paste into project.toml, rename parts and checks to match your project, '
            'then declare the typed checks each gate lists. See the skill reference gates.md.'}


def projects_version():
    from . import __version__
    return __version__
