import json,sys
from pathlib import Path
import trimesh,numpy as np
data=json.loads(Path(sys.argv[1]).read_text())
for obj in data['objects']:
    m=trimesh.Trimesh(obj['vertices'],obj['faces'],process=True)
    bodies=m.split(only_watertight=False)
    bad=not m.is_watertight or not m.is_winding_consistent or m.volume<=0 or len(bodies)>1
    print(obj['part'], 'BAD' if bad else 'ok',len(m.faces),'faces',len(bodies),'bodies',m.is_watertight,'watertight',round(m.volume,2))
    if bad:
        print('body sizes',[(len(b.faces),round(b.volume,4),b.bounds.round(3).tolist()) for b in bodies[:12]])
        edge_counts=np.bincount(m.edges_unique_inverse)
        broken=m.vertices[m.edges_unique[edge_counts!=2]].reshape(-1,3)
        print('broken edges:',broken[:20].round(4).tolist())
