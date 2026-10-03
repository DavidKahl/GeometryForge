import json
from pathlib import Path
import pytest
from geometryforge import engine, projects, backends
from geometryforge.storage import read, write, digest, inside
from geometryforge.locking import exclusive

def test_incremental_reuses_unaffected_artifacts_and_checks(project):
    root,calls=project
    first=engine.execute(root)
    assert first['status']=='passed',first['failures']
    write(root/'parameters.json',{'width_a':12,'width_b':20})
    assert engine.context(root)['safe_point_label'].endswith('predates working edits')
    second=engine.execute(root)
    assert second['status']=='passed',second['failures']
    assert calls[-1]['parts']==['a']
    info=second['backends']['blender']
    assert info['parts']['b']['reused'] and not info['parts']['a']['reused']
    assert info['checks']['check_b']['reused']
    assert not info['checks']['check_a']['reused'] and not info['checks']['interface']['reused']
    assert info['parts']['b']['artifacts']==first['backends']['blender']['parts']['b']['artifacts']
    assert engine.context(root)['safe_point']==second['id']

def test_manual_scene_continuation_full_verification_and_restore(project):
    root,calls=project;first=engine.execute(root)
    state=projects.load(root)['state']['backends']['blender'];working=inside(root,state['working'])
    objects=read(working)
    for vertex in objects[0]['vertices']:vertex[0]*=1.1
    write(working,objects);edited_hash=digest(working)
    assert engine.context(root)['backends']['blender']['working_changed']
    second=engine.execute(root,source='scene',full=True)
    assert second['status']=='passed',second['failures']
    assert calls[-1]['parts']==[]
    assert digest(working)==edited_hash
    assert all(not c['reused'] for c in second['backends']['blender']['checks'].values())
    restored=engine.restore(root,first['id'])
    restored_root=Path(restored['working_copy'])
    assert (restored_root/'blender/model.blend').exists()
    assert (restored_root/'sources/parameters.json').exists()
    assert digest(working)==edited_hash

def test_conflicting_source_and_native_edits_need_choice(project):
    root,calls=project;first=engine.execute(root)
    working=inside(root,projects.load(root)['state']['backends']['blender']['working'])
    objects=read(working);objects[0]['vertices'][0][0]-=1;write(working,objects)
    write(root/'parameters.json',{'width_a':12,'width_b':20})
    before=len(calls);second=engine.execute(root)
    assert second['status']=='candidate' and len(calls)==before
    assert engine.context(root)['safe_point']==first['id']

def test_changed_checker_invalidates_cached_results(project):
    root,_=project;engine.execute(root)
    with (root/'checks/verify.py').open('a') as f:f.write('\n# changed checker implementation\n')
    result=engine.execute(root)
    assert result['status']=='passed'
    info=result['backends']['blender']
    assert all(v['reused'] for v in info['parts'].values())
    assert all(not v['reused'] for v in info['checks'].values())

def test_artifact_tamper_prevents_reuse(project):
    root,_=project;first=engine.execute(root)
    output=next(a for a in first['backends']['blender']['parts']['b']['artifacts'] if a['path'].endswith('.stl'))
    inside(root,output['path']).write_bytes(b'corrupt')
    second=engine.execute(root)
    assert second['status']=='passed'
    assert not second['backends']['blender']['parts']['b']['reused']

def test_unknown_scene_parts_preserve_safe_point(project):
    root,_=project;first=engine.execute(root)
    working=inside(root,projects.load(root)['state']['backends']['blender']['working'])
    objects=read(working);objects[0]['part']='unregistered';write(working,objects)
    second=engine.execute(root,source='scene')
    assert second['status']=='candidate'
    assert engine.context(root)['safe_point']==first['id']

def test_failure_and_cancellation_keep_safe_point(project,monkeypatch):
    root,_=project;first=engine.execute(root)
    for exc,status in [(RuntimeError('backend failure'),'failed'),(KeyboardInterrupt(),'cancelled')]:
        def fail(*a,**kw):raise exc
        monkeypatch.setattr(backends,'run_native',fail)
        result=engine.execute(root)
        assert result['status']==status
        assert engine.context(root)['safe_point']==first['id']

def test_lock_and_source_snapshot_integrity(project):
    root,_=project
    with exclusive(root/'.geometryforge'):
        with pytest.raises(RuntimeError,match='Another operation'):
            engine.execute(root)
    p=projects.load(root);expected=projects.inputs(p)
    (root/'models/a.py').write_text('changed')
    with pytest.raises(RuntimeError,match='snapshot'):
        engine.snapshot(p,root/'snapshot-test',expected)

def test_independent_backends_and_reconciliation(project):
    root,_=project;d=read(root/'decisions.json');d['deliverables']='both';write(root/'decisions.json',d)
    first=engine.execute(root);assert first['status']=='passed',first['failures']
    write(root/'parameters.json',{'width_a':12,'width_b':20})
    partial=engine.execute(root,backend='blender')
    assert partial['status']=='candidate'
    assert engine.context(root)['safe_point']==first['id']
    assert engine.context(root)['backends']['houdini']['stale']
    final=engine.execute(root)
    assert final['status']=='passed',final['failures']
    assert final['backends']['blender']['parts']['a']['reused']

def test_dependency_closure_handles_cycles():
    config={'parts':{'a':{'depends':['b']},'b':{'depends':['a']},'c':{'depends':[]}}}
    assert projects.closure(config,{'a'})=={'a','b'}

def test_corrupt_snapshot_is_not_restorable(project):
    root,_=project;r=engine.execute(root)
    (engine.run_path(projects.load(root),r['id'])/'inputs/parameters.json').write_text('{}')
    with pytest.raises(ValueError,match='snapshot'):
        engine.restore(root)
