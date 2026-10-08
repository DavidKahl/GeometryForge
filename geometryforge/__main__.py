import argparse
import json
import sys
from . import __version__

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog='geometryforge')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--json', action='store_true', help='Explicit machine-readable mode (all commands already emit JSON)')
    sub = parser.add_subparsers(dest='command', required=True, metavar='command')
    p = sub.add_parser('install-skill', help='Install the agent skill for Claude Code and/or Codex')
    p.add_argument('--target', help='Workspace folder to install into (default: current folder)')
    p.add_argument('--user', action='store_true', help='Install for your user account instead of one workspace')
    p.add_argument('--harness', choices=['codex','claude','both'], default='both', help='Which agent harness to install for')
    sub.add_parser('doctor', help='Report the Blender, Houdini and Bambu Studio executables that will be used')
    p = sub.add_parser('init', help='Create a new project folder (empty or from a bundled example)')
    p.add_argument('destination', help='Empty or new project folder')
    p.add_argument('--example', choices=['desk_organizer'], help='Start from a bundled example')
    p.add_argument('--id', help='Project ID (lowercase, underscores; default: folder name)')
    p.add_argument('--deliverables', choices=['geometry','blender','houdini','both'], default='both', help='Native files to produce')
    p.add_argument('--backend', choices=['blender','houdini'], default='blender', help="Application used when deliverables is 'geometry'")
    p.add_argument('--brief', default='', help='One-line design brief')
    p.add_argument('--bed', nargs=3, type=float, default=[220,220,250], metavar=('X','Y','Z'), help='Printer build volume in mm')
    descriptions = {'context': 'Show decisions, parameters, safe point and backend state (start here)', 'status': 'Alias of context',
                    'history': 'List all run records, newest first', 'register': 'Add an existing project to the viewer catalog'}
    for name, text in descriptions.items():
        p = sub.add_parser(name, help=text); p.add_argument('project', nargs='?', default='.', help='Project folder (default: current folder)')
    descriptions = {'plan': 'Show which parts and checks a run would rebuild, without running', 'run': 'Build changed parts, export, check and record a run',
                    'verify': 'Re-check the saved native scenes without rebuilding (same as run --source scene)'}
    for name, text in descriptions.items():
        p = sub.add_parser(name, help=text)
        p.add_argument('project', nargs='?', default='.', help='Project folder (default: current folder)')
        p.add_argument('--backend', choices=['blender','houdini'], help='Limit to one application')
        p.add_argument('--parts', nargs='*', default=[], help='Rebuild these part IDs (plus their dependents)')
        p.add_argument('--full', action='store_true', help='Ignore reusable evidence and re-run every export and check')
        p.add_argument('--source', choices=['auto','scene','code'], default='auto', help='Use the saved native scene, regenerate from code, or decide automatically')
        p.add_argument('--timeout', type=int, default=900, help='Seconds per native operation')
        p.add_argument('--blender', help='Blender executable (overrides GEOMETRYFORGE_BLENDER)')
        p.add_argument('--houdini', help='Houdini executable (overrides GEOMETRYFORGE_HOUDINI)')
    p = sub.add_parser('restore', help='Copy a safe point into a new working folder (current work is kept)')
    p.add_argument('project', nargs='?', default='.', help='Project folder (default: current folder)'); p.add_argument('--run', help='Run ID (default: the safe point)')
    p = sub.add_parser('adopt', help='Make a saved .blend/.hip file the working scene for a backend')
    p.add_argument('project', help='Project folder'); p.add_argument('--backend', choices=['blender','houdini'], required=True, help='Application the file belongs to')
    p.add_argument('--file', required=True, help='Saved native file to copy in')
    p = sub.add_parser('viewer', help='Start the local browser viewer (http://127.0.0.1:8743)'); p.add_argument('--port', type=int, default=8743, help='Port to listen on')
    p = sub.add_parser('session', help='Inspect or stop the managed Houdini session'); p.add_argument('action', choices=['status','stop'])
    args=parser.parse_args()
    try:
        from . import projects, engine
        if args.command == 'install-skill':
            from .install import install
            result=install(args.target,args.harness,args.user)
        elif args.command == 'doctor':
            from .backends import doctor
            result=doctor()
        elif args.command == 'init':
            result=projects.initialize(args.destination,args.example,args.id,args.deliverables,args.backend,args.brief,args.bed)
        elif args.command in ('context','status'):
            result=engine.context(args.project)
        elif args.command == 'register':
            result=projects.register(args.project)
        elif args.command == 'history':
            from .storage import read
            result=[read(p) for p in sorted((projects.load(args.project)['root']/'.geometryforge/runs').glob('*/run.json'),reverse=True)]
        elif args.command == 'plan':
            result=engine.plan(args.project,args.backend,args.parts,args.full,args.source)
        elif args.command in ('run','verify'):
            source='scene' if args.command=='verify' else args.source
            result=engine.execute(args.project,args.backend,args.parts,args.full,source,args.timeout,{'blender':args.blender,'houdini':args.houdini})
        elif args.command == 'restore':
            result=engine.restore(args.project,args.run)
        elif args.command == 'adopt':
            result=engine.adopt(args.project,args.backend,args.file)
        elif args.command == 'session':
            from .houdini import current, request, terminate
            current_session=current()
            if args.action=='stop' and current_session:
                from .houdini import STATE
                request({'action':'recover','out':str(STATE/'stop')})
                terminate(current_session)
            result={'running':bool(current_session) if args.action=='status' else False}
        else:
            from .web import serve
            serve(args.port); return
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if isinstance(result,dict) and result.get('status') in ('failed','cancelled','candidate'):
            return 2
        return 0
    except Exception as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
