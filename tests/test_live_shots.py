import math

import pytest

from geometryforge import live_shots as shots

ASSET = ([-3400, -1300, 0], [3400, 1300, 1700])
NACELLE = ([-2600, 1300, 600], [-1400, 2100, 1300])
BOLT = ([100, -1310, 900], [130, -1290, 930])


def config(**raw):
    return shots.settings(raw)


def test_settings_reject_typos():
    with pytest.raises(ValueError, match='unknown keys'):
        shots.settings({'pacing': {'beat_secs': 1}})
    with pytest.raises(ValueError, match='unknown sections'):
        shots.settings({'camera': {}})
    with pytest.raises(ValueError, match='stages must be'):
        shots.settings({'lookdev': {'materials': {'M_Glass': 'shiny'}}})
    with pytest.raises(ValueError, match='cue kind'):
        shots.settings({'parts': {'pads': {'cues': [{'kind': 'zoom'}]}}})
    assert shots.settings({'pacing': {'beat_seconds': 3}})['pacing']['beat_seconds'] == 3.0


def test_eye_matches_azimuth_and_elevation():
    v = shots.view((0, 0, 0), 10, azimuth=90, elevation=0)
    assert [round(c, 6) for c in shots.eye(v)] == [0, 10, 0]
    assert round(shots.eye(shots.view((0, 0, 0), 10, elevation=90))[2], 6) == 10


def test_moves_never_snap_and_respect_the_velocity_cap():
    cfg = config()
    start = shots.view(shots.centre(ASSET), 20000)
    beats = []
    view = start
    for i, (part, bounds) in enumerate((('nacelle_drive', NACELLE), ('fasteners', BOLT), ('master_hull', ASSET))):
        beats += shots.part_beats(part, bounds, ASSET, view, i, 3, cfg)
    beats += shots.lookdev_beats(ASSET, cfg, {'armor', 'glass'})
    frames = shots.frames(start, beats, cfg['pacing'])
    cap = cfg['pacing']['max_degrees_per_second']/60*1.02
    previous = start
    for frame in frames:
        assert shots.angle(previous, frame) <= cap
        previous = frame


def test_rhythm_frames_small_parts_closer_and_pulls_back_periodically():
    cfg = config()
    start = shots.view(shots.centre(ASSET), 20000)
    medium = shots.part_beats('nacelle_drive', NACELLE, ASSET, start, 0, 2, cfg)
    micro = shots.part_beats('fasteners', BOLT, ASSET, start, 1, 2, cfg)
    assert micro[0]['view']['distance'] < medium[0]['view']['distance']
    assert not any(b['kind'] == 'pull_back' for b in medium)
    fourth = shots.part_beats('trim', NACELLE, ASSET, start, 3, 2, cfg)
    assert any(b['kind'] == 'pull_back' for b in fourth)
    hero = shots.part_beats('pads', NACELLE, ASSET, start, 0, 2, config(parts={'pads': {'hero': True}}))
    assert any(b['kind'] == 'pull_back' for b in hero)


def test_stages_are_capped_and_the_last_enables_the_rest():
    beats = shots.part_beats('panels', NACELLE, ASSET, shots.view((0, 0, 0), 9000), 0, 11, config())
    stages = [b for b in beats if b['kind'] == 'stage']
    assert len(stages) == 6 and stages[-1]['last'] and not stages[0]['last']
    assert [b['kind'] for b in beats[:2]] == ['push_in', 'show']


def test_part_framing_keeps_the_part_in_view():
    cfg = config()
    target = shots.part_beats('nacelle_drive', NACELLE, ASSET, shots.view((0, 0, 0), 9000), 0, 1, cfg)[0]['view']
    radius = shots.bounds_span(NACELLE)/2
    half_fov = math.atan(18/cfg['framing']['lens_mm'])
    assert math.asin(radius/target['distance']) < half_fov


def test_cues_replace_the_default_push_in():
    cfg = config(parts={'pads': {'cues': [{'kind': 'low_glide'}, {'kind': 'orbit_arc', 'degrees': 90}]}})
    beats = shots.part_beats('pads', NACELLE, ASSET, shots.view((0, 0, 0), 9000), 0, 1, cfg)
    assert beats[0]['kind'] == 'low_glide' and beats[0]['view']['elevation'] < 0
    assert beats[1] == {'kind': 'orbit_arc', 'orbit': 90.0, 'seconds': cfg['pacing']['beat_seconds']}


def test_lookdev_skips_absent_material_groups_and_ends_on_a_turntable():
    beats = shots.lookdev_beats(ASSET, config(), {'armor'})
    steps = [b['step'] for b in beats if b['kind'] == 'lookdev']
    assert steps == ['set', 'key', 'fill', 'rim', 'top', 'armor']
    assert beats[-1]['orbit'] == 360.0


def test_resolve_follows_a_user_orbit_while_paused():
    user = shots.view((0, 0, 0), 5000, azimuth=170)
    target = shots.resolve(user, {'view': shots.view((0, 0, 0), 5000, azimuth=-170)})
    assert target['azimuth'] == 190


def test_presentation_material_maps_are_validated():
    cfg = shots.settings({'lookdev': {'parts': {'pads': 'metal'}, 'objects': {'*lamp*': 'emissive'}},
                          'studio': {'palette': {'armor': {'color': [0.9, 0.7, 0.05]}}}})
    assert cfg['lookdev']['parts'] == {'pads': 'metal'} and cfg['lookdev']['objects'] == {'*lamp*': 'emissive'}
    with pytest.raises(ValueError, match='lookdev.parts'):
        shots.settings({'lookdev': {'parts': {'pads': 'chrome'}}})
    with pytest.raises(ValueError, match='studio.palette'):
        shots.settings({'studio': {'palette': {'armor': {'gloss': 1}}}})
