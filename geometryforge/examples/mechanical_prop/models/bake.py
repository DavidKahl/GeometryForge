def build_parts(p, parts, api):
    if api.__class__.__name__=='Blender':
        import bpy
        sources = [o for o in bpy.context.scene.objects if o.get('gf_bake_source')]
        for obj in list(bpy.context.scene.objects):
            if obj.get('gf_role')=='render' and obj.get('gf_part') in parts:
                api.bake(obj,sources,resolution=p['texture_resolution'],samples=p['bake_samples'],cage_extrusion=3)
    # Houdini materials may use constant PBR values. Projects requiring baked detail
    # must author a native BAKE ROP and call api.bake; unsupported licenses fail explicitly.
