# Reference-driven surface modeling

Use this workflow for close-up hard-surface assets whose identity depends on compound curvature, panel transitions or layered mechanical construction. Blender Python and the GeometryForge helpers are different levels of access: the helpers are conveniences, not a modeling vocabulary limit. Background Blender can build meshes, curves, modifiers and Geometry Nodes.

## Why top-down

One monolithic subdivision mesh that must carry both broad curvature and every lamp recess and vent stays simplistic: dense local loops propagate across the hull and pinch it. Independent high-detail parts drift apart: placed by bounding boxes and scalar datums, separately lofted panels break curvature at every boundary. The fix is the automotive master-model split:

1. **Curvature authority:** one hidden master hull.
2. **Panel topology:** panels sliced from the master and shrinkwrapped back onto it.
3. **Mechanical detail:** parts bound to interface rings exported by their parents.

The [gates](gates.md) enforce this order.

## Gate 0: calibrated reference

1. Start with `context`, the accepted reference review and the viewing distance. Name the primary identity view. Treat generated alternate images and generated meshes as interpretations; note their disagreements rather than averaging incompatible shapes.
2. Pick datums visible in the primary view whose 3D positions you can state: pad or wheel centres, overall length and width extremes, nose tip, roof peak. Store `world_mm` (or `{"param": "..."}` from parameters.json) and the pixel of each in `references/correspondences.json`. Add a lens prior when the datums are nearly coplanar.
3. Run `geometryforge calibrate`. Inspect the overlay (red picks, blue reprojections, green feature curves, yellow datum box). Fix bad picks rather than raising `max_rms_px`.
4. Solve each supplementary view against the same datums. Model nothing from a view flagged `inconsistent` until its proportions are normalized to the primary proxy or the view is replaced.

## Gate 1: master hull

- Build one closed, low-poly quad cage for the entire exterior skin, from nose to tail and roof to lower skirt: `api.surf.master_hull(name, verts, faces, regions={...}, creases=[...], levels=4)` (or synthesize multi-frequency creases, taut facet planes, and semantic regions from a base cage with `api.surf.inflected_master_hull(...)`; see [procedural paneling](procedural-paneling.md)). It has no openings, panel gaps or mechanical detail. Name the faces of each future panel and opening as regions now.
- Hold styling breaks (a chine between upper hull and skirt, a beltline) with edge creases, not congested support loops. Keep even quad flow running uninterrupted over the hull. Keep poles off tight curvature, because panels shrinkwrap poorly near them.
- Review it alone (`selection.roles = ["guide"]`) with zebra, silhouette and overlay modes, from the calibrated camera and the `survey21` preset. Zebra bands should flow without breaks or kinks across shoulders and crowns. Iterate until the calibrated silhouette IoU meets the gate and the overlay lines up roof roll, pillar widths, crown and taper.
- The master stays hidden and unrendered (role `guide`). After acceptance it is locked.

## Gate 2: panels and pockets

```python
s = api.surf
guide = bpy.data.objects['Master hull']
body = s.slice_panel(guide, 'front_body', openings=['lamp_l', 'lamp_r'], name='Front body')
s.inset_panel_perimeter(body, 8.0, gap=1.8)                 # control loop + seam retreat
s.tighten_panel_corners(body, 15.0)                         # straight outline: even seams to their ends
s.tighten_opening(body, 'lamp_l', 20.0)                     # rectangular opening instead of an oval
s.build_guide_mesh_stack(body, guide, thickness=3.0, bevel_width=.6, subsurf_levels=3)
s.recessed_pocket_extrude(body, 'lamp_l', depth=60, draft_angle_deg=5, fillet_mm=12)
s.extract_interface_ring(body, 'lamp_l', name='_interface_lamp_l')             # rim: openings and pull axis
s.extract_interface_ring(body, 'lamp_l_floor', name='_interface_lamp_l_seat')  # seat for contents
```

- `slice_panel` copies the region's cage faces and conforms them onto the master surface. A limit surface lies inside its control cage, so unconformed cages leave partly weighted vertices proud.
- `slice_panel` keeps the master's creases, so the panel subdivides to the master's own limit surface. `tighten_panel_corners` and `tighten_opening` add support cuts beside panel and opening corners; an opening on one or two master faces otherwise subdivides into an oval. A corner distance too tight for the panel thickness folds the solidified shell; `build_guide_mesh_stack` adds a `Shell guard` (INSIDE shrinkwrap on the inner shell) that moves such vertices back onto the master, so `recess` only reports proud vertices on the outer skin.
- `build_guide_mesh_stack` gives each panel the same stack: Subdivision → Shrinkwrap onto the master (vertex group `guide_bound`) → Solidify inward → Bevel by weight. Every panel's exterior lies on the one master, so highlights continue across panel gaps.
- The border control strip must stay wider than the bevel after subdivision (strip / 2^levels > 1.25 × bevel). The helper refuses narrower combinations. Raise the panel level where chords sag on tight curvature; `coverage` measures it.
- An opening that crosses a panel line (a vent across a seam, a lamp in a corner) cannot be a pocket in either panel. Slice its own region as a panel, `inset_panel_perimeter` it with the seam gap, `open_well` it, bind it and extrude the pocket with `floor=True`. `tighten_panel_corners` on the neighbours keeps the master from showing at the three-panel corners.
- `recessed_pocket_extrude` forms lamps, vents and sockets as painted returns. The rim stays flush at weight 1. The explicitly built quarter-circle fillet, drafted wall and open seat sit at weight 0 and keep their constructed shape; partial weights would drag the return back onto the master and fold it. A `Pocket guard` Shrinkwrap (INSIDE) after the master lock pulls back any subdivided vertex between rim and first ring that would stand proud. Place lenses, bearing races, glands and webs behind the return; do not mount a box proud of the skin.
- Panels and openings are never lofted independently. A missing panel or open belly gap shows up in `coverage`.

