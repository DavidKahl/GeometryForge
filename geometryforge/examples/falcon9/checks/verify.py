import numpy as np
import trimesh

def mesh(objects):
    return trimesh.util.concatenate([trimesh.Trimesh(o['vertices'],o['faces'],process=True) for o in objects])

def loops(m,z):
    section=m.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    assert section is not None, 'Required interface cross section is missing'
    return section.discrete

def rectangle_size(loop):
    return np.ptp(loop[:,:2],axis=0)

def verify(payload):
    p=payload['parameters'];kind=payload['check'];m={k:mesh(v) for k,v in payload['objects'].items()}
    w,d,j,c=[p[k] for k in ('joint_width','joint_depth','joint_height','clearance')]
    assert .1<=c<=.8 and min(w,d)>2 and j>=3, 'Unsupported joint dimensions'
    if kind in ('lower_joint','upper_joint'):
        lower,upper=('stage1','stage2') if kind=='lower_joint' else ('stage2','fairing')
        z=p['stage1_height']+(p['stage2_height'] if kind=='upper_joint' else 0)
        peg=loops(m[lower],z+j/2)
        socket=loops(m[upper],z+j/2)
        assert len(peg)==1 and len(socket)==2, 'Missing peg or socket'
        peg_size=rectangle_size(peg[0]);socket_size=min((rectangle_size(s) for s in socket),key=lambda a:a.prod())
        inner = min(socket,key=lambda s:rectangle_size(s).prod())
        peg_center = (peg[0][:,:2].min(0)+peg[0][:,:2].max(0))/2
        socket_center = (inner[:,:2].min(0)+inner[:,:2].max(0))/2
        assert np.allclose(peg_center,socket_center,atol=.025), 'Joint axes do not align'
        assert np.allclose(peg_size,[w,d],atol=.025)
        assert np.allclose(socket_size,[w+2*c,d+2*c],atol=.025)
        measured=(socket_size-peg_size)/2
        assert np.all(measured>=.09)
        assert len(loops(m[upper],z+j+c+.2))==1, 'Socket is not capped above engagement depth'
        return {'passed':True,'clearance_per_side_mm':measured.tolist(),'engagement_mm':j}
    if kind=='stand_fit':
        rings=loops(m['stand'],10)
        assert len(rings)==2
        bore=min((rectangle_size(s) for s in rings),key=lambda a:a.prod())
        body=rectangle_size(loops(m['stage1'],10)[0])
        clearance=(bore-body)/2
        assert np.allclose(clearance,[c,c],atol=.025)
        return {'passed':True,'cradle_radial_clearance_mm':clearance.tolist()}
    if kind=='coupon_fit':
        sections=loops(m['coupon'],4)
        assert len(sections)==3
        sizes=sorted((rectangle_size(s) for s in sections),key=lambda a:a.prod())
        assert np.allclose(sizes[0],[w,d],atol=.025)
        assert np.allclose(sizes[1],[w+2*c,d+2*c],atol=.025)
        return {'passed':True,'coupon_clearance_mm':((sizes[1]-sizes[0])/2).tolist()}
    raise ValueError('Unknown check')
