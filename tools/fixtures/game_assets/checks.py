"""Measured doorway clearance and representative print wall/fit checks."""
import numpy as np
from scipy.spatial import ConvexHull


def ray_hits(objects,origin,direction):
    origin=np.asarray(origin,dtype=float);direction=np.asarray(direction,dtype=float)
    hits=[]
    for obj in objects:
        triangles=np.asarray(obj['vertices'])[np.asarray(obj['faces'])]
        e1=triangles[:,1]-triangles[:,0];e2=triangles[:,2]-triangles[:,0]
        h=np.cross(np.broadcast_to(direction,e2.shape),e2);a=np.einsum('ij,ij->i',e1,h)
        valid=np.abs(a)>1e-9;inverse=np.zeros_like(a);inverse[valid]=1/a[valid]
        s=origin-triangles[:,0];u=inverse*np.einsum('ij,ij->i',s,h)
        q=np.cross(s,e1);v=inverse*(q@direction);distance=inverse*np.einsum('ij,ij->i',e2,q)
        mask=valid&(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(distance>=0)
        hits.extend(distance[mask].tolist())
    return sorted({round(v,5) for v in hits})


def verify(payload):
    if payload['parameters']['kind']=='doorway':
        items=payload['objects']['body']
        path=np.asarray([[1500,y,1000] for y in np.linspace(-1000,1000,21)])
        blocked=False
        for obj in items:
            if obj['role']!='collision':continue
            v=np.asarray(obj['vertices']);matrix=np.asarray(obj['matrix_world'])
            world=(np.column_stack([v,np.ones(len(v))])@matrix.T)[:,:3]
            hull=ConvexHull(world)
            blocked|=bool(np.any(np.all(path@hull.equations[:,:3].T+hull.equations[:,3]<=1e-5,axis=1)))
        return {'passed':not blocked,'traversal_samples':len(path),'collision_clear':not blocked,'grid_mm':100}
    shell=payload['objects']['body'];coupon=payload['objects']['coupon']
    sides=ray_hits(shell,(-100,0,20),(1,0,0));floor=ray_hits(shell,(0,0,-100),(0,0,1))
    fit=ray_hits(coupon,(-100,0,4),(1,0,0))
    walls=[sides[1]-sides[0],sides[-1]-sides[-2]]
    floor_mm=floor[1]-floor[0]
    clearance=(fit[4]-fit[3]-(fit[1]-fit[0]))/2
    return {'passed':bool(np.allclose(walls,[2,2],atol=.01) and abs(floor_mm-2)<.01 and abs(clearance-.2)<.01),
            'walls_mm':walls,'floor_mm':floor_mm,'radial_clearance_mm':clearance,'physically_tested':False}
