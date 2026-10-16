"""Gate 3 detail: every mechanical part is bound to an interface ring exported by Gate 2, or seated on a panel surface.

Vehicle space in mm: X forward, Y left, Z up, Z=0 at the pad-bottom plane.

- pads: one pad built once, four linked placements, each bound to a belly pad-bay seat ring.
- nacelle_drive: bearing drum and bulkhead flange on each socket seat ring, a shaft coaxial with the drum that ends in
  a bellows-sealed angle joint at the nacelle hub, a coupling hub on each nacelle hub seat ring, ribbed service hoses
  from the nacelle nose into glands in the socket's inboard wall, and a cross-drive spine behind both sockets.
  The socket faces 18 deg up (the rear face leans back) while the hub faces straight forward, so the two axes meet
  in the angle joint instead of a single straight shaft.
- glass: curved panes parallel to the hull, filling each window seat ring (set back by the pocket depth).
- inserts: headlamp and tail light clusters and nacelle exhaust slats inside their pockets.
- roof_equipment: taxi sign, drum pod on a pedestal and antenna, seated on the roof surface.
- interior: simple seats, dash and wheel.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SIDES = ('r', 'l')
PADS = ('fr', 'fl', 'rr', 'rl')
WINDOWS = ('qwin', 'win2', 'win3', 'win4')


# Construction helpers ------------------------------------------------------------------------------------------
def fillet(profile, radius, segments=4):
    """Round each interior corner of an open 2D polyline with a Bezier arc; radius is a number or one per point."""
    pts = [np.asarray(p, dtype=float) for p in profile]
    radii = list(radius) if isinstance(radius, (list, tuple)) else [radius] * len(pts)
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p, a, b = pts[i], pts[i - 1], pts[i + 1]
        u, v = a - p, b - p
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        u, v = u / lu, v / lv
        half = math.acos(max(-1.0, min(1.0, float(u @ v)))) / 2
        if radii[i] <= 0 or half > math.radians(89):
            out.append(p)
            continue
        setback = min(radii[i] / math.tan(half), lu * .45, lv * .45)
        start, end = p + u * setback, p + v * setback
        out += [(1 - t) ** 2 * start + 2 * (1 - t) * t * p + t ** 2 * end for t in np.linspace(0, 1, segments + 1)]
    out.append(pts[-1])
    return out


def outward_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def lathe(s, name, profile, segments=64, radius=0.0, arc=None):
    """Closed solid of revolution about local Z from an (r, z) profile; arc=(a0, a1) degrees builds a sector."""
    points = fillet(profile, radius) if radius else [np.asarray(p, dtype=float) for p in profile]
    if arc is None:
        angles = np.linspace(0, 2 * math.pi, segments, endpoint=False)
        rings = [[(r * math.cos(a), r * math.sin(a), z) for a in angles] for r, z in points]
        return outward_normals(s.loft(name, rings, caps=True))
    # Sector: loft the closed section along the arc.
    angles = np.radians(np.linspace(arc[0], arc[1], segments))
    rings = [[(r * math.cos(a), r * math.sin(a), z) for r, z in points] for a in angles]
    return outward_normals(s.loft(name, rings, caps=True))


def block(s, name, size, centre=(0, 0, 0), bevel=3.0, matrix=None):
    """Box with a rounded-edge Bevel modifier (no raw 90-degree edges)."""
    x, y, z = (v / 2 for v in size)
    verts = [(sx * x + centre[0], sy * y + centre[1], sz * z + centre[2])
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    obj = outward_normals(s.mesh_object(name, verts, faces, smooth=True))
    if matrix is not None:
        obj.data.transform(matrix)
    rounded(obj, bevel)
    return obj


def prism(s, name, outline, z0, z1, bevel=3.0):
    """Extruded closed 2D outline (XY) between z0 and z1, edges rounded by a Bevel modifier."""
    rings = [[(x, y, z0) for x, y in outline], [(x, y, z1) for x, y in outline]]
    obj = outward_normals(s.loft(name, rings, caps=True))
    rounded(obj, bevel)
    return obj


def rounded(obj, width, segments=3):
    if width:
        mod = obj.modifiers.new('Edge rounding', 'BEVEL')
        mod.width, mod.segments, mod.limit_method, mod.angle_limit = width, segments, 'ANGLE', math.radians(30)
        mod.harden_normals = False
        obj.modifiers.new('Feature shading', 'WEIGHTED_NORMAL').keep_sharp = True
    return obj


def place(objects, matrix):
    for obj in objects:
        obj.matrix_world = matrix
    return objects


def frame(axis, up=(0, 0, 1)):
    """Orthonormal (u, w, axis): u horizontal across the axis, w completing a right-handed frame."""
    a = np.asarray(axis, dtype=float)
    a /= np.linalg.norm(a)
    u = np.cross(np.asarray(up, dtype=float), a)
    if np.linalg.norm(u) < 1e-6:
        u = np.cross([1.0, 0.0, 0.0], a)
    u /= np.linalg.norm(u)
    return u, np.cross(a, u), a


def matrix_from(origin, u, w, a):
    from mathutils import Matrix
    m = Matrix.Identity(4)
    for row in range(3):
        m[row][0], m[row][1], m[row][2], m[row][3] = u[row], w[row], a[row], origin[row]
    return m


def mate_ring(s, name, radius, z=0.0, axis=(0, 0, 1), segments=48):
    """Child-side interface ring in local coordinates; bind_to_ring carries it with its part."""
    points = [(radius * math.cos(2 * math.pi * k / segments), radius * math.sin(2 * math.pi * k / segments), z)
              for k in range(segments)]
    ring = s.mesh_object(name, points, [], role=None, smooth=False, edges=[(k, (k + 1) % segments) for k in range(segments)])
    return s.api.register_output(ring, None, 'interface', axis=list(axis), loop=name)


def roll_to_up(local_axis, axis, local_up=(0, 1, 0), world_up=(0, 0, 1)):
    """Roll (deg) about the ring axis that turns the part's local up toward world up after alignment."""
    a = Vector(axis).normalized()
    align = Vector(local_axis).normalized().rotation_difference(a)
    have = align @ Vector(local_up)
    want = Vector(world_up)
    have, want = have - a * a.dot(have), want - a * a.dot(want)
    if have.length < 1e-6 or want.length < 1e-6:
        return 0.0
    have.normalize(), want.normalize()
    angle = have.angle(want)
    return math.degrees(angle if a.dot(have.cross(want)) > 0 else -angle)


