import math

def build(p,api):
    r,h=p['radius'],p['stage1_height']
    obj=api.cylinder('tank',r,0,h)
    peg=api.box('keyed_peg',(p['joint_width'],p['joint_depth'],p['joint_height']+1),(0,0,h+(p['joint_height']-1)/2))
    api.boolean(obj,peg,'UNION')
    for i in range(9):
        a=2*math.pi*i/8
        center=(0,0) if i==8 else (r*.48*math.cos(a),r*.48*math.sin(a))
        engine=api.cylinder(f'engine_{i}',r*.12,-3,4,center)
        api.boolean(obj,engine,'UNION')
    api.finish(obj)
