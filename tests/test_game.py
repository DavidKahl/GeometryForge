from copy import deepcopy
from pathlib import Path
import json

import numpy as np
import pytest
from PIL import Image

from geometryforge import backends, engine, game, projects, targets, unreal
from geometryforge.storage import digest, inside, read, write


@pytest.fixture
def game_project(project, monkeypatch):
    root,calls = project
    targets.migrate(root)
    contract=root/'project.toml'
    contract.write_text(contract.read_text()+'\n[targets.game]\nchecks = []\n',encoding='utf-8')
    decisions=read(root/'decisions.json'); decisions.update(output_targets=['game'],game={'profile':'unreal_desktop_standard'})
    write(root/'decisions.json',decisions)
    original=backends.run_native
    def native(backend,out,entry,parameters,parts,source,timeout,executable):
        context=backends.native_context.get()
        if context.get('target') != 'game':
            return original(backend,out,entry,parameters,parts,source,timeout,executable)
        calls.append({'backend':backend,'target':'game','parts':list(parts),'stages':deepcopy(context.get('stages',{}))})
        objects=read(source,[]) if source else []
        for part in parts:
            objects=[o for o in objects if o['part']!=part]
            # An intentionally OPEN render surface, distinct from closed collision.
            import trimesh
            mesh=trimesh.creation.box([parameters['width_'+part],10,10])
            v=mesh.vertices.tolist(); f=mesh.faces[:-2].tolist()
            normals=np.cross(np.asarray(v)[f][:,1]-np.asarray(v)[f][:,0],np.asarray(v)[f][:,2]-np.asarray(v)[f][:,0]); normals/=np.linalg.norm(normals,axis=1)[:,None]
            tangent=np.asarray(v)[f][:,1]-np.asarray(v)[f][:,0]; tangent/=np.linalg.norm(tangent,axis=1)[:,None]
            base={'part':part,'name':part,'role':'render','vertices':v,'faces':f,'matrix_world':np.eye(4).tolist(),
                  'uv_layers':{'UVMap':[[[0,0],[1,0],[0,1]]]*len(f)},'corner_normals':[[n.tolist()]*3 for n in normals],
                  'corner_tangents':[[[*t,1]]*3 for t in tangent],'face_materials':[0]*len(f),
                  'materials':[{'id':'M_Test','base_color':[.2,.4,.6,1],'roughness':.5,'metallic':0,'textures':{}}],
                  'metadata':{'source_parts':[part],'uv_mode':'tiled'}}
            objects.append(base)
            for level in range(1,4):
                lod=deepcopy(base); lod.update(role='lod',name=part+f'_LOD{level}',metadata={'lod':level,'source_parts':[part],'uv_mode':'tiled'}); objects.append(lod)
            objects.append({'part':part,'name':part+'_collision','role':'collision','vertices':v,'faces':mesh.faces.tolist(),
                            'matrix_world':np.eye(4).tolist(),'metadata':{},'materials':[]})
        scene=out/'model.blend'; write(scene,objects)
        exports={}
        for part in {o['part'] for o in objects}:
            fbx=out/(part+'.fbx'); fbx.write_bytes(b'unit-test native export stand-in')
            lods={}
            for level in range(1,4):
                file=out/(part+f'_LOD{level}.fbx');file.write_bytes(b'unit-test native LOD stand-in');lods[str(level)]=str(file)
            exports[part]={'path':str(fbx),'sha256':digest(fbx),'lods':lods,'roundtrip':{'passed':True}}
        return {'version':'fixture-2','scene':str(scene),'objects':objects,'mesh_exports':exports}
    monkeypatch.setattr(backends,'run_native',native)
    return root,calls


def test_game_only_open_surfaces_and_safe_package(game_project):
    root,_=game_project
    d=read(root/'decisions.json'); d['print']['bed_mm']='irrelevant'; write(root/'decisions.json',d)
    run=engine.execute(root)
    assert run['status']=='passed',run['failures']
    assert 'kit' not in run['backends']['blender']
    assert not list((root/'.geometryforge/runs'/run['id']).rglob('*.stl'))
    manifest=game.verify_package(inside(root,run['backends']['blender']['game']['manifest']).parent)
    assert manifest['coverage']=={'package_safe':True,'unreal_verified':False}
    assert engine.context(root)['targets']['game']['stale'] is False


def test_failed_print_keeps_game_and_aggregate_safe_points(game_project):
    root,_=game_project; first=engine.execute(root)
    d=read(root/'decisions.json'); d['output_targets']=['game','print']; d['print']['bed_mm']=[1,1,1]; write(root/'decisions.json',d)
    result=engine.execute(root)
    assert result['targets']['game']['status']=='passed'
    assert result['targets']['print']['status']=='failed'
    p=projects.load(root)
    assert p['state']['safe_point']==first['id']
    assert p['state']['safe_points']['game']==result['id']
    restored=engine.restore(root,result['id'],target='game')
    assert (Path(restored['working_copy'])/'game/blender/model.blend').is_file()