def ring_points(ring):
    """World points of an interface ring in edge order."""
    mw = ring.matrix_world
    edges = [tuple(e.vertices) for e in ring.data.edges]
    neighbours = {}
    for a, b in edges:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    order, previous, current = [edges[0][0]], None, edges[0][0]
    while True:
        following = [n for n in neighbours[current] if n != previous][0]
        if following == order[0]:
            break
        order.append(following)
        previous, current = current, following
    return np.array([mw @ ring.data.vertices[i].co for i in order], dtype=float)


def surface(obj):
    """Closest point and normal on an evaluated object (world space)."""
    graph = bpy.context.evaluated_depsgraph_get()
    inverse, rotation = obj.matrix_world.inverted(), obj.matrix_world.to_3x3()

    def query(point):
        hit, location, normal, _ = obj.closest_point_on_mesh(inverse @ Vector(point), depsgraph=graph)
        if not hit:
            raise ValueError(f'No surface on {obj.name} near {point}')
        return np.array(obj.matrix_world @ location), np.array((rotation @ normal).normalized())
    return query


def roof_height(master, x, y):
    graph = bpy.context.evaluated_depsgraph_get()
    inverse = master.matrix_world.inverted()
    hit, location, normal, _ = master.ray_cast(inverse @ Vector((x, y, 4000.0)), Vector((0, 0, -1)), depsgraph=graph)
    if not hit:
        raise ValueError(f'Roof not found at {x}, {y}')
    return (master.matrix_world @ location).z


def closest_between(p1, d1, p2, d2):
    """Midpoint of the shortest segment between two lines, with each line's parameter."""
    w = p1 - p2
    a, b, c, d, e = d1 @ d1, d1 @ d2, d2 @ d2, d1 @ w, d2 @ w
    denominator = a * c - b * b
    t1, t2 = (b * e - c * d) / denominator, (a * e - b * d) / denominator
    return (p1 + t1 * d1 + p2 + t2 * d2) / 2, t1, t2


