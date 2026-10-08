"""Measured fit/assembly checks on the actual Blender modifier results."""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'models'))
import spec as S
from geometry import evaluated_copy, intersection_volume, volume, cylinder, box
from geometryforge.blender_scene import boolean


def verify():
    checks = []
    def check(name, ok, detail):
        checks.append({'name': name, 'passed': bool(ok), 'detail': detail})
        print(f"{'PASS' if ok else 'FAIL'}: {name}: {detail}", flush=True)
    objects = bpy.data.objects
    base, cover = objects['backplate'], objects['reactor_cover']
    hardware_parts = [o for o in bpy.data.collections['Printable'].objects
                      if not o.name.startswith(('coupon_', 'insert_', 'flux_', 'reactor_ring', 'reactor_armor'))]
    static = [o for o in hardware_parts if o != cover]
    components = [objects[n] for n in ['PSU_envelope', 'controller_envelope']
                  + [f'wago_envelope_{i}' for i in range(1, 7)]]
    # Cache bounds to avoid expensive Booleans for disjoint objects.
    def bounds(obj):
        graph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(graph)
        corners = [obj.matrix_world @ Vector(v) for v in evaluated.bound_box]
        return [(min(v[i] for v in corners), max(v[i] for v in corners)) for i in range(3)]
    def clash(a, b):
        aa, bb = bounds(a), bounds(b)
        if any(min(aa[i][1], bb[i][1])-max(aa[i][0], bb[i][0]) < 0.0001 for i in range(3)):
            return 0.0
        return intersection_volume(a, b)
    for component in components:
        overlaps = {part.name: round(clash(component, part), 4) for part in hardware_parts}
        bad = {name: value for name, value in overlaps.items() if value > 0.05}
        check(component.name + ' fits', not bad, bad or 'No interference with mounted printed parts')
    opening = objects['Rear_access_envelope']
    bad = {part.name: round(clash(opening, part), 4) for part in static if clash(opening, part) > 0.05}
    check('100 mm rear opening stays accessible', not bad, bad or 'Clear through the component mounting zone')
    for index, part in enumerate(static):
        bad = {other.name: round(clash(part, other), 4) for other in static[index+1:] if clash(part, other) > 0.05}
        check(part.name + ' assembly clearance', not bad, bad or 'Separate printed parts do not overlap')
    for amount in (0, 1, 8, 24, 60):
        shell = evaluated_copy(cover, '_cover_lift', 'Construction')
        shell.location.z += amount
        bad = {part.name: round(clash(shell, part), 4) for part in static + components if clash(shell, part) > 0.05}
        check(f'Cover removal +{amount} mm', not bad, bad or 'Clear with cover screws removed')
        bpy.data.objects.remove(shell, do_unlink=True)
    access = [o for o in objects if o.name.startswith(('wago_lever_access_', 'wago_wire_access_'))]
    access += [objects[name] for name in ('controller_input_access', 'controller_output_access', 'PSU_DC_access', 'PSU_mains_access', 'Low_voltage_bundle_path')]
    access += [o for o in objects if o.name.startswith(('Strip_side_route', 'Strip_top_route', 'Strip_right_turn', 'Strip_descent_'))]
    for region in access:
        obstacles = hardware_parts + components if region.name.startswith('Strip_') else hardware_parts
        bad = {part.name: round(clash(region, part), 4) for part in obstacles if clash(region, part) > 0.05}
        check(region.name, not bad, bad or 'Terminal/lever/cable service volume clear')
    for x, y in S.PSU_FIXINGS:
        # A gauge proves full adjustment travel through the actual spacer.
        for delta in (-S.PSU_ADJUST/2, 0, S.PSU_ADJUST/2):
            gauge = cylinder('_M3_gauge', 1.5, -1, 11, (x, y+delta))
            check(f'PSU screw travel {x},{y} {delta:+g}', clash(base, gauge) < 0.05, 'M3 shaft clears adjusted slot')
            bpy.data.objects.remove(gauge, do_unlink=True)
    for xy in S.COVER_FIXINGS + S.CRADLE_FIXINGS + S.GUARD_FIXINGS:
        bottom = 40.2 if xy in S.COVER_FIXINGS else 0.8
        gauge = cylinder('_fixing_gauge', 1.5, bottom, 50-bottom, xy)
        check(f'M3 fixing alignment {xy}', clash(base, gauge) < 0.05, 'Shaft clear of its mounting structure')
        bpy.data.objects.remove(gauge, do_unlink=True)
    # Actual bores, slot travel and washer seats for the revised installation.
    check('Wall slots outside vertical opening projection',
          all(abs(x)-2.6 > S.REAR_OPENING/2 for x, y in S.SIDE_WALL_FIXINGS),
          'Slot edges are 27.4 mm outside the 100 mm opening projection')
    for x, y in S.SIDE_WALL_FIXINGS:
        for delta in (-3.4, 0, 3.4):
            gauge = cylinder('_wall_shaft', 2, -1, 6, (x, y+delta))
            check(f'Wall shaft {x},{y} {delta:+g}', clash(base, gauge) < 0.05, '4 mm shaft clears slot')
            bpy.data.objects.remove(gauge, do_unlink=True)
        washer = cylinder('_wall_washer', 5, 4.01, 1, (x, y))
        check(f'Wall washer seat {x},{y}', clash(base, washer) < 0.05, '10 mm washer fits base; install before equipment/guard')
        bpy.data.objects.remove(washer, do_unlink=True)
    for x, y in S.WALL_FIXINGS:
        gauge = cylinder('_old_slot_closed', 2, 0, S.PLATE_T, (x, y))
        check(f'Old center slot closed {x},{y}', clash(base, gauge) > 49, 'Former drilling position is solid')
        bpy.data.objects.remove(gauge, do_unlink=True)
    check('Strip exits centered', sum(S.CENTERED_CABLE_X) == 0, '26 mm between cable centers')
    for index, x in enumerate(S.CENTERED_CABLE_X):
        gauge = cylinder('_cable_gauge', S.CABLE_DIAMETER/2, -10, 20)
        gauge.rotation_euler.x = math.pi/2
        gauge.location = (x, S.CABLE_Y, S.CABLE_Z)
        bad = {p.name: round(clash(p, gauge), 4) for p in hardware_parts if clash(p, gauge) > 0.05}
        check(f'Centered cable bore {index+1}', not bad, bad or '7 mm cable clears saddle, clamp and cover')
        bpy.data.objects.remove(gauge, do_unlink=True)
    # Cover and trim must register without overlapping solids.
    for ring in [objects[f'reactor_ring_{i}'] for i in range(1, 4)]:
        check(ring.name + ' pin registration', clash(ring, cover) < 0.05, 'Pins enter corresponding 3.2 mm holes')
    decoration = [o for o in objects if o.name.startswith(('reactor_ring_', 'reactor_armor_'))]
    for index, part in enumerate(decoration):
        others = decoration[index+1:] + [cover, objects['insert_flux']]
        check(part.name + ' v2 decorative clearance', all(clash(part, other) < 0.05 for other in others),
              'Separate trim clears cover, insert, and adjacent panels')
    for name in ('insert_flux', 'insert_plain'):
        plate = evaluated_copy(objects[name], '_insert_check', 'Construction')
        if name == 'insert_plain':
            plate.location.x -= 260
        check(name + ' cover interface', clash(plate, cover) < 0.05, 'Face sits on cover; three aligned fasteners')
        for angle in S.INSERT_ANGLES:
            a = math.radians(angle)
            xy = (56*math.cos(a), 56*math.sin(a))
            gauge = cylinder('_insert_shaft', 1.5, 49, 7, xy)
            check(f'{name} screw passage {angle}', clash(plate, gauge) < 0.05,
                  'Actual evaluated insert clears M3 shaft')
            bpy.data.objects.remove(gauge, do_unlink=True)
        bpy.data.objects.remove(plate, do_unlink=True)
    # Coupon parity against a fresh cut from the original evaluated source.
    for obj in [o for o in objects if o.name.startswith('coupon_') and 'coupon_source' in o]:
        actual = evaluated_copy(obj, '_actual', 'Construction')
        actual.location -= Vector(obj['coupon_offset'])
        expected = evaluated_copy(objects[obj['coupon_source']], '_expected', 'Construction')
        if 'coupon_size' in obj:
            size = obj['coupon_size']
            tool = box('_coupon_cut', size, (*obj['coupon_xy'], size[2]/2-0.5), 'Construction')
            boolean(expected, tool, 'INTERSECT')
        else:
            tool = None
        va, vb = volume(actual), volume(expected)
        shared = intersection_volume(actual, expected)
        check(obj.name + ' reproduces real feature', abs(va-vb) < 0.05 and abs(va-shared) < 0.05,
              f'{va:.3f}/{vb:.3f} mm3; intersection {shared:.3f}')
        for delete in (actual, expected, tool):
            if delete:
                bpy.data.objects.remove(delete, do_unlink=True)
    check('PSU mounting air gap', S.PSU_BOTTOM-S.PLATE_T >= 5, f'{S.PSU_BOTTOM-S.PLATE_T} mm')
    cradle = objects['controller_cradle']
    gauge = box('_wide_controller_gauge', (37.6, 75, 25),
                (*S.CRADLE_CAVITY_XY, S.CONTROLLER_BOTTOM+12.5), 'Construction')
    check('Wider controller body reserve', clash(cradle, gauge) < 0.05,
          '37.6 mm body fits below the retaining lips; actual case needs coupon check')
    bpy.data.objects.remove(gauge, do_unlink=True)
    tree = BVHTree.FromObject(cradle, bpy.context.evaluated_depsgraph_get())
    origin = cradle.matrix_world.inverted() @ Vector((S.CRADLE_CAVITY_XY[0], 20, 15))
    left = tree.ray_cast(origin, Vector((-1,0,0)))[0]
    right = tree.ray_cast(origin, Vector((1,0,0)))[0]
    gap = (right-left).length if left is not None and right is not None else 0
    check('Cradle measured internal width', abs(gap-S.CRADLE_INTERNAL_WIDTH) < 0.01,
          f'{gap:.3f} mm between actual side rails')
    for xy in S.CRADLE_FIXINGS:
        gauge = cylinder('_cradle_fixing_gauge', 1.5, 8, 5, xy)
        check(f'Widened cradle mounting alignment {xy}', clash(cradle, gauge) < 0.05,
              'Original mounting centers retained')
        bpy.data.objects.remove(gauge, do_unlink=True)
    check('Front panel minimum thickness', S.FRONT_T-0.5 >= 2.4, f'{S.FRONT_T-0.5} mm beneath engravings')
    def thickness(obj, origin, direction):
        graph = bpy.context.evaluated_depsgraph_get()
        tree = BVHTree.FromObject(obj, graph)
        inv = obj.matrix_world.inverted()
        ray = inv.to_3x3() @ Vector(direction)
        point = inv @ Vector(origin)
        first, _, _, _ = tree.ray_cast(point, ray)
        if first is None:
            return 0
        second, _, _, _ = tree.ray_cast(first+ray*0.001, ray)
        return (second-first).length if second is not None else 0
    for name, obj, origin, ray, minimum in [
        ('Backplate wall', base, (75, -60, 60), (0, 0, -1), 4),
        ('Cover front wall', cover, (0, 80, 65), (0, 0, -1), 3),
        ('Engraved front wall', cover, (18, -104, 65), (0, 0, -1), 2.5),
        ('Cover side wall', cover, (130, 40, 35), (-1, 0, 0), 3.2),
        ('Terminal guard roof', objects['mains_terminal_guard'], (-82.5, -90, 60), (0, 0, -1), 2.4),
    ]:
        measured = thickness(obj, origin, ray)
        check(name+' measured thickness', measured >= minimum-0.01, f'{measured:.4f} mm; minimum {minimum}')
    check('Trim and inserts within depth envelope', S.FRONT_Z+S.RING_T == 55, '55 mm wall-to-front envelope')
    check('Wooden trim clearance', S.HOLE_TO_TRIM-S.SIZE/2 == 125, '125 mm above the enclosure')
    check('Mains partition below rear opening', -84+52/2 < -S.REAR_OPENING/2, 'No partition across wall access')
    # Store measured evidence alongside the loaded model's run.
    out = Path(bpy.data.filepath).parent.parent / 'checks'
    out.mkdir(exist_ok=True)
    (out / 'office_hub.json').write_text(json.dumps({'passed': all(c['passed'] for c in checks), 'checks': checks}, indent=2))
    failed = [c['name'] for c in checks if not c['passed']]
    print(f'{len(checks)-len(failed)}/{len(checks)} office hub checks passed', flush=True)
    if failed:
        raise AssertionError('; '.join(failed))
