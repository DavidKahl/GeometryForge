"""Viewport driver, staged part reveal and look-dev studio for live builds. Blender GUI only."""
import fnmatch
import hashlib
import math

import bpy
import numpy
from mathutils import Euler, Vector

PRESENTATION = 'GF_Live_Presentation'


def viewport():
    """Largest 3D viewport of the first window; looked up every tick because file loads replace screens."""
    best = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D' and (best is None or area.width*area.height > best[1].width*best[1].height):
                best = (window, area)
    if best is None:
        return None
    window, area = best
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return window, area, region, area.spaces.active


def rotation(azimuth, elevation):
    return Euler((math.radians(90-elevation), 0, math.radians(azimuth+90))).to_quaternion()


def apply(v):
    found = viewport()
    if not found:
        return
    *_, space = found
    r3d = space.region_3d
    r3d.view_perspective = 'PERSP'
    r3d.view_location = Vector(v['center'])
    r3d.view_rotation = rotation(v['azimuth'], v['elevation'])
    r3d.view_distance = v['distance']
    found[1].tag_redraw()


def current(fallback):
    found = viewport()
    if not found:
        return dict(fallback)
    r3d = found[3].region_3d
    back = r3d.view_rotation @ Vector((0, 0, 1))
    azimuth = math.degrees(math.atan2(back.y, back.x))
    return {'center': list(r3d.view_location), 'distance': r3d.view_distance,
            'azimuth': fallback['azimuth'] + ((azimuth-fallback['azimuth']+180) % 360 - 180),
            'elevation': math.degrees(math.asin(max(-1, min(1, back.z))))}


def redraw():
    found = viewport()
    if not found:
        return
    window, area, region, _ = found
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def clip(span):
    """Millimetre scenes are thousands of units across; the default 1000-unit clip range cuts them off."""
    found = viewport()
    if found:
        found[3].clip_start, found[3].clip_end = max(span/2000, .1), span*60


def recording_layout(span, studio):
    """Clean recording look: clay matcap with cavity, no gizmos or helper overlays."""
    found = viewport()
    if not found:
        return
    window, area, region, space = found
    clip(span)
    space.lens = 50
    space.show_gizmo = False
    # Region visibility updates need an active window; timers have none, and Blender 5.2 crashes without it.
    with bpy.context.temp_override(window=window, area=area, region=region):
        space.show_region_toolbar = False
        space.show_region_ui = False
    overlay = space.overlay
    for name in ('show_floor', 'show_axis_x', 'show_axis_y', 'show_axis_z', 'show_cursor', 'show_text', 'show_stats',
                 'show_extras', 'show_relationship_lines', 'show_object_origins', 'show_bones'):
        setattr(overlay, name, False)
    shading = space.shading
    shading.type = 'SOLID'
    shading.light = 'MATCAP'
    try:
        shading.studio_light = 'clay_studio.exr'
    except TypeError:
        pass
    shading.color_type = 'SINGLE'
    shading.single_color = studio.get('clay', (0.62, 0.6, 0.57))
    shading.show_cavity = True
    shading.cavity_type = 'BOTH'
    shading.background_type = 'VIEWPORT'
    shading.background_color = studio.get('background', (0.71, 0.66, 0.6))
    for obj in bpy.context.view_layer.objects.selected:
        obj.select_set(False)


def owned(part):
    return [o for o in bpy.data.objects if o.get('gf_owner') == part]


def presentable(objects):
    """What a viewer should see of a part: its visible objects, else its hidden design meshes
    (design routes hide every output), else its master guide surface (Gate 1)."""
    visible = [o for o in objects if o.visible_get()]
    if visible:
        return visible
    meshes = [o for o in objects if o.type == 'MESH']
    return ([o for o in meshes if o.get('gf_role') in ('design', 'high_detail')]
            or [o for o in meshes if o.get('gf_role') == 'guide'])


