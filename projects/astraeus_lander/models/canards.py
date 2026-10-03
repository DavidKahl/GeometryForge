from native import flat_rotation
from design import nose_radius
def build(p,d,s,part):
    a=(int(part.rsplit('_',1)[1])-1)*90;r=d['R'];z=d['cargo'];t=3.8
    outline=[(nose_radius(d,z+9)+.3,z+9),(r+10,z+4),(r+9,z+20)]
    outline += [(nose_radius(d,z+dz)+.3,z+dz) for dz in (54,45,36,27,18)]
    obj=s.prism('forward_swept_canard',outline,t,a)
    panel_outline=[(r+1,z+12),(r+8,z+8),(r+6,z+19),(nose_radius(d,z+40)+3,z+40)]
    panel_outline += [(nose_radius(d,z+dz)+2,z+dz) for dz in (34,26,18)]
    panel=s.prism('reinforced_control_panel',panel_outline,t+.65,a,tangent=.325);s.union(obj,panel)
    tab=s.prism('keyed_root',[(r-6,z+13),(r+1,z+13),(r+1,z+23),(r-6,z+23)],3.8,a);s.union(obj,tab)
    s.finish(obj,'dark',flat_rotation(a))
