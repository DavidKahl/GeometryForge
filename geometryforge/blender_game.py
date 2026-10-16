"""Editable Blender game preparation, attribute extraction and native FBX exports."""
import json
from pathlib import Path


def equivalent(left, right):
    """Native float32 recooking may round attributes; topology and identities stay exact."""
    import numpy as np
    if isinstance(left, dict):
        return isinstance(right, dict) and left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if isinstance(left, list):
        if not isinstance(right, list) or len(left) != len(right): return False
        return all(equivalent(a,b) for a,b in zip(left,right))
    if isinstance(left, float) and isinstance(right,(float,int)):
        return bool(np.isclose(left,right,atol=1e-6,rtol=1e-7))
    return left == right


def relocate_textures(directory):
    """Packed images travel with copied native scenes; unpack only into the new run."""
    import bpy
    import hashlib
    directory.mkdir(parents=True,exist_ok=True)
    for image in bpy.data.images:
        if not image.packed_file:
            continue
        if image.is_dirty:
            raise ValueError(f'Save or pack texture edits before verification: {image.name}')
        payload = bytes(image.packed_file.data)
        source = Path(bpy.path.abspath(image.filepath))
        if source.is_file() and hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(payload).digest():
            continue
        suffix = Path(image.filepath).suffix or '.png'
        path = directory / (hashlib.sha256(payload).hexdigest()[:16] + suffix)
        path.write_bytes(payload)
        image.filepath_raw = str(path.resolve())


def activate(obj):
    import bpy
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def unwrap(obj, margin=0.02):
    import bpy
    # Unwrap the actual render topology. Keep the editable preparation construction
    # in the scene rather than evaluating bevel/retopology after the UV atlas.
    if obj.modifiers:
        original = obj.copy(); original.data = obj.data.copy(); original.name = obj.name+'_UV_source'
        collection = bpy.data.collections.get('Construction')
        collection.objects.link(original)
        original['gf_role'] = 'construction'; original.hide_render=True; original.hide_set(True)
        graph=bpy.context.evaluated_depsgraph_get()
        mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(graph),preserve_all_data_layers=True,depsgraph=graph)
        obj.modifiers.clear(); obj.data=mesh
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(island_margin=margin)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def finalize_mesh(obj):
    modifier = obj.modifiers.get('Game triangulation') or obj.modifiers.new('Game triangulation', 'TRIANGULATE')
    modifier.quad_method = 'FIXED'
    modifier.ngon_method = 'BEAUTY'
    return obj


def pbr_material(name, base_color, roughness, metallic, textures=None):
    import bpy
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = base_color
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    for name in ('Base Color','Roughness','Metallic','Normal','Emission Color'):
        for link in list(shader.inputs[name].links):
            mat.node_tree.links.remove(link)
    mat.diffuse_color = base_color
    for channel, file in (textures or {}).items():
        file = file['path'] if isinstance(file, dict) else file
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(Path(file).resolve()), check_existing=True)
        node.image.colorspace_settings.name = 'sRGB' if channel in ('base_color', 'emissive') else 'Non-Color'
        node['gf_channel'] = channel
        if channel == 'normal':
            normal = mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(node.outputs['Color'], normal.inputs['Color'])
            mat.node_tree.links.new(normal.outputs['Normal'], shader.inputs['Normal'])
        elif channel in ('base_color', 'roughness', 'metallic', 'emissive'):
            socket = {'base_color': 'Base Color', 'roughness': 'Roughness', 'metallic': 'Metallic', 'emissive': 'Emission Color'}[channel]
            mat.node_tree.links.new(node.outputs['Color'], shader.inputs[socket])
    return mat


def material_evidence(mat):
    import bpy
    if not mat:
        raise ValueError('Game outputs must have assigned materials')
    shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if mat.use_nodes else None
    result = {'id': mat.name, 'base_color': list(shader.inputs['Base Color'].default_value) if shader else list(mat.diffuse_color),
              'roughness': float(shader.inputs['Roughness'].default_value) if shader else float(mat.roughness),
              'metallic': float(shader.inputs['Metallic'].default_value) if shader else float(mat.metallic),
              'blend_mode': mat.get('gf_blend_mode', 'OPAQUE'), 'textures': {}}
    if shader:
        for channel, socket in [('base_color', 'Base Color'), ('roughness', 'Roughness'), ('metallic', 'Metallic'), ('emissive', 'Emission Color'), ('normal', 'Normal')]:
            input_socket = shader.inputs.get(socket)
            if not input_socket or not input_socket.is_linked:
                continue
            node = input_socket.links[0].from_node
            if channel == 'normal' and node.type == 'NORMAL_MAP' and node.inputs['Color'].is_linked:
                node = node.inputs['Color'].links[0].from_node
            if node.type == 'TEX_IMAGE' and node.image:
                if node.image.is_dirty:
                    raise ValueError(f'Save texture edits before verification: {node.image.name}')
                path = Path(bpy.path.abspath(node.image.filepath)).resolve()
                if not path.is_file():
                    raise ValueError(f'Missing texture file: {path}; save image edits before verifying')
                result['textures'][channel] = {'path': str(path), 'color_space': 'sRGB' if channel in ('base_color', 'emissive') else 'linear',
                                                'normal_convention': 'opengl' if channel == 'normal' else None}
                from .storage import digest
                result['textures'][channel]['sha256'] = digest(path)
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.get('gf_channel') == 'occlusion' and node.image:
                result['textures']['occlusion'] = {'path': str(Path(bpy.path.abspath(node.image.filepath)).resolve()), 'color_space': 'linear'}
                from .storage import digest
                result['textures']['occlusion']['sha256'] = digest(result['textures']['occlusion']['path'])
    return result


