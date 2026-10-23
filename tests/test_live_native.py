"""Opt-in native test: a live run builds one part per recipe call; its geometry must equal a headless run."""
import os
from pathlib import Path
import shutil

import pytest

from geometryforge import backends, blender_session, engine, gates, live_shots, projects, review
from geometryforge.process import resolve_blender, run
from geometryforge.worker_env import worker_environment

pytestmark = pytest.mark.skipif(os.environ.get('GEOMETRYFORGE_RUN_NATIVE_LIVE') != '1',
                                reason='Set GEOMETRYFORGE_RUN_NATIVE_LIVE=1 and GEOMETRYFORGE_BLENDER for the live build test')

FIXTURE = Path(__file__).resolve().parents[1] / 'tools/fixtures/surfacing_project'
RUNNER = Path(__file__).resolve().parent / 'live_dry_runner.py'


def dry_request(payload, explicit=None, timeout=900):
    out = Path(payload['out'])
    code = run([resolve_blender(explicit), '--background', '--factory-startup', '--python-exit-code', '1',
                '--python', RUNNER, '--', out / 'request.json'], cwd=out, env=worker_environment(), log=out / 'blender.log', timeout=timeout)
    assert code == 0, (out / 'blender.log').read_text(encoding='utf-8', errors='replace')[-4000:]


def design(root):
    route = engine.execute(root, target='design', timeout=1500)['targets']['design']
    assert route['status'] == 'passed', route['failures']
    return route['backends']['blender']


def test_live_per_part_build_matches_headless(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'catalog')
    monkeypatch.setattr(blender_session, 'request', dry_request)
    geometry = {}
    for mode in ('headless', 'live'):
        root = tmp_path / mode
        shutil.copytree(FIXTURE, root)
        first = design(root)
        review.execute(root, root / first['native']['path'], root / 'reviews/master.json', timeout=900)
        gates.accept(root, 'master', 'native test', 'fixture acceptance')
        token = backends.live_settings.set({**live_shots.settings(), 'dry': True}) if mode == 'live' else None
        try:
            panels = design(root)
        finally:
            if token:
                backends.live_settings.reset(token)
        assert panels.get('mode') == ('live' if mode == 'live' else None)
        geometry[mode] = panels['geometry']
    assert set(geometry['live']) == {'master_hull', 'body', 'skirt', 'vent'}
    assert geometry['live'] == geometry['headless']