# Pads ----------------------------------------------------------------------------------------------------------
def pad_pieces(s, label, p):
    """One pad in local space: Z up into the body, pad bottom centre at the origin."""
    R, top, boss_top = p['pad_radius_mm'], p['pad_height_mm'], p['pad_boss_top_mm']
    pieces = []
    # Shell: stepped chrome rim with a recessed side-band groove and a flat top deck.
    shell = [(400, 55), (420, 18), (470, 0), (R - 25, 0), (R, 30), (R, 95), (R - 12, 101), (R - 12, 139), (R, 145),
             (R, 185), (R - 35, top - 25), (420, top - 10), (400, top), (215, top)]
    radii = [0, 6, 10, 14, 18, 3, 2, 2, 3, 18, 14, 4, 4, 0]
    pieces.append(lathe(s, f'Pad {label} shell', fillet(shell, radii), segments=96))
    # Emitter: concentric ridges in the recess, a central service cap and twelve radial ribs.
    emitter = [(110, 55), (110, 40), (150, 38), (150, 52), (170, 52), (170, 40), (230, 40), (230, 52), (250, 52),
               (250, 42), (320, 42), (320, 52), (340, 52), (340, 44), (398, 44), (398, 55)]
    pieces.append(lathe(s, f'Pad {label} emitter', fillet(emitter, 2.5), segments=96))
    pieces.append(lathe(s, f'Pad {label} cap', fillet([(20, 30), (80, 30), (108, 42), (108, 56)], [0, 10, 4, 0]), segments=48))
    for k in range(12):
        angle = 2 * math.pi * k / 12
        rib = block(s, f'Pad {label} rib {k}', (250, 14, 22), ((150 + 398) / 2, 0, 44), bevel=2.0)
        rib.data.transform(_rotation_z(angle))
        pieces.append(rib)
    # Side band: sixteen curved emitter segments in the groove.
    for k in range(16):
        a0 = 360 * k / 16 + 2.5
        pieces.append(lathe(s, f'Pad {label} band {k}', fillet([(R - 13, 104), (R - 3, 104), (R - 3, 136), (R - 13, 136)], 0),
                            segments=10, arc=(a0, a0 + 360 / 16 - 5)))
    # Boss: two-tier column up through the bay with a bearing collar below the belly rim.
    boss = [(215, top - 1), (215, top + 12), (175, top + 24), (175, top + 56), (182, top + 60), (182, top + 76),
            (150, top + 84), (140, top + 96), (140, boss_top)]
    pieces.append(lathe(s, f'Pad {label} boss', fillet(boss, [0, 6, 8, 4, 3, 3, 6, 6, 0]), segments=64))
    # Four gussets from the deck into the boss collar (load path), and deck bolts.
    profile = [(190, top - 2), (430, top - 2), (190, top + 70)]
    verts = [(r, side, z) for r, z in profile for side in (-12, 12)]
    faces = [(0, 2, 4), (1, 5, 3), (0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 1, 0)]
    for k in range(4):
        gusset = rounded(outward_normals(s.mesh_object(f'Pad {label} gusset {k}', verts, faces, smooth=True)), 3.0)
        gusset.data.transform(_rotation_z(math.pi / 4 + k * math.pi / 2))
        pieces.append(gusset)
    for k in range(12):
        angle = 2 * math.pi * (k + .5) / 12
        bolt = lathe(s, f'Pad {label} bolt {k}', [(9, top - 1), (14, top - 1), (14, top + 9), (9, top + 11)], segments=6)
        bolt.data.transform(_translation(330 * math.cos(angle), 330 * math.sin(angle), 0))
        pieces.append(bolt)
    return pieces


def _rotation_z(angle):
    from mathutils import Matrix
    return Matrix.Rotation(angle, 4, 'Z')


def _translation(x, y, z):
    from mathutils import Matrix
    return Matrix.Translation((x, y, z))


