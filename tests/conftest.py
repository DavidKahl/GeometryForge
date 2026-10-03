import json
from pathlib import Path
import pytest
import trimesh
from geometryforge import projects, backends
from geometryforge.storage import read, write

@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(projects,'HOME',tmp_path/'catalog')
    root=tmp_path/'project'
    projects.initialize(root,ident='fixture',deliverables='blender',brief='Two independent blocks')
    (root/'models').mkdir();(root/'checks').mkdir()
    (root/'models/entry.py').write_text('# native entry')
    for name in ['a','b']:
        (root/f'models/{name}.py').write_text('# independent recipe')
    (root/'checks/verify.py').write_text('def verify(payload):\n    assert payload["objects"]\n    return {"passed": True, "measured_parts": sorted(payload["objects"])}\n')
    (root/'project.toml').write_text('''format_version = 1
[project]
id = "fixture"
[backends.blender]
entry = "models/entry.py"
[backends.houdini]
entry = "models/entry.py"
[parts.a]
sources = ["models/a.py"]
parameters = ["width_a"]
depends = []
[parts.b]
sources = ["models/b.py"]
parameters = ["width_b"]
depends = []
[checks.check_a]
source = "checks/verify.py"
parts = ["a"]
parameters = ["width_a"]
[checks.check_b]
source = "checks/verify.py"
parts = ["b"]
parameters = ["width_b"]
[checks.interface]
source = "checks/verify.py"
parts = ["a", "b"]
parameters = []
''')
    write(root/'parameters.json',{'width_a':10,'width_b':20})
    calls=[]
    def native(backend,out,entry,parameters,parts,source,timeout,executable):
        calls.append({'backend':backend,'parts':list(parts),'source':str(source) if source else None})
        objects=read(source,[]) if source else []
        for name in parts:
            objects=[o for o in objects if o['part']!=name]
            mesh=trimesh.creation.box([parameters['width_'+name],10,10])
            mesh.apply_translation([0 if name=='a' else 30,0,5])
            objects.append(dict(name=name,part=name,vertices=mesh.vertices.tolist(),faces=mesh.faces.tolist(),filament=1,print_rotation_deg=[0,0,0],expected_bodies=1))
        scene=out/('model.blend' if backend=='blender' else 'model.hipnc')
        write(scene,objects)
        return {'version':'test-native-1','scene':str(scene),'objects':objects}
    monkeypatch.setattr(backends,'run_native',native)
    return root,calls
