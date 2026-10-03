"""Blender-only modeling helpers. Import inside Blender, never host Python."""
import bpy
from mathutils import Vector


def initialize():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for name in ("Printable", "Construction", "Presentation"):
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene["geometryforge_units"] = "mm"


def box(name, dimensions, center, collection="Printable"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    bpy.data.collections[collection].objects.link(obj)
    if collection == "Construction":
        obj.hide_render = True
        obj.hide_set(True)
        obj.display_type = "WIRE"
    return obj


def boolean(obj, tool, operation="DIFFERENCE", name="Parametric cut"):
    modifier = obj.modifiers.new(name, "BOOLEAN")
    modifier.operation = operation
    modifier.solver = "EXACT"
    modifier.object = tool
    return modifier


def printable(obj, *, part=None, expected=None, rotation=(0, 0, 0), filament=1):
    obj["gf_part"] = part or obj.name
    obj["gf_print_rotation_deg"] = rotation
    obj["gf_filament"] = filament
    obj["gf_expected_bodies"] = 1
    if expected:
        obj["gf_expected_bbox_mm"] = expected
    return obj


def presentation():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.world.color = (0.22, 0.22, 0.22)
    material = bpy.data.materials.new("Enclosure teal")
    material.diffuse_color = (0.045, 0.42, 0.48, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = material.diffuse_color
    shader.inputs["Roughness"].default_value = 0.42
    for obj in bpy.data.collections["Printable"].objects:
        obj.data.materials.append(material)
    collection = bpy.data.collections["Presentation"]
    light_data = bpy.data.lights.new("Softbox", "AREA")
    light_data.energy = 150000
    light_data.shape = "DISK"
    light_data.size = 120
    light = bpy.data.objects.new("Softbox", light_data)
    collection.objects.link(light)
    light.location = (20, -70, 130)
    light.rotation_euler = (Vector((15, 0, 10)) - light.location).to_track_quat('-Z', 'Y').to_euler()
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    collection.objects.link(camera)
    camera.location = (130, -170, 160)
    camera.rotation_euler = (Vector((20, 15, 8)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 170
    scene.camera = camera
