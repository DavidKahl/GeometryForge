---
name: geometryforge
description: Create and revise printable geometry and editable Blender or Houdini projects, preserving manual edits and validating only affected parts. Use for agent-led modeling, print exports, native-scene revisions, and GeometryForge run inspection.
---

# GeometryForge

Use the user's own agent harness for conversation, modeling decisions, code authoring and execution. The optional viewer only manages projects and inspects results. No API key, model provider, or embedded agent is needed.

## Establish the project

Run `geometryforge doctor`, then `geometryforge context <project>` for an existing project. If the command is missing, install the GeometryForge package from its checkout with `uv pip install -e /path/to/GeometryForge[viewer]` in the chosen environment; viewer is optional. Do not install bpy or hou in host Python.

For a new project, establish the brief, dimensions, intended use, target printer/process, execution backend, and deliverables: `geometry`, `blender`, `houdini`, or `both`. Preserve explicit user choices. Ask only for missing decisions that affect the design. Create an empty project or copy a bundled example using `geometryforge init <folder> --example desk_organizer --deliverables both`. Record dimensions in parameters.json and choices in decisions.json. Unavailable requested applications must be reported, not silently substituted.

Read [contracts](references/contracts.md) when authoring a project. Read [Blender](references/blender.md) or [Houdini](references/houdini.md) for the selected backends.

## Design for the target printer

For print deliverables, read [printing](references/printing.md) **before choosing construction, part splits or fine detail**. Reuse the recorded printer, installed nozzle, material and process choices. Verify relevant capabilities using the matching local slicer preset or manufacturer documentation; distinguish confirmed settings, measured calibration and provisional assumptions.

Establish a part-level print plan: intended orientation/contact face, usable build volume with process margins, feature/wall targets, joint clearance, load direction, support access and assembly order. Let this plan determine geometry. Preserve the requested finished size; split or redesign parts instead of silently shrinking them or assuming different hardware. Do not treat nozzle diameter as the printable feature limit, a generic overhang angle as a printer capability, or successful mesh export as proof of manufacturability.

Test uncertain features with a small representative section or fit coupon before detailing the entire model. For complex print work, use an available local slicer to inspect the actual exported parts and settings, including retained detail and removable supports. If slicing or physical testing is unavailable, record the unverified coverage and continue useful design work without claiming printer-ready results. Modeling or slicing does not authorize starting a printer job.

## Revise and verify

Start each resumed modeling task with `context`. Native working files, parameter choices, stale outputs and safe points belong to the project, not conversation memory. Read the referenced latest/safe run when its detailed evidence matters.

Run `geometryforge plan <project>` before execution. Use the smallest meaningful part selection; maintain source, parameter, dependency and interface-check declarations as geometry evolves. A new run record does not imply rebuilding the whole model. Example: `geometryforge run <project> --parts fairing`.

A change of printer, nozzle, material, layer/line settings, support policy or fit calibration requires reassessing the affected print plan. Update the geometry-driving parameters and check dependencies, not just a printer label; see [printing](references/printing.md#printer-and-process-changes). Preserve existing native edits during that reassessment.

On manual file changes, follow [revisions](references/revisions.md). Continuing an edited native scene is allowed. Never regenerate pristine geometry merely to perform full checks. `geometryforge verify <project> --full` verifies the working scenes. Explain uncertain scope and offer fuller verification or investigation rather than silently launching expensive work.

Deliver print artifacts, requested native files, measured check results, and the viewer/project reference. Include the target printer/process, orientations, support/assembly instructions and remaining assumptions. Distinguish fresh checks, reused evidence, candidates and SAFE POINTS, and separately state geometry verification, slicer review and physical testing. Renders show appearance; they do not establish fit, wall thickness or physical print success.

## Both native backends

Build meaningful Blender structures and Houdini SOP networks with shared named interfaces. A mesh imported into a second app is not equivalent native construction. After manual changes, retain both versions, identify which is authoritative, and ask about ambiguous reconciliation. Reconcile through explicit project recipes or native edits; never claim automatic history translation. A partial backend run remains a candidate until every requested backend is current and passes shared checks.
