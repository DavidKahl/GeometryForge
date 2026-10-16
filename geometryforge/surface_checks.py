"""Typed surface checks: exterior seams, recessed housings, mechanical mating and global form.

Runs in the host check worker on evaluated world-space evidence, so Blender and Houdini
outputs are measured by the same code. Every check measures surface relationships;
none passes merely because two meshes touch.
"""
from pathlib import Path
import math

import numpy as np
from scipy.spatial import cKDTree

from geometryforge.meshquery import TriangleIndex, as_mesh, edges, open_edges, sample_surface, vertex_normals
from geometryforge.thresholds import resolve

KINDS = ('seam', 'recess', 'mating', 'global')
GLOBAL_TESTS = ('silhouette_iou', 'open_edges', 'coverage')
SURFACE_ROLES = ('design', 'high_detail')


def select(payload, selector, roles=SURFACE_ROLES, label='selection'):
    """Objects of one declared part, optionally narrowed by object name and role."""
    if isinstance(selector, str):
        selector = {'part': selector}
    if not isinstance(selector, dict) or selector.get('part') not in payload['objects']:
        raise ValueError(f'{label}: select a part declared by this check')
    names = selector.get('objects')
    wanted = selector.get('roles', roles)
    chosen = [o for o in payload['objects'][selector['part']]
              if o.get('role', 'design') in wanted and (not names or o['name'] in names)]
    if names and {o['name'] for o in chosen} != set(names):
        raise ValueError(f'{label}: missing objects {sorted(set(names) - {o["name"] for o in chosen})}')
    if not chosen:
        raise ValueError(f'{label}: no {"/".join(wanted)} objects in part {selector["part"]}')
    return chosen


def attributes(objects, name):
    """Concatenated per-vertex attribute, NaN where an object lacks it; None if absent everywhere."""
    values, present = [], False
    for obj in objects:
        data = obj.get('point_attributes', {}).get(name)
        if data is None:
            values.append(np.full(len(obj['vertices']), np.nan))
        else:
            present = True
            values.append(np.asarray(data, dtype=float).reshape(len(obj['vertices']), -1)[:, 0])
    return np.concatenate(values) if present else None


def surface(objects):
    V, F = as_mesh(objects)
    if not len(F):
        raise ValueError('Selected objects have no faces')
    return V, F


def master_index(payload, spec):
    V, F = surface(select(payload, spec.get('master'), ('guide', 'design'), 'master'))
    return TriangleIndex(V, F)


def angle(a, b):
    return np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', a, b), -1, 1)))


def worst(points, values, count=10, reverse=True):
    order = np.argsort(values)
    order = order[::-1] if reverse else order
    return [{'location_mm': np.round(points[i], 3).tolist(), 'value': round(float(values[i]), 5)} for i in order[:count]]


def exterior(V, F, master, limits, objects):
    """Flush exterior skin: near the master, facing the same way, not the solidify shell or rim."""
    sd, _, mnormal, _ = master.signed_distance(V)
    normals = vertex_normals(V, F)
    mask = (sd > -limits['exterior_band_mm']) & (np.einsum('ij,ij->i', normals, mnormal) > math.cos(math.radians(limits['exterior_normal_deg'])))
    for name in ('gf_inner', 'gf_solidify_rim'):
        values = attributes(objects, name)
        if values is not None:
            mask &= ~(np.nan_to_num(values) >= 0.5)
    bound = attributes(objects, 'guide_bound')
    if bound is not None:
        mask &= np.nan_to_num(bound, nan=1.0) >= .999  # pocket returns are recessed on purpose
    return mask, sd, normals, mnormal


