"""Master-hull surfacing helpers for Blender recipes (api.surf).

Curvature authority lives in one hidden master hull. Panels are sliced from its cage and
shrinkwrapped back onto it; pockets fall off from a flush rim; children bind to interface
rings instead of scalar datums. Every result is an ordinary editable modifier stack.
Units are scene millimeters.
"""
import json
import math

import numpy as np

from .sections import ring_frame as _ring_frame

GROUPS = ('guide_bound', 'gf_inner', 'gf_solidify_rim', 'gf_pocket')


def _bpy():
    import bpy
    return bpy


def _group(obj, name):
    return obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)


def _evaluated_points(obj, keep=('SUBSURF', 'SHRINKWRAP')):
    """World vertices, edges and group weights with only the surface-defining modifiers enabled."""
    bpy = _bpy()
    states = [(m, m.show_viewport) for m in obj.modifiers]
    try:
        for modifier, _ in states:
            modifier.show_viewport = modifier.type in keep
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
        try:
            matrix = np.asarray(obj.matrix_world)
            local = np.array([v.co for v in mesh.vertices], dtype=float)
            world = (np.column_stack((local, np.ones(len(local)))) @ matrix.T)[:, :3]
            names = {g.index: g.name for g in obj.vertex_groups}
            weights = {}
            for vertex in mesh.vertices:
                for element in vertex.groups:
                    weights.setdefault(names[element.group], np.zeros(len(local)))[vertex.index] = element.weight
            edges = np.array([e.vertices[:] for e in mesh.edges], dtype=np.int64)
            return world, edges, weights
        finally:
            evaluated.to_mesh_clear()
    finally:
        for modifier, shown in states:
            modifier.show_viewport = shown
        bpy.context.view_layer.update()


def _cycle(edges):
    neighbours = {}
    for a, b in edges:
        neighbours.setdefault(int(a), []).append(int(b))
        neighbours.setdefault(int(b), []).append(int(a))
    if not neighbours or any(len(n) != 2 for n in neighbours.values()):
        raise ValueError('Interface loop is not a single closed edge cycle')
    start = next(iter(neighbours))
    order, previous, current = [start], None, start
    while True:
        following = [n for n in neighbours[current] if n != previous][0]
        if following == start:
            break
        order.append(following)
        previous, current = current, following
    if len(order) != len(neighbours):
        raise ValueError('Interface loop has more than one cycle; give each opening its own loop ID')
    return order


