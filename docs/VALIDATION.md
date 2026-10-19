# Validation

What has actually been verified, on what, and when. Nothing here claims a physical print. Native validation has only been done on Windows.

## Procedural panel seam recovery (18 October 2026)

The local procedural hover-taxi study exposed seam drift through unprotected region borders, insufficient master tessellation for short curvature probes, warped closed vent floors, and excessive scalar overhead during native evidence comparison.

- Host suite: `uv run python -m pytest -q` — **185 passed, 4 skipped**. The warning is an existing Starlette/httpx deprecation. The procedural host tests also collect through the `uv run pytest` entry point.
- Procedural paneling suite: **8 passed** (seven host tests and one native integration in Blender 5.2.1 LTS). The native scene was saved and reopened and checked for master closure and a measured panel seam, transformed independent topology, a planar pocket floor, louvers, tangent fields and cable routing. Host regressions verify unchanged boundary collars, separated clusters and macro creases pinned before displacement.
- Float-equivalence regressions compare the scalar tolerance with NumPy at tolerance boundaries, NaN/infinity cases, and changed integer topology. A local 300,000-scalar comparison completed in 0.18 s; this is an evidence-comparison measurement, not a whole-model build benchmark.
- Opening coverage rejects points outside the existing plane band and polygon bounds before iterating dense rings. Differential tests on concave openings, including a transformed ring, match the previous full polygon predicate; the complete surface-check suite passed 31 tests.
- The revised master has a retained 26-view clay/zebra/silhouette/overlay review. Its artistic limitations (roof and nacelle highlight unevenness and reduced faceting around protected seams) are recorded in the local critique. A technical pass does not establish visual acceptance.
- The final panel preflight passed **25/25** unchanged checks: 14 seams, eight recesses, two coverage checks and one detail inventory. Maximum measured seam step was 0.0056 mm and master deviation 0.000242 mm. Body coverage had zero uncovered samples at the existing 14 mm tolerance (largest measured distance 10.97 mm); nacelles were within 3.02 mm at their existing 9 mm tolerance. The revised master is a passed design safe point and `gate check master` is ready. Visual approval and formal acceptance remain pending; the panel preflight does not constitute Gate 2 acceptance.

The project remains outside the checkout in the configured projects folder. This work does not establish a finished game package, Unreal verification, Houdini parity, or print readiness.

## Gated advanced hover taxi (16-17 October 2026, branch `clean-references-detail`)

