import json
import sys
from fastapi.testclient import TestClient
from geometryforge import projects, __main__ as cli
from geometryforge.web import create_app


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, 'argv', ['geometryforge', *args])
    code = cli.main()
    return code, json.loads(capsys.readouterr().out)


def test_projects_root_resolution_order(tmp_path, monkeypatch, projects_root):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'home')
    assert projects.projects_root() == projects_root.resolve()           # environment variable wins
    monkeypatch.delenv('GEOMETRYFORGE_PROJECTS')
    checkout = (projects.ROOT / 'pyproject.toml').is_file()
    assert projects.projects_root().name == 'GF_Projects'               # default beside the checkout
    assert projects.projects_root().parent == (projects.ROOT.parent if checkout else projects.Path.home())
    projects.set_projects_root(tmp_path / 'configured')                  # then the user config
    assert projects.projects_root() == (tmp_path / 'configured').resolve()
    monkeypatch.setenv('GEOMETRYFORGE_PROJECTS', str(projects_root))
    assert projects.projects_root() == projects_root.resolve()


def test_init_name_lands_in_root_and_paths_stay_explicit(tmp_path, monkeypatch, projects_root):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'home')
    named = projects.initialize('taxi', ident='taxi')
    assert named['project'] == str((projects_root / 'taxi').resolve())
    explicit = projects.initialize(tmp_path / 'elsewhere' / 'lamp', ident='lamp')
    assert explicit['project'] == str((tmp_path / 'elsewhere' / 'lamp').resolve())
    assert not (projects_root / 'lamp').exists()
    assert projects.resolve('taxi') == (projects_root / 'taxi').resolve()   # bare names find root projects
    assert projects.load('taxi')['root'] == (projects_root / 'taxi').resolve()
    assert not projects.bare('../taxi') and not projects.bare('C:/taxi') and not projects.bare('.')


def test_config_command_sets_and_shows_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'home')
    monkeypatch.delenv('GEOMETRYFORGE_PROJECTS')
    code, shown = run_cli(monkeypatch, capsys, 'config', 'projects-root', str(tmp_path / 'mine'))
    assert code == 0 and shown['projects_root'] == str((tmp_path / 'mine').resolve())
    code, shown = run_cli(monkeypatch, capsys, 'config', 'projects-root')
    assert shown == {'projects_root': str((tmp_path / 'mine').resolve()), 'exists': True}
    code, created = run_cli(monkeypatch, capsys, 'init', 'bench', '--deliverables', 'blender')
    assert created['project'] == str((tmp_path / 'mine' / 'bench').resolve())
    code, context = run_cli(monkeypatch, capsys, 'context', 'bench')    # commands accept the bare name
    assert code == 0 and context['project'] == created['project']


def test_viewer_reports_root_and_creates_names_there(tmp_path, monkeypatch, projects_root):
    monkeypatch.setattr(projects, 'HOME', tmp_path / 'home')
    client = TestClient(create_app())
    token = client.get('/api/session').json()['token']
    assert client.get('/api/settings').json() == {'projects_root': str(projects_root.resolve())}
    added = client.post('/api/projects', headers={'x-geometryforge-token': token}, json={'path': 'kiosk', 'create': True})
    assert added.status_code == 200 and added.json()['path'] == str((projects_root / 'kiosk').resolve())
