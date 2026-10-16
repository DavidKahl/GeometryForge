# Houdini

Set GEOMETRYFORGE_HOUDINI to the executable or installation directory. On Windows standard Side Effects installations are discovered. Host Python never imports hou.

The adapter owns a dedicated Houdini GUI session with authenticated loopback JSON jobs. It saves recovery files before replacing an unsaved scene and never attaches to or terminates unrelated Houdini windows. Use `geometryforge session status|stop` for the owned session. Startup/license prompts may need the user's attention.

Use native editable SOP construction under /obj/geometryforge; the root carries geometryforge_units='mm'. Owned containers carry gf_owner; printable containers carry gf_role='Printable' and JSON gf_export metadata, and an OUT node. Native helpers create these structures. The supported OBJ interchange route feeds STL/3MF validation. Actual license category selects .hipnc, .hiplc or .hip; no license restriction is bypassed.

Gates and typed checks work with Houdini output. Register a hidden master as role `guide`, its panels as `design`, and mating rings as role `interface`: a polyline or closed polygon under an OUT node, with `axis` in its metadata. Float point attributes named `guide_bound`, `gf_inner`, `gf_solidify_rim`, `gf_pocket` or `gf_*` reach the checks as surfacing weights. The `api.surf` helpers are Blender-only in this release; build the equivalent SOP networks directly, for example Subdivide, Ray (minimum distance) blended by `guide_bound`, PolyExtrude thickness and PolyBevel by group. Gate reviews render the Blender scene, so a Houdini-only route cannot satisfy a gate review requirement.

An inspection can evaluate the complete scene; this does not mean rebuilding all SOP networks or regenerating all print deliverables. Native launch/cook time remains part of incremental-run cost.
