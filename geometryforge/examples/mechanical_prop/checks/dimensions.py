def verify(payload):
    import numpy as np
    p=payload['parameters']
    scale=(payload.get('derivation') or {}).get('scale',1)
    objects=payload['objects']['body']
    points=np.concatenate([np.asarray(o['vertices']) for o in objects])
    actual=np.ptp(points,axis=0)
    source=(payload.get('derivation') or {}).get('outputs',{}).get(payload.get('backend'),{}).get('body',{}).get('bbox_mm')
    expected=np.asarray(source or [p['width'],p['depth'],p['height']])*scale
    return {'passed':bool(np.allclose(actual,expected,atol=.03)), 'bbox_mm':actual.tolist(), 'expected_mm':expected.tolist()}
