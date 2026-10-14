"""Game validation and portable packages. No native modules or model providers."""
from pathlib import Path
import json
import math
import re
import shutil
import struct
import zipfile

import numpy as np
from PIL import Image, ImageOps

from .storage import digest, fingerprint, inside, write

PROFILES = {
    'unreal_desktop_standard': {'triangle_budget': 20000, 'material_budget': 2, 'texture_resolution': 2048,
                                'lod_ratios': [1, .5, .25, .125], 'nanite': False},
    'unreal_desktop_nanite': {'triangle_budget': 250000, 'material_budget': 2, 'texture_resolution': 2048,
                              'lod_ratios': [1], 'nanite': True},
}


def evidence_key(objects):
    """Relocating a packed texture must not be mistaken for a material edit."""
    def stable(value):
        if isinstance(value,dict):
            return {k:stable(v) for k,v in value.items() if not (k=='path' and 'sha256' in value)}
        if isinstance(value,list): return [stable(v) for v in value]
        if isinstance(value,float): return round(value,5)
        return value
    return fingerprint(stable(objects))


def evidence_equivalent(left, right):
    """Avoid cache churn when native float32 recooking crosses a hash rounding boundary."""
    if isinstance(left,dict):
        if not isinstance(right,dict): return False
        keys={k for k in left if not (k=='path' and 'sha256' in left)}
        other={k for k in right if not (k=='path' and 'sha256' in right)}
        return keys==other and all(evidence_equivalent(left[k],right[k]) for k in keys)
    if isinstance(left,list):
        return isinstance(right,list) and len(left)==len(right) and all(evidence_equivalent(a,b) for a,b in zip(left,right))
    if isinstance(left,float) and isinstance(right,(float,int)):
        return bool(np.isclose(left,right,atol=1e-6,rtol=1e-7))
    return left==right


def profile_settings(settings):
    name = settings.get('profile', 'unreal_desktop_standard')
    if name not in PROFILES:
        raise ValueError(f'Unknown game profile: {name}')
    result = {**PROFILES[name], 'profile': name, 'lighting': 'dynamic', 'collision': 'blocking', **settings}
    for key in ('triangle_budget', 'material_budget', 'texture_resolution'):
        if type(result[key]) is not int or result[key] <= 0:
            raise ValueError(f'{key} must be a positive integer')
    if result['lighting'] not in ('dynamic', 'baked') or result['collision'] not in ('decorative', 'blocking', 'traversable', 'physics'):
        raise ValueError('Invalid lighting or collision policy')
    if not result['lod_ratios'] or result['lod_ratios'][0] != 1 or any(not math.isfinite(r) or not 0 < r <= 1 for r in result['lod_ratios']):
        raise ValueError('LOD ratios must start at 1 and be positive finite fractions')
    return result


def safe_name(name):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError(f'Use a stable filename-safe output ID: {name!r}')
    return name


def world_vertices(obj):
    v = np.asarray(obj['vertices'], dtype=float)
    matrix = np.asarray(obj.get('matrix_world', np.eye(4)), dtype=float)
    return (np.column_stack((v, np.ones(len(v)))) @ matrix.T)[:, :3]


def uv_overlaps(triangles):
    """Positive-area overlap, with grid broad-phase and shared-edge tolerance."""
    triangles=np.asarray(triangles,dtype=float)
    size=max(1,min(64,int(math.sqrt(len(triangles)/4))))
    cells={}; tested=set()
    def cross(a,b): return a[0]*b[1]-a[1]*b[0]
    def overlap(a,b):
        polygon=list(a)
        orientation=1 if cross(b[1]-b[0],b[2]-b[0])>0 else -1
        for i in range(3):
            start,end=b[i],b[(i+1)%3]; edge=end-start
            clipped=[]
            for index,p in enumerate(polygon):
                q=polygon[(index+1)%len(polygon)]
                dp=orientation*cross(edge,p-start); dq=orientation*cross(edge,q-start)
                if dp>=-1e-10: clipped.append(p)
                if (dp>0)!=(dq>0) and abs(dp-dq)>1e-12: clipped.append(p+(q-p)*dp/(dp-dq))
            polygon=clipped
            if len(polygon)<3: return False
        area=abs(sum(cross(p,polygon[(i+1)%len(polygon)]) for i,p in enumerate(polygon)))/2
        return area>1e-9
    for index,triangle in enumerate(triangles):
        low=np.floor(triangle.min(axis=0)*size).astype(int)
        high=np.floor(triangle.max(axis=0)*size-1e-10).astype(int)
        for x in range(low[0],max(low[0],high[0])+1):
            for y in range(low[1],max(low[1],high[1])+1):
                bucket=cells.setdefault((x,y),[])
                for other in bucket:
                    pair=(other,index)
                    if pair in tested: continue
                    tested.add(pair)
                    if overlap(triangles[other],triangle): return True
                bucket.append(index)
    return False


