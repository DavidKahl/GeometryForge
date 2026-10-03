# Astraeus Heavy Lander

A 480 mm multipart model based on the supplied concept sheet, designed for a Bambu X2D with a 0.4 mm FDM nozzle and 256 mm bed.

The native models retain a hollow segmented hull, weld seams, recessed fasteners and hatches, a hex-tile sleeve, separate dark nose cap, swept fins and canards, seven hollow engine bells, and deployed landing legs. See [print and assembly instructions](PRINT_AND_ASSEMBLE.md) and the [reference interpretation](references/design-brief.md).

This folder is a standalone GeometryForge project. The toolkit stays separate from this model's construction code. `project.toml` declares stable part IDs, source/parameter dependencies, and interface checks. `decisions.json` records the requested printer and deliverables.

## Reproduce or revise

Install GeometryForge and this project's `requirements-checks.txt` into a Python 3.12 environment. Set `GEOMETRYFORGE_BLENDER` if Blender is not on PATH; GeometryForge detects a local Houdini installation and its license capabilities.

```powershell
geometryforge context .
geometryforge plan .
geometryforge run .
```

For a procedural local edit, change its owning module under `models/`, inspect the plan, and run again. For a native edit, save the working scene and request context before choosing how to reconcile it. Do not overwrite retained snapshots in `.geometryforge/runs`.

The project-specific checker measures exported geometry and uses Manifold 3.5.4 for solid-intersection checks. Local Bambu Studio slicing evidence is additional to the safe-point contract; slicer scripts never send a print job. `tools/slice_check.py` resolves presets from the installed Bambu Studio rather than redistributing vendor preset files. Its CLI usage follows [Bambu Studio's command-line documentation](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage).

Validated release files are under `deliverables/`. Working source and editable scenes remain available in this folder for the next agent-led revision.
