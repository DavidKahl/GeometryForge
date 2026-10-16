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


# Screen axes of each clean view, written out independently of camera.ORTHO_VIEWS:
# pixel = offset + scale * Rot(roll) @ (a, b), with b pointing down the image.
ORTHO_AXES = {'front': lambda p: (p[:, 1], -p[:, 2]), 'back': lambda p: (-p[:, 1], -p[:, 2]),
              'left': lambda p: (-p[:, 0], -p[:, 2]), 'right': lambda p: (p[:, 0], -p[:, 2]),
              'top': lambda p: (-p[:, 1], -p[:, 0]), 'bottom': lambda p: (p[:, 1], -p[:, 0])}


def ortho_pixels(view, points, scale=0.17, roll_deg=1.5, offset=(612.0, 655.0)):
    a, b = ORTHO_AXES[view](np.asarray(points, dtype=float))
    c, s = np.cos(np.radians(roll_deg)), np.sin(np.radians(roll_deg))
    return np.column_stack((offset[0] + scale * (c * a - s * b), offset[1] + scale * (s * a + c * b)))


@pytest.mark.parametrize('view', sorted(ORTHO_AXES))
def test_orthographic_views_recover_scale_roll_and_offset(view):
    points = cloud(8, 5)
    pixels = ortho_pixels(view, points)
    result = camera.solve_orthographic(points, pixels, [1254, 1254], view)
    solved = result['camera']
    assert result['rms_px'] < 1e-6 and result['roll_deg'] == pytest.approx(1.5, abs=1e-6)
    assert solved.projection == 'orthographic' and solved.ortho_scale_mm == pytest.approx(1254 / 0.17, rel=1e-9)
    np.testing.assert_allclose(solved.project(points)[0], pixels, atol=1e-6)
    assert (solved.project(points)[1] > 0).all()


def test_orthographic_view_conventions():
    nose, tail, left, right, high = [3000, 0, 800], [-3000, 0, 800], [0, 1100, 800], [0, -1100, 800], [0, 0, 2000]
    def uv(view, point):
        solved = camera.solve_orthographic(cloud(6, 2), ortho_pixels(view, cloud(6, 2), roll_deg=0), [1254, 1254], view)['camera']
        return solved.project([point])[0][0]
    assert uv('right', nose)[0] > uv('right', tail)[0] and uv('left', nose)[0] < uv('left', tail)[0]
    assert uv('front', left)[0] > uv('front', right)[0] and uv('back', left)[0] < uv('back', right)[0]
    assert uv('top', nose)[1] < uv('top', tail)[1] and uv('top', right)[0] > uv('top', left)[0]
    assert uv('bottom', nose)[1] < uv('bottom', tail)[1] and uv('bottom', left)[0] > uv('bottom', right)[0]
    assert uv('right', high)[1] < uv('right', nose)[1] and uv('front', high)[1] < uv('front', left)[1]


def test_orthographic_noise_and_degenerate_inputs():
    points = cloud(10, 7)
    noisy = ortho_pixels('right', points) + np.random.default_rng(8).normal(0, 1.0, (10, 2))
    result = camera.solve_orthographic(points, noisy, [1254, 1254], 'right')
    assert 0.3 < result['rms_px'] < 2.0 and result['max_px'] >= result['rms_px']
    with pytest.raises(ValueError, match='at least 3'):
        camera.solve_orthographic(points[:2], noisy[:2], [1254, 1254], 'right')
    with pytest.raises(ValueError, match='view'):
        camera.solve_orthographic(points, noisy, [1254, 1254], 'diagonal')
    with pytest.raises(ValueError, match='coincide'):
        camera.solve_orthographic([[0, 0, 0], [500, 0, 0], [900, 0, 0]], [[1, 1], [2, 2], [3, 3]], [1254, 1254], 'front')


def test_calibrate_orthographic_camera(project):
    root, _ = project
    (root / 'references').mkdir()
    Image.new('RGB', (1254, 1254), 'white').save(root / 'references/right.png')
    world = [[2900, -1000, 300], [-2900, -1000, 300], [0, -1100, 1950], [1500, -1000, 0], [-1800, -1000, 0]]
    pixels = ortho_pixels('right', world)
    write(root / 'references/correspondences.json', {'version': 1, 'cameras': {'right': {
        'role': 'primary', 'image': 'references/right.png', 'projection': 'orthographic', 'view': 'right',
        'points': [{'id': f'p{i}', 'world_mm': w, 'pixel': list(map(float, xy))} for i, (w, xy) in enumerate(zip(world, pixels))]}}})
    result = camera.calibrate(root)
    entry = read(root / 'references/cameras.json')['cameras']['right']
    assert result['status'] == 'passed' and entry['status'] == 'calibrated'
    assert entry['projection'] == 'orthographic' and entry['view'] == 'right' and entry['rms_px'] < 1e-6
    np.testing.assert_allclose(camera.Camera.from_dict(entry).project(world)[0], pixels, atol=1e-6)