def retire_guides(ledger):
    """Once real panels show, the master guide they were sliced from would only show through the seams."""
    for name in ledger:
        obj = bpy.data.objects.get(name)
        if obj is not None and obj.get('gf_role') == 'guide':
            obj.hide_set(True)


def restore_visibility(ledger):
    """Exact pre-reveal visibility, applied before the evidence scene is saved."""
    for name, hidden in ledger.items():
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.hide_set(hidden)
    ledger.clear()


def present_all(parts):
    """Presentation file only: show every part's presentable objects, guides only if nothing else exists."""
    shown = [o for part in parts for o in presentable(owned(part))]
    solid = any(o.get('gf_role') != 'guide' for o in shown)
    for obj in shown:
        obj.hide_set(solid and obj.get('gf_role') == 'guide')


def bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box)
    if not points:
        return None
    return ([min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)])


def fingerprint(objects):
    """Cheap edit detector for pause/resume: transforms, base mesh coordinates and modifier switches."""
    digest = hashlib.sha256()
    for obj in sorted(objects, key=lambda o: o.name):
        digest.update(obj.name.encode())
        digest.update(repr([list(r) for r in obj.matrix_world]).encode())
        if obj.type == 'MESH':
            coords = numpy.empty(len(obj.data.vertices)*3, dtype=numpy.float32)
            obj.data.vertices.foreach_get('co', coords)
            digest.update(repr(len(obj.data.polygons)).encode())
            digest.update(coords.tobytes())
        digest.update(repr([(m.name, m.type, m.show_viewport) for m in obj.modifiers]).encode())
    return digest.hexdigest()


class Reveal:
    """Hide a built part, then bring it back as base mesh and one modifier level per stage.

    Modifier switches are restored when the part's reveal ends; the part then stays visible so the asset
    accumulates, and `ledger` keeps each object's original visibility for restore_visibility."""

    def __init__(self, part, objects, ledger):
        self.objects = objects
        for obj in owned(part):
            ledger.setdefault(obj.name, not obj.visible_get())
        self.cutters = [o for o in owned(part) if not o.visible_get() and o.type == 'MESH' and o not in objects
                        and any(c.name == 'Construction' for c in o.users_collection)]
        self.modifiers = {o.name: [(m, m.show_viewport) for m in o.modifiers] for o in objects}
        self.stages = max((len(v) for v in self.modifiers.values()), default=0)
        self.ledger = ledger
        for obj in objects:
            obj.hide_set(True)

    def show(self):
        if any(o.get('gf_role') != 'guide' for o in self.objects):
            retire_guides(self.ledger)
        for obj in self.objects:
            for modifier, _ in self.modifiers[obj.name]:
                modifier.show_viewport = False
            obj.hide_set(False)
        for cutter in self.cutters:
            cutter.hide_set(False)

    def stage(self, n, last, limit):
        # With more modifiers than stage beats, the final beat enables the rest of the stack.
        upto = self.stages if last else n+1
        for obj in self.objects:
            for i, (modifier, original) in enumerate(self.modifiers[obj.name]):
                if i < upto:
                    modifier.show_viewport = original
        if last:
            for cutter in self.cutters:
                cutter.hide_set(True)

    def restore(self):
        for obj in self.objects:
            for modifier, original in self.modifiers[obj.name]:
                modifier.show_viewport = original
            obj.hide_set(False)
        for cutter in self.cutters:
            cutter.hide_set(True)


def classify(material, mapping):
    if material.name.startswith('GF live ') and material.name[8:] in PALETTE:
        return material.name[8:]
    for pattern, stage in mapping.items():
        if fnmatch.fnmatchcase(material.name, pattern):
            return stage
    lowered = material.name.lower()
    if 'glass' in lowered or 'lens' in lowered:
        return 'glass'
    shader = material.node_tree.nodes.get('Principled BSDF') if material.use_nodes and material.node_tree else None
    if shader:
        def value(name, default=0.0):
            socket = shader.inputs.get(name)
            return socket.default_value if socket is not None and not socket.is_linked else default
        strength = value('Emission Strength')
        colour = shader.inputs.get('Emission Color')
        if strength and colour is not None and (colour.is_linked or max(colour.default_value[:3]) > 0):
            return 'emissive'
        if value('Transmission Weight') > .5:
            return 'glass'
        if value('Metallic') > .5:
            return 'metal'
        base = shader.inputs.get('Base Color')
        if base is not None and not base.is_linked and sum(base.default_value[:3])/3 < .08:
            return 'dark'
    return 'armor'


