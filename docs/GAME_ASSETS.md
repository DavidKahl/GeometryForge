# Game assets and printable derivatives

GeometryForge now has independent game and print delivery routes. Your agent establishes the brief and authors native recipes; the toolkit remains deterministic and local. The viewer inspects evidence and never executes modeling, imports or build jobs. This release focuses on desktop static props, modular pieces and rigid assemblies. Batch factories, characters, animation, foliage systems and terrain authoring remain later work.

## Start a game project

```powershell
uv run geometryforge init C:/Models/Housing --example mechanical_prop --target game --deliverables blender
uv run geometryforge context C:/Models/Housing
uv run geometryforge plan C:/Models/Housing
uv run geometryforge run C:/Models/Housing
```

When you start from reference images, your agent runs a reference intake first: it confirms the route, reviews which surfaces the images actually show, and either asks for missing views or waits for you to accept its listed assumptions.

The mechanical housing example keeps a detailed native design, makes a render representation, unwraps the actual evaluated topology, bakes five PBR maps, generates three LODs, and creates convex collision and an attachment socket. Its 256-pixel maps make the demonstration quick; texture resolution and bake samples are parameters. Increase them for production as the asset's viewing distance requires.

Choose the Nanite profile with `run --target game --profile unreal_desktop_nanite`. The effective profile is recorded in the run; it does not rewrite project preferences. Conventional and Nanite are alternative game versions with their own retained runs. Keep print size separate from intended game size. Internally coordinates remain millimeters; FBX/Unreal uses centimeters and GLB uses meters with Y up.

## Package contents and checks

Every passed game route writes `game/manifest.json`, FBX meshes and separate LOD files, PBR maps, GLB previews, Unreal import settings/script, reports and `asset-package.zip`. Each base FBX carries its associated UCX collision. The manifest carries asset-local mesh bounds, assembly transforms, source identities, materials, sockets, profile and file hashes. Native FBX read-back checks unit dimensions and UV coverage; GLB containers are read back and all delivered files are hashed.

Game checks permit open render surfaces. They validate finite triangle data, UV atlases, normals/tangents, material assignments and budgets, conventional LOD coverage, convex collision and material compatibility for Nanite. Unique UV atlases are the default; intentionally overlapping/tiled primary UVs require `uv_mode="tiled"`. Baked lighting requires a separate unique UV channel. Projects must add semantic checks such as doorway clearance and modular grid alignment.

Textures use sRGB for base color/emissive and linear data for normals/roughness/metallic/AO. Unreal normals are DirectX; preview normals are OpenGL. Packed ORM is R=occlusion, G=roughness, B=metallic. Imported texture files must be declared project inputs; generated images are retained with the run and packed into native Blender scenes. Copying a native scene does not depend on its old relative texture folder remaining beside it.

Starter budgets are 20,000 triangles/output for conventional assets, 250,000 for Nanite, two used material slots and 2048-pixel maps. Conventional LOD targets are 1/.5/.25/.125. They are configurable production defaults, not universal engine limits. Failed budgets require asset revision or an explicit profile change.

## Unreal integration

Enable PythonScriptPlugin and EditorScriptingUtilities in the selected `.uproject`. Discover Unreal with `doctor`, or set `GEOMETRYFORGE_UNREAL` to its installation/executable. Then:

```powershell
uv run geometryforge unreal import C:/Models/Housing --uproject C:/Games/MyGame/MyGame.uproject --run <game-run-id>
uv run geometryforge unreal verify C:/Models/Housing --uproject C:/Games/MyGame/MyGame.uproject --import <import-id>
uv run geometryforge unreal review C:/Models/Housing --uproject C:/Games/MyGame/MyGame.uproject --import <import-id>
```

The current adapter checks the Unreal 5.8 editor API. It imports through configured FBX tasks, creates PBR materials/instances and textures explicitly, attaches LODs/collision/sockets, applies Nanite/fallback settings and creates a review level. Saved assets are reopened and checked for dimensions, LOD/collision counts, material slots and Nanite settings.

Imports use `/Game/GeometryForge/<project>/v_<package-id>/`. Reimporting the same unchanged package verifies the existing assets. Artist changes cause a conflict rather than an overwrite. A failed partial import stays intact; an unchanged retry can use a separate managed namespace. Package safe points remain independent of import attempts.

Import/verification runs unattended with NullRHI for saved-asset checks. `unreal review` separately loads the managed review level offscreen with graphics enabled, creates temporary review lighting/camera, captures a 1280×720 image and 120 editor frames of CSV profiling after warmup, and records hardware/driver information. It rejects managed material compilation errors. It does not change saved assets or establish a cooked-game frame-rate guarantee. Import evidence, screenshots and profiler CSVs live under `.geometryforge/imports/`, and the viewer distinguishes **Package safe** from **Unreal verified**.

## Game ↔ print conversion

Existing v1 projects remain printable projects. Use `migrate <project> --format 2` to back up project/decision/state files and introduce a print target while preserving sources, working scenes and retained runs. Author the game target before attempting conversion.

```powershell
uv run geometryforge derive C:/Models/Housing --target print --from-run <game-run-id> --from-target game --scale 1.25
uv run geometryforge derive C:/Models/Housing --target game --from-run <print-run-id> --from-target print --scale 0.8
```

`derive` requires a declared `derivation_recipe` and an implemented destination builder. It snapshots the current recipe, verifies frozen source artifacts, and passes lineage/scale to the native API. It does not invent missing geometry, reconstruct construction history or recover solids uniquely from normal maps.

Prefer retained detailed construction. Print-to-game recipes remove manufacturing features and add rendering preparation. Game-to-print recipes add thickness/closure, strengthen details, plan part splits/joints and validate against the recorded process. Transform the whole construction, including Boolean operands. Record deliberate differences and validate each route independently. Print mesh validity still does not replace slicer review, fit coupons or physical testing.

Per-route safe points preserve successful game packages when optional print conversion fails. `restore --target game|print` copies a validated route and matching inputs without replacing current work. `adopt --target ...` explicitly selects the working-scene owner. The viewer compares representations; optional size normalization aligns comparison views without changing exported dimensions.

## Authoring target-aware projects

See the [v2 contract](../geometryforge/skill/references/targets.md) and bundled example for the complete interface. Keep stable design IDs in `parts`; target outputs may merge/split them through `source_parts`. Targets can have independent backend entries/check selection. Optional shared design executes before requested delivery routes.

Ordered preparation stages are UV, materials, bake, LOD and collision. Each declares its own entry, helper sources, parameters and earlier-stage dependencies. Material-only edits can rerun materials/baking/LOD while preserving source geometry, UVs and collision. Full verification invokes none of these builders. Native edits plus changed recipes require reconciliation rather than silent regeneration.

Blender helpers cover registration, retained-source loading/scaling, finalized UV topology, PBR materials, source-to-target baking, editable LOD construction and collision. Houdini extracts vertex attributes directly from native SOPs instead of flattening through the legacy OBJ reader. Its game FBX adapter and authored BAKE ROP execution require a supported license. Apprentice native design extraction has separate coverage and must not be presented as commercial game production validation.

## Reproduce validation

```powershell
uv run pytest
npm run build --prefix ui
npm test --prefix ui
uv run python tools/validate_game.py --unreal C:/Path/UE_5.8 --review --houdini
```

The native validator creates dedicated timestamped fixture projects and a disposable Unreal project under its workspace. It preserves prior validation runs and does not open your working game project. See [validation coverage](VALIDATION.md) for the checks actually run.
