# Windows validation ? 3 October 2026

Validated SAFE POINT: `20261003T112208Z-88ad3d7d`.

## Native geometry

| Backend | Version | Editable construction | Required interface checks |
|---|---|---|---|
| Blender | 5.2.1 LTS | {'native_objects': 226, 'modifiers': 197} | 8/8 passed |
| Houdini | 22.0.368 | {'native_nodes': 1622} | 8/8 passed |

Both native files were saved and reopened. Each backend passed mesh watertightness, winding, positive volume, body count, bed fit and exported STL/3MF round-trip checks for all 22 part groups. Part identity, assembly bounds, dimensions and volumes passed cross-backend comparison.

The eight interface checks cover the main collars, nose cap, thermal sleeve, engine mounting, aft fin roots, canard roots, landing-leg roots and fit coupon. Measurements use exported triangle geometry; relevant assembly pairs also passed Manifold solid-intersection checks. Intended mating clearance is 0.30 mm per side.

## Bambu Studio slicing

Bambu Studio 2.8.2.61 used its installed Bambu Lab X2D 0.4 nozzle profile, 0.16 mm High Quality, three walls, 15% gyroid, Generic PLA and a textured PEI plate. Build-plate supports were enabled for the complete-model check. The printer, nozzle and bed came from the user; filament and build plate were assumptions for this offline check.

All 29 STL files were included in 2 sliced plates, with 43,266,057 bytes of generated G-code. The slicer reported success and no plate warnings.

| Test plate | Model objects | Estimated total time | Estimated filament |
|---|---|---|---|
| 1 | 19 | 15 h 12 min | 278.0 g |
| 2 | 10 | 1 h 45 min | 28.8 g |

The coupon was also sliced separately. Slicing output stays local under `review/slicing_all/` and `review/slicing_coupon/`. These test layouts do not arrange parts by final color. Reslice with the actual filament, build plate and preferred color grouping before printing.

## Scope

The existing toolkit regression suite also passed: 18 tests on Windows. The running local viewer returned the registered Astraeus project successfully.

This is digital validation on Windows. No physical print, real-world fit test, landing-leg load test, native macOS test or native Linux test has been performed. Print the coupon first and inspect support removal and adhesion in the selected slicer settings. No printer job was sent.

Review renders were generated from the recorded Blender model; `render-provenance.json` records its SHA-256. Earlier failed attempts remain retained as failed runs, and cannot replace this safe point.
