def build_parts(p, parts, api):
    import bpy
    for part in parts:
        api.begin(part)
        if api.target == 'design':
            obj = api.box('detailed_housing', (p['width'],p['depth'],p['height']), (0,0,p['height']/2))
            bevel = obj.modifiers.new('Editable edge radius','BEVEL')
            bevel.width = 2; bevel.segments = 5
            for x in (-p['width']*.3,p['width']*.3):
                tool = api.cylinder('recess',3,p['height']-2,4,(x,0))
                api.boolean(obj,tool,'DIFFERENCE')
            obj.data.materials.append(api.pbr_material('M_Detail',(.18,.32,.42,1),.45,.7))
            api.register_output(obj,part,'design')
        elif api.target == 'game':
            sources = api.load_design()
            scale = api.derivation['scale'] if api.derivation else 1
            api.scale_design(scale)
            low,high=api.design_bounds()
            if api.profile.get('profile') == 'unreal_desktop_nanite':
                obj = sources[0].copy(); obj.data = sources[0].data.copy()
                bpy.context.scene.collection.objects.link(obj)
            else:
                obj = api.box('render_housing',tuple(high[i]-low[i] for i in range(3)),tuple((high[i]+low[i])/2 for i in range(3)))
                bevel = obj.modifiers.new('Editable game bevel','BEVEL'); bevel.width=1.5*scale; bevel.segments=1
            obj.hide_set(False); obj.hide_render=False
            api.register_output(obj,part,'render',sockets=[{'name':'Attachment','position_mm':[0,0,p['height']*scale]}])
        elif api.target == 'print':
            sources = api.load_design()
            api.scale_design(api.derivation['scale'] if api.derivation else 1)
            obj = sources[0].copy(); obj.data = sources[0].data.copy()
            bpy.context.scene.collection.objects.link(obj)
            api.mark(obj); api.finish(obj)
