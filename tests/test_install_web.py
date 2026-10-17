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


def test_viewer_mesh_packs_corner_and_indexed_objects():
    import numpy as np
    from geometryforge.viewer_mesh import pack_objects, unpack
    vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]]
    faces = [[0, 1, 2], [1, 3, 2]]
    normals = [[[0, 0, 1]] * 3, [[0, 0, -1]] * 3]
    design = {'role': 'design', 'vertices': vertices, 'faces': faces, 'corner_normals': normals, 'face_materials': [1, 0],
              'uv_layers': {'UVMap': [[[0, 0], [1, 0], [0, 1]], [[1, 0], [1, 1], [0, 1]]]}, 'materials': [{'id': 'A'}, {'id': 'B'}],
              'matrix_world': np.eye(4).tolist(), 'metadata': {'lod': 0, 'feature': 'plate'}}
    printable = {'vertices': vertices, 'faces': faces, 'filament': 2}
    (entry, arrays), (plain, plain_arrays) = unpack(pack_objects([design, printable]))
    # Corner-expanded and ordered by face material: material 0 (the second face) first, as the viewer draws groups.
    np.testing.assert_allclose(arrays['position'].reshape(-1, 3, 3)[0], np.asarray(vertices)[faces[1]])
    np.testing.assert_allclose(arrays['normal'].reshape(-1, 3, 3)[0], normals[1])
    np.testing.assert_allclose(arrays['uv'].reshape(-1, 3, 2)[1], [[0, 0], [1, 0], [0, 1]])
    assert entry['groups'] == [[0, 3, 0], [3, 3, 1]] and entry['materials'] == ['A', 'B'] and entry['metadata'] == {'lod': 0}
    assert 'index' not in arrays and plain['filament'] == 2
    np.testing.assert_array_equal(plain_arrays['index'], np.ravel(faces))
    np.testing.assert_allclose(plain_arrays['position'], np.ravel(vertices))


def test_mesh_endpoint_serves_only_run_evidence(project):
    from geometryforge.viewer_mesh import unpack
    root, _ = project
    result = engine.execute(root)
    key = projects.register(root)['key']
    client = TestClient(create_app())
    assembly = next(a['path'] for part in result['backends']['blender']['parts'].values() for a in part['artifacts'] if a['path'].endswith('assembly.json'))
    served = client.get(f'/api/projects/{key}/mesh', params={'path': assembly})
    assert served.status_code == 200 and served.headers['content-type'] == 'application/octet-stream'
    assert len(unpack(served.content)) >= 1
    assert list((root / '.geometryforge/cache/viewer').glob('*.gfm'))
    assert client.get(f'/api/projects/{key}/mesh', params={'path': assembly}).content == served.content   # cached
    assert client.get(f'/api/projects/{key}/mesh', params={'path': 'decisions.json'}).status_code == 404
    assert client.get(f'/api/projects/{key}/mesh', params={'path': '../secret.txt'}).status_code == 400
