"""Offline Bambu Studio check. Reads installed presets; never connects to a printer."""
import json,subprocess,sys,zipfile,re
from pathlib import Path

app=Path('C:/Program Files/Bambu Studio')
presets=app/'resources/profiles/BBL'
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
support='--supports' in sys.argv[2:]
files=[Path(arg).resolve() for arg in sys.argv[2:] if arg!='--supports']
index={p.stem:p for p in presets.rglob('*.json')}
def resolve(name,stack=()):
    assert name not in stack,'Preset inheritance cycle'
    d=json.loads(index[name].read_text(encoding='utf-8'));parent=d.get('inherits');merged={}
    if parent:merged.update(resolve(parent,stack+(name,)))
    for include in d.get('include',[]):merged.update(resolve(include,stack+(name,)))
    merged.update(d)
    for key in ('inherits','include'):merged.pop(key,None)
    return merged

settings={
    'machine':resolve('Bambu Lab X2D 0.4 nozzle'),
    'process':resolve('0.16mm High Quality @BBL X2D'),
    'filament':resolve('Generic PLA @BBL X2D 0.4 nozzle')}
settings['process'].update(wall_loops='3',sparse_infill_density='15%',enable_support='0',brim_type='outer_only',brim_width='3')
if support:settings['process'].update(enable_support='1',support_type='normal(auto)',support_on_build_plate_only='1')
for kind,data in settings.items():(out/(kind+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
command=[str(app/'bambu-studio.exe'),'--debug','2','--arrange','1',
         '--load-settings',str(out/'machine.json')+';'+str(out/'process.json'),
         '--load-filaments',str(out/'filament.json'),'--curr-bed-type','Textured PEI Plate',
         '--slice','0','--export-3mf',str(out/'slice_check.3mf'),*map(str,files)]
with (out/'slicer.log').open('w',encoding='utf-8') as log:
    result=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=600,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
summary={'command':command,'exit_code':result.returncode,'source_files':[str(p) for p in files],
         'build_plate_supports':support,
         'printer_profile':settings['machine']['name'],'process':settings['process']['name'],
         'filament':'Generic PLA (assumed for offline check)','no_printer_connection':True}
if (out/'slice_check.3mf').is_file():
    with zipfile.ZipFile(out/'slice_check.3mf') as archive:
        gcode=[n for n in archive.namelist() if n.endswith('.gcode')]
        summary['gcode_files']=gcode
        summary['gcode_bytes']=sum(archive.getinfo(n).file_size for n in gcode)
        summary['statistics']={}
        for name in gcode:
            code=archive.read(name).decode('utf-8',errors='replace')
            summary['statistics'][name]=[line for line in code.splitlines() if line.startswith(';') and any(k in line.lower() for k in ('total estimated time','filament used [g]','total layer number','total filament weight'))]
summary['passed']=result.returncode==0 and bool(summary.get('gcode_bytes'))
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
