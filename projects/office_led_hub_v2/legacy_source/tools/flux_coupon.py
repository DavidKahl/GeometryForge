"""Blender script: derive coupon from a revised scene without changing that scene."""
import argparse
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'models'))
from geometry import evaluated_copy, box, finish, volume, intersection_volume
from geometryforge.blender_scene import boolean
from geometryforge.blender_worker import meshes

p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--out',required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
original=list(bpy.data.collections['Printable'].all_objects)
coupons=[]
for name,slot in [('insert_flux',1),('flux_Y_inlay',2)]:
    source=bpy.data.objects[name]
    copy=evaluated_copy(source,'coupon_flux_'+str(slot))
    tool=box('_coupon_slice',(22,30,5),(0,-49,53.5),'Construction')
    mod=boolean(copy,tool,'INTERSECT','Coupon cut from finished insert')
    bpy.context.view_layer.objects.active=copy;bpy.ops.object.modifier_apply(modifier=mod.name)
    expected=intersection_volume(source,tool)
    if abs(volume(copy)-expected)>.01:
        raise ValueError('Coupon parity failed')
    finish(copy,source.data.materials[0],rotation=(180,0,0),part='coupon_flux',filament=slot,bodies=2)
    if 'gf_expected_bbox_mm' in copy: del copy['gf_expected_bbox_mm']
    copy.hide_set(False);copy.hide_render=False
    coupons.append(copy)
for o in original:
    # Freeze coupon first, then remove assembly only in this disposable process.
    bpy.data.objects.remove(o,do_unlink=True)
payload={'backend':'blender','version':bpy.app.version_string,'units':'mm','objects':meshes()}
(out/'meshes.json').write_text(json.dumps(payload))
(out/'parity.json').write_text(json.dumps({'passed':True,'slice_mm':[22,30,5],'center_mm':[0,-49,53.5]}))
