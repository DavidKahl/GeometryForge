"""Read-only native appearance evidence, separate from validation and safe points."""
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import projects
from .blender_review import part_color, part_srgb
from .process import resolve_blender, run
from .storage import digest, read, write
from .worker_env import worker_environment

RENDER_MODES = ('clay', 'glossy', 'silhouette', 'wireframe', 'zebra', 'normal', 'part_id')
MODES = (*RENDER_MODES, 'overlay')
DEFAULT_MODES = ['clay', 'glossy', 'silhouette', 'wireframe']
ROLES = ('design', 'high_detail', 'render', 'printable', 'guide')
AXES = {'x': 0, 'y': 1, 'z': 2}


def _number(value, label, positive=False):
    if type(value) not in (float, int) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{label} must be a finite {"positive " if positive else ""}number')
    return value


def _vector(value, label):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f'{label} must contain three numbers')
    return [_number(v, label) for v in value]


def _reference(root, path, label):
    file = projects.inside(root, path)
    if not file.is_file():
        raise ValueError(f'{label}: missing reference {path}')
    with Image.open(file) as im:
        im.load()
        return file, im.size


def _calibrated(root, ident, label):
    from .camera import load_cameras, camera_current
    cameras = load_cameras(root)
    if ident not in cameras:
        raise ValueError(f'{label}: camera ref {ident!r} is not in references/cameras.json; run geometryforge calibrate')
    entry = cameras[ident]
    return entry, camera_current(root, entry)


