import math

import numpy as np
import pytest
import trimesh
from PIL import Image

from geometryforge import meshquery, surface_checks
from geometryforge.camera import Camera
from geometryforge.storage import write
from surfacing_fixtures import R, grid, obj, sphere


def payload(objects, kind, spec, thresholds=None, mode='enforce', parameters=None, **extra):
    grouped = {}
    for o in objects:
        grouped.setdefault(o['part'], []).append(o)
    return {'objects': grouped, 'kind': kind, 'spec': spec, 'thresholds': thresholds or {}, 'mode': mode,
            'parameters': parameters or {}, **extra}


def seam_scene(tilt_deg=0.0, lift=0.0, half_gap=1.5):
    delta = half_gap / R
    MV, MF = grid(sphere(), (-.5, .5), (-.3, .3), 401, 121)
    AV, AF = grid(sphere(), (delta, .4), (-.25, .25), 120, 60)
    BV, BF = grid(sphere(R + lift), (-.4, -delta), (-.25, .25), 120, 60)
    if tilt_deg:
        hinge = sphere()(0, 0)
        rotation = trimesh.transformations.rotation_matrix(math.radians(tilt_deg), [0, 1, 0], hinge)
        BV = trimesh.transform_points(BV, rotation)
    return [obj('master', 'master', MV, MF, 'guide'), obj('A', 'front', AV, AF), obj('B', 'skirt', BV, BF)]


SEAM = {'a': {'part': 'front'}, 'b': {'part': 'skirt'}, 'master': {'part': 'master'}}


def test_triangle_index_matches_brute_force():
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=100)
    index = meshquery.TriangleIndex(mesh.vertices, mesh.faces)
    points = np.random.default_rng(2).uniform(-160, 160, (300, 3))
    distance, _, _, _ = index.closest(points)
    brute = []
    for p in points:
        q, _ = meshquery._closest_on_triangles(np.repeat(p[None], len(mesh.faces), 0), *[mesh.vertices[mesh.faces[:, i]] for i in range(3)])
        brute.append(np.linalg.norm(q - p, axis=1).min())
    np.testing.assert_allclose(distance, brute, atol=1e-9)
    signed = index.signed_distance(points)[0]
    clear = np.abs(np.linalg.norm(points, axis=1) - 100) > 2
    np.testing.assert_array_equal((signed < 0)[clear], (np.linalg.norm(points, axis=1) < 100)[clear])
    flipped = meshquery.TriangleIndex(mesh.vertices, mesh.faces[:, ::-1]).signed_distance(points)[0]
    np.testing.assert_allclose(flipped, signed)


def test_open_edges_and_segment_crossings():
    box = trimesh.creation.box([10, 10, 10])
    assert len(meshquery.open_edges(box.faces)) == 0
    assert len(meshquery.open_edges(box.faces[:-1])) == 3
    count, _ = meshquery.TriangleIndex(box.vertices, box.faces).segment_crossings([[0, 0, -20], [20, 20, 20]], [[0, 0, 20], [30, 30, 30]])
    assert count == 1


def test_flush_seam_passes():
    result = surface_checks.verify(payload(seam_scene(), 'seam', SEAM))
    assert result['passed'], result['acceptance']
    m = result['measurements']
    assert m['seam_pairs'] > 20 and 2.9 < m['gap_min_mm'] <= m['gap_max_mm'] < 3.2
    assert m['master_deviation_max_mm'] < 0.05 and m['step_max_mm'] < 0.05


def test_staggered_coarse_borders_measure_the_true_gap():
    # Coarse borders offset by half a vertex spacing along the seam (~11 mm): the gap is still 3 mm.
    delta, step = 1.5 / R, .5 / 11 / 2
    MV, MF = grid(sphere(), (-.5, .5), (-.3, .3), 401, 121)
    AV, AF = grid(sphere(), (delta, .4), (-.25, .25), 40, 12)
    BV, BF = grid(sphere(), (-.4, -delta), (-.25 + step, .25 + step), 40, 12)
    objects = [obj('master', 'master', MV, MF, 'guide'), obj('A', 'front', AV, AF), obj('B', 'skirt', BV, BF)]
    m = surface_checks.verify(payload(objects, 'seam', SEAM))['measurements']
    assert 2.9 < m['gap_min_mm'] <= m['gap_max_mm'] < 3.2


