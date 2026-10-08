def build(p,api):
    r,z,h=p['radius'],p['stage1_height'],p['stage2_height']
    obj=api.cylinder('tank',r,z,h)
    c=p['clearance'];j=p['joint_height']
    socket=api.box('lower_socket',(p['joint_width']+2*c,p['joint_depth']+2*c,j+c+1),(0,0,z+(j+c-1)/2))
    api.boolean(obj,socket,'DIFFERENCE')
    peg=api.box('upper_peg',(p['joint_width'],p['joint_depth'],j+1),(0,0,z+h+(j-1)/2))
    api.boolean(obj,peg,'UNION')
    api.finish(obj)
