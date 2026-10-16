# Blender

Set GEOMETRYFORGE_BLENDER to the executable when it is outside PATH or standard install locations. CLI --blender overrides discovery. Background scripts use Blender's bundled Python.

For compound curved reference geometry use [surface modeling](surface-modeling.md). Prefer editable quad cages, surface patches, thickness and swept profiles where they match the form; the toolkit's primitives do not limit direct bpy/bmesh/Geometry Nodes construction. `geometryforge review` evaluates a saved scene in a disposable process for neutral appearance evidence without saving native changes or promoting safe points.

`api.surf` holds the master-hull helpers. All units are millimetres and every result is an ordinary editable modifier stack or vertex group.

- `master_hull(name, verts, faces, regions, creases, levels=4)`: the hidden `guide` role object with a `gf_region` face attribute.
- `slice_panel(guide, region, openings, name)`: conforms the panel cage onto the master and writes `gf_loop_<opening>` groups.
- `inset_panel_perimeter(panel, distance, gap)` and `build_guide_mesh_stack(panel, guide, thickness, bevel_width, subsurf_levels)`.
- `recessed_pocket_extrude(panel, loop, depth, draft_angle_deg, fillet_mm)`: weights `guide_bound` and `gf_pocket`, and stores the pull axis.
- `extract_interface_ring(obj, loop, name)` and `local_ring(name, radius)`: edge-only `interface` role objects.
- `ring_frame`, `bind_to_ring(child, ring, lap, interfaces)` and `project_detail(obj, parent)`.
- `patch`, `loft`, `sweep` and `mesh_object`, plus `feature_curves(features.json)`.

Recipes receive parts dependencies-first, so a dependent part can look up objects built by the parts it declares in `depends`.

Save editable objects, construction operands, modifiers and/or Geometry Nodes. Use the Printable collection and stable gf_part/gf_owner properties. Scene units are millimeters with scale_length=.001 and geometryforge_units='mm'. Evaluated exports include modifiers and instances; save their editable sources. gf_print_rotation_deg changes print exports only. gf_expected_bodies records intentionally separate shells.

The worker opens the selected scene, runs only requested part builders, saves a new native snapshot and reopens it. Revisions must preserve unselected evaluated geometry. For a hand-edited scene, use adopt then --source scene. If procedural inputs changed too, make the choice explicit rather than discarding either version.
