from design import nose_radius
def build(p,d,s,part):
    z0=d['top']-p['nose_tip_height_mm'];height=p['nose_tip_height_mm']
    outer=[(nose_radius(d,z0+height*i/32),z0+height*i/32) for i in range(33)]
    obj=s.lathe('ceramic_nose_cap',outer,closed=False)
    socket=s.api.cylinder('nose_collar_socket',nose_radius(d,z0+5)-d['wall'],z0-.5,5.5+d['fit'])
    s.cut(obj,socket)
    s.finish(obj,'dark')
