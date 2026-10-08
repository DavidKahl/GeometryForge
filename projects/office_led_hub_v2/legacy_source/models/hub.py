"""Reactor office distribution hub. All printable objects use assembly coordinates."""
import math
import bpy
from mathutils import Vector
from geometryforge.blender_scene import initialize, boolean
import spec as S
from geometry import (box, prism, rounded, cylinder, sector, fuse, cut, hole, nut, radial_box,
                      countersink, evaluated_copy, collection, material, finish)


def accessory_pad(base, xy):
    fuse(base, cylinder('Accessory stand', 5.5, 3.8, 4.2, xy))
    hole(base, xy, 0.5, 8)
    nut(base, xy, 4.0, side=True)


def tie_anchor(base, xy, angle=0):
    x, y = xy
    block = box('Cable tie bridge', (9, 5, 5), (x, y, 6.3), 'Construction')
    block.rotation_euler.z = math.radians(angle)
    tunnel = box('Tie passage', (3.4, 8, 1.8), (x, y, 6.0), 'Construction')
    tunnel.rotation_euler.z = math.radians(angle)
    cut(block, tunnel)
    fuse(base, block, 'Cable-tie anchor')


def backplate(black):
    base = rounded('backplate', S.SIZE, S.SIZE, S.CORNER, 0, S.PLATE_T)
    cut(base, rounded('Rear wall opening', S.REAR_OPENING, S.REAR_OPENING, S.REAR_RADIUS, -1, 60, group='Construction'))
    rim = rounded('Registration rim', S.LIP_OUTER, S.LIP_OUTER, 8.4, 3.8, 3.2, group='Construction')
    cut(rim, rounded('Rim interior', S.LIP_OUTER-6, S.LIP_OUTER-6, 5.4, 3.6, 4, group='Construction'))
    fuse(base, rim)
    for xy in S.COVER_FIXINGS:
        fuse(base, cylinder('Cover column', 6, 3.8, 45.2, xy))
        hole(base, xy, 38, 12)
        nut(base, xy, 42.0, side=True)
    for xy in S.SIDE_WALL_FIXINGS:
        cut(base, rounded('Wall fixing slot', 5.2, 12, 2.6, -1, 6, xy, 'Construction'))
    for xy in S.ALTERNATE_FIXINGS:
        cut(base, cylinder('Optional fixing pilot mark', 1, 3.4, 0.7, xy), 'Blind alternative drilling mark')
    for x, y in S.PSU_FIXINGS:
        fuse(base, rounded('PSU spacer', 12, 22, 2, 3.8, 5.2, (x, y), 'Construction'))
        cut(base, rounded('PSU adjustment', S.M3_CLEAR, S.PSU_ADJUST+S.M3_CLEAR, 1.7, -1, 11, (x, y), 'Construction'))
        cut(base, rounded('Sliding captive nut channel', S.NUT_AF, S.PSU_ADJUST+S.NUT_AF, 0.5, -0.1, 2.7, (x, y), 'Construction'))
    for xy in S.CRADLE_FIXINGS + S.GUARD_FIXINGS:
        accessory_pad(base, xy)
    for x in S.WAGO_X:
        for y in S.WAGO_Y:
            hole(base, (x, y-14), -1, 6)
            nut(base, (x, y-14), -0.1)
    # A low partition defines the mains routing corridor below the rear opening.
    fuse(base, box('Mains partition', (2.4, 52, 24), (-40, -84, 15.8), 'Construction'))
    for xy in [(-47, -63), (-24, 82), (20, 82), (107, 52), (107, 5), (107, -47), (35, -105)]:
        tie_anchor(base, xy, 90 if xy[0] > 100 else 0)
    for x in S.CENTERED_CABLE_X:
        saddle = box('Fixed cable saddle', (24, 10, 12.2), (x, 110, 9.9), 'Construction')
        bore = cylinder('Cable bore', (S.CABLE_DIAMETER+S.CABLE_CLEARANCE)/2, -6, 12, group='Construction')
        bore.rotation_euler.x = math.pi/2
        bore.location = (x, 110, S.CABLE_Z)
        cut(saddle, bore)
        fuse(base, saddle)
        for dx in (-9, 9):
            hole(base, (x+dx, 110), 5, 13)
            nut(base, (x+dx, 110), 9.0)
            cut(base, box('Cable nut front-loading mouth', (5.8, 8, 2.6), (x+dx, 106, 10.3), 'Construction'))
    base['gf_expected_bbox_mm'] = (230, 230, 49)
    finish(base, black)
    return base


