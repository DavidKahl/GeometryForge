import numpy as np
import trimesh

def verify(payload):
    p=payload['parameters']
    mesh=trimesh.util.concatenate([trimesh.Trimesh(o['vertices'],o['faces'],process=True) for o in payload['objects']['organizer']])
    w,d,h,t,f,n=[p[k] for k in ('width','depth','height','wall','floor','count')]
    expected=w*d*h-(w-(n+1)*t)*(d-2*t)*(h-f)
    assert np.allclose(mesh.extents,[w,d,h],atol=.02)
    assert abs(mesh.volume-expected)<max(.1,expected*.0001), 'Cavity volume does not match compartment dimensions'
    # A horizontal section above the floor must have one outer and n inner loops.
    section=mesh.section(plane_origin=[0,0,f+(h-f)/2],plane_normal=[0,0,1])
    assert section is not None and len(section.discrete)==n+1, 'Compartments are missing or connected'
    floor_section=mesh.section(plane_origin=[0,0,f/2],plane_normal=[0,0,1])
    assert floor_section is not None and len(floor_section.discrete)==1, 'Floor contains holes'
    assert min(t,f)>=1.2
    return {'passed':True,'measured_volume_mm3':float(mesh.volume),'expected_volume_mm3':expected,'cavity_count':len(section.discrete)-1,'wall_mm':t,'floor_mm':f}