def test_skin_border_sits_where_the_normal_limit_is_crossed():
    # A border vertex flat on the master (0 deg) next to a bevel vertex at 20 deg: the 10 deg limit is crossed halfway.
    V = np.array([[0.0, 0, 0], [10, 0, 0], [0, 10, 0], [10, 10, 0]])
    F = np.array([[0, 1, 3], [0, 3, 2]])
    tilt = np.radians(20)
    normals = np.array([[0, 0, 1.0], [math.sin(tilt), 0, math.cos(tilt)], [0, 0, 1.0], [math.sin(tilt), 0, math.cos(tilt)]])
    mnormal = np.tile([0, 0, 1.0], (4, 1))
    mask = np.array([True, False, True, False])
    limits = {'exterior_normal_deg': 10.0, 'exterior_band_mm': 1.0}
    P = surface_checks.skin_edge_positions(V, F, mask, np.zeros(4), normals, mnormal, np.array([0, 2]), limits)
    np.testing.assert_allclose(P[[0, 2], 0], [5.0, 5.0])
    np.testing.assert_allclose(P[[1, 3]], V[[1, 3]])


def test_stepped_seam_fails_with_locations():
    result = surface_checks.verify(payload(seam_scene(lift=1.0), 'seam', SEAM))
    assert not result['passed']
    assert any('Seam step' in f for f in result['acceptance']['failures'])
    assert any('master' in f for f in result['acceptance']['failures'])
    assert result['worst'] and all(len(w['location_mm']) == 3 for w in result['worst'])


def test_tangent_break_fails():
    result = surface_checks.verify(payload(seam_scene(tilt_deg=5), 'seam', SEAM))
    assert any('Tangent break' in f for f in result['acceptance']['failures'])


def test_curvature_break_with_matching_tangents_fails():
    # Two cylinders tangent along the seam line: G0 and G1 hold, curvature jumps from 1/500 to 1/250.
    def cylinder(radius):
        return lambda phi, y: np.array([radius * math.sin(phi), y, radius * math.cos(phi) - radius + R])
    MV, MF = grid(cylinder(R), (-.5, .5), (-150, 150), 401, 61)
    AV, AF = grid(cylinder(R), (1.5 / R, .4), (-120, 120), 160, 50)
    BV, BF = grid(cylinder(250), (-.8, -1.5 / 250), (-120, 120), 160, 50)
    objects = [obj('master', 'master', MV, MF, 'guide'), obj('A', 'front', AV, AF), obj('B', 'skirt', BV, BF)]
    result = surface_checks.verify(payload(objects, 'seam', SEAM, {'master_deviation_mm': 1000}))
    m = result['measurements']
    assert m['step_max_mm'] < .05 and m['normal_angle_p95_deg'] < .5
    assert any('Curvature mismatch' in f for f in result['acceptance']['failures']), m


def test_measure_mode_records_without_failing():
    result = surface_checks.verify(payload(seam_scene(lift=1.0), 'seam', SEAM, mode='measure'))
    assert result['passed'] and not result['acceptance']['met']


def test_project_thresholds_override_defaults():
    params = {'gf_thresholds': {'seam': {'step_mm': 2.0, 'master_deviation_mm': 2.0}}}
    result = surface_checks.verify(payload(seam_scene(lift=1.0), 'seam', SEAM, parameters=params))
    assert result['passed'] and result['thresholds']['step_mm'] == 2.0
    result = surface_checks.verify(payload(seam_scene(lift=1.0), 'seam', SEAM, {'step_mm': 0.5}, parameters=params))
    assert not result['passed']


def pocket_scene(wall='smooth', proud=False):
    big = 2000.0
    rings = np.concatenate([np.linspace(0, 30, 7), np.linspace(31, 80, 50), np.linspace(82, 120, 20)])
    segments = 72

    def depth(r):
        if wall == 'vertical':
            return 20.0 if r < 40 else 0.0
        t = np.clip((80 - r) / 50, 0, 1)
        return 20 * (3 * t * t - 2 * t ** 3)

    def weight(r):
        if wall == 'vertical':
            return 1.0 if r >= 40 else 0.0
        return float(np.clip((r - 30) / 50, 0, 1))

    def build(with_pocket):
        V, W = [], []
        for r in rings:
            for k in range(segments):
                a = 2 * math.pi * k / segments
                x, y = r * math.cos(a), r * math.sin(a)
                z = math.sqrt(big * big - x * x - y * y) - big
                if with_pocket:
                    z -= depth(r)
                V.append([x, y, z])
                W.append(weight(r))
        F = []
        for i in range(len(rings) - 1):
            for k in range(segments):
                a, b = i * segments + k, i * segments + (k + 1) % segments
                c, d = (i + 1) * segments + (k + 1) % segments, (i + 1) * segments + k
                F += [[a, c, b], [a, d, c]]  # outward (+z) normals
        return np.array(V), np.array(F), np.array(W)

    MV, MF, _ = build(False)
    PV, PF, W = build(True)
    objects = [obj('master', 'master', MV, MF, 'guide'), obj('panel', 'front', PV, PF, point_attributes={'guide_bound': W.tolist()})]
    if proud:
        lamp = trimesh.creation.box([20, 20, 20])
        lamp.apply_translation([95, 0, 5])
        objects.append(obj('lamp', 'lamp', lamp.vertices, lamp.faces))
    return objects


