# Mechanical housing

A small editable source design with conventional/Nanite game representations and a printable derivative. Blender retains bevel/Boolean construction, unwraps the render mesh, bakes base color, normal, roughness, metallic and occlusion, and supplies LODs, collision and a socket. The 256-pixel bake is deliberately small for a quick example; change texture_resolution for production work.

Use `geometryforge init <folder> --example mechanical_prop --target game --deliverables blender`, then `plan` and `run`. Houdini uses native SOP geometry and PBR constants; detailed texture baking requires an authored native BAKE network and a supported license. Do not interpret this fixture as proof that the two backends produce identical artistic detail.
