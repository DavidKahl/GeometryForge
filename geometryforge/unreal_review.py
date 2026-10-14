"""Optional offscreen editor review. Completion is driven by Slate ticks, not sleeps."""
import csv
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))


def main():
    import unreal
    try:
        from unreal_worker import execute
    except ModuleNotFoundError:
        from import_asset import execute
    request=json.loads(Path(os.environ['GEOMETRYFORGE_UNREAL_REQUEST']).read_text(encoding='utf-8'))
    result=execute(request)
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level.load_level(result['review_level']):
        raise RuntimeError('Could not load the managed review level')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assets=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.StaticMeshActor)]
    if not assets: raise RuntimeError('Review level has no mesh actors')
    bounds=[a.get_actor_bounds(False) for a in assets]
    def vector(v): return (v.x,v.y,v.z)
    low=[min(vector(center)[i]-vector(extent)[i] for center,extent in bounds) for i in range(3)]
    high=[max(vector(center)[i]+vector(extent)[i] for center,extent in bounds) for i in range(3)]
    center=unreal.Vector(*[(a+b)/2 for a,b in zip(low,high)])
    span=max(max(b-a for a,b in zip(low,high)),10)
    position=center+unreal.Vector(span*2.5,-span*3,span*2)
    camera=actors.spawn_actor_from_class(unreal.CameraActor,position)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(position,center),False)
    camera.camera_component.set_field_of_view(40)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(position,camera.get_actor_rotation())
    light=actors.spawn_actor_from_class(unreal.DirectionalLight,center+unreal.Vector(0,0,span*4))
    light.set_actor_rotation(unreal.Rotator(-45,-35,0),False)
    light.light_component.set_editor_property('intensity',8)
    fill=actors.spawn_actor_from_class(unreal.DirectionalLight,center+unreal.Vector(0,0,span*3))
    fill.set_actor_rotation(unreal.Rotator(-25,145,0),False)
    fill.light_component.set_editor_property('intensity',3)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS 0')
    unreal.SystemLibrary.execute_console_command(world,'Slate.bAllowThrottling 0')
    output=Path(request['report']).parent
    screenshot=output/'review.png'
    profiling=Path(unreal.Paths.project_saved_dir())/'Profiling/CSV'
    existing=set(profiling.glob('*.csv'))
    start=time.monotonic()
    state={'phase':'warmup','samples':[],'task':None,'stop':None}
    handle=None

    def finish(error=None):
        unreal.unregister_slate_post_tick_callback(handle)
        if error:
            result.update(passed=False,error=str(error))
        Path(request['report']).write_text(json.dumps(result,indent=2),encoding='utf-8')
        unreal.SystemLibrary.quit_editor()

    def tick(delta):
        try:
            elapsed=time.monotonic()-start
            if elapsed>120: raise RuntimeError('Offscreen review did not finish within 120 seconds')
            if state['phase']=='warmup' and elapsed>=5:
                unreal.SystemLibrary.execute_console_command(world,'csvprofile start')
                state['phase']='profile'
            elif state['phase']=='profile':
                state['samples'].append(delta*1000)
                if len(state['samples'])>=120:
                    unreal.SystemLibrary.execute_console_command(world,'csvprofile stop')
                    state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(screenshot),camera)
                    state['phase']='capture';state['stop']=time.monotonic()
            elif state['phase']=='capture' and state['task'].is_task_done() and screenshot.is_file():
                candidates=set(profiling.glob('*.csv'))-existing
                if not candidates and time.monotonic()-state['stop']<15: return
                files=[];timings={}
                for source in sorted(candidates):
                    dest=output/source.name;shutil.copy2(source,dest);files.append(str(dest))
                    rows=list(csv.reader(source.read_text(encoding='utf-8-sig').splitlines()))
                    header_index=next((i for i,row in enumerate(rows) if any('frametime' in c.lower().replace(' ','') for c in row)),None)
                    if header_index is not None:
                        header=rows[header_index]
                        for column,name in enumerate(header):
                            values=[]
                            if not any(t in name.lower() for t in ('frame','game','render','gpu','rhi')): continue
                            for row in rows[header_index+1:]:
                                if row==header or row and row[0].startswith('[HasHeaderRowAtEnd]'): break
                                if len(row)!=len(header): continue
                                try: values.append(float(row[column]))
                                except (IndexError,ValueError): pass
                            if values: timings[name]={'mean':statistics.mean(values),'max':max(values),'samples':len(values)}
                result['coverage'].update(rendered_review=True,performance_measured=bool(files))
                result['review']={'screenshot':str(screenshot),'resolution':[1280,720],'asset_instances':len(assets),
                                  'warmup_seconds':5,'editor_frames':120,'profiler_csv':files,'profiler_metrics':timings,
                                  'editor_tick_ms_median':statistics.median(state['samples']),
                                  'limits':'Editor review scene; this is not a cooked-game frame-rate guarantee. Inspect the screenshot and CSV on the target hardware.'}
                finish()
        except BaseException as exc:
            finish(exc)
    handle=unreal.register_slate_post_tick_callback(tick)


try:
    main()
except BaseException as exc:
    import unreal
    try:
        request=json.loads(Path(os.environ['GEOMETRYFORGE_UNREAL_REQUEST']).read_text(encoding='utf-8'))
        Path(request['report']).write_text(json.dumps({'passed':False,'error':str(exc)}),encoding='utf-8')
    finally:
        unreal.SystemLibrary.quit_editor()