def build_pads(s, p):
    seats = {k: bpy.data.objects[f'_interface_pad_{k}_seat'] for k in PADS}
    lap = p['pad_lap_mm']
    # Pad bottoms on Z=0: the boss top sits `lap` above the mean seat height.
    seat_z = np.mean([s.ring_frame(r)[0][2] for r in seats.values()])
    p = dict(p, pad_boss_top_mm=float(seat_z + lap))
    source = pad_pieces(s, PADS[0].upper(), p)
    origin = (0, 0, p['pad_boss_top_mm'])
    for key in PADS:
        label = key.upper()
        if key == PADS[0]:
            pieces = source
        else:
            pieces = []
            for obj in source:
                copy = obj.copy()  # linked duplicate: one pad mesh, four placements
                copy.name = obj.name.replace(f'Pad {PADS[0].upper()}', f'Pad {label}')
                bpy.context.scene.collection.objects.link(copy)
                pieces.append(s.api.register_output(copy, None, 'design'))
        ring = mate_ring(s, f'_mate_pad_{key}', 140, z=p['pad_boss_top_mm'], axis=(0, 0, -1))
        s.bind_to_ring(pieces[0], seats[key], local_axis=(0, 0, -1), local_origin=origin, lap=lap,
                       interfaces=(*pieces[1:], ring))


# Nacelle drive -------------------------------------------------------------------------------------------------
def ribbed_tube(s, name, path, radius, rib=4.0, pitch=24.0, sides=14):
    """Tube along a polyline with alternating rib radii every half pitch (service hose)."""
    path = np.asarray(path, dtype=float)
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    steps = max(4, int(lengths[-1] / (pitch / 2)))
    t = np.linspace(0, lengths[-1], steps + 1)
    points = np.column_stack([np.interp(t, lengths, path[:, i]) for i in range(3)])
    tangents = np.gradient(points, axis=0)
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    normal = np.cross(tangents[0], [0, 0, 1] if abs(tangents[0][2]) < .9 else [1, 0, 0])
    normal /= np.linalg.norm(normal)
    rings = []
    for i, (centre, tangent) in enumerate(zip(points, tangents)):
        normal = normal - tangent * (normal @ tangent)
        normal /= np.linalg.norm(normal)
        binormal = np.cross(tangent, normal)
        r = radius + (rib if i % 2 else 0.0)
        rings.append([tuple(centre + r * (normal * math.cos(2 * math.pi * k / sides) + binormal * math.sin(2 * math.pi * k / sides)))
                      for k in range(sides)])
    return outward_normals(s.loft(name, rings, caps=True))


