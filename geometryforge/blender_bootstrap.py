"""Startup script of the dedicated live Blender GUI (blender --python ...), never host Python."""
import contextlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback

import bpy

VERSION = 1
TOKEN = os.environ['GEOMETRYFORGE_SESSION_TOKEN']
STATE = Path(os.environ['GEOMETRYFORGE_SESSION_STATE'])
jobs = {}
pending = queue.Queue()
lock = threading.Lock()
quitting = threading.Event()
active = None


def load_package():
    if 'geometryforge' not in sys.modules:
        package_dir = Path(os.environ['GEOMETRYFORGE_ROOT'])/'geometryforge'
        spec = importlib.util.spec_from_file_location('geometryforge', package_dir/'__init__.py', submodule_search_locations=[str(package_dir)])
        module = importlib.util.module_from_spec(spec)
        sys.modules['geometryforge'] = module
        spec.loader.exec_module(module)


def busy():
    return any(job['status'] in ('queued', 'running') or job['phase'] == 'presenting' for job in jobs.values())


def submit(job_id, request_json):
    with lock:
        if busy():
            presenting = any(job['phase'] == 'presenting' for job in jobs.values())
            raise RuntimeError('Blender live session is presenting; skip or wait' if presenting else 'Blender live session busy')
        request = json.loads(request_json)
        jobs[job_id] = {'status': 'queued', 'phase': 'queued', 'cancel': False, 'pause': False, 'skip': False,
                        'speed': 1.0, 'build_seconds': 0.0, 'part': None, 'index': 0, 'total': 0, 'beat': None}
        pending.put((job_id, request))
    return job_id


def status(job_id):
    job = jobs[job_id]
    return json.dumps({k: v for k, v in job.items() if k not in ('cancel', 'pause', 'skip')} | {'paused': job['pause']})


def current():
    return jobs[active[0]] if active else None


def control(name, value=True):
    job = current()
    if job is None:
        return False
    job[name] = value
    return True


def recover(reason):
    """Keep the session's unsaved state before anything replaces or abandons it."""
    if not bpy.data.is_dirty or not (bpy.data.objects or bpy.data.filepath):
        return None
    folder = STATE/'recovery'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/f'{time.strftime("%Y%m%dT%H%M%S")}-{reason}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
    return str(path)


def start(job_id, request):
    global active
    load_package()
    from geometryforge import live_shots, blender_live_view, native_worker, live_executor
    for module in (live_shots, blender_live_view, native_worker, live_executor):
        importlib.reload(module)
    job = jobs[job_id]
    if job['cancel']:
        job.update(status='cancelled', phase='done')
        return
    log = Path(request['out'])/'blender.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    stream = log.open('a', encoding='utf-8')
    job.update(status='running', recovered=recover('before-live-run'))
    active = (job_id, live_executor.run(request, job), stream)


def finish(**update):
    global active
    job_id, generator, stream = active
    stream.close()
    jobs[job_id].update(phase='done', **update)
    active = None


def tick():
    if quitting.is_set():
        if active is None:
            quit_session()
            return None
        control('cancel')
    if active is None:
        try:
            job_id, request = pending.get_nowait()
        except queue.Empty:
            return .25
        try:
            start(job_id, request)
        except BaseException:
            jobs[job_id].update(status='failed', phase='done', error=traceback.format_exc())
            return .25
        if active is None:
            return .25
    job_id, generator, stream = active
    job = jobs[job_id]
    from geometryforge.live_executor import Cancelled
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            wait = next(generator)
    except StopIteration:
        finish()
    except Cancelled:
        # Cancelling a finished run only stops the presentation; its evidence stays valid.
        finish(**({} if job['status'] == 'passed' else {'status': 'cancelled', 'recovered': recover('cancelled')}))
    except BaseException:
        error = traceback.format_exc()
        stream.write(error)
        if job['status'] == 'passed':
            finish(presentation_error=error)
        else:
            finish(status='failed', error=error, recovered=recover('failed'))
    else:
        return max(float(wait or 0), 1/120)
    return .25


def quit_session():
    recover('stop')
    bpy.ops.wm.quit_blender()