def seam(payload, limits, spec):
    master = master_index(payload, spec)
    sides = {}
    for key in ('a', 'b'):
        objects = select(payload, spec.get(key), label=key)
        V, F = surface(objects)
        mask, sd, normals, mnormal = exterior(V, F, master, limits, objects)
        skin = F[mask[F].all(axis=1)]
        border = np.unique(open_edges(skin)) if len(skin) else np.zeros(0, dtype=np.int64)
        if len(skin):
            # Skin-only normals: border vertices must not average in the bevel roll-off.
            normals = np.where(mask[:, None], vertex_normals(V, skin), normals)
        sides[key] = dict(V=V, sd=sd, normals=normals, mnormal=mnormal, mask=mask, border=border, skin=skin,
                          index=TriangleIndex(V, skin) if len(skin) else None)
    a, b = sides['a'], sides['b']
    deviation = np.concatenate([np.abs(s['sd'][s['mask']]) for s in (a, b)])
    deviation_points = np.concatenate([s['V'][s['mask']] for s in (a, b)])
    measurements = {'exterior_vertices': int(len(deviation)),
                    'master_deviation_max_mm': float(deviation.max()) if len(deviation) else None}
    failures, report = [], []
    if not len(deviation):
        failures.append('No exterior skin found near the master on either side')
    elif measurements['master_deviation_max_mm'] > limits['master_deviation_mm']:
        failures.append(f'Exterior skin leaves the master by {measurements["master_deviation_max_mm"]:.3f} mm')
        report += [{'metric': 'master_deviation_mm', **w} for w in worst(deviation_points, deviation, 5)]
    pairs = []
    if len(a['border']) and len(b['border']):
        # Mutual nearest border vertices: borders running away from the seam do not pair.
        reach = 2 * limits['gap_max_mm'] + 2
        distance, forward = cKDTree(b['V'][b['border']]).query(a['V'][a['border']], distance_upper_bound=reach)
        found = np.nonzero(np.isfinite(distance))[0]
        if len(found):
            _, back = cKDTree(a['V'][a['border']]).query(b['V'][b['border'][forward[found]]])
            mutual = found[back == found]
            pairs = list(zip(a['border'][mutual], b['border'][forward[mutual]]))
    measurements['seam_pairs'] = len(pairs)
    if len(pairs) < limits['min_pairs']:
        failures.append(f'No shared seam between {spec["a"]} and {spec["b"]}: {len(pairs)} paired border vertices')
        return measurements, failures, report
    i, j = np.asarray([x for x, _ in pairs]), np.asarray([y for _, y in pairs])
    p, q = a['V'][i], b['V'][j]
    middle = (p + q) / 2
    _, _, mnorm, _ = master.signed_distance(middle)
    delta = q - p
    step = np.abs(np.einsum('ij,ij->i', delta, mnorm))
    across = delta - np.einsum('ij,ij->i', delta, mnorm)[:, None] * mnorm
    gap = np.linalg.norm(across, axis=1)
    g1 = np.maximum(angle(a['normals'][i], b['normals'][j]) - angle(a['mnormal'][i], b['mnormal'][j]), 0)

    def curvature(side, index, away):
        """Normal turn per mm from the seam vertex to the skin surface `probe_mm` across the seam."""
        from geometryforge.meshquery import interpolate
        _, point, face, _ = side['index'].closest(side['V'][index] + limits['probe_mm'] * away)
        normal = interpolate(side['V'], side['skin'], face, point, side['normals'])
        normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-300)[:, None]
        length = np.linalg.norm(point - side['V'][index], axis=1)
        turn = np.radians(angle(side['normals'][index], normal))
        return np.where(length > 1e-6, turn / np.maximum(length, 1e-6), 0)

    unit = across / np.maximum(gap, 1e-9)[:, None]
    ka, kb = curvature(a, i, -unit), curvature(b, j, unit)
    # Relative curvature mismatch, floored at a reference curvature: two nearly flat sides (R of
    # metres) differ only by discretization noise and are compared against the floor instead.
    g2 = np.abs(ka - kb) / np.maximum(ka + kb, 2 * limits['flat_curvature_per_mm'])
    measurements.update(step_max_mm=float(step.max()), gap_min_mm=float(gap.min()), gap_max_mm=float(gap.max()),
                        normal_angle_p95_deg=float(np.percentile(g1, 95)), normal_angle_max_deg=float(g1.max()),
                        curvature_ratio_p95=float(np.percentile(g2, 95)), curvature_ratio_max=float(g2.max()))
    for metric, values, limit, label in (('step_mm', step, limits['step_mm'], 'Seam step'),):
        if values.max() > limit:
            failures.append(f'{label} {values.max():.3f} mm exceeds {limit} mm')
            report += [{'metric': metric, **w} for w in worst(middle, values, 5)]
    if gap.min() < limits['gap_min_mm'] or gap.max() > limits['gap_max_mm']:
        failures.append(f'Seam gap {gap.min():.2f}-{gap.max():.2f} mm outside {limits["gap_min_mm"]}-{limits["gap_max_mm"]} mm')
        report += [{'metric': 'gap_mm', **w} for w in worst(middle, np.abs(gap - (limits['gap_min_mm'] + limits['gap_max_mm']) / 2), 5)]
    if measurements['normal_angle_p95_deg'] > limits['normal_angle_deg']:
        failures.append(f'Tangent break {measurements["normal_angle_p95_deg"]:.2f} deg (p95) exceeds {limits["normal_angle_deg"]} deg')
        report += [{'metric': 'normal_angle_deg', **w} for w in worst(middle, g1, 5)]
    if measurements['curvature_ratio_p95'] > limits['curvature_ratio']:
        failures.append(f'Curvature mismatch {measurements["curvature_ratio_p95"]:.3f} (p95) exceeds {limits["curvature_ratio"]}')
        report += [{'metric': 'curvature_ratio', **w} for w in worst(middle, g2, 5)]
    return measurements, failures, report


