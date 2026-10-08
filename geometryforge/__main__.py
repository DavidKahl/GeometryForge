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
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('install-skill'); p.add_argument('--target'); p.add_argument('--user', action='store_true'); p.add_argument('--harness', choices=['codex','claude','both'], default='both')
    sub.add_parser('doctor')
    p = sub.add_parser('init'); p.add_argument('destination'); p.add_argument('--example', choices=['desk_organizer']); p.add_argument('--id'); p.add_argument('--deliverables', choices=['geometry','blender','houdini','both'], default='both'); p.add_argument('--backend', choices=['blender','houdini'], default='blender'); p.add_argument('--brief', default=''); p.add_argument('--bed', nargs=3,type=float,default=[220,220,250])
    for name in ['context','status','history','register']:
        p = sub.add_parser(name); p.add_argument('project', nargs='?', default='.')
    for name in ['plan','run','verify']:
        p = sub.add_parser(name); p.add_argument('project', nargs='?', default='.'); p.add_argument('--backend',choices=['blender','houdini']); p.add_argument('--parts',nargs='*',default=[]); p.add_argument('--full',action='store_true'); p.add_argument('--source',choices=['auto','scene','code'],default='auto'); p.add_argument('--timeout',type=int,default=900); p.add_argument('--blender'); p.add_argument('--houdini')
    p=sub.add_parser('restore'); p.add_argument('project',nargs='?',default='.'); p.add_argument('--run')
    p=sub.add_parser('adopt'); p.add_argument('project'); p.add_argument('--backend',choices=['blender','houdini'],required=True); p.add_argument('--file',required=True)
    p=sub.add_parser('viewer'); p.add_argument('--port',type=int,default=8743)
    p=sub.add_parser('session'); p.add_argument('action',choices=['status','stop'])
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