def validate_config(config, root):
    """Normalize a v1 review configuration; reference paths are project-relative."""
    if not isinstance(config, dict) or type(config.get('version')) is not int or config.get('version') != 1:
        raise ValueError('Review config requires version=1')
    views = [*config.get('views', []), *expand_presets(config.get('presets', []), root)]
    if not isinstance(config.get('views', []), list) or not views:
        raise ValueError('Review config needs at least one view')
    normalized, ids = [], set()
    for view in views:
        if not isinstance(view, dict):
            raise ValueError('Each view must be an object')
        ident = view.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', ident) or ident in ids:
            raise ValueError(f'Invalid or duplicate view ID: {ident}')
        ids.add(ident)
        camera = view.get('camera', {})
        if not isinstance(camera, dict):
            raise ValueError(f'{ident}: camera must be an object')
        calibration = None
        if 'ref' in camera:
            if set(camera) != {'ref'} or 'reference' in view:
                raise ValueError(f'{ident}: a camera ref supplies camera, reference, crop and mask by itself')
            entry, current = _calibrated(root, camera['ref'], ident)
            calibration = {'ref': camera['ref'], 'status': entry.get('status'), 'rms_px': entry.get('rms_px'),
                           'current': current, 'crop': entry['crop'], 'mask': entry.get('mask')}
            camera = {k: entry[k] for k in ('position_mm', 'target_mm', 'up', 'projection', 'lens_mm', 'sensor_width_mm',
                                            'shift_x', 'shift_y', 'ortho_scale_mm') if k in entry}
            width, height = entry['resolution']
            scale = min(1.0, 1600 / max(width, height))
            view = {**view, 'reference': entry['image'], 'reference_crop': entry['crop'],
                    'resolution': view.get('resolution', [max(32, round(width * scale)), max(32, round(height * scale))])}
            if entry.get('mask'):
                view.setdefault('reference_mask', entry['mask'])
            if abs(view['resolution'][0] / view['resolution'][1] - width / height) > .01 * width / height:
                raise ValueError(f'{ident}: resolution must keep the calibrated aspect ratio {width}:{height}')
        position = _vector(camera.get('position_mm'), 'camera.position_mm')
        target = _vector(camera.get('target_mm'), 'camera.target_mm')
        up = _vector(camera.get('up', [0, 0, 1]), 'camera.up')
        direction = [b-a for a, b in zip(position, target)]
        cross = [direction[1]*up[2]-direction[2]*up[1], direction[2]*up[0]-direction[0]*up[2], direction[0]*up[1]-direction[1]*up[0]]
        cross_size = sum(v*v for v in cross)
        if not math.isfinite(cross_size) or cross_size <= 1e-12:
            raise ValueError(f'{ident}: camera direction and up must be nonzero and nonparallel')
        projection = camera.get('projection', 'perspective')
        if projection not in ('perspective', 'orthographic'):
            raise ValueError(f'{ident}: invalid camera projection')
        cam = dict(position_mm=position, target_mm=target, up=up, projection=projection,
                   lens_mm=_number(camera.get('lens_mm', 50), 'camera.lens_mm', True),
                   sensor_width_mm=_number(camera.get('sensor_width_mm', 36), 'camera.sensor_width_mm', True),
                   shift_x=_number(camera.get('shift_x', 0), 'camera.shift_x'),
                   shift_y=_number(camera.get('shift_y', 0), 'camera.shift_y'))
        if projection == 'orthographic':
            cam['ortho_scale_mm'] = _number(camera.get('ortho_scale_mm'), 'camera.ortho_scale_mm', True)
        resolution = view.get('resolution', [1280, 960])
        if not isinstance(resolution, list) or len(resolution) != 2 or any(type(v) is not int or not 32 <= v <= 4096 for v in resolution):
            raise ValueError(f'{ident}: resolution needs two integers between 32 and 4096')
        modes = view.get('modes', DEFAULT_MODES)
        if not isinstance(modes, list) or not modes or any(not isinstance(m, str) or m not in MODES for m in modes) or len(set(modes)) != len(modes):
            raise ValueError(f'{ident}: invalid review modes')
        if 'overlay' in modes and not set(modes) & set(RENDER_MODES):
            raise ValueError(f'{ident}: overlay draws onto a rendered mode; add clay or another render mode')
        selection = view.get('selection', {})
        if not isinstance(selection, dict) or set(selection) - {'parts', 'objects', 'roles'}:
            raise ValueError(f'{ident}: selection supports parts, objects and roles only')
        for key, values in selection.items():
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f'{ident}: selection.{key} needs nonempty names')
        if set(selection.get('roles', [])) - set(ROLES):
            raise ValueError(f'{ident}: selection.roles must be among {ROLES}')
        samples = view.get('samples', 16)
        if type(samples) is not int or not 1 <= samples <= 256:
            raise ValueError(f'{ident}: samples must be between 1 and 256')
        result = dict(id=ident, camera=cam, resolution=resolution, selection=selection, modes=modes, samples=samples,
                      notes=str(view.get('notes', 'Camera matching is approximate; this is appearance evidence, not validation.'
                                         if not calibration else 'Calibrated reference camera; appearance evidence, not validation.')))
        if calibration:
            result['calibration'] = calibration
        if 'studio' in view:
            studio = view['studio']
            if not isinstance(studio, dict) or set(studio) != {'center_mm', 'size_mm'}:
                raise ValueError(f'{ident}: studio needs center_mm and size_mm')
            result['studio'] = dict(center_mm=_vector(studio['center_mm'], 'studio.center_mm'),
                                    size_mm=_number(studio['size_mm'], 'studio.size_mm', True))
        if 'section' in view:
            section = view['section']
            if not isinstance(section, dict) or section.get('axis') not in AXES or section.get('keep', 'negative') not in ('negative', 'positive'):
                raise ValueError(f'{ident}: section needs axis x|y|z, offset_mm and keep negative|positive')
            result['section'] = dict(axis=section['axis'], offset_mm=_number(section.get('offset_mm', 0), 'section.offset_mm'),
                                     keep=section.get('keep', 'negative'))
        if 'zebra' in view:
            zebra = view['zebra']
            if not isinstance(zebra, dict) or set(zebra) - {'stripes', 'rotation_deg'}:
                raise ValueError(f'{ident}: zebra supports stripes and rotation_deg')
            result['zebra'] = dict(stripes=_number(zebra.get('stripes', 12), 'zebra.stripes', True),
                                   rotation_deg=_vector(zebra.get('rotation_deg', [0, 0, 0]), 'zebra.rotation_deg'))
        elif 'zebra' in modes:
            result['zebra'] = dict(stripes=12, rotation_deg=[0, 0, 0])
        if 'reference' in view:
            ref = view['reference']
            if not isinstance(ref, str):
                raise ValueError(f'{ident}: reference must be a project-relative image path')
            path, (width, height) = _reference(root, ref, ident)
            crop = view.get('reference_crop', [0, 0, width, height])
            if not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop) or not (0 <= crop[0] < crop[2] <= width and 0 <= crop[1] < crop[3] <= height):
                raise ValueError(f'{ident}: reference_crop must be an in-bounds [left, top, right, bottom] pixel rectangle')
            result.update(reference=str(path), reference_sha256=digest(path), reference_crop=crop)
            if 'reference_mask' in view:
                if view['reference_mask'] == 'alpha':
                    result.update(reference_mask='alpha')
                else:
                    mask, size = _reference(root, view['reference_mask'], ident)
                    if size != (width, height):
                        raise ValueError(f'{ident}: reference_mask must match the reference image size')
                    result.update(reference_mask=str(mask), reference_mask_sha256=digest(mask))
        elif 'reference_crop' in view or 'reference_mask' in view:
            raise ValueError(f'{ident}: reference_crop and reference_mask require a reference')
        normalized.append(result)
    return {'version': 1, 'views': normalized}


