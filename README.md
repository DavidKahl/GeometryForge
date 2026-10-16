# GeometryForge

**Model in your agent. Keep editable native files. Inspect every iteration.**

[![CI](https://github.com/DavidKahl/GeometryForge/actions/workflows/ci.yml/badge.svg)](https://github.com/DavidKahl/GeometryForge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

GeometryForge lets a coding agent, [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) or [Codex](https://developers.openai.com/codex), build **game assets and printable models** as real, editable **Blender** and **Houdini** projects. Describe an idea or supply references. Your agent authors the design and destination recipes; GeometryForge executes them, validates each route independently, packages the results and retains inspectable history.

![The GeometryForge viewer showing the Astraeus Heavy Lander, its parts and its run history](docs/viewer-windows.png)

## Watch the introduction

[![AI Builds My 3D Models Now. So What's Left for Me?](https://img.youtube.com/vi/L7bTOa_qrdc/maxresdefault.jpg)](https://youtu.be/L7bTOa_qrdc)

How GeometryForge came to be, from hand-modeled chess pieces to agent-built, validated print kits: [watch on YouTube](https://youtu.be/L7bTOa_qrdc).

## What you get

- **Editable native files, not just meshes.** Every part is built with Blender modifiers or Houdini nodes and saved as a `.blend` / `.hip` file you can open, tweak and hand back to the agent.
- **Incremental runs.** Change one part and only that part and the checks that depend on it are rebuilt. Unchanged parts reuse their verified evidence.
- **Safe points.** A run that passes every check in every requested application becomes a safe point. Failed or partial attempts never replace it, and you can always restore it.
- **Print-ready output.** Each part is exported as STL and 3MF in its print orientation and checked for watertightness, volume, bed fit and an STL/3MF round trip. Projects add their own fit and interface checks.
- **Multi-material 3MF.** Every run also writes the whole model as one 3MF: an assembled version for judging colours and a print kit with every part. With [Bambu Studio](https://bambulab.com/en/download/studio) installed, the kit becomes a ready-to-slice project with plates and filament colours.
- **A local viewer.** Browse projects and runs, isolate parts, compare any two runs side by side or as an overlay, view renders and download files.
- **Reference geometry review.** Render saved Blender scenes as clay, glossy, silhouette, wireframe and zebra comparisons from repeatable or calibrated cameras, including section cuts, a 21-view survey and region-invariance diffs. Retain hashed evidence without changing native scenes or safe points; see [the review guide](docs/GUIDE.md#reference-and-geometry-review).
- **Gated hard-surface workflow.** Format 3 projects build curved hulls top-down: calibrated reference, one locked master hull, panels shrinkwrapped to it, then detail bound to interface rings. Typed checks measure seams, pockets and joints instead of mere contact; see [the gated workflow](docs/GUIDE.md#gated-hard-surface-workflow).
- **No AI service of its own.** GeometryForge has no API keys, model provider or chat. Your existing agent does the thinking; GeometryForge does deterministic execution and bookkeeping.

## Requirements

Game projects add optional Unreal Engine integration. The first verified editor adapter targets Unreal 5.8 with PythonScriptPlugin and EditorScriptingUtilities enabled. Blender supplies the complete baked PBR example. Houdini retains native SOP game geometry/attributes; production FBX and native texture baking require a supported license. See [game assets](docs/GAME_ASSETS.md) for capabilities and coverage.

| | Required | Notes |
|---|---|---|
| Python 3.12 and [uv](https://docs.astral.sh/uv/) | Yes | uv manages the environment |
| An agent harness | Yes | Claude Code or Codex |
| [Blender](https://www.blender.org/download/) | At least one of the two | Verified with 5.2.1 LTS |
| [Houdini](https://www.sidefx.com/download/) | At least one of the two | Verified with 22.0 (Apprentice works, saves `.hipnc`) |
| [Bambu Studio](https://bambulab.com/en/download/studio) | Optional | Verified with 2.8.2; arranges the multi-material print kit |
| Node.js 22 | Only for development | End users get the prebuilt viewer |

**Platform:** Windows is the verified platform. The code is portable and the automated tests also run on Linux, but native Blender/Houdini operation on macOS and Linux has not been verified yet.

## Install

```powershell
git clone https://github.com/DavidKahl/GeometryForge.git
cd GeometryForge
uv sync --frozen --extra viewer
uv run geometryforge doctor
```

`doctor` shows which Blender, Houdini and Bambu Studio executables were found. GeometryForge looks at environment variables first, then your `PATH`, then the standard Windows install folders. If something isn't found, point to it:

```powershell
$env:GEOMETRYFORGE_BLENDER = 'C:/path/to/blender.exe'
$env:GEOMETRYFORGE_HOUDINI = 'C:/Program Files/Side Effects Software/Houdini 22.0.368'
$env:GEOMETRYFORGE_BAMBU   = 'C:/Program Files/Bambu Studio/bambu-studio.exe'   # optional
```

To use GeometryForge from another Python environment, install the checkout as a package with `uv pip install "path/to/GeometryForge[viewer]"` (omit `[viewer]` for the command line only). It isn't on PyPI yet.

### Install the skill for your agent

The skill teaches your agent the workflow: establish the brief and printer, model each part natively, plan, run, read the evidence and report honestly.

```powershell
uv run geometryforge install-skill --target C:/Models/MyWorkspace   # one workspace
uv run geometryforge install-skill --user                           # all your projects
```

This writes `.claude/skills/geometryforge` and `.agents/skills/geometryforge` (for Codex). Existing `CLAUDE.md`/`AGENTS.md` files are left alone, and locally modified skill files are never overwritten. Restart your agent if the skill doesn't show up.

## Your first project

For a game asset with an optional printable version:

```powershell
uv run geometryforge init C:/Models/Housing --example mechanical_prop --target game --deliverables blender
uv run geometryforge plan C:/Models/Housing
uv run geometryforge run C:/Models/Housing
uv run geometryforge viewer
```

This creates editable detailed construction, a conventional game mesh with UVs, baked PBR maps, LODs, convex collision, a socket, FBX exports and GLB previews. Use `--profile unreal_desktop_nanite` for the Nanite representation. To derive a print version, use the game safe-point ID reported by `context`:

```powershell
uv run geometryforge derive C:/Models/Housing --target print --from-run <game-run-id> --from-target game --scale 1.25
```

Output routes and native applications are independent: `--target both` means game + print; `--deliverables both` still means Blender + Houdini. Existing v1 print projects continue to work; `migrate --format 2` creates backups before enabling target contracts. [Game workflow and project authoring](docs/GAME_ASSETS.md).

For the existing print workflow:

```powershell
uv run geometryforge init C:/Models/Organizer --example desk_organizer --deliverables both
uv run geometryforge plan C:/Models/Organizer
uv run geometryforge run C:/Models/Organizer
uv run geometryforge viewer
```

Open <http://127.0.0.1:8743> to see the result. Then start your agent in that folder and ask, for example:

> Use GeometryForge to make this organizer 150 mm wide with four compartments. Keep both native projects editable, reuse unaffected checks, and show me the resulting run.

For a new model, just describe it, including the printer you'll use:

> Use GeometryForge to design a wall-mounted holder for two game controllers. I print on a Bambu X1C with a 0.4 mm nozzle in PLA. Blender only.

The agent asks only for decisions that change the design, writes the brief, dimensions and print plan into the project, and builds part by part. On Windows, double-click `Launch Viewer.cmd` in this repository to start the viewer.

## Showcase: Astraeus Heavy Lander

[`projects/astraeus_lander`](projects/astraeus_lander) is a 480 mm, 22-part display model of a fictional heavy lander, built entirely by an agent with GeometryForge from a single concept sheet. It has native Blender and Houdini versions, eight interface checks and a four-colour filament plan for a Bambu Lab X2D. See its [README](projects/astraeus_lander/README.md) and [print and assembly guide](projects/astraeus_lander/PRINT_AND_ASSEMBLE.md).

The printable files (STL, 3MF, the Bambu print kit and the native scenes) are attached to the [GitHub release](https://github.com/DavidKahl/GeometryForge/releases), so you can print it without Blender or Houdini.

## Showcase: gated hover taxi

[`projects/hover_taxi_gated`](projects/hover_taxi_gated) is a 5.8 m cyberpunk hover taxi built top-down through the format 3 gates:
- a calibrated master hull;
- panels sliced from it, with recessed pockets;
- mechanical detail bound to the pockets' interface rings: pads, nacelle drive, glass and roof equipment.

Each gate was accepted after a blind review and measured seam, pocket, mating and silhouette checks. Its [README](projects/hover_taxi_gated/README.md) compares it with two earlier ungated builds from the same cameras: it is ahead on surfacing and attachment, and behind on small detail.

## How it works

```text
you ──► agent (Claude Code / Codex) ──► project files: models/, checks/, parameters.json, decisions.json
                                            │
                    geometryforge plan/run  ▼
        Blender / Houdini build the parts ──► checks ──► STL / 3MF / previews ──► run record
                                                                                    │
                                                         local viewer  ◄────────────┘
```

| Term | Meaning |
|---|---|
| **Project** | A folder with `project.toml` (parts, builders, checks and their dependencies), `parameters.json` (dimensions), `decisions.json` (brief, printer, filaments) and the modeling code in `models/` and `checks/`. |
| **Run** | One execution. It snapshots its inputs, builds the selected parts, exports and checks them, and records everything under `.geometryforge/runs/<id>`. |
| **Safe point** | The latest run that passed every required check in every requested application. |
| **Candidate** | Kept work whose coverage is incomplete or whose scope was uncertain. It never replaces the safe point. |
| **Working scene** | The editable `.blend`/`.hip` under `working/`. Save your manual edits there, then ask the agent to continue. GeometryForge detects the change. |

The [user guide](docs/GUIDE.md) covers the full workflow: editing native files by hand, restoring, the command reference, the project files, multi-material printing and troubleshooting.

## Limits, honestly

- Geometry checks don't replace slicing, a material-specific fit test or a physical print. Print the fit coupon first.
- GeometryForge exports STL and 3MF. It never slices for you or sends anything to a printer.
- The game route exports FBX, GLB and PBR packages. Package validation, actual Unreal verification, rendered review and performance measurements have separate coverage; static geometry checks do not prove a frame-rate target.
- Blender and Houdini versions are separate native implementations of the same design intent, compared by dimensions and volume. There's no automatic translation of construction history between them.
- Project scripts are trusted local code and run unsandboxed in your applications. Only run projects you trust. See [SECURITY.md](SECURITY.md).
- Houdini's own license terms (e.g. Apprentice: non-commercial, `.hipnc`) still apply to the files it produces.

## Documentation

- [User guide](docs/GUIDE.md): workflow, commands, project files, multi-material printing, troubleshooting
- [Architecture](docs/ARCHITECTURE.md): how runs, evidence reuse, recovery and the viewer work
- [Validation](docs/VALIDATION.md): what has actually been verified, on what
- [The agent skill](geometryforge/skill/SKILL.md) and its [project contract](geometryforge/skill/references/contracts.md) and [printing guidance](geometryforge/skill/references/printing.md)
- [Changelog](CHANGELOG.md)

## Contributing

Bug reports, ideas and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md). Report security issues privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 David Kahl. Blender, Houdini and Bambu Studio are separate products under their own licenses and are not distributed here. See [third-party notices](THIRD_PARTY_NOTICES.md).
