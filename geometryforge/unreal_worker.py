"""Run only inside Unreal Editor. Packaged alongside every game export."""
import hashlib
import json
import os
from pathlib import Path
import traceback
import math


def assembly_transform(matrix):
    """Convert a right-handed mm placement into Unreal location, quaternion and scale."""
    signs=(1,-1,1)
    rotation=[[matrix[i][j]*signs[i]*signs[j] for j in range(3)] for i in range(3)]
    scales=[math.sqrt(sum(rotation[i][j]**2 for i in range(3))) for j in range(3)]
    determinant=(rotation[0][0]*(rotation[1][1]*rotation[2][2]-rotation[1][2]*rotation[2][1])-
                 rotation[0][1]*(rotation[1][0]*rotation[2][2]-rotation[1][2]*rotation[2][0])+
                 rotation[0][2]*(rotation[1][0]*rotation[2][1]-rotation[1][1]*rotation[2][0]))
    if determinant<0: scales[0]*=-1
    rotation=[[rotation[i][j]/scales[j] for j in range(3)] for i in range(3)]
    trace=sum(rotation[i][i] for i in range(3))
    if trace>0:
        s=math.sqrt(trace+1)*2
        quaternion=[(rotation[2][1]-rotation[1][2])/s,(rotation[0][2]-rotation[2][0])/s,(rotation[1][0]-rotation[0][1])/s,s/4]
    else:
        i=max(range(3),key=lambda i:rotation[i][i]);j=(i+1)%3;k=(i+2)%3
        s=math.sqrt(1+rotation[i][i]-rotation[j][j]-rotation[k][k])*2
        quaternion=[0,0,0,(rotation[k][j]-rotation[j][k])/s]
        quaternion[i]=s/4;quaternion[j]=(rotation[j][i]+rotation[i][j])/s;quaternion[k]=(rotation[k][i]+rotation[i][k])/s
    return [matrix[i][3]*signs[i]*.1 for i in range(3)],quaternion,scales


