"""Diagnostic native runner, including Boolean construction operands."""
import sys,json
from pathlib import Path
def build_parts(p,parts,api):
    import hou
    project=Path(__file__).resolve().parents[1];folder=project/'models'
    prior=dict(sys.modules);sys.path.insert(0,str(folder))
    try:
        from assembly import build_parts as build
        build(p,parts,api)
        out=Path(p['probe_output']);out.mkdir(parents=True,exist_ok=True)
        summary={}
        for geo in hou.node('/obj/geometryforge').children():
            if geo.userData('gf_owner')!='leg_1':continue
            for node in geo.children():
                if node.type().name() not in ('boolean','polyextrude::2.0','polyextrude','null'):continue
                node.cook(force=True)
                path=out/(geo.name()+'_'+node.name()+'.obj');node.geometry().saveToFile(str(path))
                summary[str(path)]={'type':node.type().name(),'warnings':node.warnings(),'errors':node.errors()}
        (out/'nodes.json').write_text(json.dumps(summary,indent=2))
    finally:
        sys.path.remove(str(folder))
        for name,module in list(sys.modules.items()):
            file=getattr(module,'__file__',None)
            if file and Path(file).resolve().is_relative_to(folder):
                if name in prior:sys.modules[name]=prior[name]
                else:sys.modules.pop(name,None)
