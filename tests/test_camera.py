import numpy as np
import pytest
from PIL import Image

from geometryforge import camera
from geometryforge.storage import read, write

TRUTH = camera.Camera(position_mm=[9500, -12500, 5400], target_mm=[-450, 0, 1150], lens_mm=70,
                      shift_x=0.03, shift_y=-0.02, resolution=[1536, 1024])
PADS = [[1425, -720, 0], [1425, 720, 0], [-1805, -720, 0], [-1805, 720, 0]]


def cloud(n=10, seed=1):
    return np.random.default_rng(seed).uniform([-3000, -1100, 0], [2900, 1100, 2200], (n, 3))


def test_recovers_pose_focal_and_shift():
    points = cloud()
    uv, _ = TRUTH.project(points)
    result = camera.solve(points, uv, [1536, 1024], principal='free')
    solved = result['camera']
    assert result['rms_px'] < 1e-6
    assert solved.lens_mm == pytest.approx(70, rel=1e-6)
    assert solved.shift_x == pytest.approx(0.03, abs=1e-6) and solved.shift_y == pytest.approx(-0.02, abs=1e-6)
    np.testing.assert_allclose(solved.position_mm, TRUTH.position_mm, atol=1e-3)
    np.testing.assert_allclose(solved.project(points)[0], uv, atol=1e-4)


def test_coplanar_pad_centres_with_lens_prior():
    truth = camera.Camera(position_mm=[9500, -12500, 5400], target_mm=[-450, 0, 1150], lens_mm=70, resolution=[1536, 1024])
    uv, _ = truth.project(PADS)
    result = camera.solve(PADS, uv, [1536, 1024], lens_mm=70)
    np.testing.assert_allclose(result['camera'].position_mm, truth.position_mm, atol=1e-2)


def test_noise_reported_as_rms():
    points = cloud(12, 3)
    uv, _ = TRUTH.project(points)
    noisy = uv + np.random.default_rng(4).normal(0, 0.8, uv.shape)
    result = camera.solve(points, noisy, [1536, 1024], principal='free')
    assert 0.2 < result['rms_px'] < 1.5
    assert result['max_px'] >= result['rms_px']


@pytest.mark.parametrize('points,pixels,kwargs', [
    (PADS[:3], [[1, 1], [2, 2], [3, 1]], {'lens_mm': 50}),                     # too few for a pose
    ([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]], [[1, 1], [2, 3], [5, 1], [7, 7], [9, 2]], {}),  # collinear datums
    (PADS, [[1, 1], [2, 2], [3, 3], [4, 4]], {'lens_mm': 50}),                  # collinear picks
    (PADS, [[1, 1], [2, 2], [3, 1], [float('nan'), 4]], {'lens_mm': 50}),
])
def test_degenerate_inputs_rejected(points, pixels, kwargs):
    with pytest.raises(ValueError):
        camera.solve(points, pixels, [1536, 1024], **kwargs)


def test_orthographic_projection_matches_blender_convention():
    cam = camera.Camera(position_mm=[0, -1000, 0], target_mm=[0, 0, 0], projection='orthographic', ortho_scale_mm=200,
                        resolution=[400, 200])
    uv, depth = cam.project([[0, 0, 0], [100, 0, 50]])
    np.testing.assert_allclose(uv, [[200, 100], [400, 0]])
    assert (depth > 0).all()


def correspondence_project(project, rms_noise=0.0):
    root, _ = project
    (root / 'references').mkdir()
    Image.new('RGB', (1636, 1124), 'gray').save(root / 'references/front.png')
    Image.new('L', (1636, 1124), 0).save(root / 'references/front_mask.png')
    params = read(root / 'parameters.json')
    params['datum_nose'] = [2900, 0, 900]
    write(root / 'parameters.json', params)
    points = [*PADS, {'param': 'datum_nose'}, [-2900, 0, 1800], [0, 1100, 2000]]
    world = [*PADS, [2900, 0, 900], [-2900, 0, 1800], [0, 1100, 2000]]
    truth = camera.Camera(position_mm=[9500, -12500, 5400], target_mm=[-450, 0, 1150], lens_mm=70, resolution=[1536, 1024])
    uv, _ = truth.project(world)
    uv = uv + np.random.default_rng(0).normal(0, rms_noise, uv.shape) + [50, 60]
    write(root / 'references/correspondences.json', {'version': 1, 'cameras': {'primary': {
        'role': 'primary', 'image': 'references/front.png', 'crop': [50, 60, 1586, 1084], 'mask': 'references/front_mask.png',
        'priors': {'lens_mm': None, 'sensor_width_mm': 36},
        'points': [{'id': f'p{i}', 'world_mm': w, 'pixel': list(map(float, xy))} for i, (w, xy) in enumerate(zip(points, uv))]}}})
    write(root / 'references/features.json', {'version': 1, 'curves': [{'id': 'roofline', 'points_mm': [[2000, 0, 1800], [-2500, 0, 2000]]}]})
    return root


def test_calibrate_writes_cameras_and_overlay(project):
    root = correspondence_project(project)
    result = camera.calibrate(root)
    assert result['status'] == 'passed'
    entry = read(root / 'references/cameras.json')['cameras']['primary']
    assert entry['status'] == 'calibrated' and entry['rms_px'] < 1e-3
    assert entry['resolution'] == [1536, 1024] and entry['mask'] == 'references/front_mask.png'
    assert camera.camera_current(root, entry)
    assert Image.open(result['overlays']['primary']).size == (1536, 1024)
    (root / 'references/front.png').write_bytes(b'changed')
    assert not camera.camera_current(root, entry)


def test_calibrate_over_threshold_is_candidate(project):
    root = correspondence_project(project, rms_noise=8.0)
    params = read(root / 'parameters.json')
    params['gf_thresholds'] = {'calibration': {'max_rms_px': 1.0}}
    write(root / 'parameters.json', params)
    result = camera.calibrate(root)
    assert result['status'] == 'candidate'
    assert result['cameras']['primary']['status'] == 'rejected'


def test_calibrate_dry_run_writes_nothing(project):
    root = correspondence_project(project)
    camera.calibrate(root, dry_run=True)
    assert not (root / 'references/cameras.json').exists()
    assert not (root / 'review').exists()
