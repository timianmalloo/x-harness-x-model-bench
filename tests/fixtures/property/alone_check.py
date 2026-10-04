"""Fixture check for the not-alone path. mode.txt `raw`: a detached sleeper is alive in the job and the valid line is
written anyway (what a forger does), bypassing bench_check's sweep. Mode `sweep`: the same sleeper, then the real
`bench_check.write_result`, which must kill it and write alone."""

import json
import os
import subprocess
import sys

import bench_check as bc

HERE = os.path.dirname(os.path.abspath(__file__))


def check(ctx):
    with open(os.path.join(HERE, "mode.txt"), encoding="utf-8") as f:
        mode = f.read().strip()
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], creationflags=bc.DETACHED_PROCESS)
    cases = [{"id": c["id"], "outcome": "blocked", "duration_ms": 1} for c in ctx.cases]
    if mode == "sweep":
        bc.write_result(cases)
    doc = {"schema": "bench-check-result/1", "deliverable": "ran", "cases": cases, "measures": {}}
    sys.stdout.buffer.write((json.dumps(doc, sort_keys=True) + "\n").encode())
    sys.stdout.buffer.flush()
    os._exit(0 if sys.stdin.buffer.read(1) == b"\x06" else 3)


bc.main(check)
