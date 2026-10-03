"""Fast native prototype check for one part; never promotes a project safe point."""
import sys,json
from pathlib import Path
project=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(project.parents[1]),str(project/'models')]
from geometryforge.blender_scene import initialize
from geometryforge.native_api import Blender
from geometryforge.blender_worker import meshes
from assembly import build_parts
initialize();part=sys.argv[sys.argv.index('--')+1]
build_parts(json.loads((project/'parameters.json').read_text()),[part],Blender())
output=project/'review'/('probe_'+part+'.json')
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({'objects':meshes()}))
