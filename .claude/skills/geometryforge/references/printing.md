# Model for the actual printer

Use this reference before deciding part construction, splitting or surface detail. Printer settings are design inputs, not a final export label.

## Establish the process envelope

Reuse `decisions.json` and `context`; ask only for missing information that materially changes the model. A printer name does not establish the installed nozzle, filament, build plate or available support material. Prior examples and CLI initialization defaults are not confirmed user choices.

Record the relevant facts under `decisions.print`, preserving `bed_mm` and `nozzle_mm` for toolkit compatibility:

| Record | How it affects modeling |
|---|---|
| Technology, exact printer/variant, installed nozzle or resin process | Choose the appropriate manufacturing constraints; FDM line-width rules do not apply to resin. |
| Usable X/Y/Z, bed shape, exclusion zones, active tool restrictions | Size parts in their actual print orientation. Reserve space for brims, supports and any purge structure. |
| Material, intended loads/environment, cosmetic priorities | Choose wall/strut targets, joint style and layer orientation; distinguish display detail from load-bearing structure. |
| Slicer/version and matching printer, material and process presets | Establish intended layer heights, extrusion widths, supported features and support behavior. Resolve inherited preset values before interpreting them. |
| Support preference and available materials/tools | Decide whether to reorient, split, chamfer or use accessible supports; do not assume soluble supports or a second material system. |
| Fit calibration, assembly/glue preferences | Choose clearance per side, lead-ins and test coupons rather than one universal tolerance. |

For each consequential value record its provenance: user-confirmed, local preset path/name/version and hash, manufacturer URL and access date, measured coupon, or explicit assumption. Do not silently replace a user-specified constraint with a contradictory preset. Keep the conflict visible and resolve it before relying on the disputed capability. Unknown settings can remain provisional while independent work continues; do not describe them as verified.

## Turn constraints into geometry

Record a concise print plan in `decisions.print.part_plan`, keyed by stable part ID. Include orientation, bed-contact face, support strategy and removal access, critical features/interfaces, assembly order, and required checks. Use it to make construction choices:

- **Size and placement:** assess the oriented part plus process margins against the usable volume and exclusion zones. Split an oversized model at sensible joints while preserving the requested assembled dimensions. A rectangular bounding-box pass does not check a shaped bed, tool exclusions or a complete supported plate layout.
- **FDM detail and walls:** use intended extrusion width and layer height, not nozzle diameter alone. Choose wall/strut thickness for the needed toolpaths and load; choose raised/recessed detail for resolvable XY width and Z layers. For example, three nominal 0.45 mm paths suggest a starting wall near 1.35 mm, not a guaranteed printed strength or an exact requirement for variable-width slicing. Verify critical features in the sliced paths. Enlarge, deepen, simplify or make a feature separate when its literal scaled form would disappear or become fragile.
- **Orientation and strength:** keep assembly coordinates separate from print orientation. Check the actual first contact, unsupported islands and layer direction at stressed roots. A fin with relief on both sides is not flat on the bed just because its overall thickness is small. A wide foot can lift an entire sideways leg off the plate. Prefer a flat back, separate foot, or a justified support plan.
- **Overhangs and cavities:** use process-specific evidence for bridge spans and overhang limits; record whether angles are measured from horizontal or vertical. Compare reorientation, chamfers and splitting with support cost and surface damage. Ensure supports can actually be reached and removed from hollow shells and blind sockets. Support generation alone does not prove this.
- **Joints and assembly:** check evaluated wall thickness at collars, sockets, grooves and tapers, plus solid interference beyond the nominal tab. Include lead-ins and first-layer effects where relevant. Check insertion/removal paths and assembly order, not only the final pose. Derive the coupon from the actual interface, orientation and intended material; state whether clearance is radial/per-side or diametral/total.
- **Color and other processes:** separate color parts or allow finishing when that meets the brief; do not assume multicolor hardware. For resin, replace extrusion assumptions with process-specific feature/support limits and account for drainage, trapped resin, cleaning and support removal in hollow parts.

Use a low-detail assembly to establish placement, joints and print splits first. Prototype uncertain fine detail, an overhang, or a stressed connection as a small representative section before expensive full-model iteration. Preserve visual priorities when making print adaptations and explain consequential departures from the reference.

## Evidence and delivery

Declare project-specific required checks before claiming those requirements verified. Generic toolkit checks cover watertightness, winding, positive volume, body count, dimensions, rectangular bed fit and STL/3MF readback. They do **not** automatically establish minimum wall thickness, strength, support removal, printable detail or assembly clearance. Inspect actual evaluated geometry; author relevant functional checks and record any manual review separately.

For complex or uncertain print features, use an available local slicer with the matching effective settings. Read back the exported STL/3MF and inspect oriented placement, first layers, missing/thinned features, islands, bridges, supports and joint surfaces. A successful exit or G-code file is only evidence that slicing ran; inspect critical toolpaths and warnings before marking slicer review complete. Retain input hashes, settings/version, part/plate inventory, findings and any time/material estimates. Clearly label assumed filament or plate settings.

Primary deliverables remain millimeter STL/3MF and requested native scenes. Local slicing may generate diagnostic G-code; it is not an automatically approved printer job. Material/filament metadata may need reassignment in another slicer. Provide orientation, support-removal and assembly notes, plus relevant fit coupons. Distinguish **geometry checks passed**, **slicer/toolpaths reviewed**, and **physically test-printed**. A SAFE POINT means the registered checks passed, not a physical-print guarantee. If the slicer is unavailable or a limitation remains unresolved, deliver the useful candidate/evidence with that gap stated; do not substitute a render or a generic preset for missing verification.

## Printer and process changes

On a change, compare the old and new effective settings and reassess affected parts: a smaller bed can change splits, a larger nozzle can erase relief, another material can change joint clearance and structural decisions, and a no-support request can change orientation or construction. Keep unrelated geometry and manual edits intact.

Promote geometry-driving limits into named `parameters.json` entries and declare their affected parts/checks in `project.toml`. Check payloads contain parameters and evaluated objects, not `decisions.print`; a descriptive limit in decisions alone cannot drive a builder or verify a feature. Snapshot any extra project-local inputs used by builders/checkers through their declared sources. See [contracts](contracts.md).

Changing `decisions.print` invalidates export/check evidence in the toolkit, but does not by itself select new builders or redesign parts. Inspect `plan`, update the relevant parameters/recipes and explicitly select affected parts where needed. Re-slice affected outputs when geometry, print orientation or effective process settings change. Keep earlier physical coupon results associated with their original printer/material/process. Reuse only evidence that still supports the current choices.

## Source guidance

[Prusa's modeling guidance](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135) discusses orientation, walls, tolerance and support tradeoffs; its printer-specific examples are not universal capabilities. [Bambu Studio's CLI documentation](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage) describes effective/full preset input for local slicing. Use documentation or installed profiles matching the user's actual process and version.
