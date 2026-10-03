import sys,json,runpy,tomllib,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=json.loads(Path(sys.argv[1]).read_text())
config=tomllib.loads((root/'project.toml').read_text())
p=json.loads((root/'parameters.json').read_text());objects={}
for obj in data['objects']:objects.setdefault(obj['part'],[]).append(obj)
verify=runpy.run_path(str(root/'checks/verify.py'))['verify']
for name,check in config['checks'].items():
    try:print(name,verify({'check':name,'parameters':p,'objects':{part:objects[part] for part in check['parts']}}))
    except Exception as exc: print(name,'FAILED',str(exc));traceback.print_exc(limit=2)
