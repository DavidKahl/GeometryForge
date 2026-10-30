"""Background Blender runner for the opt-in live test: drives live_executor.run without a GUI (dry mode)."""
import importlib.util
import json
from pathlib import Path
import sys

package_dir = Path(__file__).resolve().parents[1]/'geometryforge'
spec = importlib.util.spec_from_file_location('geometryforge', package_dir/'__init__.py', submodule_search_locations=[str(package_dir)])
module = importlib.util.module_from_spec(spec)
sys.modules['geometryforge'] = module
spec.loader.exec_module(module)

from geometryforge import live_executor

request = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
job = {'cancel': False, 'pause': False, 'skip': False, 'speed': 1.0, 'build_seconds': 0.0, 'status': 'running'}
for _ in live_executor.run(request, job):
    pass
assert job['status'] == 'passed', job