RECESS = {'panel': {'part': 'front'}, 'master': {'part': 'master'}}


def test_smooth_recessed_pocket_passes():
    result = surface_checks.verify(payload(pocket_scene(), 'recess', RECESS))
    assert result['passed'], result['acceptance']
    m = result['measurements']
    assert m['pocket_faces'] > 0 and m['draft_min_deg'] > 45 and m['fillet_min_mm'] > 5 and m['proud_vertices'] == 0


def test_recess_region_selects_pockets():
    everywhere = surface_checks.verify(payload(pocket_scene(), 'recess', RECESS))['measurements']['pocket_faces']
    far = {**RECESS, 'region_mm': [[1e5, 1e5, 1e5], [2e5, 2e5, 2e5]]}
    result = surface_checks.verify(payload(pocket_scene(), 'recess', far))
    assert result['measurements']['pocket_faces'] == 0 and any('No recessed pocket' in f for f in result['acceptance']['failures'])
    whole = {**RECESS, 'region_mm': [[-1e5, -1e5, -1e5], [1e5, 1e5, 1e5]]}
    assert surface_checks.verify(payload(pocket_scene(), 'recess', whole))['measurements']['pocket_faces'] == everywhere


def test_proud_lamp_fails():
    spec = {**RECESS, 'contents': [{'part': 'lamp'}]}
    result = surface_checks.verify(payload(pocket_scene(proud=True), 'recess', spec))
    assert any('proud' in f for f in result['acceptance']['failures'])


def test_straight_pocket_wall_fails_draft():
    # A 20 mm drop over 1 mm of radius: a near-vertical wall without draft.
    result = surface_checks.verify(payload(pocket_scene('vertical'), 'recess', RECESS))
    assert any('draft' in f for f in result['acceptance']['failures'])


def test_sharp_pocket_return_fails_fillet():
    result = surface_checks.verify(payload(pocket_scene(), 'recess', RECESS, {'fillet_min_mm': 500}))
    assert any('radius' in f for f in result['acceptance']['failures'])


def test_recess_without_weights_is_an_error():
    objects = pocket_scene()
    objects[1].pop('point_attributes')
    with pytest.raises(ValueError, match='guide_bound'):
        surface_checks.verify(payload(objects, 'recess', RECESS))


def ring_obj(name, part, centre, radius=50, axis_meta=None, n=64):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = np.column_stack((radius * np.cos(a), radius * np.sin(a), np.zeros(n))) + centre
    return {'name': name, 'part': part, 'role': 'interface', 'vertices': V.tolist(), 'faces': [],
            'edges': [[i, (i + 1) % n] for i in range(n)], 'matrix_world': np.eye(4).tolist(),
            'metadata': {'axis': axis_meta} if axis_meta else {}}


def mating_scene(child_centre=(0, 0, 48), solid_radius=None):
    objects = [ring_obj('parent', 'mounts', [0, 0, 0]), ring_obj('child', 'engines', child_centre)]
    if solid_radius:
        skin = trimesh.creation.annulus(r_min=60, r_max=200, height=4)
        objects.append(obj('skin', 'body', skin.vertices, skin.faces))
        shaft = trimesh.creation.cylinder(radius=solid_radius, height=200)
        objects.append(obj('shaft', 'engines', shaft.vertices, shaft.faces))
    return objects


MATING = {'parent': {'part': 'mounts'}, 'child': {'part': 'engines'}}
LAP = {'lap_min_mm': 47.5, 'lap_max_mm': 48.5}


def test_coaxial_ring_with_lap_passes():
    result = surface_checks.verify(payload(mating_scene(), 'mating', MATING, LAP))
    assert result['passed'], result['acceptance']
    assert result['measurements']['lap_mm'] == pytest.approx(48)


@pytest.mark.parametrize('centre,message', [((0.2, 0, 48), 'off axis'), ((0, 0, 60), 'lap')])
def test_misaligned_ring_fails(centre, message):
    result = surface_checks.verify(payload(mating_scene(centre), 'mating', MATING, LAP))
    assert any(message in f for f in result['acceptance']['failures'])


def test_mating_requires_lap_window():
    with pytest.raises(ValueError, match='lap_min_mm'):
        surface_checks.verify(payload(mating_scene(), 'mating', MATING))


def test_child_piercing_skin_fails():
    spec = {**MATING, 'skin': [{'part': 'body'}], 'child_solids': [{'part': 'engines'}]}
    ok = surface_checks.verify(payload(mating_scene(solid_radius=40), 'mating', spec, LAP))
    assert ok['passed'] and ok['measurements']['skin_crossings'] == 0
    bad = surface_checks.verify(payload(mating_scene(solid_radius=80), 'mating', spec, LAP))
    assert any('pierce' in f for f in bad['acceptance']['failures'])


