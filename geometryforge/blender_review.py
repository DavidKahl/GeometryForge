"""Standalone Blender review worker. Never saves a .blend or runs project recipes."""
import hashlib
import json
import math
from pathlib import Path
import sys

AXES = {'x': 0, 'y': 1, 'z': 2}


def part_color(part):
    """Stable linear emission colour per part; the host decodes it for region-invariance diffs."""
    value = hashlib.sha256(str(part).encode()).digest()
    return [round(.05 + .9 * value[i] / 255, 4) for i in range(3)]


def part_srgb(part):
    """8-bit pixel value of part_color after Blender's Standard (sRGB) view transform."""
    def encode(c):
        return 12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055
    return [round(255 * encode(c)) for c in part_color(part)]


def execute(request):
    import bpy
    from mathutils import Vector, Matrix

    bpy.ops.wm.open_mainfile(filepath=request['scene'])
    scene = bpy.context.scene
    # Normalize to millimeters in disposable memory; preserve object transforms.
    unit = scene.unit_settings.scale_length if scene.unit_settings.system != 'NONE' else .001
    scale = unit / .001
    # Guide surfaces (master hulls) are hidden from render but reviewable on request.
    candidates = [o for o in scene.objects if (o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'} or
                  (o.type == 'EMPTY' and o.instance_type == 'COLLECTION'))
                  and o.get('gf_role') not in {'construction', 'presentation', 'collision', 'lod', 'interface'}
                  and (o.get('gf_role') in {'design', 'high_detail', 'render', 'printable', 'guide'} or not o.hide_render)]
    # Evaluate the saved render settings, including modifiers disabled only in
    # the viewport. The changes live exclusively in this disposable process.
    for obj in candidates:
        for mod in obj.modifiers:
            mod.show_viewport = mod.show_render
            if mod.type == 'SUBSURF':
                mod.levels = mod.render_levels
            elif mod.type == 'MULTIRES':
                mod.levels = mod.render_levels
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    cache = {}
    # DepsgraphObjectInstance wrappers are valid only during iteration. Copy
    # their fields now, rather than retaining expired iterator RNA objects.
    instances = [(i.parent.original, i.object, i.matrix_world.copy(), tuple(i.persistent_id))
                 for i in graph.object_instances if i.is_instance and i.parent]
    views = request['settings']['views']
    for view in views:
        selection = view['selection']
        named = {k: v for k, v in selection.items() if k in ('parts', 'objects')}
        for key, names in named.items():
            available = {o.get('gf_part') if key == 'parts' else o.name for o in candidates}
            missing = set(names) - available
            if missing:
                raise ValueError(f'{view["id"]}: unknown or non-renderable {key}: {sorted(missing)}')
        roles = selection.get('roles')

        def wanted(o):
            role = o.get('gf_role') or 'render'
            if o.name in named.get('objects', []):
                return True
            return (role in roles) if roles else role != 'guide'
        chosen = [o for o in candidates if wanted(o) and (not named or o.get('gf_part') in named.get('parts', []) or o.name in named.get('objects', []))]
        if not chosen:
            raise ValueError(f'{view["id"]}: no renderable geometry selected')
        keys = []
        for obj in chosen:
            sources = []
            if obj.type != 'EMPTY':
                sources.append((obj.name, obj.evaluated_get(graph), obj.matrix_world))
            for parent, instanced, matrix, persistent_id in instances:
                if parent == obj and instanced.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
                    ident = '/'.join(str(v) for v in persistent_id)
                    sources.append((f'{obj.name} / {instanced.original.name} / {ident}', instanced, matrix))
            for key, evaluated, matrix in sources:
                if key not in cache:
                    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
                    mesh.transform(Matrix.Scale(scale, 4) @ matrix)
                    mesh.calc_loop_triangles()
                    if not mesh.loop_triangles:
                        bpy.data.meshes.remove(mesh)
                        continue
                    cache[key] = (mesh, obj.get('gf_part'), len(mesh.loop_triangles))
                keys.append(key)
        if not keys:
            raise ValueError(f'{view["id"]}: selected geometry evaluates to no triangles')
        view['_objects'] = keys
    # Rendering only the evaluated copies ensures cutters, old lights and hidden
    # collections cannot leak into evidence. No original datablock is saved.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = .001
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.use_denoising = True
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.render.resolution_percentage = 100
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.use_simplify = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.use_nodes = False
    for layer in scene.view_layers:
        layer.use = layer == scene.view_layers[0]
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'None'
    scene.view_settings.use_curve_mapping = False
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    world = bpy.data.worlds.new('GF review studio')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.12, .14, .18, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .45
    scene.world = world

    def material(name, color, roughness, metallic=0, emission=False):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        node = mat.node_tree.nodes.get('Principled BSDF')
        node.inputs['Base Color'].default_value = (*color, 1)
        node.inputs['Roughness'].default_value = roughness
        node.inputs['Metallic'].default_value = metallic
        if emission:
            node.inputs['Emission Color'].default_value = (*color, 1)
            node.inputs['Emission Strength'].default_value = 1
        return mat

    def emission(name, build):
        """Unlit diagnostic material; build(nodes, links) returns the colour socket."""
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial')
        emit = nodes.new('ShaderNodeEmission')
        links.new(build(nodes, links), emit.inputs['Color'])
        links.new(emit.outputs[0], output.inputs['Surface'])
        return mat

    def zebra(stripes, rotation):
        # Reflection-vector bands: G0 breaks jump, G1 kinks bend, G2 surfaces flow continuously.
        def build(nodes, links):
            coord = nodes.new('ShaderNodeTexCoord')
            mapping = nodes.new('ShaderNodeMapping')
            mapping.inputs['Rotation'].default_value = [math.radians(a) for a in rotation]
            wave = nodes.new('ShaderNodeTexWave')
            wave.wave_type, wave.bands_direction, wave.wave_profile = 'BANDS', 'X', 'SIN'
            wave.inputs['Scale'].default_value = stripes
            wave.inputs['Distortion'].default_value = 0
            wave.inputs['Detail'].default_value = 0
            ramp = nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.interpolation = 'CONSTANT'
            ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
            ramp.color_ramp.elements[1].position = .5
            ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
            links.new(coord.outputs['Reflection'], mapping.inputs['Vector'])
            links.new(mapping.outputs['Vector'], wave.inputs['Vector'])
            links.new(wave.outputs['Fac'], ramp.inputs['Fac'])
            return ramp.outputs['Color']
        return emission('GF zebra', build)

    def normals(nodes, links):
        geometry = nodes.new('ShaderNodeNewGeometry')
        remap = nodes.new('ShaderNodeVectorMath')
        remap.operation = 'MULTIPLY_ADD'
        remap.inputs[1].default_value = (.5, .5, .5)
        remap.inputs[2].default_value = (.5, .5, .5)
        links.new(geometry.outputs['Normal'], remap.inputs[0])
        return remap.outputs[0]

    def flat(colour):
        def build(nodes, links):
            rgb = nodes.new('ShaderNodeRGB')
            rgb.outputs[0].default_value = (*colour, 1)
            return rgb.outputs[0]
        return build

    mats = dict(clay=material('GF clay', (.48, .51, .55), .7),
                glossy=material('GF glossy', (.38, .42, .48), .2, .55),
                silhouette=material('GF silhouette', (0, 0, 0), 1),
                wireframe=material('GF wire base', (.32, .36, .4), .8),
                normal=emission('GF normals', normals))
    wire = material('GF wire edges', (.006, .008, .012), 1)
    part_mats = {}
    out = Path(request['out'])
    result = dict(blender_version=bpy.app.version_string, engine='CYCLES', units='mm', views=[], part_colors={})
    for view in views:
        objects = []
        counts = []
        for name in view['_objects']:
            mesh, part, triangles = cache[name]
            obj = bpy.data.objects.new('Review ' + name, mesh.copy())
            obj['gf_review_part'] = str(part)
            scene.collection.objects.link(obj)
            obj.data.materials.clear()
            for poly in obj.data.polygons:
                poly.material_index = 0
            if view.get('section'):
                import bmesh
                section = view['section']
                normal = [0.0, 0.0, 0.0]
                normal[AXES[section['axis']]] = 1.0
                point = [0.0, 0.0, 0.0]
                point[AXES[section['axis']]] = section['offset_mm']
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=point, plane_no=normal,
                                       clear_outer=section['keep'] == 'negative', clear_inner=section['keep'] == 'positive')
                bm.to_mesh(obj.data)
                bm.free()
            objects.append(obj)
            counts.append(dict(name=name, part=part, triangles=triangles))
        coords = [Vector(c) for o in objects for c in o.bound_box]
        if not coords:
            raise ValueError(f'{view["id"]}: the section removes all selected geometry')
        low = Vector([min(c[i] for c in coords) for i in range(3)])
        high = Vector([max(c[i] for c in coords) for i in range(3)])
        span = max((high-low).length, 1)
        center = (low+high)/2
        if 'studio' in view:
            span = view['studio']['size_mm']
            center = Vector(view['studio']['center_mm'])
        cam = view['camera']
        position, target, up = Vector(cam['position_mm']), Vector(cam['target_mm']), Vector(cam['up']).normalized()
        direction = (target-position).normalized()
        right = direction.cross(up).normalized()
        vertical = right.cross(direction).normalized()
        data = bpy.data.cameras.new('GF review camera')
        camera = bpy.data.objects.new('GF review camera', data)
        scene.collection.objects.link(camera)
        camera.location = position
        camera.rotation_euler = Matrix((right, vertical, -direction)).transposed().to_euler()
        data.type = 'ORTHO' if cam['projection'] == 'orthographic' else 'PERSP'
        data.lens = cam['lens_mm']
        data.sensor_width = cam['sensor_width_mm']
        data.sensor_fit = 'HORIZONTAL'
        data.shift_x = cam.get('shift_x', 0)
        data.shift_y = cam.get('shift_y', 0)
        data.ortho_scale = cam.get('ortho_scale_mm', span)
        data.clip_start = .1
        data.clip_end = max(span*100, position.length*10)
        scene.camera = camera
        lights = []
        for i, (r, u, d, energy, width, height) in enumerate(((-.7, .9, .6, 4, .7, .16), (.8, .2, .2, 2.8, .22, .8), (0, 1.1, -.7, 5, .9, .12))):
            lamp = bpy.data.lights.new(f'GF strip {i}', 'AREA')
            lamp.shape = 'RECTANGLE'
            lamp.energy = span*span*energy
            lamp.size, lamp.size_y = span*width, span*height
            obj = bpy.data.objects.new(lamp.name, lamp)
            scene.collection.objects.link(obj)
            obj.location = center + span*(right*r + vertical*u - direction*d)
            obj.rotation_euler = (target-obj.location).to_track_quat('-Z', 'Y').to_euler()
            lights.append(obj)
        scene.render.resolution_x, scene.render.resolution_y = view['resolution']
        scene.cycles.samples = view['samples']
        artifacts = {}
        for mode in view['modes']:
            exact = mode in ('normal', 'part_id')
            # Diagnostic modes are unlit; normal/part_id are exact pixels for region-invariance diffs.
            scene.view_settings.view_transform = 'Standard' if mode in ('normal', 'part_id', 'zebra') else 'AgX'
            scene.cycles.samples = 1 if exact else view['samples']
            scene.cycles.use_denoising = not exact
            scene.cycles.filter_width = .01 if exact else 1.5
            for obj in objects:
                obj.data.materials.clear()
                if mode == 'part_id':
                    part = obj['gf_review_part']
                    if part not in part_mats:
                        part_mats[part] = emission(f'GF part {part}', flat(part_color(part)))
                        result['part_colors'][part] = part_srgb(part)
                    obj.data.materials.append(part_mats[part])
                elif mode == 'zebra':
                    if 'zebra' not in mats:
                        mats['zebra'] = zebra(view['zebra']['stripes'], view['zebra']['rotation_deg'])
                    obj.data.materials.append(mats['zebra'])
                else:
                    obj.data.materials.append(mats[mode])
                for poly in obj.data.polygons:
                    poly.material_index = 0
                if mode == 'wireframe':
                    obj.data.materials.append(wire)
                    mod = obj.modifiers.new('Review topology', 'WIREFRAME')
                    mod.thickness = span*.00035
                    mod.use_replace = False
                    mod.use_even_offset = False
                    mod.offset = 1
                    mod.material_offset = 1
            path = out / f'{view["id"]}_{mode}.png'
            scene.render.filepath = str(path)
            if mode == 'silhouette':
                # Holdout renders a texture-free exact alpha mask of the evaluated
                # geometry; compose black foreground on white in Blender itself.
                hold = bpy.data.materials.new('GF holdout')
                hold.use_nodes = True
                nodes = hold.node_tree.nodes
                nodes.clear()
                output = nodes.new('ShaderNodeOutputMaterial')
                holdout = nodes.new('ShaderNodeHoldout')
                hold.node_tree.links.new(holdout.outputs[0], output.inputs['Surface'])
                scene.view_layers[0].material_override = hold
                # Transparent film would make both foreground/background alpha=0.
                # Keep opaque world: holdout alpha=0, background alpha=1.
                scene.render.image_settings.color_mode = 'RGBA'
            bpy.ops.render.render(write_still=True)
            scene.view_layers[0].material_override = None
            scene.render.image_settings.color_mode = 'RGB'
            artifacts[mode] = str(path)
            for obj in objects:
                for mod in list(obj.modifiers):
                    obj.modifiers.remove(mod)
        mats.pop('zebra', None)  # zebra settings are per view
        result['views'].append(dict(id=view['id'], camera=cam, resolution=view['resolution'],
                                    studio=dict(center_mm=list(center), size_mm=span),
                                    bounds_mm=[list(low), list(high)],
                                    objects=counts, triangles=sum(c['triangles'] for c in counts), artifacts=artifacts))
        for obj in objects + lights + [camera]:
            mesh = obj.data if obj.type == 'MESH' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh:
                bpy.data.meshes.remove(mesh)
    (out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    execute(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8')))
