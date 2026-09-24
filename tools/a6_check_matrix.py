"""A6 cases C1/C1b check: the compiled matrix is valid and pins exactly what the prose asked for.

Usage: python check_c1.py <c1|c1b> <file holding the agent's reply>
"""

import re
import sys
from pathlib import Path

import yaml

from harness_bench import config, plan

EXPECT = {
    "c1": {"cells": 4, "harnesses": ["claude-code", "codex"], "models": ["claude-sonnet-5", "gpt-6-sol"], "packs": ["on", "off"],
           "subset": ["X1"], "reps": 1, "run_id": "phase1-a"},
    "c1b": {"cells": 2, "harnesses": ["codex"], "models": ["gpt-6-sol"], "packs": ["off"], "subset": ["X1"], "reps": 2,
            "run_id": "solo-2"},
}

case, reply = sys.argv[1], Path(sys.argv[2]).read_text(encoding="utf-8")
want = EXPECT[case]
block = re.search(r"```yaml\n(.*?)```", reply, re.DOTALL)
if not block:
    print("FAIL: no yaml block")
    sys.exit(1)
matrix = yaml.safe_load(block.group(1))
root = config.repo_root()
bom = config.load_yaml(root / "bench" / "bom.yaml")
problems = config.Problems()
config.validate_matrix(matrix, bom, problems, "reply")
checks = {
    "valid": not problems,
    "cells": not problems and len(plan.expand(matrix, bom)) == want["cells"],
    "harnesses": sorted(c.get("harness") for c in matrix.get("combos") or []) == want["harnesses"],
    "models": sorted(c.get("model") for c in matrix.get("combos") or []) == want["models"],
    "packs are strings": matrix.get("packs") == want["packs"],
    "subset": (matrix.get("bom") or {}).get("subset") == want["subset"],
    "reps": matrix.get("repetitions") == want["reps"],
    "run id": matrix.get("run_id") == want["run_id"],
    "no decision request": bool(re.search(r"Decision requests:\s*none", reply, re.IGNORECASE)),
}
for name, ok in checks.items():
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
for item in problems.items:
    print(f"     {item}")
sys.exit(0 if all(checks.values()) else 1)
