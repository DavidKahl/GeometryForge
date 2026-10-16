"""Gated hover taxi. Parts are added gate by gate: master hull (Gate 1), panels (Gate 2), detail (Gate 3)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import detail  # noqa: E402
import master_cage  # noqa: E402
import panels  # noqa: E402


def build_parts(parameters, parts, api):
    s = api.surf
    for part in parts:
        api.begin(part)
        if part == 'master_hull':
            verts, faces, regions, creases = master_cage.body_cage()
            s.master_hull('Master hull', verts, faces, regions=regions, creases=creases, levels=parameters['master_levels'])
        elif part == 'nacelle_master':
            for side, label in (('l', 'L'), ('r', 'R')):
                verts, faces, regions, creases = master_cage.nacelle_cage(side, parameters)
                s.master_hull(f'Nacelle master {label}', verts, faces, regions=regions, creases=creases,
                              levels=parameters['master_levels'])
        elif part in ('body_panels', 'skirt', 'belly', 'nacelle_armor'):
            panels.build(part, parameters, api)
        elif part in ('pads', 'nacelle_drive', 'glass', 'inserts', 'roof_equipment', 'interior'):
            detail.build(part, parameters, api)
        else:
            raise ValueError(f'Unknown part {part}')
