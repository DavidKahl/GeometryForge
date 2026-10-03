from math import pi,cos,sin
def build(p,d,s,part):
    r=d['R']-d['wall']-d['fit'];z=d['base'];ring=2.4*d['scale']
    obj=s.lathe('engine_bulkhead',[(r,z),(r,z+5)],closed=False)
    for i in range(7):
        xy=(0,0) if i==0 else (ring*cos((i-1)*pi/3),ring*sin((i-1)*pi/3))
        tool=s.api.cylinder('engine_mount_socket',2.45+d['fit'],z-.5,4.8,xy);s.cut(obj,tool)
    # An outer stiffening ring is integrated into the bulkhead.
    rim=s.lathe('bulkhead_rim',[(r-2,z+4),(r,z+4),(r,z+7),(r-2,z+7)]);s.union(obj,rim)
    s.finish(obj,'engine')
