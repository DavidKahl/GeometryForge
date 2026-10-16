import numpy as np
import pytest
import trimesh

from geometryforge import backends, engine, gates, projects, targets
from geometryforge.storage import digest, inside, read, write
from surfacing_fixtures import closed_sphere, obj, panels

CONTRACT = '''format_version = 3
[project]
id = "fixture"
[backends.blender]
entry = "models/entry.py"
[parts.hull]
sources = ["models/a.py"]
[parts.front]
sources = ["models/b.py"]
parameters = ["lift"]
depends = ["hull"]
[parts.skirt]
sources = ["models/b.py"]
parameters = ["lift"]
depends = ["hull"]
[parts.bolt]
sources = ["models/b.py"]
[checks.hull_closed]
kind = "global"
parts = ["hull"]
[checks.hull_closed.spec]
test = "open_edges"
targets = [{part = "hull", roles = ["guide"]}]
[checks.seam]
kind = "seam"
parts = ["front", "skirt", "hull"]
[checks.seam.spec]
a = {part = "front"}
b = {part = "skirt"}
master = {part = "hull"}
[targets.design]
[targets.game]
[gates.master]
order = 0
parts = ["hull"]
checks = ["hull_closed"]
[gates.master.review]
modes = ["zebra"]
min_views = 2
[gates.panels]
order = 1
parts = ["front", "skirt"]
checks = ["seam"]
[gates.detail]
order = 2
parts = ["bolt"]
'''


@pytest.fixture
def gated(project, monkeypatch):
    root, calls = project
    (root / 'project.toml').write_text(CONTRACT, encoding='utf-8')
    write(root / 'parameters.json', {'lift': 0.0})
    decisions = read(root / 'decisions.json')
    decisions.update(output_targets=['game'], game={'profile': 'unreal_desktop_standard'})
    write(root / 'decisions.json', decisions)

    def native(backend, out, entry, parameters, parts, source, timeout, executable):
        context = backends.native_context.get()
        calls.append({'backend': backend, 'target': context.get('target'), 'parts': list(parts)})
        objects = read(source, []) if source else []
        (A, B) = panels(lift=parameters['lift'])
        made = {'hull': lambda: [obj('Master hull', 'hull', *closed_sphere(), 'guide')],
                'front': lambda: [obj('Front', 'front', *A)], 'skirt': lambda: [obj('Skirt', 'skirt', *B)],
                'bolt': lambda: [obj('Bolt', 'bolt', trimesh.creation.box([5, 5, 5]).vertices, trimesh.creation.box([5, 5, 5]).faces)]}
        for part in parts:
            objects = [o for o in objects if o['part'] != part] + made[part]()
        scene = out / 'model.blend'
        write(scene, objects)
        return {'version': 'fixture-gates', 'scene': str(scene), 'objects': objects}
    monkeypatch.setattr(backends, 'run_native', native)
    return root, calls


def design_run(root, **kw):
    return engine.execute(root, target='design', **kw)['targets']['design']


def fake_review(root, views=2, modes=('zebra', 'clay'), metrics=None):
    p = projects.load(root)
    safe = p['state']['targets']['design']['safe_point']
    native = engine.record(p, safe)['targets']['design']['backends']['blender']['native']
    count = len(list((root / 'review').glob('*'))) if (root / 'review').exists() else 0
    folder = root / 'review' / f'20990101T0000{count:02d}Z-0000beef'  # newest review wins
    folder.mkdir(parents=True)
    write(folder / 'report.json', {'version': 1, 'review_id': folder.name, 'status': 'complete', 'scene_sha256': native['sha256'],
                                   'config_sha256': 'x', 'metrics': metrics or {},
                                   'views': [{'id': f'v{i}', 'artifacts': {m: 'x.png' for m in modes}} for i in range(views)]})


def accept(root, gate):
    return gates.accept(root, gate, 'Dave', 'Dave: "accepted, go ahead"')


def test_only_the_active_gate_is_built(gated):
    root, calls = gated
    route = design_run(root)
    assert route['status'] == 'passed', route['failures']
    assert calls[-1]['parts'] == ['hull']
    assert set(route['backends']['blender']['geometry']) == {'hull'}
    assert route['gates']['active'] == 'master' and route['gates']['dormant'] == ['bolt', 'front', 'skirt']
    check = route['backends']['blender']['checks']['hull_closed']
    assert check['kind'] == 'global' and check['measurements']['open_edges'] == 0
    context = engine.context(root)
    assert context['gates']['active_gate'] == 'master'
    assert any("Gate 'master' is active" in issue for issue in context['issues'])


