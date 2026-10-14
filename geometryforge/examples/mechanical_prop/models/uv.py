def build_parts(p, parts, api):
    if api.request.get('target') != 'game': return
    if api.__class__.__name__ == 'Blender':
        import bpy
        for obj in list(bpy.context.scene.objects):
            if obj.get('gf_role')=='render' and obj.get('gf_part') in parts:
                api.finalize_mesh(obj); api.unwrap(obj)
    else:
        from geometryforge.houdini_scene import PARTS
        for part in parts: api.finalize_mesh(PARTS[part]); api.unwrap(PARTS[part])
