"""Package validated example sources, native scenes, print files and evidence."""
import argparse
from pathlib import Path
import sys
import zipfile
import json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geometryforge import projects, engine
from geometryforge.storage import inside, digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',default='validation-workspace');parser.add_argument('--output',default='dist/GeometryForge-examples-windows.zip');args=parser.parse_args()
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write('LICENSE','LICENSE')
        for folder,name in [('organizer','desk_organizer'),('rocket','falcon9')]:
            project=projects.load(Path(args.workspace)/folder)
            run=engine.record(project,project['state']['safe_point'])
            if run['status']!='passed':raise ValueError('Only validated safe points can be packaged')
            prefix=Path(name)
            archive.write(projects.PACKAGE/'examples'/name/'README.md',str(prefix/'README.md'))
            source=engine.run_path(project,run['id'])/'inputs'
            for relative,sha in run['inputs'].items():
                file=inside(source,relative)
                if digest(file)!=sha:raise ValueError('Source snapshot was modified')
                archive.write(file,str(prefix/'sources'/relative))
            evidence={'run':run['id'],'decisions':run['decisions'],'parameters':run['parameters'],'validation':run['validation'],'backends':{}}
            for backend,info in run['backends'].items():
                native=info['native']
                if not engine.artifact_ok(project,native):raise ValueError('Native snapshot was modified')
                archive.write(inside(project['root'],native['path']),str(prefix/backend/Path(native['path']).name))
                evidence['backends'][backend]={k:info[k] for k in ['version','license','native_structure','checks']}
                for part,data in info['parts'].items():
                    for item in data['artifacts']:
                        if not engine.artifact_ok(project,item):raise ValueError('Part artifact was modified')
                        filename=Path(item['path']).name
                        archive.write(inside(project['root'],item['path']),str(prefix/backend/'parts'/part/filename))
            archive.writestr(str(prefix/'evidence.json'),json.dumps(evidence,indent=2))
    print(str(target.resolve()))

if __name__=='__main__':main()
