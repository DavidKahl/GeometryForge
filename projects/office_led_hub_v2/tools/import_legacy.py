"""One-off import of GeometryForge 0.3 run history into this project (read-only on the source).

Usage: python tools/import_legacy.py <legacy out dir> <legacy source dir>
Each legacy run becomes .geometryforge/runs/<id>Z-<hash>/run.json with per-part assembly.json,
preview, print files and the native scene, so the viewer can browse and compare them.
Imported runs are history only: they were never validated by this engine, so no safe point is set.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent.parent))
from geometryforge.storage import digest, write  # noqa: E402


def artifact(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def import_run(legacy, parent, bed):
    build = load(legacy / "build.json")
    stamp, short = legacy.name.split("-", 1)
    ident = f"{stamp}Z-{short}"  # legacy IDs are UTC without the Z marker
    out = ROOT / ".geometryforge/runs" / ident
    if out.exists():
        raise SystemExit(f"{out} already exists; refusing to overwrite")
    backend = build.get("backend", "blender")
    directory = out / backend
    objects = load(legacy / "meshes.json")["objects"]
    grouped = {}
    for obj in objects:
        grouped.setdefault(obj["part"], []).append(obj)
    measured = {p["name"]: p for p in load(legacy / "checks/meshes.json", {"parts": []})["parts"]}
    prints = {p["name"]: p for p in load(legacy / "print-files.json", [])}
    previews = {f.stem.split("_", 1)[1]: f for f in (legacy / "previews").glob("*.png")} if (legacy / "previews").is_dir() else {}
    parts = {}
    for name in sorted(grouped):
        part_dir = directory / "parts" / name
        # Legacy exports vary key order and only later ones carry matrix_world (vertices are already world space).
        # Dropping it and fixing the order keeps identical geometry byte-identical, which the viewer's comparison checks;
        # the engine's geometry_hash ignores matrix_world for the same reason.
        write(part_dir / "assembly.json", {"units": "mm", "objects": [dict(sorted((k, v) for k, v in o.items() if k != "matrix_world")) for o in grouped[name]]})
        files = [part_dir / "assembly.json"]
        # Multi-body parts had one preview per body (insert_flux_1, insert_flux_2); keep the first.
        preview = previews.get(name) or next((previews[k] for k in sorted(previews) if k.startswith(name + "_")), None)
        if preview:
            files.append(copy(preview, part_dir / "preview.png"))
        entry = prints.get(name, {})
        for file in [*entry.get("stls", []), *([entry["three_mf"]] if entry.get("three_mf") else [])]:
            if (legacy / "prints" / file).is_file():
                files.append(copy(legacy / "prints" / file, part_dir / "prints" / file))
        vertices = [v for o in grouped[name] for v in o["vertices"]]
        bounds = [[min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)]]
        measurements = {**measured.get(name, {}), "bed_mm": bed}
        parts[name] = {"reused": False, "artifacts": [artifact(f) for f in files], "measurements": measurements, "assembly_bounds_mm": bounds}
    checks = {}
    for report in sorted((legacy / "checks").glob("*.json")):
        data = load(report)
        if isinstance(data, dict) and isinstance(data.get("checks"), list):
            for check in data["checks"]:
                checks[check["name"]] = {"passed": bool(check.get("passed")), "reused": False, "detail": check.get("detail", ""), "suite": report.stem}
    native = None
    if (legacy / "models/model.blend").is_file():
        native = artifact(copy(legacy / "models/model.blend", directory / "model.blend"))
    for log in ("blender.log", "presentation.log"):
        if (legacy / log).is_file():
            copy(legacy / log, directory / log)
    for log in (legacy / "checks").glob("*.log"):
        copy(log, directory / "checks" / log.name)
    failures = [f.replace(str(legacy), f"legacy run {legacy.name}") for f in build.get("failures", [])]
    write(out / "run.json", {
        "format_version": 1, "id": ident, "parent": parent, "status": build["status"], "owner_pid": None,
        "inputs": {}, "decisions": {}, "parameters": load(legacy / "parameters.json", build.get("parameters", {})), "plan": None,
        "backends": {backend: {"version": build.get("backend_version"), "parts": parts, "checks": checks, "native": native,
                               "changed_parts": [], "rebuilt_parts": [], "source": "legacy-import"}},
        "failures": failures, "validation": {"imported": True},
        "imported_from": {"path": str(legacy), "toolkit": "GeometryForge 0.3", "operation": build.get("operation"),
                          "inputs": build.get("inputs", {}), "note": "History only; not validated by this engine."},
        "engine_version": None, "toolkit": "legacy-import"})
    return ident


def main(legacy_out, legacy_source):
    legacy_out, legacy_source = Path(legacy_out), Path(legacy_source)
    decisions = load(ROOT / "decisions.json")
    bed = decisions["print"]["bed_mm"]
    parent, imported = None, []
    for run in sorted(p for p in (legacy_out / "runs").iterdir() if (p / "build.json").is_file()):
        parent = import_run(run, parent, bed)
        imported.append(parent)
    reference = ROOT / "legacy_source"
    if not reference.exists():
        shutil.copytree(legacy_source, reference, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    write(ROOT / ".geometryforge/state.json", {"format_version": 1, "backends": {}, "latest_attempt": imported[-1], "safe_point": None,
          "issues": ["Imported legacy history only; port legacy_source/models/hub.py to a backend entry before running."]})
    print(json.dumps({"imported": imported}, indent=2))


if __name__ == "__main__":
    main(*sys.argv[1:3])
