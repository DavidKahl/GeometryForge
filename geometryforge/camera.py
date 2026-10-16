"""Reference camera calibration: solve a Blender-compatible camera from 3D datums and 2D picks.

Conventions match blender_review.py: millimeters, horizontal sensor fit, shift as a
fraction of image width, pixel origin at the top-left with y pointing down.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math

import numpy as np
from PIL import Image, ImageDraw

from . import projects
from .storage import digest, read, write
from .thresholds import resolve as thresholds


@dataclass
class Camera:
    position_mm: list
    target_mm: list
    up: list = field(default_factory=lambda: [0, 0, 1])
    lens_mm: float = 50.0
    sensor_width_mm: float = 36.0
    shift_x: float = 0.0
    shift_y: float = 0.0
    resolution: list = field(default_factory=lambda: [1280, 960])
    projection: str = 'perspective'
    ortho_scale_mm: float = None

    @classmethod
    def from_dict(cls, value, resolution=None):
        keys = {k: value[k] for k in ('position_mm', 'target_mm', 'up', 'lens_mm', 'sensor_width_mm', 'shift_x',
                                      'shift_y', 'projection', 'ortho_scale_mm') if k in value}
        return cls(**keys, resolution=list(resolution or value.get('resolution', [1280, 960])))

    def basis(self):
        position, target, up = (np.asarray(v, dtype=float) for v in (self.position_mm, self.target_mm, self.up))
        direction = target - position
        direction /= np.linalg.norm(direction)
        right = np.cross(direction, up)
        right /= np.linalg.norm(right)
        return position, right, np.cross(right, direction), direction

    def intrinsics(self):
        width, height = self.resolution
        f = self.lens_mm / self.sensor_width_mm * width
        return f, width / 2 + self.shift_x * width, height / 2 - self.shift_y * width

    def project(self, points):
        """World points (N,3) to continuous pixel coordinates (N,2) and view depth (N,)."""
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        position, right, vertical, direction = self.basis()
        local = points - position
        x, y, z = local @ right, -(local @ vertical), local @ direction
        f, cx, cy = self.intrinsics()
        if self.projection == 'orthographic':
            scale = self.resolution[0] / self.ortho_scale_mm
            return np.column_stack((cx + x * scale, cy + y * scale)), z
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.column_stack((cx + f * x / z, cy + f * y / z)), z

    def review(self):
        """Camera block accepted by review configs."""
        result = dict(position_mm=list(map(float, self.position_mm)), target_mm=list(map(float, self.target_mm)),
                      up=list(map(float, self.up)), projection=self.projection, lens_mm=float(self.lens_mm),
                      sensor_width_mm=float(self.sensor_width_mm), shift_x=float(self.shift_x), shift_y=float(self.shift_y))
        if self.projection == 'orthographic':
            result['ortho_scale_mm'] = float(self.ortho_scale_mm)
        return result


def _rotation(vector):
    from scipy.spatial.transform import Rotation
    return Rotation.from_rotvec(vector).as_matrix()


def _project_cv(points, rotation, position, f, cx, cy):
    local = (points - position) @ rotation.T
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.column_stack((cx + f * local[:, 0] / local[:, 2], cy + f * local[:, 1] / local[:, 2])), local[:, 2]


def _look_at(position, target, up):
    direction = target - position
    direction /= np.linalg.norm(direction)
    right = np.cross(direction, up)
    if np.linalg.norm(right) < 1e-9:
        right = np.cross(direction, [0, 1, 0])
    right /= np.linalg.norm(right)
    vertical = np.cross(right, direction)
    return np.array([right, -vertical, direction])


def _dlt(points, pixels):
    """Direct linear transform for six or more non-coplanar correspondences."""
    from scipy.linalg import rq
    def normalizer(values):
        center = values.mean(axis=0)
        scale = math.sqrt(values.shape[1]) / max(np.linalg.norm(values - center, axis=1).mean(), 1e-12)
        matrix = np.eye(values.shape[1] + 1)
        matrix[:-1, :-1] *= scale
        matrix[:-1, -1] = -scale * center
        return matrix
    T3, T2 = normalizer(points), normalizer(pixels)
    X = (np.column_stack((points, np.ones(len(points)))) @ T3.T)
    x = (np.column_stack((pixels, np.ones(len(pixels)))) @ T2.T)
    rows = []
    for (u, v, w), Xi in zip(x, X):
        rows.append(np.concatenate((np.zeros(4), -w * Xi, v * Xi)))
        rows.append(np.concatenate((w * Xi, np.zeros(4), -u * Xi)))
    P = np.linalg.svd(np.asarray(rows))[2][-1].reshape(3, 4)
    P = np.linalg.inv(T2) @ P @ T3
    if np.median(np.column_stack((points, np.ones(len(points)))) @ P[2]) < 0:
        P = -P
    M = P[:, :3]
    if np.linalg.det(M) <= 0:
        return None
    K, R = rq(M)
    signs = np.diag(np.sign(np.diag(K)))
    K, R = K @ signs, signs @ R
    if np.linalg.det(R) <= 0 or K[2, 2] <= 0:
        return None
    K /= K[2, 2]
    return R, -np.linalg.solve(M, P[:, 3]), (K[0, 0] + K[1, 1]) / 2, K[0, 2], K[1, 2]


def solve(points_3d, points_2d, image_size, lens_mm=None, sensor_width_mm=36.0, principal='center'):
    """Least-squares camera pose (and focal length unless lens_mm is given) from correspondences."""
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation
    points = np.asarray(points_3d, dtype=float)
    pixels = np.asarray(points_2d, dtype=float)
    width, height = image_size
    if points.ndim != 2 or points.shape[1] != 3 or pixels.shape != (len(points), 2):
        raise ValueError('Calibration needs matching 3D world_mm and 2D pixel points')
    if not (np.isfinite(points).all() and np.isfinite(pixels).all()):
        raise ValueError('Calibration points must be finite')
    if principal not in ('center', 'free'):
        raise ValueError('principal must be center or free')
    free_focal = lens_mm is None
    needed = 4 + free_focal + 2 * (principal == 'free')
    if len(points) < needed:
        raise ValueError(f'Calibration needs at least {needed} correspondences with these priors')
    spread = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
    if spread[1] <= 1e-6 * spread[0]:
        raise ValueError('Calibration datums are collinear; add points off that line')
    if np.linalg.svd(pixels - pixels.mean(axis=0), compute_uv=False)[1] <= 1e-6 * max(width, 1):
        raise ValueError('Calibration image points are collinear')
    extent = float(spread[0] / math.sqrt(len(points))) * 2 or 1.0
    f_prior = (lens_mm or 50.0) / sensor_width_mm * width
    centroid = points.mean(axis=0)

    def unpack(x):
        rotation, position = _rotation(x[:3]), x[3:6]
        index = 6
        f = f_prior
        if free_focal:
            f, index = math.exp(x[index]), index + 1
        cx, cy = (x[index], x[index + 1]) if principal == 'free' else (width / 2, height / 2)
        return rotation, position, f, cx, cy

    def residual(x):
        uv, depth = _project_cv(points, *unpack(x))
        penalty = np.minimum(depth, 0) * 1e3
        return np.concatenate(((uv - pixels).ravel(), penalty))

    starts = []
    if len(points) >= 6 and spread[2] > 1e-3 * spread[0]:
        dlt = _dlt(points, pixels)
        if dlt:
            R, C, f, cx, cy = dlt
            if f > 0:
                starts.append((R, C, f if free_focal else f_prior, cx, cy))
    golden = math.pi * (3 - math.sqrt(5))
    for scale in (0.6, 1.2, 2.5):
        distance = extent * f_prior / (scale * width) * 1.6
        for i in range(32):
            z = 1 - 2 * (i + .5) / 32
            r = math.sqrt(1 - z * z)
            direction = np.array([math.cos(golden * i) * r, math.sin(golden * i) * r, z])
            position = centroid + direction * distance
            starts.append((_look_at(position, centroid, np.array([0, 0, 1.0])), position, f_prior, width / 2, height / 2))
    def fit(x0, budget):
        try:
            result = least_squares(residual, np.asarray(x0, dtype=float), method='trf', x_scale='jac', max_nfev=budget)
        except (ValueError, np.linalg.LinAlgError):
            return None
        return result if np.isfinite(result.cost) else None

    # Screen every start briefly, then refine the most promising few.
    screened = []
    for R, C, f, cx, cy in starts:
        x0 = [*Rotation.from_matrix(R).as_rotvec(), *C]
        if free_focal:
            x0.append(math.log(f))
        if principal == 'free':
            x0 += [cx, cy]
        quick = fit(x0, 25)
        if quick is not None:
            screened.append(quick)
            if quick.cost < 1e-8 * len(points):
                break
    refined = [fit(s.x, 400) for s in sorted(screened, key=lambda s: s.cost)[:4]]
    refined = [r for r in refined if r is not None]
    if not refined:
        raise ValueError('Calibration did not converge')
    best = min(refined, key=lambda r: r.cost)
    rotation, position, f, cx, cy = unpack(best.x)
    uv, depth = _project_cv(points, rotation, position, f, cx, cy)
    if (depth <= 0).any():
        raise ValueError('Calibration placed datums behind the camera; check the correspondences')
    errors = np.linalg.norm(uv - pixels, axis=1)
    jac = best.jac[:2 * len(points)] * np.r_[np.ones(3), np.full(3, extent), np.ones(best.x.size - 6)]
    singular = np.linalg.svd(jac, compute_uv=False)
    condition = float(singular[0] / max(singular[-1], 1e-300))
    if not math.isfinite(condition) or condition > 1e8:
        raise ValueError('Calibration is under-constrained (pose and focal length trade off); add a lens prior or more spread datums')
    right, vertical, direction = rotation[0], -rotation[1], rotation[2]
    distance = float(max((centroid - position) @ direction, extent))
    camera = Camera(position_mm=position.tolist(), target_mm=(position + direction * distance).tolist(), up=vertical.tolist(),
                    lens_mm=f * sensor_width_mm / width, sensor_width_mm=sensor_width_mm,
                    shift_x=(cx - width / 2) / width, shift_y=-(cy - height / 2) / width, resolution=[int(width), int(height)])
    return {'camera': camera, 'residuals_px': errors.tolist(), 'rms_px': float(math.sqrt((errors ** 2).mean())),
            'max_px': float(errors.max()), 'condition': condition}


# Clean orthographic reference views in vehicle space (X forward, Y left, Z up): view direction and screen up.
ORTHO_VIEWS = {'front': ((-1, 0, 0), (0, 0, 1)), 'back': ((1, 0, 0), (0, 0, 1)),
               'left': ((0, -1, 0), (0, 0, 1)), 'right': ((0, 1, 0), (0, 0, 1)),
               'top': ((0, 0, -1), (1, 0, 0)), 'bottom': ((0, 0, 1), (1, 0, 0))}


def solve_orthographic(points_3d, points_2d, image_size, view):
    """Orthographic camera for a fixed view direction: a linear similarity fit of scale, offset and roll."""
    if view not in ORTHO_VIEWS:
        raise ValueError(f'Orthographic view must be one of {sorted(ORTHO_VIEWS)}')
    points = np.asarray(points_3d, dtype=float)
    pixels = np.asarray(points_2d, dtype=float)
    width, height = image_size
    if points.ndim != 2 or points.shape[1] != 3 or pixels.shape != (len(points), 2):
        raise ValueError('Calibration needs matching 3D world_mm and 2D pixel points')
    if not (np.isfinite(points).all() and np.isfinite(pixels).all()):
        raise ValueError('Calibration points must be finite')
    direction, up = (np.asarray(v, dtype=float) for v in ORTHO_VIEWS[view])
    right = np.cross(direction, up)
    vertical = np.cross(right, direction)
    a, b = points @ right, -(points @ vertical)
    if len(points) < 3:
        raise ValueError('Orthographic calibration needs at least 3 correspondences (2 fit exactly and give no error estimate)')
    if np.ptp(np.column_stack((a, b)), axis=0).max() <= 1e-6:
        raise ValueError('Calibration datums coincide in this view; add points spread across the image')
    # u = u0 + p*a - q*b,  v = v0 + q*a + p*b  with p = s cos(roll), q = s sin(roll)
    ones, zeros = np.ones_like(a), np.zeros_like(a)
    design = np.vstack((np.column_stack((a, -b, ones, zeros)), np.column_stack((b, a, zeros, ones))))
    target = np.concatenate((pixels[:, 0], pixels[:, 1]))
    (p, q, u0, v0), *_ = np.linalg.lstsq(design, target, rcond=None)
    scale, roll = math.hypot(p, q), math.atan2(q, p)
    if scale <= 0:
        raise ValueError('Orthographic calibration did not find a positive scale')
    errors = np.linalg.norm((design @ np.array([p, q, u0, v0]) - target).reshape(2, -1).T, axis=1)
    rolled_right = math.cos(roll) * right + math.sin(roll) * vertical
    rolled_up = -math.sin(roll) * right + math.cos(roll) * vertical
    depth = float((points @ direction).min()) - 20000.0  # camera well in front of every datum
    position = rolled_right * ((width / 2 - u0) / scale) + rolled_up * ((v0 - height / 2) / scale) + direction * depth
    camera = Camera(position_mm=position.tolist(), target_mm=(position + direction * 20000.0).tolist(), up=rolled_up.tolist(),
                    resolution=[int(width), int(height)], projection='orthographic', ortho_scale_mm=width / scale)
    return {'camera': camera, 'residuals_px': errors.tolist(), 'rms_px': float(math.sqrt((errors ** 2).mean())),
            'max_px': float(errors.max()), 'condition': float(np.linalg.cond(design)), 'roll_deg': math.degrees(roll)}


def resolve_point(value, parameters, label):
    if isinstance(value, dict) and set(value) == {'param'}:
        if value['param'] not in parameters:
            raise ValueError(f'{label}: unknown parameter {value["param"]}')
        value = parameters[value['param']]
    if not isinstance(value, list) or len(value) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f'{label}: expected three finite millimeter coordinates')
    return [float(v) for v in value]


def feature_curves(root, parameters):
    path = root / 'references/features.json'
    if not path.is_file():
        return []
    data = read(path)
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('curves'), list):
        raise ValueError('references/features.json requires version=1 and a curves list')
    curves = []
    for curve in data['curves']:
        if not isinstance(curve, dict) or not projects.ID.fullmatch(str(curve.get('id', ''))):
            raise ValueError('Feature curves need lowercase IDs')
        points = curve.get('points_mm')
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError(f'Feature curve {curve["id"]} needs at least two points')
        curves.append({'id': curve['id'], 'closed': bool(curve.get('closed', False)),
                       'points_mm': [resolve_point(p, parameters, f'features.{curve["id"]}') for p in points]})
    return curves


def box_edges(low, high):
    corners = np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])])
    pairs = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    return [corners[[a, b]] for a, b in pairs]


def draw_overlay(image, camera, curves=(), boxes=(), observed=None, solved=None, scale=1.0):
    """Draw projected feature curves, datum boxes and pick residuals onto an RGB image copy."""
    image = image.convert('RGB').copy()
    draw = ImageDraw.Draw(image)
    width = max(1, round(2 * scale))
    def polyline(points, colour, closed=False):
        uv, depth = camera.project(points)
        uv = uv * scale
        for a, b, da, db in zip(uv[:-1], uv[1:], depth[:-1], depth[1:]):
            if da > 0 and db > 0 and np.isfinite([*a, *b]).all():
                draw.line([tuple(a), tuple(b)], fill=colour, width=width)
        if closed and len(points) > 2:
            polyline(np.asarray([points[-1], points[0]]), colour)
    for edge in boxes:
        polyline(edge, '#ffd166')
    for curve in curves:
        polyline(np.asarray(curve['points_mm']), '#06d6a0', curve.get('closed', False))
    if observed is not None and solved is not None:
        for (ox, oy), (sx, sy) in zip(np.asarray(observed) * scale, np.asarray(solved) * scale):
            r = 5 * scale
            draw.ellipse([ox - r, oy - r, ox + r, oy + r], outline='#ef476f', width=width)
            draw.line([(ox, oy), (sx, sy)], fill='#ef476f', width=width)
            draw.line([(sx - r, sy), (sx + r, sy)], fill='#118ab2', width=width)
            draw.line([(sx, sy - r), (sx, sy + r)], fill='#118ab2', width=width)
    return image


def calibrate(root, cameras=None, dry_run=False):
    """Solve cameras from references/correspondences.json; write references/cameras.json and overlays."""
    p = projects.load(root)
    root = p['root']
    source = root / 'references/correspondences.json'
    if not source.is_file():
        raise ValueError('Missing references/correspondences.json (3D datums and their reference pixels)')
    data = read(source)
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('cameras'), dict) or not data['cameras']:
        raise ValueError('correspondences.json requires version=1 and a cameras object')
    chosen = cameras or list(data['cameras'])
    if set(chosen) - data['cameras'].keys():
        raise ValueError(f'Unknown calibration cameras: {sorted(set(chosen) - data["cameras"].keys())}')
    limit = thresholds(p['parameters'], 'calibration')['max_rms_px']
    curves = feature_curves(root, p['parameters'])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = root / 'review' / f'calibration-{stamp}'
    previous = read(root / 'references/cameras.json', {'version': 1, 'cameras': {}})
    solved, overlays, status = dict(previous.get('cameras', {})), {}, 'passed'
    for ident in chosen:
        spec = data['cameras'][ident]
        if not projects.ID.fullmatch(ident) or not isinstance(spec, dict):
            raise ValueError(f'Invalid calibration camera: {ident}')
        image_path = projects.inside(root, spec.get('image', ''))
        if not image_path.is_file():
            raise ValueError(f'{ident}: missing reference image {spec.get("image")}')
        with Image.open(image_path) as im:
            im.load()
            full = im.convert('RGB')
        crop = spec.get('crop', [0, 0, *full.size])
        if not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop) or not (0 <= crop[0] < crop[2] <= full.size[0] and 0 <= crop[1] < crop[3] <= full.size[1]):
            raise ValueError(f'{ident}: crop must be an in-bounds [left, top, right, bottom] pixel rectangle')
        priors = spec.get('priors', {})
        picks = spec.get('points', [])
        if not isinstance(picks, list) or len({q.get('id') for q in picks if isinstance(q, dict)}) != len(picks):
            raise ValueError(f'{ident}: points need unique ids')
        world = [resolve_point(q.get('world_mm'), p['parameters'], f'{ident}.{q["id"]}') for q in picks]
        pixel = []
        for q in picks:
            value = q.get('pixel')
            if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) for v in value):
                raise ValueError(f'{ident}.{q["id"]}: pixel needs [x, y]')
            pixel.append([value[0] - crop[0], value[1] - crop[1]])
        size = [crop[2] - crop[0], crop[3] - crop[1]]
        if spec.get('projection', 'perspective') == 'orthographic':
            result = solve_orthographic(world, pixel, size, spec.get('view'))
        elif spec.get('projection', 'perspective') == 'perspective':
            result = solve(world, pixel, size, priors.get('lens_mm'), priors.get('sensor_width_mm', 36.0), priors.get('principal', 'center'))
        else:
            raise ValueError(f'{ident}: projection must be perspective or orthographic')
        role = spec.get('role', 'supplementary')
        accepted = result['rms_px'] <= limit
        state = 'calibrated' if accepted else ('rejected' if role == 'primary' else 'inconsistent')
        if role == 'primary' and not accepted:
            status = 'candidate'
        camera = result['camera']
        entry = {**camera.review(), 'resolution': size, 'role': role, 'status': state, 'image': spec['image'],
                 'image_sha256': digest(image_path), 'crop': crop, 'rms_px': result['rms_px'], 'max_px': result['max_px'],
                 'max_rms_px': limit, 'condition': result['condition'],
                 'residuals_px': {q['id']: e for q, e in zip(picks, result['residuals_px'])},
                 'correspondences_sha256': digest(source), 'solved_at': stamp}
        if camera.projection == 'orthographic':
            entry.update(view=spec['view'], roll_deg=result['roll_deg'])
        if spec.get('mask'):
            mask = projects.inside(root, spec['mask'])
            if not mask.is_file():
                raise ValueError(f'{ident}: missing mask {spec["mask"]}')
            entry.update(mask=spec['mask'], mask_sha256=digest(mask))
        solved[ident] = entry
        if not dry_run:
            out.mkdir(parents=True, exist_ok=True)
            low, high = np.min(world, axis=0), np.max(world, axis=0)
            uv, _ = camera.project(world)
            image = draw_overlay(full.crop(crop), camera, curves, box_edges(low, high), pixel, uv)
            overlays[ident] = str(out / f'{ident}_overlay.png')
            image.save(overlays[ident])
    document = {'version': 1, 'cameras': solved}
    if not dry_run:
        write(root / 'references/cameras.json', document)
    return {'status': status, 'cameras': {k: solved[k] for k in chosen}, 'overlays': overlays,
            'cameras_file': None if dry_run else str(root / 'references/cameras.json'),
            'note': 'Overlay: red circles are picks, blue crosses their reprojection, green feature curves, yellow datum box.'}


def load_cameras(root):
    data = read(root / 'references/cameras.json', None)
    if data is None:
        return {}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('cameras'), dict):
        raise ValueError('references/cameras.json requires version=1')
    return data['cameras']


def camera_current(root, entry):
    """True if the image, mask and correspondences still match the solved camera."""
    try:
        if digest(projects.inside(root, entry['image'])) != entry['image_sha256']:
            return False
        if entry.get('mask') and digest(projects.inside(root, entry['mask'])) != entry.get('mask_sha256'):
            return False
        return digest(root / 'references/correspondences.json') == entry['correspondences_sha256']
    except (KeyError, OSError, ValueError):
        return False
