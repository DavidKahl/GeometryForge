"""Master hull cages for the gated hover taxi (pure numpy, no bpy).

Vehicle space in mm: X forward, Y left, Z up. Z=0 is the pad-bottom plane, X=0 lies midway between the bumper faces.
Heights along X come from the calibrated side profile (4.108 mm/px); half-widths are interpretations of the primary.

The body cage is a box lattice wrapped onto the hull: i runs along X (stations), j across the roof and belly
(columns T), k up each side (rows). Side faces carry the panel and opening layout that Gate 2 slices, so every
region boundary is a cage edge here. Regions are locked with the master: plan new panels before acceptance.
"""
import numpy as np

# Rows up the side (k): belly corner, skirt bottom, skirt mid, chine, mid flank, belt, sill, window top, shoulder.
ROWS = ('belly_corner', 'skirt_bottom', 'skirt_mid', 'chine', 'mid_flank', 'belt', 'sill', 'window_top', 'shoulder')
NZ = len(ROWS) - 1
# Columns across roof, belly and end caps (t from right -1 to left +1).
T = np.array([-1.0, -0.9, -0.5, -0.18, 0.0, 0.18, 0.5, 0.9, 1.0])
NY = len(T) - 1
# Stations along X; 'r'/'f' entries are offsets from the per-row rear/front ends.
STATIONS = [('r', 0), ('r', 130), -2080, -2020, -1800, -1720, -1420, -1040, -960, -500, -100, 100, 520, 950, 1050,
            1170, 1500, 1760, 1824, 2150, ('f', -400), ('f', -130), ('f', 0)]
NX = len(STATIONS) - 1

# Per-row X of the rear and front ends (the end caps' boundary), then the top and bottom centrelines.
REAR_X = [-2860, -2905, -2912, -2912, -2790, -2700, -2640, -2520, -2390]
FRONT_X = [2860, 2905, 2912, 2912, 2880, 2800, 2780, 2750, 2720]
REAR_TOP, FRONT_TOP, REAR_BOTTOM, FRONT_BOTTOM = -2360, 2770, -2860, 2860


def curve(*keys):
    xs, vs = zip(*keys)
    return lambda x: float(np.interp(x, xs, vs))


# Centreline roof/windshield/hood silhouette, read from the calibrated profile.
Z_TOP = curve((-2950, 1900), (-2500, 1930), (-2420, 1950), (-1500, 1975), (-900, 1990), (0, 1985), (500, 1965),
              (838, 1890), (1002, 1850), (1167, 1740), (1824, 1261),  # windshield: straight centreline, single curvature
              (2645, 916), (2800, 850), (2950, 790))  # hood: straight slope from the cowl
CROWN = curve((-2950, 60), (-2450, 70), (950, 75), (1167, 60), (1760, 25), (1824, 15), (2300, 15), (2950, 12))
RAIL = curve((-2950, 100), (-2450, 110), (950, 120), (1500, 90), (1824, 40), (2300, 40), (2950, 30))
Z_BELT = curve((-2950, 1120), (-2600, 1170), (-2300, 1270), (950, 1280), (1500, 1220), (1824, 1130), (2300, 950),
               (2600, 820), (2950, 720))
Z_CHINE = curve((-2950, 945), (-2700, 945), (-2500, 760), (-2300, 727), (2400, 727), (2700, 640), (2950, 616))
Z_SKIRT = curve((-2950, 522), (-2700, 450), (-2450, 400), (2600, 400), (2950, 385))
Z_BELLY = curve((-2950, 470), (-2700, 380), (-2450, 340), (2600, 340), (2950, 330))
SKIRT_MID = curve((-2950, .6), (-2500, .5), (2950, .5))

Y_SHOULDER = curve((-2950, 800), (-2450, 840), (-2000, 870), (950, 870), (1500, 920), (1824, 980), (2300, 1010),
                   (2600, 980), (2950, 880))
Y_WINDOW = curve((-2950, 880), (-2450, 920), (-2000, 950), (950, 950), (1500, 990), (1824, 1050), (2300, 1070),
                 (2600, 1030), (2950, 900))
