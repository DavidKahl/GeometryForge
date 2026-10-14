def build_parts(p,parts,api):
    for part in parts:
        api.begin(part)
        obj=api.box('editable_PBR_source',(80,50,40),(0,0,20))
        api.finalize_mesh(obj);api.unwrap(obj)
        material=api.pbr_material('M_Source',(.15,.3,.4,1),.5,.3)
        api.set_material(obj,material)
        api.register_output(obj,part,'design')
