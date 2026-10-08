"""Replace only the saved insert_flux group; retain all other assembly objects."""
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'models'))
from flux_insert import build_flux


def revise():
    selected=[o for o in bpy.data.collections['Printable'].all_objects if o.get('gf_part',o.name)=='insert_flux']
    black=next(o for o in selected if o.get('gf_filament')==1).data.materials[0]
    translucent=next(o for o in selected if o.get('gf_filament')==2).data.materials[0]
    # Retain historical construction tools: they are nonprinting and may be shared.
    for o in selected:
        bpy.data.objects.remove(o,do_unlink=True)
    for obj in build_flux(black,translucent):
        weld=obj.modifiers.new('Merge Boolean seam vertices (0.00005 mm)','WELD')
        weld.merge_threshold=.00005