Y_BELT = curve((-2950, 1020), (-2450, 1080), (-2000, 1100), (2300, 1100), (2600, 1060), (2950, 920))
Y_FLANK = curve((-2950, 1040), (-2450, 1100), (2300, 1100), (2600, 1070), (2950, 930))
Y_SKIRT = curve((-2950, 1060), (-2450, 1110), (2350, 1110), (2650, 1070), (2950, 940))
Y_BELLY = curve((-2950, 980), (-2450, 1030), (2350, 1030), (2650, 990), (2950, 880))


def row_z(k, x):
    z8 = Z_TOP(x) - CROWN(x)
    z7 = z8 - RAIL(x)
    z5, z3, z1 = Z_BELT(x), Z_CHINE(x), Z_SKIRT(x)
    return [Z_BELLY(x), z1, z1 + SKIRT_MID(x) * (z3 - z1), z3, z3 + .45 * (z5 - z3), z5,
            z5 + min(45.0, .3 * (z7 - z5)), z7, z8][k]


def row_y(k, x):
    return [Y_BELLY, Y_SKIRT, Y_SKIRT, Y_SKIRT, Y_FLANK, Y_BELT, Y_BELT, Y_WINDOW, Y_SHOULDER][k](x)


def station_x(i, rear, front):
    s = STATIONS[i]
    if isinstance(s, tuple):
        return (rear if s[0] == 'r' else front) + s[1]
    return float(s)


def side_point(i, k, sign):
    x = station_x(i, REAR_X[k], FRONT_X[k])
    return np.array([x, sign * row_y(k, x), row_z(k, x)])


def top_point(i, t):
    blend = 1 - t * t
    rear = REAR_X[NZ] + (REAR_TOP - REAR_X[NZ]) * blend
    front = FRONT_X[NZ] + (FRONT_TOP - FRONT_X[NZ]) * blend
    x = station_x(i, rear, front)
    z8 = Z_TOP(x) - CROWN(x)
    return np.array([x, t * Y_SHOULDER(x), z8 + CROWN(x) * blend])


def bottom_point(i, t):
    blend = 1 - t * t
    rear = REAR_X[0] + (REAR_BOTTOM - REAR_X[0]) * blend
    front = FRONT_X[0] + (FRONT_BOTTOM - FRONT_X[0]) * blend
    x = station_x(i, rear, front)
    return np.array([x, t * Y_BELLY(x), Z_BELLY(x) - 15.0 * blend])


def boundary_point(i, j, k):
    if j == 0:
        return side_point(i, k, -1)
    if j == NY:
        return side_point(i, k, 1)
    if k == NZ:
        return top_point(i, T[j])
    return bottom_point(i, T[j])


def cap_point(i, j, k, bulge):
    """Coons patch over the end-cap boundary, pushed outward by a small crown."""
    s, r = (T[j] + 1) / 2, k / NZ
    B, Tp = boundary_point(i, j, 0), boundary_point(i, j, NZ)
    L, R = boundary_point(i, 0, k), boundary_point(i, NY, k)
    P00, P10 = boundary_point(i, 0, 0), boundary_point(i, NY, 0)
    P01, P11 = boundary_point(i, 0, NZ), boundary_point(i, NY, NZ)
    p = (1 - r) * B + r * Tp + (1 - s) * L + s * R - ((1 - s) * (1 - r) * P00 + s * (1 - r) * P10 + (1 - s) * r * P01 + s * r * P11)
    p[0] += bulge * np.sin(np.pi * s) * np.sin(np.pi * r)
    return p