def test_migration_preserves_old_sources_scenes_and_restoration(project):
    root,_=project; first=engine.execute(root)
    source_hash=digest(root/'models/a.py'); native=inside(root,first['backends']['blender']['native']['path']); native_hash=digest(native)
    result=targets.migrate(root)
    assert (Path(result['backup'])/'project.toml').is_file()
    assert digest(root/'models/a.py')==source_hash and digest(native)==native_hash
    assert projects.load(root)['decisions']['output_targets']==['print']
    assert engine.restore(root,first['id'],target='print')['targets']==['print']
    second=engine.execute(root)
    assert second['status']=='passed',second['failures']


def test_route_settings_do_not_invalidate_other_route(game_project):
    root,_=game_project
    before=targets.route_key(projects.load(root),'game')
    d=read(root/'decisions.json'); d['print']['nozzle_mm']=.6; write(root/'decisions.json',d)
    assert targets.route_key(projects.load(root),'game')==before
    d['game']['material_budget']=1; write(root/'decisions.json',d)
    assert targets.route_key(projects.load(root),'game')!=before


def test_attributes_and_texture_bytes_invalidate_evidence(game_project):
    root,calls=game_project; first=engine.execute(root)
    state=projects.load(root)['state']['targets']['game']['backends']['blender']; scene=inside(root,state['working'])
    objects=read(scene); objects[0]['uv_layers']['UVMap'][0][0]=[.1,.2]; write(scene,objects)
    result=engine.execute(root,source='scene',full=True)
    assert result['status']=='passed',result['failures']
    assert calls[-1]['parts']==[]
    assert 'a' in result['backends']['blender']['changed_parts']
    assert 'a' in result['backends']['blender']['native_edits']
    assert inside(root,state['working']).is_file()


def test_preparation_stages_invalidate_without_geometry_rebuild(game_project):
    root,calls=game_project
    (root/'models/materials.py').write_text('# recipe')
    with (root/'project.toml').open('a') as stream:
        stream.write('\n[targets.game.stages.materials]\nentry="models/materials.py"\nparameters=["width_b"]\ndepends=["geometry"]\n')
    first=engine.execute(root); assert first['status']=='passed',first['failures']
    # Changing a recipe, rather than geometry-driving dimensions, only runs preparation.
    (root/'models/materials.py').write_text('# changed material recipe')
    plan=engine.plan(root)['targets']['game']['backends']['blender']
    assert plan['parts']==[] and plan['stages']['materials']['run']
    result=engine.execute(root); assert result['status']=='passed',result['failures']
    assert calls[-1]['parts']==[] and calls[-1]['stages']['materials']['run']
    verify=engine.execute(root,source='scene',full=True)
    assert verify['status']=='passed'
    assert not any(s['run'] for s in calls[-1]['stages'].values())


def test_budget_and_material_compatibility_failures(game_project):
    root,_=game_project; result=engine.execute(root)
    raw=inside(root,next(a for a in result['backends']['blender']['parts']['a']['artifacts'] if a['path'].endswith('assembly.json'))['path'])
    objects=read(raw)['objects']
    assert not game.validate(objects,{'triangle_budget':1})['passed']
    objects[0]['materials'][0]['blend_mode']='TRANSLUCENT'
    assert not game.validate(objects,{'profile':'unreal_desktop_nanite'})['passed']
    objects[0]['metadata']['nanite']=False
    assert game.validate(objects,{'profile':'unreal_desktop_nanite'})['passed']


def test_glb_preserves_corner_seams_and_package_detects_corruption(game_project):
    root,_=game_project; result=engine.execute(root)
    folder=inside(root,result['backends']['blender']['game']['manifest']).parent
    document=game.verify_glb(folder/'preview/a.glb')
    position=document['accessors'][document['meshes'][0]['primitives'][0]['attributes']['POSITION']]
    assert position['count']==30  # Expanded corners retain ten triangles' seams.
    (folder/'meshes/a.fbx').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='artifact changed'): game.verify_package(folder)


def test_texture_conventions_and_packed_orm(tmp_path):
    root=tmp_path; frozen=root/'.geometryforge/runs/test/inputs'; frozen.mkdir(parents=True)
    for channel,color in [('normal',(128,64,255)),('roughness',(80,80,80)),('metallic',(200,200,200)),('occlusion',(240,240,240))]:
        Image.new('RGB',(4,4),color).save(frozen/(channel+'.png'))
    material={'id':'M_Textured','base_color':[1,1,1,1],'roughness':.5,'metallic':0,
              'textures':{c:{'path':c+'.png','normal_convention':'opengl'} for c in ('normal','roughness','metallic','occlusion')}}
    out=root/'package'; out.mkdir()
    result=game.pack_materials([{'materials':[material]}],game.profile_settings({}),out,root,frozen)['M_Textured']
    assert Image.open(out/result['textures']['normal']['path']).getpixel((0,0))==(128,191,255)
    assert Image.open(out/result['textures']['normal']['preview_path']).getpixel((0,0))==(128,64,255)
    assert Image.open(out/result['textures']['orm']['path']).getpixel((0,0))==(240,80,200)


