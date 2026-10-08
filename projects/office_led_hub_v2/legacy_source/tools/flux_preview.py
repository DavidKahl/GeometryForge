"""Installed front view from actual revision meshes, independent of slicer rotation."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args()
fig,ax=plt.subplots(figsize=(8,9));fig.patch.set_facecolor('#e3e6e9')
for obj in json.loads((args.run/'meshes.json').read_text())['objects']:
    t=np.array(obj['vertices'])[np.array(obj['faces'])]
    n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);t=t[n[:,2]>1e-8]
    ax.add_collection(PolyCollection(t[:,:,:2],facecolors='#25303b' if obj['filament']==1 else '#8ed9de',edgecolors='none',antialiased=False))
ax.set(xlim=(-72,72),ylim=(-72,72),aspect='equal');ax.axis('off')
ax.set_title('FLUX INSERT / INSTALLED FRONT',fontsize=17,pad=20)
fig.text(.5,.045,'130 mm diameter · 3 mm thick · flush through-inlay\nPrint front-face down; assign translucent PETG to material 2.\nCountersink: Ø6.4 / Ø3.4 × 1.6 mm. Test with your screw.',ha='center',fontsize=10)
fig.savefig(args.run/'previews/installed_front.png',dpi=170)
import trimesh
fig,ax=plt.subplots(figsize=(12,3))
for obj in json.loads((args.run/'meshes.json').read_text())['objects']:
    mesh=trimesh.Trimesh(obj['vertices'],obj['faces'])
    section=mesh.section(plane_origin=(0,0,0),plane_normal=(1,0,0))
    if section:
        for line in section.discrete:
            ax.fill(line[:,1],line[:,2],color='#25303b' if obj['filament']==1 else '#69bfc6')
ax.set(xlim=(-66,66),ylim=(51.5,55.5),xlabel='Installed Y (mm)',ylabel='Installed Z (mm)',
       title='Actual mesh section X = 0: through-inlay and bottom screw countersink')
ax.grid(alpha=.2);fig.tight_layout();fig.savefig(args.run/'previews/through_section.png',dpi=170)