def controller_cradle(black):
    x, y = S.CRADLE_CAVITY_XY
    cradle = rounded('controller_cradle', S.CRADLE_FLOOR_WIDTH, 81, 3, S.CRADLE_BOTTOM, S.CRADLE_FLOOR, (x, y))
    for xy in S.CRADLE_FIXINGS:
        fuse(cradle, cylinder('Cradle screw ear', 5.5, S.CRADLE_BOTTOM, S.CRADLE_FLOOR, xy))
        hole(cradle, xy, 8, 4)
    for sign in (-1, 1):
        wallx = x + sign*(S.CRADLE_INTERNAL_WIDTH/2+1.4)
        fuse(cradle, box('Cradle side rail', (2.8, 67, 8), (wallx, y, 14.6), 'Construction'))
        # Two compliant retaining uprights; ends stay open for terminals.
        fuse(cradle, box('Retaining upright', (1.8, 10, 28.2), (wallx+sign*0.5, y, 22.7), 'Construction'))
        fuse(cradle, box('Retaining lip', (3.0, 10, 1.6), (wallx-sign*0.8, y, 37.3), 'Construction'))
    finish(cradle, black)
    return cradle


def wago_holder(x, y, index, black):
    holder = rounded(f'wago_holder_{index+1}', 23, 22.2, 2, 4.3, 2, (x, y))
    for sign in (-1, 1):
        fuse(holder, box('Wago side cheek', (2.1, 17, 5.2), (x+sign*10.85, y-0.5, 8.7), 'Construction'))
    fuse(holder, box('Wago rear stop', (22, 2, 5.2), (x, y-10.7, 8.7), 'Construction'))
    fuse(holder, cylinder('Holder fixing ear', 4.8, 4.3, 2, (x, y-14)))
    hole(holder, (x, y-14), 4, 3)
    # A shallow front lip locates the body below conductor entry level.
    fuse(holder, box('Wago front toe', (18.8, 1.4, 1), (x, y+10.2, 6.7), 'Construction'))
    holder['channel'] = S.WAGO_CHANNELS[index]
    finish(holder, black)
    return holder


def cable_clamp(x, index, black):
    obj = rounded(f'cable_clamp_{index+1}', 24, 10, 2, 16.3, 4, (x, 110))
    bore = cylinder('Clamp cable relief', (S.CABLE_DIAMETER+S.CABLE_CLEARANCE)/2, -6, 12)
    bore.rotation_euler.x = math.pi/2
    bore.location = (x, 110, S.CABLE_Z)
    cut(obj, bore)
    for dx in (-9, 9):
        hole(obj, (x+dx, 110), 15, 7)
    finish(obj, black, rotation=(180, 0, 0))
    return obj


def mains_guard(black):
    guard = rounded('mains_terminal_guard', 57, 37, 2, 36.4, 2.4, (-82.5, -92.5))
    for x in (-109.3, -55.7):
        fuse(guard, box('Guard cheek', (2.4, 36, 28.2), (x, -92.5, 22.5), 'Construction'))
    fuse(guard, box('Guard lower end', (56, 2.4, 28.2), (-82.5, -109.8, 22.5), 'Construction'))
    hole(guard, (-103, -103), 0, 45, 13.0, 'Cover-column clearance')
    for x, y in S.GUARD_FIXINGS:
        fuse(guard, box('Guard ear bridge', (8, 10, 2.4), (-52, y, 9.6), 'Construction'))
        fuse(guard, cylinder('Guard fixing ear', 5.5, 8.4, 2.4, (x, y)))
        hole(guard, (x, y), 8, 4)
    wire = cylinder('Mains cable entry', 6, -6, 12)
    wire.rotation_euler.y = math.pi/2
    wire.location = (-55.7, -96, 17)
    cut(guard, wire)
    boundary = rounded('Guard skirt clearance', 222.8, 222.8, 8.4, 0, 45, group='Construction')
    boolean(guard, boundary, 'INTERSECT', 'Clear rounded cover corner')
    finish(guard, black, rotation=(180, 0, 0))
    return guard


