# Windows validation — 3 October 2026

Verified with Python 3.12.13, Blender 5.2.1 LTS and Houdini 22.0.368 Apprentice. Houdini produced `.hipnc` files through its supported GUI/OBJ workflow. No physical print test or macOS/Linux native validation is claimed.

## Automated coverage

Final result: **18 core/API/installer tests passed; 2 Chromium browser tests passed.**

- Core tests cover dependency closure, incremental artifact/check reuse, checker invalidation, corrupted outputs, source conflicts, manual continuation, source-preserving full verification, restoration, locking, snapshot integrity, failure/cancellation and independent backend freshness.
- Installer tests verify both harness folders, repeat installation, preservation of existing instructions, and refusal to overwrite local skill modifications.
- Viewer API tests cover registration/creation, rename/archive, safe-point context, artifact downloads, path boundaries, Host validation, same-origin writes and session tokens.
- Playwright tests render actual assemblies in Chromium, switch projects/backends/runs, toggle parts, inspect dimensions, navigate safe points and display failed-run diagnostics. Screenshot: [viewer-windows.png](viewer-windows.png).
- The canonical skill passes the skill-creator validator. Harness-specific discovery folders and packaged references are installed and checked; full end-to-end Claude conversations were not automated.

## Native application evidence

Both examples were built, saved and reopened in both applications. The organizer retains three Blender Boolean modifiers and 22 Houdini nodes. The rocket retains 22 Blender modifiers and 172 Houdini nodes. Mesh validity, STL/3MF readback, bed fit and measured functional checks passed, as did cross-backend geometry comparisons.

The native acceptance suite demonstrates:

1. A fairing-height change rebuilds only the fairing in each backend, refreshes its exports/preview and the upper-joint check, and reuses five parts plus three checks.
2. A clearance change refreshes the two joint sides, stand and coupon while reusing the unrelated legs.
3. Saved edits in both Blender and Houdini are detected and continued. Full verification invokes zero builders, preserves source hashes and retains the prior safe point while the other backend awaits reconciliation.
4. Restoration creates separate working copies with matching procedural inputs; the edited files remain unchanged.

Detailed evidence is in [native-evidence.json](native-evidence.json). Reproduce with `uv run python tools/validate_native.py --workspace validation-workspace` after configuring the installed native applications. This uses a disposable test workspace; do not point it at personal modeling projects.

## Packaging

Built a wheel and source distribution. Installed the wheel into a separate virtual environment and invoked it outside the source checkout. The installed package supplied its own example, installed the skill into both harnesses, built and verified a Blender organizer, and exposed the bundled viewer assets and license notice. See [package-evidence.json](package-evidence.json).

The normal verification commands are `uv run pytest -q`, `npm run build --prefix ui`, and `npm run test --prefix ui` with the local viewer running and the native acceptance projects registered. Browser tests currently use those acceptance projects rather than generating native geometry during browser startup.

## Known limits

Saved disk files are monitored; unsaved UI edits must be saved first. Native history reconciliation remains agent-authored work. Dependency declarations must include every relevant source, parameter and interface. Scene inspection can still evaluate the whole assembly. The viewer is local and single-user; model scripts are trusted local code, not sandboxed. The test client currently emits an upstream HTTPX deprecation warning; tests pass.
