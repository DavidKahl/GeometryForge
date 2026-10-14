def build_parts(p, parts, api):
    if api.profile.get('profile')=='unreal_desktop_nanite': return
    if api.__class__.__name__=='Blender':
        import bpy
        for obj in list(bpy.context.scene.objects):
            if obj.get('gf_role')=='lod' and obj.get('gf_part') in parts: bpy.data.objects.remove(obj,do_unlink=True)
        for obj in list(bpy.context.scene.objects):
            if obj.get('gf_role')=='render' and obj.get('gf_part') in parts: api.lods(obj)
    else:
        from geometryforge.houdini_scene import PARTS
        for part in parts: api.lods(PARTS[part])
