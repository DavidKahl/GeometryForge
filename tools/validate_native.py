"""Real application acceptance checks. Run explicitly; writes only its workspace.

uv run python tools/validate_native.py --workspace validation-workspace
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geometryforge import engine, projects
from geometryforge.storage import read, write, digest, inside
from geometryforge.backends import run_native

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',default='validation-workspace');args=parser.parse_args()
    workspace=Path(args.workspace).resolve();workspace.mkdir(exist_ok=True)
    report={'platform':sys.platform,'checks':[]}
    def checked(label, operation):
        start=time.monotonic();result=operation();report['checks'].append({'name':label,'passed':True,'seconds':round(time.monotonic()-start,2),'details':result});write(workspace/'native-evidence.json',report)
    def success(result):
        assert result['status']=='passed',result['failures']
        return result
    # The rocket is a multipart regression fixture only; it is not a shipped example or a viewer project.
    fixtures={'desk_organizer':projects.PACKAGE/'examples'/'desk_organizer','falcon9':Path(__file__).resolve().parent/'fixtures'/'falcon9'}
    for name,example in [('organizer','desk_organizer'),('rocket','falcon9')]:
        root=workspace/name;source=fixtures[example]
        if not root.exists():
            projects.initialize(root,example if example=='desk_organizer' else None,ident=name)
            if example=='falcon9':projects.unregister(root)
        # Update test fixture code without touching the user's working scenes.
        for sub in ('models','checks'):
            shutil.copytree(source/sub,root/sub,dirs_exist_ok=True)
        shutil.copy2(source/'project.toml',root/'project.toml')
        shutil.copy2(source/'parameters.json',root/'parameters.json')
        decisions=read(root/'decisions.json');decisions['deliverables']='both';write(root/'decisions.json',decisions)
        # Explicit code source is appropriate for this disposable fixture reset.
        def build(root=root):
            result=success(engine.execute(root,full=True,source='code',parts=list(projects.load(root)['config']['parts'])))
            return {'run':result['id'],'backends':{b:{'version':v['version'],'license':v['license'],'structure':v['native_structure']} for b,v in result['backends'].items()}}
        checked(name+' native build/reopen/print checks',build)
    root=workspace/'rocket'
    baseline=engine.record(projects.load(root),projects.load(root)['state']['safe_point'])
    params=read(root/'parameters.json');params['fairing_height']+=5;write(root/'parameters.json',params)
    def incremental():
        result=success(engine.execute(root))
        for backend,info in result['backends'].items():
            assert info['rebuilt_parts']==['fairing'],info['rebuilt_parts']
            assert info['changed_parts']==['fairing'],info['changed_parts']
            assert [p for p,v in info['parts'].items() if not v['reused']]==['fairing']
            assert [c for c,v in info['checks'].items() if not v['reused']]==['upper_joint']
        return {'run':result['id'],'rebuilt':['fairing'],'fresh_checks':['upper_joint'],'reused_parts':5,'reused_checks':3}
    checked('fairing-only incremental update in both applications',incremental)
    params['clearance']=.3;write(root/'parameters.json',params)
    def shared_interface():
        result=success(engine.execute(root))
        for info in result['backends'].values():
            assert set(info['rebuilt_parts'])=={'stage1','stage2','fairing','stand','coupon'}
            assert all(not c['reused'] for c in info['checks'].values())
            assert info['parts']['legs']['reused']
        return {'run':result['id'],'fresh_checks':4,'legs_reused':True}
    checked('shared clearance invalidates both joint sides',shared_interface)
    safe=projects.load(root)['state']['safe_point']
    safe_record=engine.record(projects.load(root),safe)
    for backend in ('blender','houdini'):
        def manual(backend=backend):
            p=projects.load(root);state=p['state']['backends'][backend];original=inside(root,state['working']);sha=digest(original)
            directory=workspace/('manual-'+backend);directory.mkdir(exist_ok=True)
            entry=directory/'edit.py'
            if backend=='blender':
                text="import bpy\ndef build_parts(p,parts,api):\n    for o in bpy.data.objects:\n        if o.get('gf_owner')=='legs': o.location.x += 1.5\n"
            else:
                text="import hou\ndef build_parts(p,parts,api):\n    for n in hou.node('/obj/geometryforge').children():\n        if n.userData('gf_owner')=='legs':\n            parm=n.node('placement').parm('tx');parm.set(parm.eval()+1.5)\n"
            entry.write_text(text)
            native=run_native(backend,directory,entry,params,['legs'],original,900)
            assert digest(original)==sha
            edited=Path(native['scene']);edited_sha=digest(edited)
            engine.adopt(root,backend,edited)
            ctx=engine.context(root)
            assert ctx['backends'][backend]['working_changed']
            assert ctx['safe_point']==safe
            result=engine.execute(root,backend=backend,source='scene',full=True)
            assert result['status']=='candidate',result['failures']
            info=result['backends'][backend]
            assert not info['rebuilt_parts']
            assert info['changed_parts']==['legs']
            assert all(not c['reused'] for c in info['checks'].values())
            assert digest(edited)==edited_sha and digest(original)==sha
            restored=engine.restore(root,safe)
            assert Path(restored['working_copy']).exists()
            # Re-select the retained safe scene for subsequent independent tests.
            engine.adopt(root,backend,inside(root,safe_record['backends'][backend]['native']['path']))
            return {'run':result['id'],'source_preserved':True,'builders_invoked':0,'changed_parts':['legs'],'full_checks_executed':4,'restore':True}
        checked(backend+' saved manual edit, full verification, safe-point restore',manual)
    checked('return to matching native safe scenes',lambda:{'run':success(engine.execute(root,source='scene'))['id']})
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
