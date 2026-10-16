"""Opt-in native tests only create/open dedicated temporary managed scenes."""
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
import pytest

from geometryforge import projects, review
from geometryforge.process import resolve_blender
from geometryforge.storage import digest, read, write

pytestmark = pytest.mark.skipif(os.environ.get('GEOMETRYFORGE_RUN_NATIVE_REVIEW') != '1',
                              reason='Set GEOMETRYFORGE_RUN_NATIVE_REVIEW=1 and GEOMETRYFORGE_BLENDER for dedicated native tests')


def test_native_review_preserves_scene_and_evaluates_curvature(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, 'HOME', tmp_path/'catalog')
    root = tmp_path/'managed_review_fixture'
    projects.initialize(root, ident='review_fixture', target='game', deliverables='blender', brief='Dedicated native review fixture')
    scene = root/'fixture.blend'
    subprocess.run([resolve_blender(), '--background', '--factory-startup', '--python-exit-code', '1', '--python',
                    str(Path(__file__).resolve().parents[1]/'tools/fixtures/review_scene.py'), '--', str(scene)],
                   check=True, capture_output=True, timeout=60)
    state = root/'.geometryforge/state.json'
    write(state, {'format_version': 2, 'backends': {}, 'targets': {}, 'safe_points': {'design': 'preserved'}})
    cfg = root/'review.json'
    write(cfg, {'version': 1, 'views': [{'id': 'panel', 'selection': {'parts': ['panel']},
          'camera': {'position_mm': [180, -220, 190], 'target_mm': [0, 0, 4],
                     'projection': 'orthographic', 'ortho_scale_mm': 170}, 'samples': 4, 'resolution': [160, 120],
          'studio': {'center_mm': [0,0,4], 'size_mm': 150}}]})
    hashes = digest(scene), digest(state)
    result = review.execute(root, scene, cfg, timeout=120)
    view = result['views'][0]
    assert view['studio'] == {'center_mm': [0,0,4], 'size_mm': 150}
    assert view['triangles'] >= read(root/'fixture.json')['expected_min_triangles']
    assert len(view['objects']) == 1
    assert view['objects'][0]['name'] == 'Crowned panel'
    for mode, path in view['artifacts'].items():
        with Image.open(path) as im:
            pixels = np.asarray(im)
            assert im.size == (160, 120)
            assert pixels.std() > 8, f'{mode} must show geometry'
            if mode == 'silhouette':
                assert pixels.min() == 0 and pixels.max() == 255
    assert hashes == (digest(scene), digest(state))
    value = read(cfg)
    value['views'][0]['selection'] = {'parts': ['instance']}
    write(cfg, value)
    instanced = review.execute(root, scene, cfg, timeout=120)['views'][0]
    assert instanced['triangles'] == 4
    assert instanced['objects'][0]['part'] == 'instance'
    assert 'Instance-only tetrahedron' in instanced['objects'][0]['name']
    assert hashes == (digest(scene), digest(state))
    value = read(cfg)
    value['views'][0]['selection'] = {'parts': ['node_instance']}
    write(cfg, value)
    procedural = review.execute(root, scene, cfg, timeout=120)['views'][0]
    assert procedural['triangles'] == 4
    assert procedural['objects'][0]['part'] == 'node_instance'
    assert hashes == (digest(scene), digest(state))
    value = read(cfg)
    value['views'][0]['selection'] = {'objects': ['Invisible construction operand']}
    write(cfg, value)
    with pytest.raises(RuntimeError, match='Blender review failed'):
        review.execute(root, scene, cfg, timeout=60)
    logs = list((root/'review').glob('*/blender.log'))
    assert any('unknown or non-renderable objects' in p.read_text() for p in logs)
    assert hashes == (digest(scene), digest(state))


def test_native_diagnostic_modes_and_sections(tmp_path, monkeypatch):
    from geometryforge.blender_review import part_srgb
    monkeypatch.setattr(projects, 'HOME', tmp_path/'catalog')
    root = tmp_path/'managed_review_fixture'
    projects.initialize(root, ident='review_fixture', target='game', deliverables='blender', brief='Dedicated native review fixture')
    scene = root/'fixture.blend'
    subprocess.run([resolve_blender(), '--background', '--factory-startup', '--python-exit-code', '1', '--python',
                    str(Path(__file__).resolve().parents[1]/'tools/fixtures/review_scene.py'), '--', str(scene)],
                   check=True, capture_output=True, timeout=60)
    cfg = root/'review.json'
    camera = {'position_mm': [180, -220, 190], 'target_mm': [0, 0, 4], 'projection': 'orthographic', 'ortho_scale_mm': 170}
    write(cfg, {'version': 1, 'views': [
        {'id': 'panel', 'selection': {'parts': ['panel']}, 'camera': camera, 'samples': 4, 'resolution': [160, 120],
         'modes': ['zebra', 'normal', 'part_id', 'clay', 'overlay'], 'zebra': {'stripes': 8}},
        {'id': 'cut', 'selection': {'parts': ['panel']}, 'camera': camera, 'samples': 4, 'resolution': [160, 120],
         'modes': ['clay', 'part_id'], 'section': {'axis': 'x', 'offset_mm': 0, 'keep': 'negative'}}]})
    first = review.execute(root, scene, cfg, timeout=180)
    panel, cut = first['views']
    with Image.open(panel['artifacts']['part_id']) as im:
        pixels = np.asarray(im.convert('RGB')).reshape(-1, 3)
    colour = np.asarray(part_srgb('panel'))
    assert (np.abs(pixels - colour) <= 2).all(axis=1).sum() > 200, 'part_id must render the exact part colour'
    with Image.open(panel['artifacts']['zebra']) as im:
        zebra = np.asarray(im.convert('L'))
    assert zebra.min() < 40 and zebra.max() > 215, 'zebra must show dark and bright bands'
    with Image.open(cut['artifacts']['part_id']) as im:
        cut_pixels = (np.abs(np.asarray(im.convert('RGB')).reshape(-1, 3) - colour) <= 2).all(axis=1).sum()
    full = (np.abs(pixels - colour) <= 2).all(axis=1).sum()
    assert 0 < cut_pixels < full, 'a section keeps part of the panel'
    assert Path(panel['artifacts']['overlay']).is_file() and len(panel['bounds_mm']) == 2
    second = review.execute(root, scene, cfg, timeout=180)
    diff = review.diff(root, first['review_id'], second['review_id'], ['panel'], margin_px=0)
    assert diff['status'] == 'passed' and diff['views']['panel']['changed_outside_px'] == 0
