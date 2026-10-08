# Falcon 9–style printable display model

An original simplified interpretation, not an engineering replica or an affiliated SpaceX product. Default assembled body height is 205 mm, excluding engine protrusions. Dimensions are editable in parameters.json; radius and stage/fairing dimensions control scale. Stand, four decorative legs and a two-piece joint coupon are laid out beside the rocket for inspection.

Print each stage upright. The lower stage has protruding engines: use supports beneath the tank base or orient/support it in your slicer. Fairing prints socket-down; coupon and stand print base-down. Print the coupon first to tune clearance for your machine. Insert the rectangular stage keys into their matching sockets. Seat the lower stage in the stand. The legs are separate decorative pieces intended for adhesive mounting; they have no load-bearing latch.

The default 0.25 mm per-side clearance is a starting value, not a fit guarantee. Both native implementations use the same named interfaces and independent measured section checks. No physical print is claimed.

## Incremental walkthrough

1. Run `geometryforge run .` to create both native outputs and the first SAFE POINT.
2. Change only fairing_height in parameters.json (for example 40 to 45).
3. Run `geometryforge plan .`, then `geometryforge run .`.
4. Inspect rebuilt_parts: only fairing is rebuilt. Its exports/preview and upper_joint check are refreshed; unrelated exports and checks reuse valid evidence.
5. Change clearance to 0.3: the two stage joints, stand and coupon are affected. Their measured interface checks must run again.
6. To use a manual scene edit, save the working file and run `geometryforge run . --backend blender --source scene`. The other native output remains stale until reconciliation. `geometryforge verify . --backend blender --full` performs every Blender check without rebuilding from scripts.