def recess(payload, limits, spec):
    master = master_index(payload, spec)
    objects = select(payload, spec.get('panel'), label='panel')
    V, F = surface(objects)
    weights = attributes(objects, 'guide_bound')
    if weights is None:
        raise ValueError('Recess checks need guide_bound vertex weights; build pockets with api.surf.recessed_pocket_extrude')
    weights = np.nan_to_num(weights, nan=1.0)
    sd, _, mnormal, _ = master.signed_distance(V)
    normals = vertex_normals(V, F)
    failures, report = [], []
    protruding = [(V, sd)]
    for n, selector in enumerate(spec.get('contents', [])):
        CV, _ = as_mesh(select(payload, selector, label=f'contents[{n}]'))
        protruding.append((CV, master.signed_distance(CV)[0]))
    points = np.concatenate([x for x, _ in protruding])
    outside = np.concatenate([d for _, d in protruding])
    measurements = {'protrusion_max_mm': float(outside.max()),
                    'proud_vertices': int((outside > limits['protrusion_mm']).sum())}
    if measurements['proud_vertices']:
        failures.append(f'{measurements["proud_vertices"]} vertices stand proud of the master by up to {outside.max():.3f} mm')
        report += [{'metric': 'protrusion_mm', **w} for w in worst(points, outside, 5)]
    front = np.ones(len(V), dtype=bool)
    for name in ('gf_inner', 'gf_solidify_rim'):
        values = attributes(objects, name)
        if values is not None:
            front &= ~(np.nan_to_num(values) >= 0.5)
    facing = np.einsum('ij,ij->i', normals, mnormal) > math.cos(math.radians(limits['exterior_normal_deg']))
    rim = front & facing & (weights >= limits['rim_weight'])
    measurements['rim_step_max_mm'] = float(np.abs(sd[rim]).max()) if rim.any() else None
    if rim.any() and measurements['rim_step_max_mm'] > limits['rim_step_mm']:
        failures.append(f'Flush rim steps {measurements["rim_step_max_mm"]:.3f} mm off the master')
        report += [{'metric': 'rim_step_mm', **w} for w in worst(V[rim], np.abs(sd[rim]), 5)]
    face_front = front[F].all(axis=1)
    face_weight = weights[F].mean(axis=1)
    pocket = attributes(objects, 'gf_pocket')
    if pocket is not None:
        # Helper-built pockets mark rim, return, wall and floor; pure rim faces stay out.
        band = face_front & (np.nan_to_num(pocket)[F] >= .5).all(axis=1) & (face_weight < limits['rim_weight'])
    else:
        band = face_front & (face_weight > 1e-6) & (face_weight < limits['rim_weight'])
    measurements['pocket_faces'] = int(band.sum())
    if not band.any():
        failures.append('No recessed pocket found: no front faces with guide_bound falloff below the rim weight')
        return measurements, failures, report
    corners = V[F]
    centroids = corners.mean(axis=1)
    fn = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    fn /= np.maximum(np.linalg.norm(fn, axis=1), 1e-300)[:, None]
    # One pull axis per pocket: the mean master normal around its flush rim. Deep inside a pocket the
    # nearest master point can lie on another face of the hull, so local normals are not used.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    pocket_faces = F[band]
    links = np.concatenate([pocket_faces[:, [0, 1]], pocket_faces[:, [1, 2]]])
    graph = coo_matrix((np.ones(len(links)), (links[:, 0], links[:, 1])), shape=(len(V), len(V)))
    _, component = connected_components(graph, directed=False)
    axes = np.zeros((band.sum(), 3))
    face_component = component[pocket_faces[:, 0]]
    _, _, nearest_normals, _ = master.signed_distance(centroids[band])
    designed = None
    if spec.get('ring'):
        # A declared rim ring carries the pocket's design pull axis.
        rim_ring = select(payload, spec['ring'], ('interface',), 'ring')
        metadata = rim_ring[0].get('metadata', {})
        designed = np.asarray(metadata.get('pull_axis') or ring(rim_ring)[1], dtype=float)
    for label in np.unique(face_component):
        members = np.unique(pocket_faces[face_component == label])
        rim_members = members[weights[members] >= limits['rim_weight']]
        if designed is not None:
            axis = designed
        else:
            axis = mnormal[rim_members].mean(axis=0) if len(rim_members) else nearest_normals[face_component == label].mean(axis=0)
        axes[face_component == label] = axis / max(np.linalg.norm(axis), 1e-300)
    measurements['pockets'] = int(len(np.unique(face_component)))
    draft = np.degrees(np.arcsin(np.clip(np.einsum('ij,ij->i', fn[band], axes), -1, 1)))
    measurements['draft_min_deg'] = float(draft.min())
    if draft.min() < limits['draft_min_deg']:
        failures.append(f'Pocket wall draft {draft.min():.2f} deg is below {limits["draft_min_deg"]} deg (undercut or straight wall)')
        report += [{'metric': 'draft_deg', **w} for w in worst(centroids[band], draft, 5, reverse=False)]
    # Fillet: section radius of the painted return, i.e. how fast the face angle to the pull axis changes.
    # Rotation about the axis (plan-view corners of an opening) is not part of the return profile.
    face_axis = np.full((len(F), 3), np.nan)
    face_axis[np.nonzero(band)[0]] = axes
    faces_by_edge = {}
    for face in np.nonzero(face_front & ((face_weight > 1e-6) | band))[0]:
        tri = F[face]
        for k in range(3):
            faces_by_edge.setdefault(tuple(sorted((int(tri[k]), int(tri[(k + 1) % 3])))), []).append(face)
    radii, where = [], []
    for pair in faces_by_edge.values():
        if len(pair) != 2 or not (band[pair[0]] or band[pair[1]]):
            continue
        axis = face_axis[pair[0]] if band[pair[0]] else face_axis[pair[1]]
        sections = [math.asin(max(-1.0, min(1.0, float(fn[f] @ axis)))) for f in pair]
        turn = abs(sections[0] - sections[1])
        if turn > 1e-4:
            radii.append(float(np.linalg.norm(centroids[pair[0]] - centroids[pair[1]])) / turn)
            where.append((centroids[pair[0]] + centroids[pair[1]]) / 2)
    measurements['fillet_min_mm'] = min(radii) if radii else None
    if radii and min(radii) < limits['fillet_min_mm']:
        failures.append(f'Painted return turns with a {min(radii):.2f} mm radius, below {limits["fillet_min_mm"]} mm')
        report += [{'metric': 'fillet_mm', **w} for w in worst(np.asarray(where), np.asarray(radii), 5, reverse=False)]
    return measurements, failures, report


