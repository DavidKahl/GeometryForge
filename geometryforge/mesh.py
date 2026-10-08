"""Validate evaluated print geometry before writing STL and 3MF deliverables."""
import json
from pathlib import Path
import re


def print_pose(name, objects):
    """Trimesh bodies of one part rotated to its print orientation, centred in X/Y and resting on Z=0."""
    import numpy as np
    import trimesh
    rotations = {tuple(obj["print_rotation_deg"]) for obj in objects}
    if len(rotations) != 1:
        raise ValueError(f"{name}: bodies must share a print rotation")
    rotation = trimesh.transformations.euler_matrix(*np.radians(next(iter(rotations))))
    meshes = []
    for obj in objects:
        vertices = np.asarray(obj["vertices"], dtype=float)
        faces = np.asarray(obj["faces"], dtype=int)
        if (vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0
                or faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0
                or not np.isfinite(vertices).all() or faces.min() < 0 or faces.max() >= len(vertices)):
            raise ValueError(f"{name}: invalid or empty mesh arrays")
        mesh = trimesh.Trimesh(vertices=vertices, faces=obj["faces"], process=True)
        mesh.apply_transform(rotation)
        meshes.append(mesh)
    combined = trimesh.util.concatenate(meshes)
    offset = [-combined.bounds[:, 0].mean(), -combined.bounds[:, 1].mean(), -combined.bounds[0, 2]]
    for mesh in meshes:
        mesh.apply_translation(offset)
    return meshes


def export(raw: Path, out: Path, constraints: dict) -> dict:
    import numpy as np
    import trimesh
    from .three_mf import mesh_body, write

    payload = json.loads(raw.read_text(encoding="utf-8"))
    grouped = {}
    for obj in payload["objects"]:
        part = obj["part"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part):
            raise ValueError(f"Use a filename-safe gf_part: {part!r}")
        grouped.setdefault(part, []).append(obj)
    if not grouped:
        raise ValueError("No printable parts")
    if len({name.casefold() for name in grouped}) != len(grouped):
        raise ValueError("Part names collide on a case-insensitive filesystem")
    report = {"units": "mm", "passed": True, "parts": []}
    ready = []
    for name, objects in grouped.items():
        expectations = {(tuple(obj.get('expected_bbox_mm', [])), obj.get('expected_bodies', 1)) for obj in objects}
        if len(expectations) != 1:
            raise ValueError(f"{name}: bodies must share part-level dimension and body-count expectations")
        meshes = print_pose(name, objects)
        combined = trimesh.util.concatenate(meshes)
        expected = objects[0].get("expected_bbox_mm", [])
        bed = constraints.get("bed_mm", [256, 256])
        checks = {
            "watertight": all(m.is_watertight for m in meshes),
            "consistent_winding": all(m.is_winding_consistent for m in meshes),
            "positive_volume": all(m.volume > 0 for m in meshes),
            "body_count": len(combined.split(only_watertight=False)) == objects[0].get("expected_bodies", 1),
            "bed_fit": bool(np.all(combined.extents[:len(bed)] <= np.asarray(bed) + 1e-5)),
            "expected_dimensions": not expected or bool(np.allclose(combined.extents, expected, atol=0.02, rtol=0)),
            "filament_slots": all(isinstance(obj['filament'], int) and obj['filament'] > 0 for obj in objects),
        }
        report["parts"].append({"name": name, "bbox_mm": combined.extents.tolist(),
                                "expected_bbox_mm": expected or None,
                                "bed_mm": bed,
                                "expected_bodies": objects[0].get("expected_bodies", 1),
                                "volume_mm3": float(combined.volume), "checks": checks})
        report["passed"] &= all(checks.values())
        ready.append((name, objects, meshes))
    reports = out / "checks"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "meshes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passed"]:
        failures = [f"{p['name']}: {', '.join(k for k,v in p['checks'].items() if not v)}" for p in report['parts'] if not all(p['checks'].values())]
        raise ValueError("Print validation failed: " + "; ".join(failures))
    prints = out / "prints"
    prints.mkdir(parents=True, exist_ok=True)
    inventory = []
    for name, objects, meshes in ready:
        bodies = []
        stls = []
        for index, (obj, mesh) in enumerate(zip(objects, meshes)):
            suffix = f"_{index + 1}" if len(meshes) > 1 else ""
            mesh.export(prints / f"{name}{suffix}.stl")
            stls.append(f"{name}{suffix}.stl")
            bodies.append(mesh_body(obj["name"], mesh.vertices, mesh.faces, float(mesh.volume), obj["filament"]))
        write({name: bodies}, prints / f"{name}.3mf")
        inventory.append({'name': name, 'stls': stls, 'three_mf': f'{name}.3mf'})
    (out / 'print-files.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    verify_exports(out)
    return report


def verify_exports(out: Path):
    """Read delivered files back, checking their geometry against measured output."""
    import numpy as np
    import trimesh
    import zipfile
    import xml.etree.ElementTree as ET
    from .three_mf import CORE_NS

    inventory = json.loads((out / 'print-files.json').read_text(encoding='utf-8'))
    report = json.loads((out / 'checks/meshes.json').read_text(encoding='utf-8'))
    expected = {part['name']: part for part in report['parts']}
    results = []
    for part in inventory:
        stls = [trimesh.load_mesh(out / 'prints' / name) for name in part['stls']]
        with zipfile.ZipFile(out / 'prints' / part['three_mf']) as archive:
            model = ET.fromstring(archive.read('3D/3dmodel.model'))
            config = ET.fromstring(archive.read('Metadata/model_settings.config'))
        ns = {'c': CORE_NS}
        meshes = []
        for node in model.findall('.//c:mesh', ns):
            vertices = [[float(v.attrib[key]) for key in ('x', 'y', 'z')] for v in node.findall('c:vertices/c:vertex', ns)]
            faces = [[int(f.attrib[key]) for key in ('v1', 'v2', 'v3')] for f in node.findall('c:triangles/c:triangle', ns)]
            meshes.append(trimesh.Trimesh(vertices=vertices, faces=faces, process=True))
        metadata_ids = {p.attrib['id'] for p in config.findall('.//part')}
        referenced_ids = {c.attrib['objectid'] for c in model.findall('.//c:component', ns)}
        target = expected[part['name']]
        def matches(items):
            if not items or not all(m.is_watertight and m.is_winding_consistent and m.volume > 0 for m in items):
                return False
            combined = trimesh.util.concatenate(items)
            return (bool(np.allclose(combined.extents, target['bbox_mm'], atol=0.02, rtol=0))
                    and abs(combined.volume - target['volume_mm3']) <= max(0.02, target['volume_mm3'] * 1e-5)
                    and abs(combined.bounds[0, 2]) < 0.02)
        ok = (model.attrib.get('unit') == 'millimeter' and metadata_ids == referenced_ids
              and len(stls) == len(meshes) and matches(stls) and matches(meshes))
        results.append({'name': part['name'], 'passed': bool(ok)})
    passed = bool(results) and len(results) == len(expected) and all(r['passed'] for r in results)
    (out / 'checks/roundtrip.json').write_text(json.dumps({'passed': passed, 'parts': results}, indent=2), encoding='utf-8')
    if not passed:
        raise ValueError('Exported STL/3MF geometry differs from the validated print meshes')
