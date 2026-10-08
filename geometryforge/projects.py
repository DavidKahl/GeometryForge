"""Versioned standalone project and dependency contracts."""
from pathlib import Path
import re
import shutil
import tomllib
from .storage import read, write, inside, digest, HOME, fingerprint
from .locking import exclusive

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path(__file__).resolve().parent
ID = re.compile(r"^[a-z][a-z0-9_]*$")

def load(root):
    root = Path(root).resolve()
    config = tomllib.loads((root / "project.toml").read_text(encoding="utf-8"))
    if config.get("format_version") != 1:
        raise ValueError("Unsupported GeometryForge project format")
    if not ID.fullmatch(config["project"]["id"]):
        raise ValueError("Invalid project ID")
    parts = config.get("parts", {})
    if any(not ID.fullmatch(p) for p in parts):
        raise ValueError("Invalid part ID")
    for part, spec in parts.items():
        if set(spec.get("depends", [])) - parts.keys():
            raise ValueError(f"Unknown dependency of {part}")
        for path in spec.get("sources", []):
            if not inside(root, path).is_file():
                raise ValueError(f"Missing source {path}")
    for name, check in config.get("checks", {}).items():
        if not ID.fullmatch(name) or set(check["parts"]) - parts.keys():
            raise ValueError(f"Invalid check {name}")
        if not inside(root, check["source"]).is_file():
            raise ValueError(f"Missing checker {name}")
    for backend, spec in config.get("backends", {}).items():
        if backend not in ("blender", "houdini") or not inside(root, spec["entry"]).is_file():
            raise ValueError(f"Invalid backend {backend}")
    state = read(root / ".geometryforge/state.json", {"format_version": 1, "backends": {}, "latest_attempt": None, "safe_point": None, "issues": []})
    if state.get("format_version") != 1:
        raise ValueError("Unsupported state version")
    decisions = read(root / "decisions.json", {})
    params = read(root / "parameters.json", {})
    fingerprint(params)  # rejects nonfinite JSON values
    if decisions.get('units', 'mm') != 'mm':
        raise ValueError('GeometryForge project units must be mm')
    bed = decisions.get('print', {}).get('bed_mm', [220,220,250])
    if not isinstance(bed, list) or len(bed) not in (2,3) or any(type(v) not in (int,float) or not 0 < v < 100000 for v in bed):
        raise ValueError('Print bed must have two or three positive finite dimensions')
    return {"root": root, "config": config, "state": state, "decisions": decisions, "parameters": params}

def save_state(project):
    write(project["root"] / ".geometryforge/state.json", project["state"])

def inputs(project):
    root = project["root"]
    names = {"project.toml", "parameters.json", "decisions.json"}
    for spec in project["config"].get("parts", {}).values():
        names.update(spec.get("sources", []))
    for spec in project["config"].get("checks", {}).values():
        names.add(spec["source"])
        names.update(spec.get("sources", []))
    for spec in project["config"].get("backends", {}).values():
        names.add(spec["entry"])
    return {name: digest(inside(root, name)) for name in sorted(names)}

def closure(config, changed):
    result = set(changed)
    while True:
        expanded = result | {p for p, spec in config["parts"].items() if result.intersection(spec.get("depends", []))}
        if expanded == result:
            return result
        result = expanded

def part_inputs(project, name):
    spec = project["config"]["parts"][name]
    return {"sources": {s: digest(inside(project["root"], s)) for s in spec.get("sources", [])},
            "parameters": {p: project["parameters"][p] for p in spec.get("parameters", [])}, "spec": spec}

def initialize(destination, example=None, ident=None, deliverables="both", backend="blender", brief="", bed=(220,220,250)):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Initialize into an empty directory")
    ident = ident or destination.name.lower().replace("-", "_").replace(" ", "_")
    if not ID.fullmatch(ident):
        raise ValueError("Use a lowercase project ID with underscores")
    if example:
        if example not in ("desk_organizer",):
            raise ValueError("Unknown example")
        shutil.copytree(PACKAGE / "examples" / example, destination, dirs_exist_ok=True)
        text = (destination / "project.toml").read_text(encoding="utf-8")
        (destination / "project.toml").write_text(text.replace(f'id = "{example}"', f'id = "{ident}"', 1), encoding="utf-8")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "project.toml").write_text(f'format_version = 1\n[project]\nid = "{ident}"\ntitle = "{ident}"\n[parts]\n', encoding="utf-8")
        write(destination / "parameters.json", {})
    write(destination / "decisions.json", {"brief": brief or ("Printable " + example.replace("_", " ") if example else ""),
          "intended_use": "3d printing", "units": "mm", "deliverables": deliverables, "execution_backend": backend,
          "print": {"bed_mm": list(bed), "nozzle_mm": 0.4}, "unresolved": [] if example or brief else ["Define design brief and dimensions"]})
    (destination / "AGENTS.md").write_text("# Modeling this project\n\nUse the geometryforge skill. Start with `geometryforge context .`.\nKeep decisions in decisions.json and dimensions in parameters.json.\nPreserve working edits and safe points. Use `plan` before `run`.\n", encoding="utf-8")
    (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    register(destination)
    return {"project": str(destination), "id": ident}

def unregister(root):
    """Remove a project from the viewer catalog; its folder and runs are left untouched."""
    key = fingerprint(str(Path(root).resolve()))[:16]
    with exclusive(HOME):
        items = registry()
        removed = items.pop(key, None)
        write(HOME / "projects.json", items)
    return removed

def registry():
    return read(HOME / "projects.json", {})

def register(root, title=None, archived=False):
    p = load(root)
    key = fingerprint(str(p["root"]))[:16]
    with exclusive(HOME):
        items = registry()
        items[key] = {"path": str(p["root"]), "title": title or p["config"]["project"].get("title", p["config"]["project"]["id"]), "archived": archived}
        write(HOME / "projects.json", items)
    return {"key": key, **items[key]}
