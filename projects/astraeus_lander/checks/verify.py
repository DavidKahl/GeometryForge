"""Inspect exported geometry: section radii, mating clearance and physical sockets."""
import math,itertools
import numpy as np
import trimesh

def mesh(objects):
    return trimesh.util.concatenate([trimesh.Trimesh(o['vertices'],o['faces'],process=True) for o in objects])

def radii(m,z,center=(0,0)):
    section=m.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    assert section is not None, 'Required interface section missing'
    result=[]
    for loop in section.discrete:
        xy=loop[:,:2]-center
        # Only concentric loops, ignoring hatches and disconnected engine bells.
        if np.linalg.norm((xy.min(0)+xy.max(0))/2)<.08:
            result.append(float(np.linalg.norm(xy,axis=1).max()))
    return sorted(result)

def line_hits(m,origin,direction):
    """Vectorized line/triangle intersections; no external ray index dependency."""
    tri=m.triangles;e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
    direction=np.array(direction,float);origin=np.array(origin,float)
    h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
    mask=np.abs(det)>1e-9;tri=tri[mask];e1=e1[mask];e2=e2[mask];h=h[mask];det=det[mask]
    inv=1/det;s=origin-tri[:,0];u=inv*np.einsum('ij,ij->i',s,h)
    q=np.cross(s,e1);v=inv*q.dot(direction);t=inv*np.einsum('ij,ij->i',e2,q)
    good=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
    return np.unique(np.round(t[good],5))

def assert_clearance(value,expected):
    assert abs(value-expected)<.045, f'Clearance {value:.4f} differs from requested {expected:.4f} mm'

def verify(payload):
    p=payload['parameters'];kind=payload['check'];m={k:mesh(v) for k,v in payload['objects'].items()}
    scale=p['height_mm']/72;r=8.5*scale/2;c=p['clearance_mm'];w=p['wall_mm'];j=p['joint_height_mm'];base=4.5*scale
    assert .15<=c<=.6 and w>=2, 'Print settings outside supported FDM range'
    measurements={}
    if kind=='body_joints':
        for lower,upper,z in [('aft_hull','tank_lower',12.5*scale),('tank_lower','tank_upper',29.5*scale),('tank_upper','cargo',46.5*scale),('cargo','nose',56.5*scale)]:
            a=radii(m[lower],z+j/2);b=radii(m[upper],z+j/2)
            assert len(a)==2 and len(b)>=2, f'Missing hollow collar at {lower}/{upper}'
            gap=min(b)-max(a);assert_clearance(gap,c);measurements[lower+'/'+upper]=gap
            assert a[-1]-a[0]>=1.8, 'Male collar too thin'
    elif kind=='nose_joint':
        z=p['height_mm']-p['nose_tip_height_mm']+2.5
        a=radii(m['nose'],z);b=radii(m['nose_tip'],z)
        assert len(a)==2 and len(b)==2
        gap=b[0]-a[-1];assert_clearance(gap,c);measurements['tip_radial_gap']=gap
    elif kind=='thermal_fit':
        z=46.5*scale-p['thermal_band_height_mm']/2
        a=radii(m['tank_upper'],z);b=radii(m['thermal_band'],z)
        gap=b[0]-a[-1];assert_clearance(gap,c)
        assert a[-1]-a[0]>=w-.04 and b[-1]-b[0]>=w-c-.04
        measurements['sleeve_gap']=gap
    elif kind=='engine_fit':
        assert len(m['engines'].split(only_watertight=False))==7
        for i in range(7):
            xy=(0,0) if i==0 else (2.4*scale*math.cos((i-1)*math.pi/3),2.4*scale*math.sin((i-1)*math.pi/3))
            a=radii(m['engines'],base+2,xy);b=radii(m['engine_mount'],base+2,xy)
            assert len(a)==2 and len(b)>=1
            gap=min(b)-max(a);assert_clearance(gap,c);measurements[f'engine_{i+1}_gap']=gap
            throat=radii(m['engines'],base-7,xy)
            assert len(throat)==2 and throat[-1]-throat[0]>=1.19, 'Engine throat wall below 1.2 mm'
    elif kind in ('fin_roots','canard_roots','landing_legs'):
        for i in range(1,5):
            if kind=='fin_roots':
                angle=(i-1)*90;part=f'aft_fin_{i}';rad=r-.5
                interfaces=[('aft_hull',base+20),('tank_lower',12.5*scale+18)]
            elif kind=='canard_roots':
                angle=(i-1)*90;part=f'canard_{i}';rad=r-2.6;interfaces=[('nose',56.5*scale+18)]
            else:
                angle=45+(i-1)*90;part=f'leg_{i}';rad=r-1;interfaces=[('aft_hull',base+25)]
            a=math.radians(angle);direction=(-math.sin(a),math.cos(a),0)
            for hull,z in interfaces:
                origin=(rad*math.cos(a),rad*math.sin(a),z+.037)
                tab=line_hits(m[part],origin,direction);socket=line_hits(m[hull],origin,direction)
                assert len(tab)>=2 and len(socket)>=2, f'Missing {part} attachment'
                inside=sorted(socket,key=abs)[:2]
                gap=(max(inside)-min(inside)-(max(tab)-min(tab)))/2
                assert_clearance(gap,c);measurements[part+'/'+hull]=gap
    elif kind=='fit_coupon':
        a=radii(m['coupon'],5,(100,0));b=radii(m['coupon'],5,(100,65))
        assert len(a)==2 and len(b)==2
        gap=b[0]-a[-1];assert_clearance(gap,c);measurements['coupon_gap']=gap
    else: raise ValueError(kind)
    intersections={}
    for first,second in itertools.combinations(m,2):
        overlap=np.minimum(m[first].bounds[1],m[second].bounds[1])-np.maximum(m[first].bounds[0],m[second].bounds[0])
        if np.any(overlap<1e-5):continue
        common=trimesh.boolean.intersection([m[first],m[second]],engine='manifold')
        volume=abs(float(common.volume))
        intersections[first+'/'+second]=volume
        assert volume<.005,f'Assembly interference: {first}/{second} overlaps by {volume:.4f} mm3'
    return {'passed':True,'measured_clearances_mm':measurements,'intersection_volume_mm3':intersections,
            'method':'exported triangle sections, interface ray intersections, and Manifold solid intersections'}
