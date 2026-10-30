# Architecture

The skill guides decisions and modeling inside the host agent. The CLI performs deterministic native execution, snapshotting, validation and artifact management. The optional loopback app reads this same file-backed state and edits only the project catalog. There is no embedded agent, job service, credential store or database.

## Evidence and ownership

A run snapshots its declared procedural/check inputs and chosen saved native file before execution. Backend workers use the copied sources and write new native scenes, then reopen them. Working outputs are new copies, never overwrites. SHA-256 hashes detect saved edits, unstable input capture and changed reusable artifacts. Retained snapshots are immutable by convention rather than OS permissions; hash mismatches prevent restoration/reuse.

Each part has source and parameter dependencies, stable identity, and dependency edges to affected parts. Native workers replace only selected ownership groups. Full scene inspection detects unexpected changes to unselected evaluated geometry. Manual-scene continuation can accept multiple changed parts and select the corresponding checks. Unknown part identities require updating the project contract before a safe point is possible.

Generic validation and print exports are cached by evaluated geometry, export metadata, print constraints, native version and toolkit code fingerprint. Functional checks add all declared geometry, parameters, checker sources and check configuration. A reused result is evidence attached to the same inputs, not an unconditional skip. Artifacts preserve assembly coordinates separately from centered print coordinates.

Safe points require every requested backend. Native parity compares part identities, dimensions (0.1 mm tolerance), volumes (1% tolerance), and shared measured functional checks. These are geometric checks, not proof that arbitrary artistic histories are equivalent. Reconciliation is agent-authored work; no automatic Blender/Houdini history translation is attempted.

## Whole-model files

After a backend's parts and checks pass, the run writes `kit/assembled.3mf` (assembly coordinates) and `kit/kit-raw.3mf` (print orientation, non-overlapping layout) from the same evaluated geometry. Each part is one 3MF object; each body carries its filament slot as a Bambu-compatible extruder assignment, and slots must exist in `decisions.print.filaments` when a plan is declared. Both files are read back and compared slot for slot. If `decisions.print.bambu` names installed presets, the local Bambu Studio CLI arranges the kit onto plates and stamps the planned filament colours (`kit.3mf`, `assembled-bambu.3mf`); those files are read back as well, checking slots, colours and that every part was placed. These files are rebuilt on every run rather than reused, because they are cheap and must always match the evaluated scene. Nothing is sliced or sent to a printer.

## Failure and recovery

Per-project OS locks serialize modifications. Atomic state/manifest writes prevent torn JSON. Candidates, failures and cancellation preserve the prior safe point. An interrupted process leaves its run record available, and the viewer labels a non-live running owner as interrupted. Source conflicts and ambiguous scope return a candidate with a reason; full checks are explicit.

Houdini uses a dedicated owned GUI process with authenticated JSON loopback requests, cooperative cancellation and recovery saves before scene replacement. Actual license capabilities determine native formats. Blender uses background subprocesses by default; `--live` runs the same build steps in a dedicated, visible Blender GUI over the same transport, one recipe call per part with a scripted viewport reveal, and writes its evidence scene before any presentation changes. Native modules are never imported into the host environment.

## Independent v2 delivery routes

v1 projects retain their original print behavior. The v2 target coordinator normalizes route contracts into the native engine, with independent working scenes/backend state, part/output mappings, preparation fingerprints and package safe points. Optional shared design precedes delivery; frozen cross-route derivation avoids cyclic live dependencies. Failure in one route cannot replace another route's safe point, and aggregate promotion requires every requested route/backend.

Game extraction preserves per-corner shading/UV data, materials, asset-local transforms, collision/LOD roles and sockets. Print validation/3MF kits run only for the print target. Preparation stages are explicit agent-authored recipes; verification never invokes them or promotes changed-but-unapplied preparation. Stage dependencies isolate material, bake, LOD and collision work from source geometry. Retained textures are hashed and packaged; packed Blender images survive copied native scenes. Evidence hashes normalize relocated texture paths by content hash, and bounded native float32 recooking tolerance prevents cache churn while topology and identities remain exact. Frozen derivation does not depend on the latest live design scene.

Game packages carry file hashes, native FBX read-back evidence, independently written/read GLBs and PBR conventions. Unreal is an optional editor-only adapter with its own import records/safe pointer and managed versioned namespaces. Saved-asset verification is independent of rendered review/performance. The viewer reads route/import evidence and serves game artifacts under the same retained-directory boundaries; it adds no execution endpoints.

## Viewer access boundary

FastAPI serves bundled offline assets and registered-project evidence. Metadata writes require a session token and same-origin requests; Host is restricted to loopback. Artifact paths must stay inside retained run directories, including resolved symlinks. Project code is not executed by browser endpoints.
