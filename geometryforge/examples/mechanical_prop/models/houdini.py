def build_parts(p, parts, api):
    from geometryforge import houdini_scene
    for part in parts:
        api.begin(part)
        scale = api.derivation['scale'] if api.derivation else 1
        dimensions=(api.derivation['outputs']['houdini'][part]['bbox_mm'] if api.derivation else [p['width'],p['depth'],p['height']])
        obj = api.box('housing',tuple(v*scale for v in dimensions),(0,0,dimensions[2]*scale/2))
        if api.target == 'print':
            api.finish(obj)
        else:
            api.register_output(obj,part,'design' if api.target=='design' else 'render')
            houdini_scene.PARTS[part] = obj
