"""Small native modeling vocabulary. Operations stay editable in each application."""
import math
import json
from pathlib import Path

# guide: hidden master surfaces and feature cages (design evidence, never rendered or exported).
# interface: edge-only mating rings that children bind to.
ROLES = {'design', 'high_detail', 'render', 'lod', 'collision', 'printable', 'construction', 'presentation', 'guide', 'interface'}


class Context:
    def __init__(self, request=None):
        self.request = request or {}
        self.target = self.request.get('target', 'print')
        self.profile = self.request.get('profile', {})
        self.design_scene = self.request.get('design_scene')
        self.derivation = self.request.get('derivation')
        self.output_directory = Path(self.request.get('out', '.'))

    def source_scene(self, backend):
        if self.derivation:
            return Path(self.request['project_root']) / self.derivation['scenes'][backend]
        if self.design_scene:
            return Path(self.design_scene)
        raise ValueError('No retained design or derivation source was supplied')

class Blender(Context):
    def begin(self, part):
        import bpy
        self.part = part
        for obj in list(bpy.data.objects):
            if obj.get('gf_owner') == part and obj.get('gf_target', self.target) == self.target:
                bpy.data.objects.remove(obj, do_unlink=True)

    def mark(self, obj):
        obj['gf_owner'] = self.part
        obj['gf_target'] = self.target
        for key in ('gf_imported_source','gf_source_role','gf_bake_source'):
            if key in obj: del obj[key]
        return obj

    def box(self, name, size, center):
        from .blender_scene import box
        return self.mark(box(self.part+'_'+name, size, center, 'Construction'))

    def cylinder(self, name, radius, bottom, height, center=(0,0), top_radius=None):
        import bpy
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=radius, radius2=radius if top_radius is None else top_radius, depth=height, location=(*center,bottom+height/2))
        obj = bpy.context.object
        obj.name = self.part+'_'+name
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        bpy.data.collections['Construction'].objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
        return self.mark(obj)

    def boolean(self, obj, tool, operation):
        from .blender_scene import boolean
        boolean(obj, tool, operation)
        return obj

    def rotate(self, obj, degrees):
        obj.rotation_euler = [math.radians(x) for x in degrees]

    def finish(self, obj, bodies=1, rotation=(0,0,0), filament=1):
        import bpy
        from .blender_scene import printable
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        bpy.data.collections['Printable'].objects.link(obj)
        obj.hide_render = False
        obj.hide_set(False)
        printable(obj, part=self.part, rotation=rotation, filament=filament)
        obj['gf_role'] = 'printable'
        obj['gf_expected_bodies'] = bodies
        obj.color = (0.32,0.65,0.61,1)
        return obj

    def register_output(self, obj, output_id=None, role='render', source_parts=None, **metadata):
        import bpy
        if role not in ROLES:
            raise ValueError('Unknown representation role')
        output_id = output_id or self.part
        if role == 'printable':
            self.finish(obj, bodies=metadata.pop('bodies', 1), rotation=metadata.pop('rotation', (0,0,0)), filament=metadata.pop('filament', 1))
        else:
            name = 'Design' if role in ('design', 'high_detail') else 'Guides' if role in ('guide', 'interface') else 'Game'
            collection = bpy.data.collections.get(name) or bpy.data.collections.new(name)
            if collection.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(collection)
            for current in list(obj.users_collection):
                current.objects.unlink(obj)
            collection.objects.link(obj)
        self.mark(obj)
        obj['gf_part'] = output_id
        obj['gf_role'] = role
        obj['gf_metadata'] = json.dumps({'source_parts': source_parts or [self.part], **metadata}, allow_nan=False)
        obj.hide_set(role in ('collision', 'high_detail', 'design', 'guide', 'interface'))
        obj.hide_render = role in ('collision', 'high_detail', 'design', 'guide', 'interface')
        return obj

    @property
    def surf(self):
        """Master-hull surfacing helpers (geometryforge.blender_surfacing)."""
        from .blender_surfacing import Surfacing
        if getattr(self, '_surf', None) is None:
            self._surf = Surfacing(self)
        return self._surf

    def load_design(self):
        """Append retained native construction, rather than importing a baked mesh."""
        import bpy
        source = self.source_scene('blender')
        for obj in list(bpy.data.objects):
            if obj.get('gf_imported_source'):
                bpy.data.objects.remove(obj, do_unlink=True)
        with bpy.data.libraries.load(str(source), link=False) as (data_from, data_to):
            data_to.objects = list(data_from.objects)
        collection = bpy.data.collections.get('Design') or bpy.data.collections.new('Design')
        if collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(collection)
        result = []
        for obj in data_to.objects:
            if obj is None:
                continue
            collection.objects.link(obj)
            source_role = obj.get('gf_source_role', obj.get('gf_role', 'printable' if obj.get('gf_part') else 'construction'))
            obj['gf_source_role'] = source_role
            obj['gf_imported_source'] = True
            obj['gf_target'] = 'design'
            obj['gf_role'] = 'design'
            obj.hide_render = True
            obj.hide_set(True)
            if source_role in ('design','high_detail','printable','render'):
                result.append(obj)
        if self.derivation and self.derivation['from_target']=='print':
            preferred=[o for o in result if o.get('gf_source_role')=='printable']
        else:
            preferred=[o for o in result if o.get('gf_source_role') in ('design','high_detail')]
        result=preferred or result
        for obj in result: obj['gf_bake_source']=True
        return sorted(result,key=lambda o: {'high_detail':0,'design':1,'printable':2,'render':3}.get(o.get('gf_source_role'),4))

    def scale_design(self, scale):
        import bpy
        from mathutils import Matrix
        bpy.context.view_layer.update()
        transform=Matrix.Diagonal((scale,scale,scale,1))
        for obj in bpy.context.scene.objects:
            if obj.get('gf_imported_source'): obj.matrix_world=transform@obj.matrix_world

    def design_bounds(self):
        import bpy
        from mathutils import Vector
        bpy.context.view_layer.update()
        points=[obj.matrix_world@Vector(p) for obj in bpy.context.scene.objects if obj.get('gf_bake_source') for p in obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).bound_box]
        if not points: raise ValueError('No retained design outputs are loaded')
        return [min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]

    def unwrap(self, obj, margin=0.02):
        from .blender_game import unwrap
        return unwrap(obj, margin)

    def finalize_mesh(self, obj):
        from .blender_game import finalize_mesh
        return finalize_mesh(obj)

    def pbr_material(self, name, base_color=(0.32,0.65,0.61,1), roughness=0.5, metallic=0.0, textures=None):
        from .blender_game import pbr_material
        return pbr_material(name, base_color, roughness, metallic, textures)

    def bake(self, obj, sources, resolution=2048, margin=16, cage_extrusion=0.1, samples=32):
        from .blender_game import bake
        return bake(obj, sources, self.output_directory / 'native-textures', resolution, margin, cage_extrusion, samples)

    def lods(self, obj, ratios=(0.5,0.25,0.125)):
        import bpy
        self.part = obj.get('gf_owner', obj['gf_part'])
        result = []
        for level, ratio in enumerate(ratios, 1):
            copy = obj.copy()
            copy.data = obj.data.copy()
            bpy.context.scene.collection.objects.link(copy)
            copy.name = obj.name + f'_LOD{level}'
            modifier = copy.modifiers.new('LOD simplification', 'DECIMATE')
            modifier.ratio = ratio
            modifier.use_collapse_triangulate = True
            self.register_output(copy, obj['gf_part'], 'lod', lod=level, ratio=ratio)
            result.append(copy)
        return result

    def collision(self, obj, output_id=None):
        return self.register_output(obj, output_id, 'collision', kind='convex')