def test_open_edges_global():
    box = trimesh.creation.box([10, 10, 10])
    spec = {'test': 'open_edges', 'targets': [{'part': 'hull', 'roles': ['guide']}]}
    closed = surface_checks.verify(payload([obj('m', 'hull', box.vertices, box.faces, 'guide')], 'global', spec))
    assert closed['passed'] and closed['measurements']['open_edges'] == 0
    holed = surface_checks.verify(payload([obj('m', 'hull', box.vertices, box.faces[:-2], 'guide')], 'global', spec))
    assert not holed['passed']


def test_coverage_finds_uncovered_master_and_respects_openings():
    MV, MF = grid(sphere(), (-.5, .5), (-.3, .3), 201, 61)
    AV, AF = grid(sphere(), (-.5, -.06), (-.3, .3), 100, 61)
    BV, BF = grid(sphere(), (.06, .5), (-.3, .3), 100, 61)
    objects = [obj('master', 'master', MV, MF, 'guide'), obj('A', 'front', AV, AF), obj('B', 'skirt', BV, BF)]
    spec = {'test': 'coverage', 'master': {'part': 'master'}, 'panels': [{'part': 'front'}, {'part': 'skirt'}], 'sample_mm': 5}
    result = surface_checks.verify(payload(objects, 'global', spec))
    assert not result['passed'] and result['measurements']['uncovered_area_mm2'] > 1000
    # A declared opening ring over the gap (axis along the master normal) excuses it.
    objects.append(ring_obj('hole', 'front', [0, 0, R], radius=80))
    spec['openings'] = [{'part': 'front', 'roles': ['interface']}]
    spec['region_mm'] = [[-60, -60, 0], [60, 60, 600]]
    covered = surface_checks.verify(payload(objects, 'global', spec))
    assert covered['passed'], covered['acceptance']
    spec.pop('openings')
    exposed = surface_checks.verify(payload(objects, 'global', spec))
    assert not exposed['passed']


def silhouette_scene(tmp_path, offset=0.0):
    box = trimesh.creation.box([2000, 1000, 800])
    cam = Camera(position_mm=[6000, -6000, 3000], target_mm=[0, 0, 0], lens_mm=50, resolution=[320, 240])
    uv, _ = cam.project(box.vertices)
    mask = Image.new('L', (320, 240), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    for tri in box.faces:
        draw.polygon([tuple(uv[i]) for i in tri], fill=255)
    (tmp_path / 'references').mkdir()
    mask.save(tmp_path / 'references/mask.png')
    write(tmp_path / 'references/cameras.json', {'version': 1, 'cameras': {'primary': {
        **cam.review(), 'resolution': [320, 240], 'crop': [0, 0, 320, 240], 'status': 'calibrated',
        'mask': 'references/mask.png', 'rms_px': 0.1}}})
    moved = box.copy()
    moved.apply_translation([offset, 0, 0])
    return [obj('hull', 'hull', moved.vertices, moved.faces, 'guide')]


def test_silhouette_iou_and_delta(tmp_path):
    spec = {'test': 'silhouette_iou', 'camera': 'primary', 'targets': [{'part': 'hull', 'roles': ['guide']}]}
    match = surface_checks.verify(payload(silhouette_scene(tmp_path), 'global', spec, mode='measure', snapshot_root=str(tmp_path)))
    assert match['measurements']['silhouette_iou'] > 0.97 and match['acceptance']['met']
    shifted = silhouette_scene(tmp_path / 'b', offset=600) if (tmp_path / 'b').mkdir() is None else None
    worse = surface_checks.verify(payload(shifted, 'global', spec, mode='measure', snapshot_root=str(tmp_path / 'b'), previous=match))
    m = worse['measurements']
    assert m['silhouette_iou'] < 0.9 and m['delta_iou'] < 0 and worse['passed'] and not worse['acceptance']['met']
    assert any('regressed' in f for f in worse['acceptance']['failures'])


def test_silhouette_requires_calibrated_mask(tmp_path):
    objects = silhouette_scene(tmp_path)
    cameras = tmp_path / 'references/cameras.json'
    import json
    data = json.loads(cameras.read_text())
    data['cameras']['primary'].pop('mask')
    cameras.write_text(json.dumps(data))
    spec = {'test': 'silhouette_iou', 'camera': 'primary', 'targets': [{'part': 'hull', 'roles': ['guide']}]}
    with pytest.raises(ValueError, match='mask'):
        surface_checks.verify(payload(objects, 'global', spec, snapshot_root=str(tmp_path)))
