# GeometryForge user guide

This guide covers what you need after the [README](../README.md) quick start: how a project is laid out, what each command does, how to edit models by hand, how multi-material printing works, and what to do when something goes wrong.

Most of the time you won't type these commands yourself. Your agent runs them through the installed skill. Knowing them helps you follow along and step in.

- [Working with your agent](#working-with-your-agent)
- [Project layout](#project-layout)
- [Commands](#commands)
- [Editing native files by hand](#editing-native-files-by-hand)
- [The viewer](#the-viewer)
- [Printing and multi-material](#printing-and-multi-material)
- [Game assets and printable derivatives](GAME_ASSETS.md)
- [Writing builders and checks](#writing-builders-and-checks)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Working with your agent

After `geometryforge install-skill`, ask your agent to "use GeometryForge" for a modeling task. The skill makes it:

1. Run `geometryforge context` to read the current state of an existing project.
2. For a new model, establish the brief, dimensions, intended use and **output route** (`print`, `game` or both), separately from native files (`blender`, `houdini` or both). Print work adds printer/process choices; game work adds profile, materials, pivots and collision. Record choices in `decisions.json` and dimensions in `parameters.json`.
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

If you start from reference images, the agent first asks whether you want a printable model, a game asset or both, then reviews what the images show. If views are missing it names them (and, for generated images, suggests a prompt for matching views). Otherwise it lists the assumptions it will make and waits for your go-ahead. The review is recorded under `reference_review` in `decisions.json`.

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
| `geometryforge migrate [DIR] --format 2\|3` | Backs up and upgrades a project; format 3 enables modeling gates |
| `geometryforge calibrate [DIR] [--camera ID …] [--dry-run]` | Solves reference cameras from `references/correspondences.json` and writes overlays |
| `geometryforge gate status\|check\|accept\|reopen\|template …` | Inspects, checks, accepts or reopens modeling gates (format 3) |
| `geometryforge review DIR --scene … --config … [--blind] [--baseline ID]` | Renders read-only appearance evidence |
| `geometryforge review-diff DIR --before ID --after ID --parts …` | Fails if pixels outside the edited parts changed between two reviews |

`--parts` selects parts to rebuild; everything that depends on them follows automatically, and parts are built dependencies first. `--full` ignores reusable evidence and reruns every export and check. Run `geometryforge <command> --help` for every option.

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

## Gated hard-surface workflow

Curved multi-panel assets such as vehicles, housings and armour go wrong in two predictable ways when an agent models them in code. One monolithic mesh stays simplistic, because every local detail loop disturbs the whole hull. Many independently built pieces drift apart, because they are placed by coordinates and nothing ties their curvature together. A format 3 project makes the agent work top-down, and the toolkit enforces the order:

| Gate | Builds | Must pass before acceptance |
|---|---|---|
| 0 calibration | a solved camera for the primary reference, feature curves | RMS reprojection error within `max_rms_px`, current image and picks |
| 1 master hull | one hidden, watertight low-poly cage for the whole exterior | closed mesh, calibrated silhouette IoU, zebra/silhouette/overlay review |
| 2 panels | panels sliced from the master and shrinkwrapped back onto it; recessed pockets | seam, coverage (and recess) checks |
| 3 detail | mechanical parts bound to interface rings exported by their parents | mating and recess checks |

Only accepted gates and the active gate can be built; later parts are dormant, and `run --parts` on them is refused. Accepting a gate records its evidence under `.geometryforge/gates/` and locks its geometry. A run that changes locked geometry becomes a candidate. `gate reopen` releases it and supersedes later gates. Game and print routes wait until the final gate is accepted.

```powershell
geometryforge migrate projects/taxi --format 3
geometryforge gate template            # prints a [gates.*] starting point
geometryforge calibrate projects/taxi  # after recording correspondences.json
geometryforge gate check projects/taxi calibration
geometryforge gate accept projects/taxi calibration --by Dave --note "Dave: overlay matches, go"
geometryforge run projects/taxi --target design
geometryforge review projects/taxi --scene … --config projects/taxi/reviews/master.json --blind
geometryforge gate check projects/taxi master
```

`gate accept` requires `--by` and a `--note` quoting the approval. The agent must only run it after you have approved the evidence; the toolkit can verify the evidence, not who approved it.

### Calibration

`references/correspondences.json` lists, per camera, the image, an optional crop and mask, lens priors and picked points:

```json
{"version": 1, "cameras": {"primary": {
  "role": "primary", "image": "references/front_right_3q.png", "mask": "references/front_right_3q_mask.png",
  "priors": {"lens_mm": null, "sensor_width_mm": 36},
  "points": [{"id": "pad_fl", "world_mm": [1425, -720, 0], "pixel": [412.5, 803.0]},
             {"id": "nose", "world_mm": {"param": "datum_nose_mm"}, "pixel": [1290.0, 610.0]}]}}}
```

Use at least six well-spread datums, or four or more with a known lens. Masks are white object on black, or use an alpha channel. `calibrate` writes `references/cameras.json` and an overlay image showing picks (red), reprojections (blue), feature curves from `references/features.json` (green) and the datum box (yellow). Supplementary views solved against the same datums are flagged `inconsistent` when they disagree with the primary proportions. Review views can then use `"camera": {"ref": "primary"}`.

### Surfacing helpers and typed checks

Blender recipes get `api.surf`: `master_hull`, `slice_panel`, `inset_panel_perimeter`, `build_guide_mesh_stack` (Subdivision → Shrinkwrap onto the master → Solidify → weighted Bevel), `recessed_pocket_extrude`, `extract_interface_ring`, `local_ring`, `bind_to_ring`, `project_detail`, plus `patch`, `loft` and `sweep`. Everything stays an editable modifier stack. In Houdini, build equivalent SOP networks and register them with the `guide` and `interface` roles; the helpers themselves are Blender-only for now.

Checks can name a packaged `kind` instead of a checker file:

```toml
[checks.seam_front_skirt]
kind = "seam"                 # seam | recess | mating | global
parts = ["front_body", "skirt", "master_hull"]
[checks.seam_front_skirt.spec]
a = {part = "front_body"}
b = {part = "skirt"}
master = {part = "master_hull"}
```

**seam** measures how far the panel skin leaves the master, plus step, gap, tangent break and curvature mismatch across the joint. **recess** measures protrusion beyond the master, rim flushness, wall draft and the return's fillet radius. **mating** measures ring axis, centre offset, engagement lap and skin crossings. **global** runs `open_edges`, `coverage` (master area no panel covers) or calibrated `silhouette_iou`. Defaults live in `parameters.json` under `gf_thresholds`, can be overridden per check, and are recorded with every result. The defaults are starting values from an unverified engineering report; tune them to the asset. The [checks reference](../geometryforge/skill/references/checks.md) lists every measure, and [`tools/fixtures/surfacing_project`](../tools/fixtures/surfacing_project) is a complete three-gate example.

## Reference and geometry review

For close-up reference assets, establish proportions and compound curvature before panel structure, mechanical detail, materials and optimization. The [surface-modeling reference](../geometryforge/skill/references/surface-modeling.md) covers the master-hull workflow, quad subdivision cages, surface-derived panels, thickness, swept trim and selective Boolean cuts. Blender's Python API is available beyond GeometryForge's helpers.

Render a saved scene without rebuilding, saving or adopting it:

```powershell
geometryforge review projects/my_asset --scene projects/my_asset/working/model.blend --config projects/my_asset/review-views.json
```

Set `GEOMETRYFORGE_BLENDER` or pass `--blender <executable>`. The `--timeout` default is 900 seconds for the whole subprocess. Scene/config CLI paths are relative to the calling directory; reference paths are relative to the project and must remain inside it. Review outputs are written to a new `review/<timestamp-id>/` folder; existing evidence is retained. The command never runs project recipes, modifies a source scene or promotes a safe point.

```json
{
  "version": 1,
  "views": [{
    "id": "front",
    "selection": {"parts": ["body"]},
    "camera": {
      "position_mm": [8000, -10000, 5000],
      "target_mm": [0, 0, 1200],
      "projection": "perspective",
      "lens_mm": 50,
      "sensor_width_mm": 36,
      "up": [0, 0, 1]
    },
    "studio": {"center_mm": [0, 0, 1200], "size_mm": 7000},
    "resolution": [1280, 960],
    "samples": 16,
    "modes": ["clay", "glossy", "silhouette", "wireframe"],
    "reference": "references/front.png",
    "reference_crop": [0, 0, 1024, 768],
    "notes": "Primary identity view; photographic camera matching is approximate."
  }]
}
```

Use unique lowercase view IDs with underscores. Cameras and geometry are interpreted in millimeters; source scenes with metric unit scaling are normalized in memory. For orthographic views set `projection` to `orthographic` and provide positive `ortho_scale_mm`. The default is a 50 mm perspective camera with a 36 mm sensor and Z up. Camera direction and up must be nonparallel.

`selection` can contain `parts` (stable `gf_part` values), `objects` (exact object names), or both; both selectors form a union. Omit it to review all eligible geometry. Explicit design/high-detail/render/printable objects and visible untagged mesh/curve/surface/text geometry are eligible. Collection and Geometry Nodes instances are expanded from the evaluated dependency graph using their world transforms. Construction, presentation, collision and LOD helpers are excluded. Unknown/non-renderable selectors fail with details in the retained Blender log. References/crops are optional; crops are `[left, top, right, bottom]` pixels. Resolution defaults to 1280×960 (32–4096 per dimension), samples to 16 (1–256), and all four modes are enabled by default.

Evidence includes the neutral images, reference contact sheets, saved normalized camera settings, source/config/reference hashes, Blender version, evaluated object/triangle counts and artifact hashes. Render subdivision levels are used. The CPU Cycles studio uses a fixed seed and view-relative strip lights; source textures, materials, cameras and lights are ignored. Wireframe shows evaluated topology rather than the sparse source cage. Silhouette is a black foreground on white, composed from holdout alpha. For matched before/after lighting, give both views the same optional `studio.center_mm` and positive `studio.size_mm`; without them the rig fits each selection's bounds. The report records the effective studio placement and renderer source hash. Runtime failures retain `report.json` and any available log/images. Invalid configuration or missing input files fail before launching Blender or creating a review folder.

Additional review options:

- **Diagnostic modes.**
  - `zebra`: reflection stripes. Positional breaks make bands jump, tangent breaks make them kink, and curvature-continuous surfaces keep them flowing. Set `zebra.stripes` and `zebra.rotation_deg`.
  - `normal` and `part_id`: exact, unfiltered pixels, used by `review-diff`.
  - `overlay`: feature curves and the selection box projected onto a render and, for calibrated views, onto the reference.
- **Sections.** `"section": {"axis": "x", "offset_mm": 2400, "keep": "negative"}` cuts the evaluated copies for X-ray checks of closure and wall thickness.
- **Guide objects.** `selection.roles` adds hidden `guide` objects such as the master hull.
- **Presets.** `"presets": [{"preset": "survey21", "bounds_mm": [[…], […]] | "safe_point", "camera_refs": ["primary"]}]` adds 6 orthographic, 8 three-quarter, calibrated, 3 section and 3 close-up views. `standard6` and a configurable `survey` are also available.
- **Silhouette IoU.** Calculated only for views with a mask (`camera.ref` with a calibrated mask, or `reference_mask`). It is compared with the latest earlier review using the same camera and mask (or `--baseline ID`) and recorded under `metrics`. No score is produced for uncalibrated photographs without a mask.
- **Blind output.** `--blind` keeps metrics off the contact sheets and out of the command output. Write the visual critique first, then read `report.json`.
- **Region invariance.** `review-diff --before ID --after ID --parts front_body` compares the `part_id` and `normal` renders of two reviews made with the same cameras. Pixels outside the edited parts, plus `--margin-px`, must not change.

Inspect the images and record remaining differences. Use identical camera settings for before/after comparison. A technically validated run is not visual acceptance; generated alternate views and meshes remain interpretations of the primary image. Preserve the detailed master and optimize a derived copy only after reviewing its shape.

Convex forms can still have intentional hard features. Keep top/chamfer/side breaks explicit and round only their small manufacturing radii. Bind mating parts to interface rings rather than scalar datums, and measure them with `mating` checks. Machinery in curved bodywork sits behind a painted recessed return (`recessed_pocket_extrude`) instead of standing proud of the skin. The load path (housing, races, webs into a beam or bulkhead) stays behind that return, visible only where the reference shows it. A Boolean clearance provides space for an assembly, not its mechanical purpose.

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
