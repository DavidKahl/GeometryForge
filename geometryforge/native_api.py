"""Small native modeling vocabulary. Operations stay editable in each application."""
import math

class Blender:
    def begin(self, part):
        import bpy
        self.part = part
        for obj in list(bpy.data.objects):
            if obj.get('gf_owner') == part:
                bpy.data.objects.remove(obj, do_unlink=True)

    def mark(self, obj):
        obj['gf_owner'] = self.part
        return obj

    def box(self, name, size, center):
        from .blender_scene import box
        return self.mark(box(self.part+'_'+name, size, center, 'Construction'))

    def cylinder(self, name, radius, bottom, height, center=(0,0), top_radius=None):
        import bpy
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=radius, radius2=radius if top_radius is None else top_radius, depth=height, location=(*center,bottom+height/2))
        obj = bpy.context.object
        obj.name = self.part+'_'+name
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        bpy.data.collections['Construction'].objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
        return self.mark(obj)

    def boolean(self, obj, tool, operation):
        from .blender_scene import boolean
        boolean(obj, tool, operation)
        return obj

    def rotate(self, obj, degrees):
        obj.rotation_euler = [math.radians(x) for x in degrees]

    def finish(self, obj, bodies=1, rotation=(0,0,0)):
        import bpy
        from .blender_scene import printable
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        bpy.data.collections['Printable'].objects.link(obj)
        obj.hide_render = False
        obj.hide_set(False)
        printable(obj, part=self.part, rotation=rotation)
        obj['gf_expected_bodies'] = bodies
        obj.color = (0.32,0.65,0.61,1)
        return obj

class Houdini:
    def begin(self, part):
        from . import houdini_scene as s
        self.part = part
        for node in list(s.ROOT.children()):
            if node.userData('gf_owner') == part:
                node.destroy()

    def mark(self, obj):
        obj.geo.setUserData('gf_owner', self.part)
        obj.geo.setDisplayFlag(False)
        return obj

    def box(self, name, size, center):
        from .houdini_scene import box
        return self.mark(box(self.part+'_'+name, size, center, 'Construction'))

    def cylinder(self, name, radius, bottom, height, center=(0,0), top_radius=None):
        from .houdini_scene import cylinder
        obj = cylinder(self.part+'_'+name, radius, bottom, height, center)
        if top_radius is not None:
            obj.source.parm('rad1').set(top_radius)
        return self.mark(obj)

    def boolean(self, obj, tool, operation):
        from .houdini_scene import boolean
        boolean(obj, tool, operation)
        return obj

    def rotate(self, obj, degrees):
        obj.transform.parmTuple('r').set(degrees)

    def finish(self, obj, bodies=1, rotation=(0,0,0)):
        from .houdini_scene import finish, material
        finish(obj, material('GeometryForge',(.32,.65,.61)), rotation=rotation, part=self.part, bodies=bodies)
        obj.geo.layoutChildren()
        return obj