def measurements(name, objects):
    primary = [o for o in objects if o.get('role') in ('render', 'design', 'high_detail')]
    v = np.concatenate([np.asarray(o['vertices'], dtype=float) for o in primary or objects])
    return {'name': name, 'bbox_mm': np.ptp(v, axis=0).tolist(),
            'triangles': sum(len(o['faces']) for o in primary or objects),
            'materials': len({m['id'] for o in primary or objects for m in o.get('materials', [])}),
            'checks': {'finite_geometry': bool(np.isfinite(v).all())}}


def validate(objects, settings):
    import trimesh
    profile = profile_settings(settings)
    outputs = {}
    failures = []
    for obj in objects:
        name = safe_name(obj['part'])
        outputs.setdefault(name, []).append(obj)
        v = np.asarray(obj['vertices'], dtype=float)
        f = np.asarray(obj['faces'])
        if v.ndim != 2 or v.shape[1:] != (3,) or not len(v) or not np.isfinite(v).all():
            raise ValueError(f'{name}: invalid vertex positions')
        if f.ndim != 2 or f.shape[1:] != (3,) or not len(f) or f.dtype.kind not in 'iu' or f.min() < 0 or f.max() >= len(v):
            raise ValueError(f'{name}: invalid triangle indices')
        points = v[f]
        if np.any(np.linalg.norm(np.cross(points[:,1]-points[:,0], points[:,2]-points[:,0]), axis=1) < 1e-10):
            failures.append(f'{name}: degenerate triangles')
        matrix = np.asarray(obj.get('matrix_world', np.eye(4)), dtype=float)
        if matrix.shape != (4,4) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix[:3,:3])) < 1e-12:
            failures.append(f'{name}: invalid asset transform')
        else:
            axes=matrix[:3,:3];normalized=axes/np.linalg.norm(axes,axis=0)
            if not np.allclose(normalized.T@normalized,np.eye(3),atol=1e-5) or not np.allclose(matrix[3],[0,0,0,1]):
                failures.append(f'{name}: apply shear/perspective to render geometry before exporting a rigid asset')
        role = obj.get('role', 'render')
        if role in ('render', 'lod'):
            if obj.get('metadata',{}).get('uv_mode','unique') not in ('unique','tiled'):
                failures.append(f'{name}: unknown UV policy')
            if not obj.get('uv_layers'):
                failures.append(f'{name}: missing UV atlas')
            for channel, uv in obj.get('uv_layers', {}).items():
                uv = np.asarray(uv, dtype=float)
                if uv.shape != (len(f),3,2) or not np.isfinite(uv).all():
                    failures.append(f'{name}: invalid {channel} UV data')
                elif np.any(np.abs((uv[:,1,0]-uv[:,0,0])*(uv[:,2,1]-uv[:,0,1])-(uv[:,1,1]-uv[:,0,1])*(uv[:,2,0]-uv[:,0,0])) < 1e-12):
                    failures.append(f'{name}: degenerate {channel} UV triangles')
                elif obj.get('metadata',{}).get('uv_mode','unique') == 'unique' or channel != next(iter(obj['uv_layers'])):
                    if np.any(uv<-.00001) or np.any(uv>1.00001) or uv_overlaps(uv):
                        failures.append(f'{name}: {channel} must be a non-overlapping atlas within 0–1; declare tiled UVs explicitly when intended')
            for key, size in [('corner_normals',3), ('corner_tangents',4)]:
                data = np.asarray(obj.get(key, []), dtype=float)
                if data.shape != (len(f),3,size) or not np.isfinite(data).all() or not np.allclose(np.linalg.norm(data[...,:3], axis=2), 1, atol=.005):
                    failures.append(f'{name}: missing or invalid {key}')
            mats = obj.get('materials', [])
            for material in mats:
                factors=[*material.get('base_color',[1,1,1,1]),material.get('roughness',.5),material.get('metallic',0)]
                if not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in factors):
                    failures.append(f'{name}: invalid PBR material factors')
            indices = np.asarray(obj.get('face_materials', []))
            if not mats or indices.shape != (len(f),) or indices.dtype.kind not in 'iu' or indices.min() < 0 or indices.max() >= len(mats):
                failures.append(f'{name}: invalid material assignments')
            if len(mats) > profile['material_budget']:
                failures.append(f'{name}: material budget exceeded')
            if profile['nanite'] and obj.get('metadata', {}).get('nanite', True):
                if any(m.get('blend_mode', 'OPAQUE') not in ('OPAQUE', 'MASKED') for m in mats):
                    failures.append(f'{name}: split unsupported materials into an explicitly conventional output')
            if profile['lighting'] == 'baked' and len(obj.get('uv_layers', {})) < 2:
                failures.append(f'{name}: baked lighting requires a separate lightmap UV channel')
        elif role == 'collision':
            mesh = trimesh.Trimesh(v, f, process=False)
            if not mesh.is_watertight or not mesh.is_convex:
                failures.append(f'{name}: UCX collision must be a closed convex body')
        else:
            failures.append(f'{name}: unsupported game output role {role}')
    for name, items in outputs.items():
        base = [o for o in items if o.get('role', 'render') == 'render']
        lods = [o for o in items if o.get('role') == 'lod']
        if len(base) != 1:
            failures.append(f'{name}: register exactly one render mesh per output ID')
            continue
        if len(base[0]['faces']) > profile['triangle_budget']:
            failures.append(f'{name}: triangle budget exceeded; revise or explicitly change the profile')
        levels = [o.get('metadata', {}).get('lod') for o in lods]
        if len(set(levels)) != len(levels) or any(type(n) is not int or n <= 0 for n in levels):
            failures.append(f'{name}: invalid LOD identities')
        nanite = profile['nanite'] and base[0].get('metadata',{}).get('nanite',True)
        ratios = profile['lod_ratios'] if not profile['nanite'] else [1] if nanite else settings.get('conventional_lod_ratios',PROFILES['unreal_desktop_standard']['lod_ratios'])
        if not nanite and set(levels) != set(range(1, len(ratios))):
            failures.append(f'{name}: incomplete conventional LOD chain')
        for lod in lods:
            if len(lod['faces']) > len(base[0]['faces']):
                failures.append(f'{name}: LOD is more complex than its base mesh')
        policy = base[0].get('metadata', {}).get('collision', profile['collision'])
        if policy != 'decorative' and not any(o.get('role') == 'collision' for o in items):
            failures.append(f'{name}: missing simplified collision')
        for socket in base[0].get('metadata', {}).get('sockets', []):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', socket['name']) or len(socket.get('position_mm', [])) != 3:
                failures.append(f'{name}: invalid socket metadata')
    return {'passed': bool(outputs) and not failures, 'profile': profile, 'failures': failures,
            'outputs': {n: measurements(n, items) for n, items in outputs.items()}}


