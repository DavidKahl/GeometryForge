"""Versioned standalone project and dependency contracts."""
from pathlib import Path
import os
import re
import shutil
import tomllib
from .storage import read, write, inside, digest, HOME, fingerprint
from .locking import exclusive

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path(__file__).resolve().parent
ID = re.compile(r"^[a-z][a-z0-9_]*$")

CHECK_KINDS = ("seam", "recess", "mating", "global", "detail")
SURFACE_CHECKS = PACKAGE / "surface_checks.py"

def projects_root():
    """Where new projects are created: GEOMETRYFORGE_PROJECTS, then the user config, then GF_Projects
    beside a source checkout (or in the home folder for a wheel install). Projects keep working anywhere."""
    configured = os.environ.get("GEOMETRYFORGE_PROJECTS") or read(HOME / "config.json", {}).get("projects_root")
    if configured:
        return Path(configured).expanduser().resolve()
    return (ROOT.parent if (ROOT / "pyproject.toml").is_file() else Path.home()) / "GF_Projects"

def set_projects_root(path):
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with exclusive(HOME):
        config = read(HOME / "config.json", {})
        config["projects_root"] = str(root)
        write(HOME / "config.json", config)
    return {"projects_root": str(root), "exists": True}

def bare(name):
    """A plain folder name (no separators, not '.' or '..') means a project in the projects root."""
    text = str(name)
    return bool(text) and text not in (".", "..") and not Path(text).is_absolute() and not re.search(r"[\\/:]", text)

def resolve(root):
    """Project folder for a CLI argument: an existing path as given, else a bare name in the projects root."""
    path = Path(root)
    if not path.exists() and bare(root) and (projects_root() / root).exists():
        path = projects_root() / root
    return path.resolve()

def checker(root, check):
    """Typed checks run the packaged surface checker; others run a project file."""
    return SURFACE_CHECKS if check.get("kind") else inside(root, check["source"])

def validate_check(root, name, check, parts, version, params):
    if not ID.fullmatch(name) or not isinstance(check.get("parts"), list) or set(check["parts"]) - parts.keys():
        raise ValueError(f"Invalid check {name}")
    if "kind" in check:
        if version < 2 or "source" in check:
            raise ValueError(f"Typed check {name} needs format 2+ and replaces source with kind")
        if check["kind"] not in CHECK_KINDS:
            raise ValueError(f"Unknown check kind for {name}: {check['kind']}")
        if not isinstance(check.get("spec", {}), dict) or not isinstance(check.get("thresholds", {}), dict):
            raise ValueError(f"Check {name}: spec and thresholds must be tables")
        default = "measure" if check.get("spec", {}).get("test") == "silhouette_iou" else "enforce"
        check.setdefault("mode", default)
        if check["mode"] not in ("enforce", "measure"):
            raise ValueError(f"Check {name}: mode must be enforce or measure")
        # Threshold layers and calibration evidence are inputs of the result.
        if "gf_thresholds" in params and "gf_thresholds" not in check.setdefault("parameters", []):
            check["parameters"].append("gf_thresholds")
        if check.get("spec", {}).get("test") == "silhouette_iou":
            sources = check.setdefault("sources", [])
            cameras = root / "references/cameras.json"
            if cameras.is_file():
                for extra in ["references/cameras.json", read(cameras).get("cameras", {}).get(check["spec"].get("camera"), {}).get("mask")]:
                    if extra and extra not in sources:
                        sources.append(extra)
    elif not inside(root, check.get("source", "")).is_file():
        raise ValueError(f"Missing checker {name}")
    for path in check.get("sources", []):
        if not inside(root, path).is_file():
            raise ValueError(f"Missing checker source {path}")

def load(root):
    root = resolve(root)
    config = tomllib.loads((root / "project.toml").read_text(encoding="utf-8"))
    if config.get("format_version") not in (1, 2, 3):
        raise ValueError("Unsupported GeometryForge project format")
    if config.get("gates") and config["format_version"] < 3:
        raise ValueError("Gates require format_version = 3; run geometryforge migrate --format 3")
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
    params = read(root / "parameters.json", {})
    fingerprint(params)  # rejects nonfinite JSON values
    for name, check in config.get("checks", {}).items():
        validate_check(root, name, check, parts, config["format_version"], params)
    for backend, spec in config.get("backends", {}).items():
        if backend not in ("blender", "houdini") or not inside(root, spec["entry"]).is_file():
            raise ValueError(f"Invalid backend {backend}")
    state = read(root / ".geometryforge/state.json", {"format_version": config['format_version'], "backends": {}, "targets": {}, "safe_points": {}, "latest_attempt": None, "safe_point": None, "issues": []})
    if state.get("format_version") not in (1, 2, 3):
        raise ValueError("Unsupported state version")
    decisions = read(root / "decisions.json", {})
    if decisions.get('units', 'mm') != 'mm':
        raise ValueError('GeometryForge project units must be mm')
    p = {"root": root, "config": config, "state": state, "decisions": decisions, "parameters": params}
    if config['format_version'] >= 2:
        from .targets import validate_contract
        validate_contract(p)
    if config['format_version'] == 1 or 'print' in decisions.get('output_targets', []):
        bed = decisions.get('print', {}).get('bed_mm', [220,220,250])
        if not isinstance(bed, list) or len(bed) not in (2,3) or any(type(v) not in (int,float) or not 0 < v < 100000 for v in bed):
            raise ValueError('Print bed must have two or three positive finite dimensions')
    return p

