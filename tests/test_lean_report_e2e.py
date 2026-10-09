"""L-SUM-C: `bench report <batch-2> --pool <batch-1> [--prereg PATH]` end to end (ADR-0022 section 3, ADR-0023).

Fixture lean runs are built on disk with hand-built ledgers: a confirmed plan (ring tag `lean`, one comparison, two
arms, ten tasks for one combo, so ten planned pack-off cells: the MDE 0.42 case), the engine's events and a sealed
grading pass with scores. Every case launches `bench` as a subprocess, with the console flag.
"""

import hashlib
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


# ---------------------------------------------------------------- C3: the cases, each through the subprocess launch


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2026-01-01T00:00:00+00:00")
    return subprocess.run(["git", "-c", "user.name=bench-test", "-c", "user.email=bench-test@example.invalid", *args],
                          cwd=repo, capture_output=True, text=True, env=env, timeout=60, check=True,
                          creationflags=NO_WINDOW)


def test_a_pooled_report_names_both_batches_and_has_the_pooled_row(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    _make_run(root, runs, B2)
    done = _bench(root, runs, "report", B2, "--pool", B1)
    assert done.returncode == 0, done.stderr
    page = _page(runs, B2)
    assert f'data-field="run-ids">{B1}, {B2}<' in page  # batch order: the --pool run is batch 1
    assert f"Sections below cover batch {B2} only" in page
    assert 'data-harness="pooled"' in page and "n 20 of 20" in page
    assert "Not pre-registered: no pre-registration supplied" in page
    assert not (runs / B1 / "report.html").exists()


def test_b_a_lean_run_alone_renders_one_of_two_and_mde_042(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    done = _bench(root, runs, "report", B1)
    assert done.returncode == 0, done.stderr
    page = _page(runs, B1)
    assert "Batches: 1 of 2" in page and "MDE 0.42" in page and "n 10 of 10" in page
    assert "Sections below cover batch" not in page


def test_c_a_non_lean_run_with_pool_is_refused_and_alone_renders_no_lean_section(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, "n1", tag=None)
    _make_run(root, runs, "n2", tag=None)
    done = _bench(root, runs, "report", "n2", "--pool", "n1")
    assert done.returncode != 0 and "HB-USR-002" in done.stderr and "--pool" in done.stderr
    assert not (runs / "n2" / "report.html").exists()
    alone = _bench(root, runs, "report", "n2")
    assert alone.returncode == 0, alone.stderr
    assert "Batches:" not in _page(runs, "n2")


def test_d_the_pooling_checks_refusals_reach_the_cli_with_their_codes(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    _make_run(root, runs, "ring2", ring_hash="ring-2")
    _make_run(root, runs, "more", tasks=(*TASKS, "T11"))
    _make_run(root, runs, "plain", tag=None)
    ring = _bench(root, runs, "report", "ring2", "--pool", B1)
    assert ring.returncode != 0 and "HB-PLN-003" in ring.stderr
    cells = _bench(root, runs, "report", "more", "--pool", B1)
    assert cells.returncode != 0 and "HB-STA-002" in cells.stderr and "only in B: T11-" in cells.stderr
    lean_report = _bench(root, runs, "report", B1, "--pool", "plain")
    assert lean_report.returncode != 0 and "HB-STA-002" in lean_report.stderr
    assert "run plain has ring tag None, not lean" in lean_report.stderr
    unknown = _bench(root, runs, "report", B1, "--pool", "absent")
    assert unknown.returncode != 0 and "absent" in unknown.stderr
    assert not any((runs / r / "report.html").exists() for r in ("ring2", "more", B1))


def test_e_prereg_sets_the_status_both_ways(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    _make_run(root, runs, B2)
    repo = tmp_path / "prereg"
    repo.mkdir()
    _git(repo, "init", "-q")
    committed = repo / "lean-preregistration.md"
    committed.write_bytes(b"# Lean pre-registration\n\nThe question, the rule and the MDE.\n")
    _git(repo, "add", committed.name)
    _git(repo, "commit", "-q", "-m", "pre-register")
    done = _bench(root, runs, "report", B2, "--pool", B1, "--prereg", str(committed))
    assert done.returncode == 0, done.stderr
    sha = hashlib.sha256(committed.read_bytes()).hexdigest()
    assert f"pre-registered ({sha[:12]})" in _page(runs, B2)
    loose = repo / "uncommitted.md"
    loose.write_bytes(b"# not committed\n")
    done = _bench(root, runs, "report", B2, "--pool", B1, "--prereg", str(loose))
    assert done.returncode == 0, done.stderr
    assert "Not pre-registered: the pre-registration is not committed" in _page(runs, B2)


def test_f_a_shown_difference_is_printed_and_does_not_refuse(tmp_path):
    root, runs = _setup(tmp_path)
    _make_run(root, runs, B1)
    _make_run(root, runs, B2, parameters={"parallelism": 4, "grading_step_timeout": 900})
    done = _bench(root, runs, "report", B2, "--pool", B1)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    shown = next((n for n, line in enumerate(lines) if line.startswith("parameters differ: A ")), None)
    assert shown is not None and "'parallelism': 2" in lines[shown] and "'parallelism': 4" in lines[shown]
    assert shown < next(n for n, line in enumerate(lines) if line.startswith("report: "))
    assert "Batches: 2 of 2" in _page(runs, B2)
