from design import tube_profile,seamed_profile,nose_radius

def build(p,d,s,part):
    r,w,c,j=d['R'],d['wall'],d['fit'],d['joint']
    spans={'aft_hull':(d['base'],d['aft']),'tank_lower':(d['aft'],d['mid']),'tank_upper':(d['mid'],d['tank']),'cargo':(d['tank'],d['cargo'])}
    if part=='nose':
        z0,z1=d['cargo'],d['top']-p['nose_tip_height_mm'];h=z1-z0
        # Smooth pointed ogive, with a rounded 1.6 mm printable apex.
        heights={z0+h*i/48:0 for i in range(49)}
        for index in range(1,int(h/9)):
            height=z0+index*9
            for dz,depth in [(-.45,0),(-.2,.22),(.2,.22),(.45,0)]:heights[height+dz]=depth
        outer=[(nose_radius(d,z)-depth,z) for z,depth in sorted(heights.items())]
        peg=nose_radius(d,z1+5)-w-c
        inner=[(rad-w,z) for rad,z in reversed(outer) if z0+j+2<z<z1-3]
        profile=outer+[(peg,z1),(peg,z1+5),(peg-1.4,z1+5),(peg-1.4,z1-3)]+inner+[(r-w,z0+j+2),(r-w,z0)]
        obj=s.lathe('ogive_with_inner_wall',profile)
        # Canard root pockets are in the broad lower ogive.
        for a in (0,90,180,270):
            cut=s.radial_box('canard_socket',r-2.6,z0+18,3.8+2*c,10+2*c,9,a)
            s.cut(obj,cut)
        s.finish(obj)
        return
    z0,z1=spans[part]
    profile=tube_profile(d,z0,z1,part=='tank_upper')
    if part=='aft_hull':
        profile=[(r+.5,z0),(r+.5,z0+2),(r,z0+2)]+profile[1:]
    obj=s.lathe('welded_shell_with_slip_collar',profile)
    # Shallow engraved longitudinal panel boundaries and recessed service hatches.
    seam_top=z1-d['band']-1 if part=='tank_upper' else z1-2
    for a in (30,90,150,210,270,330):
        tool=s.radial_box('panel_seam',r+.36,(z0+seam_top)/2,.5,seam_top-z0-2,1.3,a)
        s.cut(obj,tool)
    for a in range(15,360,30):
        s.cut(obj,s.radial_cylinder('recessed_fastener',r+.1,z0+5,.65,1.1,a))
        if part=='cargo':
            s.cut(obj,s.radial_cylinder('cargo_upper_fastener',r+.1,z1-6,.65,1.1,a))
    for a in ((30,150,240) if part in ('aft_hull','tank_lower') else (0,120,240)):
        z=z0+(seam_top-z0)*.48
        frame=s.radial_box('service_hatch_frame',r+.12,z,6,19,1.35,a);s.union(obj,frame)
        inset=s.radial_box('recessed_access_panel',r+.85,z,3.8,15,1.15,a);s.cut(obj,inset)
        for dz in (-7,7):
            handle=s.radial_box('hatch_latch',r+.63,z+dz,1.8,1.0,.5,a);s.union(obj,handle)
    if part in ('aft_hull','tank_lower'):
        # Two radial tabs per aft fin; each pocket belongs to its owning hull section.
        z=d['base']+20 if part=='aft_hull' else d['aft']+18
        for a in (0,90,180,270):
            tool=s.radial_box('fin_tab_socket',r-1.1,z,3.2+2*c,9+2*c,5,a);s.cut(obj,tool)
    if part=='aft_hull':
        for a in (45,135,225,315):
            tool=s.radial_box('landing_leg_socket',r-1,d['base']+25,4+2*c,11+2*c,5,a);s.cut(obj,tool)
    s.finish(obj)
