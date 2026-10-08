# Third-party notices and provenance

## Bundled software

The prebuilt viewer in `geometryforge/web_dist` includes [Three.js](https://github.com/mrdoob/three.js) (MIT, copyright the Three.js authors). Its full license ships beside the compiled assets as `THREE-LICENSE.txt`.

Python dependencies (numpy, scipy, trimesh, networkx, psutil, Pillow, and optionally FastAPI and Uvicorn) are installed separately under their own licenses and are not redistributed here. Node.js build tools (TypeScript, Vite, Playwright) are development-only.

Blender, Houdini and Bambu Studio are separately installed applications under their own licenses and are not distributed with GeometryForge. Files produced with Houdini Apprentice or Indie remain subject to SideFX's license terms. The optional Bambu Studio integration reads presets from your local installation and does not redistribute them.

## Original work

Scene helpers, mesh and export validation, the 3MF writer, process isolation and the Houdini session transport were adapted from the author's earlier, unpublished GeometryForge prototype. Its domain-specific geometry and provider integrations are not included.

The desk organizer example, the rocket test fixture (`tools/fixtures/falcon9`) and the Astraeus Heavy Lander are original geometry under this project's MIT license. The rocket fixture is a simplified generic shape, not affiliated with or endorsed by SpaceX, and contains no logos or downloaded models.

The Astraeus Heavy Lander concept sheet (`projects/astraeus_lander/references/astraeus-concept-sheet.png`) was created by the author with AI image generation and is provided under this project's MIT license. The Astraeus Heavy Lander is a fictional vehicle.
