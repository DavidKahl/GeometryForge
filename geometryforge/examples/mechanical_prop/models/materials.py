def build_parts(p, parts, api):
    material = api.pbr_material('M_Housing',(.18,.32,.42,1),p['roughness'],p['metallic'])
    if api.__class__.__name__=='Blender':
        import bpy
        detail=api.pbr_material('M_Detail',(.18,.32,.42,1),p['roughness'],p['metallic'])
        for obj in bpy.context.scene.objects:
            if obj.type=='MESH' and obj.get('gf_source_role')=='construction' and not obj.data.materials:
                obj.data.materials.append(detail)
            if obj.get('gf_role')=='render' and obj.get('gf_part') in parts:
                obj.data.materials.clear(); obj.data.materials.append(material)
    else:
        from geometryforge.houdini_scene import PARTS
        for part in parts: api.set_material(PARTS[part],material)