def bezier(p0, p1, p2, p3, count=24):
    t = np.linspace(0, 1, count)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def build_drive_side(s, side, p):
    label = side.upper()
    socket_seat = bpy.data.objects[f'_interface_socket_{side}_seat']
    socket_rim = bpy.data.objects[f'_interface_socket_{side}']
    hub_seat = bpy.data.objects[f'_interface_hub_{side}_seat']
    c_s, a_s, _ = s.ring_frame(socket_seat)
    c_h, a_h, _ = s.ring_frame(hub_seat)
    drum_lap, shaft_lap, coupling_lap = p['drum_lap_mm'], p['shaft_lap_mm'], p['coupling_lap_mm']

    # Bearing drum on a bulkhead flange behind the socket seat (local Z points out of the socket).
    flange_t, drum_front = 12.0, 132.0
    from geometryforge.sections import superellipse_ring
    outline = superellipse_ring(330, 470, exponent=3.0, segments=48)
    flange = prism(s, f'Drive {label} bulkhead flange', [tuple(q) for q in outline], 0, flange_t, bevel=3.0)
    drum = lathe(s, f'Drive {label} bearing drum', [(60, flange_t - 1), (105, flange_t - 1), (105, 30), (92, 40), (92, 118),
                                                   (98, 122), (98, drum_front), (60, drum_front)], radius=4, segments=64)
    bolts = []
    for k in range(10):
        angle = 2 * math.pi * k / 10
        bolt = lathe(s, f'Drive {label} flange bolt {k}', [(7, flange_t - 1), (12, flange_t - 1), (12, flange_t + 9), (7, flange_t + 11)], segments=6)
        bolt.data.transform(_translation(118 * math.cos(angle), 170 * math.sin(angle), 0))
        bolts.append(bolt)
    drum_mate = mate_ring(s, f'_mate_drum_{side}', 105, z=0.0)
    drum_ring = mate_ring(s, f'_interface_drum_{side}', 60, z=drum_front)
    roll = roll_to_up((0, 0, 1), a_s)
    s.bind_to_ring(flange, socket_seat, local_axis=(0, 0, 1), lap=drum_lap, roll_deg=roll,
                   interfaces=(drum, *bolts, drum_mate, drum_ring))

    # Angle joint where the drum axis meets the nacelle hub axis.
    c_d, a_d, _ = s.ring_frame(drum_ring)
    joint, _, _ = closest_between(c_d, a_d, c_h, a_h)
    shaft_origin = c_d - a_d * shaft_lap
    length = float((joint - shaft_origin) @ a_d)
    shaft = lathe(s, f'Drive {label} shaft', [(30, 0), (40, 0), (40, shaft_lap), (52, shaft_lap + 4), (52, shaft_lap + 22),
                                             (44, shaft_lap + 26), (44, length - 40), (30, length - 40)], radius=3, segments=48)
    folds = [(44, length - 170)]
    for k in range(6):
        z = length - 165 + k * 20
        folds += [(70, z + 5), (70, z + 10), (58, z + 15), (58, z + 20)]
    folds += [(76, length - 40), (60, length - 30)]
    bellows = lathe(s, f'Drive {label} bellows', folds, radius=3, segments=48)
    ball = lathe(s, f'Drive {label} joint ball', [(20, length - 75)] + [(72 * math.sin(a), length + 72 * -math.cos(a)) for a in np.linspace(.35, math.pi - .35, 9)] + [(20, length + 70)], segments=48)
    shaft_mate = mate_ring(s, f'_mate_shaft_{side}', 40, z=0.0)
    s.bind_to_ring(shaft, drum_ring, local_axis=(0, 0, 1), lap=shaft_lap, interfaces=(bellows, ball, shaft_mate))

    # Coupling hub on the nacelle hub seat (local Z points out of the nacelle toward the body), cupping the ball.
    reach = float((joint - (c_h - a_h * coupling_lap)) @ a_h)
    coupling = lathe(s, f'Drive {label} coupling hub', [(40, 0), (105, 0), (105, 14), (85, 20), (85, 40), (62, 48),
                                                       (62, reach - 95), (88, reach - 80), (88, reach - 10), (76, reach - 10), (76, reach - 70), (40, reach - 70)],
                     radius=[0, 3, 3, 4, 4, 4, 4, 6, 4, 2, 2, 0], segments=64)
    hub_bolts = []
    for k in range(8):
        angle = 2 * math.pi * (k + .5) / 8
        bolt = lathe(s, f'Drive {label} hub bolt {k}', [(6, 13), (10, 13), (10, 22), (6, 24)], segments=6)
        bolt.data.transform(_translation(92 * math.cos(angle), 92 * math.sin(angle), 0))
        hub_bolts.append(bolt)
    coupling_mate = mate_ring(s, f'_mate_coupling_{side}', 105, z=0.0)
    s.bind_to_ring(coupling, hub_seat, local_axis=(0, 0, 1), lap=coupling_lap, roll_deg=roll_to_up((0, 0, 1), a_h),
                   interfaces=(*hub_bolts, coupling_mate))

    # Service hoses: nacelle nose face -> glands in the socket's inboard wall.
    nacelle = bpy.data.objects[f'Nacelle master {label}']
    seat_pts, rim_pts = ring_points(socket_seat), ring_points(socket_rim)
    u, w, _ = frame(a_s)
    inboard = -np.sign(c_s[1]) * np.array([0.0, 1.0, 0.0])
    graph = bpy.context.evaluated_depsgraph_get()
    inverse = nacelle.matrix_world.inverted()
    hoses = []
    for k, lift in enumerate((-70.0, 70.0)):
        def wall_point(points, centre):
            local = points - centre
            score = local @ inboard - .6 * np.abs(local @ w - lift)
            return points[np.argmax(score)]
        g_seat, g_rim = wall_point(seat_pts, c_s), wall_point(rim_pts, s.ring_frame(socket_rim)[0])
        gland_at = g_seat + .45 * (g_rim - g_seat)
        towards_axis = c_s + a_s * ((gland_at - c_s) @ a_s) - gland_at
        towards_axis /= np.linalg.norm(towards_axis)
        gland = lathe(s, f'Drive {label} gland {k}', [(18, -12), (34, -12), (34, 6), (30, 12), (30, 24), (18, 24)], radius=2, segments=6)
        gu, gw, ga = frame(towards_axis)
        gland.matrix_world = matrix_from(gland_at, gu, gw, ga)
        start_guess = c_h + a_h * 400 + inboard * 150 + np.array([0.0, 0.0, lift])  # in front of the nose, outside the hub pocket
        hit, location, normal, _ = nacelle.ray_cast(inverse @ Vector(start_guess), Vector(-a_h), depsgraph=graph)
        start = np.array(nacelle.matrix_world @ location) if hit else c_h + inboard * 150
        fitting = lathe(s, f'Drive {label} hose fitting {k}', [(16, -30), (30, -30), (30, 10), (24, 22), (16, 22)], radius=2, segments=6)
        fu, fw, fa = frame(a_h)
        fitting.matrix_world = matrix_from(start, fu, fw, fa)
        end = gland_at + towards_axis * 24
        path = bezier(start + a_h * 22, start + a_h * 130, end + towards_axis * 70, end)
        hoses.append(ribbed_tube(s, f'Drive {label} hose {k}', path, 18.0))
    return np.array(flange.matrix_world.translation), a_s


