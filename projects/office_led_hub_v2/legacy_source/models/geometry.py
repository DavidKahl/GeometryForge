"""Project-native Blender primitives and inspectable manufacturing operations."""
import math
import bpy
import bmesh
from mathutils import Vector
from geometryforge.blender_scene import boolean, printable


def box(name, dimensions, center, group='Printable'):
    """Direct mesh construction avoids operator-driven scene reevaluation."""
    w, d, h = dimensions
    obj = prism(name, [(-w/2, -d/2), (w/2, -d/2), (w/2, d/2), (-w/2, d/2)], -h/2, h, group)
    obj.location = center
    return obj


def collection(obj, name):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    bpy.data.collections[name].objects.link(obj)
    if name == 'Construction':
        obj.hide_render = True
        obj.hide_set(True)
        obj.display_type = 'WIRE'
    return obj


def prism(name, points, bottom, height, group='Printable'):
    n = len(points)
    vertices = [(x, y, z) for z in (bottom, bottom + height) for x, y in points]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.data.collections[group].objects.link(obj)
    return collection(obj, group)


def rounded(name, width, length, radius, bottom, height, center=(0, 0), group='Printable'):
    points = []
    for cx, cy, start in [(width/2-radius, length/2-radius, 0),
                           (-width/2+radius, length/2-radius, 90),
                           (-width/2+radius, -length/2+radius, 180),
                           (width/2-radius, -length/2+radius, 270)]:
        for i in range(13):
            a = math.radians(start+i*90/12)
            points.append((center[0]+cx+radius*math.cos(a), center[1]+cy+radius*math.sin(a)))
    return prism(name, points, bottom, height, group)


def cylinder(name, radius, bottom, height, center=(0, 0), group='Construction', count=64):
    return prism(name, [(center[0]+radius*math.cos(2*math.pi*i/count),
                         center[1]+radius*math.sin(2*math.pi*i/count)) for i in range(count)], bottom, height, group)


def sector(name, inner, outer, a0, a1, bottom, height):
    count = max(12, round((a1-a0)/2))
    angles = [math.radians(a0+(a1-a0)*i/count) for i in range(count+1)]
    points = [(outer*math.cos(a), outer*math.sin(a)) for a in angles]
    points += [(inner*math.cos(a), inner*math.sin(a)) for a in reversed(angles)]
    return prism(name, points, bottom, height)


def fuse(obj, tool, label='Joined support'):
    collection(tool, 'Construction')
    boolean(obj, tool, 'UNION', label)
    return obj


def cut(obj, tool, label='Clearance cut'):
    collection(tool, 'Construction')
    boolean(obj, tool, 'DIFFERENCE', label)
    return obj


def hole(obj, xy, bottom, height, diameter=3.4, name='M3 clearance'):
    return cut(obj, cylinder(name, diameter/2, bottom, height, xy), name)


def nut(obj, xy, bottom, side=False):
    # Hex across flats 5.8; open-bottom pockets or side-loaded column sockets.
    tool = cylinder('M3 hex nut pocket', 5.8/math.sqrt(3), bottom, 2.6, xy, count=6)
    cut(obj, tool, 'Captive M3 nut')
    if side:
        direction = -1 if xy[0] > 0 else 1
        cut(obj, box('Nut insertion mouth', (8, 5.8, 2.6), (xy[0]+direction*4, xy[1], bottom+1.3), 'Construction'))


def radial_box(name, radius, angle, radial, tangent, bottom, height, group='Construction'):
    a = math.radians(angle)
    obj = box(name, (radial, tangent, height), (radius*math.cos(a), radius*math.sin(a), bottom+height/2), group)
    obj.rotation_euler.z = a
    return obj


def countersink(obj, xy, top, outer=6.4, inner=3.4, depth=1.6):
    count = 48
    vertices = [(xy[0]+r*math.cos(2*math.pi*i/count), xy[1]+r*math.sin(2*math.pi*i/count), z)
                for r, z in ((inner/2, top-depth), (outer/2, top+0.1)) for i in range(count)]
    faces = [tuple(reversed(range(count))), tuple(range(count, count*2))]
    faces += [(i, (i+1)%count, (i+1)%count+count, i+count) for i in range(count)]
    mesh = bpy.data.meshes.new('Countersink')
    mesh.from_pydata(vertices, [], faces)
    tool = bpy.data.objects.new('Countersink', mesh)
    bpy.data.collections['Construction'].objects.link(tool)
    cut(obj, tool, 'M3 countersunk seat')


def evaluated_copy(obj, name, group='Printable'):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph), depsgraph=graph)
    copy = bpy.data.objects.new(name, mesh)
    bpy.data.collections[group].objects.link(copy)
    copy.matrix_world = obj.matrix_world.copy()
    return collection(copy, group)


def volume(obj):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return abs(bm.calc_volume(signed=True)) * abs(obj.matrix_world.determinant())
    finally:
        bm.free()
        evaluated.to_mesh_clear()


def intersection_volume(a, b):
    obj = evaluated_copy(a, '_intersection', 'Construction')
    boolean(obj, b, 'INTERSECT')
    result = volume(obj)
    bpy.data.objects.remove(obj, do_unlink=True)
    return result


def material(name, color, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = 0.43
    return mat


def finish(obj, mat, rotation=(0, 0, 0), part=None, filament=1, bodies=1):
    printable(obj, part=part, rotation=rotation, filament=filament)
    obj['gf_expected_bodies'] = bodies
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj
