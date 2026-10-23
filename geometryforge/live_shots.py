"""Scripted viewport choreography for live builds. Pure math: imported by host tests and Blender."""
import math

BEATS = {'push_in', 'orbit_arc', 'pull_back', 'low_glide', 'top_down', 'show', 'stage', 'settle', 'beauty_pause', 'lookdev'}
PACING = {'beat_seconds': 2.0, 'speed': 1.0, 'max_degrees_per_second': 40.0, 'macro_every': 4, 'slate_seconds': 3.0,
          'max_stages': 6, 'progress_redraw_after': 3.0, 'turntable_seconds': 14.0}
FRAMING = {'elevation': 22.0, 'micro_ratio': 0.08, 'medium_fit': 1.8, 'micro_fit': 4.0, 'macro_fit': 1.25, 'lens_mm': 50.0}
LOOKDEV = ['set', 'key', 'fill', 'rim', 'top', 'dark', 'armor', 'inserts', 'metal', 'glass', 'emissive', 'turntable']
MATERIAL_STAGES = ('dark', 'armor', 'inserts', 'metal', 'glass', 'emissive')
SECTIONS = {'pacing', 'framing', 'parts', 'lookdev', 'studio', 'hud'}


def settings(raw=None):
    """Defaults merged with a project's presentation/live.toml; unknown keys are errors, not silent typos."""
    raw = raw or {}
    unknown = set(raw) - SECTIONS
    if unknown:
        raise ValueError(f'live.toml: unknown sections {sorted(unknown)}')
    result = {'pacing': dict(PACING), 'framing': dict(FRAMING), 'parts': {}, 'hud': bool(raw.get('hud', False)),
              'lookdev': {'sequence': list(LOOKDEV), 'materials': {}, 'parts': {}, 'objects': {}}, 'studio': {}}
    for name, defaults in (('pacing', PACING), ('framing', FRAMING)):
        extra = set(raw.get(name, {})) - set(defaults)
        if extra:
            raise ValueError(f'live.toml [{name}]: unknown keys {sorted(extra)}')
        result[name].update({k: float(v) if isinstance(defaults[k], float) else int(v) for k, v in raw.get(name, {}).items()})
    lookdev = raw.get('lookdev', {})
    extra = set(lookdev) - {'sequence', 'materials', 'parts', 'objects'}
    if extra:
        raise ValueError(f'live.toml [lookdev]: unknown keys {sorted(extra)}')
    if 'sequence' in lookdev:
        bad = [s for s in lookdev['sequence'] if s not in LOOKDEV]
        if bad:
            raise ValueError(f'live.toml [lookdev] sequence: unknown steps {bad}')
        result['lookdev']['sequence'] = list(lookdev['sequence'])
    # materials: existing material name pattern -> stage. parts / objects: presentation materials from the palette
    # for scenes without materials (design routes); object name patterns win over parts.
    for key in ('materials', 'parts', 'objects'):
        bad = {k: v for k, v in lookdev.get(key, {}).items() if v not in MATERIAL_STAGES}
        if bad:
            raise ValueError(f'live.toml [lookdev.{key}]: stages must be one of {list(MATERIAL_STAGES)}, got {bad}')
        result['lookdev'][key] = dict(lookdev.get(key, {}))
    for stage, spec in raw.get('studio', {}).get('palette', {}).items():
        if stage not in MATERIAL_STAGES or set(spec) - {'color', 'roughness', 'metallic', 'transmission', 'emission'}:
            raise ValueError(f'live.toml [studio.palette.{stage}]: stage must be one of {list(MATERIAL_STAGES)} with keys '
                             'color, roughness, metallic, transmission, emission')
    for part, spec in raw.get('parts', {}).items():
        extra = set(spec) - {'hero', 'cues'}
        if extra:
            raise ValueError(f'live.toml [parts.{part}]: unknown keys {sorted(extra)}')
        for cue in spec.get('cues', []):
            if cue.get('kind') not in ('push_in', 'low_glide', 'top_down', 'orbit_arc'):
                raise ValueError(f'live.toml [parts.{part}] cue kind must be push_in, low_glide, top_down or orbit_arc')
        result['parts'][part] = {'hero': bool(spec.get('hero', False)), 'cues': list(spec.get('cues', []))}
    result['studio'] = dict(raw.get('studio', {}))
    return result


def view(center, distance, azimuth=-60.0, elevation=22.0):
    return {'center': [float(c) for c in center], 'distance': float(distance), 'azimuth': float(azimuth), 'elevation': float(elevation)}


def eye(v):
    a, e = math.radians(v['azimuth']), math.radians(v['elevation'])
    return [c + v['distance']*d for c, d in zip(v['center'], (math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e)))]


def bounds_span(bounds):
    low, high = bounds
    return max(math.dist(low, high), 1.0)


def centre(bounds):
    return [(a+b)/2 for a, b in zip(*bounds)]


def fit_distance(span, fit, lens_mm=50.0):
    """Perspective distance that frames a sphere of diameter span*fit (36 mm sensor, as in review presets)."""
    return (span*fit/2)/math.tan(math.atan(18/lens_mm))


def ease(t):
    """Smoothstep: cubic ease-in-out whose peak velocity is 1.5x the mean."""
    t = min(max(t, 0.0), 1.0)
    return t*t*(3-2*t)


def shortest(a, b):
    return a + ((b-a+180) % 360 - 180)


def resolve(start, beat):
    """Target view of a beat from the actual current view (the user may have orbited while paused)."""
    if 'view' in beat:
        target = dict(beat['view'])
        target['azimuth'] = shortest(start['azimuth'], target['azimuth'])
        return target
    target = dict(start)
    target['azimuth'] = start['azimuth'] + beat.get('orbit', 0.0)
    for key in ('center', 'distance', 'elevation'):
        if key in beat:
            target[key] = beat[key]
    return target


def angle(a, b):
    """Degrees the eye direction sweeps between two views; orbits count their full arc."""
    return math.hypot((b['azimuth']-a['azimuth'])*math.cos(math.radians((a['elevation']+b['elevation'])/2)), b['elevation']-a['elevation'])


def duration(a, b, seconds, pacing):
    # Cubic ease peaks at 1.5x the mean angular velocity; size the move so the peak respects the cap.
    zoom = abs(math.log(max(b['distance'], 1e-6)/max(a['distance'], 1e-6)))*30
    needed = 1.5*max(angle(a, b), zoom)/pacing['max_degrees_per_second']
    return max(seconds, needed)/pacing['speed']


def interpolate(a, b, t):
    k = ease(t)
    return {'center': [x+(y-x)*k for x, y in zip(a['center'], b['center'])],
            'distance': a['distance']*(b['distance']/a['distance'])**k,
            'azimuth': a['azimuth']+(b['azimuth']-a['azimuth'])*k,
            'elevation': a['elevation']+(b['elevation']-a['elevation'])*k}


def side_azimuth(part_bounds, asset_bounds, current):
    """Look at the part from its own side of the asset, staying near the current azimuth for centred parts."""
    pc, ac = centre(part_bounds), centre(asset_bounds)
    dx, dy = pc[0]-ac[0], pc[1]-ac[1]
    if math.hypot(dx, dy) < .12*bounds_span(asset_bounds):
        return current
    side = math.degrees(math.atan2(dy, dx))
    # Three-quarter on the part's side rather than straight-on.
    return min((side-35, side+35), key=lambda a: abs(shortest(current, a)-current))