class GF_OT_live_control(bpy.types.Operator):
    bl_idname = 'geometryforge.live_control'
    bl_label = 'GeometryForge live control'
    action: bpy.props.EnumProperty(items=[('pause', 'Pause', ''), ('resume', 'Resume', ''), ('skip', 'Skip beat', ''),
                                          ('toggle', 'Start / pause / resume', '')])

    def execute(self, context):
        job = current()
        if self.action == 'skip':
            control('skip')
        elif self.action == 'toggle':
            control('pause', not (job and job['pause']))
        else:
            control('pause', self.action == 'pause')
        return {'FINISHED'}


def set_speed(self, context):
    control('speed', self.gf_live_speed)


class GF_PT_live(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category, bl_label = 'VIEW_3D', 'UI', 'GeometryForge', 'GeometryForge Live'

    def draw(self, context):
        layout = self.layout
        job = current()
        if job is None:
            layout.label(text='Waiting for a run')
            return
        layout.label(text=f'{job["phase"]}: {job["part"] or "-"} ({job["index"]+1}/{job["total"]})')
        layout.label(text=f'Beat: {job["beat"] or "-"}')
        row = layout.row()
        if job['phase'] == 'armed':
            row.scale_y = 1.6
            row.operator(GF_OT_live_control.bl_idname, text='Start').action = 'resume'
            return
        if job['pause']:
            row.operator(GF_OT_live_control.bl_idname, text='Resume').action = 'resume'
        else:
            row.operator(GF_OT_live_control.bl_idname, text='Pause').action = 'pause'
        row.operator(GF_OT_live_control.bl_idname, text='Skip beat').action = 'skip'
        layout.prop(context.window_manager, 'gf_live_speed')
        layout.prop(context.window_manager, 'gf_live_hud')


def draw_hud():
    # Opt-in only: recordings stay label-free unless the user switches the HUD on.
    job = current()
    if job is None or not bpy.context.window_manager.gf_live_hud:
        return
    import blf
    blf.size(0, 14)
    blf.color(0, .9, .9, .9, .8)
    blf.position(0, 24, 24, 0)
    blf.draw(0, f'{job["part"] or ""}  {job["index"]+1}/{job["total"]}')


def register():
    # A recording starts from an empty stage: no splash, no default cube, camera or light.
    bpy.context.preferences.view.show_splash = False
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.utils.register_class(GF_OT_live_control)
    bpy.utils.register_class(GF_PT_live)
    bpy.types.WindowManager.gf_live_speed = bpy.props.FloatProperty(name='Speed', default=1.0, min=.25, max=8.0, update=set_speed)
    bpy.types.WindowManager.gf_live_hud = bpy.props.BoolProperty(name='Show part HUD', default=False)
    bpy.types.SpaceView3D.draw_handler_add(draw_hud, (), 'WINDOW', 'POST_PIXEL')
    # The sidebar is hidden while recording: Ctrl+Shift+Enter in the viewport starts an armed run or pauses/resumes.
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig:
        keymap = keyconfig.keymaps.new(name='3D View', space_type='VIEW_3D')
        item = keymap.keymap_items.new(GF_OT_live_control.bl_idname, 'RET', 'PRESS', ctrl=True, shift=True)
        item.properties.action = 'toggle'
    bpy.app.timers.register(tick, first_interval=.5, persistent=True)


load_package()
from geometryforge.houdini_transport import server as make_server

server = make_server(int(os.environ['GEOMETRYFORGE_RPC_PORT']), TOKEN, {
    'hello': lambda: VERSION,
    'submit': submit,
    'status': status,
    'cancel': lambda job_id: jobs[job_id].update(cancel=True),
    'pause': lambda: control('pause', True),
    'resume': lambda: control('pause', False),
    'skip': lambda: control('skip'),
    'speed': lambda value: control('speed', float(value)),
    'state': lambda: json.dumps({'active': active[0] if active else None, 'busy': busy(), 'last': next(reversed(jobs), None)}),
    'quit': lambda: quitting.set() or True,
})
threading.Thread(target=server.serve_forever, daemon=True).start()
register()
