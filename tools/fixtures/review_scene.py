"""Dedicated disposable Blender fixture for native review integration tests."""
import json
from pathlib import Path
import sys

import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .001
verts = [(x*20-60, y*20-40, 15*(1-((x-3)/3)**2)*(1-((y-2)/2)**2)) for y in range(5) for x in range(7)]
faces = [(y*7+x, y*7+x+1, (y+1)*7+x+1, (y+1)*7+x) for y in range(4) for x in range(6)]
mesh = bpy.data.meshes.new('Editable curved control cage')
mesh.from_pydata(verts, [], faces)
mesh.update()
obj = bpy.data.objects.new('Crowned panel', mesh)
scene.collection.objects.link(obj)
obj['gf_part'], obj['gf_role'] = 'panel', 'design'
obj.modifiers.new('Editable curvature', 'SUBSURF').levels = 2
solid = obj.modifiers.new('Panel thickness', 'SOLIDIFY')
solid.thickness = 4
for p in mesh.polygons:
    p.use_smooth = True
bpy.ops.mesh.primitive_cube_add(size=15, location=(0, 0, 50))
helper = bpy.context.object
helper.name = 'Invisible construction operand'
helper['gf_role'] = 'construction'
helper.hide_render = True
collection = bpy.data.collections.new('Instance-only source')
tetra = bpy.data.meshes.new('Instanced tetrahedron')
tetra.from_pydata([(-20,-20,0),(20,-20,0),(0,20,0),(0,0,35)], [], [(0,2,1),(0,1,3),(1,2,3),(2,0,3)])
child = bpy.data.objects.new('Instance-only tetrahedron', tetra)
collection.objects.link(child)
instance = bpy.data.objects.new('Editable collection instance', None)
instance.instance_type = 'COLLECTION'
instance.instance_collection = collection
instance['gf_part'], instance['gf_role'] = 'instance', 'design'
scene.collection.objects.link(instance)
points = bpy.data.meshes.new('Geometry Nodes source points')
points.from_pydata([(35,0,0)], [], [])
node_object = bpy.data.objects.new('Editable Geometry Nodes instances', points)
node_object['gf_part'], node_object['gf_role'] = 'node_instance', 'design'
scene.collection.objects.link(node_object)
group = bpy.data.node_groups.new('Native instance fixture', 'GeometryNodeTree')
group.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
group.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
inp = group.nodes.new('NodeGroupInput')
out = group.nodes.new('NodeGroupOutput')
info = group.nodes.new('GeometryNodeObjectInfo')
info.inputs['Object'].default_value = child
info.inputs['As Instance'].default_value = True
on_points = group.nodes.new('GeometryNodeInstanceOnPoints')
group.links.new(inp.outputs['Geometry'], on_points.inputs['Points'])
group.links.new(info.outputs['Geometry'], on_points.inputs['Instance'])
group.links.new(on_points.outputs['Instances'], out.inputs['Geometry'])
node_object.modifiers.new('Editable instancing recipe', 'NODES').node_group = group
# Polluted source presentation must never affect review output.
scene.render.use_border = True
scene.render.resolution_percentage = 10
path = Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.wm.save_as_mainfile(filepath=str(path))
(path.parent/'fixture.json').write_text(json.dumps({'raw_triangles': len(faces)*2, 'expected_min_triangles': len(faces)*2*16}), encoding='utf-8')