def _bounds(preset, root):
    bounds = preset.get('bounds_mm')
    if bounds == 'safe_point':
        from . import engine, gates
        p = projects.load(root)
        route = gates.route(p)
        safe = p['state'].get('targets', {}).get(route, {}).get('safe_point')
        run = engine.record(p, safe) if safe else None
        if not run:
            raise ValueError(f'Preset bounds_mm=safe_point needs a {route} safe point')
        boxes = [part['assembly_bounds_mm'] for backend in run['targets'][route]['backends'].values() for part in backend['parts'].values()]
        bounds = [np.min([b[0] for b in boxes], axis=0).tolist(), np.max([b[1] for b in boxes], axis=0).tolist()]
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError('Presets need bounds_mm [[min], [max]] or "safe_point"')
    low, high = (np.asarray(_vector(list(b), 'bounds_mm'), dtype=float) for b in bounds)
    if (high <= low).any():
        raise ValueError('bounds_mm max must exceed min on every axis')
    return low, high


def expand_presets(presets, root):
    """Concrete views for survey presets: orthographic, three-quarter, calibrated, sections, close-ups."""
    if not isinstance(presets, list):
        raise ValueError('presets must be a list')
    views = []
    for preset in presets:
        if not isinstance(preset, dict) or preset.get('preset') not in ('survey21', 'standard6', 'survey'):
            raise ValueError('preset must be survey21, standard6 or survey')
        kind = preset['preset']
        prefix = preset.get('id_prefix', kind)
        low, high = _bounds(preset, root)
        centre, size = (low + high) / 2, high - low
        span = float(np.linalg.norm(size))
        common = {k: preset[k] for k in ('modes', 'samples', 'selection', 'studio', 'zebra') if k in preset}
        common.setdefault('studio', {'center_mm': centre.tolist(), 'size_mm': span})
        resolution = preset.get('resolution', [1280, 960])
        orthographic = preset.get('orthographic', True)
        three_quarter = {'survey21': 8, 'standard6': 0}.get(kind, preset.get('three_quarter', 8))
        sections = preset.get('sections', [{'axis': a} for a in 'xyz'] if kind == 'survey21' else [] if kind == 'standard6' else preset.get('sections', []))
        refs = preset.get('camera_refs', []) if kind != 'standard6' else []
        close_ups = preset.get('close_ups') if 'close_ups' in preset else (
            [{'name': name, 'target_mm': [float(v) for v in target], 'size_mm': span / 3} for name, target in (
                ('front', [high[0] - size[0] / 6, centre[1], centre[2]]), ('rear', [low[0] + size[0] / 6, centre[1], centre[2]]),
                ('top', [centre[0], centre[1], high[2]]))] if kind == 'survey21' else [])
        distance = span * 3
        fit = 1.15 * span
        if orthographic:
            for name, axis in (('front', [1, 0, 0]), ('rear', [-1, 0, 0]), ('left', [0, 1, 0]), ('right', [0, -1, 0]),
                               ('top', [0, 0, 1]), ('bottom', [0, 0, -1])):
                up = [0, 1, 0] if axis[2] else [0, 0, 1]
                views.append({**common, 'id': f'{prefix}_{name}', 'resolution': resolution,
                              'camera': {'position_mm': (centre + np.asarray(axis) * distance).tolist(), 'target_mm': centre.tolist(),
                                         'up': up, 'projection': 'orthographic', 'ortho_scale_mm': fit}})
        lens = 50
        half_fov = math.atan(18 / lens)
        far = (fit / 2) / math.tan(half_fov)
        for n in range(three_quarter):
            azimuth = math.radians(45 + 90 * (n % 4))
            elevation = math.radians(25 if n < 4 else -20)
            direction = np.array([math.cos(elevation) * math.cos(azimuth), math.cos(elevation) * math.sin(azimuth), math.sin(elevation)])
            views.append({**common, 'id': f'{prefix}_q{n + 1}', 'resolution': resolution,
                          'camera': {'position_mm': (centre + direction * far).tolist(), 'target_mm': centre.tolist(), 'lens_mm': lens}})
        for ref in refs:
            views.append({**common, 'id': f'{prefix}_ref_{ref}', 'camera': {'ref': ref}})
        for n, section in enumerate(sections):
            axis = section.get('axis')
            if axis not in AXES:
                raise ValueError('Preset sections need axis x|y|z')
            normal = np.zeros(3)
            normal[AXES[axis]] = 1
            offset = section.get('offset_mm', float(centre[AXES[axis]]))
            up = [0, 1, 0] if axis == 'z' else [0, 0, 1]
            views.append({**common, 'id': f'{prefix}_section_{axis}{n + 1}', 'resolution': resolution,
                          'section': {'axis': axis, 'offset_mm': offset, 'keep': 'negative'},
                          'camera': {'position_mm': (centre + normal * distance).tolist(), 'target_mm': centre.tolist(), 'up': up,
                                     'projection': 'orthographic', 'ortho_scale_mm': fit}})
        for n, close in enumerate(close_ups):
            target = np.asarray(_vector(list(close['target_mm']), 'close_ups.target_mm'))
            reach = _number(close.get('size_mm', span / 3), 'close_ups.size_mm', True)
            direction = np.array([.55, -.6, .58]) / np.linalg.norm([.55, -.6, .58])
            views.append({**common, 'id': f'{prefix}_close_{close.get("name", n + 1)}', 'resolution': resolution,
                          'studio': {'center_mm': target.tolist(), 'size_mm': reach * 2},
                          'camera': {'position_mm': (target + direction * reach / math.tan(half_fov)).tolist(), 'target_mm': target.tolist(), 'lens_mm': lens}})
    return views