def build_drive(s, p):
    backs = [build_drive_side(s, side, p) for side in SIDES]
    # Cross-drive spine behind both bulkhead flanges, with a central gearbox (hidden load path).
    (right, a_r), (left, a_l) = backs
    behind_r, behind_l = right - a_r * 70, left - a_l * 70
    mid = (behind_r + behind_l) / 2
    span = behind_l - behind_r
    axis = span / np.linalg.norm(span)
    u, w, a = frame(axis)
    tube = lathe(s, 'Drive spine', [(20, 0), (48, 0), (48, np.linalg.norm(span)), (20, np.linalg.norm(span))], radius=3, segments=32)
    tube.matrix_world = matrix_from(behind_r, u, w, a)
    for k, t in enumerate((.2, .8)):
        collar = lathe(s, f'Drive spine flange {k}', [(20, -10), (70, -10), (70, 10), (20, 10)], radius=3, segments=32)
        collar.matrix_world = matrix_from(behind_r + span * t, u, w, a)
    box = block(s, 'Drive gearbox', (260, 300, 220), bevel=8.0)
    box.matrix_world = matrix_from(mid, *frame((1.0, 0.0, 0.0)))


# Glass ---------------------------------------------------------------------------------------------------------
def pane(s, name, seat, guide, rings=6, expand=2.0, thickness=6.0):
    """Curved pane through a seat ring: interior rings follow the hull offset by the seat depth."""
    query = surface(guide)
    edge = ring_points(seat)
    centre = edge.mean(axis=0)
    depth = np.mean([(query(q)[0] - q) @ query(q)[1] for q in edge])
    loops = []
    for f in np.linspace(1.0, .08, rings):
        loop = []
        for q in edge:
            point = centre + f * (q - centre)
            if f == 1.0:
                outward = (q - centre) / np.linalg.norm(q - centre)
                loop.append(tuple(q + outward * expand))
            else:
                location, normal = query(point)
                loop.append(tuple(location - normal * depth))
        loops.append(loop)
    obj = outward_normals(s.loft(name, loops, caps=True))
    solid = obj.modifiers.new('Glass thickness', 'SOLIDIFY')
    # Even offset divides by the fold angle and explodes on the fan centre; keep simple offset.
    solid.thickness, solid.offset, solid.use_even_offset = thickness, 1.0, False
    return obj


def build_glass(s, p):
    guide = bpy.data.objects['Master hull']
    names = ['windshield'] + [f'{w}_{side}' for side in SIDES for w in WINDOWS]
    for name in names:
        seat = bpy.data.objects[f'_interface_{name}_seat']
        obj = pane(s, f'Glass {name}', seat, guide)
        # Solidify grows toward the cabin: flip if the pane's normals face outward.
        c, a, _ = s.ring_frame(seat)
        normal = np.mean([np.array(poly.normal) for poly in obj.data.polygons], axis=0)
        if normal @ a > 0:
            obj.modifiers['Glass thickness'].offset = -1.0


