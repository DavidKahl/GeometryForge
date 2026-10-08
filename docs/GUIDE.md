# GeometryForge user guide

This guide covers what you need after the [README](../README.md) quick start: how a project is laid out, what each command does, how to edit models by hand, how multi-material printing works, and what to do when something goes wrong.

Most of the time you won't type these commands yourself. Your agent runs them through the installed skill. Knowing them helps you follow along and step in.

- [Working with your agent](#working-with-your-agent)
- [Project layout](#project-layout)
- [Commands](#commands)
- [Editing native files by hand](#editing-native-files-by-hand)
- [The viewer](#the-viewer)
- [Printing and multi-material](#printing-and-multi-material)
- [Writing builders and checks](#writing-builders-and-checks)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Working with your agent

After `geometryforge install-skill`, ask your agent to "use GeometryForge" for a modeling task. The skill makes it:

1. Run `geometryforge context` to read the current state of an existing project.
2. For a new model, establish the brief, dimensions, intended use, **target printer and process**, and which native files you want (`blender`, `houdini` or `both`). It asks only for decisions that change the design and records them in `decisions.json` and `parameters.json`.
3. Plan the print before detailing: orientation, splits to fit the bed, wall and detail sizes for your nozzle, joint clearances, supports and assembly order.
4. Write the modeling code, run `plan`, then `run` with the smallest sensible set of parts.
5. Report what was actually verified, keeping geometry checks, slicer review and physical testing separate.

A good request names the object, its size or purpose, your printer and nozzle, the material, and which applications you use. Ask for a fit coupon whenever parts have to mate.

## Project layout

```text
my_project/
├── project.toml          parts, builders, checks and their dependencies
├── parameters.json       dimensions and other values the code reads
├── decisions.json        brief, deliverables, printer, filament plan
├── models/               native builder code (Blender and/or Houdini)
├── checks/               functional checks (fit, clearances, volumes)
├── references/           your reference images and notes (optional)
├── working/              editable .blend / .hip files from each run   ← local output
└── .geometryforge/       run records and retained evidence            ← local output
```

`working/` and `.geometryforge/` are generated. Keep them out of version control and don't edit files under `.geometryforge/runs`: their hashes are how GeometryForge detects tampering and decides what can be reused.

### project.toml

```toml
format_version = 1

[project]
id = "desk_organizer"          # lowercase letters, digits, underscores
title = "Desk Organizer"

[backends.blender]
entry = "models/blender.py"     # must define build_parts(parameters, parts, api)
[backends.houdini]
entry = "models/houdini.py"

[parts.organizer]               # one table per printable part
sources = ["models/assembly.py", "models/organizer.py"]   # every file that affects this part
parameters = ["count", "width", "depth", "height", "wall", "floor"]
depends = []                    # other parts whose changes affect this one

[checks.cavities]
source = "checks/verify.py"     # must define verify(payload)
parts = ["organizer"]
parameters = ["count", "width", "depth", "height", "wall", "floor"]
```

Declare **every** input. A part is only rebuilt, and a check only rerun, when one of its declared sources, parameters or dependency parts changed. An undeclared helper file means stale evidence can be reused.

### decisions.json

| Key | Meaning |
|---|---|
| `brief`, `intended_use` | What the model is for |
| `units` | Always `"mm"` |
| `deliverables` | `"blender"`, `"houdini"`, `"both"`, or `"geometry"` (print files only, built with `execution_backend`) |
| `execution_backend` | Application used when deliverables is `"geometry"` |
| `print.bed_mm` | Usable build volume `[x, y]` or `[x, y, z]`, used by the bed-fit check |
| `print.nozzle_mm` | Installed nozzle |
| `print.filaments` | Optional filament plan, see [multi-material](#printing-and-multi-material) |
| `print.bambu` | Optional Bambu Studio presets for the print kit |
| `unresolved` | Open questions the agent still needs answered |

The agent may record more (printer model, part plan, assumptions). Changing `decisions.print` invalidates export evidence, so the next run re-exports.

### Run records

Each run lives in `.geometryforge/runs/<YYYYMMDDTHHMMSSZ-hash>/`:

```text
run.json                     status, inputs, plan, per-backend results and failures
inputs/                      snapshot of every declared source
<backend>/
  model.blend | model.hipnc  native scene saved by this run
  parts/<part>/              assembly.json, preview.png, prints/<part>.stl|.3mf, checks/
  checks/<check>.json        functional check results
  kit/                       whole-model 3MF files (see below)
  <backend>.log              application log
```

## Commands

All commands print JSON. Exit code `0` means success, `2` a failed, cancelled or candidate run, `1` an error. The project argument defaults to the current folder.

| Command | What it does |
|---|---|
| `geometryforge doctor` | Shows the Blender, Houdini and Bambu Studio executables that will be used |
| `geometryforge install-skill [--target DIR \| --user] [--harness claude\|codex\|both]` | Installs the agent skill |
| `geometryforge init DIR [--example desk_organizer] [--deliverables …] [--bed X Y Z] [--brief …]` | Creates a project and registers it with the viewer |
| `geometryforge context [DIR]` | Decisions, parameters, safe point, open issues, and whether working scenes changed. Start here. |
| `geometryforge plan [DIR] [--parts …] [--backend …]` | Which parts would be rebuilt and from which source, without running anything |
| `geometryforge run [DIR] [--parts …] [--backend …] [--full] [--source auto\|scene\|code]` | Builds, exports, checks and records a run |
| `geometryforge verify [DIR] [--backend …] [--full]` | Re-checks the saved working scenes without running any builder |
| `geometryforge history [DIR]` | All run records, newest first |
| `geometryforge restore [DIR] [--run ID]` | Copies a safe point's scenes and sources into a new `working/restore-*` folder |
| `geometryforge adopt DIR --backend blender\|houdini --file FILE` | Makes a native file you saved elsewhere the working scene |
| `geometryforge register [DIR]` | Adds an existing project to the viewer catalog |
| `geometryforge viewer [--port 8743]` | Starts the local viewer |
| `geometryforge session status\|stop` | Inspects or stops the managed Houdini session |

`--parts` selects parts to rebuild; everything that depends on them follows automatically. `--full` ignores reusable evidence and reruns every export and check. Run `geometryforge <command> --help` for every option.

## Editing native files by hand

You can open the working `.blend` or `.hip` from the latest run, change it and save it. Then:

1. Ask your agent to continue, or run `geometryforge context`. It reports `working_changed: true` for that backend.
2. `geometryforge verify` re-checks your edited scene as it is, without regenerating anything. Which parts changed is detected from the evaluated geometry.
3. A normal `run` continues from your saved scene. If **both** the code/parameters and the native file changed, GeometryForge stops and asks you to choose: `--source scene` keeps your manual edit, `--source code` lets the selected builders replace those parts in a copy.

Edits only reach GeometryForge once they're saved to disk. Your edited file is never overwritten; every run writes a new working copy. A file saved somewhere else can be brought in with `adopt`.

`geometryforge restore` copies the safe point's native scenes and matching sources into a new folder under `working/`. Nothing current is deleted. Use `adopt` to continue from a restored scene.

When a project produces both Blender and Houdini files, a safe point needs both to agree: same part names, dimensions within 0.1 mm and volumes within 1 %. A manual edit in one application makes the other one out of date until the agent reconciles it.

## The viewer

`geometryforge viewer` (or `Launch Viewer.cmd` on Windows) serves <http://127.0.0.1:8743>. It only listens on your own machine and never runs project code.

- **Projects** (left): add a project folder with **＋**. Rename and archive are under **⋯**.
- **Parts** tab: filter, show/hide, and select parts. Numbered parts (`fin_1…fin_4`) are grouped. Ctrl/Shift-click to select several.
- **Runs** tab: open any run as **A**. **Compare with A** puts another run beside it as **B**, side by side with a shared camera or as an orange overlay. The strip above the view lists changed, added and removed parts.
- **Isolate** (⛶, double-click or `I`) shows the selected parts in their own scene, in assembly or print orientation. In comparison mode, a part missing from B is reported as such.
- **Part colours / Filaments** recolours the model by planned filament.
- **Renders** open in an image viewer with zoom; downloads are always explicit. **Files & logs** has the whole-model 3MFs, each part's STL/3MF, the native scene and the application log.

Keys: `I` isolate · `H` hide selection · `Alt+H` show all · `F` fit · `Esc` back.

## Printing and multi-material

Every part is exported in its print orientation (`prints/<part>.stl` and `.3mf`), centred and resting on the bed. Checks cover watertightness, consistent winding, positive volume, the expected number of bodies, bed fit, expected dimensions and an exact STL/3MF read-back. Your project's own checks cover fits and interfaces. None of this replaces looking at the sliced result and printing a test coupon.

### Whole-model files

Each run also writes `kit/` for each application:

| File | Contents |
|---|---|
| `assembled.3mf` | Every part in its assembled position, for judging colours on the whole model. Usually larger than the bed and not meant to be sliced. |
| `kit-raw.3mf` | Every part in print orientation, laid out without overlap, for any slicer |
| `kit.3mf` | *(Bambu Studio)* The kit arranged onto plates with your filament colours, ready to slice |
| `assembled-bambu.3mf` | *(Bambu Studio)* The assembled model with filament colours |

Every part is a separate named object and every body keeps its filament slot, so you can choose materials per part in the slicer.

### Planning filaments

Filament slots are assigned in the model, so they survive every rebuild:

1. In builder code, pass the slot when finishing a body: `api.finish(obj, filament=2)`. A part can have several bodies in different slots, for example a hull with a separate accent band.
2. Drive the slot from a parameter, so changing the colour plan rebuilds the right parts. The Astraeus lander maps its material colours with `"filament_slots": {"silver": 1, "dark": 2, …}` in `parameters.json`.
3. Describe the slots in `decisions.json`:

```json
"print": {
  "bed_mm": [256, 256, 250],
  "nozzle_mm": 0.4,
  "filaments": [
    {"slot": 1, "name": "Silver", "colour": "#BFCAD1", "material": "PLA", "preset": "Generic PLA @BBL X2D 0.4 nozzle"},
    {"slot": 2, "name": "Dark",   "colour": "#2C3842", "material": "PLA", "preset": "Generic PLA @BBL X2D 0.4 nozzle"}
  ],
  "bambu": {"machine": "Bambu Lab X2D 0.4 nozzle", "process": "0.16mm High Quality @BBL X2D"}
}
```

A run fails if a part uses a slot that isn't in the plan. `bambu` is optional. When it is set, GeometryForge calls the local Bambu Studio command line to arrange `kit.3mf` onto plates and store the colours, then reads the file back to confirm every part's slot, the colours and that every part is on a plate. The preset names must match presets installed with Bambu Studio. GeometryForge never slices or contacts a printer.

**Open `kit.3mf` in Bambu Studio and check the plates before printing.** Choose your real filaments there; colour-matched generic presets are placeholders. On dual-nozzle printers such as the X2D, Bambu Studio's command line can't slice more than one filament offline, so slicing the multi-filament kit happens in the Bambu Studio app.

## Writing builders and checks

Your agent normally writes these. If you want to write or review them yourself:

```python
# models/blender.py (and models/houdini.py): the entry declared in project.toml
def build_parts(parameters, parts, api):
    for part in parts:              # only the parts this run rebuilds
        api.begin(part)             # removes the objects/nodes this part owned before
        body = api.box('body', (80, 60, 20), (0, 0, 10))
        cut = api.box('pocket', (70, 50, 20), (0, 0, 12))
        api.boolean(body, cut, 'DIFFERENCE')   # stays a live modifier / node
        api.finish(body, filament=1, rotation=(0, 0, 0))  # mark printable; rotation = print orientation
```

`api` offers `box`, `cylinder`, `boolean`, `rotate` and `finish` for both applications. You can also use `bpy` or `hou` directly, as long as every printable object is finished with its part ID. Builders run inside Blender or Houdini, never in the GeometryForge environment.

```python
# checks/verify.py: runs in the GeometryForge environment with numpy and trimesh
def verify(payload):
    hull = payload["objects"]["hull"]          # evaluated triangles of the declared parts
    clearance = payload["parameters"]["clearance_mm"]
    ...                                         # measure real geometry, not just parameters
    return {"passed": True, "measured_gap_mm": 0.31}   # or raise / return passed: False
```

## Configuration

| Variable | Purpose |
|---|---|
| `GEOMETRYFORGE_BLENDER` | Blender executable |
| `GEOMETRYFORGE_HOUDINI` | Houdini executable or installation folder |
| `GEOMETRYFORGE_BAMBU` | Bambu Studio executable (optional) |
| `GEOMETRYFORGE_HOME` | Where the viewer's project catalog and the Houdini session state live (default `~/.geometryforge`) |

## Troubleshooting

| Symptom | What to do |
|---|---|
| `Set GEOMETRYFORGE_BLENDER or pass --blender` | Blender isn't on `PATH` or in the standard install folder. Set the variable or pass `--blender`. Check with `geometryforge doctor`. |
| Houdini starts a visible window | Expected: GeometryForge drives a dedicated Houdini session. Leave it running during runs. `geometryforge session stop` closes it. |
| Files are `.hipnc` instead of `.hip` | Your Houdini license (e.g. Apprentice) only saves non-commercial files. That's a license restriction, not a bug. |
| Run ends as **candidate** with "Scene part IDs differ" | The scene has parts that `project.toml` doesn't declare, or the other way round. Update the part list. |
| "Both procedural inputs and native file changed" | Choose explicitly: `run --source scene` keeps your manual edit, `--source code` regenerates the selected parts. |
| "Native outputs need reconciliation" | Blender and Houdini results differ by more than the tolerance. Ask the agent to reconcile, or limit deliverables to one application. |
| Run reports filament slots "not declared" | Add the slot to `decisions.print.filaments` or change the part's filament. |
| "Bambu Studio was not found" | Install it, set `GEOMETRYFORGE_BAMBU`, or remove `decisions.print.bambu` to get only the slicer-neutral files. |
| Viewer port already in use | `geometryforge viewer --port 8750` |
| A run stays "running" in the viewer | The process was interrupted. The viewer labels it *interrupted*; the safe point is unaffected. |