SURFACE_GROUPS = ('guide_bound', 'gf_inner', 'gf_solidify_rim', 'gf_pocket')


def point_attributes(original, mesh):
    """Surfacing weights and gf_* point attributes; empty for meshes built without them."""
    result = {}
    names = {group.index: group.name for group in original.vertex_groups
             if group.name in SURFACE_GROUPS or group.name.startswith('gf_loop_')}
    if names:
        values = {name: [0.0] * len(mesh.vertices) for name in names.values()}
        for vertex in mesh.vertices:
            for element in vertex.groups:
                if element.group in names:
                    values[names[element.group]][vertex.index] = round(element.weight, 6)
        result.update(values)
    for attribute in mesh.attributes:
        if attribute.domain == 'POINT' and attribute.name.startswith('gf_') and attribute.data_type in ('FLOAT', 'FLOAT_VECTOR'):
            field = 'value' if attribute.data_type == 'FLOAT' else 'vector'
            result[attribute.name] = [getattr(item, field) if field == 'value' else list(getattr(item, field)) for item in attribute.data]
    return result


def meshes(target='game'):
    import bpy
    if bpy.context.scene.get('geometryforge_units') != 'mm':
        raise ValueError('Game source scene must use GeometryForge millimeters')
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    roles = {'render', 'lod', 'collision'} if target == 'game' else {'design', 'high_detail', 'guide', 'interface'}
    result = []
    for original in bpy.context.scene.objects:
        role = original.get('gf_role')
        if role not in roles or original.type != 'MESH':
            continue
        evaluated = original.evaluated_get(graph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
        try:
            attributes = point_attributes(original, mesh)
            if role == 'interface':
                item = {'evidence_version': 2, 'name': original.name, 'part': original.get('gf_part', original.name),
                        'role': role, 'vertices': [list(v.co) for v in mesh.vertices], 'faces': [],
                        'edges': [list(e.vertices) for e in mesh.edges],
                        'matrix_world': [list(row) for row in original.matrix_world], 'pivot_mm': list(original.location),
                        'metadata': json.loads(original.get('gf_metadata', '{}'))}
                if not item['edges']:
                    raise ValueError(f'Interface ring has no edges: {original.name}')
                if attributes:
                    item['point_attributes'] = attributes
                result.append(item)
                continue
            mesh.calc_loop_triangles()
            triangles = list(mesh.loop_triangles)
            if not triangles:
                raise ValueError(f'Empty registered output: {original.name}')
            uv = {layer.name: [[list(layer.data[i].uv) for i in t.loops] for t in triangles] for layer in mesh.uv_layers}
            normals = [[list(mesh.corner_normals[i].vector) for i in t.loops] for t in triangles]
            tangents = []
            if uv and role in ('render', 'lod'):
                mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
                tangents = [[[*mesh.loops[i].tangent, mesh.loops[i].bitangent_sign] for i in t.loops] for t in triangles]
            colors = None
            layer = mesh.color_attributes.active_color
            if layer:
                colors = [[list(layer.data[i if layer.domain == 'CORNER' else mesh.loops[i].vertex_index].color) for i in t.loops] for t in triangles]
            metadata = json.loads(original.get('gf_metadata', '{}'))
            slots = sorted({t.material_index for t in triangles})
            slot_map = {slot:index for index,slot in enumerate(slots)}
            item = {'evidence_version': 2, 'name': original.name, 'part': original.get('gf_part', original.name),
                    'role': role, 'vertices': [list(v.co) for v in mesh.vertices],
                    'faces': [list(t.vertices) for t in triangles], 'uv_layers': uv,
                    'corner_normals': normals, 'corner_tangents': tangents, 'corner_colors': colors,
                    'face_materials': [slot_map[t.material_index] for t in triangles],
                    'materials': [material_evidence(mesh.materials[slot]) for slot in slots] if role in ('render', 'lod') else [],
                    'matrix_world': [list(row) for row in original.matrix_world], 'pivot_mm': list(original.location),
                    'metadata': metadata}
            if attributes:
                item['point_attributes'] = attributes
            result.append(item)
        finally:
            evaluated.to_mesh_clear()
    if not result:
        raise ValueError(f'No registered {target} outputs')
    return result


def bake(obj, sources, directory, resolution, margin, cage_extrusion, samples):
    import bpy
    if not sources or obj in sources or resolution < 16:
        raise ValueError('Baking requires distinct source geometry and a valid resolution')
    if len(obj.data.materials) != 1:
        raise ValueError('Bake one material region at a time; the target helper requires exactly one material slot')
    directory.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    old_engine = scene.render.engine
    old_samples = scene.cycles.samples
    states = {o: (o.hide_render, o.hide_get()) for o in [obj, *sources]}
    material = obj.data.materials[0]
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    result = {}
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    try:
        for channel, kind in [('base_color', 'DIFFUSE'), ('normal', 'NORMAL'), ('roughness', 'ROUGHNESS'), ('metallic', 'EMIT'), ('occlusion', 'AO')]:
            image = bpy.data.images.new(obj['gf_part'] + '_' + channel, width=resolution, height=resolution, alpha=False)
            image.colorspace_settings.name = 'sRGB' if channel == 'base_color' else 'Non-Color'
            node = material.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = image
            node['gf_channel'] = channel
            material.node_tree.nodes.active = node
            replaced = []
            if channel == 'metallic':
                for src in sources:
                    for mat in src.data.materials:
                        if mat is None or not mat.use_nodes:
                            raise ValueError('Metallic baking requires source node materials')
                        tree = mat.node_tree
                        output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
                        principled = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
                        old_links = [(l.from_socket, l.to_socket) for l in output.inputs['Surface'].links]
                        emission = tree.nodes.new('ShaderNodeEmission')
                        metal = principled.inputs['Metallic']
                        if metal.is_linked:
                            tree.links.new(metal.links[0].from_socket, emission.inputs['Color'])
                        else:
                            emission.inputs['Color'].default_value = (metal.default_value,) * 3 + (1,)
                        tree.links.new(emission.outputs[0], output.inputs['Surface'])
                        replaced.append((tree, emission, old_links))
            try:
                activate(obj)
                obj.hide_render = False
                for src in sources:
                    src.hide_set(False)
                    src.hide_render = False
                    src.select_set(True)
                scene.render.bake.use_pass_direct = False
                scene.render.bake.use_pass_indirect = False
                scene.render.bake.use_pass_color = True
                bpy.ops.object.bake(type=kind, use_selected_to_active=True, margin=margin,
                                    cage_extrusion=cage_extrusion, normal_space='TANGENT')
            finally:
                for tree, emission, links in replaced:
                    tree.nodes.remove(emission)
                    for from_socket, to_socket in links:
                        tree.links.new(from_socket, to_socket)
            path = directory / f'{obj["gf_part"]}_{channel}.png'
            image.filepath_raw = str(path)
            image.file_format = 'PNG'
            image.save()
            image.pack()
            if channel == 'normal':
                normal = material.node_tree.nodes.new('ShaderNodeNormalMap')
                material.node_tree.links.new(node.outputs['Color'], normal.inputs['Color'])
                material.node_tree.links.new(normal.outputs['Normal'], shader.inputs['Normal'])
            elif channel in ('base_color', 'roughness', 'metallic'):
                material.node_tree.links.new(node.outputs['Color'], shader.inputs[{'base_color':'Base Color','roughness':'Roughness','metallic':'Metallic'}[channel]])
            result[channel] = str(path)
        obj['gf_bake'] = json.dumps({'resolution': resolution, 'margin': margin, 'cage_extrusion': cage_extrusion,
                                     'samples': samples, 'sources': [s.name for s in sources], 'maps': result})
    finally:
        scene.render.engine = old_engine
        scene.cycles.samples = old_samples
        for o, (render, hidden) in states.items():
            o.hide_render = render
            o.hide_set(hidden)
    return result


def export_fbx(objects, directory, previous=None, full=False):
    """One asset-local FBX per output; reopen in an isolated scene to check units/UVs."""
    import bpy
    from mathutils import Matrix
    from .storage import digest, fingerprint
    directory.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for item in objects:
        grouped.setdefault(item['part'], []).append(item)
    original_scene = bpy.context.scene
    result = {}
    for output, items in grouped.items():
        key = fingerprint([{k:v for k,v in item.items() if k not in ('materials','pivot_mm')}
                           | {'material_ids':[m['id'] for m in item.get('materials',[])]} for item in items])
        cached = (previous or {}).get(output,{})
        if not full and cached.get('key') == key and all(Path(file).is_file() and digest(file)==sha for file,sha in cached.get('files',{}).items()) and cached.get('files'):
            result[output] = {**cached,'reused':True}
            continue
        render = [i for i in items if i['role'] == 'render']
        if len(render) != 1:
            raise ValueError(f'{output}: each output requires exactly one base render mesh')
        temp = bpy.data.scenes.new('GeometryForge FBX check')
        temp.unit_settings.system = 'METRIC'
        temp.unit_settings.scale_length = 0.001
        bpy.context.window.scene = temp
        created = []
        try:
            for index, item in enumerate(items):
                original = bpy.data.objects.get(item['name'])
                # The original scene's dependency graph owns the evaluated modifiers.
                bpy.context.window.scene = original_scene
                mesh = bpy.data.meshes.new_from_object(original.evaluated_get(bpy.context.evaluated_depsgraph_get()), preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
                bpy.context.window.scene = temp
                used = sorted({p.material_index for p in mesh.polygons})
                slot_materials = [mesh.materials[slot] for slot in used] if mesh.materials else []
                indices = [used.index(p.material_index) for p in mesh.polygons]
                mesh.materials.clear()
                for mat in slot_materials: mesh.materials.append(mat)
                for polygon,index in zip(mesh.polygons,indices): polygon.material_index=index
                if item['role'] == 'collision':
                    name = f'UCX_{output}_{index:02d}'
                elif item['role'] == 'lod':
                    name = output + f'_LOD{item["metadata"]["lod"]}'
                else:
                    name = output
                obj = bpy.data.objects.new(name, mesh)
                obj.matrix_world = Matrix.Identity(4)
                # Registered collision/LODs may have separate local frames; move into the base frame.
                delta = Matrix(render[0]['matrix_world']).inverted() @ Matrix(item['matrix_world'])
                mesh.transform(delta)
                temp.collection.objects.link(obj)
                obj.select_set(True)
                created.append(obj)
            path = directory / f'{output}.fbx'
            for obj, item in zip(created, items):
                obj.select_set(item['role'] != 'lod')
            bpy.context.view_layer.objects.active = created[0]
            bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                                     use_mesh_modifiers=False, add_leaf_bones=False,
                                     axis_forward='-Y', axis_up='Z', apply_unit_scale=True,
                                     bake_anim=False, path_mode='STRIP',mesh_smooth_type='FACE')
            lod_files = {}
            for obj,item in zip(created,items):
                if item['role'] == 'lod':
                    activate(obj)
                    lod_path = directory / f'{output}_LOD{item["metadata"]["lod"]}.fbx'
                    bpy.ops.export_scene.fbx(filepath=str(lod_path),use_selection=True,object_types={'MESH'},
                                             use_mesh_modifiers=False,axis_forward='-Y',axis_up='Z',
                                             apply_unit_scale=True,bake_anim=False,path_mode='STRIP',mesh_smooth_type='FACE')
                    lod_files[str(item['metadata']['lod'])] = str(lod_path)
            for obj in created:
                bpy.data.objects.remove(obj, do_unlink=True)
            created.clear()
            bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
            imported = [o for o in temp.objects if o.type == 'MESH' and not o.name.startswith('UCX_') and '_LOD' not in o.name]
            if len(imported) != 1:
                raise ValueError(f'{output}: FBX read-back lost the base mesh')
            probe = imported[0]
            expected = render[0]
            import numpy as np
            v = np.asarray(expected['vertices'])
            actual = np.asarray([list(probe.matrix_world @ vertex.co) for vertex in probe.data.vertices])
            if not np.allclose(np.ptp(actual, axis=0), np.ptp(v, axis=0), atol=0.02, rtol=1e-5):
                raise ValueError(f'{output}: FBX read-back changed source millimeter dimensions')
            if len(probe.data.uv_layers) != len(expected['uv_layers']):
                raise ValueError(f'{output}: FBX read-back lost UV layers')
            result[output] = {'path': str(path), 'sha256': digest(path), 'lods': lod_files,
                              'key': key, 'reused':False, 'files':{str(f):digest(f) for f in [path,*map(Path,lod_files.values())]},
                              'roundtrip': {'passed': True, 'bbox_mm': np.ptp(actual, axis=0).tolist(), 'uv_layers': len(probe.data.uv_layers)}}
        finally:
            bpy.context.window.scene = original_scene
            for obj in list(temp.objects):
                mesh = obj.data if obj.type == 'MESH' else None
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            bpy.data.scenes.remove(temp)
    return result