def ring(objects):
    """Arc-length centroid, plane axis and mean radius of interface polylines (same math as bind_to_ring)."""
    from geometryforge.game import world_vertices
    from geometryforge.sections import ring_frame
    points, edges, axes, offset = [], [], [], 0
    for obj in objects:
        V = world_vertices(obj)
        E = np.asarray(obj.get('edges', []), dtype=np.int64).reshape(-1, 2)
        if not len(E):
            raise ValueError(f'{obj["name"]}: interface rings need edges')
        points.append(V)
        edges.append(E + offset)
        offset += len(V)
        if obj.get('metadata', {}).get('axis'):
            axes.append(np.asarray(obj['metadata']['axis'], dtype=float))
    centroid, axis, radius = ring_frame(np.concatenate(points), np.concatenate(edges), axes[0] if axes else None)
    return centroid, axis, radius, bool(axes)


def inside_opening(points, opening):
    """Points whose projection falls inside a ring polygon, within one ring radius of its plane."""
    from geometryforge.game import world_vertices
    centroid, axis, radius, _ = ring([opening])
    V = world_vertices(opening)
    neighbours = {}
    for a, b in opening['edges']:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    order, previous, current = [opening['edges'][0][0]], None, opening['edges'][0][0]
    while True:
        following = [n for n in neighbours[current] if n != previous]
        if not following or following[0] == order[0]:
            break
        previous, current = current, following[0]
        order.append(current)
    u = np.cross(axis, [1, 0, 0] if abs(axis[0]) < .9 else [0, 1, 0])
    u /= np.linalg.norm(u)
    w = np.cross(axis, u)
    polygon = np.column_stack(((V[order] - centroid) @ u, (V[order] - centroid) @ w))
    offset = points - centroid
    sx, sy = offset @ u, offset @ w
    inside = np.zeros(len(points), dtype=bool)
    for (x1, y1), (x2, y2) in zip(polygon, np.roll(polygon, -1, axis=0)):
        crosses = (y1 > sy) != (y2 > sy)
        with np.errstate(divide='ignore', invalid='ignore'):
            inside ^= crosses & (sx < (x2 - x1) * (sy - y1) / (y2 - y1) + x1)
    return inside & (np.abs(offset @ axis) < radius)


