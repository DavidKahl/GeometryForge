"""Flat, through-material Flux insert shared by builds and saved-scene revisions."""
import math
import bpy
import spec as S
from geometry import cylinder, fuse, cut, hole, radial_box, finish, prism


def seat(xy, name='Flush countersink', clearance=0):
    # Nominal seat: diameter 6.4 at face, 3.4 at depth 1.6 mm.
    count = 64
    rings = [(1.7-clearance, 53.4), (3.2-clearance, 55), (3.2-clearance, 55.1)]
    vertices = [(xy[0]+r*math.cos(i*2*math.pi/count), xy[1]+r*math.sin(i*2*math.pi/count), z)
                for r,z in rings for i in range(count)]
    faces = [tuple(reversed(range(count))), tuple(range(2*count,3*count))]
    faces += [(j*count+i,j*count+(i+1)%count,(j+1)*count+(i+1)%count,(j+1)*count+i)
              for j in range(2) for i in range(count)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.data.collections['Construction'].objects.link(obj)
    return obj


def blank(name='Flux blank', group='Construction'):
    obj=cylinder(name,S.INSERT_RADIUS,52,3,group=group,count=128)
    for angle in S.INSERT_ANGLES:
        a=math.radians(angle); xy=(56*math.cos(a),56*math.sin(a))
        hole(obj,xy,51,5)
        cut(obj,seat(xy))
    return obj


def build_flux(black, translucent):
    base=blank('insert_flux','Printable')
    motif=cylinder('flux_Y_inlay',7,52,3,group='Printable')
    for angle in (30,150,270):
        fuse(motif,radial_box('Flux arm',23,angle,42,7,52,3))
        a=math.radians(angle)
        fuse(motif,cylinder('Flux terminal pod',7,52,3,(43*math.cos(a),43*math.sin(a))))
    cut(base,motif,'Exact shared through-inlay boundary')
    # cut() moves its operand into Construction: restore the material body.
    from geometry import collection
    collection(motif,'Printable')
    motif.hide_set(False)
    motif.hide_render=False
    for obj, mat, slot in ((base,black,1),(motif,translucent,2)):
        finish(obj,mat,rotation=(180,0,0),part='insert_flux',filament=slot,bodies=2)
        obj['gf_expected_bbox_mm']=(130,130,3)
    return base,motif
