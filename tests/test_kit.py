import pytest
import trimesh
from geometryforge.kit import write_kits, bambu_package, bambu_executable, read_back
from geometryforge import engine
from geometryforge.storage import read, write

def part(name, filament, x=0, rotation=(0, 0, 0)):
    mesh = trimesh.creation.box([20, 10, 30])
    mesh.apply_translation([x, 0, 15])
    return dict(name=name, part=name.split(':')[0], vertices=mesh.vertices.tolist(), faces=mesh.faces.tolist(),
                filament=filament, print_rotation_deg=list(rotation), expected_bodies=1)

PLAN = {'bed_mm': [256, 256], 'filaments': [{'slot': 1, 'name': 'Body', 'colour': '#BFCAD1', 'preset': 'Generic PLA @BBL X2D 0.4 nozzle'},
                                            {'slot': 2, 'name': 'Accent', 'colour': '#2C3842', 'preset': 'Generic PLA @BBL X2D 0.4 nozzle'}]}

def grouped():
    # 'stripe' shares part 'hull' but prints in slot 2, so the hull is a two-filament part.
    return {'hull': [part('hull', 1), {**part('stripe', 2, x=0), 'part': 'hull'}], 'fin': [part('fin', 2, x=40, rotation=(90, 0, 0))]}

def test_whole_model_files_keep_filament_slots(tmp_path):
    result = write_kits(grouped(), tmp_path, PLAN)
    assert result['parts'] == {'fin': [2], 'hull': [1, 2]}
    for name in ('assembled.3mf', 'kit-raw.3mf'):
        assert read_back(tmp_path / name)['extruders'] == {'fin': [2], 'hull': [1, 2]}

def test_undeclared_filament_slot_is_refused(tmp_path):
    with pytest.raises(ValueError, match='not declared'):
        write_kits(grouped(), tmp_path, {**PLAN, 'filaments': PLAN['filaments'][:1]})

def test_bambu_step_is_skipped_unless_requested(tmp_path):
    write_kits(grouped(), tmp_path, PLAN)
    assert 'skipped' in bambu_package(tmp_path, PLAN, {'fin': [2], 'hull': [1, 2]})

@pytest.mark.skipif(not bambu_executable(), reason='Bambu Studio not installed')
def test_bambu_project_has_plates_and_colours(tmp_path):
    plan = {**PLAN, 'bambu': {'machine': 'Bambu Lab X2D 0.4 nozzle', 'process': '0.16mm High Quality @BBL X2D'}}
    used = write_kits(grouped(), tmp_path, plan)['parts']
    result = bambu_package(tmp_path, plan, used)
    assert result['files']['kit.3mf'] == {'plates': 1, 'instances': 2}
    back = read_back(tmp_path / 'kit.3mf')
    assert back['extruders'] == used and back['colours'][:2] == ['#BFCAD1', '#2C3842']

def test_runs_record_whole_model_files(project):
    root, _ = project
    result = engine.execute(root, backend='blender')
    kit = result['backends']['blender']['kit']
    assert {a['path'].rsplit('/', 1)[1] for a in kit['artifacts']} == {'assembled.3mf', 'kit-raw.3mf'}
    assert kit['parts'] == {'a': [1], 'b': [1]} and 'skipped' in kit['bambu']
