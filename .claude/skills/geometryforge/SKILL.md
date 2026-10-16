---
name: geometryforge
description: Create and revise game assets and printable geometry as editable Blender or Houdini projects, preserving manual edits and validating only affected routes and parts. Use for reference-driven modeling, PBR assets, Unreal delivery, print conversion and GeometryForge run inspection.
---

# GeometryForge

Use the user's own agent harness for conversation, modeling decisions, code authoring and execution. The optional viewer only manages projects and inspects results. No API key, model provider, or embedded agent is needed.

## Establish the project

Run `geometryforge doctor`, then `geometryforge context <project>` for an existing project. If the command is missing, install the GeometryForge package from its checkout with `uv pip install -e /path/to/GeometryForge[viewer]` in the chosen environment; viewer is optional. Do not install bpy or hou in host Python.

For a new project, establish the brief, dimensions, intended use, output route, execution backend, and native deliverables: `geometry`, `blender`, `houdini`, or `both`. Print projects also establish printer/process choices. Preserve explicit user choices. Ask only for missing decisions that affect the design. Create an empty project or copy a bundled example using `geometryforge init <folder> --example desk_organizer --deliverables both` or `--example mechanical_prop --target game --deliverables blender`. Record dimensions in parameters.json and choices in decisions.json. Unavailable requested applications must be reported, not silently substituted.

Establish the output route separately: `print`, `game`, or both. Existing v1 projects remain print projects. Use `init --target game|print|both` for v2, or explicitly `migrate --format 2` an existing project. `--deliverables both` still means Blender and Houdini native deliverables, not both delivery routes. Do not require a printer for game-only work.

For game work read [game assets](references/game-assets.md), then [v2 contracts](references/targets.md). Record actual game dimensions, viewing distance, style, desktop profile, material/texture budgets, pivots, grid, sockets, collision and lighting. Interpret unseen reference surfaces explicitly through the reference intake below. Use the shared editable design before deriving destination geometry; preserve high detail for later baking/printing. A successful print mesh or a dense Nanite import does not establish game suitability.

For destination conversion read [conversion](references/conversion.md). Author the conversion recipe, declare its dependencies and outputs, then use `derive` with a retained run, source route and explicit scale. Derivation is not automatic history reconstruction. Preserve source snapshots and explain manufacturing-driven differences. Normal maps do not uniquely recover solid geometry.

Read [contracts](references/contracts.md) when authoring a project. Read [Blender](references/blender.md) or [Houdini](references/houdini.md) for the selected backends.

For reference-driven hero geometry, follow the gated workflow below and read [surface modeling](references/surface-modeling.md). Direct native APIs are available beyond the supplied helpers. Passing technical validation does not establish reference fidelity. Protect intentional feature edges while rounding broad forms. Preserve accepted native components and verify their geometry when reusing them in a larger study.

## Reference intake

When a new project starts from reference images, complete this intake before writing geometry code. It applies to every route.

1. **Output route.** Ask whether the result is a printable model, a game asset, or both, unless the user has already said so. Never infer it from the image, the example or CLI defaults; the route changes construction from the start.
2. **Coverage.** List each image with its view direction. For each major part, state whether it is *seen*, *inferable* (symmetry, convention, a matching part) or a *guess*. Note scale cues, ambiguous connections and hidden surfaces. Judge against the route: a game asset needs every surface its camera will see at its viewing distance; a print needs real thickness, closure and attachment points.
3. **Verdict.**
   - *Not enough reference:* name the missing views precisely (e.g. "rear three-quarter", "underside of the pads", "side profile at the engine mounts") and why each matters. If the reference was generated, offer a short prompt the user can give their image tool to produce matching views of the same object. Then stop. Continue only when the views arrive or the user explicitly overrides; an override turns every gap into a listed assumption.
   - *Enough reference:* give a final warning before starting: the assumptions you will make (every *guess*, and how you will resolve it), and which decisions will be expensive to change later. Ask for explicit acceptance. Do not model before it.
4. **Record.** Copy the images into `references/` and store the review under `decisions.reference_review`: each reference's path, SHA-256 and view; the coverage map; `verdict` (`sufficient`, `insufficient` or `override`); requested views; assumptions; and who accepted, when. Until acceptance, keep `"Reference review not accepted"` in `decisions.unresolved` so `context` reports it. This is agent-maintained context, not an enforced schema.

5. **Calibrate.** For the primary identity view, record 3D datums (pad centres, length and width extremes, nose tip) and their pixels in `references/correspondences.json`, feature curves (roofline, beltline, chine, mount centrelines) in `references/features.json`, and a white-on-black silhouette mask. Run `geometryforge calibrate` and inspect the overlay. Solve supplementary views against the same datums; one flagged `inconsistent` disagrees with the primary proportions, so do not model from it until it is normalized or replaced. Never quote a similarity score without a calibrated camera and a mask.

New references arriving later reopen the review for the parts they show. Explain departures from the accepted assumptions instead of silently changing them.

## Gated hard-surface workflow

Multi-panel curved hulls (vehicles, housings, armour) are built top-down in a format 3 project (`migrate --format 3`; `gate template` prints a starting `[gates.*]` set). The toolkit enforces the order: only accepted gates and the active gate are buildable, later parts stay dormant, and accepted geometry is locked. Read [gates](references/gates.md) and [checks](references/checks.md).

