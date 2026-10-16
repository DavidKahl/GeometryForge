# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

## [1.2.0] - 2026-10-16

### Added

- **Per-gate review IoU:** `[gates.<id>.review] iou_min` scores a gate's review below the project default, for early gates whose reference masks include parts that later gates add.
- **Format 3 modeling gates:** `[gates.*]` order calibration, master hull, panels and detail.
  - Only accepted gates and the active gate are buildable; later parts are dormant and refused.
  - Accepted geometry is locked; a changed locked part makes the run a candidate.
  - `gate status|check|accept|reopen|template` manages them. Acceptance records hashes, check measurements, review and calibration evidence, critique and the quoted approval.
  - Dependent game/print routes wait for the final gate.
  - `migrate --format 3`.
- **Typed surface checks** (`kind = seam | recess | mating | global`), run on evaluated evidence from either backend:
  - master deviation, seam step/gap/tangent/curvature;
  - pocket protrusion, rim flushness, draft and return fillet;
  - ring axis/centre/lap and skin crossings;
  - open edges, master coverage and calibrated silhouette IoU with delta.
  - Thresholds layer toolkit defaults (starting values from an unverified engineering report), `parameters.json` `gf_thresholds` and per-check overrides. They are recorded with results and are cache inputs. Measure mode records misses without failing runs.
- **Reference camera calibration:** `geometryforge calibrate` solves Blender-compatible cameras (pose, focal length, optional principal point) from datum correspondences. It writes `references/cameras.json` and reprojection overlays, and flags supplementary views that disagree with the primary.
- **Review additions:**
  - `zebra`, `normal`, `part_id` and `overlay` modes; section cuts; calibrated `camera.ref` views; guide-role selection;
  - `survey21`/`standard6`/`survey` presets;
  - silhouette IoU with baseline deltas;
  - `--blind` output;
  - `review-diff` region-invariance checks.
- **`api.surf` Blender surfacing helpers:** master hull with regions and creases, conforming panel slicing, perimeter control loops with seam gaps, the Subdivision→Shrinkwrap→Solidify→Bevel guide stack, drafted recessed pockets, interface ring extraction, ring binding, detail projection, patch/loft/sweep. `geometryforge.sections` has the shared ring/section math.
- **New roles:** `guide` (hidden master surfaces) and `interface` (edge-only rings). Design evidence carries surfacing point attributes only when present, so existing evidence hashes are unchanged. Houdini extraction supports both roles; `api.surf` is Blender-only for now.
- Dedicated three-gate native fixture (`tools/fixtures/surfacing_project`) and opt-in native surfacing test.
- Skill: calibration intake step, gated workflow, recessed-fairing rule, interface-ring binding, blind critique before metrics; new `gates.md` and `checks.md` references; rewritten surface-modeling reference.

### Fixed

