# Working on GeometryForge

GeometryForge is a portable modeling skill, deterministic Python toolkit, and optional local evidence viewer. The user's agent harness owns conversations, decisions and modeling. Do not add embedded model providers, credentials, chat orchestration or browser build controls.

- Use Python 3.12: `uv sync --frozen --extra viewer --extra dev`.
- Run `uv run pytest`; build the viewer with `npm ci --prefix ui` and `npm run build --prefix ui`, then `npm test --prefix ui` (self-contained fixture projects on port 8744). Commit the rebuilt `geometryforge/web_dist`.
- Use `geometryforge context <project>` before modeling or revising an example. Read `geometryforge/skill/SKILL.md` and only the relevant references.
- Preserve manual working scenes and retained run snapshots. New run records do not imply complete regeneration. Check dependency closure and evidence keys before reuse.
- Run native integration tests only against dedicated managed scenes. Set GEOMETRYFORGE_BLENDER/GEOMETRYFORGE_HOUDINI for local executables; do not hardcode personal paths in the package.
- Maintain one canonical skill under geometryforge/skill. Installer copies it into harness discovery folders, detecting local conflicts.
- Example templates belong under geometryforge/examples and test fixtures under tools/fixtures; never inside generic toolkit logic. All projects built with GeometryForge live outside the repository in `GF_Projects` (`E:\Projects\GF_Projects`, resolved automatically when passing a bare project name to `geometryforge init <name>` or `geometryforge context <name>`), never inside the `GeometryForge` checkout. Both native backends must remain meaningfully editable.
- After editing the canonical skill, refresh both the repository's and `GF_Projects`'s installed copies with `uv run geometryforge install-skill --target .` and `uv run geometryforge install-skill --target ../GF_Projects` (plus `--user` if installed globally).
- User-facing docs live in README.md and docs/GUIDE.md; update them, CHANGELOG.md and docs/VALIDATION.md with behaviour changes.
- Tests, docs, viewer bundle and package data are release deliverables. Report which native checks actually ran and never imply physical print testing.
