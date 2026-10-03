"""Run as a startup script in the dedicated Houdini GUI, never in host Python."""
import contextlib
import json
import os
from pathlib import Path
import queue
import sys
import threading
import traceback
import types

import hou

bridge = types.ModuleType('geometryforge_bridge')
sys.modules[bridge.__name__] = bridge
jobs = {}
pending = queue.Queue()
lock = threading.Lock()
bridge.token = os.environ['GEOMETRYFORGE_SESSION_TOKEN']
bridge.version = 2


def submit(token, job_id, request_json):
    if token != bridge.token:
        raise ValueError('Wrong session owner')
    with lock:
        if any(job['status'] in ('queued', 'running') for job in jobs.values()):
            raise RuntimeError('Houdini session busy')
        request = json.loads(request_json)
        jobs[job_id] = {'status': 'queued', 'cancel': False}
        pending.put((job_id, request))
    return job_id


def status(token, job_id):
    if token != bridge.token:
        raise ValueError('Wrong session owner')
    return json.dumps(jobs[job_id])


def cancel(token, job_id):
    if token != bridge.token:
        raise ValueError('Wrong session owner')
    jobs[job_id]['cancel'] = True


def dispatch():
    try:
        job_id, request = pending.get_nowait()
    except queue.Empty:
        return
    job = jobs[job_id]
    if job['cancel']:
        job['status'] = 'cancelled'
        return
    job['status'] = 'running'
    try:
        root = os.environ['GEOMETRYFORGE_ROOT']
        if root not in sys.path:
            sys.path.insert(0, root)
        import importlib
        from geometryforge import houdini_worker
        execute = importlib.reload(houdini_worker).execute
        logfile = Path(request['out']) / 'houdini.log'
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open('a', encoding='utf-8') as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                result = execute(request, lambda: job['cancel'])
        job.update(status='cancelled' if job['cancel'] else 'passed', result=result)
    except BaseException:
        job.update(status='failed', error=traceback.format_exc())


bridge.submit, bridge.status, bridge.cancel = submit, status, cancel
sys.path.insert(0, os.environ['GEOMETRYFORGE_ROOT'])
from geometryforge.houdini_transport import server as make_server
server = make_server(int(os.environ['GEOMETRYFORGE_RPC_PORT']), bridge.token, {
    'hello': lambda: 2,
    'submit': lambda job, payload: submit(bridge.token, job, payload),
    'status': lambda job: status(bridge.token, job),
    'cancel': lambda job: cancel(bridge.token, job),
})
threading.Thread(target=server.serve_forever, daemon=True).start()
hou.ui.addEventLoopCallback(dispatch)
