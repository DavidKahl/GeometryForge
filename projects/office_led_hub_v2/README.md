# Office LED Hub V2 (imported)

Run history imported from the first GeometryForge (0.3) at
`E:\3d Printing\Experiments\out\office_led_hub_v2`. The original project is untouched.

- `.geometryforge/runs/` holds the 7 legacy runs (2026-09-07 to 2026-09-13) in the current run format,
  so the viewer can browse and compare them. Each `run.json` has `imported_from` with the original path and inputs.
- `legacy_source/` is a copy of the original sources (`examples/office_led_hub_v2`) for reference.
- No safe point: these runs were validated by the 0.3 toolkit, not this engine.
- New runs need `legacy_source/models/hub.py` ported to a backend entry with per-part sources and checks.

Re-import into a fresh folder with `python tools/import_legacy.py <legacy out dir> <legacy source dir>`.
