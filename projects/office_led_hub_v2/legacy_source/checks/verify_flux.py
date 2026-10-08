"""Focused geometry proof against the saved enclosure; no rebuild required."""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'models'))
import spec as S
from flux_insert import blank, seat
from geometry import volume, intersection_volume, cylinder


def verify():
    checks=[]
    def check(name,ok,detail):
        checks.append(dict(name=name,passed=bool(ok),detail=detail))
        print(('PASS' if ok else 'FAIL')+': '+name+': '+str(detail),flush=True)
    base=bpy.data.objects['insert_flux']; motif=bpy.data.objects['flux_Y_inlay']
    reference=blank('_expected_disc')
    vb,vm,vr=map(volume,(base,motif,reference))
    overlap=intersection_volume(base,motif)
    inside=intersection_volume(base,reference)+intersection_volume(motif,reference)
    check('Exact material partition',overlap<.01 and abs(vb+vm-vr)<.02 and abs(inside-vr)<.02,
          dict(overlap_mm3=overlap,missing_mm3=vr-inside,volume_error_mm3=vb+vm-vr))
    bpy.data.objects.remove(reference,do_unlink=True)
    for obj in (base,motif):
        points=[obj.matrix_world@Vector(v) for v in obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).bound_box]
        z=[p.z for p in points]
        check(obj.name+' flush thickness',abs(min(z)-52)<.001 and abs(max(z)-55)<.001,(min(z),max(z)))
        check(obj.name+' front on bed',list(obj['gf_print_rotation_deg'])==[180,0,0],'Both visible faces export to Z=0')
        for other in [o for o in bpy.data.collections['Printable'].objects if o.name=='reactor_cover' or o.name.startswith(('reactor_ring_','reactor_armor_'))]:
            check(obj.name+' clears '+other.name,intersection_volume(obj,other)<.05,'Saved mating geometry')
    for angle in S.INSERT_ANGLES:
        a=math.radians(angle); xy=(56*math.cos(a),56*math.sin(a))
        gauge=seat(xy,'_head_gauge',.05)
        check(f'Flush screw head {angle}',intersection_volume(base,gauge)<.01,'6.3 mm head / 3.3 mm neck / 1.6 mm depth; face Z=55')
        bpy.data.objects.remove(gauge,do_unlink=True)
        gauge=cylinder('_shaft',1.5,49,7,xy)
        check(f'Screw registration {angle}',all(intersection_volume(o,gauge)<.01 for o in (base,motif,bpy.data.objects['reactor_cover'])),'3 mm shaft through insert and original cover')
        bpy.data.objects.remove(gauge,do_unlink=True)
    tree=BVHTree.FromObject(motif,bpy.context.evaluated_depsgraph_get())
    for angle in (30,150,270):
        a=math.radians(angle); origin=Vector((43*math.cos(a),43*math.sin(a),60))
        top=tree.ray_cast(origin,Vector((0,0,-1)))[0]
        bottom=tree.ray_cast(Vector((origin.x,origin.y,48)),Vector((0,0,1)))[0]
        check(f'Through Y endpoint {angle}',top is not None and bottom is not None and abs(top.z-bottom.z-3)<.001,'Upright installed Y, 3 mm translucent path')
    out=Path(bpy.data.filepath).parent.parent
    (out/'flux_checks.json').write_text(json.dumps({'passed':all(c['passed'] for c in checks),'checks':checks},indent=2))
    if not all(c['passed'] for c in checks):
        raise ValueError('Flux interface checks failed')
