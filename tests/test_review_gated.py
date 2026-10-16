"""Gated review features: presets, calibrated refs, diagnostic modes, IoU, blind output and region diffs."""
from pathlib import Path

from PIL import Image
import pytest

from geometryforge import camera, review
from geometryforge.blender_review import part_srgb
from geometryforge.storage import digest, read, write
from test_review import config, review_project  # noqa: F401  (fixture)


def calibrated(root):
    entry = {**camera.Camera(position_mm=[9000, -9000, 4000], target_mm=[0, 0, 1000], resolution=[100, 80]).review(),
             'resolution': [100, 80], 'crop': [0, 0, 100, 80], 'image': 'references/front.png', 'status': 'calibrated',
             'rms_px': .4, 'image_sha256': digest(root/'references/front.png'), 'correspondences_sha256': 'x'}
    write(root/'references/cameras.json', {'version': 1, 'cameras': {'primary': entry}})


def test_survey21_preset_expands_to_concrete_views(review_project):
    root, _, _ = review_project
    calibrated(root)
    value = {'version': 1, 'presets': [{'preset': 'survey21', 'bounds_mm': [[-3000, -1100, 0], [3000, 1100, 2200]],
                                        'modes': ['clay', 'zebra'], 'resolution': [320, 240], 'camera_refs': ['primary']}]}
    views = review.validate_config(value, root)['views']
    ids = [v['id'] for v in views]
    assert len(views) == 21 and len(set(ids)) == 21 and 'survey21_ref_primary' in ids
    sections = [v for v in views if 'section' in v]
    assert [s['section']['axis'] for s in sections] == ['x', 'y', 'z']
    assert all(v['camera']['projection'] == 'orthographic' for v in sections)
    ref = next(v for v in views if v['id'] == 'survey21_ref_primary')
    assert ref['calibration']['ref'] == 'primary' and ref['reference_crop'] == [0, 0, 100, 80]
    assert ref['resolution'] == [100, 80] and ref['zebra'] == {'stripes': 12, 'rotation_deg': [0, 0, 0]}
    assert not ref['calibration']['current']  # correspondences.json is absent in this fixture
    standard = review.validate_config({'version': 1, 'presets': [{'preset': 'standard6', 'bounds_mm': [[0, 0, 0], [1, 1, 1]]}]}, root)
    assert len(standard['views']) == 6


@pytest.mark.parametrize('mutate', [
    lambda c: c['views'][0].update(modes=['overlay']),
    lambda c: c['views'][0].update(section={'axis': 'w'}),
    lambda c: c['views'][0].update(zebra={'stripes': 0}),
    lambda c: c['views'][0].update(selection={'roles': ['interface']}),
    lambda c: c['views'][0].update(camera={'ref': 'missing'}),
    lambda c: c['views'][0].update(reference_mask='references/missing.png'),
    lambda c: c.update(presets=[{'preset': 'survey21'}]),
    lambda c: c.update(presets=[{'preset': 'survey21', 'bounds_mm': [[0, 0, 0], [0, 1, 1]]}]),
])
def test_invalid_gated_review_config(review_project, mutate):
    root, _, _ = review_project
    value = config()
    mutate(value)
    with pytest.raises(ValueError):
        review.validate_config(value, root)


def mask_native(box):
    """Fake renderer whose silhouette shows a box (black object over a transparent holdout)."""
    def native(command, **kwargs):
        request = read(command[-1])
        out = kwargs['log'].parent
        kwargs['log'].write_text('fixture')
        views = []
        for view in request['settings']['views']:
            artifacts = {}
            for mode in view['modes']:
                path = out/f'{view["id"]}_{mode}.png'
                if mode == 'silhouette':
                    im = Image.new('RGBA', tuple(view['resolution']), (0, 0, 0, 255))
                    im.paste((0, 0, 0, 0), box)
                else:
                    im = Image.new('RGB', tuple(view['resolution']), 'gray')
                im.save(path)
                artifacts[mode] = str(path)
            views.append({'id': view['id'], 'artifacts': artifacts, 'bounds_mm': [[-10, -10, 0], [10, 10, 10]]})
        write(out/'result.json', {'blender_version': 'fixture', 'views': views, 'part_colors': {}})
        return 0
    return native


def test_iou_baseline_overlay_and_blind_output(review_project, monkeypatch):
    root, scene, cfg = review_project
    mask = Image.new('L', (100, 80), 0)
    mask.paste(255, (20, 10, 60, 50))
    mask.save(root/'references/front_mask.png')
    value = config()
    value['views'][0].update(reference_mask='references/front_mask.png', resolution=[100, 80], modes=['clay', 'silhouette', 'overlay'])
    write(cfg, value)
    monkeypatch.setattr(review, 'run', mask_native((20, 10, 60, 50)))
    first = review.execute(root, scene, cfg)
    assert first['metrics']['front']['silhouette_iou'] == pytest.approx(1.0)
    assert first['metrics']['front']['delta_iou'] is None
    assert not first['metrics']['front']['calibrated']
    assert Path(first['views'][0]['artifacts']['overlay']).is_file()
    monkeypatch.setattr(review, 'run', mask_native((20, 10, 40, 50)))
    second = review.execute(root, scene, cfg, blind=True)
    assert 'metrics' not in second and 'Blind' in second['note']
    stored = read(second['report'])['metrics']['front']
    assert stored['silhouette_iou'] == pytest.approx(0.5) and stored['delta_iou'] == pytest.approx(-0.5)
    assert stored['baseline_review'] == first['review_id']
    assert second['views'][0]['contact_sheet'].endswith('_blind.png')


def diff_reports(root, before, after):
    ids = []
    for n, painter in enumerate((before, after)):
        folder = root/'review'/f'2099010{n + 1}T000000Z-00000000'
        folder.mkdir(parents=True)
        artifacts = {}
        for mode in ('part_id', 'normal'):
            im = Image.new('RGB', (40, 30), 'black')
            painter(im, mode)
            im.save(folder/f'v_{mode}.png')
            artifacts[mode] = str(folder/f'v_{mode}.png')
        view = {'id': 'v', 'camera': {'position_mm': [1, 0, 0]}, 'resolution': [40, 30]}
        write(folder/'report.json', {'status': 'complete', 'review_id': folder.name, 'settings': {'views': [view]},
                                     'views': [{'id': 'v', 'artifacts': artifacts}]})
        ids.append(folder.name)
    return ids


def painter(shift=0, leak=False):
    edited, other = tuple(part_srgb('front')), tuple(part_srgb('skirt'))
    def paint(im, mode):
        im.paste(edited if mode == 'part_id' else (128, 128, 255), (5 + shift, 5, 15 + shift, 15))
        im.paste(other if mode == 'part_id' else ((200, 128, 255) if leak else (128, 128, 250)), (25, 5, 35, 15))
    return paint


def test_review_diff_allows_edits_inside_the_part(review_project):
    root, _, _ = review_project
    before, after = diff_reports(root, painter(), painter(shift=2))
    result = review.diff(root, before, after, ['front'])
    assert result['status'] == 'passed' and result['views']['v']['changed_inside_px'] > 0
    assert Path(result['views']['v']['heatmap']).is_file()


def test_review_diff_flags_changes_outside_the_part(review_project):
    root, _, _ = review_project
    before, after = diff_reports(root, painter(), painter(leak=True))
    result = review.diff(root, before, after, ['front'])
    assert result['status'] == 'candidate'
    assert result['views']['v']['changed_outside_px'] == 100
    assert review.diff(root, before, after, ['front', 'skirt'])['status'] == 'passed'
