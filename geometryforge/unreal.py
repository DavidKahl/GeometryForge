"""Optional editor-only imports; package safe points are never mutated here."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import uuid

from .storage import digest, fingerprint, inside, read, write
from .locking import exclusive


def resolve(explicit=None, uproject=None):
    chosen = explicit or os.environ.get('GEOMETRYFORGE_UNREAL')
    if chosen:
        path = Path(chosen).expanduser()
        if path.is_dir():
            path = path/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
        if path.is_file():
            return str(path.resolve())
        raise FileNotFoundError(f'Unreal editor not found: {chosen}')
    found = shutil.which('UnrealEditor-Cmd.exe') or shutil.which('UnrealEditor-Cmd')
    if found:
        return found
    association = read(uproject, {}).get('EngineAssociation') if uproject else None
    candidates = list(Path(os.environ.get('PROGRAMFILES','C:/Program Files')).glob('Epic Games/UE_*/Engine/Binaries/Win64/UnrealEditor-Cmd.exe'))
    launcher = Path(os.environ.get('PROGRAMDATA','C:/ProgramData'))/'Epic/UnrealEngineLauncher/LauncherInstalled.dat'
    for install in read(launcher, {}).get('InstallationList', []):
        location = Path(install['InstallLocation'])/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
        if location.is_file():
            candidates.append(location)
    if association:
        matching = [p for p in candidates if p.parents[3].name == 'UE_'+association]
        candidates = matching
    if candidates:
        return str(sorted(candidates)[-1])
    raise FileNotFoundError('Set GEOMETRYFORGE_UNREAL to the editor executable or engine installation')


def capabilities():
    try:
        executable = resolve()
        return {'available':True,'executable':executable,'optional':True,'tested_api_versions':['5.8'],
                'required_plugins':['PythonScriptPlugin','EditorScriptingUtilities'],'mode':'editor_only'}
    except FileNotFoundError as exc:
        return {'available':False,'optional':True,'error':str(exc),'tested_api_versions':['5.8']}


def import_path(root, ident):
    if not ident or any(c not in '0123456789abcdefT-Z-_' for c in ident):
        raise ValueError('Invalid import ID')
    return Path(root).resolve()/'.geometryforge/imports'/ident


def content_hashes(uproject, destination):
    if not destination.startswith('/Game/GeometryForge/'):
        raise ValueError('Managed imports must remain under /Game/GeometryForge')
    root = Path(uproject).parent/'Content'
    folder = inside(root,destination.removeprefix('/Game/'))
    return {str(p.relative_to(root)).replace('\\','/'):digest(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def execute(root, uproject, run_id=None, backend='blender', executable=None, timeout=1200, import_id=None, verify=False, review=False):
    from . import projects, engine
    from .game import verify_package
    from .process import run
    p = projects.load(root)
    uproject = Path(uproject).resolve()
    if not uproject.is_file() or uproject.suffix != '.uproject':
        raise ValueError('Select an existing Unreal .uproject')
    plugins = {s['Name']:s.get('Enabled',False) for s in read(uproject).get('Plugins',[])}
    if not plugins.get('PythonScriptPlugin') or not plugins.get('EditorScriptingUtilities'):
        raise ValueError('Enable PythonScriptPlugin and EditorScriptingUtilities in the selected Unreal project')
    with exclusive(p['root']/'.geometryforge'):
        previous = read(import_path(root,import_id)/'import.json') if import_id else None
        if verify and (not previous or previous.get('status') != 'passed'):
            raise ValueError('Verification requires a successful retained import ID')
        if previous and previous['uproject'] != str(uproject):
            raise ValueError('Import record belongs to a different Unreal project')
        run_id = previous['run'] if previous else run_id or p['state'].get('safe_points',{}).get('game')
        record = engine.record(p,run_id)
        target = record.get('targets',{}).get('game') if record else None
        if not target or target['status'] != 'passed' or backend not in target['backends']:
            raise ValueError('Unreal import requires a passed game route and selected backend')
        game = target['backends'][backend]['game']
        package = inside(root,game['manifest']).parent
        manifest = verify_package(package)
        destination = f'/Game/GeometryForge/{p["config"]["project"]["id"]}/v_{manifest["package_id"]}'
        state_file = p['root']/'.geometryforge/import-state.json'
        state = read(state_file,{'destinations':{},'attempts':{},'latest_attempt':None,'safe_import':None})
        key = fingerprint([str(uproject),destination])
        prior_id = state['destinations'].get(key)
        prior = read(import_path(root,prior_id)/'import.json') if prior_id else None
        attempt_id = state.get('attempts',{}).get(key)
        attempt = read(import_path(root,attempt_id)/'import.json') if attempt_id else None
        if prior:
            destination = prior['destination']
        elif attempt:
            destination = attempt['destination']
        current = content_hashes(uproject,destination)
        if verify and current != previous.get('content_hashes'):
            raise ValueError('Saved Unreal assets have artist changes; reconcile them before verifying this import')
        if not verify and current and (not prior and (not attempt or current != attempt.get('content_hashes')) or prior and current != prior.get('content_hashes')):
            raise ValueError('Managed Unreal content has artist changes or no matching import record; preserve it and import a new package version')
        ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        if current and not prior:
            # Keep partial imports intact and retry into a new managed namespace.
            destination = destination.split('_retry_')[0] + '_retry_' + ident[-8:]
            current = {}
        out = import_path(root,ident); out.mkdir(parents=True)
        report = {'id':ident,'status':'running','run':run_id,'backend':backend,'uproject':str(uproject),
                  'package_id':manifest['package_id'],'destination':destination,'owner_pid':os.getpid(),'failures':[],
                  'mode':'review' if review else 'verify' if verify else 'import','coverage':{'commandlet':False,'rendered_review':False,'performance_measured':False}}
        write(out/'import.json',report)
        state['latest_attempt'] = ident; write(state_file,state)
        request = {'package':str(package),'destination':destination,'report':str(out/'editor-result.json'),
                   'verify_only':verify or bool(current),'expected':previous.get('measurements') if previous else prior.get('measurements') if prior else None}
        write(out/'request.json',request)
        env = os.environ.copy(); env['GEOMETRYFORGE_UNREAL_REQUEST'] = str(out/'request.json')
        env['GEOMETRYFORGE_UNREAL_REVIEW_SCRIPT'] = str(projects.PACKAGE/'unreal_review.py')
        try:
            command=[resolve(executable,uproject),str(uproject),'-unattended','-nop4','-nosplash']
            if review:
                command += ['-RenderOffscreen','-NoSound',"-ExecCmds=py __import__('runpy').run_path(__import__('os').environ['GEOMETRYFORGE_UNREAL_REVIEW_SCRIPT'])"]
            else:
                command += [f'-ExecutePythonScript={projects.PACKAGE / "unreal_worker.py"}','-NullRHI','-ExecCmds=Interchange.FeatureFlags.Import.FBX 0']
            code = run(command,cwd=uproject.parent,
                       env=env,log=out/'editor.log',timeout=timeout,native_options=True)
            result = read(out/'editor-result.json',{'passed':False,'error':'Editor exited without verification evidence'})
            engine_log=uproject.parent/'Saved/Logs'/(uproject.stem+'.log')
            native_log=engine_log.read_text(encoding='utf-8',errors='replace') if engine_log.is_file() else ''
            if native_log:
                (out/'editor-native.log').write_text(native_log,encoding='utf-8')
            failed_materials=[line for line in native_log.splitlines() if 'Failed to compile Material' in line and destination.removeprefix('/Game/').lower() in line.replace('\\','/').lower()]
            if failed_materials:
                result.update(passed=False,error='Managed PBR material failed shader compilation; inspect editor-native.log',shader_errors=failed_materials)
            report.update(editor=result,engine_version=result.get('engine_version'),measurements=result.get('measurements',{}))
            if code or not result['passed']:
                raise ValueError(result.get('error',f'Unreal editor exited {code}; inspect editor.log'))
            report['status'] = 'passed'; report['coverage']['editor_automation'] = True
            report['coverage'].update(result.get('coverage',{}))
            if review:
                import platform
                import psutil
                report['review'] = result.get('review',{})
                report['hardware'] = {'platform':platform.platform(),'cpu':platform.processor(),'logical_cpus':os.cpu_count(),
                                      'ram_bytes':psutil.virtual_memory().total}
                import re
                gpu=re.search(r'Found D3D12 adapter 0: (.+?) \(VendorId:',native_log)
                driver=re.search(r'Driver Version: ([\d.]+)',native_log)
                report['hardware'].update(gpu=gpu.group(1) if gpu else None,driver=driver.group(1) if driver else None)
            report['content_hashes'] = content_hashes(uproject,destination)
            state['destinations'][key] = ident; state['safe_import'] = ident
        except BaseException as exc:
            report['status'] = 'cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed'
            report['failures'].append(str(exc))
        finally:
            report['content_hashes'] = content_hashes(uproject,destination)
            state.setdefault('attempts',{})[key] = ident
            write(out/'import.json',report); write(state_file,state)
        return report