def save_state(project):
    write(project["root"] / ".geometryforge/state.json", project["state"])

def inputs(project):
    root = project["root"]
    names = {"project.toml", "parameters.json", "decisions.json"}
    for spec in project["config"].get("parts", {}).values():
        names.update(spec.get("sources", []))
    for spec in project["config"].get("checks", {}).values():
        if "source" in spec:
            names.add(spec["source"])
        names.update(spec.get("sources", []))
    for spec in project["config"].get("backends", {}).values():
        names.add(spec["entry"])
    if project['config']['format_version'] >= 2:
        from .targets import declared_files
        names.update(declared_files(project))
    return {name: digest(inside(root, name)) for name in sorted(names)}

def closure(config, changed):
    result = set(changed)
    while True:
        expanded = result | {p for p, spec in config["parts"].items() if result.intersection(spec.get("depends", []))}
        if expanded == result:
            return result
        result = expanded

def build_order(config, parts):
    """Dependencies before dependents, alphabetical among independent parts.

    Recipes may reference objects another part created; building a dependent first would bind
    it to geometry that the dependency's rebuild then deletes.
    """
    remaining, ordered = set(parts), []
    while remaining:
        ready = sorted(p for p in remaining if not set(config["parts"][p].get("depends", [])) & remaining)
        if not ready:
            raise ValueError(f"Cyclic part dependencies: {sorted(remaining)}")
        ordered.append(ready[0])
        remaining.discard(ready[0])
    return ordered

def part_inputs(project, name):
    spec = project["config"]["parts"][name]
    return {"sources": {s: digest(inside(project["root"], s)) for s in spec.get("sources", [])},
            "parameters": {p: project["parameters"][p] for p in spec.get("parameters", [])}, "spec": spec}

def initialize(destination, example=None, ident=None, deliverables="both", backend="blender", brief="", bed=(220,220,250), target=None):
    destination = (projects_root() / destination if bare(destination) else Path(destination)).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Initialize into an empty directory")
    ident = ident or destination.name.lower().replace("-", "_").replace(" ", "_")
    if not ID.fullmatch(ident):
        raise ValueError("Use a lowercase project ID with underscores")
    if example:
        if example not in ("desk_organizer", "mechanical_prop"):
            raise ValueError("Unknown example")
        shutil.copytree(PACKAGE / "examples" / example, destination, dirs_exist_ok=True)
        text = (destination / "project.toml").read_text(encoding="utf-8")
        (destination / "project.toml").write_text(text.replace(f'id = "{example}"', f'id = "{ident}"', 1), encoding="utf-8")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "project.toml").write_text(f'format_version = 1\n[project]\nid = "{ident}"\ntitle = "{ident}"\n[parts]\n', encoding="utf-8")
        write(destination / "parameters.json", {})
    decisions = {"brief": brief or (example.replace("_", " ") if example else ""),
          "intended_use": "3d printing", "units": "mm", "deliverables": deliverables, "execution_backend": backend,
          "print": {"bed_mm": list(bed), "nozzle_mm": 0.4}, "unresolved": [] if example or brief else ["Define design brief and dimensions"]}
    if target is not None or example == 'mechanical_prop':
        target = target or 'game'
        if target not in ('print', 'game', 'both'):
            raise ValueError('Unknown output target')
        decisions.update(output_targets=['print', 'game'] if target == 'both' else [target],
                         intended_use='game asset' if target == 'game' else 'game asset and/or printable object',
                         game={'profile': 'unreal_desktop_standard'})
        contract = destination / 'project.toml'
        text = contract.read_text(encoding='utf-8').replace('format_version = 1', 'format_version = 2', 1)
        if example != 'mechanical_prop':
            for route in decisions['output_targets']:
                text += f'\n[targets.{route}]\n'
        contract.write_text(text, encoding='utf-8')
    write(destination / 'decisions.json', decisions)
    (destination / "AGENTS.md").write_text("# Modeling this project\n\nUse the geometryforge skill. Start with `geometryforge context .`.\nKeep decisions in decisions.json and dimensions in parameters.json.\nPreserve working edits and safe points. Use `plan` before `run`.\n", encoding="utf-8")
    (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    register(destination)
    return {"project": str(destination), "id": ident}

def unregister(root):
    """Remove a project from the viewer catalog; its folder and runs are left untouched."""
    key = fingerprint(str(resolve(root)))[:16]
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
