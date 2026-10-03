"""Subprocess isolation shared by CAD and Blender backends."""
import os
from pathlib import Path
import shutil
import subprocess
import time
from contextvars import ContextVar

cancel_event = ContextVar('geometryforge_cancel', default=None)


def is_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def check_cancelled():
    event = cancel_event.get()
    if event is not None and event.is_set():
        raise KeyboardInterrupt('Cancelled by user')


def resolve_blender(explicit=None) -> str:
    chosen = explicit or os.environ.get("GEOMETRYFORGE_BLENDER")
    if chosen:
        path = Path(chosen).expanduser()
        resolved = str(path.resolve()) if path.is_file() else shutil.which(str(path))
        if not resolved:
            raise FileNotFoundError(f"Blender executable not found: {chosen}")
        return resolved
    found = shutil.which("blender")
    if not found and os.name == 'nt':
        candidates = list(Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')).glob('Blender Foundation/Blender */blender.exe'))
        found = str(sorted(candidates)[-1]) if candidates else None
    if not found:
        raise FileNotFoundError("Set GEOMETRYFORGE_BLENDER or pass --blender with the executable path")
    return found


def run(command, *, cwd, env=None, log=None, timeout=None) -> int:
    """No shell interpolation; terminate the whole process tree on interruption."""
    output = open(log, "w", encoding="utf-8") if log else None
    proc = None
    try:
        proc = subprocess.Popen([str(x) for x in command], cwd=cwd, env=env,
                                stdout=output, stderr=subprocess.STDOUT if output else None,
                                start_new_session=os.name != "nt")
        started = time.monotonic()
        while proc.poll() is None:
            check_cancelled()
            if timeout is not None and time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(0.05)
        return proc.returncode
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        if proc is not None and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else:
                import signal
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        raise
    finally:
        if output:
            output.close()
