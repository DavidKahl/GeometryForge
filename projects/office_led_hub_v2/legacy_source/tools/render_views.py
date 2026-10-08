"""Render assembly views with Blender; never overwrite the source scene.

blender --background --python render_views.py -- --blend <model.blend> --out <previews>
"""
import argparse
from pathlib import Path
import sys
import math
import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blend', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'models'))
    from geometry import material
    scene = bpy.context.scene
    # Freeze evaluated geometry in this disposable render session before moving
    # parts: their retained Boolean tools stay in assembly coordinates.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    snapshots = [(obj, bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph)))
                 for obj in bpy.data.collections['Printable'].objects if obj.type == 'MESH']
    for obj, mesh in snapshots:
        obj.modifiers.clear()
        obj.data = mesh
    scene.cycles.samples = 48
    camera = scene.camera
    def view(name, target=(0, 0, 25), position=(235, -310, 500), scale=340):
        camera.location = position
        camera.rotation_euler = (Vector(target)-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(out / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    view('01_flux_assembled')
    bpy.data.objects['insert_flux'].hide_render = True
    bpy.data.objects['flux_Y_inlay'].hide_render = True
    plain = bpy.data.objects['insert_plain']
    plain.location.x -= 260
    plain.hide_render = False
    view('02_reactor_assembled')
    plain.hide_render = True
    cover_parts = [bpy.data.objects[name] for name in ('reactor_cover', 'insert_flux', 'flux_Y_inlay')]
    cover_parts += [bpy.data.objects[f'reactor_ring_{i}'] for i in range(1, 4)]
    cover_parts += [bpy.data.objects[f'reactor_armor_{i}'] for i in range(1, 5)]
    for obj in cover_parts:
        obj.hide_render = True
    equipment = []
    gray = material('PSU aluminum proxy', (0.18, 0.21, 0.24), 0.4)
    white = material('Controller proxy', (0.75, 0.77, 0.79))
    orange = material('Connector proxy', (0.95, 0.29, 0.055))
    for name in ('PSU_envelope', 'controller_envelope', *[f'wago_envelope_{i}' for i in range(1, 7)]):
        obj = bpy.data.objects[name]
        obj.hide_set(False)
        obj.hide_render = False
        obj.data.materials.clear()
        obj.data.materials.append(gray if name.startswith('PSU') else white if name.startswith('controller') else orange)
        equipment.append(obj)
    view('03_internal_layout', target=(0, 0, 8), position=(0, 0, 550), scale=260)
    for obj in cover_parts:
        obj.hide_render = False
        obj.location.z += 95
    view('04_exploded_assembly', target=(0, 0, 63), position=(260, -380, 540), scale=410)
    print(f'Assembly previews: {out}', flush=True)


if __name__ == '__main__':
    main()
