"""Native execution adapters; the calling agent owns orchestration and recipes."""
import json
from pathlib import Path
from .storage import write, read
from .projects import PACKAGE
from .process import resolve_blender, run
from .worker_env import worker_environment

def run_native(backend, out, entry, parameters, parts, source, timeout, executable=None):
    request = {"action": "native", "out": str(out), "entry": str(entry), "parameters": parameters,
               "parts": parts, "source": str(source) if source else None}
    if backend == "blender":
        path = out / "request.json"
        write(path, request)
        code = run([resolve_blender(executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", PACKAGE / "native_worker.py", "--", path],
                   cwd=entry.parent, env=worker_environment(), log=out / "blender.log", timeout=timeout)
        if code:
            raise RuntimeError(f"Blender failed ({code}); see {out / 'blender.log'}")
        return read(out / "result.json")
    if backend == "houdini":
        from .houdini import request as rpc
        rpc(request, executable, timeout)
        return read(out / "result.json")
    raise ValueError(f"Unknown backend {backend}")

def doctor():
    result = {}
    from .houdini import resolve
    for name, fn in (("blender", resolve_blender), ("houdini", resolve)):
        try:
            result[name] = {"available": True, "executable": fn()}
        except (FileNotFoundError, ValueError) as exc:
            result[name] = {"available": False, "error": str(exc)}
    return result
