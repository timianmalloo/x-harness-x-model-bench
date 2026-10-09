"""L-SUM-C: `bench report <batch-2> --pool <batch-1> [--prereg PATH]` end to end (ADR-0022 section 3, ADR-0023).

Fixture lean runs are built on disk with hand-built ledgers: a confirmed plan (ring tag `lean`, one comparison, two
arms, ten tasks for one combo, so ten planned pack-off cells: the MDE 0.42 case), the engine's events and a sealed
grading pass with scores. Every case launches `bench` as a subprocess, with the console flag.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from archived_runs import make_root

from harness_bench import config, ledger, verdicts
from harness_bench import plan as plan_mod
from harness_bench.grade import runner

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TREAT = "cand"  # the treatment arm's id; the CLI reads both from plan.comparisons
ARMS = (config.ARM_OFF, TREAT)
TASKS = tuple(f"T{n:02d}" for n in range(1, 11))
HARNESS, MODEL, COMBO = "claude-code", "claude-opus-5-5", "cc"
STARTED = "2026-10-09T10:00:00.000Z"
B1, B2 = "lean-b1", "lean-b2"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    return make_root(tmp_path), tmp_path / "runs"


def _make_run(root: Path, runs: Path, run_id: str, *, tag: str | None = "lean", ring_hash: str = "ring-1",
              tasks: tuple[str, ...] = TASKS, parameters: dict | None = None) -> Path:
    """A completed, graded run: pack-off passes no task, the treatment passes the first six (a known effect)."""
    run_dir = runs / run_id
    run_dir.mkdir(parents=True)
    cells = [{"cell_id": f"{task}-{arm}", "label": f"{task}.{COMBO}.{arm}.r1", "task": task, "task_version": "v1",
              "harness": HARNESS, "model": MODEL, "combo": COMBO, "arm": arm, "rep": 1, "budget_seconds": 300}
             for task in tasks for arm in ARMS]
    plan = {"run_id": run_id, "created_at": STARTED, "plan_hash": "",
            "price_list_hash": runner.file_hash(root / "bench" / "prices.yaml"),
            "parameters": parameters or {"parallelism": 2, "grading_step_timeout": 900},
            "profiles": {HARNESS: plan_mod.profile_record(root, HARNESS)},
            "matrix": {"combos": [{"id": COMBO, "harness": HARNESS, "model": MODEL}]},
            "comparisons": [list(ARMS)], "arms": {arm: {"pack": None} for arm in ARMS}, "cells": cells}
    if tag is not None:
        plan["ring"] = {"tag": tag, "hash": ring_hash}
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev, \
            ledger.SegmentWriter.create(run_dir / "turn_usage", "engine-1") as tu:
        ev.append({"kind": "run.started", "run_id": run_id, "mono_ns": 0, "recorded_at": STARTED})
        for cell in cells:
            cid = cell["cell_id"]
            ev.append({"kind": "cell.launch_intent", "cell_id": cid})
            ev.append({"kind": "attempt.process_started", "cell_id": cid, "mono_ns": 1_000_000_000, "recorded_at": STARTED})
            ev.append({"kind": "attempt.process_ended", "cell_id": cid, "mono_ns": 31_000_000_000})
            ev.append({"kind": "cell.outcome", "cell_id": cid, "outcome": "completed", "cause": None, "code": None})
            tu.append({"cell_id": cid, "model": MODEL, "uncached_input": 100, "cache_read": 0, "cache_write": 0,
                       "output": 50, "reasoning": 0})
        ev.append({"kind": "run.completed", "run_id": run_id, "mono_ns": 600_000_000_000, "recorded_at": STARTED,
                   "segment_heads": {}, "cells_ended": len(cells)})
    catalog = str(yaml.safe_load((root / "bench" / "metrics.yaml").read_text(encoding="utf-8"))["version"])
    gid = "grade-g1"
    with ledger.SegmentWriter.create(run_dir / "scores", gid) as sc:
        for cell in cells:
            passed = cell["arm"] == TREAT and cell["task"] in TASKS[:6]
            sc.append({"grading_id": gid, "cell_id": cell["cell_id"], "metric_id": verdicts.PRIMARY,
                       "value": 1 if passed else 0, "reason": None, "extraction_id": "x"})
        sc.seal()
    with ledger.SegmentWriter.create(run_dir / "events", gid) as gr:
        gr.append({"kind": "grading.started", "grading_id": gid, "catalog_version": catalog, "recorded_at": STARTED,
                   "mono_ns": 0})
        gr.append({"kind": "grading.completed", "grading_id": gid, "cells_graded": len(cells), "recorded_at": STARTED,
                   "mono_ns": 120_000_000_000})
        gr.seal()
    return run_dir


def _bench(root: Path, runs: Path, *args: str) -> subprocess.CompletedProcess:
    """`bench --root <root> --runs <runs> <args>` in a child process; `~` points at an empty folder (no real credential
    file is read by the report's credential scan), and no provider key reaches the child."""
    env = {k: v for k, v in os.environ.items() if k not in ("XAI_API_KEY", "GEMINI_API_KEY")}
    env["USERPROFILE"] = env["HOME"] = str(runs.parent / "fake-home")
    return subprocess.run([sys.executable, "-c", "import sys; from harness_bench.cli import main; sys.exit(main())",
                           "--root", str(root), "--runs", str(runs), *args], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=600, check=False, creationflags=NO_WINDOW)


def _page(runs: Path, run_id: str) -> str:
    return (runs / run_id / "report.html").read_text(encoding="utf-8")


def test_pool_renders_two_of_two_batches(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    _make_run(root, runs, B2)
    done = _bench(root, runs, "report", B2, "--pool", B1)
    assert done.returncode == 0, done.stderr
    assert "Batches: 2 of 2" in _page(runs, B2)