def part_beats(part, part_bounds, asset_bounds, current, index, stages, config):
    """Beats for one freshly built part: frame, base mesh, modifier stages, inspection, periodic macro reveal."""
    pacing, framing = config['pacing'], config['framing']
    spec = config['parts'].get(part, {})
    beat = pacing['beat_seconds']*(1.5 if spec.get('hero') else 1.0)
    span, asset = bounds_span(part_bounds), bounds_span(asset_bounds)
    micro = span < framing['micro_ratio']*asset
    fit = framing['micro_fit'] if micro else framing['medium_fit']
    target = view(centre(part_bounds), fit_distance(span, fit, framing['lens_mm']),
                  side_azimuth(part_bounds, asset_bounds, current['azimuth']), framing['elevation'])
    beats = []
    cues = spec.get('cues') or [{'kind': 'push_in'}]
    for cue in cues:
        if cue['kind'] == 'orbit_arc':
            beats.append({'kind': 'orbit_arc', 'orbit': float(cue.get('degrees', 60)), 'seconds': beat})
            continue
        shot = dict(target)
        shot['elevation'] = {'low_glide': -12.0, 'top_down': 72.0}.get(cue['kind'], float(cue.get('elevation', framing['elevation'])))
        if 'azimuth' in cue:
            shot['azimuth'] = float(cue['azimuth'])
        beats.append({'kind': cue['kind'], 'view': shot, 'seconds': beat})
    beats.append({'kind': 'show', 'seconds': .6*beat})
    count = min(stages, int(pacing['max_stages']))
    for n in range(count):
        beats.append({'kind': 'stage', 'stage': n, 'last': n == count-1, 'orbit': 8.0, 'seconds': .55*beat})
    if not count:
        beats.append({'kind': 'stage', 'stage': 0, 'last': True, 'orbit': 8.0, 'seconds': .3*beat})
    beats.append({'kind': 'orbit_arc', 'orbit': 70.0 if not micro else 45.0, 'seconds': 1.2*beat})
    beats.append({'kind': 'settle', 'seconds': .2*beat})
    if spec.get('hero') or (index+1) % int(pacing['macro_every']) == 0:
        beats.extend(macro_beats(asset_bounds, config, 120.0))
    return beats


def macro_beats(asset_bounds, config, arc):
    pacing, framing = config['pacing'], config['framing']
    whole = view(centre(asset_bounds), fit_distance(bounds_span(asset_bounds), framing['macro_fit'], framing['lens_mm']),
                 -60.0, framing['elevation'])
    return [{'kind': 'pull_back', 'center': whole['center'], 'distance': whole['distance'], 'elevation': whole['elevation'],
             'orbit': 30.0, 'seconds': 1.2*pacing['beat_seconds']},
            {'kind': 'orbit_arc', 'orbit': arc, 'seconds': 2*pacing['beat_seconds']},
            {'kind': 'beauty_pause', 'seconds': .8*pacing['beat_seconds']}]


def lookdev_beats(asset_bounds, config, available):
    """Clay to final: studio set, lights one by one, material groups in order, then a turntable."""
    pacing = config['pacing']
    beats = macro_beats(asset_bounds, config, 45.0)[:1]
    for step in config['lookdev']['sequence']:
        if step in MATERIAL_STAGES and step not in available:
            continue
        if step == 'turntable':
            beats.append({'kind': 'orbit_arc', 'orbit': 360.0, 'seconds': pacing['turntable_seconds']})
            continue
        beats.append({'kind': 'lookdev', 'step': step, 'seconds': .3*pacing['beat_seconds']})
        beats.append({'kind': 'orbit_arc', 'orbit': 40.0, 'seconds': 1.4*pacing['beat_seconds']})
    return beats


def frames(start, beats, pacing, fps=60):
    """Every viewport state a beat list produces (host-side simulation of the Blender driver)."""
    current, out = dict(start), []
    for beat in beats:
        target = resolve(current, beat)
        steps = max(1, round(duration(current, target, beat['seconds'], pacing)*fps))
        out.extend(interpolate(current, target, (i+1)/steps) for i in range(steps))
        current = target
    return out
