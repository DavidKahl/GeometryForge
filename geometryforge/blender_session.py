"""Host-side ownership and job lifecycle for the dedicated live Blender GUI."""
import json
import socket
import subprocess
import time
import uuid

import psutil

from .houdini import owned
from .process import check_cancelled, resolve_blender
from .projects import ROOT
from .storage import HOME

STATE = HOME / 'blender_session'
VERSION = 1


def current():
    path = STATE / 'session.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    return record if owned(record) else None


def connect(record):
    if not owned(record):
        raise RuntimeError('Owned Blender live session no longer exists')
    from .houdini_transport import Client
    connection = Client(record['port'], record['token'])
    if connection.invoke('hello') != VERSION:
        raise RuntimeError('Restart the Blender live session to upgrade its transport')
    return connection


def start(explicit=None, user_prefs=False, timeout=120):
    from .locking import exclusive
    with exclusive(STATE):
        return _start(explicit, user_prefs, timeout)


def _start(explicit, user_prefs, timeout):
    existing = current()
    if existing:
        if explicit and resolve_blender(explicit) != existing['executable']:
            raise RuntimeError('Stop the current live session before selecting another Blender')
        connect(existing)
        return existing
    executable = resolve_blender(explicit)
    STATE.mkdir(parents=True, exist_ok=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    token = uuid.uuid4().hex
    from .worker_env import worker_environment
    env = worker_environment()
    env.update(GEOMETRYFORGE_ROOT=str(ROOT), GEOMETRYFORGE_SESSION_TOKEN=token, GEOMETRYFORGE_RPC_PORT=str(port),
               GEOMETRYFORGE_SESSION_STATE=str(STATE))
    # A visible window is intentional: this is the session the user watches and records.
    command = [executable] + ([] if user_prefs else ['--factory-startup']) + ['--python', str(ROOT/'geometryforge/blender_bootstrap.py')]
    log = (STATE / 'startup.log').open('w')
    try:
        process = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    finally:
        log.close()
    record = dict(pid=process.pid, created=psutil.Process(process.pid).create_time(),
                  executable=executable, port=port, token=token, user_prefs=user_prefs)
    (STATE/'session.json').write_text(json.dumps(record, indent=2))
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if not owned(record):
            raise RuntimeError(f'Blender exited during startup; see {STATE / "startup.log"}')
        try:
            connect(record)
            return record
        except (OSError, EOFError, ValueError):
            time.sleep(.3)
    raise RuntimeError(f'Blender live session did not become ready; see {STATE / "startup.log"}')


def stop(record, timeout=30):
    """Ask Blender to save a recovery copy and quit; terminate only if it does not exit."""
    if not owned(record):
        raise RuntimeError('Refusing to stop a process without matching ownership')
    try:
        connect(record).invoke('quit')
    except (OSError, RuntimeError):
        pass
    process = psutil.Process(record['pid'])
    try:
        process.wait(timeout=timeout)
    except psutil.TimeoutExpired:
        process.terminate()
        process.wait(timeout=10)


def control(action, value=None):
    record = current()
    if not record:
        raise RuntimeError('No Blender live session is running; start one with geometryforge session start --app blender')
    args = () if value is None else (value,)
    return connect(record).invoke(action, *args)


def status():
    record = current()
    if not record:
        return {'running': False}
    state = json.loads(connect(record).invoke('state'))
    if state.get('last'):
        state['job'] = json.loads(connect(record).invoke('status', state['last']))
    return {'running': True, 'pid': record['pid'], **state}


def request(payload, explicit=None, timeout=900):
    """Submit one live job and wait for its evidence. `timeout` counts build time only, not reveal beats or pauses.

    Long native operations can hold Blender's main thread and GIL, so missed status replies are retried while the
    owned process lives and the unreachable time counts as build time."""
    record = start(explicit)
    connection = connect(record)
    job = uuid.uuid4().hex
    connection.invoke('submit', job, json.dumps(payload))
    unreachable, last = 0.0, time.monotonic()
    try:
        while True:
            check_cancelled()
            try:
                result = json.loads(connection.invoke('status', job))
                unreachable = 0.0
            except OSError:
                if not owned(record):
                    raise RuntimeError('Blender live session exited during the run')
                now = time.monotonic()
                unreachable += now-last
                last = now
                if unreachable >= timeout:
                    raise TimeoutError('Blender live job timed out (session unresponsive)')
                continue
            last = time.monotonic()
            if result['status'] == 'passed':
                return result.get('result')
            if result['status'] in ('failed', 'cancelled'):
                raise RuntimeError(result.get('error', 'Blender live job cancelled'))
            if result['build_seconds'] + unreachable >= timeout:
                raise TimeoutError(f'Blender live job exceeded {timeout} s of build time')
            time.sleep(.25)
    except (KeyboardInterrupt, TimeoutError):
        # The window stays open: it is the user's view of the run, and the recovery copy is saved inside it.
        try:
            connection.invoke('cancel', job)
        except (OSError, RuntimeError):
            pass
        raise
