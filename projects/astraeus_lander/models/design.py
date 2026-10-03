"""Shared dimensions derived from the concept sheet; working units are millimeters."""
def dimensions(p):
    s=p['height_mm']/72
    return dict(scale=s,R=8.5*s/2,aft=12.5*s,mid=29.5*s,tank=46.5*s,cargo=56.5*s,top=72*s,
                base=4.5*s,band=p['thermal_band_height_mm'],wall=p['wall_mm'],fit=p['clearance_mm'],joint=p['joint_height_mm'])

def seamed_profile(r,z0,z1,pitch=9,depth=.28):
    profile=[(r,z0)]
    z=z0+pitch
    while z<z1-2:
        profile.extend([(r,z-.45),(r-depth,z-.2),(r-depth,z+.2),(r,z+.45)])
        z+=pitch
    profile.append((r,z1))
    return profile

def nose_radius(d,z):
    t=(z-d['cargo'])/(d['top']-d['cargo'])
    return d['R']*(1-t**1.75)+.8*t**1.75 if t>0 else d['R']

def tube_profile(d,z0,z1,thermal=False):
    r,w,c,j=d['R'],d['wall'],d['fit'],d['joint']
    end=z1-d['band'] if thermal else z1
    profile=seamed_profile(r,z0,end)
    if thermal:profile += [(r-w,end),(r-w,z1)]
    spigot=r-w-c
    profile += [(spigot,z1),(spigot,z1+j-.7),(spigot-.5,z1+j),(spigot-2,z1+j),(spigot-2,z1-3)]
    # Female bore at the bottom accepts the previous section's male collar.
    inside=r-2*w if thermal else r-w
    profile += [(inside,z1-6),(inside,z0+j+5),(r-w,z0+j+2),(r-w,z0)]
    return profile
