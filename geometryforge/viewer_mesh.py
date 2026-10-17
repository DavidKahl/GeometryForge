"""Compact binary meshes for the viewer.

Run evidence (`assembly.json`) stores every vertex, face and corner normal as JSON text. A detailed design part reaches
hundreds of megabytes, which a browser cannot fetch and parse. The viewer instead loads this format, converted once per
artifact and cached under `.geometryforge/cache/viewer/`:

    b'GFM1' | uint32 header length | UTF-8 JSON header | padding to 4 bytes | little-endian float32/uint32 buffers

The header lists each object's role, filament, materials, matrix, metadata, material groups and buffer slices
(`[byte offset from the buffer start, element count]`). Objects with corner normals are expanded per corner and ordered by
face material, exactly as the viewer draws them; other objects are indexed meshes whose normals the viewer computes.
"""
import hashlib
import json
import threading
from pathlib import Path

import numpy as np

MAGIC = b'GFM1'
_lock = threading.Lock()   # one conversion at a time: a large part can briefly need gigabytes while its JSON is parsed


def pack_objects(objects):
    header, chunks, offset = [], [], 0

    def add(array, dtype):
        nonlocal offset
        data = np.ascontiguousarray(array, dtype=dtype).ravel()
        chunks.append(data.tobytes())
        start, offset = offset, offset + data.nbytes
        return [start, int(data.size)]

    for obj in objects:
        vertices = np.asarray(obj.get('vertices', []), dtype=np.float64).reshape(-1, 3)
        faces = np.asarray(obj.get('faces', []), dtype=np.int64).reshape(-1, 3)
        entry = {key: obj[key] for key in ('role', 'filament', 'print_rotation_deg', 'matrix_world') if obj.get(key) is not None}
        entry['materials'] = [m.get('id') for m in obj.get('materials') or []]
        metadata = obj.get('metadata') or {}
        entry['metadata'] = {key: metadata[key] for key in ('lod', 'sockets') if key in metadata}
        normals = obj.get('corner_normals')
        if obj.get('role') and normals:
            materials = np.asarray(obj.get('face_materials') or [0] * len(faces), dtype=np.int64)
            order = np.argsort(materials, kind='stable')
            buffers = {'position': add(vertices[faces[order]], np.float32),
                       'normal': add(np.asarray(normals, dtype=np.float32).reshape(-1, 3, 3)[order], np.float32)}
            layers = obj.get('uv_layers') or {}
            if layers:
                buffers['uv'] = add(np.asarray(next(iter(layers.values())), dtype=np.float32).reshape(-1, 3, 2)[order], np.float32)
            if obj.get('corner_tangents'):
                buffers['tangent'] = add(np.asarray(obj['corner_tangents'], dtype=np.float32).reshape(-1, 3, 4)[order], np.float32)
            sorted_materials = materials[order]
            groups, start = [], 0
            for i in range(1, len(order) + 1):
                if i == len(order) or sorted_materials[i] != sorted_materials[start]:
                    groups.append([start * 3, (i - start) * 3, int(sorted_materials[start])])
                    start = i
            entry['groups'] = groups
        else:
            buffers = {'position': add(vertices, np.float32), 'index': add(faces, np.uint32)}
        entry['buffers'] = buffers
        header.append(entry)
    text = json.dumps({'objects': header}, separators=(',', ':')).encode('utf-8')
    padding = b'\0' * (-(8 + len(text)) % 4)
    return MAGIC + np.uint32(len(text)).tobytes() + text + padding + b''.join(chunks)


def unpack(data):
    """Inverse of pack_objects for tests and debugging: [(entry, {name: numpy array})]."""
    if data[:4] != MAGIC:
        raise ValueError('Not a GeometryForge viewer mesh')
    length = int(np.frombuffer(data[4:8], dtype=np.uint32)[0])
    header = json.loads(data[8:8 + length])
    base = 8 + length + (-(8 + length) % 4)
    result = []
    for entry in header['objects']:
        arrays = {}
        for name, (start, count) in entry['buffers'].items():
            arrays[name] = np.frombuffer(data, dtype=np.uint32 if name == 'index' else np.float32, count=count, offset=base + start)
        result.append((entry, arrays))
    return result


def cached(root, artifact):
    """Path of the packed mesh for an evidence JSON file, converting it on first use (keyed by path, size and mtime)."""
    artifact = Path(artifact)
    stat = artifact.stat()
    key = hashlib.sha256(f'{artifact.resolve()}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()[:32]
    target = Path(root) / '.geometryforge' / 'cache' / 'viewer' / f'{key}.gfm'
    if target.is_file():
        return target
    with _lock:
        if not target.is_file():
            data = pack_objects(json.loads(artifact.read_text(encoding='utf-8')).get('objects', []))
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix('.part')
            partial.write_bytes(data)
            partial.replace(target)
    return target
