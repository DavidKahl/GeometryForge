from native import flat_rotation
def build(p,d,s,part):
    a=(int(part.rsplit('_',1)[1])-1)*90;r=d['R'];lo=d['base'];high=d['aft']+44;tip=6.5*d['scale'];t=p['fin_thickness_mm']
    outline=[(r+.2,lo+4),(tip,lo-4),(tip,lo+38),(r+.2,high)]
    obj=s.prism('swept_aft_fin',outline,t,a)
    inset=[(r+2,lo+9),(tip-2,lo+2),(tip-2,lo+36),(r+2,high-7)]
    panel=s.prism('raised_armored_panel',inset,t+.7,a,tangent=.35);s.union(obj,panel)
    # Raised split line across the aerodynamic panel.
    rib=s.prism('panel_stiffener',[(r+1,lo+34),(tip-.5,lo+24),(tip-.5,lo+25.2),(r+1,lo+35.2)],t+1.15,a,tangent=.575);s.union(obj,rib)
    for z in (lo+20,d['aft']+18):
        tab=s.prism('assembly_tab',[(r-3,z-4.5),(r+1,z-4.5),(r+1,z+4.5),(r-3,z+4.5)],3.2,a);s.union(obj,tab)
    s.finish(obj,'dark',flat_rotation(a))