PALETTE = {'armor': {'color': (0.75, 0.3, 0.04), 'roughness': .32},
           'dark': {'color': (0.018, 0.018, 0.02), 'roughness': .45},
           'inserts': {'color': (0.045, 0.045, 0.05), 'roughness': .62},
           'metal': {'color': (0.62, 0.62, 0.64), 'roughness': .28, 'metallic': 1.0},
           'glass': {'color': (0.02, 0.025, 0.03), 'roughness': .03, 'transmission': 1.0},
           'emissive': {'color': (1.0, 0.45, 0.1), 'roughness': .4, 'emission': 6.0}}


def palette_material(stage, studio):
    spec = {**PALETTE[stage], **studio.get('palette', {}).get(stage, {})}
    name = f'GF live {stage}'
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*spec['color'], 1)
    shader.inputs['Roughness'].default_value = spec['roughness']
    shader.inputs['Metallic'].default_value = spec.get('metallic', 0.0)
    shader.inputs['Transmission Weight'].default_value = spec.get('transmission', 0.0)
    if spec.get('emission'):
        shader.inputs['Emission Color'].default_value = (*spec['color'], 1)
        shader.inputs['Emission Strength'].default_value = spec['emission']
    material.diffuse_color = (*spec['color'], 1)
    return material


def assigned_stage(obj, lookdev):
    for pattern, stage in lookdev['objects'].items():
        if fnmatch.fnmatchcase(obj.name, pattern):
            return stage
    return lookdev['parts'].get(obj.get('gf_owner'))


