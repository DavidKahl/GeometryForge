# Frozen game/print derivation

Author the destination builder first. Declare `targets.<route>.derivation_recipe`, dependencies, source-part/output mappings, required checks and `conversion_notes`. Then `derive <project> --target print|game --from-run <id> --from-target design|print|game --scale <positive factor>`. The source route must have passed; its retained native scenes and artifacts are hashed and checked before use. The destination recipe is snapshotted independently.

`api.derivation` carries source run, route, scale, native scenes, hashes, recipe and notes. `api.load_design()` uses the frozen source during derivation. Prefer retained detailed construction where it corresponds to the selected asset. Preserve geometric-source scale; do not substitute the latest working design for an older requested source.

Print to game: recover intended in-game scale, merge unnecessary print splits, remove print-only assembly features, reconsider enlarged details, and add pivots, UVs/PBR, LOD or Nanite preparation and simplified collision. Keep a clear mapping from print parts to game outputs. Existing flattened meshes do not recover native construction history.

Game to print: apply physical scale to the entire construction, including cutters and dependent tools; close open surfaces, add thickness, resolve shells, strengthen details and split for the recorded printer/process. Add joints, orientation and support/assembly guidance. Rebuild meaningful detail from source geometry. Tangent normal maps do not uniquely encode a printable displacement field.

Use measured landmarks and normalized views to compare route intent; volume/topology equality across print and game is inappropriate. Record deliberate differences. Package-safe, slicer-reviewed and physically tested remain distinct evidence levels. Failures preserve the source route and previous destination safe point.