# Inserts -------------------------------------------------------------------------------------------------------
def seat_frame(s, seat):
    """Centre, long in-plane axis, short in-plane axis and outward axis of a seat ring."""
    centre, axis, _ = s.ring_frame(seat)
    points = ring_points(seat) - centre
    flat = points - np.outer(points @ axis, axis)
    long = np.linalg.svd(flat)[2][0]
    long -= axis * (long @ axis)
    long /= np.linalg.norm(long)
    return centre, long, np.cross(axis, long), axis


def build_inserts(s, p):
    guide = bpy.data.objects['Master hull']
    for side in SIDES:
        label = side.upper()
        # Headlamp: lens in the seat, three projector cells and an amber corner element standing on it.
        seat = bpy.data.objects[f'_interface_headlamp_{side}_seat']
        c, l, w, a = seat_frame(s, seat)
        pane(s, f'Headlamp {label} lens', seat, guide, rings=4, expand=1.0, thickness=4.0)
        outboard = np.sign(l[1] * c[1]) or 1.0
        for k, (along, size) in enumerate(((-120, 70), (-35, 70), (50, 70), (130, 50))):
            cell = block(s, f'Headlamp {label} cell {k}', (size, 58, 14), bevel=4.0)
            cell.matrix_world = matrix_from(c + l * along * outboard + a * 8, l, w, a)
        # Tail light: lens and a horizontal ribbed light bar.
        seat = bpy.data.objects[f'_interface_tail_{side}_seat']
        c, l, w, a = seat_frame(s, seat)
        pane(s, f'Tail {label} lens', seat, guide, rings=4, expand=1.0, thickness=4.0)
        for k in range(5):
            rib = block(s, f'Tail {label} bar {k}', (370, 8, 10), bevel=2.0)
            rib.matrix_world = matrix_from(c + w * (k - 2) * 26 + a * 6, l, w, a)
        # Nacelle exhaust: emitter back plate and six horizontal slats.
        seat = bpy.data.objects[f'_interface_exhaust_{side}_seat']
        c, a = s.ring_frame(seat)[:2]
        u, v, a = frame(a)
        from geometryforge.sections import chamfered_ring
        outline = [tuple(q) for q in chamfered_ring(450, 550, chamfer=.42, radius=6.0)]
        plate = prism(s, f'Exhaust {label} emitter', outline, 0, 12, bevel=3.0)
        plate.matrix_world = matrix_from(c, u, v, a)
        for k in range(6):
            slat = block(s, f'Exhaust {label} slat {k}', (430, 26, 90), bevel=4.0)
            slat.matrix_world = matrix_from(c + v * (k - 2.5) * 86 + a * 57, u, v, a)


# Roof equipment ------------------------------------------------------------------------------------------------
def seat_on_roof(obj, master, sink=4.0):
    """Drop every vertex of an object's lowest layer onto the roof surface (minus sink): base follows the crown."""
    mw = obj.matrix_world
    zs = [(mw @ v.co).z for v in obj.data.vertices]
    floor = min(zs)
    for v in obj.data.vertices:
        world = mw @ v.co
        if world.z < floor + .5:
            world.z = roof_height(master, world.x, world.y) - sink
            v.co = mw.inverted() @ world
    obj.data.update()


