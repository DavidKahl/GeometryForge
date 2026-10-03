from native import flat_rotation
def build(p,d,s,part):
    a=45+(int(part.rsplit('_',1)[1])-1)*90;r=d['R'];foot=7.25*d['scale'];top=d['base']+37;bottom=d['base']+17;t=3.8
    outline=[(r+.8,top),(r+3.5,top),(foot-4,9),(foot,6),(foot,1),(foot-11,1),(foot-11,5),(foot-7,9),(r+.8,bottom-16)]
    obj=s.prism('deployed_leg_frame',outline,t,a)
    hole=s.prism('triangular_lightening_void',[(r+2.3,bottom-11),(r+2.3,top-12),(foot-9,14)],t+2,a);s.cut(obj,hole)
    tab=s.prism('root_tab',[(r-4,d['base']+19.5),(r+2,d['base']+19.5),(r+2,d['base']+30.5),(r-4,d['base']+30.5)],4,a);s.union(obj,tab)
    piston=s.prism('hydraulic_cylinder',[(r+1.8,top-9.3),(r+4,top-10),(foot-6,12),(foot-8,12)],t+.9,a);s.union(obj,piston)
    # Wider foot pad provides a real contact patch when printed separately flat.
    pad=s.prism('landing_foot',[(foot-11.25,0),(foot+.25,0),(foot+.25,4.3),(foot-11.25,4.3)],11,a);s.union(obj,pad)
    s.finish(obj,'engine',flat_rotation(a))
