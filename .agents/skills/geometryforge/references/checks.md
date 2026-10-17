# Typed surface checks

A Boolean overlap only proves that two meshes touch. An agent can satisfy it by pushing a flange into the neighbour, while the surfaces still meet at a visible angle. Typed checks measure how surfaces meet. They run on evaluated design evidence in the host, so Blender and Houdini output are measured by the same code.

```toml
[checks.seam_front_skirt]
kind = "seam"                       # seam | recess | mating | global | detail
parts = ["front_body", "skirt", "master_hull"]
mode = "enforce"                    # enforce fails the run; measure records misses (gates still require them)
[checks.seam_front_skirt.spec]
a = {part = "front_body"}           # optional: objects = [...], roles = [...]
b = {part = "skirt"}
master = {part = "master_hull"}     # selects the hidden guide objects
[checks.seam_front_skirt.thresholds]
gap_max_mm = 5.0                    # per-check override
```

Thresholds resolve as toolkit defaults, then `parameters.json` `gf_thresholds.<class>`, then the check's own `thresholds`. The effective values are stored with each result and are part of its cache key. **The defaults are starting values from an unverified engineering report on agentic surfacing; set limits that suit the asset and record why.**

## seam: exterior panel joints

Measures the flush exterior skin: vertices within `exterior_band_mm` of the master, facing within `exterior_normal_deg` of it, at full guide weight and not on the solidify shell or rim.

| Measure | Default limit | Meaning |
|---|---|---|
| `master_deviation_max_mm` | 0.25 | skin vertices leaving the master |
| `step_max_mm` | 0.5 | height offset across the seam along the master normal |
| `gap_min_mm`–`gap_max_mm` | 2–4 | visible gap between the flush skins, bevel roll-off included |
| `normal_angle_p95_deg` | 2.5 | tangent break across the seam, beyond the master's own turn |
| `curvature_ratio_p95` | 0.08 | `|κa−κb| / max(κa+κb, 2·flat_curvature_per_mm)`, probed `probe_mm` (15) across the seam |

Seam pairs are mutual nearest border vertices; fewer than `min_pairs` means the parts do not share a seam. An optional `region_mm = [[x0, y0, z0], [x1, y1, z1]]` in the spec measures one stretch of the seam, for example away from a junction with a well that its own `recess` check covers. Vertices are measured, so chords between them can still sag: pair seams with a `coverage` check. Curvature flatter than `flat_curvature_per_mm` (R ≥ 2 m by default) is compared against that floor, because two nearly flat sides differ only by discretization noise.

## recess: pockets, lamps, sockets

Spec: `panel`, `master`, optional `ring` (the rim interface ring carrying the pocket's pull axis), `contents` (lenses, races, bosses that must stay inside) and `region_mm` (`[[low], [high]]` box: measure only the pockets inside it, e.g. glazing separately from a socket on the same panel). Needs `guide_bound` weights; helper-built pockets also mark `gf_pocket`.

| Measure | Default | Meaning |
|---|---|---|
| `proud_vertices` / `protrusion_max_mm` | 0.05 | panel or contents outside the master envelope |
| `rim_step_max_mm` | 0.05 | flush rim (weight 1) off the master |
| `draft_min_deg` | 3 | pocket wall angle to the pull axis; negative is an undercut |
| `fillet_min_mm` | 5 | section radius of the painted return (rate of change of the angle to the pull axis); plan-view corners are not counted |

Fillet and draft are estimated from faces, so they depend on mesh density; review close-ups as well.

## mating: interface rings

Spec: `parent` and `child` interface rings, optional `skin` and `child_solids`. **`lap_min_mm` and `lap_max_mm` are required per joint.** Measures the axis angle (default ≤0.1°), lateral centre offset (≤0.05 mm), engagement lap along the parent axis, and child edges piercing the exterior skin (0). Rings bound with `api.surf.bind_to_ring` pass by construction; the check catches later edits that move them.

## detail: the inventory of real detail

Surface checks reward clean surfaces, so detail can silently fall away while every check passes. A `detail` check makes the accepted detail inventory measurable.

```toml
[checks.detail_skirt]
kind = "detail"
parts = ["skirt", "fasteners"]
[checks.detail_skirt.spec]
parent = [{part = "skirt"}]                 # the skin the details sit on
features = [{part = "fasteners"}]           # objects carrying metadata feature tags
inventory = [
  {id = "skirt_bolts", feature = "bolt", min_count = 60, relief_mm = [3, 12]},
  {id = "left_vents", feature = "vent", min_count = 2, region_mm = [[-3000, 0, 0], [3000, 1500, 1200]], density_min_per_m2 = 0.5},
]
```

- **Count:** each separate mesh island (after welding coincident vertices) of objects tagged `feature` counts once, so a joined bolt row of 60 heads counts 60. Tag objects with `register_output(..., feature="bolt")` or pass `feature=` to any `api.surf` detail primitive (`bolts` sets it by default).
- **Seated:** every island needs a vertex within `seat_mm` (default 1.0) of the parent skin; floating parts fail with their locations.
- **Relief:** optional `relief_mm` bounds each island's largest distance from the skin (height of a bolt, depth of a vent).
- **Region and density:** `region_mm` limits an item to a box. `density_min_per_m2` divides the count by the parent skin area in that box.
- `untracked_tags` lists feature tags present but missing from the inventory.

The final geometry gate must declare at least one `detail` check, or `gate check` stays not ready. Build the inventory from the clean reference set (every region, with counts) and have the user accept it before Gate 1.

## global

- `test = "open_edges"`: open boundary edges on `targets` (optionally within `region_mm`). Use it to keep the master watertight; signed distances assume a closed master.
- `test = "coverage"`: samples the master and reports area farther than `cover_tolerance_mm` (3) from any panel. It catches unsealed belly-to-bumper gaps and chord sag on tight curvature. Declare `openings` as interface rings so pockets do not count. Poles (extraordinary vertices) under tight curvature shrinkwrap poorly; move them or raise the tolerance locally with a recorded reason.
- `test = "silhouette_iou"`: rasterizes `targets` through calibrated `camera` and compares against its mask (default limit 0.90; `delta_iou` against the previous run). It defaults to measure mode and needs `geometryforge calibrate` with a mask.

## Replacing Boolean contact checks

| Old project check | Typed replacement |
|---|---|
| panel/fairing overlap volume > 0 | `seam` against the master + `coverage` |
| clearance cut + flange contact | `recess` with contents and the rim ring |
| collar/armor/hose overlap | `mating` with lap window and skin crossings |
| side-by-side screenshot | calibrated `silhouette_iou` + blind review |

Functional `verify(payload)` checks (dimensions, joints, fits) remain valid; declare them alongside.