def build_roof_equipment(s, p):
    master = bpy.data.objects['Master hull']
    from mathutils import Matrix
    # Taxi sign: plinth and a chamfered box with an amber cell grid on its front and rear faces.
    x, y = p['sign_x_mm'], 0.0
    z0 = max(roof_height(master, x + dx, dy) for dx in (-150, 150) for dy in (-380, 380))
    plinth = block(s, 'Sign plinth', (300, 760, 60), (x, y, z0 + 10), bevel=6.0)
    seat_on_roof(plinth, master)
    block(s, 'Sign box', (230, 700, 170), (x, y, z0 + 40 + 85), bevel=12.0)
    for face in (1, -1):
        block(s, f'Sign bezel {"front" if face > 0 else "rear"}', (10, 640, 120), (x + face * 113, y, z0 + 125), bevel=3.0)
        for row in range(3):
            for col in range(8):
                block(s, f'Sign cell {"F" if face > 0 else "B"}{row}{col}', (8, 66, 30),
                      (x + face * 121, y - 262 + col * 75, z0 + 125 + (row - 1) * 36), bevel=2.0)
    # Roof pod: base plate with service blocks, pedestal, drum with a cyan side band, concentric capped top.
    x = p['pod_x_mm']
    z0 = max(roof_height(master, x + dx, dy) for dx in (-280, 280) for dy in (-350, 350))
    base = block(s, 'Pod base', (560, 700, 50), (x, 0, z0 + 5), bevel=8.0)
    seat_on_roof(base, master)
    for side in (1, -1):
        block(s, f'Pod service block {"L" if side > 0 else "R"}', (200, 120, 90), (x - 40, side * 270, z0 + 30 + 45), bevel=6.0)
    top = p['pod_top_mm']
    h = top - (z0 + 30)
    profile = [(150, 0), (205, 0), (205, .1 * h), (180, .16 * h), (180, .4 * h), (320, .44 * h), (320, .55 * h), (310, .56 * h),
               (310, .66 * h), (320, .67 * h), (320, .8 * h), (290, .84 * h), (290, .87 * h), (210, .9 * h), (210, .93 * h),
               (120, .96 * h), (75, .97 * h), (70, h), (20, h)]
    pod = lathe(s, 'Pod drum', fillet(profile, [0, 4, 6, 8, 10, 12, 3, 2, 2, 3, 10, 6, 4, 6, 4, 6, 4, 6, 0]), segments=96)
    pod.matrix_world = Matrix.Translation((x, 0, z0 + 30))
    band = lathe(s, 'Pod band', [(306, .565 * h), (313, .565 * h), (313, .655 * h), (306, .655 * h)], segments=96)
    band.matrix_world = Matrix.Translation((x, 0, z0 + 30))
    # Antenna behind-left of the pod.
    ax, ay = p['antenna_xy_mm']
    az = roof_height(master, ax, ay)
    mount = block(s, 'Antenna mount', (70, 70, 34), (ax, ay, az + 13), bevel=6.0)
    seat_on_roof(mount, master)
    rod = lathe(s, 'Antenna', [(3, 30), (11, 30), (9, 120), (4, 470), (2, 480)], radius=2, segments=12)
    rod.matrix_world = Matrix.Translation((ax, ay, az))


# Interior ------------------------------------------------------------------------------------------------------
def build_interior(s, p):
    from mathutils import Matrix
    block(s, 'Cabin floor', (3200, 1800, 20), (-500, 0, 570), bevel=4.0)
    for side in (1, -1):
        y = side * 430
        block(s, f'Front seat cushion {"L" if side > 0 else "R"}', (520, 500, 120), (360, y, 700), bevel=30.0)
        back = block(s, f'Front seat back {"L" if side > 0 else "R"}', (120, 500, 650), bevel=30.0)
        back.matrix_world = Matrix.Translation((70, y, 1050)) @ Matrix.Rotation(math.radians(-12), 4, 'Y')
        block(s, f'Front seat base {"L" if side > 0 else "R"}', (360, 380, 60), (360, y, 610), bevel=8.0)
    block(s, 'Rear bench cushion', (520, 1700, 130), (-1000, 0, 705), bevel=30.0)
    back = block(s, 'Rear bench back', (130, 1700, 640), bevel=30.0)
    back.matrix_world = Matrix.Translation((-1290, 0, 1060)) @ Matrix.Rotation(math.radians(-12), 4, 'Y')
    block(s, 'Dash', (340, 1800, 230), (1180, 0, 1040), bevel=40.0)
    wheel = s.sweep('Steering wheel', [(185 * math.cos(a), 185 * math.sin(a), 0) for a in np.linspace(0, 2 * math.pi, 33)[:-1]],
                    17.0, sides=12, cyclic=True)
    tilt = Matrix.Translation((900, 430, 1180)) @ Matrix.Rotation(math.radians(-62), 4, 'Y')
    wheel.matrix_world = tilt
    column = lathe(s, 'Steering column', [(20, -260), (35, -260), (35, -20), (60, -10), (60, 0), (20, 0)], radius=3, segments=24)
    column.matrix_world = tilt


def build(part, p, api):
    s = api.surf
    {'pads': build_pads, 'nacelle_drive': build_drive, 'glass': build_glass, 'inserts': build_inserts,
     'roof_equipment': build_roof_equipment, 'interior': build_interior}[part](s, p)
