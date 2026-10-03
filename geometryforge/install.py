"""Copy one canonical skill into either harness, with conflict detection."""
from pathlib import Path
import shutil
from .projects import PACKAGE
from .storage import digest, read, write, inside

def install(target=None, harness="both", user=False):
    root = Path.home() if user else Path(target or '.').resolve()
    names = ["codex", "claude"] if harness == "both" else [harness]
    source = PACKAGE / "skill"
    files = {str(p.relative_to(source)): p for p in source.rglob('*') if p.is_file()}
    destinations = [root / ('.agents/skills' if name == 'codex' else '.claude/skills') / 'geometryforge' for name in names]
    # Preflight every destination before writing anything.
    for dest in destinations:
        tracked = read(dest / '.geometryforge-install.json', {})
        for rel in tracked:
            inside(dest, rel)
        if dest.exists():
            for p in dest.rglob('*'):
                if not p.is_file() or p.name == '.geometryforge-install.json':
                    continue
                rel = str(p.relative_to(dest))
                if digest(p) != tracked.get(rel) and (rel not in files or digest(p) != digest(files[rel])):
                    raise ValueError(f'Locally modified/unmanaged skill file: {p}. Preserve or merge it before updating.')
    for dest in destinations:
        old = read(dest / '.geometryforge-install.json', {})
        dest.mkdir(parents=True, exist_ok=True)
        for rel, src in files.items():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
        for rel in old.keys() - files.keys():
            inside(dest, rel).unlink(missing_ok=True)
        write(dest / '.geometryforge-install.json', {rel: digest(src) for rel, src in files.items()})
    return {"installed": [str(p) for p in destinations], "instructions": "Existing AGENTS.md and CLAUDE.md were preserved. Restart the harness if the skill is not yet visible."}