def _mask(path, crop, size, alpha=False):
    with Image.open(path) as im:
        im.load()
        im = im.crop(crop)
        values = im.getchannel('A') if alpha or im.mode in ('RGBA', 'LA') else im.convert('L')
        return np.asarray(values.resize(size, Image.NEAREST)) > 127


def silhouette_iou(view, silhouette_path):
    """IoU of the render silhouette (black object on white) and the reference mask (white object)."""
    if not view.get('reference_mask'):
        return None
    with Image.open(silhouette_path) as im:
        rendered = np.asarray(im.convert('L')) < 128
    size = tuple(view['resolution'])
    alpha = view['reference_mask'] == 'alpha'
    reference = _mask(view['reference'] if alpha else view['reference_mask'], view['reference_crop'], size, alpha)
    union = (rendered | reference).sum()
    return float((rendered & reference).sum() / union) if union else 0.0


def overlay(root, parameters, view, base, bounds, out):
    """Project feature curves and the selection box onto a render and, when calibrated, the reference."""
    from .camera import Camera, box_edges, draw_overlay, feature_curves
    camera = Camera.from_dict(view['camera'], resolution=view['resolution'])
    curves = feature_curves(root, parameters)
    boxes = box_edges(*bounds) if bounds else []
    with Image.open(base) as im:
        draw_overlay(im, camera, curves, boxes).save(out / f'{view["id"]}_overlay.png')
    result = {'overlay': str(out / f'{view["id"]}_overlay.png')}
    if view.get('reference') and view.get('calibration'):
        with Image.open(view['reference']) as im:
            ref = im.crop(view['reference_crop']).resize(tuple(view['resolution']))
            draw_overlay(ref, camera, curves, boxes).save(out / f'{view["id"]}_reference_overlay.png')
        result['reference_overlay'] = str(out / f'{view["id"]}_reference_overlay.png')
    return result


