# Contributing

Thanks for your interest in GeometryForge! Bug reports, ideas, documentation fixes and code are all welcome. Please follow the [code of conduct](CODE_OF_CONDUCT.md).

## Before you start

- **Bugs:** open an issue with the bug template. Include `geometryforge doctor` output, your OS, the command you ran and the JSON it printed.
- **Larger changes:** open an issue first to agree on the approach. That saves both of us time.
- **Security issues:** report privately, see [SECURITY.md](SECURITY.md).

## Development setup

You need Python 3.12, [uv](https://docs.astral.sh/uv/) and Node.js 22.

```powershell
uv sync --frozen --extra viewer --extra dev
npm ci --prefix ui
npx --prefix ui playwright install chromium
```

## Tests

```powershell
uv run pytest                      # toolkit, API, installer, kit; no native apps needed
npm run build --prefix ui          # type-check and rebuild the bundled viewer
npm test --prefix ui               # browser tests
```

The browser tests start their own viewer on port 8744 over generated fixture projects (`ui/tests/fixture_server.py`). A stand-in replaces Blender/Houdini there, so they run anywhere. The test that drives Bambu Studio skips itself when Bambu Studio isn't installed. CI runs all of this on Windows and Linux for every pull request.

**Native tests** need real Blender and Houdini installations:

```powershell
uv run python tools/validate_native.py --workspace validation-workspace
```

It builds the desk organizer and a multipart rocket fixture (`tools/fixtures/falcon9`) in both applications and exercises incremental rebuilds, shared interfaces, manual edits and restoration. Use a dedicated GeometryForge Houdini session, never one with your own unrelated scene open. Record native versions, license category and skips in `docs/VALIDATION.md`.

## Guidelines

- **Behavioural tests** for changes to source ownership, evidence reuse, recovery, exports or dependencies. Test effects and preservation of user work, not instruction wording.
- **Keep the core generic.** Example and project geometry belong in `geometryforge/examples`, `projects/` or test fixtures, never inside toolkit modules.
- **Declare all inputs.** Recipe and check inputs must be declared so caches can't hide changes.
- **One canonical skill** lives in `geometryforge/skill`. After editing it, refresh the repository's own copies with `uv run geometryforge install-skill --target .` and commit both.
- **Rebuild the viewer** after changing `ui/src` and commit `geometryforge/web_dist`. CI fails if the bundle doesn't match the sources.
- **The viewer stays an inspection app:** no build orchestration, model providers or credentials.
- **Be honest in docs and evidence.** Never claim a native check, slicer review or physical print that didn't happen.
- Match the surrounding code style. Keep commits focused, and describe *why* in the message.

## Releasing

1. Update `CHANGELOG.md` and the version in `pyproject.toml` and `geometryforge/__init__.py`.
2. Run the full test suite, and the native validation if native code changed.
3. `uv build`, then install the wheel into a clean environment and run `geometryforge doctor` and the desk-organizer example.
4. Tag `vX.Y.Z` and create a GitHub release. Attach the wheel, and the showcase print package made by `projects/astraeus_lander/tools/package_release.py`.
