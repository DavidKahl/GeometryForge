"""Native SOP game evidence. Vertex attributes bypass the legacy OBJ parser."""
import json
from pathlib import Path


SURFACE_ATTRIBUTES = ('guide_bound', 'gf_inner', 'gf_solidify_rim', 'gf_pocket')


def point_attributes(geometry):
    """Surfacing weights and gf_* float point attributes; empty for geometry built without them."""
    import hou
    result = {}
    for attribute in geometry.pointAttribs():
        name = attribute.name()
        if attribute.dataType() != hou.attribData.Float or not (name in SURFACE_ATTRIBUTES or name.startswith('gf_')):
            continue
        values = geometry.pointFloatAttribValues(name)
        size = attribute.size()
        result[name] = [round(v, 6) for v in values] if size == 1 else [list(values[i:i + size]) for i in range(0, len(values), size)]
    return result


def interface(node, output):
    """Edge-only mating ring evidence from polylines or closed polygons, without triangulation."""
    import hou
    import numpy as np
    geometry = output.geometry()
    if geometry is None:
        raise ValueError(f'{node.path()}: cannot evaluate interface ring')
    edges = []
    for primitive in geometry.prims():
        points = [v.point().number() for v in primitive.vertices()]
        edges += [[a, b] for a, b in zip(points, points[1:])]
        if primitive.type() == hou.primType.Polygon and primitive.isClosed() and len(points) > 2:
            edges.append([points[-1], points[0]])
    if not edges:
        raise ValueError(f'Interface ring has no edges: {node.path()}')
    matrix = np.asarray(node.worldTransform().asTuple()).reshape(4, 4).T
    item = {'evidence_version': 2, 'name': node.name(), 'node': node.path(), 'part': node.userData('gf_part') or node.name(),
            'role': 'interface', 'vertices': [list(p.position()) for p in geometry.points()], 'faces': [], 'edges': edges,
            'matrix_world': matrix.tolist(), 'pivot_mm': matrix[:3, 3].tolist(),
            'metadata': json.loads(node.userData('gf_metadata') or '{}')}
    attributes = point_attributes(geometry)
    if attributes:
        item['point_attributes'] = attributes
    return item


def extract(target='game'):
    import hou
    import numpy as np
    roles = {'render','lod','collision'} if target == 'game' else {'design','high_detail','guide','interface'}
    root = hou.node('/obj/geometryforge')
    result = []
    for node in root.children():
        role = node.userData('gf_role')
        if role not in roles:
            continue
        output = node.node('OUT')
        if output is None:
            raise ValueError(f'{node.path()}: registered output requires OUT')
        if role == 'interface':
            result.append(interface(node, output))
            continue
        triangulate = node.createNode('divide','gf_evidence_triangles')
        triangulate.setInput(0,output)
        try:
            geometry = triangulate.geometry()
            if geometry is None or triangulate.errors():
                raise ValueError(f'{node.path()}: cannot evaluate game geometry')
            vertices = [list(p.position()) for p in geometry.points()]
            faces,normals,uvs,colors,assignments = [],[],{},[],[]
            uv_names = sorted({a.name() for a in [*geometry.vertexAttribs(),*geometry.pointAttribs()] if a.name()=='uv' or a.name().startswith('uv') and a.name()[2:].isdigit()})
            for name in uv_names: uvs[name] = []
            def value(vertex, name, fallback):
                if geometry.findVertexAttrib(name): return vertex.attribValue(name)
                if geometry.findPointAttrib(name): return vertex.point().attribValue(name)
                return fallback
            for primitive in geometry.prims():
                corners = list(primitive.vertices())
                if len(corners) != 3:
                    raise ValueError('Game extraction requires triangle primitives')
                faces.append([v.point().number() for v in corners])
                normal = list(primitive.normal())
                normals.append([list(value(v,'N',normal)) for v in corners])
                for name in uv_names: uvs[name].append([list(value(v,name,(0,0,0)))[:2] for v in corners])
                colors.append([list(value(v,'Cd',(1,1,1)))+[1] for v in corners])
                assignments.append(int(primitive.attribValue('gf_material_slot')) if geometry.findPrimAttrib('gf_material_slot') else 0)
            tangents = []
            if uvs:
                uv = next(iter(uvs.values()))
                for face,tex,ns in zip(faces,uv,normals):
                    p = np.asarray([vertices[i] for i in face]); t = np.asarray(tex)
                    edges = p[1:]-p[0]; deltas = t[1:]-t[0]
                    determinant = np.linalg.det(deltas)
                    if abs(determinant) < 1e-12:
                        tangents.append([[1,0,0,1]]*3); continue
                    tangent = (edges[0]*deltas[1,1]-edges[1]*deltas[0,1])/determinant
                    bitangent = (edges[1]*deltas[0,0]-edges[0]*deltas[1,0])/determinant
                    row = []
                    for normal in ns:
                        n = np.asarray(normal); n /= max(np.linalg.norm(n),1e-12)
                        projected = tangent-n*np.dot(n,tangent); projected /= max(np.linalg.norm(projected),1e-12)
                        row.append([*projected,1 if np.dot(np.cross(n,projected),bitangent)>=0 else -1])
                    tangents.append(row)
            metadata = json.loads(node.userData('gf_metadata') or '{}')
            matrix = np.asarray(node.worldTransform().asTuple()).reshape(4,4).T
            item = {'evidence_version':2,'name':node.name(),'node':node.path(),'part':node.userData('gf_part') or node.name(),
                    'role':role,'vertices':vertices,'faces':faces,'uv_layers':uvs,'corner_normals':normals,
                    'corner_tangents':tangents,'corner_colors':colors,'face_materials':assignments,
                    'materials':json.loads(node.userData('gf_materials') or '[]'),'matrix_world':matrix.tolist(),
                    'pivot_mm':matrix[:3,3].tolist(),'metadata':metadata}
            attributes = point_attributes(geometry)
            if attributes:
                item['point_attributes'] = attributes
            result.append(item)
        finally:
            triangulate.destroy()
    if not result: raise ValueError(f'No registered {target} SOP outputs')
    return result


