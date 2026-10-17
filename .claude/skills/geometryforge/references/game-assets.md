# Game assets

Support static props, modular pieces and rigid assemblies first. Rigging, skinning, animation, foliage systems and terrain authoring are outside this release. Your harness owns reference interpretation and modeling; GeometryForge has no embedded generator or agent queue.

## Establish the game brief

Start reference-driven work with the reference intake in [SKILL.md](../SKILL.md#reference-intake): ask the route, map coverage, and either request missing views or get explicit acceptance of the listed assumptions. Hero props seen up close need far more coverage than background pieces.

Record intended dimensions, camera/viewing distance, reference assumptions, style, conventional/Nanite profile, budgets, material regions, pivot, grid, sockets, collision and lighting. Keep game dimensions separate from physical print scale. Internal units remain mm; FBX/Unreal delivery converts to centimeters and GLB preview to meters/Y-up.

Conventional defaults: 20,000 base triangles/output, two used material slots, 2048-pixel material maps, LOD ratios 1/.5/.25/.125. Nanite defaults: 250,000 source triangles/output, two materials, 2048-pixel maps, independent convex collision and recorded fallback error. Defaults are configurable production budgets, not universal engine limits. Fail and revise or change the profile; never silently sacrifice requested detail.

## Geometry and materials

For close-up reference fidelity follow [surface modeling](surface-modeling.md) before material work. Review broad curvature, panels and mechanical detail separately. Dense source geometry and a technically valid package do not establish visual acceptance. Keep useful geometric seams and relief on the detailed master; reserve bake-only detail for features appropriate to the camera distance.

Retain an editable detailed source. Choose silhouette-aware simplified construction or retopology for conventional meshes; decimation alone is not a general solution. Finalize render triangulation before UV authoring/baking. Blender unwrap retains the preparation construction separately and unwraps evaluated topology. Preserve seams, custom normals/tangents and material indices. Open render surfaces are permitted; UCX collision must be closed and convex.

Use `api.pbr_material`, `finalize_mesh`, `unwrap`, `bake`, `lods` and `collision`, or direct native APIs. Blender baking supplies base color, tangent normals, roughness, metallic and AO with explicit source correspondence/settings. Bake one material region per helper call; author multiple-region workflows explicitly. Houdini baking executes a project-authored BAKE ROP rather than translating Blender shaders automatically.

Save imported texture images and declare their source files. Base/emissive maps are sRGB; normals and roughness/metallic/AO are non-color. Packages write DirectX Unreal normals and OpenGL preview normals. ORM is R=occlusion, G=roughness, B=metallic. Do not call a shaded viewport proof that material color spaces or baking are correct.

Conventional LODs preserve placement/pivots and shading. Modular assets add measured grid/interface checks. Declare traversable openings and collision clearance checks; convex collision enclosing a doorway is geometrically valid but functionally wrong. Physics assets use appropriate simple hulls. Baked lighting requires a separate unique lightmap UV channel; dynamic lighting does not.

Nanite retains useful geometric detail but still has material, storage, instance and hardware costs. Explicitly split unsupported materials into conventional outputs. Configure fallback behavior and validate it in the destination engine. Never label an arbitrary dense print mesh Nanite-ready.

## Hero assets on Nanite

These practices come from a gated hero vehicle taken to the Nanite profile. Its game runs never reached `passed`, so treat them as guidance and verify each one with your own checks.

- **Render meshes come from the retained design.** Evaluate the accepted design with its panel subdivision at a lower game level (for example 2 instead of 3), and merge the evaluated objects per output in world space. Bevels, seams, bolts and louvres stay real geometry; decimation would erase them. Keep the full-level design objects in the scene as bake sources.
- **Split outputs to fit the budget.** Group parts into outputs (body, lower hull, details, drives, pads) so each stays within 250k triangles. Declare glass and interior as conventional outputs (`nanite=False`), because Nanite does not render translucency. Give purely decorative outputs no collision.
- **Base colour from `api.bake` darkens metal.** The helper bakes base colour with Cycles' DIFFUSE colour pass, which scales colour by (1 − metallic), so bare metal bakes black. Until the helper changes, re-bake albedo as an EMIT bake of each source's Base Color input, into a fresh image (re-packing an already packed image keeps its old pixels). The helper bakes no emissive map either: add an EMIT bake with the same cage, with emission strength set to 1 on emissive source materials and 0 on the rest.
- **Clean before unwrapping.** Bevels and Booleans leave zero-area slivers and needle triangles. MikkTSpace leaves needles without a tangent, so collapse their short edges, renormalize custom normals, and give the face normal to any corner still without a tangent. After smart projection, re-project and repack overlapping faces at a smaller angle limit, and fall back to lightmap islands for any that still overlap.
- **LODs for conventional outputs.** Collapse decimation of thin glass slabs makes degenerate triangles: build glass LODs from the single-sided outer panes instead. A small interior of simple boxes keeps its topology at every level, with a clean lightmap atlas. Remove zero-area triangles after baking; they cover no texels.
- **Strictly convex collision.** Convex hulls of render vertices inherit thousands of nearly coplanar facets and can fail convexity checks. Use support points along fixed directions (a k-DOP), snapped to a 10–20 mm grid, then limited dissolve and re-hull, and split each output into several hulls by region (front/rear, left/right, per pad).

## Deliver and inspect

Read package reports and export round-trip evidence. Deliver the package ZIP plus editable sources. The viewer supports PBR, wireframe, LOD, collision, pivots/sockets and representation comparison. Unreal integration is editor-only and currently checks the 5.8 API; it uses versioned managed folders and protects artist-modified imports. Imported properties and saved assets are verified separately from rendered review/performance.

Use `unreal review --import <id> --uproject ...` for offscreen native appearance and editor profiling evidence. Inspect the captured image; do not promote a checkerboard/default shader as a correct PBR result. Review rejects managed shader compilation errors, retains profiler CSVs, and records resolution, scene density and hardware. Editor profiling is not a cooked-game performance guarantee.

Relevant official references: [FBX static mesh pipeline](https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine), [PBR](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine), [Nanite](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine).
