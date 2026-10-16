"""Contract details of format 3 and typed checks that need no native application."""
import pytest

from geometryforge import native_api, projects, targets
from geometryforge.storage import read, write


def test_build_order_puts_dependencies_first():
    config = {'parts': {'body': {'depends': ['master_hull']}, 'lens': {'depends': ['body']},
                        'master_hull': {}, 'skirt': {'depends': ['master_hull']}}}
    assert projects.build_order(config, {'body', 'lens', 'master_hull', 'skirt'}) == ['master_hull', 'body', 'lens', 'skirt']
    assert projects.build_order(config, {'skirt', 'body'}) == ['body', 'skirt']
    with pytest.raises(ValueError, match='Cyclic'):
        projects.build_order({'parts': {'a': {'depends': ['b']}, 'b': {'depends': ['a']}}}, {'a', 'b'})


def typed(project, extra, version=2):
    root, _ = project
    targets.migrate(root)
    text = (root / 'project.toml').read_text(encoding='utf-8').replace('format_version = 2', f'format_version = {version}')
    (root / 'project.toml').write_text(text + extra, encoding='utf-8')
    return root


@pytest.mark.parametrize('extra,message', [
    ('\n[checks.bad]\nkind = "seam"\nsource = "checks/verify.py"\nparts = ["a"]\n', 'replaces source'),
    ('\n[checks.bad]\nkind = "flush"\nparts = ["a"]\n', 'Unknown check kind'),
    ('\n[checks.bad]\nkind = "seam"\nparts = ["a"]\nmode = "warn"\n', 'mode'),
    ('\n[checks.bad]\nkind = "seam"\nparts = ["missing"]\n', 'Invalid check'),
])
def test_invalid_typed_checks(project, extra, message):
    root = typed(project, extra)
    with pytest.raises(ValueError, match=message):
        projects.load(root)


def test_typed_check_defaults_and_threshold_inputs(project):
    root = typed(project, '\n[checks.iou]\nkind = "global"\nparts = ["a"]\n[checks.iou.spec]\ntest = "silhouette_iou"\ncamera = "primary"\n'
                          '\n[checks.closed]\nkind = "global"\nparts = ["a"]\n[checks.closed.spec]\ntest = "open_edges"\n')
    params = read(root / 'parameters.json')
    params['gf_thresholds'] = {'global': {'open_edges_max': 2}}
    write(root / 'parameters.json', params)
    checks = projects.load(root)['config']['checks']
    assert checks['iou']['mode'] == 'measure' and checks['closed']['mode'] == 'enforce'
    assert 'gf_thresholds' in checks['closed']['parameters']
    assert 'checks/verify.py' in projects.inputs(projects.load(root))  # legacy checkers still hashed


def test_typed_checks_need_format_two(project):
    root, _ = project
    (root / 'project.toml').write_text((root / 'project.toml').read_text() + '\n[checks.bad]\nkind = "seam"\nparts = ["a"]\n')
    with pytest.raises(ValueError, match='format 2'):
        projects.load(root)


def test_houdini_surfacing_is_explicitly_blender_only():
    with pytest.raises(NotImplementedError, match='Blender-only'):
        native_api.Houdini({'target': 'design'}).surf


def test_unknown_threshold_class_and_non_numeric_values():
    from geometryforge.thresholds import resolve
    with pytest.raises(ValueError):
        resolve({}, 'paint')
    with pytest.raises(ValueError):
        resolve({'gf_thresholds': {'seam': {'step_mm': 'small'}}}, 'seam')
    assert resolve({}, 'mating', {'lap_min_mm': 47.5})['lap_min_mm'] == 47.5