def test_later_parts_refused_before_running(gated):
    root, calls = gated
    with pytest.raises(ValueError, match="accept gate 'master' first"):
        engine.plan(root, parts=['front'], target='design')
    with pytest.raises(ValueError):
        engine.execute(root, parts=['bolt'], target='design')
    assert not calls


def test_acceptance_requires_safe_point_checks_and_review(gated):
    root, _ = gated
    assert 'No passed design safe point' in ' '.join(gates.check(root, 'master')['failures'])
    design_run(root)
    blocked = gates.check(root, 'master')
    assert not blocked['ready'] and any('No complete review' in f for f in blocked['failures'])
    with pytest.raises(ValueError, match='not ready'):
        accept(root, 'master')
    fake_review(root, views=1)
    assert any('needs 2' in f for f in gates.check(root, 'master')['failures'])
    fake_review(root, views=2, modes=('clay',))
    assert any('lacks modes' in f for f in gates.check(root, 'master')['failures'])
    fake_review(root, views=3)
    assert gates.check(root, 'master')['ready']
    with pytest.raises(ValueError, match='--note'):
        gates.accept(root, 'master', 'Dave', ' ')
    result = accept(root, 'master')
    assert result['next'] == 'panels'
    record = read(root / f'.geometryforge/gates/master/{result["acceptance"]}.json')
    assert record['accepted_by'] == 'Dave' and set(record['backends']['blender']['geometry']) == {'hull'}
    assert record['checks']['blender/hull_closed']['acceptance']['met']
    assert record['review']['views'] == 3


def test_gate_review_iou_minimum_overrides_the_project_default(gated):
    root, _ = gated
    contract = CONTRACT.replace('min_views = 2', 'min_views = 2\niou_views = ["v0"]')
    (root / 'project.toml').write_text(contract, encoding='utf-8')
    design_run(root)
    fake_review(root, metrics={'v0': {'silhouette_iou': 0.85}})
    assert any('silhouette IoU 0.850 below 0.9' in f for f in gates.check(root, 'master')['failures'])
    (root / 'project.toml').write_text(contract.replace('iou_views', 'iou_min = 0.8\niou_views'), encoding='utf-8')
    assert gates.check(root, 'master')['ready']
    (root / 'project.toml').write_text(contract.replace('iou_views', 'iou_min = 1.5\niou_views'), encoding='utf-8')
    with pytest.raises(ValueError, match='iou_min'):
        projects.load(root)


def accept_master(root):
    design_run(root)
    fake_review(root)
    accept(root, 'master')


def test_accepting_opens_the_next_gate_and_locks_geometry(gated):
    root, calls = gated
    accept_master(root)
    assert engine.context(root)['targets']['design']['stale']
    route = design_run(root)
    assert route['status'] == 'passed', route['failures']
    assert sorted(calls[-1]['parts']) == ['front', 'skirt']
    seam = route['backends']['blender']['checks']['seam']
    assert seam['acceptance']['met'] and 2.9 < seam['measurements']['gap_min_mm']
    with pytest.raises(ValueError, match='locked by accepted gate'):
        engine.plan(root, parts=['hull'], target='design')


def test_native_edit_of_locked_geometry_is_a_candidate(gated):
    root, _ = gated
    accept_master(root)
    design_run(root)
    p = projects.load(root)
    working = inside(root, p['state']['targets']['design']['backends']['blender']['working'])
    objects = read(working)
    hull = next(o for o in objects if o['part'] == 'hull')
    hull['vertices'][0][2] += 25
    write(working, objects)
    route = design_run(root, source='scene')
    assert route['status'] == 'candidate'
    assert any('Locked geometry' in f and 'hull' in f for f in route['failures'])


def test_enforced_seam_failure_keeps_measurements(gated):
    root, _ = gated
    accept_master(root)
    write(root / 'parameters.json', {'lift': 1.0})
    route = design_run(root)
    assert route['status'] == 'failed'
    seam = route['backends']['blender']['checks']['seam']
    assert not seam['passed'] and not seam['acceptance']['met']
    assert any('Seam step' in f for f in seam['acceptance']['failures']) and seam['worst']


