"""Whole-model 3MF deliverables: the assembled model and a print kit holding every part.

The assembled file keeps assembly coordinates so filament colours can be judged on the whole model;
it is usually larger than the bed and is not meant to be sliced. The kit holds every part in its
print orientation. When decisions.print.bambu names a Bambu Studio printer and process, Bambu Studio
arranges the kit onto plates and stamps the filament colours, producing a project that opens ready to slice.
"""
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from .three_mf import CORE_NS, mesh_body, write


def filament_plan(constraints):
    """Declared slots {slot: entry} from decisions.print.filaments, or {} when none are declared."""
    plan = {}
    for entry in constraints.get("filaments", []):
        slot = entry.get("slot")
        if not isinstance(slot, int) or slot < 1 or slot in plan:
            raise ValueError("decisions.print.filaments needs unique positive integer slots")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", entry.get("colour", "")):
            raise ValueError(f"Filament slot {slot} needs a #RRGGBB colour")
        plan[slot] = entry
    return plan


def _bodies(name, objects, meshes):
    return [mesh_body(f"{name}:{obj['name']}" if len(objects) > 1 else name, m.vertices, m.faces, float(m.volume), obj["filament"])
            for obj, m in zip(objects, meshes)]


def write_kits(grouped, out, constraints):
    """Write assembled.3mf and kit-raw.3mf; return what each part prints in."""
    import trimesh
    from .mesh import print_pose
    plan = filament_plan(constraints)
    used = {name: sorted({o["filament"] for o in objs}) for name, objs in grouped.items()}
    if plan:
        missing = {n: [s for s in slots if s not in plan] for n, slots in used.items()}
        missing = {n: s for n, s in missing.items() if s}
        if missing:
            raise ValueError(f"Parts use filament slots not declared in decisions.print.filaments: {missing}")
    assembled, kit = {}, {}
    # Parts are laid out in rows so the raw kit never overlaps, even before a slicer arranges it.
    bed_x = constraints.get("bed_mm", [256, 256])[0]
    cursor_x = cursor_y = row_depth = 0.0
    gap = 10.0
    for name in sorted(grouped):
        objects = grouped[name]
        raw = [trimesh.Trimesh(vertices=o["vertices"], faces=o["faces"], process=True) for o in objects]
        assembled[name] = _bodies(name, objects, raw)
        posed = print_pose(name, objects)
        size = trimesh.util.concatenate(posed).extents
        if cursor_x and cursor_x + size[0] > bed_x * 2:
            cursor_x, cursor_y, row_depth = 0.0, cursor_y + row_depth + gap, 0.0
        for mesh in posed:
            mesh.apply_translation([cursor_x + size[0] / 2, cursor_y + size[1] / 2, 0])
        cursor_x += size[0] + gap
        row_depth = max(row_depth, size[1])
        kit[name] = _bodies(name, objects, posed)
    out.mkdir(parents=True, exist_ok=True)
    write(assembled, out / "assembled.3mf")
    write(kit, out / "kit-raw.3mf")
    for file in ("assembled.3mf", "kit-raw.3mf"):
        if read_back(out / file)["extruders"] != used:
            raise ValueError(f"{file}: filament slots read back differently from the evaluated parts")
    return {"parts": used, "filaments": {str(k): v for k, v in sorted(plan.items())}}