- **Panel corners stay sharp:** `tighten_panel_corners(panel, corner_mm)` adds support cuts beside each outer corner of a panel (turn measured in the surface's tangent plane), so subdivision keeps panel outlines straight and seams even to their ends. A vertex crease was tried first and flipped the solidified shell outward at acute corners.
- **Rectangular openings:** `tighten_opening(panel, opening, corner_mm)` adds support cuts beside each plan corner of an opening rim, so openings sliced from one or two master faces stay rectangular instead of subdividing into ovals. Pocket rings slide their corner-adjacent vertices with the corner, so deeper rings keep the rim's corner shape instead of undercutting it. Corner distances that are too tight for the panel thickness fold the shell; the hover taxi uses 160 mm on windows.
- **Panels keep the master's creases:** `slice_panel` no longer drops the master's edge creases, so panels subdivide to the master's limit surface and shrinkwrap only corrects small offsets (nacelle coverage misses fell from 1.37 m2 to 0.28 m2).
- **Seam gap at the visible edge:** the skin border sits where the normal limit is crossed along the edge that runs most nearly across the border, independent of how coarse or skewed the subdivided strip is. Step and curvature still compare the flush skin vertices.
- **Pocket returns never stand proud:** `recessed_pocket_extrude` adds a `Pocket guard` Shrinkwrap (INSIDE mode, `gf_pocket` group) after the master lock. Subdivision creates vertices between the locked rim and the free first ring with partial `guide_bound`; where the cage bulges past the master they stayed up to 0.64 mm proud on the hover taxi's rear sockets. The guard moves only vertices outside the master back onto it.
- **Viewer hides guide surfaces:** master hulls and interface rings no longer draw over the panels that cover them (the hover taxi showed its smooth master instead of windows and seams). A **Guides** toggle shows them on request.
- **Viewer reports each route:** the banner lists every output route with its own state, for example `design: current · print: not built`, instead of marking a finished design route out of date while a later route is unbuilt.
- **Seam gap on staggered borders:** seam checks pair each border vertex with the nearest point on the other panel's border edges and measure the gap to that point. Coarse or differently subdivided borders no longer drop out of pairing or count their along-seam offset as gap. Border vertices whose gap vector runs along their own border (panel corners) are excluded.

- Recipes now receive parts dependencies-first. Alphabetical order could build a dependent part against geometry that its dependency's rebuild then deleted.
- Failed project checks keep their measurements in the run record instead of only an error string.

- `geometryforge review`: disposable Blender rendering of saved scenes with repeatable cameras, part/object selection, clay/glossy/silhouette/wireframe images, reference contact sheets and hashed provenance. Review does not run builders, save scene edits or change safe points; failed reviews retain evidence.
- Reference-driven surface-modeling guidance covering compound curvature, subdivision cages, surface-derived panels, swept trim, real geometric detail, staged visual review and detail-preserving optimization.
- Dedicated native review fixture and input/provenance/failure regression tests.
- Surface-modeling guidance covers feature-edge protection, shared mating sections and visible structural load paths, learned from two ungated hover-taxi studies (kept locally, not in the repository).
- **Showcase: `projects/hover_taxi_gated`.** A hover taxi built through all four gates in Blender, with its acceptance records, blind critiques and a same-camera comparison against the ungated studies.

## [1.1.0] - 2026-10-14

### Added

- Backward-compatible v2 projects with independent game/print targets, optional shared design, output/source mappings and route safe points.
- Explicit migration backups, frozen derivation recipes/scales, route-aware scene adoption/restoration and incremental preparation stages.
- Blender game extraction preserving UV seams, normals/tangents, materials and placement; editable preparation, PBR baking, LOD and convex collision helpers.
- Conventional/Nanite desktop profiles; FBX native read-back, attribute-preserving GLB previews, DirectX/OpenGL normal variants, ORM textures and hashed portable packages.
- Optional Unreal 5.8 imports, saved-asset verification, offscreen review/editor profiling and versioned managed namespaces protecting artist changes.
- Native Houdini SOP attribute extraction and license-aware production FBX/BAKE interfaces; commercial export/baking coverage remains explicit.
- PBR game inspection, wireframe, LOD/collision, pivots/sockets, representation comparison and package/import evidence in the local viewer.
- Mechanical housing example, game regression/browser tests and dedicated native validation tooling.
- Skill reference intake: explicit print/game/both question, per-part reference coverage review, requests for missing views or explicit acceptance of listed assumptions before modeling, recorded as `decisions.reference_review`.

### Preserved

- v1 print behavior, editable native construction, retained scenes/snapshots, print exports/kits and agent-owned modeling. No embedded provider, credentials, chat, build controls or autonomous queue.

## [1.0.0] - 2026-10-09

First public release.

### Added

- Agent skill for Claude Code and Codex: brief, printer-aware planning, native modeling, incremental runs and honest reporting.
- Toolkit with incremental runs, evidence reuse, safe points, candidates, restore and adoption of manually edited Blender/Houdini scenes.
- Native Blender and Houdini backends with cross-application parity checks.
- Print exports (STL, 3MF) with mesh, bed-fit and round-trip checks, plus project-defined functional checks.
- Whole-model 3MF files on every run: an assembled model and a print kit with per-part filament slots. Optional Bambu Studio packaging arranges the kit onto plates with filament colours and verifies the result.
- Local browser viewer: projects, runs, part selection and isolation, assembly/print pose, side-by-side and overlay run comparison, filament colours, image viewer, downloads.
- `geometryforge doctor` reports Blender, Houdini and Bambu Studio.
- Showcase project: Astraeus Heavy Lander (22 parts, Blender + Houdini, four-filament plan).
- Bundled example: desk organizer.
- Self-contained browser tests on generated fixture projects, and CI on Windows and Linux.

[1.0.0]: https://github.com/DavidKahl/GeometryForge/releases/tag/v1.0.0
