# Manual edits and incremental evidence

The working scene is editable; snapshots are retained evidence. context detects saved-file hashes, not unsaved app changes. Ask the user to save when the latest edits are still in memory.

After edits, the prior SAFE POINT is marked as predating the current working files. Offer continuing the edited scene, reconciling it into procedural sources/the other backend, or restoring a separate copy. `adopt` can register a new saved file. `run --source scene` explicitly continues native edits. `run --source code` explicitly applies changed/selected builders to a copy of the scene; it can replace edits in those selected parts, so choose it only when that matches the user's intent.

An incremental run inspects evaluated part changes and follows declared dependencies to select checks. Fresh affected checks plus valid unchanged evidence can establish a new safe point. Missing part identities, unexpected effects, conflicting sources or incomplete backend parity retain a candidate. Explain why scope is uncertain and offer investigation or `verify --full`; do not silently run everything.

Full verification uses edited native files, not pristine generators. If native modifications depart from recorded dimensions, reconcile the brief/parameters/check requirements explicitly. Do not weaken checks merely to obtain a pass. A restored native scene and its matching procedural inputs are copied together; existing work remains intact.

Printer/process changes are design revisions too. Follow [printer and process changes](printing.md#printer-and-process-changes): compare effective constraints, update affected geometry-driving parameters and checks, and preserve native edits. A changed printer label does not redesign a model, and a previously sliced or physically fitted part may need new evidence even when its mesh is unchanged.
