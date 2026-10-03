import importlib
from native import Shapes
from design import dimensions

def build_parts(p,parts,api):
    d=dimensions(p);shapes=Shapes(api,p)
    for part in parts:
        shapes.begin(part)
        if part.startswith('aft_fin_'):module='fins'
        elif part.startswith('canard_'):module='canards'
        elif part.startswith('leg_'):module='legs'
        elif part in ('aft_hull','tank_lower','tank_upper','cargo','nose'):module='hull'
        else:module=part
        importlib.import_module(module).build(p,d,shapes,part)
