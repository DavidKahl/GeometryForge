"""Incremental runs with immutable evidence and recoverable working scenes."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import runpy
import uuid
import sys
from . import __version__
from .storage import digest, fingerprint, read, write, inside
from .projects import load, inputs, part_inputs, closure, save_state, PACKAGE
from .locking import exclusive

def run_path(project, ident):
    if not ident or any(c not in "0123456789abcdefT-Z-_" for c in ident):
        raise ValueError("Invalid run ID")
    return project["root"] / ".geometryforge/runs" / ident

def record(project, ident):
    return read(run_path(project, ident) / "run.json") if ident else None

def selected_backends(project):
    choice = project["decisions"].get("deliverables", "geometry")
    if choice not in ("geometry", "blender", "houdini", "both"):
        raise ValueError("Unknown deliverables choice")
    return ["blender", "houdini"] if choice == "both" else [project["decisions"].get("execution_backend", "blender") if choice == "geometry" else choice]

def context(root):
    p = load(root)
    current = inputs(p)
    backends = {}
    for backend in selected_backends(p):
        state = p["state"]["backends"].get(backend, {})
        baseline = record(p, state.get("run"))
        working = inside(p["root"], state["working"]) if state.get("working") else None
        changed = bool(working and (not working.exists() or digest(working) != state.get("working_hash")))
        stale = not baseline or baseline["inputs"] != current or changed or state.get("stale", False)
        prior_info = baseline.get('backends', {}).get(backend, {}) if baseline else {}
        backends[backend] = {**state, "working_changed": changed, "stale": stale,
                             'native_edits': prior_info.get('native_edits', []),
                             'procedural_reconciliation_required': bool(prior_info.get('native_edits', []))}
    safe = p["state"].get("safe_point")
    safe_record = record(p, safe)
    predates = bool(safe_record and (safe_record['inputs'] != current or any(
        state.get('working_hash') != safe_record.get('backends', {}).get(b, {}).get('native', {}).get('sha256')
        or state.get('working_changed') for b, state in backends.items())))
    return {"project": str(p["root"]), "decisions": p["decisions"], "parameters": p["parameters"],
            "backends": backends, "safe_point": safe, "latest_attempt": p["state"].get("latest_attempt"),
            "safe_point_label": ("SAFE POINT — predates working edits" if predates else "SAFE POINT") if safe else "No validated safe point",
            "issues": p["state"].get("issues", []) + p["decisions"].get("unresolved", []),
            "note": "Only saved files can be inspected. Save native-app edits before continuing."}

def plan(root, backend=None, parts=(), full=False, source="auto"):
    p = load(root)
    targets = [backend] if backend else selected_backends(p)
    if set(parts) - p["config"].get("parts", {}).keys():
        raise ValueError("Unknown selected part")
    results = {}
    ctx = context(root)
    for b in targets:
        if b not in p["config"].get("backends", {}):
            raise ValueError(f"Project has no {b} builder")
        state = p["state"]["backends"].get(b, {})
        base = record(p, state.get("run"))
        prior = base.get("backends", {}).get(b, {}) if base else {}
        changed = set(parts) | {name for name in p["config"]["parts"] if prior.get("part_inputs", {}).get(name) != part_inputs(p, name)}
        if base and (base["inputs"].get(p["config"]["backends"][b]["entry"]) != inputs(p).get(p["config"]["backends"][b]["entry"])):
            changed.update(p["config"]["parts"])
        manual = ctx["backends"].get(b, {}).get("working_changed", False)
        changed = closure(p["config"], changed)
        native_edits = set(prior.get('native_edits', []))
        unresolved = bool(source == 'auto' and changed and (manual or changed.intersection(native_edits)))
        chosen = 'scene' if source == 'scene' or (source == 'auto' and (manual or not changed)) else 'code'
        results[b] = {"parts": sorted(changed), "source": chosen, "inspect_saved_scene": bool(state.get("working")),
                      "full_verification": full, "manual_edits": manual, "needs_choice": unresolved,
                      "reason": "Both procedural inputs and native file changed; choose --source scene or --source code explicitly" if unresolved else "Inspect evaluated parts, then select affected checks"}
    return {"backends": results, "requested_parts": list(parts), "full": full}

def snapshot(p, out, expected):
    destination = out / "inputs"
    for name, sha in expected.items():
        src = inside(p["root"], name)
        dst = inside(destination, name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if digest(dst) != sha or digest(src) != sha:
            raise RuntimeError(f"Source changed during snapshot: {name}")
    if inputs(p) != expected:
        raise RuntimeError("Project changed during snapshot")
    return destination

def engine_version():
    return fingerprint({f.name: digest(f) for f in PACKAGE.glob("*.py")})

def objects_by_part(objects):
    grouped = {}
    for obj in objects:
        grouped.setdefault(obj["part"], []).append(obj)
    return grouped

def geometry_hash(objects):
    # Ignore transient object names; retain geometry, placement and export metadata.
    return fingerprint(sorted([fingerprint({k: v for k, v in o.items() if k not in ("name", "matrix_world", "obj", "role", "material")}) for o in objects]))

def artifact_ok(p, artifact):
    try:
        file = inside(p["root"], artifact["path"])
        return file.is_file() and digest(file) == artifact["sha256"]
    except (KeyError, ValueError):
        return False

def artifact(p, path):
    return {"path": str(path.relative_to(p["root"])).replace("\\", "/"), "sha256": digest(path)}

def execute(root, backend=None, parts=(), full=False, source="auto", timeout=900, executables=None):
    p = load(root)
    with exclusive(p["root"] / ".geometryforge"):
        p = load(root)
        proposal = plan(root, backend, parts, full, source)
        if not p["config"].get("parts"):
            raise ValueError("Define parts and backend builders before running")
        ident = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        out = run_path(p, ident)
        out.mkdir(parents=True)
        data = {"format_version": 1, "id": ident, "parent": p["state"].get("safe_point"), "status": "running", "owner_pid": os.getpid(),
                "inputs": inputs(p), "decisions": p["decisions"], "parameters": p["parameters"], "plan": proposal,
                "backends": {}, "failures": [], "validation": {}, "engine_version": engine_version(), "toolkit": __version__}
        p["state"]["latest_attempt"] = ident
        save_state(p)
        write(out / "run.json", data)
        try:
            frozen = snapshot(p, out, data["inputs"])
            pending_states = {}
            for b, spec in proposal["backends"].items():
                if spec["needs_choice"]:
                    raise ScopeUncertain(spec["reason"])
                pending_states[b] = execute_backend(p, data, out, frozen, b, spec, full, timeout, (executables or {}).get(b))
                write(out / "run.json", data)
            if inputs(p) != data["inputs"]:
                raise ScopeUncertain("Working inputs changed during the run; candidate retained")
            for b, update in pending_states.items():
                old = p["state"]["backends"].get(b, {})
                if old.get("working") and digest(inside(p["root"], old["working"])) != data["backends"][b]["working_input_hash"]:
                    raise ScopeUncertain("Working native scene changed during execution; candidate retained")
            p["state"]["backends"].update(pending_states)
            for b, state in p["state"]["backends"].items():
                if b not in pending_states:
                    state["stale"] = True
            requested = selected_backends(p)
            all_current = all(b in pending_states for b in requested)
            if all_current and len(requested) == 2:
                parity(p, data)
            data["status"] = "passed" if all_current else "candidate"
            data["validation"]["complete"] = all_current
            if all_current:
                p["state"]["safe_point"] = ident
                p["state"]["issues"] = []
            else:
                p["state"]["issues"] = ["Selected backend validated; other requested native output needs reconciliation"]
            save_state(p)
        except ScopeUncertain as exc:
            data["status"] = "candidate"
            data["failures"].append(str(exc))
            p["state"]["issues"] = [str(exc)]
            save_state(p)
        except BaseException as exc:
            data["status"] = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
            data["failures"].append(str(exc))
            p["state"]["issues"] = [str(exc)]
            save_state(p)
        finally:
            write(out / "run.json", data)
        return data

class ScopeUncertain(RuntimeError):
    pass

def execute_backend(p, data, out, frozen, backend, spec, full, timeout, executable):
    from .backends import run_native
    from .mesh import export
    state = p["state"]["backends"].get(backend, {})
    prior_run = record(p, state.get("run"))
    prior = prior_run.get("backends", {}).get(backend, {}) if prior_run else {}
    directory = out / backend
    directory.mkdir()
    scene = None
    source_hash = None
    if state.get("working"):
        working = inside(p["root"], state["working"])
        source_hash = digest(working)
        scene = directory / ("input" + working.suffix)
        shutil.copy2(working, scene)
        if digest(scene) != source_hash or digest(working) != source_hash:
            raise ScopeUncertain("Native source changed during snapshot")
    elif spec["source"] == "scene":
        raise ValueError("No working native scene is registered")
    rebuild = spec["parts"] if spec["source"] == "code" else []
    result = run_native(backend, directory, frozen / p["config"]["backends"][backend]["entry"], data["parameters"], rebuild, scene, timeout, executable)
    grouped = objects_by_part(result["objects"])
    known = set(p["config"]["parts"])
    if set(grouped) != known:
        raise ScopeUncertain(f"Scene part IDs differ from project: missing {sorted(known-set(grouped))}, extra {sorted(set(grouped)-known)}. Update the part/check contract before verification.")
    hashes = {name: geometry_hash(objects) for name, objects in grouped.items()}
    changed = {name for name in known if hashes[name] != prior.get("geometry", {}).get(name)}
    affected = closure(p["config"], changed | set(rebuild))
    if scene and spec["source"] == "code" and changed - set(rebuild):
        raise ScopeUncertain(f"Revision changed unselected geometry: {sorted(changed-set(rebuild))}. Inspect dependencies or explicitly use the edited scene.")
    native_path = Path(result["scene"])
    procedural = dict(prior.get('procedural_geometry', {n:h for n,h in prior.get('geometry', {}).items() if n not in prior.get('native_edits', [])}))
    for name in rebuild:
        procedural[name] = hashes[name]
    info = {"version": result["version"], "license": result.get("license"), "geometry": hashes,
            "procedural_geometry": procedural,
            "native_edits": sorted(n for n,h in hashes.items() if procedural.get(n) != h),
            "native_structure": {k: result[k] for k in ('native_objects','modifiers','native_nodes') if k in result},
            "part_inputs": {n: part_inputs(p, n) for n in known}, "working_input_hash": source_hash,
            "changed_parts": sorted(changed), "rebuilt_parts": rebuild, "affected_parts": sorted(affected),
            "parts": {}, "checks": {}, "native": artifact(p, native_path), "source": spec["source"]}
    data["backends"][backend] = info
    tool_key = fingerprint([result["version"], data["engine_version"], data["decisions"].get("print", {})])
    for name in sorted(known):
        old = prior.get("parts", {}).get(name, {})
        key = fingerprint([hashes[name], tool_key])
        if not full and key == old.get("key") and all(artifact_ok(p, a) for a in old.get("artifacts", [])) and old.get("artifacts"):
            info["parts"][name] = {**old, "reused": True, "from_run": old.get("from_run") or state["run"]}
            continue
        part_dir = directory / "parts" / name
        part_dir.mkdir(parents=True)
        raw = part_dir / "assembly.json"
        write(raw, {"units": "mm", "objects": grouped[name]})
        report = export(raw, part_dir, data["decisions"].get("print", {}))
        from .preview import preview
        preview(grouped[name], part_dir / "preview.png")
        files = [raw, part_dir / "preview.png", *sorted((part_dir / "prints").iterdir()), *sorted((part_dir / "checks").iterdir())]
        import numpy as np
        vertices = np.concatenate([o['vertices'] for o in grouped[name]])
        bounds = [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()]
        info["parts"][name] = {"key": key, "reused": False, "artifacts": [artifact(p, f) for f in files], "measurements": report["parts"][0], "assembly_bounds_mm": bounds}
    for name, check in p["config"].get("checks", {}).items():
        dependencies = {part: hashes[part] for part in check["parts"]}
        checker_hashes = {s: digest(frozen / s) for s in [check["source"], *check.get("sources", [])]}
        key = fingerprint([dependencies, checker_hashes, {k: data["parameters"][k] for k in check.get("parameters", [])}, check, tool_key])
        old = prior.get("checks", {}).get(name, {})
        if not full and old.get("key") == key and old.get("passed"):
            info["checks"][name] = {**old, "reused": True, "from_run": old.get("from_run") or state["run"]}
            continue
        payload = {"parameters": data["parameters"], "objects": {n: grouped[n] for n in check["parts"]}, "check": name}
        payload_path = directory / "checks" / f"{name}-input.json"
        write(payload_path, payload)
        report_path = directory / "checks" / f"{name}.json"
        from .process import run
        from .worker_env import worker_environment
        code = run([sys.executable, PACKAGE / "check_worker.py", frozen / check["source"], payload_path, report_path], cwd=frozen, env=worker_environment(), log=directory / "checks" / f"{name}.log", timeout=timeout)
        check_result = read(report_path, {"passed": False, "error": "Checker exited without a result"})
        info["checks"][name] = {**check_result, "key": key, "reused": False}
        if code or not check_result["passed"]:
            raise ValueError(f"{backend}: check {name} failed: {check_result}")
    # Whole-model files are rebuilt every run from the evaluated scene: cheap, and they always match it.
    from .kit import write_kits, bambu_package
    kit_dir = directory / "kit"
    constraints = data["decisions"].get("print", {})
    kit = write_kits(grouped, kit_dir, constraints)
    kit["bambu"] = bambu_package(kit_dir, constraints, kit["parts"], timeout)
    kit["artifacts"] = [artifact(p, kit_dir / f) for f in ("kit.3mf", "assembled-bambu.3mf", "assembled.3mf", "kit-raw.3mf") if (kit_dir / f).is_file()]
    info["kit"] = kit
    # Make a new editable file, never replace a user-edited scene.
    working = p["root"] / "working" / data["id"] / backend / native_path.name
    working.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(native_path, working)
    return {"run": data["id"], "working": str(working.relative_to(p["root"])), "working_hash": digest(working), "stale": False}

def parity(p, data):
    a, b = [data["backends"][n] for n in ("blender", "houdini")]
    failures = []
    for part in p["config"]["parts"]:
        x, y = [v["parts"][part]["measurements"] for v in (a, b)]
        ax, bx = [v['parts'][part]['assembly_bounds_mm'] for v in (a,b)]
        if any(abs(i-j) > 0.1 for left,right in zip(ax,bx) for i,j in zip(left,right)):
            failures.append(part + ': assembly bounds or placement differ by more than 0.1 mm')
        if any(abs(i-j) > 0.1 for i,j in zip(x["bbox_mm"], y["bbox_mm"])):
            failures.append(part + ": native dimensions differ by more than 0.1 mm")
        if abs(x["volume_mm3"]-y["volume_mm3"]) > max(1, x["volume_mm3"] * .01):
            failures.append(part + ": native volumes differ by more than 1%")
    data["validation"]["native_parity"] = {"passed": not failures, "failures": failures, "method": "part identity, dimensions, volume and shared functional checks"}
    if failures:
        raise ScopeUncertain("Native outputs need reconciliation: " + "; ".join(failures))

def restore(root, ident=None):
    p = load(root)
    with exclusive(p["root"] / ".geometryforge"):
        p = load(root)
        ident = ident or p["state"].get("safe_point")
        data = record(p, ident)
        if not data or data["status"] != "passed":
            raise ValueError("Restore requires a validated safe point")
        target = p["root"] / "working" / ("restore-" + uuid.uuid4().hex[:12])
        source = run_path(p, ident) / "inputs"
        for name, sha in data["inputs"].items():
            if digest(inside(source, name)) != sha:
                raise ValueError("Safe-point snapshot was modified")
        for backend, item in data["backends"].items():
            if not artifact_ok(p, item["native"]):
                raise ValueError("Safe-point native artifact was modified")
        shutil.copytree(source, target / "sources")
        for backend, item in data["backends"].items():
            original = inside(p["root"], item["native"]["path"])
            dest = target / backend / original.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, dest)
        return {"restored_from": ident, "working_copy": str(target), "note": "Existing working files and active sources preserved. Use adopt to select a restored native scene; sources/ contains matching procedural inputs."}

def adopt(root, backend, file):
    p = load(root)
    with exclusive(p["root"] / ".geometryforge"):
        p = load(root)
        source = Path(file).resolve()
        allowed = (".blend",) if backend == "blender" else (".hip", ".hipnc", ".hiplc")
        if source.suffix.lower() not in allowed or not source.is_file():
            raise ValueError("Missing or incompatible native file")
        target = p["root"] / "working" / ("import-" + uuid.uuid4().hex[:12]) / source.name
        target.parent.mkdir(parents=True)
        before = digest(source)
        shutil.copy2(source, target)
        if digest(target) != before or digest(source) != before:
            raise ValueError("Source changed during import")
        old = p["state"]["backends"].get(backend, {})
        p["state"]["backends"][backend] = {**old, "working": str(target.relative_to(p["root"])), "working_hash": None, "stale": True}
        save_state(p)
        return context(root)
