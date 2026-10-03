from math import pi,cos,sin
def build(p,d,s,part):
    rb=.7*d['scale'];ring=3.1*d['scale']-rb;z=5;top=d['base'];wall=1.2
    profile=[(rb,z),(rb+.35,z+.6),(rb+.35,z+1.5),(rb-.2,z+2),(rb*.83,z+5),(rb*.55,z+10),(2.5,top-7),
             (2.9,top-6.5),(2.9,top-5),(2.7,top-4),(2.7,top),(2.45,top),(2.45,top+4),(1.2,top+4),
             (1.2,top-5),(max(1.2,rb*.4-wall),top-7),(rb*.55-wall,z+10),(rb*.83-wall,z+5),(rb-wall,z)]
    # Cooling-jacket ridges are part of the revolved wall, not separate floating rings.
    outer=profile[:7];ribbed=[]
    for index,(radius,height) in enumerate(outer[:-1]):
        ribbed.append((radius,height));next_r,next_z=outer[index+1]
        if next_z-height>2:
            middle=(height+next_z)/2
            for dz,relief in [(-.5,0),(-.32,.35),(.32,.35),(.5,0)]:
                zz=middle+dz;rr=radius+(next_r-radius)*(zz-height)/(next_z-height)
                ribbed.append((rr+relief,zz))
    profile=ribbed+profile[6:]
    for i in range(7):
        xy=(0,0) if i==0 else (ring*cos((i-1)*pi/3),ring*sin((i-1)*pi/3))
        obj=s.lathe(f'bell_{i+1:02d}_cooling_rings',profile,center=xy,segments=96)
        s.finish(obj,'engine',bodies=7)