def test_derivation_requires_recipe_and_immutable_source(game_project):
    root,_=game_project; first=engine.execute(root)
    with pytest.raises(ValueError,match='derivation_recipe'):
        targets.derive(root,'print',first['id'],'game')
    # Source modification must be detected before any target builder is called.
    source=first['backends']['blender']['native']; inside(root,source['path']).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='changed'):
        targets.validate_derivation(projects.load(root),{'artifacts':[source]})


def test_unreal_missing_plugin_does_not_change_package_safe_point(game_project,tmp_path):
    root,_=game_project; first=engine.execute(root)
    uproject=tmp_path/'Disposable.uproject'; write(uproject,{'EngineAssociation':'5.8','Plugins':[]})
    with pytest.raises(ValueError,match='PythonScriptPlugin'):
        unreal.execute(root,uproject)
    assert projects.load(root)['state']['safe_points']['game']==first['id']


def test_target_contract_rejects_cycles_and_path_escapes(game_project):
    root,_=game_project
    with (root/'project.toml').open('a') as stream:
        stream.write('\n[targets.game.stages.uv]\nentry="../outside.py"\ndepends=["bake"]\n')
    with pytest.raises(ValueError): projects.load(root)


def test_uv_overlap_shared_edges_and_explicit_tiling():
    assert not game.uv_overlaps([[[0,0],[1,0],[0,1]],[[1,0],[1,1],[0,1]]])
    assert game.uv_overlaps([[[0,0],[1,0],[0,1]],[[.1,.1],[.8,.1],[.1,.8]]])


def test_rigid_assembly_units_rotation_and_scale():
    from geometryforge.unreal_worker import assembly_transform
    matrix=[[0,-3,0,100],[2,0,0,200],[0,0,4,300],[0,0,0,1]]
    location,quaternion,scale=assembly_transform(matrix)
    assert location==[10,-20,30] and scale==[2,3,4]
    assert np.allclose(quaternion,[0,0,-2**-.5,2**-.5])


def test_migration_accepts_compact_version_with_comment(project):
    root,_=project
    contract=root/'project.toml';contract.write_text(contract.read_text().replace('format_version = 1','format_version=1 # legacy contract'))
    targets.migrate(root)
    assert projects.load(root)['config']['format_version']==2


def test_package_requires_real_lod_files(game_project,monkeypatch):
    root,_=game_project;native=backends.run_native
    def missing(*args):
        result=native(*args)
        for export in result.get('mesh_exports',{}).values(): export['lods']={}
        return result
    monkeypatch.setattr(backends,'run_native',missing)
    result=engine.execute(root)
    assert result['targets']['game']['status']=='failed'
    assert 'missing delivered LOD' in result['failures'][0]


def test_recooking_noise_does_not_change_semantic_geometry():
    assert game.evidence_equivalent({'uv':[.12399499]},{'uv':[.12399501]})
    assert not game.evidence_equivalent({'uv':[.12]},{'uv':[.121]})
    assert not game.evidence_equivalent({'faces':[[0,1,2]]},{'faces':[[0,2,1]]})


def test_verify_changed_preparation_stays_candidate_and_keeps_safe_point(game_project):
    root,calls=game_project
    (root/'models/materials.py').write_text('# material recipe')
    with (root/'project.toml').open('a') as stream:
        stream.write('\n[targets.game.stages.materials]\nentry="models/materials.py"\nparameters=[]\ndepends=["geometry"]\n')
    first=engine.execute(root);assert first['status']=='passed'
    (root/'models/materials.py').write_text('# changed recipe not yet applied')
    count=len(calls);result=engine.execute(root,source='scene',full=True)
    assert result['status']=='candidate' and len(calls)==count
    assert 'Required preparation changed' in result['failures'][0]
    assert projects.load(root)['state']['safe_points']['game']==first['id']


def test_native_package_loader_does_not_expose_host_site_packages(tmp_path):
    import subprocess
    import sys
    foreign=tmp_path/'foreign-site-packages';package=foreign/'geometryforge';package.mkdir(parents=True)
    (package/'__init__.py').write_text('__version__="probe"')
    for name in ('native_worker.py','blender_worker.py'):
        (package/name).write_text((projects.PACKAGE/name).read_text(encoding='utf-8'),encoding='utf-8')
    (foreign/'numpy.py').write_text('raise RuntimeError("host ABI leaked into native interpreter")')
    program='import runpy,sys,types; runpy.run_path(sys.argv[1],run_name="probe"); sys.modules["bpy"]=types.ModuleType("bpy"); import geometryforge.blender_worker; import numpy; assert sys.argv[2] not in sys.path; assert numpy.__file__ != sys.argv[2]+"/numpy.py"'
    result=subprocess.run([sys.executable,'-c',program,str(package/'native_worker.py'),str(foreign)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