def _texture_source(root, frozen, path):
    source = Path(path)
    if not source.is_absolute():
        source = inside(frozen, path)
    source = source.resolve()
    if not source.is_relative_to(Path(root).resolve()):
        raise ValueError(f'Texture must be a declared project input or retained artifact: {source}')
    if not source.is_file():
        raise ValueError(f'Missing texture: {source}')
    # Frozen input and generated retained-run textures are immutable evidence.
    if not source.is_relative_to(Path(root) / '.geometryforge/runs'):
        relative = source.relative_to(root)
        captured = inside(frozen, relative)
        if not captured.is_file():
            raise ValueError(f'Declare the texture in target sources: {relative}')
        source = captured
    return source


def pack_materials(objects, settings, out, root, frozen):
    materials = {}
    for obj in objects:
        for original in obj.get('materials', []):
            mat = dict(original)
            mat.update(settings.get('materials', {}).get(mat['id'], {}))
            ident = mat['id']
            if ident in materials:
                if evidence_key(original) != materials[ident]['source_key']:
                    raise ValueError(f'Material identity has inconsistent definitions: {ident}')
                continue
            mat['source_key'] = evidence_key(original)
            textures = {}
            for channel, texture in mat.get('textures', {}).items():
                if channel not in ('base_color','normal','roughness','metallic','occlusion','emissive'):
                    raise ValueError(f'Unsupported PBR texture channel: {channel}')
                spec = texture if isinstance(texture, dict) else {'path': texture}
                source = _texture_source(root, frozen, spec['path'])
                with Image.open(source) as image:
                    if max(image.size) > settings['texture_resolution']:
                        raise ValueError(f'{ident}: texture resolution exceeds the profile budget')
                    image = image.convert('RGB')
                    name = re.sub(r'[^A-Za-z0-9_]', '_', ident) + '_' + fingerprint([ident,channel])[:8] + '_' + channel
                    path = out / 'textures' / (name + '.png')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if channel == 'normal':
                        convention = spec.get('normal_convention', 'opengl')
                        if convention not in ('opengl', 'directx'):
                            raise ValueError('Record opengl or directx normal-map convention')
                        if convention == 'directx':
                            r,g,b = image.split(); image = Image.merge('RGB', (r,ImageOps.invert(g),b))
                        preview = path.with_name(name + '_opengl.png')
                        image.save(preview)
                        r,g,b = image.split(); Image.merge('RGB', (r,ImageOps.invert(g),b)).save(path)
                        textures[channel] = {'path': path.relative_to(out).as_posix(), 'preview_path': preview.relative_to(out).as_posix(), 'normal_convention': 'directx', 'color_space': 'linear', 'source_sha256': digest(source)}
                    else:
                        image.save(path)
                        textures[channel] = {'path': path.relative_to(out).as_posix(), 'color_space': 'sRGB' if channel in ('base_color','emissive') else 'linear', 'source_sha256': digest(source)}
            if any(c in textures for c in ('roughness','metallic','occlusion')):
                images = {}
                size = None
                for channel in ('roughness','metallic','occlusion'):
                    if channel in textures:
                        with Image.open(out / textures[channel]['path']) as image:
                            if size is not None and image.size != size:
                                raise ValueError(f'{ident}: ORM source maps must share a resolution')
                            images[channel] = image.convert('L')
                            size = image.size
                channels = [images.get('occlusion', Image.new('L',size,255)),
                            images.get('roughness', Image.new('L',size,round(mat.get('roughness',.5)*255))),
                            images.get('metallic', Image.new('L',size,round(mat.get('metallic',0)*255)))]
                path = out / 'textures' / (re.sub(r'[^A-Za-z0-9_]', '_', ident) + '_' + fingerprint(ident)[:8] + '_orm.png')
                Image.merge('RGB',channels).save(path)
                textures['orm'] = {'path': path.relative_to(out).as_posix(), 'color_space': 'linear', 'channels': {'r':'occlusion','g':'roughness','b':'metallic'}}
            mat['textures'] = textures
            if 'base_color' in textures:
                mat['base_color'] = [1,1,1,mat.get('base_color',[1,1,1,1])[3]]
            materials[ident] = mat
    return materials


