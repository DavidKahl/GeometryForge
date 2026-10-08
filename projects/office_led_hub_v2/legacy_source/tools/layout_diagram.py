"""Dimensioned mounting/service diagram from the same spec as the Blender model."""
import argparse
from pathlib import Path
import sys
import json
import hashlib
import numpy as np
from matplotlib.collections import PolyCollection

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'models'))
import spec as S


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    run = args.run.resolve()
    manifest = json.loads((run/'build.json').read_text())
    if manifest['status'] != 'passed' or manifest['project'] != 'office_led_hub_v2':
        raise SystemExit('A successful v2 build is required.')
    project = Path(__file__).resolve().parents[1]
    for rel, digest in manifest['inputs'].items():
        if Path(rel).parts[0] in ('models', 'checks'):
            if hashlib.sha256((project/rel).read_bytes()).hexdigest() != digest:
                raise SystemExit(f'Rebuild required: {rel}')
    payload = json.loads((run/'meshes.json').read_text())
    base = next(o for o in payload['objects'] if o['name'] == 'backplate')
    triangles = np.array(base['vertices'])[np.array(base['faces'])]
    normals = np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0])
    triangles = triangles[normals[:,2] > 1e-7]
    triangles = triangles[np.argsort(triangles[:,:,2].mean(axis=1))]
    colors = ['#d9dfe4' if t[:,2].mean() < 4.1 else '#8b9dac' for t in triangles]
    fig, ax = plt.subplots(figsize=(12, 13))
    fig.patch.set_facecolor('#f4f5f6')
    ax.set_facecolor('#f4f5f6')
    def rect(x, y, w, h, color, label='', radius=2):
        patch = FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle=f'round,pad=0,rounding_size={radius}',
                              facecolor=color, edgecolor='#344454', linewidth=1.2)
        ax.add_patch(patch)
        if label:
            ax.text(x, y, label, ha='center', va='center', fontsize=8, color='#1d2a35')
    ax.add_collection(PolyCollection(triangles[:,:,:2], facecolors=colors, edgecolors='none', antialiased=False))
    rect(0, 0, 100, 100, '#ffffff', 'REAR ACCESS\n100 × 100 mm\nR10 corners', 10)
    rect(-82.5, 0, 50, 178, '#94a3b1', 'PSU\n178 × 50\n25 high')
    ax.text(-82.5, 82, '24 V', ha='center', fontsize=9, weight='bold')
    ax.text(-82.5, -82, 'MAINS', ha='center', fontsize=9, weight='bold')
    rect(*S.CRADLE_CAVITY_XY, 35, 75, '#fafafa', 'MiBoxer\n37.8 mm\ncradle gap')
    for index, (x, y) in enumerate((x,y) for y in S.WAGO_Y for x in S.WAGO_X):
        rect(x, y, 18.8, 18.6, '#efb17c', S.WAGO_CHANNELS[index])
    for x in S.CENTERED_CABLE_X:
        rect(x, 110, 24, 10, '#56b7b0')
        ax.annotate('', (x, 133), (x, 114), arrowprops={'arrowstyle':'->','color':'#168a83','lw':2})
    ax.add_patch(Rectangle((-25,116),50,24,fill=False,edgecolor='#168a83',linestyle='--'))
    ax.text(0, 151, 'CENTERED EXTERNAL CABLE TRUNKING', ha='center', fontsize=10, color='#168a83')
    ax.text(0, 143, 'Cable centers X = -13 / +13 mm', ha='center', fontsize=9, color='#168a83')
    for xy in S.SIDE_WALL_FIXINGS:
        rect(*xy, 5.2, 12, '#ffffff', radius=2.6)
        ax.add_patch(Circle(xy, 7, fill=False, edgecolor='#1766c1', linewidth=1.8))
    for xy in S.COVER_FIXINGS:
        ax.add_patch(Circle(xy, 6, facecolor='#384550'))
        ax.add_patch(Circle(xy, 1.7, facecolor='white'))
    for xy in S.PSU_FIXINGS:
        rect(*xy, 3.4, 11.4, '#ffffff', radius=1.7)
    for x,y in S.ALTERNATE_FIXINGS:
        ax.plot(x,y,marker='+',color='#305575',markersize=7)
    ax.add_patch(Rectangle((-41.2,-110),2.4,52,facecolor='#ca685c'))
    ax.text(-32,-82,'partition',fontsize=8,rotation=90,va='center',color='#9e493f')
    def route(points, color, width=2):
        x,y=zip(*points)
        ax.plot(x,y,color=color,lw=width,solid_capstyle='round',solid_joinstyle='round')
        ax.annotate('',points[-1],points[-2],arrowprops={'arrowstyle':'->','color':color,'lw':width})
    # Schematics over the real base; terminal endpoints follow actual equipment.
    route([(-20,-35),(-47,-63),(-47,-96),(-70,-96)], '#c25b35', 2.5)
    route([(-82.5,89),(-58,101),(82,101),(82,82)], '#7755aa')
    route([(82,4),(82,-7),(107,-7)], '#168a83')
    for x,y in ((x,y) for y in S.WAGO_Y for x in S.WAGO_X):
        route([(x,y+10),(x+5,y+20),(107,y+20)], '#168a83', 1.2)
    for x,color,delta in zip(S.CENTERED_CABLE_X, ('#168a83','#2878ac'),(-1.2,1.2)):
        route([(107+delta,-63),(107+delta,85),(93+delta,85),
               (93+delta,96+delta),(x,96+delta),(x,110),(x,133)],color)
    ax.text(0,70,'Strip bundles cross the top\nthen descend into the clamps',ha='center',fontsize=9,color='#168a83')
    ax.text(0,-67,'Wall slots: X = ±80 / Y = ±103 mm\n160 × 206 mm mounting centers',ha='center',fontsize=9,color='#1766c1')
    ax.text(5,-82,'Wall slots: 5.2 × 12 mm\nCoordinates from the opening center',ha='center',fontsize=8,color='#1766c1')
    ax.annotate('',(-115,-130),(115,-130),arrowprops={'arrowstyle':'<->','lw':1.2})
    ax.text(0,-139,'230 mm',ha='center',fontsize=11)
    ax.annotate('',(-130,-115),(-130,115),arrowprops={'arrowstyle':'<->','lw':1.2})
    ax.text(-139,0,'230 mm',rotation=90,ha='center',va='center',fontsize=11)
    ax.set(xlim=(-150,150),ylim=(-150,162),aspect='equal')
    ax.axis('off')
    fig.suptitle('OFFICE LED HUB V2 / MOUNTING & CABLE MANAGEMENT',fontsize=16,weight='bold',y=0.97)
    fig.text(0.5,0.065,'Blue circles: wall screws · Teal/blue: strip bundles · Purple: 24 V supply · Orange: mains\n'
             'Fit wall screws/10 mm washers before equipment and guard. Secure cables at tie anchors; leave service slack.\n'
             'Actual evaluated backplate; equipment envelopes and cable paths are schematic. Trunking is illustrative.\n'
             'Confirm concealed wiring before drilling. Not a scale drilling template; dimensions in mm.',
             ha='center',fontsize=9,color='#344454')
    fig.text(.5,.025,f'Finished model: {run.name}',ha='center',fontsize=8,color='#536170')
    fig.subplots_adjust(top=.92,bottom=.14)
    fig.savefig(out/'05_mounting_layout.png',dpi=170)
    fig.savefig(out/'05_mounting_layout.svg')
    print(out/'05_mounting_layout.png')


if __name__ == '__main__':
    main()
