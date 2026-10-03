# Contributing

Use Python 3.12. Install with `uv sync --frozen --extra viewer --extra dev`. Run `uv run pytest`. Build bundled viewer assets with `npm ci --prefix ui` and `npm run build --prefix ui`; browser tests use Playwright Chromium (`npx playwright install chromium` from ui).

Changes to source ownership, evidence reuse, recovery or dependencies need behavioral tests. Test effects and preservation, not particular instruction wording. Keep example geometry out of core modules. Declare all recipe/check inputs so caches cannot hide changes. Verify package contents with `uv build` before release.

Native tests require actual installed applications and run only when enabled. Use a dedicated GeometryForge Houdini session. Do not attach to a user's unrelated scene. Record native versions, license category and skips in validation evidence. Never advertise a physical print test that was not performed.

Canonical skill content lives under geometryforge/skill; generated installations are not separate authored copies. Review skill routing and edit-preservation behavior after changes. The viewer must remain an inspection/catalog app without build orchestration or provider authentication.
