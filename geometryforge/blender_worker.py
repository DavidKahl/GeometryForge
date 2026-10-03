"""Background Blender entrypoint. Communicates through a JSON mesh artifact."""
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def meshes():
    scene = bpy.context.scene
    if scene.get("geometryforge_units") != "mm" or abs(scene.unit_settings.scale_length - 0.001) > 1e-8:
        raise ValueError("Scene must use GeometryForge millimeters (scale_length=0.001)")
    collection = bpy.data.collections.get("Printable")
    if not collection:
        raise ValueError("Missing Printable collection")
    sources = set(collection.all_objects)
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = []
    for instance in graph.object_instances:
        obj = instance.object
        original = obj.original
        parent = instance.parent.original if instance.parent else None
        if original not in sources and parent not in sources:
            continue
        if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
            continue
        owner = parent if instance.is_instance and parent in sources else original
        mesh = obj.to_mesh(preserve_all_data_layers=False, depsgraph=graph)
        try:
            mesh.calc_loop_triangles()
            matrix = instance.matrix_world
            vertices = [list(matrix @ v.co) for v in mesh.vertices]
            faces = [list(t.vertices) for t in mesh.loop_triangles]
            # Geometry Nodes can produce only instances: its emitter has an
            # empty mesh, while the evaluated instances below hold the solids.
            if not faces:
                continue
            if matrix.determinant() < 0:
                faces = [list(reversed(f)) for f in faces]
            rotation = list(owner.get("gf_print_rotation_deg", (0, 0, 0)))
            result.append({"name": original.name, "part": owner.get("gf_part", owner.name),
                           "vertices": vertices, "faces": faces,
                           "matrix_world": [list(row) for row in matrix],
                           "print_rotation_deg": rotation,
                           "filament": int(owner.get("gf_filament", 1)),
                           "expected_bbox_mm": list(owner.get("gf_expected_bbox_mm", [])),
                           "expected_bodies": int(owner.get("gf_expected_bodies", 1))})
        finally:
            obj.to_mesh_clear()
    if not result:
        raise ValueError("Printable collection contains no evaluated geometry")
    expected_parts = {obj.get('gf_part', obj.name) for obj in sources
                      if obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
                      or obj.instance_type == 'COLLECTION'}
    missing = expected_parts - {obj['part'] for obj in result}
    if missing:
        raise ValueError(f"Printable parts have no evaluated geometry: {sorted(missing)}")
    return result

