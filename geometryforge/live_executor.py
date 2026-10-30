"""Live build job inside the GUI session: real per-part builds interleaved with a scripted reveal.

`run` is a generator; the bootstrap timer advances it and waits the yielded seconds. Geometry comes only
from the project's recipe, one part per call, and the evidence scene is saved before any look-dev."""
import contextlib
import time
from pathlib import Path

import bpy

from geometryforge import live_shots as shots
from geometryforge import blender_live_view as live
from geometryforge.native_worker import blender_finalize, blender_prepare, preparation, recipe

FPS = 60


class Edited(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


def union(a, b):
    if a is None:
        return b
    return ([min(x, y) for x, y in zip(a[0], b[0])], [max(x, y) for x, y in zip(a[1], b[1])])


def owned_objects():
    return [o for o in bpy.data.objects if o.get('gf_owner') is not None]


def scene_bounds():
    return live.bounds([o for o in owned_objects() if o.visible_get()])


@contextlib.contextmanager
def progress(api, job, state, pacing):
    """Long parts redraw as objects are finished (at most twice a second) with a slow drift, instead of freezing."""
    started, last = time.monotonic(), [0.0]

    def wrap(name):
        method = getattr(api, name)

        def inner(*args, **kwargs):
            out = method(*args, **kwargs)
            now = time.monotonic()
            if now-started > pacing['progress_redraw_after'] and now-last[0] > .5 and not job['dry']:
                last[0] = now
                drift = dict(state['view'])
                drift['azimuth'] += 2.5*(now-started)
                live.apply(drift)
                live.redraw()
            return out
        return inner

    names = ('finish', 'register_output')
    for name in names:
        setattr(api, name, wrap(name))
    try:
        yield
    finally:
        for name in names:
            delattr(api, name)


def checkpoint(job, watched):
    """Beat boundary: honour cancel, and hold while paused. Geometry edited during a pause fails the job."""
    if job['cancel']:
        raise Cancelled('Cancelled')
    if not job['pause']:
        return
    phase, job['phase'] = job['phase'], 'paused'
    before = live.fingerprint(watched()) if watched else None
    while job['pause'] and not job['cancel']:
        yield .1
    if job['cancel']:
        raise Cancelled('Cancelled')
    if watched and live.fingerprint(watched()) != before:
        raise Edited('Geometry edited while paused. The scene was saved to the live recovery folder; '
                     'bring the edits in through the revisions flow (geometryforge adopt).')
    job['phase'] = phase


def play(beats, job, state, config, actions, watched):
    for beat in beats:
        yield from checkpoint(job, watched)
        job['beat'] = beat['kind']
        if beat['kind'] in actions:
            actions[beat['kind']](beat)
        pacing = {**config['pacing'], 'speed': config['pacing']['speed']*job['speed']}
        start = live.current(state['view'])
        target = shots.resolve(start, beat)
        seconds = shots.duration(start, target, beat['seconds'], pacing)
        began = time.monotonic()
        while True:
            t = (time.monotonic()-began)/seconds
            live.apply(shots.interpolate(start, target, min(t, 1.0)))
            if t >= 1 or job['skip']:
                break
            if job['cancel']:
                raise Cancelled('Cancelled')
            yield 1/FPS
        live.apply(target)
        job['skip'] = False
        state['view'] = target


def order(request):
    if request['parts']:
        return list(request['parts']), True
    present = {o['gf_owner'] for o in owned_objects()}
    known = [p for p in request.get('known_parts') or [] if p in present]
    return known + sorted(present-set(known)), False


def run(request, job):
    config = request['live']
    job['dry'] = dry = bool(config.get('dry'))
    pacing = config['pacing']
    job['phase'] = 'preparing'
    began = time.monotonic()
    api = blender_prepare(request)
    job['build_seconds'] += time.monotonic()-began
    parts, building = order(request)
    job['total'] = len(parts)
    state = {'view': shots.view((0, 0, 0), 1000.0)}
    # Original visibility of every object the reveal touches; restored exactly before the evidence save.
    ledger = {}
    staged = {}
    if not dry:
        # Parts kept from the source scene stand as context; replayed parts start hidden and are revealed in order.
        present = {o['gf_owner'] for o in owned_objects()}
        for part in sorted(present):
            objects = live.presentable(live.owned(part))
            for obj in live.owned(part):
                ledger.setdefault(obj.name, not obj.visible_get())
            if part in parts:
                staged[part] = objects
            for obj in objects:
                obj.hide_set(part in parts)
        live.recording_layout(1000.0, config['studio'])
        existing = scene_bounds() or live.bounds([o for objects in staged.values() for o in objects])
        if existing:
            span = shots.bounds_span(existing)
            live.clip(span)
            state['view'] = shots.view(shots.centre(existing), shots.fit_distance(span, config['framing']['macro_fit']), -60, config['framing']['elevation'])
        live.apply(state['view'])
        if config.get('armed'):
            # Ready on an empty stage; the recording starts when the user presses Start (or session go).
            job.update(phase='armed', pause=True)
            while job['pause']:
                if job['cancel']:
                    raise Cancelled('Cancelled')
                yield .1
        job['phase'] = 'slate'
        yield pacing['slate_seconds']
    asset = None
    try:
        for index, part in enumerate(parts):
            job.update(part=part, index=index, phase='building' if building else 'revealing')
            if building:
                # The recipe replaces this part's objects; their visibility is whatever it sets now.
                for obj in live.owned(part):
                    ledger.pop(obj.name, None)
                began = time.monotonic()
                with progress(api, job, state, pacing):
                    recipe({**request, 'parts': [part]}, api)
                job['build_seconds'] += time.monotonic()-began
            if dry:
                continue
            # Hide before returning to the event loop so the finished part never flashes up unstaged.
            objects = live.presentable(live.owned(part)) if building else staged.get(part, [])
            reveal = live.Reveal(part, objects, ledger)
            part_bounds = live.bounds(objects)
            if part_bounds is None:
                reveal.restore()
                continue
            try:
                asset = union(union(asset, scene_bounds()), part_bounds)
                live.clip(shots.bounds_span(asset))
                job['phase'] = 'revealing'
                beats = shots.part_beats(part, part_bounds, asset, state['view'], index, reveal.stages, config)
                actions = {'show': lambda beat: reveal.show(),
                           'stage': lambda beat: reveal.stage(beat['stage'], beat['last'], pacing['max_stages'])}
                yield from play(beats, job, state, config, actions, owned_objects)
            finally:
                reveal.restore()
    finally:
        live.restore_visibility(ledger)
    began = time.monotonic()
    preparation(request, api)
    job['phase'] = 'finalizing'
    result = blender_finalize(request)
    job['build_seconds'] += time.monotonic()-began
    if not dry:
        # The reopened evidence file must never be overwritten by a stray Ctrl+S during look-dev.
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(request['out'])/'live-presentation.blend'), copy=False)
    job.update(status='passed', result={'scene': result['scene'], 'version': result['version'], 'mode': 'live'})
    if dry:
        return
    job['phase'] = 'presenting'
    # Presentation file only: design routes hide every output, but they are what the look-dev shows.
    live.present_all(sorted({o['gf_owner'] for o in owned_objects()}))
    asset = scene_bounds() or asset
    if asset is None:
        return
    live.recording_layout(shots.bounds_span(asset), config['studio'])
    live.clip(shots.bounds_span(asset))
    live.apply(state['view'])
    look = live.LookDev(asset, config)
    beats = shots.lookdev_beats(asset, config, look.available())
    yield from play(beats, job, state, config, {'lookdev': lambda beat: look.step(beat['step'])}, None)
