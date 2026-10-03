def build(p,d,s,part):
    r,z,h=d['R'],d['tank']-d['band'],d['band']
    outer=[(r,z+h*i/128) for i in range(129)]
    profile=outer+[(r-d['wall']+d['fit'],z+h),(r-d['wall']+d['fit'],z)]
    obj=s.lathe('continuous_tile_sleeve',profile,segments=768)
    s.hex_surface(obj,r,z,h,cell=p['tile_side_mm'])
    s.finish(obj,'dark')
