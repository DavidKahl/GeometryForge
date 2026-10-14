# Project contract v2

v1 remains supported without changing its print semantics. v2 adds independent `output_targets` in decisions.json, containing `game`, `print` or both. Native `deliverables` retains its v1 meaning. All internal geometry is in millimeters.

## Target configuration

Keep stable design IDs in `[parts.<id>]`. `[targets.design]` is optional shared source construction. Delivery targets can override backend entrypoints through `[targets.game.backends.blender]` (or print/Houdini), each with `entry`. If design is configured it builds/verifies before requested delivery routes. Cross-route transformations always use frozen derivation provenance, not cyclic live dependencies.

Without `outputs`, a route uses the declared part IDs. `[targets.game.outputs.<id>]` or the corresponding print table can merge/split identities using `source_parts`, sources, parameters and depends. Only declared source part IDs are allowed. Route-level `sources` are shared geometry inputs. Global checks may declare `targets`; a route's `checks = ["id"]` restricts its required checks. Check payloads add `target`, `settings` and `derivation` to the v1 payload.

Game profile and budget choices belong in decisions.game or `[targets.game]`; target contract settings take precedence. CLI `--profile` overrides only the effective run settings and is retained in that run; it does not rewrite project preferences.

## Preparation stages

The ordered stage names are `uv`, `materials`, `bake`, `lod`, `collision`. Each `[targets.game.stages.<name>]` declares entry, sources, parameters and earlier-stage depends (`geometry` is the initial stage). An entry exposes `build_parts(parameters, parts, api)`; it prepares existing owned outputs instead of blindly rebuilding source geometry. A stage can override its entry per backend. All referenced files must be declared and remain within the project.

Only changed stages and their declared dependents run. `verify --source scene`/`verify --full` invokes zero preparation builders. Changing a stage recipe requires preparation before current verification coverage can be claimed. Native edits and changed procedural preparation require explicit reconciliation.

## Native API and evidence

`api.target` is design/print/game; `api.profile` contains effective route choices. `api.register_output(obj, output_id, role, source_parts=[...], **metadata)` adds representation registration. Roles: design, high_detail, render, lod, collision, printable, construction, presentation. `finish` remains a printable convenience. Shared source scenes are available as `api.design_scene`; `load_design` appends/merges retained native construction. Blender `scale_design` transforms the whole construction including Boolean operands; scaling only a final object can change its cuts.

Game evidence contains triangles with per-corner UV layers, normals/tangents and optional colors, compact material assignments, asset-local coordinates, world placement and destination metadata. A game output ID has one render mesh plus its LOD/collision representations. Metadata includes `lod`, `sockets` (name and local `position_mm`), collision policy, optional `nanite=false` for a conventional section, and `uv_mode="tiled"` where intentional UV overlap is required. Unique atlases are the default; secondary/lightmap UVs stay unique.

Each route retains independent native working scenes, safe points and freshness. An aggregate safe point needs every requested route/backend. Optional print failure preserves game evidence. Restoration copies matching inputs and selected scenes without overwriting current work. `adopt --target` selects route ownership explicitly. Unreal import records live separately and never promote a package safe point.

See the bundled `mechanical_prop` project for complete Blender preparation entries, shared design and explicit print/game derivation recipes. Houdini constants/extraction are supported; production FBX and authored BAKE ROP execution need a supported license. Native backends are independent editable implementations, not automatic history translations.