def lattice():
    """Box-surface lattice: vertex index per (i, j, k) and quads with outward winding."""
    index, verts = {}, []
    for i in range(NX + 1):
        for j in range(NY + 1):
            for k in range(NZ + 1):
                if i in (0, NX) or j in (0, NY) or k in (0, NZ):
                    index[i, j, k] = len(verts)
                    verts.append((i, j, k))
    faces = []  # (vertex ids, face key)
    def quad(a, b, c, d, outward, key):
        ids = [index[a], index[b], index[c], index[d]]
        p = [np.array(v, float) for v in (a, b, c, d)]
        if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), outward) < 0:
            ids.reverse()
        faces.append((ids, key))
    for i in range(NX):
        for k in range(NZ):
            quad((i, 0, k), (i + 1, 0, k), (i + 1, 0, k + 1), (i, 0, k + 1), (0, -1, 0), ('side', 'r', i, k))
            quad((i, NY, k), (i + 1, NY, k), (i + 1, NY, k + 1), (i, NY, k + 1), (0, 1, 0), ('side', 'l', i, k))
        for j in range(NY):
            quad((i, j, NZ), (i + 1, j, NZ), (i + 1, j + 1, NZ), (i, j + 1, NZ), (0, 0, 1), ('top', i, j))
            quad((i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0), (0, 0, -1), ('bottom', i, j))
    for j in range(NY):
        for k in range(NZ):
            quad((0, j, k), (0, j + 1, k), (0, j + 1, k + 1), (0, j, k + 1), (-1, 0, 0), ('rear', j, k))
            quad((NX, j, k), (NX, j + 1, k), (NX, j + 1, k + 1), (NX, j, k + 1), (1, 0, 0), ('front', j, k))
    return index, verts, faces


SKIRT_PLATES = [(0, 6), (6, 9), (9, 12), (12, 16), (16, NX)]
LOWER_PANELS = [('body_rear', 0, 8), ('door_rear', 8, 11), ('door_front', 11, 14)]
# Openings in the greenhouse band (row 6: sill to window top), with pillar columns between them.
GREENHOUSE_OPENINGS = {'qwin': (3,), 'win2': (5, 6), 'win3': (8, 9), 'win4': (11, 12)}
PAD_BAYS = {'pad_rr': (range(2, 6), 1), 'pad_rl': (range(2, 6), NY - 2), 'pad_fr': (range(15, 18), 1), 'pad_fl': (range(15, 18), NY - 2)}


def region(key):
    kind = key[0]
    if kind == 'side':
        _, s, i, k = key
        if k < 3:
            return f'skirt_{s}{next(n for n, (a, b) in enumerate(SKIRT_PLATES, 1) if a <= i < b)}'
        if i >= 14:
            return f'fender_{s}'
        if k >= 5:
            if k == 6:
                for name, columns in GREENHOUSE_OPENINGS.items():
                    if i in columns:
                        return f'{name}_{s}'
            return f'greenhouse_{s}'
        return f'{next(n for n, a, b in LOWER_PANELS if a <= i < b)}_{s}'
    if kind == 'top':
        _, i, j = key
        if i >= 18:
            return 'hood'
        if 14 <= i < 17 and 1 <= j < NY - 1:
            return 'windshield'
        return 'roof'
    if kind == 'bottom':
        _, i, j = key
        for name, (stations, column) in PAD_BAYS.items():
            if i in stations and j == column:
                return name
        return 'belly'
    if kind == 'front':
        _, j, k = key
        if k < 3:
            return 'bumper_front'
        if k == 4 and j in (1, NY - 2):
            return 'headlamp_r' if j == 1 else 'headlamp_l'
        return 'nose'
    _, j, k = key
    if k < 4:
        if k == 2 and j in (1, NY - 2):
            return 'tail_r' if j == 1 else 'tail_l'
        return 'bumper_rear'
    if k == 6 and j in (1, NY - 2):  # nacelle sockets face rearward, toward the nacelle hubs (drive amendment)
        return 'socket_r' if j == 1 else 'socket_l'
    return 'rear_panel'


def body_cage():
    """Vertices (mm), quads, regions {name: [face ids]} and creases [(a, b, weight)]."""
    index, keys, faces = lattice()
    verts = []
    for i, j, k in keys:
        if i in (0, NX) and 0 < j < NY and 0 < k < NZ:
            verts.append(cap_point(i, j, k, -40.0 if i == 0 else 30.0))
        else:
            verts.append(boundary_point(i, j, k))
    regions = {}
    for n, (_, key) in enumerate(faces):
        regions.setdefault(region(key), []).append(n)
    creases = []
    def crease_row(k, weight, stations=range(NX)):
        for s in (0, NY):
            for i in stations:
                creases.append((index[i, s, k], index[i + 1, s, k], weight))
    # Facets of the wedge are held by creases, not support loops.
    crease_row(3, 1.0)   # chine: chrome skirt shelf to painted body
    crease_row(5, .8)    # beltline: painted body turns in to the glass band
    crease_row(NZ, .65)  # shoulder: roof rail, A-pillar line and hood edge
    for j in range(NY):
        creases.append((index[18, j, NZ], index[18, j + 1, NZ], .8))  # cowl: windshield to hood
        creases.append((index[14, j, NZ], index[14, j + 1, NZ], .5))  # windshield header
    for i, k in ((NX, 3), (0, 4)):  # bumper tops across the end caps
        for j in range(NY):
            creases.append((index[i, j, k], index[i, j + 1, k], .8))
    for i in (0, NX):  # end-cap rims hold the bumper faces and nose
        for j in range(NY):
            for k in (0, NZ):
                creases.append((index[i, j, k], index[i, j + 1, k], .8))
        for k in range(NZ):
            for j in (0, NY):
                creases.append((index[i, j, k], index[i, j, k + 1], .8))
    seen = {}
    for a, b, w in creases:  # one weight per edge: the strongest wins
        key = tuple(sorted((a, b)))
        seen[key] = max(w, seen.get(key, 0))
    creases = [(a, b, w) for (a, b), w in seen.items()]
    return np.array(verts), [f for f, _ in faces], regions, creases