def execute(request):
    import unreal
    version = unreal.SystemLibrary.get_engine_version()
    if not version.startswith('5.8'):
        raise RuntimeError(f'Unreal adapter is verified against 5.8; unsupported editor API version: {version}')
    package = Path(request['package'])
    manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    for name,sha in manifest['files'].items():
        if hashlib.sha256((package/name).read_bytes()).hexdigest() != sha:
            raise RuntimeError(f'Package artifact changed: {name}')
    destination = request['destination']
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    assets = unreal.EditorAssetLibrary
    meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.EditorStaticMeshLibrary
    material_tools = unreal.MaterialEditingLibrary
    measurements = {}
    material_assets = {}

    def import_file(file, name, folder, options=None):
        task = unreal.AssetImportTask()
        for key,value in {'filename':str(file),'destination_path':folder,'destination_name':name,'automated':True,
                          'replace_existing':False,'save':True}.items():
            task.set_editor_property(key,value)
        if options:
            task.set_editor_property('options',options)
        asset_tools.import_asset_tasks([task])
        paths = task.get_editor_property('imported_object_paths')
        if not paths:
            raise RuntimeError(f'Import produced no assets: {file}')
        return [assets.load_asset(path) for path in paths]

    if not request['verify_only']:
        master_name = 'M_GeometryForge'
        master = asset_tools.create_asset(master_name,destination+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        if not master:
            raise RuntimeError('Could not create managed PBR master material')
        def scalar(name, prop, x,y, value):
            node = material_tools.create_material_expression(master,unreal.MaterialExpressionScalarParameter,x,y)
            node.set_editor_property('parameter_name',name); node.set_editor_property('default_value',value)
            material_tools.connect_material_property(node,'',prop)
        scalar('Roughness',unreal.MaterialProperty.MP_ROUGHNESS,-400,140,.5)
        scalar('Metallic',unreal.MaterialProperty.MP_METALLIC,-400,240,0)
        color = material_tools.create_material_expression(master,unreal.MaterialExpressionVectorParameter,-400,0)
        color.set_editor_property('parameter_name','BaseColor'); color.set_editor_property('default_value',unreal.LinearColor(1,1,1,1))
        material_tools.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
        material_tools.recompile_material(master); assets.save_loaded_asset(master)
        for ident,material in manifest['materials'].items():
            # Each material receives its own master when it has texture connections.
            safe_id = 'M_'+hashlib.sha256(ident.encode()).hexdigest()[:12]
            parent = asset_tools.create_asset(safe_id,destination+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
            if not parent: raise RuntimeError('Could not create PBR material')
            nodes = {}
            for channel,spec in material['textures'].items():
                if channel in ('roughness','metallic','occlusion') and 'orm' in material['textures']:
                    continue
                texture = import_file(package/spec['path'],'T_'+safe_id+'_'+channel,destination+'/Textures')[0]
                texture.set_editor_property('srgb',spec['color_space']=='sRGB')
                if channel == 'normal':
                    texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
                elif channel == 'orm':
                    texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
                assets.save_loaded_asset(texture)
                node = material_tools.create_material_expression(parent,unreal.MaterialExpressionTextureSampleParameter2D,-500,len(nodes)*180)
                node.set_editor_property('parameter_name',channel); node.set_editor_property('texture',texture)
                node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if channel=='normal' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS if channel=='orm' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if spec['color_space']=='sRGB' else unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
                nodes[channel] = node
            for channel,prop in [('base_color',unreal.MaterialProperty.MP_BASE_COLOR),('normal',unreal.MaterialProperty.MP_NORMAL),('emissive',unreal.MaterialProperty.MP_EMISSIVE_COLOR)]:
                if channel in nodes: material_tools.connect_material_property(nodes[channel],'RGB',prop)
            if 'base_color' not in nodes:
                node = material_tools.create_material_expression(parent,unreal.MaterialExpressionConstant3Vector,-300,0)
                rgba = material.get('base_color',[1,1,1,1]); node.set_editor_property('constant',unreal.LinearColor(*rgba))
                material_tools.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
            for channel,prop,swizzle in [('occlusion',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,'R'),('roughness',unreal.MaterialProperty.MP_ROUGHNESS,'G'),('metallic',unreal.MaterialProperty.MP_METALLIC,'B')]:
                if 'orm' in nodes: material_tools.connect_material_property(nodes['orm'],swizzle,prop)
                elif channel in nodes: material_tools.connect_material_property(nodes[channel],'R',prop)
                elif channel != 'occlusion':
                    node = material_tools.create_material_expression(parent,unreal.MaterialExpressionScalarParameter,-300,200 if channel=='roughness' else 300)
                    node.set_editor_property('parameter_name',channel); node.set_editor_property('default_value',material.get(channel,.5 if channel=='roughness' else 0))
                    material_tools.connect_material_property(node,'',prop)
            mode = material.get('blend_mode','OPAQUE')
            if mode == 'MASKED': parent.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
            elif mode == 'TRANSLUCENT': parent.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
            material_tools.recompile_material(parent); assets.save_loaded_asset(parent)
            instance = asset_tools.create_asset('MI_'+safe_id,destination+'/Materials',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
            material_tools.set_material_instance_parent(instance,parent); assets.save_loaded_asset(instance)
            material_assets[ident] = instance
        for name,output in manifest['outputs'].items():
            options = unreal.FbxImportUI()
            options.set_editor_property('import_mesh',True); options.set_editor_property('import_as_skeletal',False)
            options.set_editor_property('import_materials',False); options.set_editor_property('import_textures',False)
            options.set_editor_property('automated_import_should_detect_type',False)
            options.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
            data = options.get_editor_property('static_mesh_import_data')
            data.set_editor_property('combine_meshes',False); data.set_editor_property('auto_generate_collision',False)
            data.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
            data.set_editor_property('generate_lightmap_u_vs',manifest['profile']['lighting']=='baked')
            data.set_editor_property('convert_scene',True); data.set_editor_property('convert_scene_unit',True)
            imported = import_file(package/output['mesh'],name,destination+'/Meshes',options)
            mesh = next((a for a in imported if isinstance(a,unreal.StaticMesh)),None)
            if mesh is None: raise RuntimeError(f'No static mesh imported for {name}')
            unreal.log(f'GeometryForge {name}: imported convex collision bodies {meshes.get_convex_collision_count(mesh)}')
            for slot,ident in enumerate(output['materials']): mesh.set_material(slot,material_assets[ident])
            for level,path in output['lod_files'].items():
                if meshes.import_lod(mesh,int(level),str(package/path)) < 0:
                    raise RuntimeError(f'{name}: LOD import failed')
            if output['nanite']:
                settings = meshes.get_nanite_settings(mesh)
                settings.set_editor_property('enabled',True)
                settings.set_editor_property('fallback_relative_error',output['fallback_relative_error'])
                meshes.set_nanite_settings(mesh,settings,True)
            for socket in output['sockets']:
                native = unreal.StaticMeshSocket(outer=mesh)
                native.set_editor_property('socket_name',socket['name'])
                x,y,z = socket['position_mm']; native.set_editor_property('relative_location',unreal.Vector(x*.1,-y*.1,z*.1))
                mesh.add_socket(native)
            assets.save_loaded_asset(mesh)
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not level.new_level(destination+'/Review'):
            raise RuntimeError('Could not create review level')
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for name,output in manifest['outputs'].items():
            mesh = assets.load_asset(destination+'/Meshes/'+name)
            location,rotation,scale=assembly_transform(output['matrix_world_mm']);location=unreal.Vector(*location)
            actor = actors.spawn_actor_from_class(unreal.StaticMeshActor,location)
            actor.static_mesh_component.set_static_mesh(mesh); actor.set_actor_label(name)
            actor.set_actor_rotation(unreal.Quat(*rotation).rotator(),False);actor.set_actor_scale3d(unreal.Vector(*scale))
        level.save_current_level()
    for name,output in manifest['outputs'].items():
        mesh = assets.load_asset(destination+'/Meshes/'+name)
        if not isinstance(mesh,unreal.StaticMesh): raise RuntimeError(f'{name}: missing saved static mesh')
        box = mesh.get_bounding_box(); extent = box.max-box.min
        actual = [extent.x,extent.y,extent.z]
        expected = [v*.1 for v in output['bbox_mm']]
        if any(abs(a-b)>max(.02,b*.001) for a,b in zip(actual,expected)):
            raise RuntimeError(f'{name}: imported dimensions {actual} differ from expected centimeters {expected}')
        lod_count = meshes.get_lod_count(mesh)
        collision_count = meshes.get_convex_collision_count(mesh)
        if not output['nanite'] and lod_count != 1+len(output['lods']): raise RuntimeError(f'{name}: incomplete imported LOD chain')
        if output['collision_policy'] != 'decorative' and collision_count < output['collision_bodies']:
            raise RuntimeError(f'{name}: missing imported collision bodies')
        if output['nanite'] and not meshes.get_nanite_settings(mesh).get_editor_property('enabled'):
            raise RuntimeError(f'{name}: Nanite did not remain enabled')
        if len(mesh.get_editor_property('static_materials')) != len(output['materials']):
            raise RuntimeError(f'{name}: material assignments changed')
        for slot,ident in enumerate(output['materials']):
            expected_material=destination+'/Materials/MI_M_'+hashlib.sha256(ident.encode()).hexdigest()[:12]
            material=mesh.get_material(slot)
            if not material or material.get_path_name().split('.')[0]!=expected_material:
                raise RuntimeError(f'{name}: material slot {slot} does not reference its declared PBR instance')
            for channel,spec in manifest['materials'][ident]['textures'].items():
                if channel in ('roughness','metallic','occlusion') and 'orm' in manifest['materials'][ident]['textures']: continue
                texture=material_tools.get_material_instance_texture_parameter_value(material,channel)
                if texture is None or texture.get_editor_property('srgb')!=(spec['color_space']=='sRGB'):
                    raise RuntimeError(f'{name}: {channel} texture or color space changed')
        measurements[name] = {'bbox_cm':actual,'lod_count':lod_count,'collision_bodies':collision_count,
                              'nanite':output['nanite'],'asset':mesh.get_path_name()}
    return {'passed':True,'engine_version':version,'measurements':measurements,'review_level':destination+'/Review',
            'coverage':{'saved_assets':True,'rendered_review':False,'performance_measured':False}}


def main():
    request = json.loads(Path(os.environ['GEOMETRYFORGE_UNREAL_REQUEST']).read_text(encoding='utf-8'))
    try:
        result = execute(request)
    except BaseException as exc:
        result = {'passed':False,'error':str(exc),'traceback':traceback.format_exc()}
    Path(request['report']).write_text(json.dumps(result,indent=2),encoding='utf-8')
    if not result['passed']:
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