def mating(payload, limits, spec):
    if 'lap_min_mm' not in limits or 'lap_max_mm' not in limits:
        raise ValueError('Mating checks need thresholds.lap_min_mm and lap_max_mm for this joint')
    parent = ring(select(payload, spec.get('parent'), ('interface',), 'parent'))
    child = ring(select(payload, spec.get('child'), ('interface',), 'child'))
    cosine = abs(float(parent[1] @ child[1])) if not (parent[3] and child[3]) else float(parent[1] @ child[1])
    axis_deg = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
    delta = child[0] - parent[0]
    along = float(delta @ parent[1])
    lateral = float(np.linalg.norm(delta - along * parent[1]))
    measurements = {'axis_deg': axis_deg, 'centroid_offset_mm': lateral, 'lap_mm': abs(along),
                    'parent_radius_mm': parent[2], 'child_radius_mm': child[2], 'oriented': parent[3] and child[3]}
    failures = []
    if axis_deg > limits['axis_deg']:
        failures.append(f'Rings are {axis_deg:.3f} deg off axis (limit {limits["axis_deg"]})')
    if lateral > limits['centroid_mm']:
        failures.append(f'Ring centres are {lateral:.3f} mm off axis (limit {limits["centroid_mm"]})')
    if not limits['lap_min_mm'] <= abs(along) <= limits['lap_max_mm']:
        failures.append(f'Engagement lap {abs(along):.2f} mm outside {limits["lap_min_mm"]}-{limits["lap_max_mm"]} mm')
    if spec.get('skin') and spec.get('child_solids'):
        SV, SF = as_mesh([o for s in spec['skin'] for o in select(payload, s, label='skin')])
        CV, CF = as_mesh([o for s in spec['child_solids'] for o in select(payload, s, label='child_solids')])
        E, _ = edges(CF)
        crossings, crossed = TriangleIndex(SV, SF).segment_crossings(CV[E[:, 0]], CV[E[:, 1]])
        measurements['skin_crossings'] = crossings
        if crossings > limits['skin_crossings_max']:
            failures.append(f'{crossings} child edges pierce the exterior skin')
            return measurements, failures, [{'metric': 'skin_crossing', 'location_mm': np.round((CV[a] + CV[b]) / 2, 3).tolist()}
                                            for a, b in E[crossed][:10]]
    return measurements, failures, []