def octagon(width, height, chamfer):
    a, b, c = width / 2, height / 2, chamfer
    return [(a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b), (a - c, -b), (a, -b + c)]


# Nacelle stations: x, scale of the armour octagon. Rear exhaust face at -3886 mm (profile), nose face toward the body.
NACELLE_RINGS = [(-3886, 1.0), (-3500, 1.0), (-2930, 1.0), (-2820, .86), (-2720, .64)]


def nacelle_cage(side, p):
    """Closed chamfered-octagon nacelle with an exhaust opening (rear) and a hub opening (front)."""
    sign = 1 if side == 'l' else -1
    yc, zc = sign * p['nacelle_y_mm'], p['nacelle_z_mm']
    base = octagon(p['nacelle_width_mm'], p['nacelle_height_mm'], p['nacelle_chamfer_mm'])
    rings = [[(x, yc + s * u, zc + s * v) for u, v in base] for x, s in NACELLE_RINGS]
    rings.insert(0, [(NACELLE_RINGS[0][0], yc + .72 * u, zc + .72 * v) for u, v in base])     # exhaust rim
    rings.append([(NACELLE_RINGS[-1][0], yc + .64 * .55 * u, zc + .64 * .55 * v) for u, v in base])  # hub rim
    verts = [v for ring in rings for v in ring]
    faces, regions, creases = [], {}, []
    def add(face, name):
        regions.setdefault(name, []).append(len(faces))
        faces.append(face)
    n = len(rings)
    for r in range(n - 1):
        for q in range(8):
            a, b = r * 8 + q, r * 8 + (q + 1) % 8
            add([a, b, b + 8, a + 8], f'nacelle_armor_{side}')
    add([3, 2, 1, 0], f'exhaust_{side}'), add([7, 4, 3, 0], f'exhaust_{side}'), add([7, 6, 5, 4], f'exhaust_{side}')
    last = (n - 1) * 8
    add([last, last + 1, last + 2, last + 3], f'hub_{side}')
    add([last, last + 3, last + 4, last + 7], f'hub_{side}')
    add([last + 4, last + 5, last + 6, last + 7], f'hub_{side}')
    if signed_volume(np.array(verts, float), faces) < 0:
        faces = [f[::-1] for f in faces]
    for r in range(1, n - 1):  # longitudinal chamfer breaks
        if r < n - 2:
            for q in range(8):
                creases.append((r * 8 + q, (r + 1) * 8 + q, .9))
    for r in (1, n - 2):  # face rims
        for q in range(8):
            creases.append((r * 8 + q, r * 8 + (q + 1) % 8, .85))
    return np.array(verts, float), faces, regions, creases


def check_closed(verts, faces):
    """Every edge shared by exactly two faces in opposite directions (host test)."""
    from collections import Counter
    directed = Counter()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            directed[a, b] += 1
    bad = [e for e, c in directed.items() if c != 1 or directed.get((e[1], e[0]), 0) != 1]
    return not bad, bad[:5]


def signed_volume(verts, faces):
    total = 0.0
    for f in faces:
        for a, b in zip(f[1:-1], f[2:]):
            total += np.dot(verts[f[0]], np.cross(verts[a], verts[b])) / 6
    return total