def write_glb(objects, materials, out, package_root):
    """Split vertices at every corner attribute; never weld away a UV or shading seam."""
    document = {'asset': {'version':'2.0','generator':'GeometryForge'}, 'buffers':[{}], 'bufferViews':[], 'accessors':[],
                'meshes':[], 'nodes':[], 'scenes':[{'nodes':[]}], 'scene':0, 'materials':[], 'images':[], 'textures':[]}
    binary = bytearray()
    def view(data, target=None):
        while len(binary)%4:
            binary.append(0)
        item = {'buffer':0,'byteOffset':len(binary),'byteLength':len(data)}
        if target:
            item['target'] = target
        document['bufferViews'].append(item)
        binary.extend(data)
        return len(document['bufferViews'])-1
    def accessor(data, kind, bounds=False):
        array = np.asarray(data,dtype='<f4')
        item = {'bufferView':view(array.tobytes(),34962),'componentType':5126,'count':len(array),'type':kind}
        if bounds:
            item.update(min=array.min(axis=0).tolist(),max=array.max(axis=0).tolist())
        document['accessors'].append(item)
        return len(document['accessors'])-1
    def texture(path):
        document['images'].append({'bufferView':view((package_root/path).read_bytes()),'mimeType':'image/png'})
        document['textures'].append({'source':len(document['images'])-1})
        return {'index':len(document['textures'])-1}
    mat_indices = {}
    for ident, mat in materials.items():
        pbr = {'baseColorFactor':mat.get('base_color',[1,1,1,1]),'roughnessFactor':mat.get('roughness',.5),'metallicFactor':mat.get('metallic',0)}
        item = {'name':ident,'pbrMetallicRoughness':pbr,'doubleSided':bool(mat.get('double_sided',False))}
        for channel,spec in mat['textures'].items():
            if channel == 'base_color': pbr['baseColorTexture'] = texture(spec['path'])
            elif channel == 'normal': item['normalTexture'] = texture(spec['preview_path'])
            elif channel == 'orm':
                pbr['metallicRoughnessTexture'] = texture(spec['path']); pbr['metallicFactor'] = 1; pbr['roughnessFactor'] = 1
                item['occlusionTexture'] = pbr['metallicRoughnessTexture']
            elif channel == 'emissive': item['emissiveTexture'] = texture(spec['path']); item['emissiveFactor'] = [1,1,1]
        mode = mat.get('blend_mode','OPAQUE')
        item['alphaMode'] = 'BLEND' if mode == 'TRANSLUCENT' else mode
        mat_indices[ident] = len(document['materials']); document['materials'].append(item)
    basis = np.array([[1,0,0],[0,0,1],[0,-1,0]],dtype=float)
    transform = np.eye(4); transform[:3,:3] = basis
    for obj in objects:
        if obj['role'] != 'render':
            continue
        vertices = np.asarray(obj['vertices']); faces = np.asarray(obj['faces'])
        positions = vertices[faces].reshape(-1,3) @ basis.T * .001
        normals = np.asarray(obj['corner_normals']).reshape(-1,3) @ basis.T
        uv = np.asarray(next(iter(obj['uv_layers'].values()))).reshape(-1,2).copy(); uv[:,1] = 1-uv[:,1]
        tangents = np.asarray(obj['corner_tangents']).reshape(-1,4).copy(); tangents[:,:3] = tangents[:,:3] @ basis.T; tangents[:,3] *= -1
        primitives = []
        for slot,mat in enumerate(obj['materials']):
            indices = np.flatnonzero(np.asarray(obj['face_materials'])==slot)
            corners = (indices[:,None]*3+np.arange(3)).reshape(-1)
            if not len(corners): continue
            attributes = {'POSITION':accessor(positions[corners],'VEC3',True),'NORMAL':accessor(normals[corners],'VEC3'),
                          'TEXCOORD_0':accessor(uv[corners],'VEC2'),'TANGENT':accessor(tangents[corners],'VEC4')}
            if obj.get('corner_colors'):
                attributes['COLOR_0'] = accessor(np.asarray(obj['corner_colors']).reshape(-1,4)[corners],'VEC4')
            primitives.append({'attributes':attributes,'material':mat_indices[mat['id']]})
        document['meshes'].append({'name':obj['part'],'primitives':primitives})
        matrix = transform @ np.asarray(obj['matrix_world']) @ transform.T; matrix[:3,3] *= .001
        document['nodes'].append({'name':obj['part'],'mesh':len(document['meshes'])-1,'matrix':matrix.T.reshape(-1).tolist()})
        document['scenes'][0]['nodes'].append(len(document['nodes'])-1)
    document['buffers'][0]['byteLength'] = len(binary)
    payload = json.dumps(document,separators=(',',':'),allow_nan=False).encode()
    payload += b' ' * (-len(payload)%4); binary.extend(b'\0'*(-len(binary)%4))
    out.write_bytes(struct.pack('<III',0x46546C67,2,12+8+len(payload)+8+len(binary))+struct.pack('<II',len(payload),0x4E4F534A)+payload+struct.pack('<II',len(binary),0x004E4942)+binary)
    # Read the actual container and accessors back, not just the writer's input.
    verify_glb(out, objects)


