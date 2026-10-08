"""Collect only hash-verified artifacts from the current validated safe point."""
import json,hashlib,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
state=read(root/'.geometryforge/state.json');ident=state['safe_point']
assert ident, 'No validated safe point to release'
run=root/'.geometryforge/runs'/ident;manifest=read(run/'run.json')
assert manifest['status']=='passed' and manifest['validation']['complete']
for relative,digest in manifest['inputs'].items():
    assert sha(root/relative)==digest, f'Working input changed since safe point: {relative}'
release=root/'deliverables'/f'Astraeus_480mm_{ident}'
release.mkdir(parents=True,exist_ok=True)
def copy(source,relative):
    target=release/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
for backend,info in manifest['backends'].items():
    native=root/info['native']['path'];assert sha(native)==info['native']['sha256']
    copy(native,'native/astraeus'+native.suffix)
    for name,part in info['parts'].items():
        for art in part['artifacts']:
            source=root/art['path'];assert sha(source)==art['sha256']
            if backend=='blender' and source.suffix.lower() in ('.stl','.3mf'):
                copy(source,'prints/'+source.suffix[1:].upper()+'/'+source.name)
            elif '/checks/' in art['path']:
                copy(source,f'evidence/{backend}/{name}/{source.name}')
    # Whole-model 3MFs: the Bambu print kit and assembled models (the Blender run's copy is the release copy).
    for art in info.get('kit',{}).get('artifacts',[]) if backend=='blender' else []:
        source=root/art['path'];assert sha(source)==art['sha256']
        copy(source,'prints/kit/'+source.name)
    for name,check in info['checks'].items():
        (release/'evidence'/backend).mkdir(parents=True,exist_ok=True)
        (release/'evidence'/backend/(name+'.json')).write_text(json.dumps(check,indent=2),encoding='utf-8')
copy(run/'run.json','evidence/run.json')
for source in (run/'inputs').rglob('*'):
    if source.is_file():copy(source,'source/'+source.relative_to(run/'inputs').as_posix())
for filename in ('PRINT_AND_ASSEMBLE.md','VALIDATION.md'):
    copy(root/filename,filename)
for filename in ('README.md','AGENTS.md','CLAUDE.md','PRINT_AND_ASSEMBLE.md'):
    copy(root/filename,'source/'+filename)
copy(root.parents[1]/'LICENSE','source/LICENSE')
for folder in ('models','checks','tools','references'):
    for source in (root/folder).rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts:copy(source,'source/'+source.relative_to(root).as_posix())
provenance=read(root/'review/render-provenance.json')
assert provenance['sha256']==manifest['backends']['blender']['native']['sha256'],'Render belongs to another native revision'
for image in (root/'review').glob('astraeus_*.png'):copy(image,'previews/'+image.name)
def public(source,relative):
    # Evidence written on the build machine carries absolute paths; publish them relative to the project instead.
    text=source.read_text(encoding='utf-8')
    for path,label in ((root,'<project>'),(Path.home(),'~')):
        for form in (str(path),path.as_posix()):
            text=text.replace(json.dumps(form)[1:-1],label).replace(form,label)
    target=release/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
public(root/'review/render-provenance.json','evidence/render-provenance.json')
for summary in (root/'review').glob('slicing_*/summary.json'):
    public(summary,'evidence/'+summary.parent.name+'.json')
inventory={'run':ident,'height_mm':480,'nominal_scale':'1:150','printer':'Bambu X2D, 0.4 mm nozzle, 256 mm bed',
           'physical_model_pieces':27,'coupon_pieces':2,'stl_files':len(list((release/'prints/STL').glob('*.stl'))),
           'native_structure':{b:v['native_structure'] for b,v in manifest['backends'].items()},
           'parts':{k:v['measurements'] for k,v in manifest['backends']['blender']['parts'].items()},
           'physical_test_print':False}
(release/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
(release/'README.md').write_text('''# Astraeus Heavy Lander — 480 mm

27 model pieces and two fit-coupon rings, designed for a Bambu Lab X2D (0.4 mm nozzle, 256 mm bed).

- Start with [print and assembly instructions](PRINT_AND_ASSEMBLE.md).
- `prints/kit/kit.3mf` is a Bambu Studio project with every part on plates and the four planned filament colours; `assembled-bambu.3mf` shows the whole model in those colours. `kit-raw.3mf` and `assembled.3mf` are the same without Bambu settings.
- `prints/STL/` and `prints/3MF/` contain the same printable geometry per part in alternative formats.
- `native/` contains editable Blender and Houdini Apprentice scenes.
- `previews/` contains renders of the actual model and an exploded assembly.
- [Validation](VALIDATION.md) records mesh, fit, native-backend and local X2D slicing checks.
- `source/` is the standalone procedural GeometryForge project; install its requirements-checks.txt before rebuilding.
- `evidence/`, `inventory.json` and `SHA256SUMS.json` provide run and artifact provenance.

Print the fit coupon first. No physical test print has been performed.
''',encoding='utf-8')
hashes={p.relative_to(release).as_posix():sha(p) for p in release.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
(release/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
archive=release.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
    for source in release.rglob('*'):
        if source.is_file():zipped.write(source,source.relative_to(release))
print(json.dumps({'release':str(release),'archive':str(archive),'archive_bytes':archive.stat().st_size,'run':ident},indent=2))
