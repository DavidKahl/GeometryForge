import pytest
from geometryforge import engine, projects
from geometryforge.storage import read, write, inside

def test_after_adopting_native_edit_later_parameters_do_not_discard_it(project):
    root,calls=project;engine.execute(root)
    working=inside(root,projects.load(root)['state']['backends']['blender']['working'])
    objects=read(working)
    for vertex in objects[0]['vertices']:vertex[0]+=1
    write(working,objects)
    assert engine.execute(root,source='scene')['status']=='passed'
    write(root/'parameters.json',{'width_a':14,'width_b':20})
    previous=len(calls)
    candidate=engine.execute(root)
    assert candidate['status']=='candidate'
    assert len(calls)==previous

def test_unknown_part_and_invalid_print_constraints_rejected(project):
    root,_=project
    with pytest.raises(ValueError,match='Unknown selected part'):
        engine.plan(root,parts=['missing'])
    decision=read(root/'decisions.json');decision['print']['bed_mm']=[-1,220];write(root/'decisions.json',decision)
    with pytest.raises(ValueError,match='positive finite'):
        projects.load(root)

def test_verification_does_not_turn_generated_sources_into_manual_edits(project):
    root,calls=project;engine.execute(root)
    verified=engine.execute(root,source='scene',full=True)
    assert verified['status']=='passed'
    assert verified['backends']['blender']['native_edits']==[]
    write(root/'parameters.json',{'width_a':14,'width_b':20})
    changed=engine.execute(root)
    assert changed['status']=='passed'
    assert calls[-1]['parts']==['a']

def test_editing_independent_part_preserves_prior_native_edit(project):
    root,calls=project;engine.execute(root)
    working=inside(root,projects.load(root)['state']['backends']['blender']['working'])
    objects=read(working)
    for vertex in objects[0]['vertices']:vertex[0]+=1
    write(working,objects)
    engine.execute(root,source='scene')
    write(root/'parameters.json',{'width_a':10,'width_b':22})
    changed=engine.execute(root)
    assert changed['status']=='passed',changed['failures']
    assert calls[-1]['parts']==['b']
    assert changed['backends']['blender']['native_edits']==['a']

def test_parity_candidate_keeps_previous_safe_point(project):
    root,_=project
    decision=read(root/'decisions.json');decision['deliverables']='both';write(root/'decisions.json',decision)
    original=engine.execute(root)
    working=inside(root,projects.load(root)['state']['backends']['blender']['working'])
    objects=read(working)
    for vertex in objects[0]['vertices']:vertex[0]*=1.2
    write(working,objects)
    candidate=engine.execute(root,source='scene')
    assert candidate['status']=='candidate'
    ctx=engine.context(root)
    assert ctx['safe_point']==original['id']
    assert ctx['safe_point_label'].endswith('predates working edits')