def silhouette(payload, limits, spec):
    from PIL import Image, ImageDraw
    from geometryforge.camera import Camera
    import json
    root = Path(payload.get('snapshot_root') or '.')
    cameras = json.loads((root / 'references/cameras.json').read_text(encoding='utf-8'))['cameras']
    ident = spec.get('camera')
    if ident not in cameras:
        raise ValueError(f'Calibrated camera {ident!r} is missing; run geometryforge calibrate')
    entry = cameras[ident]
    if entry.get('status') != 'calibrated':
        raise ValueError(f'Camera {ident} is {entry.get("status")}; recalibrate before scoring silhouettes')
    if not entry.get('mask'):
        raise ValueError(f'Camera {ident} has no reference mask; silhouette scores need a calibrated camera and a mask')
    with Image.open(root / entry['mask']) as im:
        im.load()
        mask = im.crop(entry['crop'])
        mask = (np.asarray(mask.getchannel('A')) > 127) if mask.mode in ('RGBA', 'LA') else (np.asarray(mask.convert('L')) > 127)
    width, height = entry['resolution']
    scale = min(1.0, 1024 / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    camera = Camera.from_dict(entry, resolution=entry['resolution'])
    objects = [o for s in spec.get('targets', []) for o in select(payload, s, ('design', 'high_detail', 'guide'), 'targets')]
    if not objects:
        raise ValueError('Silhouette checks need targets')
    V, F = as_mesh(objects)
    uv, depth = camera.project(V)
    uv = uv * scale
    image = Image.new('L', size, 0)
    draw = ImageDraw.Draw(image)
    tri = F[(depth[F] > 0).all(axis=1)]
    corners = uv[tri]
    visible = (corners[:, :, 0].max(axis=1) >= 0) & (corners[:, :, 0].min(axis=1) <= size[0]) & \
              (corners[:, :, 1].max(axis=1) >= 0) & (corners[:, :, 1].min(axis=1) <= size[1])
    for triangle in corners[visible]:
        draw.polygon([tuple(c) for c in triangle], fill=255)
    rendered = np.asarray(image) > 127
    reference = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(size, Image.NEAREST)) > 127
    union = (rendered | reference).sum()
    iou = float((rendered & reference).sum() / union) if union else 0.0
    previous = (payload.get('previous') or {}).get('measurements', {}).get('silhouette_iou')
    delta = None if previous is None else iou - previous
    measurements = {'silhouette_iou': iou, 'delta_iou': delta, 'previous_iou': previous, 'camera': ident,
                    'camera_rms_px': entry.get('rms_px'), 'raster': list(size),
                    'model_only_px': int((rendered & ~reference).sum()), 'reference_only_px': int((reference & ~rendered).sum())}
    failures = []
    if iou < limits['silhouette_iou_min']:
        failures.append(f'Silhouette IoU {iou:.3f} below {limits["silhouette_iou_min"]}')
        if delta is not None and delta < limits['delta_iou_min']:
            failures.append(f'Silhouette regressed by {-delta:.3f} since the previous run')
    return measurements, failures, []