def cover(black):
    shell = rounded('reactor_cover', 230, 230, 12, S.SKIRT_BOTTOM, S.FRONT_Z-S.SKIRT_BOTTOM)
    cut(shell, rounded('Cover cavity', 230-2*S.WALL, 230-2*S.WALL, 12-S.WALL,
                       3.4, S.FRONT_Z-S.FRONT_T-3.4, group='Construction'))
    hole(shell, (0, 0), 46, 10, 2*S.INSERT_OPENING, 'Interchangeable centre aperture')
    for angle in S.INSERT_ANGLES:
        fuse(shell, radial_box('Insert mounting tab', 57.5, angle, 16, 11, 49, 3), 'Front-plane insert tab')
        a = math.radians(angle)
        hole(shell, (S.INSERT_SCREW_RADIUS*math.cos(a), S.INSERT_SCREW_RADIUS*math.sin(a)), 48, 5)
    for xy in S.COVER_FIXINGS:
        hole(shell, xy, 48, 6)
        hole(shell, xy, 50.2, 3, 6.8, 'Recessed cover screw head')
    # Slots lie on side faces behind the front bezel, invisible in a head-on view.
    for side in (-1, 1):
        for y in (-50, -32, -14, 4, 22, 40, 58):
            tool = rounded('Side cooling slot', 8, 12, 2, -5, 10, group='Construction')
            tool.rotation_euler.y = math.pi/2
            tool.location = (side*113.4, y, 24)
            cut(shell, tool, 'Side ventilation')
        for x in ((-68, -50, 50, 68) if side == 1 else (-25, -7, 11, 29)):
            tool = rounded('Edge cooling slot', 8, 12, 2, -5, 10, group='Construction')
            tool.rotation_euler.x = math.pi/2
            tool.location = (x, side*113.4, 23)
            cut(shell, tool, 'Upper/lower ventilation')
    for x in S.CENTERED_CABLE_X:
        cut(shell, box('Lift-off cable opening', (26.4, 14, 20), (x, 111, 13.2), 'Construction'))
    for a0, a1 in S.RING_SEGMENTS:
        for angle in (a0+14, a1-14):
            a = math.radians(angle)
            hole(shell, (83*math.cos(a), 83*math.sin(a)), 48.5, 5, 3.2, 'Reactor trim locating pin')
    # Recessed angular panel seams live outside the reactor ring.
    for angle in (45, 135, 225, 315):
        cut(shell, radial_box('Corner panel seam', 126, angle, 20, 0.9, 51.5, 1), 'Engraved corner seam')
    # Two little datum bars below the ring; cut into the front, never raised.
    for x in (-18, 18):
        cut(shell, box('Front datum engraving', (24, 1.2, 0.5), (x, -104, 51.85), 'Construction'))
    for angle in range(0, 360, 90):
        for radius in (103, 107):
            cut(shell, radial_box('Perimeter equipment seam', radius, angle,
                                 0.9, 58, 51.5, 0.8), 'Layered perimeter engraving')
    for angle in range(0, 360, 20):
        cut(shell, radial_box('Reactor index mark', 67, angle, 1.8, 1.2,
                             51.5, 0.8), 'Reactor calibration tick')
    shell['gf_expected_bbox_mm'] = (230, 230, S.FRONT_Z-S.SKIRT_BOTTOM)
    finish(shell, black, rotation=(180, 0, 0))
    return shell


def trims(gray):
    result = []
    for index, (a0, a1) in enumerate(S.RING_SEGMENTS):
        obj = sector(f'reactor_ring_{index+1}', S.RING_INNER, S.RING_OUTER, a0, a1, 52, 3)
        # Recessed concentric line and radial breaks give depth without extra support.
        groove = sector('Ring engraved channel', 88, 89, a0+5, a1-5, 54.5, 1)
        cut(obj, groove)
        # A recessed outer race and inner spoke create three visual tiers.
        cut(obj, sector('Outer race step', 94, 101, a0+3, a1-3, 54.1, 1.2))
        fuse(obj, radial_box('Inward reactor spoke', 72, (a0+a1)/2,
                            12, 9, 52, 3))
        for angle in (a0+9, a1-9):
            cut(obj, radial_box('Radial panel break', 84, angle, 23, 1.2, 54.3, 1))
        for angle in (a0+14, a1-14):
            a = math.radians(angle)
            fuse(obj, cylinder('Trim locating peg', 1.5, 49.4, 2.8, (83*math.cos(a), 83*math.sin(a))))
        finish(obj, gray, rotation=(180, 0, 0), filament=2)
        bevel = obj.modifiers.new('Machined trim edges', 'BEVEL')
        bevel.width = 0.35
        bevel.segments = 2
        result.append(obj)
    # Separate corner armor leaves the original cover seats and depth intact.
    for index, angle in enumerate((0, 90, 180, 270), 1):
        a = math.radians(angle)
        points = [(72, 100), (92, 80), (110, 92), (110, 103),
                  (103, 110), (92, 110)]
        points = [(x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a))
                  for x, y in points]
        obj = prism(f'reactor_armor_{index}', points, 52, 3)
        xy = (103*math.cos(a)-103*math.sin(a), 103*math.sin(a)+103*math.cos(a))
        hole(obj, xy, 51.8, 4, 9, 'Access to unchanged cover fastener')
        cut(obj, radial_box('Armor recessed score', 137, 45+angle,
                            9, 1.1, 54.2, 1), 'Armor score')
        finish(obj, gray, rotation=(180, 0, 0), filament=2)
        bevel = obj.modifiers.new('Armor edge chamfers', 'BEVEL')
        bevel.width = 0.65
        bevel.segments = 1
        result.append(obj)
    return result


