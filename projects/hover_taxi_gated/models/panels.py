"""Gate 2 panels: every exterior panel is sliced from a master region and shrinkwrapped back onto it.

Openings become recessed pockets (flush rim, filleted return, drafted wall, open seat) and export interface
rings: '_interface_<opening>' at the rim and '_interface_<opening>_seat' at the seat that Gate 3 fills.
"""
import bpy

SIDES = ('r', 'l')
WINDOWS = ('qwin', 'win2', 'win3', 'win4')


def openings(region, side):
    if region == 'greenhouse':
        return [f'{w}_{side}' for w in WINDOWS]
    return []


def panel_list(part):
    if part == 'body_panels':
        items = [('roof', 'Roof', ['windshield']), ('hood', 'Hood', []),
                 ('nose', 'Nose', ['headlamp_r', 'headlamp_l']), ('rear_panel', 'Rear panel', ['socket_r', 'socket_l'])]
        for s in SIDES:
            for region, label in (('fender', 'Fender'), ('door_front', 'Front door'), ('door_rear', 'Rear door'),
                                  ('body_rear', 'Rear body'), ('greenhouse', 'Greenhouse')):
                items.append((f'{region}_{s}', f'{label} {s.upper()}', openings(region, s)))
        return 'Master hull', 'body', items
    if part == 'skirt':
        items = [('bumper_front', 'Front bumper', []), ('bumper_rear', 'Rear bumper', ['tail_r', 'tail_l'])]
        items += [(f'skirt_{s}{n}', f'Skirt plate {s.upper()}{n}', []) for s in SIDES for n in range(1, 6)]
        return 'Master hull', 'skirt', items
    if part == 'belly':
        return 'Master hull', 'belly', [('belly', 'Belly', ['pad_fr', 'pad_fl', 'pad_rr', 'pad_rl'])]
    raise ValueError(part)


def pocket(opening, p):
    """Depth, draft, fillet for an opening, from parameters.json pocket_specs keyed by opening family."""
    family = opening.split('_')[0]  # headlamp_r, pad_fr, windshield ...
    family = 'window' if family in WINDOWS else family
    spec = p['pocket_specs'][family]
    return spec['depth_mm'], spec['draft_deg'], spec['fillet_mm'], spec.get('corner_mm')


def build_panel(api, guide, region, name, holes, style, p):
    s = api.surf
    obj = s.slice_panel(guide, region, openings=holes, name=name)
    st = p['panel_styles'][style]
    s.inset_panel_perimeter(obj, st['inset_mm'], gap=st['gap_mm'])
    s.tighten_panel_corners(obj, p['panel_corner_mm'])  # straight panel outlines, so seams stay even to their ends
    for hole in holes:  # rectangular openings keep their corners; round bays and octagons stay as sliced
        corner = pocket(hole, p)[3]
        if corner:
            s.tighten_opening(obj, hole, corner)
    s.build_guide_mesh_stack(obj, guide, thickness=st['thickness_mm'], bevel_width=st['bevel_mm'],
                             subsurf_levels=p['panel_levels'])
    for hole in holes:
        depth, draft, fillet, _ = pocket(hole, p)
        s.recessed_pocket_extrude(obj, hole, depth, draft, fillet)
        s.extract_interface_ring(obj, hole, name=f'_interface_{hole}')
        s.extract_interface_ring(obj, f'{hole}_floor', name=f'_interface_{hole}_seat')
    return obj


def build(part, p, api):
    if part == 'nacelle_armor':
        for side in SIDES:
            guide = bpy.data.objects[f'Nacelle master {side.upper()}']
            build_panel(api, guide, f'nacelle_armor_{side}', f'Nacelle armor {side.upper()}',
                        [f'exhaust_{side}', f'hub_{side}'], 'nacelle', p)
        return
    guide_name, style, items = panel_list(part)
    guide = bpy.data.objects[guide_name]
    for region, name, holes in items:
        build_panel(api, guide, region, name, holes, style, p)
