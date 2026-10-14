def build_parts(p, parts, api):
    if api.__class__.__name__=='Blender':
        import bpy
        for obj in list(bpy.context.scene.objects):
            if obj.get('gf_role')=='collision' and obj.get('gf_part') in parts: bpy.data.objects.remove(obj,do_unlink=True)
    for part in parts:
        api.part=part
        scale = api.derivation['scale'] if api.derivation else 1
        if api.__class__.__name__=='Blender':
            low,high=api.design_bounds()
            obj=api.box('collision',tuple(high[i]-low[i] for i in range(3)),tuple((high[i]+low[i])/2 for i in range(3)))
        else:
            obj=api.box('collision',(p['width']*scale,p['depth']*scale,p['height']*scale),(0,0,p['height']*scale/2))
        api.collision(obj,part)
