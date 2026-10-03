"""Houdini-side jobs, invoked only on the GUI thread by the owned bridge."""
import json
from pathlib import Path
import sys
import time
import runpy
import os
import hou


def scene_suffix():
    category = str(hou.licenseCategory()).lower()
    return '.hipnc' if 'apprentice' in category else '.hiplc' if 'indie' in category else '.hip'


def recover():
    if hou.hipFile.hasUnsavedChanges():
        from .storage import HOME
        directory = HOME / 'houdini_session/recovery'
        directory.mkdir(parents=True, exist_ok=True)
        hou.hipFile.save(str(directory/f'recovery-{time.time_ns()}{scene_suffix()}'))


def execute(request, cancelled):
    out = Path(request['out'])
    out.mkdir(parents=True, exist_ok=True)
    action = request['action']
    info = {'version': hou.applicationVersionString(), 'python': sys.version,
            'license': str(hou.licenseCategory())}
    if action == 'native':
        import importlib
        from . import native_worker
        return importlib.reload(native_worker).houdini_execute(request, cancelled)
    if action == 'info':
        return info
    if action == 'recover':
        recover()
        return info
    if action == 'inspect':
        container = hou.node('/obj').createNode('geo', 'schema_probe')
        try:
            result = {}
            for kind in request['types']:
                node = container.createNode(kind)
                result[kind] = {p.name(): {'value': str(p.eval()),
                               'menu': list(p.parmTemplate().menuItems()) if hasattr(p.parmTemplate(), 'menuItems') else []}
                               for p in node.parms()}
            return result
        finally:
            container.destroy()
    if action == 'probe':
        recover()
        hou.hipFile.clear(suppress_save_prompt=True)
        geo = hou.node('/obj').createNode('geo', 'geometryforge_probe')
        box = geo.createNode('box', 'probe_20mm')
        box.parmTuple('size').set((20, 20, 20))
        box.cook(force=True)
        if cancelled():
            raise RuntimeError('Cancelled')
        box.geometry().saveToFile(str(out/'probe.obj'))
        scene = out/('probe' + scene_suffix())
        hou.hipFile.save(str(scene))
        hou.hipFile.load(str(scene), suppress_save_prompt=True, ignore_load_warnings=True)
        size = list(hou.node('/obj/geometryforge_probe/probe_20mm').geometry().boundingBox().sizevec())
        if any(abs(value-20)>1e-5 for value in size):
            raise RuntimeError('Probe dimensions changed')
        info.update(passed=True, bbox_mm=size, obj_export=(out/'probe.obj').is_file(),
                    scene_reopened=True)
        (out/'capabilities.json').write_text(json.dumps(info, indent=2))
        return info
    raise ValueError(f'Unknown Houdini job: {action}')


def export_geometry(out, cancelled):
    directory = out/'obj'
    directory.mkdir(exist_ok=True)
    inventory=[]
    nodes = [n for n in hou.node('/obj').allSubChildren() if n.userData('gf_export')]
    for index,node in enumerate(nodes):
        if cancelled():
            raise RuntimeError('Cancelled')
        metadata=json.loads(node.userData('gf_export'))
        metadata['role']=node.userData('gf_role')
        temp=hou.node('/obj').createNode('geo','export_temporary')
        try:
            merge=temp.createNode('object_merge')
            merge.parm('objpath1').set(node.node('OUT').path())
            merge.parm('xformtype').set(1)
            unpack=temp.createNode('unpack')
            unpack.setInput(0,merge)
            convert=temp.createNode('convert')
            convert.setInput(0,unpack)
            divide=temp.createNode('divide')
            divide.setInput(0,convert)
            weld=temp.createNode('fuse','merge_boolean_seams')
            weld.setInput(0,divide)
            weld.parm('tol3d').set(0.00005)
            divide=weld
            divide.cook(force=True)
            if divide.errors():
                raise RuntimeError(str(divide.errors()))
            filename=f'{index:03d}_{node.name()}.obj'
            divide.geometry().saveToFile(str(directory/filename))
            metadata['obj']=f'obj/{filename}'
            expected=node.userData('gf_expected_bbox_mm')
            if expected:
                metadata['expected_bbox_mm']=json.loads(expected)
            inventory.append(metadata)
            print(f'Exported {metadata["name"]}',flush=True)
        finally:
            temp.destroy()
    if not inventory:
        raise RuntimeError('No designated printable SOPs')
    (out/'houdini_geometry.json').write_text(json.dumps({'version':hou.applicationVersionString(),
        'units':'mm','objects':inventory},indent=2))