def contact_sheet(view, artifacts, out, metrics=None, blind=False):
    panels = []
    if view.get('reference'):
        label = (f'REFERENCE (calibrated, rms {view["calibration"]["rms_px"]:.2f} px)' if view.get('calibration')
                 else 'REFERENCE (approximate camera)')
        with Image.open(view['reference']) as im:
            panels.append((label, im.crop(view['reference_crop']).convert('RGB')))
    for mode, path in artifacts.items():
        with Image.open(path) as im:
            panels.append((mode.upper(), im.convert('RGB')))
    cell = (640, 480)
    footer = 0 if blind or not metrics else 28
    sheet = Image.new('RGB', (cell[0]*len(panels), cell[1]+32+footer), '#151922')
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(panels):
        sheet.paste(ImageOps.pad(im, cell, color='#151922'), (i*cell[0], 32))
        draw.text((i*cell[0]+12, 10), label, fill='white')
    if footer:
        text = '   '.join(f'{k}: {v:.3f}' if isinstance(v, float) else f'{k}: {v}' for k, v in metrics.items() if v is not None)
        draw.text((12, cell[1]+40), text, fill='#ffd166')
    path = out / f'{view["id"]}_{"blind" if blind else "contact"}.png'
    sheet.save(path)
    return str(path)


def baseline_metrics(root, view, exclude, baseline=None):
    """Silhouette IoU of the same view in an earlier complete review with the same camera and mask."""
    folders = [root / 'review' / baseline] if baseline else sorted((root / 'review').glob('*'), reverse=True)
    for folder in folders:
        if folder.name == exclude:
            continue
        report = read(folder / 'report.json', {})
        if report.get('status') != 'complete':
            if baseline:
                raise ValueError(f'Baseline review {baseline} is not complete')
            continue
        old = next((v for v in report.get('settings', {}).get('views', []) if v['id'] == view['id']), None)
        if old and old['camera'] == view['camera'] and old.get('reference_mask_sha256') == view.get('reference_mask_sha256') \
                and report.get('metrics', {}).get(view['id'], {}).get('silhouette_iou') is not None:
            return report['review_id'], report['metrics'][view['id']]['silhouette_iou']
        if baseline:
            raise ValueError(f'Baseline review {baseline} has no matching silhouette for view {view["id"]}')
    return None, None


