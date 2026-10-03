"""Render the actual native scene: blender -b <scene> --python tools/render.py -- <output-dir>."""
import bpy,sys,math,json,hashlib
from pathlib import Path
from mathutils import Vector

out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True)
native=Path(bpy.data.filepath)
(out/'render-provenance.json').write_text(json.dumps({'native_file':str(native),'sha256':hashlib.sha256(native.read_bytes()).hexdigest()},indent=2))
scene=bpy.context.scene
for obj in bpy.data.collections['Printable'].objects:
    obj.hide_render=obj.get('gf_part')=='coupon'
    if obj.type=='MESH':
        # Flat faces retain the real weld lines and relief in these evidence renders.
        obj.hide_set(False)
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.17,.21,.28,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'
scene.render.resolution_percentage=100
collection=bpy.data.collections.get('Presentation')
for obj in list(collection.objects):bpy.data.objects.remove(obj,do_unlink=True)

def aim(obj,point):obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()
def light(name,where,power,size,target=(0,0,240),color=(1,1,1)):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);collection.objects.link(obj);obj.location=where;aim(obj,target)
light('large warm key',(200,-300,450),1500000,350,color=(1,.87,.73))
light('cool vertical rim',(-180,180,340),2400000,280,color=(.6,.76,1))
light('front fill',(-180,-220,150),700000,220)
light('engine fill',(100,-140,35),120000,120,target=(0,0,30))
bpy.ops.mesh.primitive_plane_add(size=20000,location=(0,0,-.3));floor=bpy.context.object;floor.name='Studio ground'
for c in list(floor.users_collection):c.objects.unlink(floor)
collection.objects.link(floor)
mat=bpy.data.materials.new('Studio slate');mat.diffuse_color=(.034,.048,.068,1);mat.use_nodes=True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=mat.diffuse_color
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.65;floor.data.materials.append(mat)
data=bpy.data.cameras.new('Evidence camera');camera=bpy.data.objects.new('Evidence camera',data);collection.objects.link(camera);scene.camera=camera;data.type='ORTHO';data.clip_end=5000
views=[('astraeus_assembled',(720,-1100,540),(0,0,240),545,(1100,1600)),
       ('astraeus_propulsion',(150,-210,105),(0,0,62),154,(1300,1200)),
       ('astraeus_upper',(160,-230,455),(0,0,387),220,(1100,1300)),
       ('astraeus_thermal_detail',(140,-210,326),(0,0,288),90,(1300,1000))]
for name,location,target,scale,res in views:
    camera.location=location;aim(camera,target);data.ortho_scale=scale
    scene.render.resolution_x,scene.render.resolution_y=res
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)

# An exploded illustration uses evaluated copies in this unsaved render session;
# editable construction objects in the delivered native file remain in assembly position.
graph=bpy.context.evaluated_depsgraph_get()
offsets={'aft_hull':0,'tank_lower':35,'tank_upper':70,'thermal_band':105,'cargo':125,'nose':170,'nose_tip':210,'engine_mount':-20,'engines':-40}
for obj in list(bpy.data.collections['Printable'].objects):
    part=obj.get('gf_part');obj.hide_render=True
    if part=='coupon':continue
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(graph),depsgraph=graph)
    copy=bpy.data.objects.new('Exploded_'+part,mesh);collection.objects.link(copy);copy.matrix_world=obj.matrix_world.copy()
    copy.location.z+=offsets.get(part,170 if part.startswith('canard') else 0)
    if part.startswith(('aft_fin','canard','leg')):
        angle=math.radians((int(part.rsplit('_',1)[1])-1)*90+(45 if part.startswith('leg') else 0))
        distance=55 if part.startswith('aft_fin') else 40
        copy.location.x+=distance*math.cos(angle);copy.location.y+=distance*math.sin(angle)
floor.hide_render=True;camera.location=(720,-1100,600);aim(camera,(0,0,315));data.ortho_scale=790
scene.render.resolution_x=1400;scene.render.resolution_y=1600
scene.render.filepath=str(out/'astraeus_exploded.png');bpy.ops.render.render(write_still=True)