def test_thresholds_are_check_inputs(gated):
    root, _ = gated
    accept_master(root)
    first = design_run(root)['backends']['blender']['checks']['seam']
    params = read(root / 'parameters.json')
    again = design_run(root, source='scene')['backends']['blender']['checks']['seam']
    assert again['reused'] and again['key'] == first['key']
    params['gf_thresholds'] = {'seam': {'gap_max_mm': 3.5}}
    write(root / 'parameters.json', params)
    changed = design_run(root, source='scene')['backends']['blender']['checks']['seam']
    assert not changed['reused'] and changed['thresholds']['gap_max_mm'] == 3.5


def test_reopen_supersedes_later_gates_and_tolerates_dormant_objects(gated):
    root, calls = gated
    accept_master(root)
    design_run(root)
    # panels has no review requirement; accept it to make detail active.
    accept(root, 'panels')
    assert gates.status(root)['active_gate'] == 'detail'
    reopened = gates.reopen(root, 'master', 'Dave', 'roof roll is wrong')
    assert reopened['superseded'] == ['panels']
    status = gates.status(root)
    assert status['active_gate'] == 'master' and status['dormant_parts'] == ['bolt', 'front', 'skirt']
    route = design_run(root, source='scene')
    assert route['status'] == 'passed', route['failures']
    assert set(route['backends']['blender']['geometry']) == {'hull'}


def test_dependent_routes_wait_for_the_final_gate(gated):
    root, _ = gated
    result = engine.execute(root, target='game')
    assert result['targets']['design']['status'] == 'passed'
    assert result['targets']['game']['status'] == 'candidate'
    assert 'gates are incomplete' in result['targets']['game']['failures'][0]


@pytest.mark.parametrize('edit,message', [
    (lambda t: t.replace('format_version = 3', 'format_version = 2'), 'format_version = 3'),
    (lambda t: t.replace('parts = ["bolt"]', 'parts = ["front"]'), 'belongs to gates'),
    (lambda t: t.replace('[gates.detail]\norder = 2\nparts = ["bolt"]\n', ''), 'unassigned'),
    (lambda t: t.replace('order = 2', 'order = 5'), 'orders'),
    (lambda t: t.replace('[parts.hull]\nsources = ["models/a.py"]', '[parts.hull]\nsources = ["models/a.py"]\ndepends = ["front"]'), 'later gate'),
])
def test_invalid_gate_contracts(gated, edit, message):
    root, _ = gated
    (root / 'project.toml').write_text(edit(CONTRACT), encoding='utf-8')
    with pytest.raises(ValueError, match=message):
        projects.load(root)


def test_calibration_gate_needs_a_current_calibrated_camera(gated):
    from test_camera import correspondence_project
    from geometryforge import camera
    root, _ = gated
    text = CONTRACT.replace('[gates.master]\norder = 0', '[gates.calibration]\norder = 0\nkind = "calibration"\ncameras = ["primary"]\n[gates.master]\norder = 1')
    text = text.replace('[gates.panels]\norder = 1', '[gates.panels]\norder = 2').replace('[gates.detail]\norder = 2', '[gates.detail]\norder = 3')
    (root / 'project.toml').write_text(text, encoding='utf-8')
    params = read(root / 'parameters.json')
    correspondence_project((root, None))
    assert gates.status(root)['active_gate'] == 'calibration'
    assert any('not calibrated' in f for f in gates.check(root, 'calibration')['failures'])
    camera.calibrate(root)
    ready = gates.check(root, 'calibration')
    assert ready['ready'], ready['failures']
    assert ready['evidence']['calibration']['cameras']['primary']['rms_px'] < 1e-3
    (root / 'references/front.png').write_bytes((root / 'references/front.png').read_bytes() + b'x')
    assert any('stale' in f for f in gates.check(root, 'calibration')['failures'])


def test_migrate_to_format_three(project):
    root, _ = project
    result = targets.migrate(root, 3)
    assert result['format_version'] == 3
    p = projects.load(root)
    assert p['config']['format_version'] == 3 and p['state']['format_version'] == 3
    assert targets.migrate(root, 3)['status'] == 'unchanged'
