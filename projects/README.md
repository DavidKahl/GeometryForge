# Showcase projects

Complete GeometryForge projects built by an agent with the toolkit. Each folder is a standalone project: modeling code, checks, parameters, decisions and documentation.

| Project | What it shows |
|---|---|
| [`astraeus_lander`](astraeus_lander) | A 480 mm, 22-part display model built from one concept sheet. Native Blender and Houdini versions, eight interface checks, fit coupon, and a four-colour filament plan with a Bambu Studio print kit. |

Run records and native working scenes (`.geometryforge/`, `working/`) aren't in git: they're large and machine-specific. To print a project without Blender or Houdini, download its print package from the [releases](https://github.com/DavidKahl/GeometryForge/releases). To rebuild it yourself:

```powershell
uv run geometryforge register projects/astraeus_lander
uv run geometryforge plan projects/astraeus_lander
uv run geometryforge run projects/astraeus_lander
```

Read a project's README first. Some need extra check dependencies or a specific application.