def read_back(path):
    """Parts, per-part filament slots, plates and colours as stored in a 3MF (ours or Bambu's)."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        settings = json.loads(archive.read("Metadata/project_settings.config")) if "Metadata/project_settings.config" in names else {}
    extruders = {}
    for obj in config.findall("object"):
        name = obj.find("metadata[@key='name']").attrib["value"]
        default = obj.find("metadata[@key='extruder']")
        slots = set()
        for part in obj.findall("part"):
            value = part.find("metadata[@key='extruder']")
            slots.add(int((value if value is not None else default).attrib["value"]))
        extruders[name] = sorted(slots)
    plates = [[i.find("metadata[@key='object_id']").attrib["value"] for i in p.findall("model_instance")] for p in config.findall("plate")]
    return {"extruders": extruders, "plates": plates, "colours": settings.get("filament_colour", [])}


def bambu_executable():
    configured = os.environ.get("GEOMETRYFORGE_BAMBU")
    candidates = [configured] if configured else [r"C:\Program Files\Bambu Studio\bambu-studio.exe",
                                                  "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"]
    return next((Path(c) for c in candidates if c and Path(c).is_file()), None)


def _presets(executable):
    roots = [executable.parent / "resources/profiles/BBL", executable.parent.parent / "Resources/profiles/BBL"]
    root = next((r for r in roots if r.is_dir()), None)
    if not root:
        raise ValueError("Bambu Studio printer profiles not found next to the executable")
    index = {p.stem: p for p in root.rglob("*.json")}

    def resolve(name, stack=()):
        if name not in index:
            raise ValueError(f"Unknown Bambu Studio preset: {name}")
        if name in stack:
            raise ValueError("Preset inheritance cycle")
        data = json.loads(index[name].read_text(encoding="utf-8"))
        merged = {}
        if data.get("inherits"):
            merged.update(resolve(data["inherits"], stack + (name,)))
        for include in data.get("include", []):
            merged.update(resolve(include, stack + (name,)))
        merged.update(data)
        merged.pop("inherits", None)
        merged.pop("include", None)
        return merged
    return resolve


def bambu_package(out, constraints, used, timeout=600):
    """Arrange the kit onto plates and stamp filament colours with the local Bambu Studio CLI.

    Only reads installed presets and writes files in `out`; it never slices or contacts a printer.
    """
    settings = constraints.get("bambu")
    if not settings:
        return {"skipped": "decisions.print.bambu not set; kit-raw.3mf can be arranged in any slicer"}
    executable = bambu_executable()
    if not executable:
        raise ValueError("decisions.print.bambu is set but Bambu Studio was not found (set GEOMETRYFORGE_BAMBU)")
    plan = filament_plan(constraints)
    if not plan:
        raise ValueError("decisions.print.bambu needs decisions.print.filaments with a slot, colour and preset each")
    resolve = _presets(executable)
    work = out / "bambu"
    work.mkdir(parents=True, exist_ok=True)
    machine, process = work / "machine.json", work / "process.json"
    machine.write_text(json.dumps(resolve(settings["machine"])), encoding="utf-8")
    process.write_text(json.dumps(resolve(settings["process"])), encoding="utf-8")
    filaments = []
    # Slots are positional in Bambu Studio, so every slot up to the highest one gets a preset.
    for slot in range(1, max(plan) + 1):
        entry = plan.get(slot) or {"preset": plan[min(plan)]["preset"], "colour": "#808080"}
        preset = dict(resolve(entry["preset"]))
        preset["filament_colour"] = [entry["colour"].upper()]
        path = work / f"filament_{slot}.json"
        path.write_text(json.dumps(preset), encoding="utf-8")
        filaments.append(str(path))
    common = ["--load-settings", f"{machine};{process}", "--load-filaments", ";".join(filaments)]
    jobs = {"kit.3mf": (["--arrange", "1"], "kit-raw.3mf"), "assembled-bambu.3mf": ([], "assembled.3mf")}
    result = {"executable": str(executable), "machine": settings["machine"], "process": settings["process"], "files": {}}
    for target, (extra, source) in jobs.items():
        (out / target).unlink(missing_ok=True)
        log = work / (Path(target).stem + ".log")
        with log.open("w", encoding="utf-8") as stream:
            code = subprocess.run([str(executable), *extra, *common, "--export-3mf", str(out / target), str(out / source)],
                                  cwd=work, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
        if code or not (out / target).is_file():
            raise ValueError(f"Bambu Studio could not export {target} (exit {code}); see {log.name}")
        back = read_back(out / target)
        if back["extruders"] != used:
            raise ValueError(f"{target}: Bambu Studio changed the filament slots of some parts")
        if [c.upper() for c in back["colours"][:len(filaments)]] != [json.loads(Path(f).read_text())["filament_colour"][0] for f in filaments]:
            raise ValueError(f"{target}: filament colours were not stored as planned")
        result["files"][target] = {"plates": len(back["plates"]), "instances": sum(len(p) for p in back["plates"])}
    kit = result["files"]["kit.3mf"]
    if kit["instances"] != len(used):
        raise ValueError(f"kit.3mf places {kit['instances']} of {len(used)} parts on plates")
    return result