def execute(project, scene, config, blender=None, timeout=900, blind=False, baseline=None):
    p = projects.load(project)
    root = p['root']
    # Scene/config arguments are explicit CLI paths, relative to the calling cwd.
    scene, config = Path(scene).resolve(), Path(config).resolve()
    if scene.suffix.lower() != '.blend' or not scene.is_file():
        raise ValueError(f'Missing Blender scene: {scene}')
    if not config.is_file():
        raise ValueError(f'Missing review config: {config}')
    if type(timeout) is not int or timeout <= 0:
        raise ValueError('timeout must be a positive integer')
    settings = validate_config(read(config), root)
    executable = resolve_blender(blender)
    ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = root / 'review' / ident
    out.mkdir(parents=True)
    source_hash = digest(scene)
    renderer = projects.PACKAGE / 'blender_review.py'
    report = dict(version=1, review_id=ident, status='running', scene=str(scene), scene_sha256=source_hash,
                  config=str(config), config_sha256=digest(config), renderer_sha256=digest(renderer), settings=settings,
                  blind=blind, note='Appearance evidence only; no geometry builders, saved scene edits or safe-point promotion.')
    write(out / 'config.json', settings)
    write(out / 'report.json', report)
    request = out / 'request.json'
    render_settings = {'version': 1, 'views': [{**v, 'modes': [m for m in v['modes'] if m in RENDER_MODES]} for v in settings['views']]}
    write(request, dict(scene=str(scene), settings=render_settings, out=str(out)))
    try:
        code = run([executable, '--background', '--factory-startup', '--python-exit-code', '1', '--python',
                    renderer, '--', request], cwd=root, env=worker_environment(),
                   log=out / 'blender.log', timeout=timeout)
        if code:
            raise RuntimeError(f'Blender review failed ({code}); see {out / "blender.log"}')
        native = read(out / 'result.json')
        if not isinstance(native, dict) or not native.get('views'):
            raise RuntimeError('Blender review did not return view evidence')
        if digest(scene) != source_hash or digest(config) != report['config_sha256']:
            raise RuntimeError('Review inputs changed during rendering; evidence cannot be attributed to the recorded hashes')
        if digest(renderer) != report['renderer_sha256']:
            raise RuntimeError('Review renderer changed during rendering; repeat the review with stable tooling')
        expected = {v['id']: v for v in settings['views']}
        if [v.get('id') for v in native['views']] != list(expected):
            raise RuntimeError('Blender review returned unexpected views')
        metrics = {}
        for view in native['views']:
            setting = expected[view['id']]
            rendered = [m for m in setting['modes'] if m in RENDER_MODES]
            if set(view.get('artifacts', {})) != set(rendered):
                raise RuntimeError('Blender review returned incomplete render modes')
            for mode, path in view['artifacts'].items():
                if not Path(path).resolve().is_relative_to(out.resolve()) or not Path(path).is_file():
                    raise RuntimeError(f'Missing or out-of-folder review artifact: {path}')
                with Image.open(path) as im:
                    im.load()
                    if list(im.size) != setting['resolution']:
                        raise RuntimeError(f'Unexpected review image dimensions: {path}')
                    if mode == 'silhouette':
                        if im.mode != 'RGBA':
                            raise RuntimeError('Silhouette render requires holdout alpha evidence')
                        mask = im.getchannel('A').convert('RGB')
                if mode == 'silhouette':
                    mask.save(path)
            if setting.get('reference') and digest(setting['reference']) != setting['reference_sha256']:
                raise RuntimeError('Reference changed during rendering')
            if 'overlay' in setting['modes']:
                base = next(view['artifacts'][m] for m in ('clay', 'glossy', 'zebra', *rendered) if m in view['artifacts'])
                extra = overlay(root, p['parameters'], setting, base, view.get('bounds_mm'), out)
                view['artifacts']['overlay'] = extra['overlay']
                if 'reference_overlay' in extra:
                    view['reference_overlay'] = extra['reference_overlay']
            if 'silhouette' in view['artifacts'] and setting.get('reference_mask'):
                iou = silhouette_iou(setting, view['artifacts']['silhouette'])
                previous_id, previous = baseline_metrics(root, setting, ident, baseline)
                metrics[view['id']] = {'silhouette_iou': iou, 'baseline_review': previous_id,
                                       'delta_iou': None if previous is None else iou - previous,
                                       'calibrated': bool(setting.get('calibration', {}).get('status') == 'calibrated'
                                                          and setting['calibration'].get('current'))}
            view['contact_sheet'] = contact_sheet(setting, view['artifacts'], out, metrics.get(view['id']), blind)
            view['artifact_sha256'] = {k: digest(p) for k, p in view['artifacts'].items()}
            view['contact_sha256'] = digest(view['contact_sheet'])
        report.update(status='complete', source_unchanged=True, **native, metrics=metrics)
    except (Exception, KeyboardInterrupt) as exc:
        try:
            unchanged = digest(scene) == source_hash
        except OSError:
            unchanged = False
        report.update(status='cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc),
                      source_unchanged=unchanged)
        write(out / 'report.json', report)
        raise RuntimeError(f'{exc}; retained review report: {out / "report.json"}') from exc
    write(out / 'report.json', report)
    result = {**report, 'report': str(out / 'report.json'), 'log': str(out / 'blender.log')}
    if blind:
        # Critique the sheets before reading scores or check results; the report keeps them.
        result.pop('metrics')
        result['note'] = 'Blind review: write the visual critique from the sheets first, then read report.json metrics.'
    return result


