"""Gated master-hull fixture: one hull, two shrinkwrapped panels with a lamp pocket, a ring-bound lens."""
import bpy
import bmesh


def cage(length, width, height):
    """4x4-per-side box cage with named face regions; level-4 subdivision rounds it into a pebble hull."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    bm.verts.index_update()
    bm.faces.index_update()
    regions = {'body': [], 'skirt': [], 'lamp': []}
    for face in bm.faces:
        x, y, z = face.calc_center_median()
        if x > .49 and abs(y) < .2 and .25 < z < .45:  # fully surrounded by body faces
            regions['lamp'].append(face.index)
        else:
            regions['body' if z > 0 else 'skirt'].append(face.index)
    verts = [(v.co.x * length, v.co.y * width, v.co.z * height) for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return verts, faces, regions


def panel(api, guide, region, name, parameters, openings=()):
    s = api.surf
    obj = s.slice_panel(guide, region, openings=openings, name=name)
    # Level 3 keeps chords on the tight corners close to the master (coverage check).
    # The border strip must stay wider than the bevel after subdivision: 8 mm / 2^3 = 1 mm > 0.6 mm.
    s.inset_panel_perimeter(obj, 8.0, gap=parameters['panel_gap_mm'])
    s.build_guide_mesh_stack(obj, guide, thickness=parameters['panel_thickness_mm'], bevel_width=.6, subsurf_levels=3)
    return obj


def build_parts(parameters, parts, api):
    s = api.surf
    for part in parts:
        api.begin(part)
        if part == 'master_hull':
            verts, faces, regions = cage(parameters['length_mm'], parameters['width_mm'], parameters['height_mm'])
            s.master_hull('Master hull', verts, faces, regions=regions, levels=4)
        elif part == 'body':
            guide = bpy.data.objects['Master hull']
            body = panel(api, guide, 'body', 'Body panel', parameters, openings=['lamp'])
            s.recessed_pocket_extrude(body, 'lamp', parameters['lamp_depth_mm'], parameters['lamp_draft_deg'], parameters['lamp_fillet_mm'])
            s.extract_interface_ring(body, 'lamp', name='_interface_lamp')
            s.extract_interface_ring(body, 'lamp_floor', name='_interface_lamp_seat')
        elif part == 'skirt':
            panel(api, bpy.data.objects['Master hull'], 'skirt', 'Skirt panel', parameters)
        elif part == 'lens':
            from geometryforge.sections import superellipse_ring
            outline = superellipse_ring(60, 60, 2.0, 32)
            rings = [[(x, y, z) for x, y in outline] for z in (-4.0, 4.0)]
            lens = s.loft('Lens', rings)
            ring = s.local_ring('_interface_lens', 30.0)
            s.bind_to_ring(lens, bpy.data.objects['_interface_lamp_seat'], lap=parameters['lens_lap_mm'], interfaces=[ring])
        elif part == 'fasteners':
            # A bolt row along the roof crown, seated on the evaluated body panel it is bolted to (the panel sags
            # a few mm below the master between cage vertices; detail checks measure seating against the panel).
            from mathutils import Vector
            guide = bpy.data.objects['Body panel']
            graph = bpy.context.evaluated_depsgraph_get()
            points, normals = [], []
            for k in range(parameters['bolt_count']):
                x = -0.3 * parameters['length_mm'] + 0.6 * parameters['length_mm'] * k / max(parameters['bolt_count'] - 1, 1)
                hit, location, normal, _ = guide.ray_cast(Vector((x, 0.0, 2 * parameters['height_mm'])), Vector((0, 0, -1)), depsgraph=graph)
                points.append(tuple(location))
                normals.append(tuple(normal))
            s.bolts('Roof bolts', points, normals, radius=8.0, height=6.0)