- **Gate 0, calibration:** the calibrated primary camera and feature cage from the reference intake.
- **Gate 1, master hull:** one watertight low-poly cage for the whole exterior skin, with no openings, panel gaps or mechanical detail (`api.surf.master_hull`, regions naming future panels and openings, creases instead of support loops). Pass `global` checks (closed, calibrated silhouette IoU) and a zebra/silhouette/overlay review.
- **Gate 2, panels:** slice every exterior panel from the master (`slice_panel`, `inset_panel_perimeter`, `build_guide_mesh_stack`). Never loft adjacent body panels independently. Pass `seam`, `coverage` and section reviews.
- **Gate 3, detail:** mechanical parts bind to exported interface rings (`extract_interface_ring`, `bind_to_ring`), never to scalar datums; seat fasteners with `project_detail`. Pass `mating` and `recess` checks.

Mechanical sockets, lamps and vents in curved bodywork never stand proud of the master unless the reference shows it, and never expose raw framing. Form a painted recessed return with `recessed_pocket_extrude` (guide weight 1 at the flush rim falling to 0 inside). Place races, webs, lenses and glands behind that return so only the purposeful interface shows.

Critique the review sheets before reading metrics or check results: render with `review --blind`, write the critique to a file, then read `report.json` and the checks. Passing checks support but do not replace the critique. Run `gate check`, show the user the evidence, and run `gate accept --by <name> --note "<their words>" --critique <file>` only after their explicit approval. To change accepted geometry, `gate reopen` with a reason; later gates are superseded.

## Design for the target printer

For print deliverables, read [printing](references/printing.md) **before choosing construction, part splits or fine detail**. Reuse the recorded printer, installed nozzle, material and process choices. Verify relevant capabilities using the matching local slicer preset or manufacturer documentation; distinguish confirmed settings, measured calibration and provisional assumptions.

Establish a part-level print plan: intended orientation/contact face, usable build volume with process margins, feature/wall targets, joint clearance, load direction, support access and assembly order. Let this plan determine geometry. Preserve the requested finished size; split or redesign parts instead of silently shrinking them or assuming different hardware. Do not treat nozzle diameter as the printable feature limit, a generic overhang angle as a printer capability, or successful mesh export as proof of manufacturability.

Test uncertain features with a small representative section or fit coupon before detailing the entire model. For complex print work, use an available local slicer to inspect the actual exported parts and settings, including retained detail and removable supports. If slicing or physical testing is unavailable, record the unverified coverage and continue useful design work without claiming printer-ready results. Modeling or slicing does not authorize starting a printer job.

## Revise and verify

Start each resumed modeling task with `context`. Native working files, parameter choices, stale outputs and safe points belong to the project, not conversation memory. Read the referenced latest/safe run when its detailed evidence matters.

Run `geometryforge plan <project>` before execution. Use the smallest meaningful part selection within the active gate; maintain source, parameter, dependency and check declarations as geometry evolves. A new run record does not imply rebuilding the whole model. Example: `geometryforge run <project> --parts nose_tip`. Locked and dormant parts are refused; a changed locked part makes the run a candidate. For edits inside a part, compare `part_id`/`normal` reviews with `review-diff` so unedited regions provably stay unchanged. Measure joints and seams with typed checks (`seam`, `recess`, `mating`, `global`); a Boolean overlap only proves that parts touch.

In v2 choose `--target game|print|both` and the game `--profile` as needed. Inspect stage coverage and per-route safe points. Material preparation, baking, LOD and collision recipes are explicitly authored project code; `verify --full` never runs their builders. If recipes or required preparation changed, rebuild or reconcile before calling a package current. Save texture edits and declare imported texture dependencies.

A change of printer, nozzle, material, layer/line settings, support policy or fit calibration requires reassessing the affected print plan. Update the geometry-driving parameters and check dependencies, not just a printer label; see [printing](references/printing.md#printer-and-process-changes). Preserve existing native edits during that reassessment.

On manual file changes, follow [revisions](references/revisions.md). Continuing an edited native scene is allowed. Never regenerate pristine geometry merely to perform full checks. `geometryforge verify <project> --full` verifies the working scenes. Explain uncertain scope and offer fuller verification or investigation rather than silently launching expensive work.

Deliver print artifacts (per-part STL/3MF plus the run's whole-model `kit/` files and filament plan), requested native files, measured check results, and the viewer/project reference. Include the target printer/process, orientations, support/assembly instructions and remaining assumptions. Distinguish fresh checks, reused evidence, candidates and SAFE POINTS, and separately state geometry verification, slicer review and physical testing. Renders show appearance; they do not establish fit, wall thickness or physical print success.

For game deliverables supply the game package ZIP, manifest, FBX meshes/LODs/collision, PBR maps, GLB previews, native scenes and check evidence. Optional `unreal import --uproject ...` and `unreal verify --import ...` use a selected Unreal project with the required editor plugins. The viewer only inspects; it does not build or import. Distinguish package-safe, Unreal-verified, rendered review and measured performance. Never infer engine verification from GLB appearance, or physical testing from mesh validity. Report backend/license limits instead of substituting Blender for a requested Houdini deliverable.

## Both native backends

Build meaningful Blender structures and Houdini SOP networks with shared named interfaces. A mesh imported into a second app is not equivalent native construction. After manual changes, retain both versions, identify which is authoritative, and ask about ambiguous reconciliation. Reconcile through explicit project recipes or native edits; never claim automatic history translation. A partial backend run remains a candidate until every requested backend is current and passes shared checks. Typed checks measure evaluated evidence from either backend identically; check [houdini](references/houdini.md) for the surfacing helpers' parity status before promising them there. Gate reviews render the Blender scene.