class Surfacing:
    def __init__(self, api):
        self.api = api

    # Generic editable meshes -------------------------------------------------------------
    def mesh_object(self, name, verts, faces, role='design', smooth=True, output_id=None, edges=(), **metadata):
        bpy = _bpy()
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(map(float, v)) for v in verts], [tuple(e) for e in edges], [tuple(f) for f in faces])
        mesh.validate()
        mesh.update()
        if smooth and len(mesh.polygons):
            mesh.shade_smooth()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        if role is None:
            return self.api.mark(obj)
        return self.api.register_output(obj, output_id, role, **metadata)

    def patch(self, name, fn, u=(0.0, 1.0), v=(-1.0, 1.0), segments=(10, 10), thickness=0.0, levels=2, role='design', **metadata):
        """Editable quad cage from a parametric surface fn(u, v) -> (x, y, z), with optional subdivision and thickness."""
        nu, nv = segments
        us = [u[0] + (u[1] - u[0]) * i / nu for i in range(nu + 1)]
        vs = [v[0] + (v[1] - v[0]) * j / nv for j in range(nv + 1)]
        verts = [fn(a, b) for a in us for b in vs]
        faces = [(i * (nv + 1) + j, (i + 1) * (nv + 1) + j, (i + 1) * (nv + 1) + j + 1, i * (nv + 1) + j + 1)
                 for i in range(nu) for j in range(nv)]
        obj = self.mesh_object(name, verts, faces, role, **metadata)
        if levels:
            sub = obj.modifiers.new('Patch curvature', 'SUBSURF')
            sub.levels = sub.render_levels = levels
        if thickness:
            solid = obj.modifiers.new('Patch thickness', 'SOLIDIFY')
            solid.thickness, solid.offset, solid.use_even_offset = thickness, -1, True
        return obj

    def loft(self, name, rings, caps=True, flat=False, role='design', **metadata):
        """Quad loft through rings of equal length (lists of 3D points); flat keeps planar section breaks crisp."""
        count = len(rings[0])
        if any(len(r) != count for r in rings):
            raise ValueError('Loft rings need equal point counts')
        verts = [tuple(p) for ring in rings for p in ring]
        faces = [(k * count + i, k * count + (i + 1) % count, (k + 1) * count + (i + 1) % count, (k + 1) * count + i)
                 for k in range(len(rings) - 1) for i in range(count)]
        if caps:
            faces += [tuple(reversed(range(count))), tuple(range((len(rings) - 1) * count, len(rings) * count))]
        obj = self.mesh_object(name, verts, faces, role, smooth=not flat, **metadata)
        if flat:
            obj.modifiers.new('Planar feature shading', 'WEIGHTED_NORMAL').keep_sharp = True
        return obj

    def sweep(self, name, points, radius, sides=16, cyclic=False, role='design', **metadata):
        """Tube mesh along a polyline with parallel-transport frames (evaluated mesh, unlike a bevelled curve)."""
        points = np.asarray(points, dtype=float)
        tangents = np.gradient(points, axis=0)
        if cyclic:
            tangents = np.roll(points, -1, 0) - np.roll(points, 1, 0)
        tangents /= np.linalg.norm(tangents, axis=1)[:, None]
        normal = np.cross(tangents[0], [0, 0, 1] if abs(tangents[0][2]) < .9 else [1, 0, 0])
        normal /= np.linalg.norm(normal)
        rings = []
        for centre, t in zip(points, tangents):
            normal = normal - t * (normal @ t)
            normal /= np.linalg.norm(normal)
            binormal = np.cross(t, normal)
            rings.append([tuple(centre + radius * (normal * math.cos(2 * math.pi * k / sides) + binormal * math.sin(2 * math.pi * k / sides)))
                          for k in range(sides)])
        if cyclic:
            rings.append(rings[0])
        return self.loft(name, rings, caps=not cyclic, role=role, **metadata)

    # Master hull and panels ---------------------------------------------------------------
    def master_hull(self, name, verts, faces, regions=None, creases=None, levels=4, output_id=None):
        """One watertight low-poly cage; regions name face sets for panels and openings; creases replace support loops."""
        obj = self.mesh_object(name, verts, faces, 'guide', output_id=output_id, kind='master_hull')
        mesh = obj.data
        regions = regions or {}
        ids = {region: n + 1 for n, region in enumerate(regions)}
        values = [0] * len(mesh.polygons)
        for region, members in regions.items():
            for face in members:
                if values[face]:
                    raise ValueError(f'Face {face} is in two master regions')
                values[face] = ids[region]
        mesh.attributes.new('gf_region', 'INT', 'FACE').data.foreach_set('value', values)
        obj['gf_regions'] = json.dumps(ids)
        if creases:
            lookup = {tuple(sorted(e.vertices)): e.index for e in mesh.edges}
            layer = mesh.attributes.get('crease_edge') or mesh.attributes.new('crease_edge', 'FLOAT', 'EDGE')
            for a, b, value in creases:
                layer.data[lookup[tuple(sorted((a, b)))]].value = value
        sub = obj.modifiers.new('Master curvature', 'SUBSURF')
        sub.levels = sub.render_levels = levels
        sub.use_creases = True
        return obj

    def slice_panel(self, guide, region, openings=(), name=None, output_id=None, conform=True):
        """Copy one master region's cage faces as a panel; opening borders get gf_loop_<opening> groups.

        conform moves the copied cage onto the master's evaluated surface. A subdivision limit surface lies
        inside its control cage, so an unconformed panel cage would leave partly-weighted vertices proud.
        """
        import bmesh
        bpy = _bpy()
        ids = json.loads(guide['gf_regions'])
        for key in (region, *openings):
            if key not in ids:
                raise ValueError(f'Unknown master region: {key}')
        bm = bmesh.new()
        bm.from_mesh(guide.data)
        layer = bm.faces.layers.int.get('gf_region')
        bm.verts.ensure_lookup_table()
        loops = {}
        for opening in openings:
            border = {v.index for f in bm.faces if f[layer] == ids[opening] for v in f.verts}
            border &= {v.index for f in bm.faces if f[layer] == ids[region] for v in f.verts}
            if not border:
                raise ValueError(f'Opening {opening} does not touch region {region}')
            # Positions identify the loop across later topology edits.
            loops[opening] = [tuple(bm.verts[i].co) for i in sorted(border)]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != ids[region]], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        mesh = bpy.data.meshes.new(name or f'{guide.name} {region}')
        bm.to_mesh(mesh)
        bm.free()
        mesh.attributes.remove(mesh.attributes['gf_region'])
        # The master's edge creases stay on the copied cage: the panel then subdivides to the master's own limit
        # surface, and shrinkwrap only corrects small offsets instead of chasing sharp styling edges it rounded off.
        mesh.shade_smooth()
        obj = bpy.data.objects.new(name or f'{guide.name} {region}', mesh)  # checks select objects by this name
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = guide.matrix_world.copy()
        if conform:
            graph = bpy.context.evaluated_depsgraph_get()
            before = np.array([v.co for v in mesh.vertices], dtype=float)
            for vertex in mesh.vertices:
                hit, location, _, _ = guide.closest_point_on_mesh(vertex.co, depsgraph=graph)
                if hit:
                    vertex.co = location
            mesh.update()
            after = np.array([v.co for v in mesh.vertices], dtype=float)
            loops = {key: [tuple(after[int(np.linalg.norm(before - p, axis=1).argmin())]) for p in points] for key, points in loops.items()}
        self.api.register_output(obj, output_id, 'design', kind='panel', region=region, openings=list(openings))
        obj['gf_loops'] = json.dumps(loops)
        self._refresh_groups(obj)
        return obj

    def _refresh_groups(self, obj):
        """Before pockets: guide_bound=1 everywhere, gf_loop_<id> on the recorded opening borders, bevel weight on open borders."""
        import bmesh
        loops = json.loads(obj.get('gf_loops', '{}'))
        everything = [v.index for v in obj.data.vertices]
        _group(obj, 'guide_bound').add(everything, 1.0, 'REPLACE')
        for name in ('gf_inner', 'gf_solidify_rim'):
            _group(obj, name)
        coords = np.array([v.co for v in obj.data.vertices], dtype=float)
        for opening, points in loops.items():
            group = _group(obj, f'gf_loop_{opening}')
            group.remove(everything)
            members = []
            for point in points:
                distance = np.linalg.norm(coords - point, axis=1)
                if distance.min() < 1e-3:
                    members.append(int(distance.argmin()))
            group.add(members, 1.0, 'REPLACE')
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        layer = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        for edge in bm.edges:
            edge[layer] = 1.0 if edge.is_boundary else 0.0
        bm.to_mesh(obj.data)
        bm.free()

    def inset_panel_perimeter(self, obj, distance=4.0, gap=0.0):
        """Add a control loop `distance` inside every open border; seam borders (not openings) retreat by gap/2."""
        import bmesh
        loops = json.loads(obj.get('gf_loops', '{}'))
        opening_points = np.array([p for points in loops.values() for p in points], dtype=float).reshape(-1, 3)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.inset_region(bm, faces=bm.faces[:], use_boundary=True, use_even_offset=True, thickness=distance, depth=0)
        if gap:
            boundary = {v for e in bm.edges if e.is_boundary for v in e.verts}
            moves = []
            for v in boundary:
                if len(opening_points) and np.linalg.norm(opening_points - np.asarray(v.co), axis=1).min() < 1e-3:
                    continue
                inner = [e.other_vert(v) for e in v.link_edges if not e.is_boundary]
                if inner:
                    target = min(inner, key=lambda o: (o.co - v.co).length)
                    direction = target.co - v.co
                    moves.append((v, direction.normalized() * min(gap / 2, direction.length / 2)))
            for v, offset in moves:
                v.co += offset
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        self._refresh_groups(obj)
        return obj

    def _support_cuts(self, obj, pick, corner_mm):
        """Split boundary edges `corner_mm` from chosen ends, through the inset strip quad beside each edge.

        pick(bm, edge, a, b) returns the ends to cut ('a', 'b' or both) for a boundary edge running a->b in its
        strip face. Returns the positions of the new boundary vertices.
        """
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.normal_update()

        def split(a, b, length):
            edge = next(e for e in a.link_edges if e.other_vert(a) == b)
            _, vertex = bmesh.utils.edge_split(edge, a, length / (b.co - a.co).length)
            return vertex

        work = []
        for edge in [e for e in bm.edges if e.is_boundary]:
            if len(edge.link_faces) != 1 or len(edge.link_faces[0].verts) != 4:
                continue
            loop = next(l for l in edge.link_faces[0].loops if l.edge == edge)
            a, b = loop.vert, loop.link_loop_next.vert
            ends = pick(bm, edge, a, b)
            if ends and edge.calc_length() > (len(ends) + 1) * corner_mm:
                work.append((loop, ends))
        added = []
        for loop, ends in work:
            a, b = loop.vert, loop.link_loop_next.vert
            c, d = loop.link_loop_next.link_loop_next.vert, loop.link_loop_prev.vert  # c beside b, d beside a
            length, inner = (b.co - a.co).length, (c.co - d.co).length
            step = corner_mm * inner / length
            if 'b' in ends:
                near_b, inner_c = split(a, b, length - corner_mm), split(d, c, inner - step)
                bmesh.ops.connect_verts(bm, verts=[near_b, inner_c])
                added.append(tuple(near_b.co))
                b, c = near_b, inner_c
            if 'a' in ends:
                near_a = split(a, b, corner_mm)
                inner_d = split(d, c, step)
                bmesh.ops.connect_verts(bm, verts=[near_a, inner_d])
                added.append(tuple(near_a.co))
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        return added

    def tighten_opening(self, obj, loop_id, corner_mm=15.0):
        """Support cuts `corner_mm` from each corner of an opening rim, through the inset strip beside it.

        An opening sliced from one or two master faces has four rim corners, and subdivision turns a four-point
        boundary into an ellipse. Cuts near each corner (in the rim and the parallel inner strip edge) keep a
        rectangular opening with corner radii on the order of corner_mm; the pocket rings follow because they
        are offsets of the rim. Call after inset_panel_perimeter and before build_guide_mesh_stack.
        """
        loops = json.loads(obj.get('gf_loops', '{}'))
        if loop_id not in loops:
            raise ValueError(f'{obj.name} has no opening {loop_id}')
        on_rim = _near(loops[loop_id])

        def turns(v):  # a plan corner of the rim, not a vertex the rim runs straight through
            edges = [e for e in v.link_edges if e.is_boundary]
            if len(edges) != 2:
                return False
            a, b = (d - v.normal * d.dot(v.normal) for d in (e.other_vert(v).co - v.co for e in edges))
            return a.length > 1e-6 and b.length > 1e-6 and a.angle(b) < math.radians(150)

        def pick(bm, edge, a, b):
            if not (on_rim(a.co) and on_rim(b.co)):
                return ()
            return tuple(k for k, v in (('a', a), ('b', b)) if turns(v))

        added = self._support_cuts(obj, pick, corner_mm)
        loops[loop_id] = loops[loop_id] + [list(p) for p in added]
        obj['gf_loops'] = json.dumps(loops)
        self._refresh_groups(obj)
        return len(added)

    def tighten_panel_corners(self, obj, corner_mm=15.0, turn_deg=30.0):
        """Support cuts beside each outer corner of a panel so subdivision keeps its outline straight.

        A sparse panel cage subdivides its corners round over a long distance, opening seams toward their ends.
        Corners are border vertices whose border turns by more than turn_deg in the surface's tangent plane
        (a border wrapping around a curved hull is straight on the surface). Opening loops are left to
        tighten_opening. Call after inset_panel_perimeter.
        """
        loops = json.loads(obj.get('gf_loops', '{}'))
        on_rim = _near([p for points in loops.values() for p in points])

        def corner(v):
            if on_rim(v.co):
                return False
            edges = [e for e in v.link_edges if e.is_boundary]
            if len(edges) != 2:
                return False
            a, b = (d - v.normal * d.dot(v.normal) for d in (e.other_vert(v).co - v.co for e in edges))
            return a.length > 1e-6 and b.length > 1e-6 and a.angle(b) < math.radians(180 - turn_deg)

        added = self._support_cuts(obj, lambda bm, e, a, b: tuple(k for k, v in (('a', a), ('b', b)) if corner(v)), corner_mm)
        self._refresh_groups(obj)
        return len(added)

    def build_guide_mesh_stack(self, panel, guide, vgroup='guide_bound', thickness=3.0, bevel_width=0.6,
                               subsurf_levels=2, wrap_method='NEAREST_SURFACEPOINT', bevel_segments=2):
        """SUBSURF -> SHRINKWRAP(master, vertex group) -> SOLIDIFY(inward) -> BEVEL(weight)."""
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(panel.data)
        strips = [e.calc_length() for e in bm.edges if not e.is_boundary and any(v.is_boundary for v in e.verts)]
        bm.free()
        if strips and min(strips) / 2 ** subsurf_levels < bevel_width * 1.25:
            raise ValueError(f'{panel.name}: the border control strip subdivides to {min(strips) / 2 ** subsurf_levels:.2f} mm, '
                             f'too narrow for a {bevel_width} mm bevel; widen inset_panel_perimeter or lower the levels')
        for name in GROUPS[:3]:
            _group(panel, name)
        sub = panel.modifiers.new('Panel smoothing', 'SUBSURF')
        sub.levels = sub.render_levels = subsurf_levels
        sub.use_creases = True
        wrap = panel.modifiers.new('Master surface lock', 'SHRINKWRAP')
        wrap.target, wrap.wrap_method, wrap.vertex_group = guide, wrap_method, vgroup
        solid = panel.modifiers.new('Panel thickness', 'SOLIDIFY')
        # Even offset divides by the fold angle and explodes at sharp pocket returns; keep simple offset.
        solid.thickness, solid.offset, solid.use_even_offset, solid.use_rim = thickness, -1.0, False, True
        solid.use_quality_normals = True
        solid.shell_vertex_group, solid.rim_vertex_group = 'gf_inner', 'gf_solidify_rim'
        bevel = panel.modifiers.new('Edge highlight', 'BEVEL')
        bevel.limit_method, bevel.offset_type, bevel.width, bevel.segments = 'WEIGHT', 'OFFSET', bevel_width, bevel_segments
        return {'subsurf': sub, 'shrinkwrap': wrap, 'solidify': solid, 'bevel': bevel}

    # Pockets and interfaces -----------------------------------------------------------------
    def _guide(self, panel):
        target = next((m.target for m in panel.modifiers if m.type == 'SHRINKWRAP' and m.target), None)
        if target is None:
            raise ValueError('Bind the panel to its master with build_guide_mesh_stack first')
        return target

    def _normals(self, guide, world_points):
        bpy = _bpy()
        graph = bpy.context.evaluated_depsgraph_get()
        inverse = guide.matrix_world.inverted()
        rotation = guide.matrix_world.to_3x3()
        result = []
        for point in world_points:
            hit, _, normal, _ = guide.closest_point_on_mesh(inverse @ _vector(point), depsgraph=graph)
            if not hit:
                raise ValueError('Master hull has no surface near the interface')
            result.append(np.array((rotation @ normal).normalized(), dtype=float))
        return np.asarray(result)

    def recessed_pocket_extrude(self, panel, loop_id, depth, draft_angle_deg=4.0, fillet_mm=8.0, steps=3, floor=False):
        """Extrude an opening border inward as a painted return: flush rim, filleted turn, drafted wall.

        guide_bound is 1 on the flush rim and 0 on every pocket ring: the rim locks to the master while the
        explicitly built quarter-circle fillet, wall and seat stay as constructed (partial weights would pull
        the return back onto the master and fold it). The floor ring becomes gf_loop_<loop_id>_floor.
        Rings are mitred offsets of the rim, so every rim edge moves inward by the full inset. Subdivision rounds
        sparse openings; build more cage resolution around an opening when its corners must stay tight.
        """
        import bmesh
        bpy = _bpy()
        guide = self._guide(panel)
        group = panel.vertex_groups.get(f'gf_loop_{loop_id}')
        if group is None:
            raise ValueError(f'Panel has no opening loop {loop_id}')
        # Pull axis: mean master normal along the evaluated (subdivided, shrinkwrapped) opening border.
        # It is stored with the panel and carried by the rim interface ring, so checks use the same axis.
        world_points, edges, weights = _evaluated_points(panel)
        border_points = world_points[np.unique(edges[(weights[f'gf_loop_{loop_id}'][edges] >= .999).all(axis=1)])]
        pull = self._normals(guide, border_points).mean(axis=0)
        pull /= np.linalg.norm(pull)
        bm = bmesh.new()
        bm.from_mesh(panel.data)
        deform = bm.verts.layers.deform.verify()
        bm.verts.ensure_lookup_table()
        members = {v.index for v in bm.verts if v[deform].get(group.index, 0) >= .999}
        border = [e for e in bm.edges if e.is_boundary and {v.index for v in e.verts} <= members]
        order = _cycle([[e.verts[0].index, e.verts[1].index] for e in border])
        rim = [bm.verts[i] for i in order]
        axis_world = pull
        pockets = json.loads(panel.get('gf_pockets', '{}'))
        pockets[loop_id] = axis_world.tolist()
        panel['gf_pockets'] = json.dumps(pockets)
        local_axis = np.array(panel.matrix_world.to_3x3().inverted() @ _vector(axis_world), dtype=float)
        local_axis /= np.linalg.norm(local_axis)
        points = np.asarray([v.co for v in rim], dtype=float)
        centre = points.mean(axis=0)
        def edge_normal(a, b):
            n = np.cross(local_axis, b - a)
            return n / np.linalg.norm(n)
        # Mitred offset: every rim edge moves inward by the full inset, so corners of rectangular
        # openings keep the designed fillet radius instead of being squeezed along their diagonal.
        normals = [edge_normal(points[i - 1], points[i]) for i in range(len(points))]
        sign = 1.0 if np.mean([n @ (centre - p) for n, p in zip(normals, points)]) > 0 else -1.0
        inward = []
        for i in range(len(points)):
            n1, n2 = sign * normals[i], sign * normals[(i + 1) % len(points)]
            bisector = n1 + n2
            bisector /= max(np.linalg.norm(bisector), 1e-9)
            inward.append(bisector / max(float(bisector @ n1), .35))
        inward = np.asarray(inward)
        # A vertex beside a plan corner (e.g. a tighten_opening support cut) also follows the corner's slide along
        # its edge; otherwise deeper rings get shorter corner segments, subdivide to sharper corners than the rim
        # and poke outward as undercuts.
        def plan(v):
            return v - local_axis * (v @ local_axis)
        count = len(points)
        corner = []
        for i in range(count):
            a, b = plan(points[i - 1] - points[i]), plan(points[(i + 1) % count] - points[i])
            cosine = a @ b / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12)
            corner.append(cosine > math.cos(math.radians(170)))  # turns by more than 10 degrees
        slide = np.zeros_like(inward)
        for i in range(count):
            if not corner[i]:
                continue
            for j in ((i - 1) % count, (i + 1) % count):
                if corner[j]:
                    continue
                along = plan(points[j] - points[i])
                along /= max(np.linalg.norm(along), 1e-12)
                slide[j] += (inward[i] @ along) * along
        inward = inward + slide
        draft = math.tan(math.radians(draft_angle_deg))
        profile = [(fillet_mm * math.sin(math.radians(a)), fillet_mm * (1 - math.cos(math.radians(a))), 0.0)
                   for a in (30, 60, 90)]
        for k in range(1, steps + 1):
            d = fillet_mm + (depth - fillet_mm) * k / steps
            profile.append((fillet_mm + draft * (d - fillet_mm), d, 0.0))
        bound = panel.vertex_groups['guide_bound'].index
        pocket = _group(panel, 'gf_pocket').index
        floor_group = _group(panel, f'gf_loop_{loop_id}_floor').index
        bevel = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        for e in border:
            e[bevel] = 0.0
        for v in rim:
            v[deform][pocket] = 1.0
        bm.normal_update()
        original = [(f, f.normal.copy()) for f in bm.faces]
        previous = rim
        for inset, down, weight in profile:
            ring = []
            for v, n in zip(rim, inward):
                created = bm.verts.new(tuple(np.asarray(v.co) + n * inset - local_axis * down))
                created[deform].clear()
                created[deform][bound] = weight
                created[deform][pocket] = 1.0
                ring.append(created)
            for i in range(len(rim)):
                quad = [previous[i], previous[(i + 1) % len(rim)], ring[(i + 1) % len(rim)], ring[i]]
                bm.faces.new(quad).smooth = True
            previous = ring
        for v in previous:
            v[deform][floor_group] = 1.0
        if floor:
            bm.faces.new(previous).smooth = True
        # Wind the new faces consistently with the panel through shared edges, then keep the panel's
        # outward orientation: Solidify offsets inward along normals, so one flipped face pushes its
        # shell out through the skin.
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        flipped = sum(1 for f, n in original if f.normal.dot(n) < 0)
        if flipped > len(original) / 2:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        # An open floor is a seat for the contents (lens, bearing race); it gets no highlight bevel,
        # which would roll the wall back into an undercut.
        bm.to_mesh(panel.data)
        bm.free()
        panel.data.update()
        return {'axis': axis_world.tolist(), 'rim_vertices': len(rim), 'floor_loop': f'{loop_id}_floor', 'floor_closed': floor}

    def extract_interface_ring(self, obj, loop_id, name=None, output_id=None):
        """Edge-only ring object from the evaluated (subdivided, shrinkwrapped) gf_loop_<loop_id> cycle."""
        world, edges, weights = _evaluated_points(obj)
        values = weights.get(f'gf_loop_{loop_id}')
        if values is None:
            raise ValueError(f'{obj.name} has no gf_loop_{loop_id}')
        inner = weights.get('gf_inner', np.zeros(len(world)))
        keep = (values >= .999) & (inner < .5)
        chosen = edges[keep[edges].all(axis=1)]
        order = _cycle(chosen)
        points = world[order]
        guide = self._guide(obj)
        normals = self._normals(guide, points)
        tangents = np.roll(points, -1, 0) - np.roll(points, 1, 0)
        tangents /= np.linalg.norm(tangents, axis=1)[:, None]
        _, axis, _ = _ring_frame(points, axis_hint=normals.mean(axis=0))
        n = len(points)
        ring = self.mesh_object(name or f'_interface_{loop_id}', points.tolist(), [], role=None, smooth=False,
                                edges=[(i, (i + 1) % n) for i in range(n)])
        for attribute, data in (('gf_normal', normals), ('gf_tangent', tangents)):
            layer = ring.data.attributes.new(attribute, 'FLOAT_VECTOR', 'POINT')
            layer.data.foreach_set('vector', data.astype(float).ravel().tolist())
        extra = {}
        pull = json.loads(obj.get('gf_pockets', '{}')).get(loop_id[:-len('_floor')] if loop_id.endswith('_floor') else loop_id)
        if pull:
            extra['pull_axis'] = pull  # the pocket's design axis; recess checks measure draft against it
        self.api.register_output(ring, output_id, 'interface', axis=axis.tolist(), loop=loop_id, source=obj.name, **extra)
        return ring

    def local_ring(self, name, radius, segments=48, output_id=None):
        """Child-side interface circle in local XY (axis +Z); bind_to_ring moves it with its child."""
        points = [(radius * math.cos(2 * math.pi * k / segments), radius * math.sin(2 * math.pi * k / segments), 0.0) for k in range(segments)]
        ring = self.mesh_object(name, points, [], role=None, smooth=False, edges=[(k, (k + 1) % segments) for k in range(segments)])
        return self.api.register_output(ring, output_id, 'interface', axis=[0.0, 0.0, 1.0], loop=name)

    def ring_frame(self, ring):
        """World centroid, outward axis and mean radius of an interface ring."""
        matrix = np.asarray(ring.matrix_world)
        local = np.array([v.co for v in ring.data.vertices], dtype=float)
        world = (np.column_stack((local, np.ones(len(local)))) @ matrix.T)[:, :3]
        edges = [e.vertices[:] for e in ring.data.edges]
        hint = json.loads(ring.get('gf_metadata', '{}')).get('axis')
        return _ring_frame(world, edges, hint)

    def bind_to_ring(self, obj, ring, local_axis=(0, 0, 1), local_origin=(0, 0, 0), lap=0.0, roll_deg=0.0, interfaces=()):
        """Place a child coaxially on a parent ring: its local axis along the ring axis, origin `lap` mm inward."""
        from mathutils import Matrix, Quaternion, Vector
        centre, axis, _ = self.ring_frame(ring)
        axis_v = Vector(axis.tolist())
        align = Vector(local_axis).normalized().rotation_difference(axis_v)
        roll = Quaternion(axis_v, math.radians(roll_deg))
        matrix = Matrix.Translation(Vector(centre.tolist()) - axis_v * lap) @ (roll @ align).to_matrix().to_4x4() @ Matrix.Translation(-Vector(local_origin))
        for item in (obj, *interfaces):
            item.matrix_world = matrix
            if item.get('gf_role') == 'interface':
                metadata = json.loads(item.get('gf_metadata', '{}'))
                local = Vector(metadata.get('local_axis', metadata.get('axis', [0, 0, 1])))
                metadata.update(local_axis=list(local), axis=list((matrix.to_3x3() @ local).normalized()))
                item['gf_metadata'] = json.dumps(metadata)
        return matrix

    def project_detail(self, obj, parent, offset=0.0, method='NEAREST_SURFACEPOINT', vgroup=None):
        """Seat fasteners, decals and plates on the evaluated parent surface (Gate 3)."""
        wrap = obj.modifiers.new('Seat on parent', 'SHRINKWRAP')
        wrap.target, wrap.wrap_method, wrap.offset = parent, method, offset
        if vgroup:
            wrap.vertex_group = vgroup
        return wrap

    def feature_curves(self, source, name='Feature cage'):
        """Gate 0 feature lines (roofline, beltline, chine ...) as hidden editable poly curves."""
        bpy = _bpy()
        if isinstance(source, (str, bytes)) or hasattr(source, 'read_text'):
            from pathlib import Path
            source = json.loads(Path(source).read_text(encoding='utf-8'))
        collection = bpy.data.collections.get('Guides') or bpy.data.collections.new('Guides')
        if collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(collection)
        result = []
        for curve in source['curves']:
            data = bpy.data.curves.new(f'{name} {curve["id"]}', 'CURVE')
            data.dimensions = '3D'
            spline = data.splines.new('POLY')
            spline.points.add(len(curve['points_mm']) - 1)
            for point, co in zip(spline.points, curve['points_mm']):
                point.co = (*co, 1)
            spline.use_cyclic_u = bool(curve.get('closed'))
            obj = bpy.data.objects.new(data.name, data)
            collection.objects.link(obj)
            obj['gf_role'] = 'construction'
            obj.hide_render = True
            result.append(self.api.mark(obj))
        return result


def _near(points, tolerance=1e-3):
    """Membership test for recorded loop positions (mathutils KD-tree; scipy is not bundled with Blender)."""
    from mathutils.kdtree import KDTree
    tree = KDTree(max(len(points), 1))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    return lambda co: bool(points) and tree.find(co)[2] < tolerance


def _vector(values):
    from mathutils import Vector
    return Vector([float(v) for v in values])
