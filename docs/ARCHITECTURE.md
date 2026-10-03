# Architecture

The skill guides decisions and modeling inside the host agent. The CLI performs deterministic native execution, snapshotting, validation and artifact management. The optional loopback app reads this same file-backed state and edits only the project catalog. There is no embedded agent, job service, credential store or database.

## Evidence and ownership

A run snapshots its declared procedural/check inputs and chosen saved native file before execution. Backend workers use the copied sources and write new native scenes, then reopen them. Working outputs are new copies, never overwrites. SHA-256 hashes detect saved edits, unstable input capture and changed reusable artifacts. Retained snapshots are immutable by convention rather than OS permissions; hash mismatches prevent restoration/reuse.

Each part has source and parameter dependencies, stable identity, and dependency edges to affected parts. Native workers replace only selected ownership groups. Full scene inspection detects unexpected changes to unselected evaluated geometry. Manual-scene continuation can accept multiple changed parts and select the corresponding checks. Unknown part identities require updating the project contract before a safe point is possible.

Generic validation and print exports are cached by evaluated geometry, export metadata, print constraints, native version and toolkit code fingerprint. Functional checks add all declared geometry, parameters, checker sources and check configuration. A reused result is evidence attached to the same inputs, not an unconditional skip. Artifacts preserve assembly coordinates separately from centered print coordinates.

Safe points require every requested backend. Native parity compares part identities, dimensions (0.1 mm tolerance), volumes (1% tolerance), and shared measured functional checks. These are geometric checks, not proof that arbitrary artistic histories are equivalent. Reconciliation is agent-authored work; no automatic Blender/Houdini history translation is attempted.

## Failure and recovery

Per-project OS locks serialize modifications. Atomic state/manifest writes prevent torn JSON. Candidates, failures and cancellation preserve the prior safe point. An interrupted process leaves its run record available, and the viewer labels a non-live running owner as interrupted. Source conflicts and ambiguous scope return a candidate with a reason; full checks are explicit.

Houdini uses a dedicated owned GUI process with authenticated JSON loopback requests, cooperative cancellation and recovery saves before scene replacement. Actual license capabilities determine native formats. Blender uses background subprocesses. Native modules are never imported into the host environment.

## Viewer boundary

FastAPI serves bundled offline assets and registered-project evidence. Metadata writes require a session token and same-origin requests; Host is restricted to loopback. Artifact paths must stay inside retained run directories, including resolved symlinks. Project code is not executed by browser endpoints.
