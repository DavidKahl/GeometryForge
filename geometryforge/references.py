"""Clean reference sets: six orthographic, neutrally lit views of one object on a plain background.

references/clean_set.json (agent-authored) maps views to images:
    {"version": 1, "views": {"front": "references/clean/front.png", "right": "...", ...}}
Views are the orthographic directions of camera.ORTHO_VIEWS (vehicle space: X forward, Y left, Z up).

`masks` writes a white-on-black silhouette per view; `check` measures each silhouette's extent and
cross-checks length, width and height between views, so a generated view that disagrees is caught
before anything is modeled from it.
"""
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from . import projects
from .camera import ORTHO_VIEWS
from .storage import digest, read, write
from .thresholds import resolve as thresholds

# Which object extent each image axis shows: (horizontal, vertical).
AXES = {'front': ('width', 'height'), 'back': ('width', 'height'), 'left': ('length', 'height'),
        'right': ('length', 'height'), 'top': ('width', 'length'), 'bottom': ('width', 'length')}


def load_set(root):
    source = root / 'references/clean_set.json'
    if not source.is_file():
        raise ValueError('Missing references/clean_set.json: map each orthographic view to its clean reference image')
    data = read(source)
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('views'), dict) or not data['views']:
        raise ValueError('clean_set.json requires version=1 and a views object')
    unknown = set(data['views']) - ORTHO_VIEWS.keys()
    if unknown:
        raise ValueError(f'Unknown clean views {sorted(unknown)}; use {sorted(ORTHO_VIEWS)}')
    views = {}
    for view, path in data['views'].items():
        image = projects.inside(root, path)
        if not image.is_file():
            raise ValueError(f'{view}: missing image {path}')
        views[view] = (path, image)
    return views


def silhouette(image, threshold=28.0):
    """Boolean object mask: alpha when the image has transparency, else distance from the border colour."""
    from scipy import ndimage
    rgba = np.asarray(image.convert('RGBA'), dtype=float)
    alpha = rgba[..., 3]
    if alpha.min() < 250:
        mask = alpha > 127
    else:
        rgb = rgba[..., :3]
        border = np.concatenate((rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)))
        background = np.median(border, axis=0)
        mask = np.linalg.norm(rgb - background, axis=2) > threshold
    mask = ndimage.binary_fill_holes(ndimage.binary_opening(mask, iterations=1))
    labels, count = ndimage.label(mask)
    if not count:
        raise ValueError('No object found against the background')
    sizes = ndimage.sum(mask, labels, range(1, count + 1))
    keep = 1 + np.flatnonzero(sizes >= 0.01 * sizes.max())  # drop JPEG specks, keep separate parts (antenna, nacelles)
    return np.isin(labels, keep)


def extent(mask):
    rows, cols = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
    return {'bbox_px': [int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1],
            'horizontal_px': int(cols[-1] - cols[0] + 1), 'vertical_px': int(rows[-1] - rows[0] + 1)}


def masks(root, threshold=28.0, dry_run=False):
    p = projects.load(root)
    root = p['root']
    written = {}
    for view, (path, image_path) in load_set(root).items():
        with Image.open(image_path) as im:
            mask = silhouette(im, threshold)
        target = root / f'references/mask_{view}.png'
        if not dry_run:
            Image.fromarray((mask * 255).astype(np.uint8), 'L').save(target)
        written[view] = {'image': path, 'mask': None if dry_run else f'references/mask_{view}.png',
                         'coverage_pct': round(100 * float(mask.mean()), 2), **extent(mask)}
    return {'status': 'passed', 'views': written}


def check(root, threshold=28.0):
    """Cross-view consistency of the silhouette extents; writes references/clean_check.json."""
    p = projects.load(root)
    root = p['root']
    limit = thresholds(p['parameters'], 'references')['view_disagreement_pct']
    views, measured = load_set(root), {}
    for view, (path, image_path) in views.items():
        with Image.open(image_path) as im:
            box = extent(silhouette(im, threshold))
        horizontal, vertical = AXES[view]
        measured[view] = {'image': path, 'image_sha256': digest(image_path), **box,
                          'ratio': {f'{horizontal}/{vertical}': box['horizontal_px'] / box['vertical_px']}}

    def ratio(view, a, b):
        if view not in measured:
            return None
        h, v = AXES[view]
        values = {h: measured[view]['horizontal_px'], v: measured[view]['vertical_px']}
        return values[a] / values[b] if a in values and b in values else None

    comparisons = []
    def compare(label, x, y):
        if x is not None and y is not None:
            comparisons.append({'compare': label, 'a': round(x, 4), 'b': round(y, 4), 'disagreement_pct': round(100 * abs(x / y - 1), 2)})
    compare('length/height: left vs right', ratio('left', 'length', 'height'), ratio('right', 'length', 'height'))
    compare('width/height: front vs back', ratio('front', 'width', 'height'), ratio('back', 'width', 'height'))
    compare('length/width: top vs bottom', ratio('top', 'length', 'width'), ratio('bottom', 'length', 'width'))
    side = next((ratio(v, 'length', 'height') for v in ('right', 'left') if v in measured), None)
    plan = next((ratio(v, 'length', 'width') for v in ('top', 'bottom') if v in measured), None)
    end = next((ratio(v, 'width', 'height') for v in ('front', 'back') if v in measured), None)
    if None not in (side, plan, end):
        compare('length/height: side vs top x front', side, plan * end)
    failures = [f'{c["compare"]} disagree by {c["disagreement_pct"]}% (limit {limit}%)' for c in comparisons if c['disagreement_pct'] > limit]
    report = {'version': 1, 'checked_at': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), 'limit_pct': limit,
              'views': measured, 'comparisons': comparisons, 'failures': failures,
              'note': 'Extents include every part each view shows (nacelles, antenna); compare views that bound the same features.'}
    write(root / 'references/clean_check.json', report)
    return {'status': 'passed' if not failures else 'candidate', **report}