def export_fbx(objects, directory):
    import hou
    import numpy as np
    from .storage import digest
    if 'apprentice' in str(hou.licenseCategory()).lower():
        raise ValueError('Houdini Apprentice does not support production FBX export; use a supported Houdini license or the Blender game route')
    directory.mkdir(parents=True,exist_ok=True)
    grouped = {}
    for obj in objects: grouped.setdefault(obj['part'],[]).append(obj)
    exports = {}
    for name,items in grouped.items():
        temporary = hou.node('/obj').createNode('subnet','gf_fbx_export')
        rop = hou.node('/out').createNode('filmboxfbx','gf_fbx_export')
        try:
            lods = {}
            for index,item in enumerate(items):
                label = f'UCX_{name}_{index:02d}' if item['role']=='collision' else name+f'_LOD{item["metadata"]["lod"]}' if item['role']=='lod' else name
                geo = temporary.createNode('geo',label)
                merge = geo.createNode('object_merge','native_source')
                merge.parm('objpath1').set(item['node']+'/OUT'); merge.parm('xformtype').set(1)
                # Internal coordinates are millimeters; emit centimeter-valued FBX geometry.
                transform = geo.createNode('xform','millimeters_to_centimeters'); transform.setInput(0,merge)
                transform.parm('scale').set(.1); transform.setDisplayFlag(True); transform.setRenderFlag(True)
                geo.setDisplayFlag(item['role']!='lod')
                if item['role']=='lod': lods[str(item['metadata']['lod'])] = geo
            rop.parm('startnode').set(temporary.path())
            path = directory/f'{name}.fbx'; rop.parm('sopoutput').set(str(path))
            # Never infer a meter scale from Houdini's global preferences.
            if rop.parm('convertunits'): rop.parm('convertunits').set(False)
            rop.render()
            lod_files = {}
            for level,geo in lods.items():
                geo.setDisplayFlag(True)
                rop.parm('startnode').set(geo.path())
                path_lod = directory/f'{name}_LOD{level}.fbx'; rop.parm('sopoutput').set(str(path_lod)); rop.render()
                lod_files[level] = str(path_lod)
            imported = hou.hipFile.importFBX(str(path),suppress_save_prompt=True,merge_into_scene=True,
                                           import_cameras=False,import_lights=False,import_animation=False,import_materials=False,convert_units=False)
            imported_root = imported[0]
            try:
                candidates = [n for n in imported_root.allSubChildren() if n.type().name()=='geo' and not n.name().startswith('UCX_') and '_LOD' not in n.name()]
                if len(candidates)!=1: raise ValueError(f'{name}: FBX read-back did not preserve render identity')
                geometry = candidates[0].displayNode().geometry()
                actual = np.asarray([list(p.position()) for p in geometry.points()])
                expected = np.asarray(next(o for o in items if o['role']=='render')['vertices'])
                if not np.allclose(np.ptp(actual,axis=0),np.ptp(expected,axis=0)*.1,atol=.002,rtol=1e-5):
                    raise ValueError(f'{name}: FBX read-back changed centimeter dimensions')
                if not geometry.findVertexAttrib('uv') and not geometry.findPointAttrib('uv'):
                    raise ValueError(f'{name}: FBX read-back lost UVs')
                exports[name] = {'path':str(path),'sha256':digest(path),'lods':lod_files,'roundtrip':{'passed':True,'bbox_cm':np.ptp(actual,axis=0).tolist()}}
            finally:
                imported_root.destroy()
        finally:
            rop.destroy(); temporary.destroy()
    return exports