def verify_glb(path, expected=None):
    data = Path(path).read_bytes()
    magic,version,length = struct.unpack_from('<III',data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError('Invalid GLB header')
    size,kind = struct.unpack_from('<II',data,12)
    if kind != 0x4E4F534A:
        raise ValueError('Missing GLB JSON chunk')
    document = json.loads(data[20:20+size])
    offset = 20+size
    binary_size,binary_kind = struct.unpack_from('<II',data,offset)
    if binary_kind != 0x004E4942 or offset+8+binary_size != len(data):
        raise ValueError('Invalid GLB binary chunk')
    for view in document['bufferViews']:
        if view.get('byteOffset',0)+view['byteLength'] > binary_size:
            raise ValueError('GLB buffer view exceeds its buffer')
    binary=data[offset+8:]
    arrays=[]
    for accessor in document['accessors']:
        view=document['bufferViews'][accessor['bufferView']]
        components={'VEC2':2,'VEC3':3,'VEC4':4}[accessor['type']]
        if accessor['componentType']!=5126 or accessor['count']*components*4>view['byteLength']:
            raise ValueError('Invalid GLB vertex accessor')
        array=np.frombuffer(binary,dtype='<f4',count=accessor['count']*components,offset=view.get('byteOffset',0)).reshape(-1,components)
        if not np.isfinite(array).all(): raise ValueError('Nonfinite GLB attributes')
        arrays.append(array)
    by_name={o['part']:o for o in expected or [] if o['role']=='render'}
    basis=np.array([[1,0,0],[0,0,1],[0,-1,0]],dtype=float)
    for mesh in document['meshes']:
        obj=by_name.get(mesh['name'])
        for primitive in mesh['primitives']:
            attributes=primitive['attributes']
            count=len(arrays[attributes['POSITION']])
            if count%3 or any(len(arrays[index])!=count for index in attributes.values()):
                raise ValueError('GLB corner attributes are misaligned')
            if obj:
                material_id=document['materials'][primitive['material']]['name']
                slot=next(i for i,m in enumerate(obj['materials']) if m['id']==material_id)
                faces=np.asarray(obj['faces'])[np.asarray(obj['face_materials'])==slot]
                positions=np.asarray(obj['vertices'])[faces].reshape(-1,3)@basis.T*.001
                if not np.allclose(positions,arrays[attributes['POSITION']],atol=1e-7,rtol=1e-6):
                    raise ValueError('GLB read-back changed vertex positions or corner ordering')
                normals=np.asarray(obj['corner_normals'])[np.asarray(obj['face_materials'])==slot].reshape(-1,3)@basis.T
                if not np.allclose(normals,arrays[attributes['NORMAL']],atol=1e-6):
                    raise ValueError('GLB read-back changed shading normals')
    return document


def package(objects, out, settings, *, root, frozen, exports, prior=None, full=False):
    settings = profile_settings(settings)
    out.mkdir(parents=True, exist_ok=True)
    (out/'reports').mkdir(exist_ok=True)
    report = validate(objects,settings)
    write(out/'reports/meshes.json',report)
    if not report['passed']:
        raise ValueError('Game validation failed: '+ '; '.join(report['failures']))
    materials = pack_materials(objects,settings,out,root,frozen)
    grouped = {}
    for obj in objects: grouped.setdefault(obj['part'],[]).append(obj)
    outputs = {}
    for name,items in grouped.items():
        export = exports.get(name)
        if not export or not export.get('roundtrip',{}).get('passed'):
            raise ValueError(f'{name}: native FBX export/read-back evidence is required')
        source = inside(root,export['path'])
        if digest(source) != export['sha256']:
            raise ValueError(f'{name}: native export was modified')
        path = out/'meshes'/f'{name}.fbx'; path.parent.mkdir(exist_ok=True)
        shutil.copy2(source,path)
        lod_files = {}
        expected_lods={str(o['metadata']['lod']) for o in items if o['role']=='lod'}
        if set(export.get('lods',{})) != expected_lods:
            raise ValueError(f'{name}: native export is missing delivered LOD files')
        for level,source in export.get('lods',{}).items():
            source = inside(root,source)
            dest = out/'meshes'/f'{name}_LOD{level}.fbx'; shutil.copy2(source,dest)
            lod_files[str(level)] = dest.relative_to(out).as_posix()
        preview = out/'preview'/f'{name}.glb'; preview.parent.mkdir(exist_ok=True)
        write_glb(items,materials,preview,out)
        base = next(o for o in items if o['role']=='render')
        outputs[name] = {**measurements(name,items),'mesh':path.relative_to(out).as_posix(),'preview':preview.relative_to(out).as_posix(),
                         'lod_files':lod_files,'lods':[o['metadata']['lod'] for o in items if o['role']=='lod'],
                         'collision_bodies':sum(o['role']=='collision' for o in items),
                         'materials':[m['id'] for m in base['materials']], 'matrix_world_mm':base['matrix_world'],
                         'source_parts':base.get('metadata',{}).get('source_parts',[name]),
                         'sockets':base.get('metadata',{}).get('sockets',[]),
                         'nanite':settings['nanite'] and base.get('metadata',{}).get('nanite',True),
                         'fallback_relative_error':settings.get('fallback_relative_error',1.0),
                         'collision_policy':base.get('metadata',{}).get('collision',settings['collision'])}
    write_glb(objects,materials,out/'preview/scene.glb',out)
    from . import projects
    scripts = out/'unreal'; scripts.mkdir(exist_ok=True)
    shutil.copy2(projects.PACKAGE/'unreal_worker.py',scripts/'import_asset.py')
    shutil.copy2(projects.PACKAGE/'unreal_review.py',scripts/'review_asset.py')
    write(scripts/'settings.json',{'units':'cm','source_units':'mm','source_to_unreal_scale':.1,'profile':settings,'material_workflow':'metal_roughness','fbx_axes':{'forward':'-Y','up':'Z'}})
    derivation=settings.get('derivation') or {}
    write(out/'reports/conversion.json',{'notes':settings.get('conversion_notes',[]),'scale':derivation.get('scale'),
                                        'source_run':derivation.get('from_run'),'source_target':derivation.get('from_target'),
                                        'geometry_verified':True,'unreal_verified':False,'slicer_reviewed':False,'physically_tested':False})
    files = {str(f.relative_to(out)).replace('\\','/'):digest(f) for f in sorted(out.rglob('*')) if f.is_file()}
    ident = fingerprint({'outputs':outputs,'materials':materials,'settings':settings,'files':files})[:16]
    manifest = {'format_version':1,'evidence_version':2,'package_id':ident,'units':'mm','unreal_units':'cm',
                'profile':settings,'outputs':outputs,'materials':materials,'files':files,'derivation':derivation or None,
                'coverage':{'package_safe':True,'unreal_verified':False},'preview':'preview/scene.glb',
                'statistics':{'files_bytes':sum(f.stat().st_size for f in out.rglob('*') if f.is_file()),
                              'mesh_bytes':sum(f.stat().st_size for f in (out/'meshes').glob('*')),
                              'texture_bytes':sum(f.stat().st_size for f in (out/'textures').glob('*')) if (out/'textures').exists() else 0,
                              'outputs':len(outputs),'render_triangles':sum(o['triangles'] for o in outputs.values()),
                              'material_sections':sum(len(o['materials']) for o in outputs.values())}}
    write(out/'manifest.json',manifest)
    verify_package(out)
    archive = out/'asset-package.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(out.rglob('*')):
            if file.is_file() and file != archive:
                bundle.write(file,str(file.relative_to(out)).replace('\\','/'))
    return {'package_id':ident,'manifest':str((out/'manifest.json').relative_to(root)).replace('\\','/'),
            'profile':settings,'outputs':outputs,'materials':materials,'package_safe':True,'unreal_verified':False}


def verify_package(root):
    manifest = json.loads((Path(root)/'manifest.json').read_text(encoding='utf-8'))
    for name,sha in manifest['files'].items():
        if digest(inside(root,name)) != sha:
            raise ValueError(f'Game package artifact changed: {name}')
    verify_glb(inside(root,manifest['preview']))
    return manifest
