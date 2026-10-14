# Validation

What has actually been verified, on what, and when. Nothing here claims a physical print. Native validation has only been done on Windows.

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
