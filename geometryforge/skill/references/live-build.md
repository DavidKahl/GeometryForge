# Live build

A live build runs a normal GeometryForge run inside a visible Blender window and turns it into a watchable making-of: each part appears in its construction stages while a scripted viewport camera moves around it, then the asset gets materials and studio light and ends on a turntable. It is meant for people who want to watch, pause and look around, or record the build (OBS) as content. Headless runs stay the default; offer live only when the user wants to watch or record.

## What stays the same

- The project's recipe builds every part, one part per recipe call in dependency order. There is no free-form modeling in the window.
- The run writes the same snapshot, `model.blend`, `result.json` and run record. Gates, locks, hashes and checks decide pass or fail exactly as for a headless run; `run.json` records `mode: "live"`.
- The evidence scene is saved before any look-dev. Studio lights, the floor, the world and material swaps exist only in `live-presentation.blend` beside it, so a stray Ctrl+S never touches evidence.
- The camera is scripted from part bounds and the project's brief. A live run costs about the same agent tokens as a headless run, and the same project records the same way every time.

## Commands

- `geometryforge session start --app blender` opens the live window (factory settings; `--user-prefs` keeps the user's theme and add-ons). Start it, maximise the 3D viewport (Ctrl+Space over it), set up OBS, then run. A run with `--live` starts the window itself if none is open, but then the recording misses the start.
- `geometryforge run <project> --live --parts ...` builds the parts live. `verify <project> --live` builds nothing and replays the saved parts in build order.
- **Replay or build new for an accepted asset.** When every gate is accepted, all parts are locked:
  - `verify --live` is a replay: it reveals the saved, accepted scene part by part, and its checks confirm the scene still matches the locks.
  - `run --live --rebuild-accepted --parts <all parts>` is a real build: it rebuilds the locked parts from code. The run passes only if every locked part reproduces its accepted geometry hash exactly. Otherwise it is a candidate and the acceptances stay untouched.
  - A rebuild takes as long as the original runs (use a large `--timeout`); a replay takes minutes.
- `--armed` prepares the run and holds on the empty stage. The run starts with **Ctrl+Shift+Enter** in the viewport (the same key pauses and resumes later), the Start button in the sidebar, or `geometryforge session go --app blender`. Use it to start OBS first, so the recording begins exactly when the user says go.
- `geometryforge session pause|resume|skip --app blender`, or the GeometryForge tab in the viewport sidebar (N), which also has a speed slider and an opt-in part HUD.
- `geometryforge session status|stop --app blender`. Stop saves a recovery copy of unsaved work first.

The command returns as soon as the evidence is written and its checks run; look-dev keeps playing in the window. A new run is refused until the presentation ends or is skipped.

Pause takes effect at the next beat, or after the part that is building finishes. While paused, orbit freely; resume eases back into the choreography from wherever the view is. Geometry edited while paused fails the run with a recovery copy saved, because live runs never adopt edits; bring them in through [revisions](revisions.md).

`--timeout` counts build time only, not reveal beats or pauses. The window freezes while a long part builds; after a few seconds it redraws as objects are finished, with a slow drift.

## Art direction for sci-fi hard-surface

Present the asset like a premium industrial design object: only the asset, the floor, the lights and the camera. There is no environment, scenery, props or HDRI. The defaults follow that:

- **Build look:** clay matcap with cavity, a warm neutral viewport background, and no gizmos, grid, axes or helper overlays.
- **Studio:** a warm beige backdrop seen only by camera rays, a low neutral ambient, and a large semi-matte floor (subtle reflection, soft contact shadow). There are separate key, fill, rim and top area lights scaled to the asset, AgX colour management, and restrained emissives.
- **Construction stages:** nothing appears finished out of nowhere. Each part shows its base or cage first, with construction cutters as wire, then its modifier stack switches on in order (subdivision, solidify, bevel, booleans, panel cuts), followed by a close inspection orbit.
- **Rhythm:** alternate macro (the whole asset, silhouette, proportions), medium (an assembly: a panel set, a nacelle, a pad) and micro (fasteners, seams, lamps, vents). Parts under 8% of the asset span get micro framing. Every fourth part and every hero part ends with a pull-back beauty orbit of the whole asset.
- **Motion:** every move starts from the current view, eases in and out, and respects an angular speed cap. There are no snaps; orbit, push in, glide or pull back instead.
- **Look-dev order:** studio set, then key, fill, rim and top lights, then material groups (dark mechanical, armour, inserts, metal, glass, emissive), each followed by a slow orbit so highlights travel across the shell, ending on a turntable.
- **Labels:** the recording carries no on-screen labels unless the user turns the HUD on.

## The brief: presentation/live.toml

Write it with the user when live is chosen. It is not a hashed input, so tuning it never invalidates runs or gate locks. Every section is optional, and unknown keys are errors.

```toml
[pacing]
beat_seconds = 2.0          # base beat length; hero parts get 1.5x
speed = 1.0                 # global multiplier (the sidebar slider multiplies again)
max_degrees_per_second = 40
macro_every = 4             # pull-back beauty orbit every N parts
slate_seconds = 3           # hold before the first part so OBS catches the start
max_stages = 6              # modifier stages shown per part; the last enables the rest
progress_redraw_after = 3   # seconds before a long part starts redrawing while it builds
turntable_seconds = 14

[framing]
elevation = 22
micro_ratio = 0.08

[parts.master_hull]
hero = true
[parts.pads]
cues = [{ kind = "low_glide" }, { kind = "orbit_arc", degrees = 90 }]
[parts.nacelle_drive]
cues = [{ kind = "push_in", azimuth = 140 }]

[lookdev]
sequence = ["set", "key", "fill", "rim", "top", "dark", "armor", "inserts", "metal", "glass", "emissive", "turntable"]
[lookdev.materials]          # existing material name pattern -> stage; unmatched ones are classified from their shader
"M_TaxiGlass" = "glass"
"M_*Trim*" = "inserts"
[lookdev.parts]              # presentation materials for scenes without any (design routes): part -> stage
body_panels = "armor"
pads = "dark"
[lookdev.objects]            # object name pattern -> stage; wins over [lookdev.parts]
"Headlamp * lens" = "emissive"

[studio]                     # linear RGB
background = [0.71, 0.66, 0.60]
floor = [0.42, 0.34, 0.27]   # the cyclorama bowl
ambient = [0.22, 0.20, 0.18]
clay = [0.62, 0.60, 0.57]
[studio.palette]             # override the presentation material of a stage
armor = { color = [0.82, 0.52, 0.02], roughness = 0.3 }
emissive = { color = [0.1, 0.75, 1.0], emission = 8.0 }
```

Cue kinds are `push_in`, `low_glide` (under the body), `top_down` and `orbit_arc`; a cue can fix `azimuth` and `elevation`. Choose hero parts and cues from the reference: the features that sell the asset (sensor clusters, joints and actuators, drive units, lamp bands) deserve push-ins, and undersides deserve a low glide. Map materials whose shader alone does not reveal their role.

Design routes hide every output and carry no materials. A live build shows their design meshes anyway (the master guide until panels replace it), and `[lookdev.parts]` / `[lookdev.objects]` give them presentation materials from the palette (armor, dark, inserts, metal, glass, emissive) taken from the reference's colour scheme. These materials exist only in `live-presentation.blend`.

## Later phase

There is no final rendered shot yet. When it is added it will be a calmer camera than the viewport: a clean three-quarter angle, subtle tracking, Cycles at 1920×1080 or more, 24 or 25 fps. The asset physically leaves the frame (it drives, flies or walks out; no fade) and the shot holds briefly on the empty studio.
