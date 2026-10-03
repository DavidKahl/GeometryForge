"""Host-side ownership and RPC lifecycle for a dedicated Houdini GUI."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid

import psutil
from .projects import ROOT

from .storage import HOME
STATE = HOME / 'houdini_session'


def resolve(explicit=None):
    import shutil
    chosen = explicit or os.environ.get('GEOMETRYFORGE_HOUDINI')
    if not chosen:
        import re
        installs = list(Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')).glob('Side Effects Software/Houdini */bin/houdini.exe'))
        installs.sort(key=lambda p: tuple(int(x) for x in re.findall(r'\d+', p.parent.parent.name)), reverse=True)
        chosen = str(installs[0]) if installs else shutil.which('houdini') or ''
    path = Path(chosen)
    if path.is_dir():
        path = path / 'bin' / ('houdini.exe' if os.name == 'nt' else 'houdini')
    if not path.is_file():
        raise FileNotFoundError(f'Houdini executable not found: {path}')
    return str(path.resolve())


def owned(record):
    if not isinstance(record,dict):
        return False
    try:
        process = psutil.Process(record['pid'])
        return (abs(process.create_time()-record['created']) < 0.01
                and Path(process.exe()).resolve() == Path(record['executable']).resolve())
    except (psutil.Error, KeyError):
        return False


def current():
    path = STATE / 'session.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    return record if owned(record) else None


def connect(record):
    if not owned(record):
        raise RuntimeError('Owned Houdini session no longer exists')
    from .houdini_transport import Client
    connection = Client(record['port'], record['token'])
    if connection.invoke('hello') != 2:
        raise RuntimeError('Restart the owned Houdini session to upgrade its transport')
    return connection, connection


def start(explicit=None, timeout=120):
    from .locking import exclusive
    with exclusive(STATE):
        return _start(explicit, timeout)


def _start(explicit=None, timeout=120):
    existing = current()
    if existing:
        if explicit and resolve(explicit) != existing['executable']:
            raise RuntimeError('Stop the current owned session before selecting another installation')
        connection, _ = connect(existing)
        connection.close()
        return existing
    executable = resolve(explicit)
    STATE.mkdir(parents=True, exist_ok=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    token = uuid.uuid4().hex
    from .worker_env import worker_environment
    env = worker_environment()
    env.update(GEOMETRYFORGE_ROOT=str(ROOT), GEOMETRYFORGE_SESSION_TOKEN=token,
               GEOMETRYFORGE_RPC_PORT=str(port),
               HOUDINI_USER_PREF_DIR=str(STATE / 'prefs__HVER__'), HOUDINI_NO_ENV_FILE='1')
    # A visible window is intentional: this is the requested editable session.
    log = (STATE / 'startup.log').open('w')
    try:
        process = subprocess.Popen([executable, str(ROOT/'geometryforge/houdini_bootstrap.py')],
                                   env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    finally:
        log.close()
    record = dict(pid=process.pid, created=psutil.Process(process.pid).create_time(),
                  executable=executable, port=port, token=token)
    (STATE/'session.json').write_text(json.dumps(record, indent=2))
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if not owned(record):
            raise RuntimeError(f'Houdini exited during startup; see {STATE / "startup.log"}')
        try:
            connection, _ = connect(record)
            connection.close()
            return record
        except (OSError, EOFError, AttributeError):
            time.sleep(0.3)
    raise RuntimeError('Houdini GUI did not become ready. Check its license/startup dialog; session retained.')


def terminate(record):
    if not owned(record):
        raise RuntimeError('Refusing to stop a process without matching ownership')
    process = psutil.Process(record['pid'])
    for child in process.children(recursive=True):
        try:
            child.terminate()
        except psutil.Error:
            pass
    process.terminate()
    process.wait(timeout=10)


def request(payload, explicit=None, timeout=900):
    record = start(explicit)
    connection, bridge = connect(record)
    job = uuid.uuid4().hex
    submitted = False
    try:
        bridge.submit(record['token'], job, json.dumps(payload))
        submitted = True
        deadline = time.monotonic()+timeout
        while True:
            from .process import check_cancelled
            check_cancelled()
            result = json.loads(bridge.status(record['token'], job))
            if result['status'] == 'passed':
                return result.get('result')
            if result['status'] in ('failed', 'cancelled'):
                raise RuntimeError(result.get('error', 'Houdini job cancelled'))
            if time.monotonic() >= deadline:
                raise TimeoutError('Houdini job timed out')
            time.sleep(0.2)
    except (KeyboardInterrupt, TimeoutError):
        if submitted:
            try:
                bridge.cancel(record['token'], job)
                deadline = time.monotonic()+3
                while time.monotonic() < deadline:
                    if json.loads(bridge.status(record['token'], job))['status'] not in ('running', 'queued'):
                        break
                    time.sleep(0.1)
                else:
                    terminate(record)
            except (OSError, EOFError):
                if owned(record):
                    terminate(record)
        raise
    finally:
        connection.close()