class Houdini(Context):
    def begin(self, part):
        from . import houdini_scene as s
        self.part = part
        for node in list(s.ROOT.children()):
            if node.userData('gf_owner') == part and (node.userData('gf_target') or self.target) == self.target:
                node.destroy()

    def mark(self, obj):
        obj.geo.setUserData('gf_owner', self.part)
        obj.geo.setUserData('gf_target', self.target)
        obj.geo.setDisplayFlag(False)
        return obj

    def box(self, name, size, center):
        from .houdini_scene import box
        return self.mark(box(self.part+'_'+name, size, center, 'Construction'))

    def cylinder(self, name, radius, bottom, height, center=(0,0), top_radius=None):
        from .houdini_scene import cylinder
        obj = cylinder(self.part+'_'+name, radius, bottom, height, center)
        if top_radius is not None:
            obj.source.parm('rad1').set(top_radius)
        return self.mark(obj)

    def boolean(self, obj, tool, operation):
        from .houdini_scene import boolean
        boolean(obj, tool, operation)
        return obj

    def rotate(self, obj, degrees):
        obj.transform.parmTuple('r').set(degrees)

    def finish(self, obj, bodies=1, rotation=(0,0,0), filament=1):
        from .houdini_scene import finish, material
        finish(obj, material('GeometryForge',(.32,.65,.61)), rotation=rotation, part=self.part, filament=filament, bodies=bodies)
        obj.geo.layoutChildren()
        return obj

    @property
    def surf(self):
        raise NotImplementedError('The master-hull surfacing helpers (api.surf) are Blender-only in this release. '
                                  'Build the Houdini master, panels and rings as SOP networks and register them with the '
                                  'guide and interface roles; typed checks and gates measure Houdini evidence the same way.')

    def register_output(self, obj, output_id=None, role='render', source_parts=None, **metadata):
        if role not in ROLES:
            raise ValueError('Unknown representation role')
        self.mark(obj)
        obj.geo.setUserData('gf_part', output_id or self.part)
        obj.geo.setUserData('gf_role', role)
        obj.geo.setUserData('gf_metadata', json.dumps({'source_parts': source_parts or [self.part], **metadata}, allow_nan=False))
        obj.geo.setDisplayFlag(role in ('render', 'printable'))
        return obj

    def unwrap(self, obj, margin=0.02):
        node = obj.geo.createNode('uvunwrap', 'game_uv_atlas')
        node.setInput(0, obj.output.input(0))
        obj.output.setInput(0, node)
        return obj

    def finalize_mesh(self, obj):
        node = obj.geo.createNode('divide', 'game_triangles')
        node.setInput(0, obj.output.input(0))
        obj.output.setInput(0, node)
        normal = obj.geo.createNode('normal', 'game_normals')
        normal.setInput(0, node)
        obj.output.setInput(0, normal)
        return obj

    def pbr_material(self, name, base_color=(0.32,0.65,0.61,1), roughness=0.5, metallic=0.0, textures=None):
        import hou
        from .houdini_scene import safe
        network=hou.node('/mat')
        shader=network.node(safe(name)) or network.createNode('principledshader::2.0',safe(name))
        shader.parmTuple('basecolor').set(base_color[:3])
        shader.parm('rough').set(roughness);shader.parm('metallic').set(metallic)
        for channel,spec in (textures or {}).items():
            prefix={'base_color':'basecolor','roughness':'rough','metallic':'metallic'}.get(channel)
            if prefix and shader.parm(prefix+'_useTexture') and shader.parm(prefix+'_texture'):
                shader.parm(prefix+'_useTexture').set(True)
                shader.parm(prefix+'_texture').set(spec['path'] if isinstance(spec,dict) else spec)
        return {'id':name,'name': name, 'base_color': list(base_color), 'roughness': roughness, 'metallic': metallic, 'textures': textures or {}, 'blend_mode': 'OPAQUE','native_shader':shader.path()}

    def set_material(self, obj, material):
        obj.geo.setUserData('gf_materials', json.dumps([material]))
        node=obj.geo.createNode('material','game_PBR_material')
        node.setInput(0,obj.output.input(0));node.parm('shop_materialpath1').set(material['native_shader'])
        obj.output.setInput(0,node)
        return obj

    def load_design(self):
        import hou
        from . import houdini_scene
        source = self.source_scene('houdini')
        before = set(houdini_scene.ROOT.children())
        hou.hipFile.merge(str(source), node_pattern='/obj/geometryforge/*', overwrite_on_conflict=False,
                          ignore_load_warnings=True)
        result = list(set(houdini_scene.ROOT.children()) - before)
        for node in result:
            node.setUserData('gf_target', 'design')
            node.setUserData('gf_role', 'design')
        return result

    def bake(self, obj, sources, resolution=2048, **options):
        """Execute an explicit editable bake network supplied by the project."""
        import hou
        if 'apprentice' in str(hou.licenseCategory()).lower():
            raise ValueError('Houdini Apprentice cannot produce the unwatermarked production PBR bake')
        node_path=options.get('node_path')
        node = hou.node(node_path) if node_path else obj.geo.node('BAKE/OUT') or obj.geo.node('BAKE') or hou.node('/out/GF_'+self.part+'_BAKE')
        if node is None or not hasattr(node, 'render'):
            raise ValueError('Author a BAKE/OUT ROP, /out/GF_<part>_BAKE, or pass node_path with source/target correspondence and output maps')
        node.render()
        return {'node': node.path(), 'resolution': resolution, 'source_nodes': [s.geo.path() for s in sources], **options}

    def lods(self, obj, ratios=(0.5,0.25,0.125)):
        from . import houdini_scene as scene
        result = []
        for level, ratio in enumerate(ratios, 1):
            geo = scene.new_geo(obj.name + f'_LOD{level}')
            merge = geo.createNode('object_merge', 'render_source')
            merge.parm('objpath1').set(obj.output.path())
            reduce = geo.createNode('polyreduce', 'LOD_simplification')
            reduce.setInput(0, merge)
            reduce.parm('percentage').set(ratio * 100)
            part = scene.Part(obj.name + f'_LOD{level}', geo, reduce, 'lod')
            self.register_output(part, obj.geo.userData('gf_part'), 'lod', lod=level, ratio=ratio)
            if obj.geo.userData('gf_materials'):
                part.geo.setUserData('gf_materials', obj.geo.userData('gf_materials'))
            result.append(part)
        return result

    def collision(self, obj, output_id=None):
        return self.register_output(obj, output_id, 'collision', kind='convex')
