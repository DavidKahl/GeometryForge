# Validation: 8 October 2026 (Windows)

Validated safe point: `20261008T095111Z-aeea6705`. It supersedes the 3 October safe point `20261003T112208Z-88ad3d7d`. The geometry is unchanged; this run added the filament plan and the whole-model 3MF files.

## Native geometry

| Backend | Version | Required interface checks |
|---|---|---|
| Blender | 5.2.1 LTS | 8/8 passed |
| Houdini | 22.0.368 (Apprentice, `.hipnc`) | 8/8 passed |

Both native files were saved and reopened. Each backend passed watertightness, winding, positive volume, body count, bed fit and STL/3MF round-trip checks for all 22 parts. Part identities, assembly bounds, dimensions and volumes matched across the two applications.

The eight interface checks cover the main collars, nose cap, thermal sleeve, engine mounting, aft fin roots, canard roots, landing-leg roots and the fit coupon. They measure exported triangle geometry; relevant assembly pairs also passed Manifold solid-intersection checks. Intended mating clearance is 0.30 mm per side.

## Filament plan and whole-model files

Every part's filament slot matched the plan in `decisions.json` (silver 5 parts, dark 10, engine grey 6, accent 1). In each backend, `assembled.3mf` and `kit-raw.3mf` were written and read back slot for slot. Bambu Studio 2.8.2 (installed X2D 0.4 nozzle and 0.16 mm High Quality presets) produced `kit.3mf` with all 22 parts on two plates and `assembled-bambu.3mf`. Both were read back with the planned slots and the four colours.

Bambu Studio's command line refuses to slice more than one filament for the dual-nozzle X2D offline, even for two plain test cubes, so the **four-colour kit was not sliced**. With every part on one filament, the same kit arranged onto one plate and sliced successfully (about 14 h 13 min, 252 g, Generic PLA). Open `kit.3mf` in the Bambu Studio app and check the plates before printing.

## Bambu Studio slicing (per-part STLs)

Bambu Studio 2.8.2 with the installed Bambu Lab X2D 0.4 nozzle profile, 0.16 mm High Quality, three walls, 15 % gyroid, build-plate supports, Generic PLA and a textured PEI plate. The printer, nozzle and bed came from the user; filament and plate are assumptions for this offline check.

All 29 STL files sliced onto 2 plates without warnings (43.3 MB of G-code):

| Test plate | Objects | Estimated time | Estimated filament |
|---|---:|---|---|
| 1 | 19 | 15 h 12 min | 278.0 g |
| 2 | 10 | 1 h 45 min | 28.8 g |

This layout doesn't group parts by colour. Reslice with your real filaments, plate and colour grouping before printing.

## Scope

GeometryForge's own test suite passed: 23 Python tests and 6 browser tests. Review renders were regenerated from this safe point's Blender scene, and `review/render-provenance.json` records its SHA-256.

This is digital validation on Windows. No physical print, real-world fit test, landing-leg load test, or native macOS/Linux run has been performed. Print the coupon first and check supports and adhesion in your slicer. No printer job was sent. Earlier failed attempts remain in the run history and cannot replace this safe point.
