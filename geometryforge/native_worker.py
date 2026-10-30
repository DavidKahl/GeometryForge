"""Native workers. Loaded in Blender Python or Houdini's owned GUI session."""
import importlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys

# Load only this package. In a wheel its parent is host site-packages, whose
# compiled dependencies may target a different Python ABI from Blender/Houdini.
if 'geometryforge' not in sys.modules:
    package_dir=Path(__file__).resolve().parent
    package_spec=importlib.util.spec_from_file_location('geometryforge',package_dir/'__init__.py',submodule_search_locations=[str(package_dir)])
    package_module=importlib.util.module_from_spec(package_spec)
    sys.modules['geometryforge']=package_module
    package_spec.loader.exec_module(package_module)

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


def preparation(request, api):
    """Explicit stage recipes only; verify never executes preparation builders."""
    for name, stage in request.get('stages', {}).items():
        if stage.get('run'):
            stage_request = {**request, 'entry': str(Path(request['snapshot_root']) / stage['entry']), 'parts': stage['parts']}
            recipe(stage_request, api)

def blender_prepare(request):
    import bpy
    from geometryforge import native_api
    from geometryforge.blender_scene import initialize
    if request.get("source"):
        bpy.ops.wm.open_mainfile(filepath=request["source"])
    else:
        initialize()
    return native_api.Blender(request)

def blender_execute(request):
    api = blender_prepare(request)
    if request["parts"]:
        recipe(request, api)
    preparation(request, api)
    blender_finalize(request)

def blender_finalize(request):
    """Collect, save, reopen-compare and export; shared by headless and live runs."""
    import bpy
    from geometryforge.blender_worker import meshes
    target = request.get('target', 'print')
    if target != 'print':
        from geometryforge.blender_game import meshes, relocate_textures
        relocate_textures(Path(request['out']) / 'native-textures')
        objects = meshes(target)
    else:
        objects = meshes()
    out = Path(request["out"])
    scene = out / "model.blend"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(scene),relative_remap=False)
    # Reopen the actual delivered scene to verify persistence of native structures.
    bpy.ops.wm.open_mainfile(filepath=str(scene))
    reopened = meshes(target) if target != 'print' else meshes()
    from geometryforge.engine import geometry_hash
    from geometryforge.storage import fingerprint
    hash_geometry = fingerprint if target != 'print' else geometry_hash
    from geometryforge.blender_game import equivalent
    matches = equivalent(reopened, objects) if target != 'print' else hash_geometry(reopened) == hash_geometry(objects)
    if not matches:
        (out / 'before-reopen.json').write_text(json.dumps(objects), encoding='utf-8')
        (out / 'after-reopen.json').write_text(json.dumps(reopened), encoding='utf-8')
        raise ValueError('Native geometry changed after reopening the saved Blender file')
    result = {"version": bpy.app.version_string, "scene": str(scene), "objects": objects,
              "native_objects": len(bpy.data.objects), "modifiers": sum(len(o.modifiers) for o in bpy.data.objects)}
    if target != 'print':
        result['objects'] = reopened
    if target == 'game':
        from geometryforge.blender_game import export_fbx
        result['mesh_exports'] = export_fbx(reopened, out / 'native-fbx',request.get('previous_mesh_exports'),request.get('full',False))
    if request.get('live') is not None:
        result['mode'] = 'live'
    (out / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return result

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
        recipe(request, native_api.Houdini(request))
    preparation(request, native_api.Houdini(request))
    if cancelled():
        raise RuntimeError('Cancelled')
    out = Path(request['out'])
    scene = out / ('model' + scene_suffix())
    hou.hipFile.save(str(scene))
    hou.hipFile.load(str(scene), suppress_save_prompt=True, ignore_load_warnings=True)
    if request.get('target', 'print') != 'print':
        from geometryforge.houdini_game import extract, export_fbx
        objects = extract(request.get('target', 'game'))
        result = {**{'version': hou.applicationVersionString(), 'license': str(hou.licenseCategory()), 'scene': str(scene)},
                  'objects': objects, 'native_nodes': len(hou.node('/obj/geometryforge').allSubChildren())}
        if request['target'] == 'game':
            result['mesh_exports'] = export_fbx(objects, out / 'native-fbx')
        (out / 'result.json').write_text(json.dumps(result), encoding='utf-8')
        return {'scene': str(scene), 'version': result['version'], 'license': result['license']}
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
