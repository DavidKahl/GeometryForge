"""Serve the viewer over a throwaway catalog of generated projects for the browser tests.

Blender and Houdini are replaced by a stand-in that emits simple boxes, so the tests run anywhere
(including CI) while still exercising the real engine: runs, checks, exports, previews and whole-model 3MFs.

Usage: python ui/tests/fixture_server.py [--port 8744]
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

HOME = Path(tempfile.mkdtemp(prefix="geometryforge-browser-"))
os.environ["GEOMETRYFORGE_HOME"] = str(HOME / "catalog")  # must be set before geometryforge is imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import trimesh  # noqa: E402
import numpy as np
from PIL import Image
from geometryforge import backends, engine, projects  # noqa: E402
from geometryforge.storage import read, write, digest  # noqa: E402

CHECKER = '''def verify(payload):
    if payload["parameters"].get("break_check"):
        return {"passed": False, "error": "break_check is set"}
    return {"passed": True, "parts": sorted(payload["objects"])}
'''

# name: (size xyz mm, centre xyz mm, filament slot)
LANDER = {"hull": ([40, 40, 120], [0, 0, 60], 1), "cap": ([30, 30, 30], [0, 0, 135], 2),
          **{f"fin_{i}": ([4, 30, 40], [(-1) ** i * 28 if i < 3 else 0, 0 if i < 3 else (-1) ** i * 28, 20], 2) for i in range(1, 5)}}


def fake_native(backend, out, entry, parameters, parts, source, timeout, executable):
    """Stand-in for a Blender/Houdini worker: one box per declared part, sized from the fixture table."""
    shapes = read(Path(entry).parent / "shapes.json")
    objects = []
    for name, (size, centre, slot) in shapes.items():
        mesh = trimesh.creation.box(size)
        mesh.apply_translation(centre)
        objects.append(dict(name=name, part=name, vertices=mesh.vertices.tolist(), faces=mesh.faces.tolist(),
                            filament=slot, print_rotation_deg=[0, 0, 0], expected_bodies=1))
    exports = {}
    if backends.native_context.get().get('target') == 'game':
        game_objects=[]
        for obj in objects:
            faces=np.asarray(obj['faces']); vertices=np.asarray(obj['vertices'])
            edges=vertices[faces][:,1:]-vertices[faces][:,0,None]
            normals=np.cross(edges[:,0],edges[:,1]); normals/=np.linalg.norm(normals,axis=1)[:,None]
            tangent=edges[:,0]/np.linalg.norm(edges[:,0],axis=1)[:,None]
            item={**obj,'role':'render','matrix_world':np.eye(4).tolist(),
                  'uv_layers':{'UVMap':[[[0,0],[1,0],[0,1]]]*len(faces)},
                  'corner_normals':[[n.tolist()]*3 for n in normals],'corner_tangents':[[[*t,1]]*3 for t in tangent],
                  'face_materials':[0]*len(faces),'metadata':{'uv_mode':'tiled','source_parts':[obj['part']],
                      'sockets':[{'name':'Top','position_mm':[0,0,20]}]},
                  'materials':[{'id':'M_Fixture','base_color':[1,1,1,1],'roughness':.5,'metallic':.2,
                                'textures':{'base_color':{'path':str(Path(entry).parent/'texture.png'),'color_space':'sRGB'}}}]}
            game_objects.append(item)
            for level in range(1,4):
                game_objects.append({**item,'name':item['name']+f'_LOD{level}','role':'lod','metadata':{'lod':level,'uv_mode':'tiled'}})
            game_objects.append({**obj,'role':'collision','matrix_world':np.eye(4).tolist(),'metadata':{},'materials':[]})
            file=out/(obj['part']+'.fbx');file.write_bytes(b'browser-test FBX stand-in')
            lods={}
            for level in range(1,4):
                lod_file=out/(obj['part']+f'_LOD{level}.fbx');lod_file.write_bytes(b'browser-test LOD stand-in');lods[str(level)]=str(lod_file)
            exports[obj['part']]={'path':str(file),'sha256':digest(file),'lods':lods,'roundtrip':{'passed':True}}
        objects=game_objects
    scene = out / ("model.blend" if backend == "blender" else "model.hipnc")
    write(scene, objects)
    return {"version": f"fixture-{backend}", "scene": str(scene), "objects": objects,'mesh_exports':exports}


def project(root, title, shapes, checks, parameters, filaments=None):
    toml = [f'format_version = 1\n[project]\nid = "{root.name}"\ntitle = "{title}"',
            '[backends.blender]\nentry = "models/entry.py"', '[backends.houdini]\nentry = "models/entry.py"']
    toml += [f'[parts.{name}]\nsources = ["models/shapes.json"]\nparameters = []\ndepends = []' for name in shapes]
    toml += [f'[checks.{name}]\nsource = "checks/verify.py"\nparts = {parts!r}\nparameters = ["break_check"]'.replace("'", '"')
             for name, parts in checks.items()]
    (root / "project.toml").write_text("\n".join(toml) + "\n", encoding="utf-8")
    write(root / "models/shapes.json", shapes)
    write(root / "parameters.json", parameters)
    decisions = read(root / "decisions.json")
    if filaments:
        decisions["print"]["filaments"] = filaments
    write(root / "decisions.json", decisions)


def seed():
    backends.run_native = fake_native
    lander = HOME / "fixture_lander"
    projects.initialize(lander, ident="fixture_lander", deliverables="both", brief="Browser test lander", bed=(256, 256, 250))
    (lander / "models").mkdir()
    (lander / "checks").mkdir()
    (lander / "models/entry.py").write_text("# stand-in entry; see fixture_server.py\n", encoding="utf-8")
    (lander / "checks/verify.py").write_text(CHECKER, encoding="utf-8")
    plan = [{"slot": 1, "name": "Silver", "colour": "#BFCAD1", "material": "PLA"}, {"slot": 2, "name": "Dark", "colour": "#2C3842", "material": "PLA"}]
    fins = {k: v for k, v in LANDER.items() if k.startswith("fin_")}
    # 1: an early attempt with only the fins; 2: the full model (safe point); 3: a failed check.
    project(lander, "Fixture Lander", fins, {"fin_roots": list(fins)}, {"break_check": False}, plan)
    assert engine.execute(lander)["status"] == "passed"
    project(lander, "Fixture Lander", LANDER, {"fin_roots": list(fins), "body_joints": ["hull", "cap"]}, {"break_check": False}, plan)
    assert engine.execute(lander)["status"] == "passed"
    write(lander / "parameters.json", {"break_check": True})
    assert engine.execute(lander)["status"] == "failed"
    write(lander / "parameters.json", {"break_check": False})
    projects.register(lander, "Fixture Lander")

    box = HOME / "fixture_box"
    projects.initialize(box, ident="fixture_box", deliverables="blender", brief="Browser test box")
    (box / "models").mkdir()
    (box / "checks").mkdir()
    (box / "models/entry.py").write_text("# stand-in entry\n", encoding="utf-8")
    (box / "checks/verify.py").write_text(CHECKER, encoding="utf-8")
    project(box, "Fixture Box", {"tray": ([80, 60, 20], [0, 0, 10], 1)}, {"cavities": ["tray"]}, {"break_check": False})
    assert engine.execute(box)["status"] == "passed"
    projects.register(box, "Fixture Box")

    game_root=HOME/'fixture_game'
    projects.initialize(game_root,ident='fixture_game',deliverables='blender',brief='Game and print browser fixture')
    (game_root/'models').mkdir();(game_root/'checks').mkdir()
    (game_root/'models/entry.py').write_text('# browser stand-in')
    (game_root/'checks/verify.py').write_text(CHECKER)
    project(game_root,'Fixture Game',{'housing':([80,50,40],[0,0,20],1)},{'dimensions':['housing']},{'break_check':False})
    from geometryforge.targets import migrate
    migrate(game_root)
    with (game_root/'project.toml').open('a') as stream:
        stream.write('\n[targets.game]\nchecks=[]\nsources=["models/texture.png"]\n')
    Image.new('RGB',(8,8),'#5599bb').save(game_root/'models/texture.png')
    d=read(game_root/'decisions.json');d['output_targets']=['game','print'];write(game_root/'decisions.json',d)
    result=engine.execute(game_root);assert result['status']=='passed',result['failures']
    projects.register(game_root,'Fixture Game')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8744)
    args = parser.parse_args()
    seed()
    from geometryforge.web import serve
    serve(args.port)
