"""Package a successful run and project sources without including older outputs."""
import hashlib
import argparse
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, help='New archive path; refuses to overwrite')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    root = project.parents[1]
    from geometryforge.projects import read_project
    from geometryforge.legacy import output_root
    output = output_root(read_project(project))
    manifest = json.loads((output / 'build.json').read_text())
    if manifest['status'] != 'passed':
        raise SystemExit('Latest build did not pass; refusing to package stale results.')
    run = Path(manifest['output']).resolve()
    if not run.is_relative_to(output.resolve()):
        raise SystemExit('Run is outside the project output directory.')
    for name in ('office_hub', 'meshes', 'roundtrip'):
        report = json.loads((run / 'checks' / (name + '.json')).read_text())
        if not report['passed']:
            raise SystemExit(f'{name} did not pass.')
    for relative, expected in manifest['inputs'].items():
        # Docs/render tooling may evolve after a build, modeling inputs may not.
        if relative == 'project.toml' or Path(relative).parts[0] in ('models', 'checks'):
            actual = hashlib.sha256((project / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise SystemExit(f'Rebuild required: {relative} changed.')
    files = {}
    for directory in ('models', 'prints', 'previews', 'checks'):
        for path in (run / directory).rglob('*'):
            if path.is_file():
                files[path.relative_to(run).as_posix()] = path
    for path in project.rglob('*'):
        if path.is_file() and not any(x in ('out','__pycache__','.git') for x in path.relative_to(project).parts) and path.suffix != '.pyc':
            files['project/' + path.relative_to(project).as_posix()] = path
    if (run/'parameters.json').exists():
        files['project/parameters.json'] = run/'parameters.json'
    files['build.json'] = output / 'build.json'
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in sorted(files.items())}
    archive = args.out or output / 'office_led_hub_v2.zip'
    if args.out and archive.exists():
        raise SystemExit(f'Archive already exists: {archive}')
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, path in sorted(files.items()):
            package.write(path, name)
        package.writestr('package_manifest.json', json.dumps({
            'project': project.name, 'run': run.name, 'sha256': hashes,
            'note': 'Presentation views and documentation are packaged after the geometry build.'
        }, indent=2))
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise SystemExit('Archive integrity check failed.')
    print(f'{archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
