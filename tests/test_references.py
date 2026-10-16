import numpy as np
import pytest
from PIL import Image, ImageDraw

from geometryforge import references
from geometryforge.storage import read, write

DIMS = {'length': 5800, 'width': 2200, 'height': 1950}


def draw_view(path, view, scale=0.15, stretch=1.0, transparent=False, noise=0):
    """A box-shaped object as each orthographic view sees it, on a plain or transparent background."""
    horizontal, vertical = references.AXES[view]
    w, h = DIMS[horizontal] * scale * stretch, DIMS[vertical] * scale
    image = Image.new('RGBA' if transparent else 'RGB', (1254, 1254), (0, 0, 0, 0) if transparent else (244, 244, 244))
    draw = ImageDraw.Draw(image)
    x0, y0 = 627 - w / 2, 627 - h / 2
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(230, 180, 20, 255) if transparent else (230, 180, 20))
    draw.rectangle([x0 + w * .3, y0 + h * .3, x0 + w * .6, y0 + h * .5], fill=(244, 244, 244, 255) if transparent else (244, 244, 244))
    if noise:
        pixels = np.asarray(image, dtype=np.int16)
        pixels[..., :3] += np.random.default_rng(1).integers(-noise, noise + 1, pixels[..., :3].shape)
        image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), image.mode)
    image.save(path)


def clean_set(project, **overrides):
    root, _ = project
    folder = root / 'references/clean'
    folder.mkdir(parents=True)
    views = {}
    for view in references.AXES:
        draw_view(folder / f'{view}.png', view, **overrides.get(view, {}))
        views[view] = f'references/clean/{view}.png'
    write(root / 'references/clean_set.json', {'version': 1, 'views': views})
    return root


def test_consistent_set_passes_and_writes_masks(project):
    root = clean_set(project, front={'transparent': True}, top={'noise': 6})
    result = references.masks(root)
    assert set(result['views']) == set(references.AXES)
    mask = np.asarray(Image.open(root / 'references/mask_front.png')) > 127
    assert mask.mean() == pytest.approx(DIMS['width'] * DIMS['height'] * 0.15 ** 2 / 1254 ** 2, rel=0.03)
    # Interior holes (a window drawn in background colour) are filled; the silhouette is solid.
    side = np.asarray(Image.open(root / 'references/mask_right.png')) > 127
    assert side[627, 627]
    report = references.check(root)
    assert report['status'] == 'passed' and not report['failures']
    assert len(report['comparisons']) == 4 and max(c['disagreement_pct'] for c in report['comparisons']) < 1.0
    assert read(root / 'references/clean_check.json')['views']['top']['image_sha256']


def test_inconsistent_view_is_reported(project):
    root = clean_set(project, front={'stretch': 1.12})
    report = references.check(root)
    assert report['status'] == 'candidate'
    failed = ' '.join(report['failures'])
    assert 'front vs back' in failed and 'side vs top x front' in failed
    assert 'left vs right' not in failed


def test_tolerance_is_a_project_threshold(project):
    root = clean_set(project, front={'stretch': 1.05})
    assert references.check(root)['status'] == 'candidate'
    params = read(root / 'parameters.json')
    params['gf_thresholds'] = {'references': {'view_disagreement_pct': 6.0}}
    write(root / 'parameters.json', params)
    assert references.check(root)['status'] == 'passed'


def test_set_contract_errors(project):
    root, _ = project
    with pytest.raises(ValueError, match='clean_set.json'):
        references.check(root)
    (root / 'references').mkdir()
    write(root / 'references/clean_set.json', {'version': 1, 'views': {'diagonal': 'references/x.png'}})
    with pytest.raises(ValueError, match='Unknown clean views'):
        references.check(root)
    write(root / 'references/clean_set.json', {'version': 1, 'views': {'front': 'references/missing.png'}})
    with pytest.raises(ValueError, match='missing image'):
        references.masks(root)