## Gate 3: mechanical detail

- Children bind to their parent's exported ring with `bind_to_ring(child, ring, lap=..., interfaces=[child_ring])`, never to scalar coordinates. Create the child's own ring with `local_ring` so `mating` checks can measure axis, centre and lap.
- Seat fasteners, decals and plates on the evaluated parent with `project_detail`.
- For machinery mounted to a body, model a readable load path behind the fairing return: receiving housing, bearing or pivot, retaining flange, fasteners, and webs into a beam or bulkhead. Show it only where the reference shows it. Terminate hoses in glands. Review interfaces both isolated and mounted. Mechanical plausibility is a visual requirement; never claim engineering testing from a check.

## Choose native construction for the shape

- **Subdivision cages:** deliberate quad topology, sparse cages, live Subdivision Surface. Support loops and selective creases preserve intentional angular transitions; uniformly subdividing an intersected Boolean block rounds the wrong features.
- **Crowned patches:** `api.surf.patch(name, fn, u, v, segments)` and `api.surf.loft(name, rings)` build editable quad cages; `geometryforge.sections` supplies chamfered and superellipse ring profiles.
- **Swept trim:** `api.surf.sweep` builds evaluated tube meshes (bevelled curves are not mesh evidence). Dark painted lines are not recessed channels.
- **Selective Booleans:** genuine through-cuts after broad form. For panel boundaries, prefer surface-derived panels over hundreds of intersecting cuts.
- **Rotational and repeated detail:** lathes and controlled repetition, after the main profile is right. More bolts cannot fix a wrong profile.

## Protect designed edges

Classify reference edges before rounding: a broad crown, a small manufacturing radius and a deliberate top/chamfer/side break need different construction. Preserve feature lines with explicit section vertices, creases or support loops. Do not smooth across a designed chamfer merely because the object is convex. A weighted normal changes shading, not the lost shape.

When a user accepts a component, retain its native checkpoint and reuse its editable geometry. Record source hashes and compare evaluated geometry after intentional transforms.

## Repeatable review evidence

`geometryforge review <project> --scene <saved.blend> --config <views.json> [--blind] [--baseline <id>]`

```json
{
  "version": 1,
  "views": [
    {"id": "primary", "camera": {"ref": "primary"}, "modes": ["clay", "zebra", "silhouette", "overlay"]},
    {"id": "belly_cut", "section": {"axis": "x", "offset_mm": 2400}, "modes": ["clay", "part_id"],
     "camera": {"position_mm": [9000, 0, 600], "target_mm": [0, 0, 600], "projection": "orthographic", "ortho_scale_mm": 6000}}
  ],
  "presets": [{"preset": "survey21", "bounds_mm": "safe_point", "camera_refs": ["primary"], "modes": ["clay", "zebra"]}]
}
```

- **Modes:** `clay`, `glossy`, `silhouette`, `wireframe`, `zebra` (reflection stripes: positional breaks jump, tangent breaks kink, curvature-continuous surfaces flow), `normal` and `part_id` (exact pixels for `review-diff`), and `overlay` (feature curves and the selection box projected onto the render and, for calibrated views, onto the reference).
- **Cameras:** `camera.ref` uses a calibrated camera, its reference crop and its mask. Silhouette IoU and `delta_iou` against the previous matching review are recorded only for views with a mask.
- **Sections:** `section` cuts the evaluated copies for X-ray checks of belly closure and wall thickness. `selection.roles` adds hidden `guide` objects.
- **Presets:** `survey21` gives 6 orthographic, 8 three-quarter, calibrated, 3 section and 3 close-up views; `standard6` and `survey` are also available.
- **Blind review:** `--blind` keeps metrics out of the sheets and the command output. Critique first, then read `report.json`.

Review never runs builders, saves scenes or changes safe points. Use identical cameras and a fixed `studio` for before/after comparisons. A later native edit needs new evidence.

## Optimize after visual review

Preserve the detailed editable master and derive a separate destination copy. Triangle budgets are project settings (`decisions.game.triangle_budget` or the overriding target contract). Change them explicitly if needed; do not weaken defaults or remove reference-critical detail just to pass. Global cleanup and remeshing can collapse designed seams; prefer local construction fixes and compare the same silhouettes after reduction.

Official references: [Subdivision Surface](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html), [Shrinkwrap](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/shrinkwrap.html), [Solidify](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/solidify.html), [Bevel](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html), [Houdini PolyReduce](https://www.sidefx.com/docs/houdini/nodes/sop/polyreduce.html).
