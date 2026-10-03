"""Native SOP construction helpers. Every operation remains an editable node."""
import json
import math
import re
import hou

PARTS = {}
ROOT = None


def initialize():
    global ROOT
    PARTS.clear()
    ROOT = hou.node('/obj').createNode('subnet', 'geometryforge')
    ROOT.setUserData('geometryforge_units', 'mm')
    ROOT.setComment('GeometryForge: one coordinate unit = one millimeter')


def safe(name):
    return re.sub('[^a-zA-Z0-9_]', '_', name)


class Axis:
    def __init__(self, part, parm, degrees=False):
        self.part, self.parm, self.degrees = part, parm, degrees

    def __setattr__(self, key, value):
        if key in ('x', 'y', 'z'):
            self.part.transform.parm(self.parm+key).set(math.degrees(value) if self.degrees else value)
        else:
            object.__setattr__(self, key, value)


class Part:
    def __init__(self, name, geo, source, role):
        self.name, self.geo, self.source = name, geo, source
        self.transform = geo.createNode('xform', 'placement')
        self.transform.setInput(0, source)
        self.output = geo.createNode('null', 'OUT')
        self.output.setInput(0, self.transform)
        self.output.setDisplayFlag(True)
        self.output.setRenderFlag(True)
        self.rotation_euler = Axis(self, 'r', True)
        self.geo.setUserData('gf_role', role)
        PARTS[name] = self

    @property
    def location(self):
        return Axis(self, 't')

    @location.setter
    def location(self, value):
        self.transform.parmTuple('t').set(value)

    def __setitem__(self, key, value):
        self.geo.setUserData(key, json.dumps(value))


def new_geo(name):
    return ROOT.createNode('geo', safe(name))


def box(name, dimensions, center, group='Printable'):
    geo = new_geo(name)
    source = geo.createNode('box', 'dimensions')
    source.parmTuple('size').set(dimensions)
    part = Part(name, geo, source, group)
    part.location = center
    return part


def cylinder(name,radius,bottom,height,center=(0,0),group='Construction',count=64):
    geo=new_geo(name)
    source=geo.createNode('tube','cylinder')
    source.setParms({'type':1,'orient':2,'cap':1,'rad1':radius,'rad2':radius,
                     'height':height,'cols':count,'tx':center[0],'ty':center[1],'tz':bottom+height/2})
    return Part(name,geo,source,group)


def collection(obj,role):
    obj.geo.setUserData('gf_role',role)
    obj.geo.setDisplayFlag(role=='Printable')
    return obj


def boolean(obj,tool,operation,label='Boolean'):
    merge=obj.geo.createNode('object_merge',safe(label)+'_operand')
    merge.parm('objpath1').set(tool.output.path())
    node=obj.geo.createNode('boolean',safe(label))
    node.setInput(0,obj.output.input(0))
    node.setInput(1,merge)
    node.parm('booleanop').set({'UNION':0,'INTERSECT':1,'DIFFERENCE':2}[operation])
    obj.output.setInput(0,node)
    collection(tool,'Construction')
    return node


def material(name,color,metallic=0):
    return {'name':name,'color':color,'metallic':metallic}


def finish(obj,mat,rotation=(0,0,0),part=None,filament=1,bodies=1):
    obj['gf_export']={'name':obj.name,'part':part or obj.name,'filament':filament,
                      'expected_bodies':bodies,'print_rotation_deg':rotation,'material':mat}
    obj.geo.setColor(hou.Color(mat['color']))
    collection(obj,'Printable')
    return obj
