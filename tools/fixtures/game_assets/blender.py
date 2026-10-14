"""Native integration fixtures, kept outside generic toolkit logic."""
import bpy


def render(api,obj,part):
    material=api.pbr_material('M_Fixture',(.15,.3,.4,1),.5,.3)
    obj.data.materials.clear();obj.data.materials.append(material)
    for modifier in obj.modifiers:
        if modifier.type=='BOOLEAN' and modifier.object and not modifier.object.data.materials:
            modifier.object.data.materials.append(material)
    api.register_output(obj,part,'render',collision='traversable' if api.request['parameters']['kind']=='doorway' else 'decorative' if api.request['parameters']['kind']=='legacy' else 'blocking')
    api.finalize_mesh(obj);api.unwrap(obj)
    if api.profile.get('profile')!='unreal_desktop_nanite': api.lods(obj)


def build_parts(p,parts,api):
    for part in parts:
        api.begin(part)
        if p['kind']=='doorway':
            obj=api.box('door_frame',(3000,300,2500),(1500,0,1250))
            opening=api.box('opening',(1800,600,2200),(1500,0,1100))
            api.boolean(obj,opening,'DIFFERENCE')
            bpy.context.view_layer.objects.active=obj
            obj.hide_set(False);obj.select_set(True)
            bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            render(api,obj,part)
            for label,size,center in [('left',(600,300,2500),(300,0,1250)),('right',(600,300,2500),(2700,0,1250)),('header',(1800,300,300),(1500,0,2350))]:
                api.collision(api.box(label,size,center),part)
        elif p['kind']=='dense':
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5,radius=500)
            obj=bpy.context.object;obj.name='dense_rock';api.mark(obj)
            texture=bpy.data.textures.new('Editable rock noise',type='CLOUDS')
            modifier=obj.modifiers.new('Procedural surface detail','DISPLACE');modifier.texture=texture;modifier.strength=8
            render(api,obj,part)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=508)
            api.collision(api.mark(bpy.context.object),part)
        elif p['kind']=='shell' and part=='body':
            obj=api.box('shell',(80,50,40),(0,0,20))
            inner=api.box('cavity',(76,46,42),(0,0,23))
            api.boolean(obj,inner,'DIFFERENCE');api.finish(obj)
        elif p['kind']=='shell' and part=='coupon':
            male=api.box('male',(10,10,2),(-7,0,1))
            peg=api.cylinder('peg',2,1.9,5.1,(-7,0));api.boolean(male,peg,'UNION')
            female=api.box('female',(10,10,7),(7,0,3.5))
            hole=api.cylinder('hole',2.2,1,8,(7,0));api.boolean(female,hole,'DIFFERENCE')
            api.finish(male,bodies=2);api.finish(female,bodies=2)
        elif p['kind']=='legacy':
            source=api.load_design()[0]
            obj=source.copy();obj.data=source.data.copy();bpy.context.scene.collection.objects.link(obj)
            render(api,obj,part)
