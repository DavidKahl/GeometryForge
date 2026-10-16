# Modeling gates (format 3)

Gates turn the top-down hard-surface order into toolkit rules: calibrate the reference, lock one master surface, derive panels from it, then attach detail. They exist because part-by-part iteration on independent cages drifts: each local run builds on the previous imperfect state, and nothing stops proportions or highlight flow from wandering.

## Contract

```toml
format_version = 3

[gates.calibration]
order = 0
kind = "calibration"
cameras = ["primary"]

[gates.master]
order = 1
parts = ["master_hull"]
checks = ["master_closed", "master_silhouette"]
[gates.master.review]
config = "reviews/master.json"     # optional; when given, the review must use this exact file
modes = ["zebra", "silhouette", "overlay"]
min_views = 21                      # default gf_thresholds.review.min_views
iou_views = ["survey21_ref_primary"]
iou_min = 0.8                       # optional; default gf_thresholds.global.silhouette_iou_min

[gates.panels]
order = 2
parts = ["front_body", "cabin", "skirt", "roof"]
checks = ["seam_front_skirt", "recess_lamps", "coverage_hull"]

[gates.detail]
order = 3
parts = ["engines", "pads", "fasteners"]
checks = ["mating_engine_left", "detail_inventory"]
```

- Orders are 0..n-1. Every part belongs to exactly one geometry gate, and parts may depend only on parts in the same or an earlier gate.
- `lock` defaults to the gate's parts.
- Gates run on the design route when `[targets.design]` exists, otherwise on the first output target. Typed gate checks default to that route; legacy checks must list it in `targets`.
- `migrate --format 3` bumps a v2 project (keeping a backup). `gate template` prints this example.

## Frontier

The active gate is the lowest-order gate that is not accepted. Its parts and those of accepted gates are buildable; later parts are dormant.

- `plan`/`run` refuse `--parts` that are dormant ("accept gate X first") or locked ("reopen it deliberately").
- Dormant parts are never built, checked or required in the scene. After a reopen, their objects may remain in the saved scene; runs ignore them.
- If the evaluated geometry of a locked part differs from its accepted hash (a native edit, or a non-deterministic rebuild), the run becomes a candidate and records which gate's lock moved.
- Other routes (game, print) wait as candidates until the final gate is accepted. Textures, baking and optimization come after visual acceptance.
- Accepting a gate changes the route key: the next run builds the newly active gate's parts.

## Accepting

`gate check <project> <gate>` is read-only. A geometry gate is ready when:

1. every earlier gate is accepted;
2. the gate route has a passed safe point holding each selected backend's latest run, the working scene is unchanged and the inputs are current;
3. every gate check passed in that run and met its thresholds (measure-mode checks record misses without failing runs; the gate still requires them). The final geometry gate must declare a `detail` check (see [checks](checks.md)); without one detail can drop out while every surface check passes;
4. if the gate declares a review, the newest complete review of exactly the safe-point Blender scene (and of `review.config` when given) has at least `min_views` views, renders every required mode, and scores `iou_min` (default `silhouette_iou_min`) or better in each `iou_views` view. Lower `iou_min` on an early gate when the reference masks include parts that later gates add, and record why.

A calibration gate is ready when each listed camera is calibrated, its RMS reprojection error is within `max_rms_px`, and its image, mask and correspondences are unchanged since solving.

`gate accept <project> <gate> --by <name> --note "<their words>" [--critique notes.md]` reruns the check and writes `.geometryforge/gates/<gate>/<id>.json` with the run, geometry hashes, check measurements, review report hash, calibration RMS, the critique copy and the approval. **Only run it after the user explicitly approved the evidence**, and quote them in `--note`. The toolkit enforces the evidence; it cannot verify who approved.

`gate reopen <project> <gate> --by <name> --reason "..."` reopens an accepted gate and supersedes every later accepted gate. Records are kept. `gate status` and `context` show the active gate, dormant parts and locked parts.

## Working inside a gate

- Iterate with the smallest `--parts` selection inside the active gate. Prefer measure mode for metrics you are still converging on (silhouette IoU defaults to it).
- Each revision of the master should improve its calibrated silhouette IoU or reach the threshold; the check records `delta_iou` against the previous run.
- For edits inside one part, render `part_id` and `normal` modes before and after and run `review-diff --before <id> --after <id> --parts <edited>`: pixels outside the edited parts (plus a margin) must not change.
