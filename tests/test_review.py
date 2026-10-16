import copy
import subprocess

from PIL import Image
import pytest

from geometryforge import review
from geometryforge.storage import digest, read, write


def config():
    return {'version': 1, 'views': [{'id': 'front', 'camera': {'position_mm': [100, -100, 100],
            'target_mm': [0, 0, 0]}, 'resolution': [64, 48], 'reference': 'references/front.png'}]}


@pytest.fixture
def review_project(project, monkeypatch):
    root, _ = project
    (root/'references').mkdir()
    Image.new('RGB', (100, 80), 'orange').save(root/'references/front.png')
    scene = root/'working.blend'
    scene.write_bytes(b'dedicated fixture scene')
    cfg = root/'review.json'
    write(cfg, config())
    write(root/'.geometryforge/state.json', {'format_version': 1, 'safe_point': 'kept', 'backends': {}})
    monkeypatch.setattr(review, 'resolve_blender', lambda _: 'fixture-blender')
    return root, scene, cfg


@pytest.mark.parametrize('mutate', [
    lambda c: c.update(version=True),
    lambda c: c.update(views=[]),
    lambda c: c['views'].append(copy.deepcopy(c['views'][0])),
    lambda c: c['views'][0].update(id='../escape'),
    lambda c: c['views'][0].update(modes=['textured']),
    lambda c: c['views'][0].update(modes=[{}]),
    lambda c: c['views'][0].update(samples=0),
    lambda c: c['views'][0].update(resolution=[20, 500]),
    lambda c: c['views'][0].update(selection={'parts': []}),
    lambda c: c['views'][0].update(reference='references/missing.png'),
    lambda c: c['views'][0].update(reference='../outside.png'),
    lambda c: c['views'][0].update(reference_crop=[0, 0, 101, 80]),
    lambda c: c['views'][0]['camera'].update(projection='oblique'),
    lambda c: c['views'][0]['camera'].update(position_mm=[0, 0, 0]),
    lambda c: c['views'][0]['camera'].update(position_mm=[0, 0, 100]),
    lambda c: c['views'][0]['camera'].update(lens_mm=float('nan')),
    lambda c: c['views'][0]['camera'].update(projection='orthographic'),
    lambda c: c['views'][0].update(studio={'center_mm': [0,0,0], 'size_mm': 0}),
    lambda c: c['views'][0].update(studio={'size_mm': 100}),
])
def test_invalid_config_before_launch(review_project, monkeypatch, mutate):
    root, scene, cfg = review_project
    value = config()
    mutate(value)
    def forbidden(*a, **k):
        pytest.fail('Invalid config must not launch Blender')
    monkeypatch.setattr(review, 'run', forbidden)
    with pytest.raises(ValueError):
        review.validate_config(value, root)
    assert not (root/'review').exists()


def fake_native(command, **kwargs):
    request = read(command[-1])
    out = kwargs['log'].parent
    kwargs['log'].write_text('fixture render log')
    views = []
    for view in request['settings']['views']:
        artifacts = {}
        for mode in view['modes']:
            path = out/f'{view["id"]}_{mode}.png'
            im = Image.new('RGBA' if mode == 'silhouette' else 'RGB', tuple(view['resolution']),
                           (0, 0, 0, 255) if mode == 'silhouette' else 'gray')
            if mode == 'silhouette':
                im.putpixel((30, 20), (0, 0, 0, 0))
            im.save(path)
            artifacts[mode] = str(path)
        views.append({'id': view['id'], 'triangles': 128, 'artifacts': artifacts})
    write(out/'result.json', {'blender_version': 'fixture', 'views': views})
    return 0


def test_review_provenance_and_no_state_changes(review_project, monkeypatch):
    root, scene, cfg = review_project
    state = root/'.geometryforge/state.json'
    before = [digest(p) for p in (scene, cfg, state)]
    monkeypatch.setattr(review, 'run', fake_native)
    result = review.execute(root, scene, cfg)
    assert result['status'] == 'complete'
    assert result['source_unchanged']
    assert result['scene_sha256'] == before[0]
    assert result['config_sha256'] == before[1]
    assert [digest(p) for p in (scene, cfg, state)] == before
    assert result['settings']['views'][0]['reference_sha256'] == digest(root/'references/front.png')
    artifact = result['views'][0]['artifacts']['silhouette']
    with Image.open(artifact) as im:
        assert im.getpixel((30, 20)) == (0, 0, 0)
        assert im.getpixel((0, 0)) == (255, 255, 255)
    assert read(result['report'])['status'] == 'complete'
    assert review.execute(root, scene, cfg)['review_id'] != result['review_id']


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'no_result', 'changed_scene', 'deleted_scene', 'changed_config', 'changed_reference', 'missing_image', 'wrong_views', 'cancelled'])
def test_failure_retains_evidence(review_project, monkeypatch, failure):
    root, scene, cfg = review_project
    state_hash = digest(root/'.geometryforge/state.json')
    def fail(command, **kwargs):
        if failure == 'exit':
            kwargs['log'].write_text('unknown or non-renderable parts: missing')
            return 1
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, 1)
        if failure == 'cancelled':
            raise KeyboardInterrupt('Cancelled fixture')
        if failure == 'no_result':
            return 0
        fake_native(command, **kwargs)
        out = kwargs['log'].parent
        if failure == 'changed_scene':
            scene.write_bytes(b'changed by external actor')
        elif failure == 'deleted_scene':
            scene.unlink()
        elif failure == 'changed_config':
            cfg.write_text('{}')
        elif failure == 'changed_reference':
            Image.new('RGB', (100, 80), 'blue').save(root/'references/front.png')
        elif failure == 'missing_image':
            (out/'front_clay.png').unlink()
        else:
            write(out/'result.json', {'views': [{'id': 'wrong'}]})
        return 0
    monkeypatch.setattr(review, 'run', fail)
    with pytest.raises(RuntimeError, match='retained review report'):
        review.execute(root, scene, cfg)
    reports = list((root/'review').glob('*/report.json'))
    assert len(reports) == 1
    result = read(reports[0])
    assert result['status'] == ('cancelled' if failure == 'cancelled' else 'failed')
    assert result['source_unchanged'] == (failure not in ('changed_scene', 'deleted_scene'))
    assert digest(root/'.geometryforge/state.json') == state_hash


def test_reference_optional_orthographic_config(review_project):
    root, _, _ = review_project
    c = config()
    del c['views'][0]['reference']
    c['views'][0]['camera'].update(projection='orthographic', ortho_scale_mm=500)
    normalized = review.validate_config(c, root)
    assert normalized['views'][0]['camera']['ortho_scale_mm'] == 500


def test_fixed_studio_config(review_project):
    root, _, _ = review_project
    value = config()
    value['views'][0]['studio'] = {'center_mm': [20,30,40], 'size_mm': 250}
    assert review.validate_config(value, root)['views'][0]['studio'] == value['views'][0]['studio']
