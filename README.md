# GeometryForge

**Model in your agent. Keep editable native files. Inspect every iteration.**

GeometryForge gives Claude Code and Codex a shared skill for creating printable geometry and native Blender/Houdini projects. A small local toolkit keeps working files, snapshots, incremental checks and SAFE POINTS organized. The optional browser viewer shows projects, assemblies, runs and evidence. Your agent's existing harness handles the conversation and modeling; GeometryForge has no embedded AI provider or API-key setup.

## Install from this checkout

Requires Python 3.12 and at least one installed modeling application. Windows is the native verification platform; paths and core logic are portable, but macOS/Linux native operation is unverified.

```powershell
uv sync --frozen --extra viewer --extra dev
uv run geometryforge install-skill --target E:/Models/MyWorkspace --harness both
uv run geometryforge doctor
```

For independent use from another environment, install the local checkout with `uv pip install "E:/Projects/GeometryForge[viewer]"`, or install the built wheel. Omit `[viewer]` for CLI-only use. The repository is not yet published to PyPI. The package includes the skill, examples and browser assets; end users do not need Node.

`install-skill --user` makes the skill available across projects. Project installation writes `.agents/skills/geometryforge` and `.claude/skills/geometryforge`. Existing agent instruction files are preserved. Installation refuses to replace locally modified skill files. Restart your harness if the skill is not immediately visible.

If discovery needs help, set environment variables to your local executables:

```powershell
$env:GEOMETRYFORGE_BLENDER = 'C:/path/to/blender.exe'
$env:GEOMETRYFORGE_HOUDINI = 'C:/path/to/Houdini/bin/houdini.exe'
```

## Your first project

```powershell
uv run geometryforge init E:/Models/Organizer --example desk_organizer --deliverables both
uv run geometryforge context E:/Models/Organizer
uv run geometryforge plan E:/Models/Organizer
uv run geometryforge run E:/Models/Organizer
uv run geometryforge viewer
```

Open `http://127.0.0.1:8743`. For Blender-only output choose `--deliverables blender`; `geometry` uses `--backend` internally while print files are the requested deliverables. Internal native snapshots remain available for safe continuation. Choose `falcon9` for a multipart display model with keyed joints, stand, decorative legs and a fit coupon.

Then ask your agent, for example:

> Use GeometryForge to make this organizer 150 mm wide with four compartments. Keep both native projects editable, reuse unaffected checks, and show me the resulting run.

For print work, the skill establishes the target printer/process and a part-level print plan before detailed modeling. Usable build space, nozzle/line settings, material, load direction, removable supports and calibrated fits guide the geometry. Printer changes trigger reassessment of affected parts. See [printer-aware modeling](geometryforge/skill/references/printing.md) for the workflow and the distinction between mesh checks, slicer review and physical testing.

## Edits, runs and safe points

- A **working file** is editable. Save changes in Blender/Houdini before asking the agent to inspect them.
- A **run** retains selected inputs, native snapshots, print artifacts, actual measurements and reuse provenance. It may rebuild only one part.
- A **SAFE POINT** has complete required validation, including reusable evidence whose inputs still match. After working edits it remains recoverable and is marked as predating those edits.
- A **candidate** is retained work with incomplete coverage, uncertain scope, or another requested backend still needing reconciliation. Failed and cancelled attempts never replace a safe point.

```powershell
geometryforge run E:/Models/Rocket --parts fairing
geometryforge adopt E:/Models/Rocket --backend blender --file E:/Models/edited.blend
geometryforge run E:/Models/Rocket --backend blender --source scene
geometryforge verify E:/Models/Rocket --backend blender --full
geometryforge restore E:/Models/Rocket
```

Full verification loads edited scenes and reruns checks without regenerating pristine geometry. If both code/parameters and the native file changed, the agent must resolve which source to use. `--source code` explicitly authorizes selected builders to replace those parts in a scene copy. Restoration writes a separate working copy and matching procedural inputs, preserving current work.

Both backends are native implementations of shared design intent, not automatic translators of construction history. Manual edits may need agent-assisted reconciliation. Geometry inspection can evaluate the entire saved scene; incremental runs avoid unrelated builders, print exports, previews and functional checks.

## Project layout

`project.toml` declares parts, builders and check dependencies. `parameters.json` holds dimensions; `decisions.json` holds the brief, deliverables and print constraints. Modeling and check code live in `models/` and `checks/`. Editable copies live under `working/`; immutable-by-convention evidence lives under `.geometryforge/runs/`. Keep retained snapshots intact. Project registration is stored locally under `~/.geometryforge` (override with `GEOMETRYFORGE_HOME`).

See the [skill](geometryforge/skill/SKILL.md), [project contract](geometryforge/skill/references/contracts.md), [architecture](docs/ARCHITECTURE.md), [validation evidence](docs/VALIDATION.md), and [contributing guide](CONTRIBUTING.md).

![Local viewer showing the rocket assembly and run evidence](docs/viewer-windows.png)

Geometry checks do not replace slicing, material-specific fit testing, or a physical print. This project provides STL/3MF, not G-code. Generated project scripts execute as trusted local code. Houdini retains its actual license restrictions and selects the appropriate native file extension.

MIT licensed. Original simplified rocket geometry is not affiliated with SpaceX. See [third-party notices](THIRD_PARTY_NOTICES.md).