def diff(project, before, after, parts, margin_px=1, tolerance=0):
    """Region invariance between two reviews: pixels outside the edited parts must not change."""
    from scipy.ndimage import binary_dilation
    root = projects.load(project)['root']
    if not parts:
        raise ValueError('Name the edited parts')
    reports = []
    for ident in (before, after):
        report = read(root / 'review' / ident / 'report.json', {})
        if report.get('status') != 'complete':
            raise ValueError(f'Review {ident} is missing or incomplete')
        reports.append(report)
    settings = [{v['id']: v for v in r['settings']['views']} for r in reports]
    rendered = [{v['id']: v for v in r['views']} for r in reports]
    common = [v for v in settings[0] if v in settings[1] and all(m in rendered[i][v]['artifacts'] for i in (0, 1) for m in ('part_id', 'normal'))]
    if not common:
        raise ValueError('No shared views with part_id and normal renders in both reviews')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = root / 'review' / f'diff-{stamp}-{uuid.uuid4().hex[:6]}'
    out.mkdir(parents=True)
    colours = [np.asarray(part_srgb(part)) for part in parts]
    result, failures = {}, []
    for ident in common:
        a, b = settings[0][ident], settings[1][ident]
        if a['camera'] != b['camera'] or a['resolution'] != b['resolution'] or a.get('section') != b.get('section'):
            raise ValueError(f'View {ident}: cameras, resolutions or sections differ between the reviews')
        images = {}
        for mode in ('part_id', 'normal'):
            images[mode] = [np.asarray(Image.open(rendered[i][ident]['artifacts'][mode]).convert('RGB')).astype(int) for i in (0, 1)]
        edited = np.zeros(images['part_id'][0].shape[:2], dtype=bool)
        for image in images['part_id']:
            for colour in colours:
                edited |= (np.abs(image - colour) <= 2).all(axis=2)
        region = binary_dilation(edited, iterations=margin_px) if margin_px else edited
        changed = np.zeros_like(edited)
        for mode in ('part_id', 'normal'):
            changed |= (np.abs(images[mode][0] - images[mode][1]) > tolerance).any(axis=2)
        outside = changed & ~region
        heat = np.zeros((*edited.shape, 3), dtype=np.uint8)
        heat[region] = (40, 70, 120)
        heat[changed & region] = (90, 200, 255)
        heat[outside] = (255, 60, 60)
        Image.fromarray(heat).save(out / f'{ident}_diff.png')
        result[ident] = {'edited_px': int(region.sum()), 'changed_inside_px': int((changed & region).sum()),
                         'changed_outside_px': int(outside.sum()), 'heatmap': str(out / f'{ident}_diff.png')}
        if outside.any():
            failures.append(f'{ident}: {int(outside.sum())} pixels changed outside the edited parts')
    report = {'version': 1, 'before': before, 'after': after, 'parts': list(parts), 'margin_px': margin_px, 'tolerance': tolerance,
              'views': result, 'failures': failures, 'status': 'passed' if not failures else 'candidate',
              'note': 'Compares exact part_id and normal renders; lighting renders are not used because shadows legitimately change.'}
    write(out / 'report.json', report)
    return {**report, 'report': str(out / 'report.json')}
