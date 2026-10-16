"""Opt-in native test: drive the dedicated surfacing fixture through all three gates in real Blender."""
import os
from pathlib import Path
import shutil

import pytest

from geometryforge import engine, gates, projects, review

pytestmark = pytest.mark.skipif(os.environ.get('GEOMETRYFORGE_RUN_NATIVE_SURFACING') != '1',
                                reason='Set GEOMETRYFORGE_RUN_NATIVE_SURFACING=1 and GEOMETRYFORGE_BLENDER for the native surfacing fixture')

FIXTURE = Path(__file__).resolve().parents[1] / 'tools/fixtures/surfacing_project'


def design(root, **kw):
    route = engine.execute(root, target='design', timeout=1500, **kw)['targets']['design']
    assert route['status'] == 'passed', route['failures']
    return route['backends']['blender']


def met(backend, *names):
    for name in names:
        check = backend['checks'][name]
        assert check['acceptance']['met'], (name, check['acceptance'], check['measurements'])
    return {name: backend['checks'][name]['measurements'] for name in names}


def test_gated_master_hull_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'catalog')
    root = tmp_path / 'surfacing_project'
    shutil.copytree(FIXTURE, root)

    first = design(root)
    assert set(first['geometry']) == {'master_hull'}
    met(first, 'master_closed')
    scene = root / first['native']['path']
    report = review.execute(root, scene, root / 'reviews/master.json', timeout=900)
    assert len(report['views']) == 6 and report['status'] == 'complete'
    assert gates.check(root, 'master')['ready']
    gates.accept(root, 'master', 'native test', 'fixture acceptance')
    with pytest.raises(ValueError, match='locked'):
        engine.plan(root, parts=['master_hull'], target='design')

    panels = design(root)
    assert set(panels['geometry']) == {'master_hull', 'body', 'skirt', 'vent'}
    measured = met(panels, 'seam_body_skirt', 'coverage_hull', 'recess_vent')
    seam = measured['seam_body_skirt']
    assert seam['step_max_mm'] < .01 and seam['master_deviation_max_mm'] < .01
    # The vent well crosses the body/skirt seam: its own panel, flush rim, closed floor below the skin.
    assert measured['recess_vent']['proud_vertices'] == 0
    gates.accept(root, 'panels', 'native test', 'fixture acceptance')

    detail = design(root)
    measured = met(detail, 'recess_lamp', 'mating_lens', 'detail_fasteners')
    assert measured['recess_lamp']['proud_vertices'] == 0
    assert measured['mating_lens']['skin_crossings'] == 0
    bolts = measured['detail_fasteners']['items']['roof_bolts']
    assert bolts['count'] == 6 and bolts['floating'] == 0 and 3 <= bolts['relief_mm'][0]
    assert gates.status(root)['active_gate'] == 'detail'

    again = design(root, source='scene')
    assert again['geometry'] == detail['geometry']
    assert all(check['reused'] for check in again['checks'].values())


HOUDINI_RECIPE = '''
from geometryforge import houdini_scene as s


def node(name, kind, **parms):
    geo = s.new_geo(name)
    source = geo.createNode(kind, 'source')
    for key, value in parms.items():
        source.parm(key).set(value)
    return geo, source


def build_parts(parameters, parts, api):
    for part in parts:
        api.begin(part)
        if part == 'socket':
            geo, sphere = node('master_hull', 'sphere', type='poly', radx=200, rady=200, radz=200, freq=6)
            api.register_output(s.Part('master_hull', geo, sphere, 'guide'), 'socket', 'guide')
            geo, circle = node('parent_ring', 'circle', type='poly', orient='xy', divs=64, radx=50, rady=50)
            api.register_output(s.Part('parent_ring', geo, circle, 'interface'), 'socket', 'interface', axis=[0, 0, 1])
        elif part == 'plug':
            geo, circle = node('child_ring', 'circle', type='poly', orient='xy', divs=64, radx=50, rady=50, tz=parameters['lap_mm'])
            api.register_output(s.Part('child_ring', geo, circle, 'interface'), 'plug', 'interface', axis=[0, 0, 1])
'''

HOUDINI_CONTRACT = '''format_version = 2
[project]
id = "houdini_evidence"
[backends.houdini]
entry = "models/houdini.py"
[parts.socket]
sources = ["models/houdini.py"]
[parts.plug]
sources = ["models/houdini.py"]
parameters = ["lap_mm"]
depends = ["socket"]
[checks.closed]
kind = "global"
parts = ["socket"]
targets = ["design"]
[checks.closed.spec]
test = "open_edges"
targets = [{part = "socket", roles = ["guide"]}]
[checks.mate]
kind = "mating"
parts = ["socket", "plug"]
targets = ["design"]
[checks.mate.spec]
parent = {part = "socket", objects = ["parent_ring"]}
child = {part = "plug", objects = ["child_ring"]}
[checks.mate.thresholds]
lap_min_mm = 47.5
lap_max_mm = 48.5
[targets.design]
[targets.game]
'''


@pytest.mark.skipif(not os.environ.get('GEOMETRYFORGE_HOUDINI'), reason='Set GEOMETRYFORGE_HOUDINI for the Houdini evidence test')
def test_houdini_guide_and_interface_evidence(tmp_path, monkeypatch):
    from geometryforge.storage import write
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'catalog')
    root = tmp_path / 'houdini_evidence'
    projects.initialize(root, ident='houdini_evidence', deliverables='houdini', backend='houdini', target='game', brief='Houdini evidence fixture')
    (root / 'models').mkdir()
    (root / 'models/houdini.py').write_text(HOUDINI_RECIPE, encoding='utf-8')
    (root / 'project.toml').write_text(HOUDINI_CONTRACT, encoding='utf-8')
    write(root / 'parameters.json', {'lap_mm': 48.0})
    route = engine.execute(root, target='design', timeout=900)['targets']['design']
    assert route['status'] == 'passed', route['failures']
    checks = route['backends']['houdini']['checks']
    assert checks['closed']['measurements']['open_edges'] == 0
    mate = checks['mate']['measurements']
    assert mate['lap_mm'] == pytest.approx(48, abs=1e-3) and mate['axis_deg'] < 1e-3 and mate['oriented']
    write(root / 'parameters.json', {'lap_mm': 60.0})
    failed = engine.execute(root, target='design', timeout=900)['targets']['design']
    assert failed['status'] == 'failed' and 'lap' in ' '.join(failed['backends']['houdini']['checks']['mate']['acceptance']['failures'])
