def build(p,api):
    w,d,j,c=[p[k] for k in ('joint_width','joint_depth','joint_height','clearance')]
    male=api.box('male_base',(w+6,d+6,2),(110,-20,1))
    peg=api.box('male_key',(w,d,j+1),(110,-20,2+(j-1)/2))
    api.boolean(male,peg,'UNION');api.finish(male,bodies=2)
    female=api.box('female_base',(w+6,d+6,j+3),(110,5,(j+3)/2))
    socket=api.box('female_socket',(w+2*c,d+2*c,j+1),(110,5,3+(j+1)/2))
    api.boolean(female,socket,'DIFFERENCE');api.finish(female,bodies=2)
