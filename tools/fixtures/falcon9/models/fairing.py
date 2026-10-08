def build(p,api):
    z=p['stage1_height']+p['stage2_height'];h=p['fairing_height'];r=p['fairing_radius']
    # An ogive-like two-piece taper keeps native cone/tube parameters editable.
    obj=api.cylinder('lower_shell',r,z,h*.45)
    tip=api.cylinder('nose',r,z+h*.45-.5,h*.55+.5,top_radius=0)
    api.boolean(obj,tip,'UNION')
    c=p['clearance'];j=p['joint_height']
    socket=api.box('keyed_socket',(p['joint_width']+2*c,p['joint_depth']+2*c,j+c+1),(0,0,z+(j+c-1)/2))
    api.boolean(obj,socket,'DIFFERENCE')
    api.finish(obj)