def open_edge_test(payload, limits, spec):
    region = spec.get('region_mm')
    count, where = 0, []
    for n, selector in enumerate(spec.get('targets', [])):
        for obj in select(payload, selector, ('design', 'high_detail', 'guide'), f'targets[{n}]'):
            V, F = as_mesh([obj])
            E = open_edges(F)
            middle = (V[E[:, 0]] + V[E[:, 1]]) / 2 if len(E) else np.zeros((0, 3))
            if region:
                low, high = np.asarray(region[0]), np.asarray(region[1])
                middle = middle[((middle >= low) & (middle <= high)).all(axis=1)]
            count += len(middle)
            where += [{'object': obj['name'], 'location_mm': np.round(m, 3).tolist()} for m in middle[:5]]
    failures = [f'{count} open boundary edges (limit {limits["open_edges_max"]})'] if count > limits['open_edges_max'] else []
    return {'open_edges': count}, failures, where[:10]


def coverage(payload, limits, spec):
    master = select(payload, spec.get('master'), ('guide', 'design'), 'master')
    MV, MF = surface(master)
    samples, area = sample_surface(MV, MF, spec.get('sample_mm', 10.0))
    keep = np.ones(len(samples), dtype=bool)
    if spec.get('region_mm'):
        low, high = (np.asarray(v) for v in spec['region_mm'])
        keep &= ((samples >= low) & (samples <= high)).all(axis=1)
    for low, high in spec.get('exclude_mm', []):
        keep &= ~((samples >= np.asarray(low)) & (samples <= np.asarray(high))).all(axis=1)
    for n, selector in enumerate(spec.get('openings', [])):
        for opening in select(payload, selector, ('interface',), f'openings[{n}]'):
            keep &= ~inside_opening(samples, opening)
    panels = [o for n, s in enumerate(spec.get('panels', [])) for o in select(payload, s, label=f'panels[{n}]')]
    PV, PF = surface(panels)
    distance = TriangleIndex(PV, PF).closest(samples[keep])[0]
    uncovered = distance > limits['cover_tolerance_mm']
    points, weights = samples[keep][uncovered], area[keep][uncovered]
    measurements = {'samples': int(keep.sum()), 'uncovered_samples': int(uncovered.sum()),
                    'uncovered_area_mm2': float(weights.sum()), 'max_gap_mm': float(distance.max()) if len(distance) else 0.0}
    failures = []
    if measurements['uncovered_area_mm2'] > limits['uncovered_area_mm2_max']:
        failures.append(f'{measurements["uncovered_area_mm2"]:.0f} mm2 of master surface is not covered by panels')
    return measurements, failures, worst(points, distance[uncovered], 10) if len(points) else []


def verify(payload):
    kind = payload.get('kind')
    if kind not in KINDS:
        raise ValueError(f'Unknown typed check kind: {kind}')
    spec = payload.get('spec', {})
    limits = resolve(payload.get('parameters', {}), kind, payload.get('thresholds'))
    if kind == 'global':
        test = spec.get('test')
        if test not in GLOBAL_TESTS:
            raise ValueError(f'global checks need test in {GLOBAL_TESTS}')
        measurements, failures, report = {'silhouette_iou': silhouette, 'open_edges': open_edge_test, 'coverage': coverage}[test](payload, limits, spec)
        measurements['test'] = test
    else:
        measurements, failures, report = {'seam': seam, 'recess': recess, 'mating': mating}[kind](payload, limits, spec)
    mode = payload.get('mode', 'enforce')
    met = not failures
    return {'passed': met or mode == 'measure', 'kind': kind, 'mode': mode, 'thresholds': limits,
            'measurements': measurements, 'acceptance': {'met': met, 'failures': failures}, 'worst': report}
