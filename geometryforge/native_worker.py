"""Native workers. Loaded in Blender Python or Houdini's owned GUI session."""
import importlib
import json
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def recipe(request, api):
    entry = Path(request["entry"])
    old_path, old_modules = sys.path[:], dict(sys.modules)
    sys.path.insert(0, str(entry.parent))
    try:
        namespace = runpy.run_path(str(entry))
        namespace["build_parts"](request["parameters"], request["parts"], api)
    finally:
        sys.path[:] = old_path
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None)
            if file and Path(file).resolve().is_relative_to(entry.parent.resolve()):
                if name in old_modules:
                    sys.modules[name] = old_modules[name]
                else:
                    del sys.modules[name]

def blender_execute(request):
    import bpy
    from geometryforge import native_api
    from geometryforge.blender_worker import meshes
    from geometryforge.blender_scene import initialize
    if request.get("source"):
        bpy.ops.wm.open_mainfile(filepath=request["source"])
    else:
        initialize()
    api = native_api.Blender()
    if request["parts"]:
        recipe(request, api)
    objects = meshes()
    out = Path(request["out"])
    scene = out / "model.blend"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(scene))
    # Reopen the actual delivered scene to verify persistence of native structures.
    bpy.ops.wm.open_mainfile(filepath=str(scene))
    reopened = meshes()
    from geometryforge.engine import geometry_hash
    if geometry_hash(reopened) != geometry_hash(objects):
        raise ValueError('Native geometry changed after reopening the saved Blender file')
    result = {"version": bpy.app.version_string, "scene": str(scene), "objects": objects,
              "native_objects": len(bpy.data.objects), "modifiers": sum(len(o.modifiers) for o in bpy.data.objects)}
    (out / "result.json").write_text(json.dumps(result), encoding="utf-8")

def houdini_execute(request, cancelled):
    import hou
    from geometryforge import native_api, houdini_scene
    importlib.reload(native_api)
    importlib.reload(houdini_scene)
    from geometryforge.houdini_worker import recover, scene_suffix, export_geometry
    recover()
    hou.hipFile.clear(suppress_save_prompt=True)
    if request.get("source"):
        hou.hipFile.load(request["source"], suppress_save_prompt=True, ignore_load_warnings=True)
        houdini_scene.ROOT = hou.node('/obj/geometryforge')
        if houdini_scene.ROOT is None or houdini_scene.ROOT.userData('geometryforge_units') != 'mm':
            raise ValueError('Missing GeometryForge millimeter root')
    else:
        houdini_scene.initialize()
    houdini_scene.PARTS.clear()
    if request["parts"]:
        recipe(request, native_api.Houdini())
    if cancelled():
        raise RuntimeError('Cancelled')
    out = Path(request['out'])
    scene = out / ('model' + scene_suffix())
    hou.hipFile.save(str(scene))
    hou.hipFile.load(str(scene), suppress_save_prompt=True, ignore_load_warnings=True)
    export_geometry(out, cancelled)
    inventory = json.loads((out / 'houdini_geometry.json').read_text())
    # Read supported OBJ interchange in the host, avoiding host hou/bpy dependencies.
    for item in inventory['objects']:
        vertices, faces = [], []
        for line in (out / item['obj']).read_text().splitlines():
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'v':
                vertices.append([float(x) for x in fields[1:4]])
            elif fields[0] == 'f':
                polygon = [int(x.split('/')[0]) for x in fields[1:]]
                polygon = [i-1 if i>0 else len(vertices)+i for i in polygon]
                faces.extend([[polygon[0], polygon[i], polygon[i+1]] for i in range(1,len(polygon)-1)])
        item.update(vertices=vertices, faces=faces)
    result = {"version": hou.applicationVersionString(), "license": str(hou.licenseCategory()), "scene": str(scene),
              "objects": [o for o in inventory['objects'] if o['role']=='Printable'],
              "native_nodes": len(hou.node('/obj/geometryforge').allSubChildren())}
    (out/'result.json').write_text(json.dumps(result), encoding='utf-8')
    return {"scene": str(scene), "version": result['version'], "license": result['license']}

if __name__ == "__main__":
    request = json.loads(Path(sys.argv[sys.argv.index("--")+1]).read_text(encoding="utf-8"))
    blender_execute(request)
