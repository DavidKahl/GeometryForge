---
name: geometryforge
description: Create and revise printable geometry and editable Blender or Houdini projects, preserving manual edits and validating only affected parts. Use for agent-led modeling, print exports, native-scene revisions, and GeometryForge run inspection.
---

# GeometryForge

Use the user's own agent harness for conversation, modeling decisions, code authoring and execution. The optional viewer only manages projects and inspects results. No API key, model provider, or embedded agent is needed.

## Establish the project

Run `geometryforge doctor`, then `geometryforge context <project>` for an existing project. If the command is missing, install the GeometryForge package from its checkout with `uv pip install -e /path/to/GeometryForge[viewer]` in the chosen environment; viewer is optional. Do not install bpy or hou in host Python.

For a new project, establish the brief, dimensions, intended use, bed/nozzle constraints, execution backend, and deliverables: `geometry`, `blender`, `houdini`, or `both`. Preserve explicit user choices. Ask only for material missing decisions. Create an empty project or copy a bundled example using `geometryforge init <folder> --example desk_organizer --deliverables both`. Record dimensions in parameters.json and choices in decisions.json. Unavailable requested applications must be reported, not silently substituted.

Read [contracts](references/contracts.md) when authoring a project. Read [Blender](references/blender.md) or [Houdini](references/houdini.md) for the selected backends, and [printing](references/printing.md) for print deliverables.

## Revise and verify

Start each resumed modeling task with `context`. Native working files, parameter choices, stale outputs and safe points belong to the project, not conversation memory. Read the referenced latest/safe run when its detailed evidence matters.

Run `geometryforge plan <project>` before execution. Use the smallest meaningful part selection; maintain source, parameter, dependency and interface-check declarations as geometry evolves. A new run record does not imply rebuilding the whole model. Example: `geometryforge run <project> --parts fairing`.

On manual file changes, follow [revisions](references/revisions.md). Continuing an edited native scene is allowed. Never regenerate pristine geometry merely to perform full checks. `geometryforge verify <project> --full` verifies the working scenes. Explain uncertain scope and offer fuller verification or investigation rather than silently launching expensive work.

Deliver printable artifacts, requested native files, measured check results, and the viewer/project reference. Distinguish fresh checks, reused evidence, candidates and SAFE POINTS. Renders show appearance; they do not establish fit, wall thickness or physical print success.

## Both native backends

Build meaningful Blender structures and Houdini SOP networks with shared named interfaces. A mesh imported into a second app is not equivalent native construction. After manual changes, retain both versions, identify which is authoritative, and ask about ambiguous reconciliation. Reconcile through explicit project recipes or native edits; never claim automatic history translation. A partial backend run remains a candidate until every requested backend is current and passes shared checks.
