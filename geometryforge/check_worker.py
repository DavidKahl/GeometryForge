"""Run a project's trusted functional checker in an isolated host process."""
import json
from pathlib import Path
import runpy
import sys
import traceback

if __name__ == "__main__":
    entry, payload, output = map(Path, sys.argv[1:])
    sys.path.insert(0, str(entry.parent))
    try:
        result = runpy.run_path(str(entry))["verify"](json.loads(payload.read_text(encoding="utf-8")))
        if not isinstance(result, dict) or result.get("passed") is not True:
            raise ValueError(f"Checker must return passed=true and measurements: {result}")
    except BaseException:
        result = {"passed": False, "error": traceback.format_exc()}
    output.write_text(json.dumps(result), encoding="utf-8")
    sys.exit(0 if result["passed"] else 1)
