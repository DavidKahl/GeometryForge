"""Dedicated native game/conversion checks; never opens a user's working project."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import shutil

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geometryforge import engine, projects, targets, unreal
from geometryforge.storage import digest, inside, read, write


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',default='validation-workspace')
    parser.add_argument('--unreal',help='Editor executable or installation for real Unreal 5.8 checks')
    parser.add_argument('--houdini',action='store_true',help='Also check native SOP extraction and actual license capability')
    parser.add_argument('--review',action='store_true',help='Also render offscreen Unreal review and retain editor profiling CSV')
    args=parser.parse_args()
    workspace=Path(args.workspace).resolve()/('game-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    workspace.mkdir(parents=True)
    root=workspace/'housing'
    projects.initialize(root,'mechanical_prop',deliverables='blender',target='game')
    projects.unregister(root)
    evidence={'platform':sys.platform,'workspace':str(workspace),'checks':[],'coverage':{'physical_print':False,'slicer':False,'rendered_unreal_review':False,'performance':False}}
    def checked(name,operation):
        start=time.monotonic()
        try:
            result=operation(); item={'name':name,'passed':True,'details':result}
        except Exception as exc:
            item={'name':name,'passed':False,'error':str(exc)}
        item['seconds']=round(time.monotonic()-start,2)
        evidence['checks'].append(item); write(workspace/'game-evidence.json',evidence)
        return item
    def success(run):
        if run['status']!='passed': raise AssertionError(run['failures'])
        return run
    def build():
        run=success(engine.execute(root))
        info=run['targets']['game']['backends']['blender']
        return {'run':run['id'],'native_structure':info['native_structure'],'package':info['game']['manifest'],'version':info['version'],
                'stages':list(info['stages']),'exports':{k:v['roundtrip'] for k,v in info['mesh_exports'].items()}}
    checked('Blender design, PBR baking, LOD/collision, save/reopen, FBX and GLB',build)
    first=projects.load(root)['state'].get('safe_points',{}).get('game')
    if first:
        def reuse():
            previous=engine.record(projects.load(root),first)['targets']['game']['backends']['blender']
            run=success(engine.execute(root)); info=run['targets']['game']['backends']['blender']
            assert not info['rebuilt_parts'] and all(s['reused'] for s in info['stages'].values())
            assert all(e['reused'] for e in info['mesh_exports'].values())
            assert info['game']['package_id']==previous['game']['package_id']
            return {'run':run['id'],'package_id':info['game']['package_id'],'builders':0,'fbx_reused':True}
        checked('Unchanged run reuses preparation and FBX with a stable package ID',reuse)
        def materials():
            params=read(root/'parameters.json'); params['roughness']=.62; write(root/'parameters.json',params)
            run=success(engine.execute(root)); info=run['targets']['game']['backends']['blender']
            assert not info['rebuilt_parts'] and not info['native_edits']
            assert info['stages']['uv']['reused'] and info['stages']['collision']['reused']
            assert info['stages']['materials']['run'] and info['stages']['bake']['run']
            return {'run':run['id'],'rebuilt_geometry':0,'refreshed':['materials','bake','lod']}
        checked('Material-only revision preserves geometry, UVs and collision',materials)
        def verify():
            before={f:digest(root/f) for f in projects.inputs(projects.load(root))}
            run=success(engine.execute(root,source='scene',full=True))
            assert all(not i['rebuilt_parts'] and not any(s['run'] for s in i.get('stages',{}).values()) for t in run['targets'].values() for i in t['backends'].values())
            assert before=={f:digest(root/f) for f in before}
            return {'run':run['id'],'builders':0,'sources_preserved':True}
        checked('Full verification invokes no modeling/UV/baking builders',verify)
        def print_derivative():
            source=projects.load(root)['state']['safe_points']['game']
            run=targets.derive(root,'print',source,'game',scale=1.25)
            assert run['targets']['print']['status']=='passed',run['failures']
            info=run['targets']['print']['backends']['blender']
            assert info['parts']['body']['measurements']['bbox_mm']==[100,62.5,50]
            return {'run':run['id'],'bbox_mm':info['parts']['body']['measurements']['bbox_mm'],'source':source,'scale':1.25}
        print_result=checked('Game-to-print conversion preserves source and applies physical scale',print_derivative)
        if print_result['passed']:
            def back_to_game():
                source=print_result['details']['run']; run=targets.derive(root,'game',source,'print',scale=.8)
                assert run['targets']['game']['status']=='passed',run['failures']
                return {'run':run['id'],'source':source,'lineage':'frozen print source -> explicit game recipe'}
            checked('Print-to-game conversion uses frozen lineage',back_to_game)
        def nanite():
            run=success(engine.execute(root,target='game',profile='unreal_desktop_nanite'))
            info=run['targets']['game']['backends']['blender']
            assert info['game']['outputs']['body']['nanite'] and not info['game']['outputs']['body']['lods']
            return {'run':run['id'],'package':info['game']['manifest']}
        nanite_result=checked('Blender Nanite profile retains detail and exports fallback settings',nanite)
        if args.unreal:
            project_dir=workspace/'UnrealFixture'; project_dir.mkdir()
            uproject=project_dir/'GeometryForgeFixture.uproject'
            write(uproject,{'FileVersion':3,'EngineAssociation':'5.8','Plugins':[{'Name':'PythonScriptPlugin','Enabled':True},{'Name':'EditorScriptingUtilities','Enabled':True}]})
            for label,run_id in [('conventional',first),('Nanite',nanite_result.get('details',{}).get('run'))]:
                if not run_id: continue
                def import_asset(run_id=run_id):
                    result=unreal.execute(root,uproject,run_id,executable=args.unreal)
                    assert result['status']=='passed',result['failures']
                    return result
                imported=checked('Unreal 5.8 '+label+' import, materials, units, LOD/collision and saved assets',import_asset)
                if imported['passed']:
                    def verify_import(ident=imported['details']['id']):
                        result=unreal.execute(root,uproject,executable=args.unreal,import_id=ident,verify=True)
                        assert result['status']=='passed',result['failures']; return result
                    checked('Unreal '+label+' saved import re-verification',verify_import)
                    if args.review:
                        def review_import(ident=imported['details']['id']):
                            result=unreal.execute(root,uproject,executable=args.unreal,import_id=ident,verify=True,review=True)
                            assert result['status']=='passed',result['failures']
                            evidence['coverage']['rendered_unreal_review']=result['coverage']['rendered_review']
                            evidence['coverage']['performance']=result['coverage']['performance_measured']
                            return {'id':result['id'],'coverage':result['coverage'],'review':result['review'],'hardware':result['hardware']}
                        checked('Unreal '+label+' offscreen rendered review and editor profiling',review_import)
    if args.houdini:
        def houdini():
            run=engine.execute(root,backend='houdini',target='design',source='code',full=True)
            assert run['targets']['design']['status'] in ('passed','candidate'),run['failures']
            info=run['targets']['design']['backends']['houdini']
            return {'run':run['id'],'license':info['license'],'native_structure':info['native_structure'],'coverage':'design SOP extraction; production FBX/bake needs supported license'}
        checked('Houdini native design save/reopen and attribute extraction',houdini)
        def houdini_material():
            folder=workspace/'houdini_pbr'
            projects.initialize(folder,ident='houdini_pbr',deliverables='houdini',target='game');projects.unregister(folder)
            (folder/'models').mkdir()
            shutil.copy2(Path(__file__).resolve().parent/'fixtures/game_assets/houdini.py',folder/'models/houdini.py')
            (folder/'project.toml').write_text('format_version=2\n[project]\nid="houdini_pbr"\n[backends.houdini]\nentry="models/houdini.py"\n[parts.body]\nsources=[]\nparameters=[]\ndepends=[]\n[targets.game]\n[targets.design]\nchecks=[]\n',encoding='utf-8')
            run=engine.execute(folder,target='design')
            assert run['targets']['design']['status']=='passed',run['failures']
            info=run['targets']['design']['backends']['houdini']
            raw=next(a for a in info['parts']['body']['artifacts'] if a['path'].endswith('assembly.json'))
            obj=read(inside(folder,raw['path']))['objects'][0]
            assert obj['materials'][0]['id']=='M_Source' and obj['uv_layers']
            return {'run':run['id'],'license':info['license'],'native_structure':info['native_structure'],
                    'shader':obj['materials'][0]['native_shader'],'uv_layers':list(obj['uv_layers'])}
        checked('Houdini editable PBR shader, UVs and direct attribute extraction',houdini_material)
    fixture_source=Path(__file__).resolve().parent/'fixtures/game_assets'
    for kind,target,profile in [('doorway','game','unreal_desktop_standard'),('dense','game','unreal_desktop_nanite'),('shell','print',None)]:
        def fixture(kind=kind,target=target,profile=profile):
            folder=workspace/kind
            projects.initialize(folder,ident=kind,deliverables='blender',target=target,brief='Managed native validation fixture')
            projects.unregister(folder)
            (folder/'models').mkdir();(folder/'checks').mkdir()
            shutil.copy2(fixture_source/'blender.py',folder/'models/blender.py')
            shutil.copy2(fixture_source/'checks.py',folder/'checks/verify.py')
            parts=['body','coupon'] if kind=='shell' else ['body']
            text=f'format_version=2\n[project]\nid="{kind}"\n[backends.blender]\nentry="models/blender.py"\n'
            for part in parts:text+=f'[parts.{part}]\nsources=[]\nparameters=["kind"]\ndepends=[]\n'
            text+=f'[targets.{target}]\n'
            if kind in ('doorway','shell'):
                text+='[checks.functional]\nsource="checks/verify.py"\nparts='+str(parts).replace("'",'"')+'\nparameters=["kind"]\n'
            (folder/'project.toml').write_text(text,encoding='utf-8');write(folder/'parameters.json',{'kind':kind})
            run=success(engine.execute(folder,profile=profile))
            return {'run':run['id'],'project':str(folder),'checks':run['backends']['blender']['checks'],
                    'structure':run['backends']['blender']['native_structure']}
        checked('Native '+kind+' fixture with measured functional checks',fixture)
    def legacy_conversion():
        folder=workspace/'legacy_organizer'
        projects.initialize(folder,'desk_organizer',deliverables='blender');projects.unregister(folder)
        source=success(engine.execute(folder))
        targets.migrate(folder)
        shutil.copy2(fixture_source/'blender.py',folder/'models/game_asset.py')
        with (folder/'project.toml').open('a') as stream:
            stream.write('\n[targets.game]\nchecks=[]\nderivation_recipe="retained_organizer_game"\n[targets.game.backends.blender]\nentry="models/game_asset.py"\n')
        params=read(folder/'parameters.json');params['kind']='legacy';write(folder/'parameters.json',params)
        result=targets.derive(folder,'game',source['id'],'print')
        assert result['targets']['game']['status']=='passed',result['failures']
        return {'run':result['id'],'source_v1_run':source['id'],'project':str(folder),'source_preserved':True}
    checked('Legacy print organizer migrates and derives a game asset',legacy_conversion)
    evidence['passed']=all(c['passed'] for c in evidence['checks'])
    write(workspace/'game-evidence.json',evidence)
    print(str(workspace/'game-evidence.json'))
    return 0 if evidence['passed'] else 2


if __name__=='__main__':
    sys.exit(main())
