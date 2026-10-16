from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from geometryforge.install import install
from geometryforge import projects, engine
from geometryforge.web import create_app

def test_skill_installs_both_harnesses_without_overwriting_instructions(tmp_path):
    (tmp_path/'AGENTS.md').write_text('existing rules')
    (tmp_path/'CLAUDE.md').write_text('existing Claude rules')
    result=install(tmp_path)
    assert len(result['installed'])==2
    assert (tmp_path/'AGENTS.md').read_text()=='existing rules'
    assert (tmp_path/'CLAUDE.md').read_text()=='existing Claude rules'
    for prefix in ['.agents','.claude']:
        assert (tmp_path/prefix/'skills/geometryforge/SKILL.md').is_file()
    install(tmp_path)  # idempotent
    changed=tmp_path/'.claude/skills/geometryforge/references/blender.md'
    changed.write_text('user additions')
    with pytest.raises(ValueError,match='modified'):
        install(tmp_path)
    assert changed.read_text()=='user additions'

def test_viewer_catalog_security_and_artifacts(project):
    root,_=project;result=engine.execute(root)
    key=projects.register(root)['key']
    client=TestClient(create_app())
    assert client.get('/').status_code==200
    assert client.get('/api/projects',headers={'host':'attacker.example'}).status_code==403
    assert client.patch('/api/projects/'+key,json={'title':'bad'}).status_code==403
    token=client.get('/api/session').json()['token'];headers={'x-geometryforge-token':token}
    assert client.patch('/api/projects/'+key,headers={**headers,'origin':'https://evil.example'},json={'title':'bad'}).status_code==403
    assert client.patch('/api/projects/'+key,headers=headers,json={'title':'Renamed','archived':True}).status_code==200
    assert client.get('/api/projects').json()[key]['archived']
    assert client.get(f'/api/projects/{key}/context').json()['safe_point']==result['id']
    runs=client.get(f'/api/projects/{key}/runs').json();assert runs[0]['status']=='passed'
    native=result['backends']['blender']['native']['path']
    served=client.get(f'/api/projects/{key}/artifact',params={'path':native})
    assert served.status_code==200 and served.headers['content-disposition'].startswith('attachment')
    inline=client.get(f'/api/projects/{key}/artifact',params={'path':native,'inline':1})
    assert inline.status_code==200 and inline.headers['content-disposition'].startswith('inline')
    assert client.get(f'/api/projects/{key}/artifact',params={'path':'decisions.json','inline':1}).status_code==404
    assert client.get(f'/api/projects/{key}/artifact',params={'path':'decisions.json'}).status_code==404
    assert client.get(f'/api/projects/{key}/artifact',params={'path':'../secret.txt'}).status_code==400
    assert client.post('/api/projects',headers=headers,json={'path':str(root.parent/'empty'),'create':True,'id':'empty'}).status_code==200
    assert client.post('/api/run',headers=headers,json={}).status_code in (404,405)


def test_references_endpoint_lists_views_and_serves_only_reference_images(project):
    from PIL import Image
    from geometryforge.storage import read, write
    root, _ = project
    (root / 'references/clean').mkdir(parents=True)
    for name in ('right', 'top'):
        Image.new('RGB', (40, 40), 'grey').save(root / f'references/clean/{name}.png')
    Image.new('RGB', (40, 30), 'orange').save(root / 'references/concept.png')
    write(root / 'references/clean_set.json', {'version': 1, 'views': {'right': 'references/clean/right.png', 'top': 'references/clean/top.png'}})
    write(root / 'references/cameras.json', {'version': 1, 'cameras': {'right': {'image': 'references/clean/right.png', 'view': 'right',
        'position_mm': [0, -20000, 0], 'target_mm': [0, 0, 0], 'up': [0, 0, 1], 'ortho_scale_mm': 4000, 'resolution': [40, 40]}}})
    decisions = read(root / 'decisions.json')
    decisions['reference_review'] = {'references': [{'path': 'references/concept.png', 'view': 'identity'}, {'path': 'references/missing.png'}]}
    write(root / 'decisions.json', decisions)
    key = projects.register(root)['key']
    client = TestClient(create_app())
    listed = client.get(f'/api/projects/{key}/references').json()
    assert [(r['view'], r['kind'], r['camera']) for r in listed] == [('right', 'clean', 'right'), ('top', 'clean', None), ('identity', 'identity', None)]
    assert listed[0]['calibration']['ortho_scale_mm'] == 4000
    served = client.get(f'/api/projects/{key}/artifact', params={'path': 'references/clean/right.png', 'inline': 1})
    assert served.status_code == 200 and served.headers['content-disposition'].startswith('inline')
    assert client.get(f'/api/projects/{key}/artifact', params={'path': 'references/cameras.json'}).status_code == 404
    assert client.get(f'/api/projects/{key}/artifact', params={'path': 'references/../decisions.json'}).status_code == 404