def insert(name, black, glow=None):
    if glow:
        from flux_insert import build_flux
        return build_flux(black, glow)
    obj = cylinder(name, S.INSERT_RADIUS, 52, 3.0, group='Printable', count=128)
    for angle in S.INSERT_ANGLES:
        a = math.radians(angle)
        xy = (56*math.cos(a), 56*math.sin(a))
        hole(obj, xy, 51, 6)
        countersink(obj, xy, 55)
    groove = cylinder('Disc recessed perimeter', 50, 54.55, 0.8)
    hole(groove, (0, 0), 54.4, 1.2, 98.4)
    cut(obj, groove)
    finish(obj, black, part=name)
    return obj, None


def component_envelopes():
    psu = box('PSU_envelope', S.PSU_SIZE, (*S.PSU_XY, S.PSU_BOTTOM+12.5), 'Construction')
    psu['orientation'] = 'Mains -Y; 24 V +Y; mounting ears approximately diagonal'
    box('controller_envelope', S.CONTROLLER_SIZE, (*S.CRADLE_CAVITY_XY, S.CONTROLLER_BOTTOM+12.5), 'Construction')
    for index, (x, y) in enumerate((x, y) for y in S.WAGO_Y for x in S.WAGO_X):
        box(f'wago_envelope_{index+1}', S.WAGO_SIZE, (x, y, S.WAGO_BOTTOM+4.2), 'Construction')
        box(f'wago_lever_access_{index+1}', (18.8, 18.6, 13), (x, y, 21.7), 'Construction')
        # Individual pigtails rise over the preceding connector row, keeping
        # the short lower end aligned with the actual conductor entries.
        vertices = [(xx, yy, zz+h) for h in (0, 5)
                    for xx, yy, zz in [(x-9.4, y+9.3, 8), (x+9.4, y+9.3, 8),
                                       (x+9.4, y+23.3, 17), (x-9.4, y+23.3, 17)]]
        mesh = bpy.data.meshes.new('Wire service ramp')
        mesh.from_pydata(vertices, [], [(3, 2, 1, 0), (4, 5, 6, 7),
                                       (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
        obj = bpy.data.objects.new(f'wago_wire_access_{index+1}', mesh)
        bpy.data.collections['Construction'].objects.link(obj)
        collection(obj, 'Construction')
    box('controller_input_access', (22, 18, 15), (82, 88.5, 25), 'Construction')
    box('controller_output_access', (31, 14, 15), (82, -2.5, 25), 'Construction')
    prism('PSU_DC_access', [(-103.5, 89), (-61.5, 89), (-69.5, 104), (-95.5, 104)], 17, 14, 'Construction')
    prism('PSU_mains_access', [(-103.5, -89), (-95.5, -104), (-69.5, -104), (-61.5, -89)], 17, 14, 'Construction')
    box('Low_voltage_bundle_path', (7, 140, 7), (107, 15, 26), 'Construction')
    # Two 7 mm jackets can stack in Z with 2 mm total spare height.
    box('Strip_side_route', (7, 140, 16), (107, 15, 30.5), 'Construction')
    box('Strip_top_route', (113, 7, 16), (40, 96, 30.5), 'Construction')
    box('Strip_right_turn', (21, 7, 16), (100, 85, 30.5), 'Construction')
    box('Strip_right_turn_rise', (7, 18, 16), (93, 90.5, 30.5), 'Construction')
    for index, x in enumerate(S.CENTERED_CABLE_X):
        # Conservative descent reserve connects the top route to each saddle.
        box(f'Strip_descent_{index}', (7, 8, 26), (x, 100, 25.5), 'Construction')
    rounded('Rear_access_envelope', 100, 100, 10, -2, 44, group='Construction')


def coupons(base, first_holder, black):
    # Cut coupons from actual evaluated features, preserving their exact geometry.
    for name, source, xy, size, offset in [
        ('coupon_psu_mount', base, S.PSU_FIXINGS[0], (19, 29, 12), (-210, -65, 0)),
        ('coupon_cover_post', base, S.COVER_FIXINGS[0], (18, 18, 52), (-205, -5, 0)),
        ('coupon_cover_corner', bpy.data.objects['reactor_cover'], S.COVER_FIXINGS[0], (18, 18, 55), (-175, -5, 0)),
        ('coupon_controller_cradle', bpy.data.objects['controller_cradle'], S.CRADLE_CAVITY_XY,
         (47, 14, 40), (-205, -110, 0)),
    ]:
        obj = evaluated_copy(source, name)
        tool = box(name+'_slice', size, (*xy, size[2]/2-0.5), 'Construction')
        from geometryforge.blender_scene import boolean
        modifier = boolean(obj, tool, 'INTERSECT', 'Coupon from actual mount')
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        delta = Vector((offset[0]-xy[0], offset[1]-xy[1], offset[2]))
        obj.location += delta
        obj['coupon_source'] = source.name
        obj['coupon_xy'] = xy
        obj['coupon_size'] = size
        obj['coupon_offset'] = list(delta)
        finish(obj, black, rotation=(180, 0, 0) if name == 'coupon_cover_corner' else (0, 0, 0))
    obj = evaluated_copy(first_holder, 'coupon_wago_holder')
    obj.location += Vector((-275, 23, 0))
    obj['coupon_source'] = first_holder.name
    obj['coupon_offset'] = (-275, 23, 0)
    finish(obj, black)


def setup_view():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1400
    scene.render.resolution_percentage = 100
    scene.world.color = (0.18, 0.18, 0.18)
    for name, loc, energy, size in [('Key', (-170, 100, 330), 1700000, 240),
                                     ('Fill', (220, -120, 250), 1100000, 180)]:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.size = energy, size
        obj = bpy.data.objects.new(name, data)
        bpy.data.collections['Presentation'].objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((0, 0, 20))-obj.location).to_track_quat('-Z', 'Y').to_euler()
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    bpy.data.collections['Presentation'].objects.link(camera)
    camera.location = (235, -310, 500)
    camera.rotation_euler = (Vector((0, 0, 25))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 340
    scene.camera = camera
    # Only the installed insert is visible in the default view; all still export.
    bpy.data.objects['insert_plain'].hide_render = True
    for obj in bpy.data.collections['Printable'].objects:
        if obj.name.startswith('coupon_'):
            obj.hide_render = True
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance = 380
            area.spaces.active.region_3d.view_location = (0, 0, 24)


def build():
    initialize()
    black = material('Black PETG', (0.028, 0.034, 0.045))
    gray = material('Matte gray PETG', (0.39, 0.43, 0.47), 0.15)
    glow = material('Optional pale luminous insert', (0.56, 0.9, 0.86))
    base = backplate(black)
    print('Built backplate and fixed mounts', flush=True)
    controller_cradle(black)
    holders = []
    for index, (x, y) in enumerate((x, y) for y in S.WAGO_Y for x in S.WAGO_X):
        holders.append(wago_holder(x, y, index, black))
    for index, x in enumerate(S.CENTERED_CABLE_X):
        cable_clamp(x, index, black)
    mains_guard(black)
    print('Built controller, connector holders, cable clamps, and guard', flush=True)
    cover(black)
    trims(gray)
    plain, _ = insert('insert_plain', black)
    # Park the alternate insert off to the side in the editable scene.
    def park_with_tools(obj, visited=None):
        visited = set() if visited is None else visited
        if obj.name in visited:
            return
        visited.add(obj.name)
        obj.location.x += 260
        for modifier in obj.modifiers:
            if modifier.type == 'BOOLEAN' and modifier.object:
                park_with_tools(modifier.object, visited)
    park_with_tools(plain)
    plain['assembly_offset'] = (260, 0, 0)
    insert('insert_flux', black, glow)
    print('Built reactor cover and interchangeable inserts', flush=True)
    component_envelopes()
    coupons(base, holders[0], black)
    print('Cut mounting and connector coupons', flush=True)
    for obj in bpy.data.collections['Printable'].objects:
        weld = obj.modifiers.new('Merge Boolean seam vertices (0.00005 mm)', 'WELD')
        weld.merge_threshold = 0.00005
    setup_view()