A second real-project run of the four gates in Blender 5.2.1 LTS (a local project that isn't published in this repository; design route only), from a clean six-view orthographic reference set and with detail measured by checks. Gates 0 and 1 were accepted by the user. Gates 2 and 3 were accepted under the user's explicit delegation while they were away, with every threshold recorded as set on their behalf for later review. Native runs, in order:

- **Gate 0:**
  - `references masks|check` on the six clean views. They disagree by up to 15%, so an accepted authority rule decides which view governs which measurement.
  - Orthographic calibration: right and left at 0.07 px RMS, top at 4.2 px (limit 5 px).
- **Gate 1 master hull:** closed. Silhouette IoU 0.898 right, 0.893 left, 0.975 top (limits 0.88 / 0.88 / 0.95).
- **Gate 2 panels:** about 60 panels, chrome plates and wells.
  - 14 seam checks on the stretches away from three-panel corners (seam `region_mm`): painted gaps 1.5-3.1 mm, chrome 6.3-7.1 mm, steps at most 0.005 mm.
  - Eight recess checks; one vertex 1.14 mm proud at the rear bumper corner.
  - Coverage complete within 14 mm (body) and 9 mm (nacelles).
  - A Gate 2 detail inventory share: 18 plates, 4 doors, 10 panels, 2 modules, 2 armour shells.
- **Gate 3 detail:** five detail checks, each against the skin its pieces sit on:
  - exterior: 31/31 items, 140 pieces;
  - mounted: 7/7;
  - pads: 48 band segments, 96 slots, 4 emitters;
  - fasteners: 292 bolts;
  - interior: 4 seats.

  No piece floats more than 1 mm. Complete-model silhouette IoU 0.948 right, 0.943 left, 0.958 top.
- **Re-verification:** `run --source scene` after the final acceptance reused all 37 checks.
- **Toolkit changes from this run, each committed with tests:**
  - orthographic calibration, clean reference masks and checks, the `detail` check kind with the final-gate rule, detail primitives, and the viewer References tab (03b0039, e6c510c, 7fba815, de9eba5, 0d82198);
  - `open_well` and seam `region_mm` (a477e51);
  - `slice_panel` region unions and the `open_well` interior-edge fix (6960131);
  - the `Shell guard` against solidified shells folding out at tight corners (71cdf81).

  After the last change, the native surfacing fixture passed and the host suite passed: 167 tests, 4 skipped.

Game route: built in four Nanite runs on 17 October; none reached `passed` (the last ended as a candidate), so no game package from this project is verified. The practices it produced are written up in [game assets](GAME_ASSETS.md#hero-assets-on-nanite) as guidance, not as validated delivery.

Not run: Houdini; a physical reference (the clean views are generated images).

## Gated hover taxi rebuild (16 October 2026, branch `hover-taxi-gated`)

A real-project run of the format 3 gates in Blender 5.2.1 LTS (`hover_taxi_gated`, design route only; the project has since moved out of the repository into the local projects folder). Every gate was accepted by the user after its blind review. Native runs, in order:

- **Gate 0 calibration:** `geometryforge calibrate` on the primary and profile references. The primary solved at 10.9 px RMS from seven datums; the user set a 12 px limit, recorded with its reason. The nose and headlamp corners were dropped as datums because they are different 3D points in the two generated views.
- **Gate 1 master hull:** a closed body cage and two nacelle masters, 0 open edges. Silhouette IoU is 0.830 (primary) and 0.817 (profile) against a user limit of 0.80 for the master alone. Gate 1 was later reopened by the user to move the nacelle sockets to the rear face, and re-accepted.
- **Gate 2 panels:** 18 body panels, 12 skirt plates and bumpers, the belly and the nacelle armour, all sliced from the masters.
  - Seam gaps 1.8-4.1 mm (skirt 5.4-7.0 mm), steps at most 0.009 mm, tangent break p95 at most 0.03 deg on painted seams (skirt 1.09 deg).
  - Seven pocket checks with at most 0.104 mm protrusion; coverage complete within 9 mm.
  - Re-accepted after the socket move.
- **Gate 3 detail:** pads (one mesh, four linked placements), nacelle drive, glass, lamp and exhaust inserts, roof equipment and interior.
  - Ten mating checks exactly on axis and centre, with 0 skin crossings. Laps: pad bosses 40 mm, drum flanges 15 mm, shafts 80 mm, couplings 10 mm.
  - Five recess-contents checks with nothing proud.
  - Full-assembly silhouette IoU 0.837 and 0.887, against a user limit of 0.83 because the locked Gate 1 proportions cap it.
  - Adding Gate 3 edited the recipe entry, which rebuilt every part. The six locked Gate 1-2 parts reproduced their accepted geometry hashes.
- **Re-verification:** `run --source scene` after the final acceptance reused all 34 checks.
- **Blender review:** blind survey21 sheets, reference overlays and close-ups for every gate. The old and gated taxis were rendered from identical cameras for the project README.
- **Toolkit fixes found by the rebuild, each committed with tests:**
  - per-gate review `iou_min` (8251b2e);
  - seam pairing on staggered borders (43e85ca) and the gap measured at the visible edge (8d576a9);
  - panels keep master creases, and geometric corner cuts for panels and openings (9a7a401);
  - recess `region_mm` (634942f);
  - the `Pocket guard` shrinkwrap against proud subdivided return vertices (ca31b3a).

  After the last fix, the native surfacing fixture passed again and the host suite passed: 148 tests, 4 skipped.

Not run: the game route (UVs, bake, LODs, Unreal import) for this project; Houdini; and silhouette scores against a photographed reference (the references are generated images). Small details are deferred and listed in the project's `decisions.json`.

## Gated master-hull workflow (15 October 2026, branch `gated-surfacing`)

- **144 Python tests passed** without native applications (4 opt-in native tests skipped).
  - New coverage: camera solving (synthetic pose/focal/shift recovery, coplanar datums with a lens prior, noise, degenerate inputs), calibration files and overlays.
  - Mesh queries against brute force.
  - Every typed check class on synthetic geometry with pass and fail cases: flush/stepped/tilted seams, a tangent-continuous curvature break, proud contents, a straight-walled pocket, misaligned and over-lapped rings, skin crossings, open edges, uncovered master area with and without a declared opening, and silhouette IoU and delta.
  - Gate frontier, refusals, locks, acceptance evidence, reopen/supersede and dependent-route holds.
  - Format 3 migration and contract errors, review presets, calibrated refs, IoU baselines, blind output and region diffs.
- **Blender 5.2.1 LTS native review tests passed:** zebra, normal, part_id, section cuts and overlays rendered, and two identical reviews were pixel-identical in part_id and normal.
- **Native three-gate fixture passed in Blender 5.2.1 LTS** (`tools/fixtures/surfacing_project`, `GEOMETRYFORGE_RUN_NATIVE_SURFACING=1`):
  - **Master gate:** built only the closed master hull (0 open edges), then six zebra/silhouette review views, `gate check` and acceptance. The locked master was then refused for `--parts`.
  - **Panels gate:** seam deviation 0.0001 mm, step 0.0001 mm, gap 3.63 mm, tangent break 0.013° and curvature ratio 0.044 (p95). Coverage found no uncovered area with the lamp opening excused by its interface ring.
  - **Detail gate:** no proud vertices, rim step 0.0001 mm, draft 5.8°, return fillet 2.71 mm, lens lap 5.0 mm on axis, 0 skin crossings.
  - **Re-verification** of the saved scene reproduced every geometry hash and reused every check.
  - **Per-check fixture thresholds,** each recorded with its reason in `project.toml`: coverage tolerance 6 mm for the cube cage's valence-3 corner poles, and fillet 2.5 mm for the square plan corners of a two-face opening.
- **Houdini 22.0.368 native evidence test passed:** a guide sphere and two interface circles built as SOPs were extracted with their roles. The typed `open_edges` and `mating` checks passed (lap 48 mm), and moving the plug to 60 mm failed the run as intended. The `api.surf` helpers are Blender-only; Houdini surfacing parity is **not** claimed.
- **Evidence-hash compatibility:** the bundled `mechanical_prop` design route was built with the previous toolkit (commit 62c2817) and re-verified with this one. The geometry hash was identical and no parts were reported changed. The format 1 and 2 showcase projects load with unchanged context.
- **Fixture development surfaced engine and helper defects that are now fixed:**
  - parts are passed to recipes dependencies-first;
  - panel cages conform to the master;
  - Solidify uses simple offset (even offset exploded at pocket returns);
  - pocket rings are mitred and weighted 0 inside the flush rim;
  - check meshes ignore oversized triangles when bounding searches.

Not run: the viewer browser tests (the viewer was not changed), game packaging or Unreal import of a gated project, and any reference-calibrated silhouette on a real photograph. The thresholds are starting defaults from an unverified engineering report, not validated acceptance limits.

## Advanced taxi and attachment review (15 October 2026)

- **75 Python tests passed** with `GEOMETRYFORGE_RUN_NATIVE_REVIEW=1` and Blender configured. The dedicated managed fixture tested render-level subdivision, collection/Geometry Nodes instances, review errors, source hashes and unchanged fixture safe points. No tests used the user's working taxi as a fixture.
- **7 Chromium tests passed** on the dedicated port-8744 fixtures after `npm ci --prefix ui` and `npm run build --prefix ui`. The rebuilt viewer bundle is retained and byte-identical to the tracked bundle.
- **Blender 5.2.1 LTS** built the isolated full-exterior advanced taxi study (a local project, not in the repository), including explicit engine facet boundaries, shared exhaust seating sections, receiving housings and structural support. Saved-scene review includes all four modes and front/rear/side/roof/underside, isolated pad/engine and mounted interface views. Matched pilot/advanced comparisons retain identical cameras, resolution and studio placement.
- **61 project-specific native geometry checks passed.** Actual evaluated-mesh intersections checked collar/frame, grille carriers, shaft/races, housing/fairing/body, glands/hoses, webs/beams/rails, sills/floor, vents, rear lamps and pad saddles. All four accepted pads retain 216 native objects and 45,268 triangles each, with identical evaluated topology and modifier stacks; the largest placement-normalized vertex difference is 0.000137 mm.
- **Presentation-only delivery passed evaluated geometry equality after reopening**, with zero local vertex difference from the retained managed scene. Source/config/reference/artifact hashes, the interface report and delivery-equivalence report connect the native copy to its evidence. Original and pilot scene/working/state hashes are preserved.
- **Canonical guidance refreshed** into both repository harness installations, covering protected feature edges, shared mating sections, mechanical housing/load paths and reuse of accepted native components.

This is a first full-exterior study with visual refinements listed in its README. Technical geometry checks do not establish reference acceptance or engineering performance. No new game package, Unreal import, Houdini optimization, slicer review or physical print test ran for this continuation.

## Geometry review and taxi study checks (14 October 2026)

- **75 Python tests passed** with `GEOMETRYFORGE_RUN_NATIVE_REVIEW=1` and the local Blender executable configured. This includes input validation, hashed source/config/reference/artifact provenance, retained runtime failures, cancellation, missing/changed inputs and review execution that preserves the source and project state. Without the opt-in flag the dedicated native test skips.
- **Blender 5.2.1 LTS**, on Windows, created and reopened a dedicated temporary managed subdivision-panel fixture. Clay, glossy, silhouette and wireframe renders were nonblank, respected the requested resolution and evaluated the saved render modifier levels. Construction operands were excluded; unknown/non-renderable selections failed. Native collection and Geometry Nodes instances rendered with evaluated transforms. Source scene hashes and the fixture safe-point record stayed unchanged. Fixed studio placement was checked.
- **7 Chromium tests passed** on the self-contained port-8744 fixtures after `npm ci --prefix ui` and the viewer production build. The rebuilt `geometryforge/web_dist` is byte-identical to the tracked bundle, so there is no bundle change to commit.
- **Wheel and source distribution built.** The wheel contains both review modules, the new canonical surface-modeling reference and the prebuilt viewer. The canonical skill was refreshed into both repository harness installations.
- **Isolated hover taxi study** built and reopened editable compound-curved front surfaces, one segmented front-right pad and one right rear engine. Review evidence includes all four modes, isolated/mounted views and before/after comparisons with identical cameras, resolutions and explicit studio light placement. Original taxi design/game snapshots and project-state SHA-256 values remained unchanged. See the local study delivery (`hover_taxi_geometry_study/README.md` in the projects folder) and its `delivery.json` for geometry counts, hashes, retained reports and remaining visual mismatches.
- **Original-detail audit** ray-sampled four +Y door/fender seams at three heights in copied retained design/game scenes. Door groove centers survived; their edge sidewalls became sloped over roughly 1 mm. The largest ray-hit difference at a groove edge was about 46.44 mm, not a measured vertex displacement or proof of complete groove removal. The audit does not cover the whole asset.

The study remains a candidate with visual acceptance pending. No new game package, Unreal import, Houdini optimization, slicer review or physical print test was performed for this change. The images demonstrate geometry and review tooling, not an exact reconstruction of the photographic or generated references.

## Environment

Windows, Python 3.12.13, Blender 5.2.1 LTS, Houdini 22.0.368 Apprentice (saves `.hipnc` through its supported GUI/OBJ workflow), Bambu Studio 2.8.2.

## Game routes release checks (14 October 2026)

- **42 Python tests passed**, including v1 migration/restoration, independent target safe points, valid open game surfaces, attribute/texture provenance, stage invalidation, missing LOD delivery, UV overlap, rigid transforms, preparation-preserving verification and native package loading without host ABI leakage.
- **7 Chromium tests passed**, including PBR texture loading, route selection, LOD/wireframe/collision/pivot controls, representation comparison and game package downloads. The prebuilt viewer was rebuilt from the checked sources.
- **Blender 5.2.1 LTS** built and reopened the editable mechanical housing, baked PBR maps, exported/reopened FBX and wrote/read GLB. Unchanged runs reused preparation/FBX with a stable package ID. Material-only changes preserved source geometry, UVs and collision. Full verification invoked zero builders. Frozen conversion worked in both directions at explicit scales.
- **Unreal 5.8.3** imported conventional and Nanite packages into a disposable project and reopened saved assets. Dimensions, LODs, convex collision, declared material instances, texture color spaces and Nanite/fallback settings passed. Separate offscreen reviews produced 1280×720 captures and 120-frame editor profiling CSVs on an NVIDIA GeForce RTX 3080, driver 591.86, 32 logical CPUs and 64 GiB RAM. Managed shader compilation errors are rejected. Editor profiling is not a cooked-game performance guarantee.
- **Additional native fixtures** passed: a 3 m doorway whose 21-sample traversal path stays outside all three convex collision bodies; a displaced 20,480-triangle Nanite rock; a printable shell with measured 2 mm walls/floor and a coupon with measured 0.2 mm radial clearance; and a legacy printable organizer migrated and derived into a game asset.
- **Houdini 22.0.368 Apprentice** saved/reopened native design/SOP geometry and retained UV/material attributes with an editable Principled shader. Commercial game FBX export and production BAKE ROP execution were not verified on the installed Apprentice license; the adapter reports unsupported capability rather than bypassing restrictions.
- **Legacy native regressions passed again** in Blender and Houdini: organizer/rocket construction, incremental part/interface checks, saved manual edits, source-preserving full verification and restoration. Existing print geometry and kit behavior remained intact.
- **Packaging** produced the 1.1.0 wheel and source distribution. The wheel installed into a separate Python 3.12 environment, initialized the shipped game example and built/validated it natively from outside the checkout. Its optional viewer routes and bundled assets were present. Canonical skills were refreshed for both harnesses.

Recorded summary: [game-evidence.json](game-evidence.json). Review captures: [conventional](game-standard.png) and [Nanite](game-nanite.png). Raw run/import/profiling artifacts remain in the dedicated timestamped validation workspaces. No slicer review or physical print is claimed by these game checks.

## Automated tests (8 October 2026)

- **23 Python tests passed.** They cover dependency closure, incremental artifact and check reuse, checker invalidation, corrupted outputs, source conflicts, manual-scene continuation, source-preserving full verification, restoration, locking, snapshot integrity, failure and cancellation, independent backend freshness, the installer, the viewer API (registration, rename/archive, artifact boundaries, Host validation, same-origin writes, session tokens, inline/attachment downloads), and whole-model 3MF files (slot read-back, undeclared slots, Bambu packaging).
- **The Bambu Studio test** drives the installed Bambu Studio and skips itself where it isn't installed, as on CI.
- **6 Chromium browser tests passed.** They run on generated fixture projects with a stand-in native backend: projects, backends, part visibility, filtering and groups, isolation and print pose, run comparison (side by side, overlay, missing parts), filament colouring, whole-model downloads, the image and log viewer, and explicit downloads.
- **CI** runs the Python tests on Windows and Linux, builds the package, checks that the bundled viewer matches its sources, and runs the browser tests.
- **The canonical skill** passed the skill-creator validator on 3 October; since then it has had documentation additions only. Both harness installations are checked by the tests. End-to-end agent conversations are not automated.

## Native application evidence (3 October 2026)

`tools/validate_native.py` built, saved and reopened the desk organizer and the multipart rocket fixture (`tools/fixtures/falcon9`) in both applications. The organizer kept 3 Blender Boolean modifiers and 22 Houdini nodes; the rocket 22 modifiers and 172 nodes. Mesh validity, STL/3MF read-back, bed fit, measured functional checks and cross-application comparisons passed. The suite demonstrated:

1. A fairing-height change rebuilds only the fairing in each application, refreshes its exports, preview and the upper-joint check, and reuses five parts and three checks.
2. A clearance change refreshes both joint sides, the stand and the coupon while reusing the unrelated legs.
3. Saved manual edits in Blender and Houdini are detected and continued. Full verification invokes zero builders, preserves source hashes and keeps the prior safe point while the other application awaits reconciliation.
4. Restoration creates separate working copies with matching procedural inputs; the edited files stay unchanged.

Details: [native-evidence.json](native-evidence.json). Reproduce with `uv run python tools/validate_native.py --workspace validation-workspace` once Blender and Houdini are configured. It uses a disposable workspace; never point it at your own projects.

Since then, the whole-model 3MF step and the filament slot parameter of the native API were added. Both were exercised natively by the Astraeus lander run below, but `validate_native.py` itself has not been rerun.

## Showcase project (8 October 2026)

The Astraeus Heavy Lander (22 parts) passed in both applications with the four-colour filament plan, and Bambu Studio packaged its print kit. See the project's [VALIDATION.md](../projects/astraeus_lander/VALIDATION.md) for checks, slicing estimates and what wasn't verified: Bambu Studio's command line can't slice the multi-filament X2D kit offline.

## Packaging (3 October 2026)

A wheel and source distribution were built, and the wheel installed into a separate environment and used outside the checkout. It supplied its own example, installed the skill for both harnesses, built and verified the organizer in Blender, and served the bundled viewer with its license notice. See [package-evidence.json](package-evidence.json). Package metadata changed for the public release; CI rebuilds the package on every push.

## Known limits

- Only saved files are monitored; save native edits before continuing.
- Reconciling Blender and Houdini history is agent-authored work.
- Dependency declarations must include every relevant source, parameter and interface.
- Scene inspection may still evaluate the whole assembly.
- The viewer is local and single-user. Model scripts are trusted, unsandboxed local code.
- macOS and Linux native operation is unverified.
- The test client emits an upstream HTTPX deprecation warning; tests pass.
