# Blender

Set GEOMETRYFORGE_BLENDER to the executable when it is outside PATH or standard install locations. CLI --blender overrides discovery. Background scripts use Blender's bundled Python.

Save editable objects, construction operands, modifiers and/or Geometry Nodes. Use the Printable collection and stable gf_part/gf_owner properties. Scene units are millimeters with scale_length=.001 and geometryforge_units='mm'. Evaluated exports include modifiers and instances; save their editable sources. gf_print_rotation_deg changes print exports only. gf_expected_bodies records intentionally separate shells.

The worker opens the selected scene, runs only requested part builders, saves a new native snapshot and reopens it. Revisions must preserve unselected evaluated geometry. For a hand-edited scene, use adopt then --source scene. If procedural inputs changed too, make the choice explicit rather than discarding either version.