class LookDev:
    """Presentation-only changes after the evidence scene is written: clay swap, studio, lights, material groups."""

    def __init__(self, asset_bounds, config):
        self.low, self.high = (Vector(b) for b in asset_bounds)
        self.span = max((self.high-self.low).length, 1)
        self.centre = (self.low+self.high)/2
        self.studio = config['studio']
        self.clay = bpy.data.materials.get('GF_Clay') or bpy.data.materials.new('GF_Clay')
        self.clay.diffuse_color = (*self.studio.get('clay', (0.62, 0.6, 0.57)), 1)
        self.clay.use_nodes = True
        shader = self.clay.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = self.clay.diffuse_color
        shader.inputs['Roughness'].default_value = .55
        self.groups = {}
        for obj in bpy.data.objects:
            if obj.get('gf_owner') is None or not obj.visible_get() or not hasattr(obj.data, 'materials'):
                continue
            obj.hide_render = False
            stage = assigned_stage(obj, config['lookdev'])
            if stage:
                material = palette_material(stage, self.studio)
                if not obj.material_slots:
                    obj.data.materials.append(material)
                for slot in obj.material_slots:
                    slot.material = material
            if not obj.material_slots:
                obj.data.materials.append(self.clay)
            for slot in obj.material_slots:
                if slot.material and slot.material != self.clay:
                    stage = classify(slot.material, config['lookdev']['materials'])
                    self.groups.setdefault(stage, []).append((slot, slot.material))
                    slot.material = self.clay
        self.collection = bpy.data.collections.get(PRESENTATION) or bpy.data.collections.new(PRESENTATION)
        if self.collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(self.collection)
        scene = bpy.context.scene
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except TypeError:
            scene.render.engine = 'BLENDER_EEVEE'
        scene.view_settings.view_transform = 'AgX'
        self.world()
        found = viewport()
        if found:
            found[3].shading.type = 'RENDERED'

    def world(self):
        """Warm backdrop for camera rays, low neutral fill for lighting: no HDRI reflections."""
        world = bpy.data.worlds.get('GF_Studio') or bpy.data.worlds.new('GF_Studio')
        world.use_nodes = True
        nodes, links = world.node_tree.nodes, world.node_tree.links
        nodes.clear()
        out = nodes.new('ShaderNodeOutputWorld')
        mix = nodes.new('ShaderNodeMixShader')
        path = nodes.new('ShaderNodeLightPath')
        ambient = nodes.new('ShaderNodeBackground')
        backdrop = nodes.new('ShaderNodeBackground')
        ambient.inputs['Color'].default_value = (*self.studio.get('ambient', (0.22, 0.2, 0.18)), 1)
        backdrop.inputs['Color'].default_value = (*self.studio.get('background', (0.71, 0.66, 0.6)), 1)
        links.new(path.outputs['Is Camera Ray'], mix.inputs['Fac'])
        links.new(ambient.outputs['Background'], mix.inputs[1])
        links.new(backdrop.outputs['Background'], mix.inputs[2])
        links.new(mix.outputs['Shader'], out.inputs['Surface'])
        bpy.context.scene.world = world

    def link(self, obj):
        self.collection.objects.link(obj)
        return obj

    def light(self, name, azimuth, elevation, energy, width, height):
        lamp = bpy.data.lights.new(f'GF {name}', 'AREA')
        lamp.shape = 'RECTANGLE'
        lamp.energy = self.span*self.span*energy
        lamp.size, lamp.size_y = self.span*width, self.span*height
        a, e = math.radians(azimuth), math.radians(elevation)
        obj = self.link(bpy.data.objects.new(lamp.name, lamp))
        obj.location = self.centre + 1.6*self.span*Vector((math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e)))
        obj.rotation_euler = (self.centre-obj.location).to_track_quat('-Z', 'Y').to_euler()

    def floor(self):
        """Seamless cyclorama bowl: flat floor curving up into a wall all round, so every orbit angle sees backdrop."""
        mesh = bpy.data.meshes.new('GF studio cyclorama')
        flat, bend, wall, segments = 3*self.span, 2*self.span, 6*self.span, 96
        profile = [(0, 0)] + [(flat*k/4, 0) for k in range(1, 5)]
        profile += [(flat+bend*math.sin(a), bend*(1-math.cos(a))) for a in (math.pi/2*k/8 for k in range(1, 9))]
        profile += [(flat+bend, bend+wall*k/3) for k in range(1, 4)]
        verts = [(0, 0, 0)]
        for i in range(segments):
            a = 2*math.pi*i/segments
            verts.extend((r*math.cos(a), r*math.sin(a), z) for r, z in profile[1:])
        rings = len(profile)-1
        faces = []
        for i in range(segments):
            j = (i+1) % segments
            faces.append((0, 1+i*rings, 1+j*rings))
            for k in range(rings-1):
                faces.append((1+i*rings+k, 1+i*rings+k+1, 1+j*rings+k+1, 1+j*rings+k))
        mesh.from_pydata(verts, [], faces)
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        material = bpy.data.materials.new('GF studio cyclorama')
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*self.studio.get('floor', (0.42, 0.34, 0.27)), 1)
        shader.inputs['Roughness'].default_value = .42
        mesh.materials.append(material)
        obj = self.link(bpy.data.objects.new('GF studio cyclorama', mesh))
        obj.location = (self.centre.x, self.centre.y, self.low.z)

    def step(self, name):
        # Energies scale with span squared, so irradiance on the asset is the same for a bolt or a ship.
        if name == 'set':
            self.floor()
        elif name == 'key':
            self.light('key', 35, 42, 95, .9, .5)
        elif name == 'fill':
            self.light('fill', -70, 18, 20, .7, .7)
        elif name == 'rim':
            self.light('rim', 165, 30, 140, .2, .9)
        elif name == 'top':
            self.light('top', 0, 85, 35, 1.1, .2)
        else:
            for slot, material in self.groups.get(name, []):
                slot.material = material

    def available(self):
        return set(self.groups)
