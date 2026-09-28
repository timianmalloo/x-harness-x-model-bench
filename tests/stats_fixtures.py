"""Shared fixtures and run builder for statistics tests (S5, design: Board, D7 fidelity pairing).

`stats_run` generalises `tests/test_views.py::_copilot_run` using real Copilot events,
sealed segments, and one real grading pass.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from archived_runs import CODEX_MODEL, GOOD, STUB, complete_run

from harness_bench import archive, ledger, profiles
from harness_bench import plan as plan_mod
from harness_bench.grade import runner

COPILOT_FIX = Path(__file__).parent / "fixtures/native/copilot"
DEFAULT_TASKS = ("A1", "B1", "C1", "D1", "E1", "E2")


def _ensure_task_ready(root: Path, task_id: str) -> None:
    """Ensure root / tasks / task_id has a working python unittest setup."""
    task_dir = root / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    ws_dir = task_dir / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    slug_py = ws_dir / "slug.py"
    if not slug_py.exists():
        slug_py.write_text(GOOD, encoding="utf-8")

    test_file = tests_dir / "test_slug_hidden.py"
    if not test_file.exists():
        x1_test = root / "tasks/X1/tests/test_slug_hidden.py"
        if x1_test.exists():
            shutil.copy(x1_test, test_file)
        else:
            test_file.write_text(
                "import unittest\nfrom slug import slugify\n"
                "class TestSlugHidden(unittest.TestCase):\n"
                "    def test_basic(self):\n"
                "        self.assertEqual(slugify('Hello World'), 'hello-world')\n",
                encoding="utf-8",
            )

    spec = {
        "schema": "bench-task/1",
        "id": task_id,
        "scenario": 5,
        "title": f"Task {task_id}",
        "status": "ready",
        "language": "python",
        "source": {
            "kind": "authored",
            "upstream": "harness-bench fixture",
            "repo": f"tasks/{task_id}/workspace",
            "commit": "content-addressed",
        },
        "budget": {"minutes": 5, "usd_cap": None},
        "blast_radius": ["slug.py"],
        "model_map": None,
        "scripted_user": False,
        "graders": ["correctness", "cost"],
        "oracle": {
            "summary": f"Hidden unittest cases for {task_id}",
            "runner": "unittest",
            "command": ["{python}", "-m", "unittest", "-v", "test_slug_hidden"],
        },
    }
    (task_dir / "task.yaml").write_text(json.dumps(spec), encoding="utf-8")


def stats_run(
    root: Path,
    tmp_path: Path,
    *,
    tasks: Sequence[str] | None = None,
    reps: int = 3,
    arms: Sequence[str] = ("off", "on"),
    outcomes: Mapping[tuple[str, int, str], Any] | None = None,
    combos: Sequence[str] | None = None,
    run_id: str = "r1",
    bom_version: str = "0.4",
    pack_revision: str = "95",
) -> Path:
    """Build, archive, and grade a real multi-task, multi-rep, multi-arm run.

    tasks: defaults to 6 tasks ('A1', 'B1', 'C1', 'D1', 'E1', 'E2').
    reps: repetitions per task and arm (default 3).
    arms: pack settings ('off', 'on').
    outcomes: mapping of (task, rep, arm) -> outcome:
      - 1 / True / 'pass': slug.py with GOOD -> pass_at_1 = 1
      - 0 / False / 'fail': slug.py with STUB -> pass_at_1 = 0
      - 'na' / 'no_summary': slug.py exits 1 without summary -> pass_at_1 NA
      - dict: outcome overrides (e.g. invalid cell cause/code)
    """
    assert "copilot" in profiles.READERS, "Copilot must be registered"
    task_list = list(tasks if tasks is not None else DEFAULT_TASKS)
    combo_list = list(combos if combos is not None else ["c"])

    for tid in task_list:
        _ensure_task_ready(root, tid)

    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build cell descriptions
    cells_plan: list[dict[str, Any]] = []
    cells_spec: list[tuple[str, str, int, str, str]] = []  # (cid, task, rep, arm, combo)

    for combo in combo_list:
        for tid in task_list:
            for rep in range(1, reps + 1):
                for arm in arms:
                    cid = f"{tid}-r{rep}-{arm}-{combo}".lower()
                    t_ver = plan_mod.task_version_hash(root / "tasks" / tid)
                    label = f"{tid}.{combo}.pack-{arm}.r{rep}"
                    cells_plan.append({
                        "cell_id": cid,
                        "label": label,
                        "task": tid,
                        "task_version": t_ver,
                        "harness": "copilot",
                        "model": CODEX_MODEL,
                        "combo": combo,
                        "pack": arm,
                        "rep": rep,
                        "budget_seconds": 300,
                    })
                    cells_spec.append((cid, tid, rep, arm, combo))

    matrix_combos = [
        {"id": c, "harness": "copilot", "model": CODEX_MODEL}
        for c in combo_list
    ]

    prices_path = root / "bench" / "prices.yaml"
    if not prices_path.exists():
        prices_path.parent.mkdir(parents=True, exist_ok=True)
        prices_path.write_text(
            json.dumps({"schema": "bench-prices/1", "currency": "USD", "unit": "per_million_tokens", "entries": []}),
            encoding="utf-8",
        )

    plan = {
        "run_id": run_id,
        "created_at": "2026-09-27T10:00:00Z",
        "plan_hash": "",
        "bom_version": bom_version,
        "price_list_hash": runner.file_hash(prices_path),
        "parameters": {"parallelism": 2, "grading_step_timeout": 900},
        "matrix": {
            "repetitions": reps,
            "combos": matrix_combos,
        },
        "pack": {"revision": pack_revision},
        "profiles": {"copilot": plan_mod.profile_record(root, "copilot")},
        "cells": cells_plan,
    }
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

    outcomes_map = outcomes or {}

    with (
        ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev,
        ledger.SegmentWriter.create(run_dir / "archive_files", "engine-1") as af,
    ):
        ev.append({"kind": "run.started", "run_id": run_id})

        for cid, tid, rep, arm, combo in cells_spec:
            spec_outcome = outcomes_map.get((tid, rep, arm))
            if spec_outcome is None:
                spec_outcome = outcomes_map.get((tid, rep, arm, combo), 1)

            is_invalid = False
            custom_outcome: dict[str, Any] = {}
            if isinstance(spec_outcome, dict):
                custom_outcome = spec_outcome
                if custom_outcome.get("outcome") != "completed":
                    is_invalid = True
                source_code = custom_outcome.get("source", GOOD)
            elif spec_outcome in (1, True, "pass"):
                source_code = GOOD
            elif spec_outcome in (0, False, "fail"):
                source_code = STUB
            elif spec_outcome in ("na", "no_summary"):
                source_code = "import sys\nsys.exit(1)\n"
            else:
                source_code = GOOD

            for kind in ("cell.launch_intent", "cell.workspace_built"):
                ev.append({"kind": kind, "cell_id": cid})
            ev.append({"kind": "attempt.process_started", "cell_id": cid, "mono_ns": 1_000_000_000})
            ev.append({"kind": "attempt.session_opened", "cell_id": cid, "session_id": f"sess-{cid}"})
            ev.append({"kind": "cell.prompt_sent", "cell_id": cid})
            ev.append({"kind": "attempt.process_ended", "cell_id": cid, "mono_ns": 31_000_000_000})

            cell_outcome_rec = {
                "kind": "cell.outcome",
                "cell_id": cid,
                "outcome": "completed" if not is_invalid else "failed",
                "cause": None if not is_invalid else custom_outcome.get("cause", "provider"),
                "code": None if not is_invalid else custom_outcome.get("code", "HB-CELL-108"),
                "session_id": f"sess-{cid}",
            }
            if custom_outcome and not is_invalid:
                cell_outcome_rec.update(custom_outcome)
            ev.append(cell_outcome_rec)

            folder = run_dir / "archive" / cid / "attempt-1"
            ws = folder / "ws"
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "slug.py").write_text(source_code, encoding="utf-8")

            # Copy copilot native record
            arm_dir = "on" if arm == "on" else "off"
            record_src = next((COPILOT_FIX / arm_dir).rglob("events.jsonl"))
            record_dst = folder / "home" / "session-state" / f"sess-{cid}" / "events.jsonl"
            record_dst.parent.mkdir(parents=True, exist_ok=True)

            events = [
                json.loads(line)
                for line in record_src.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            events = [e for e in events if e.get("type") != "session.usage_checkpoint"]
            record_dst.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

            rows = [
                {
                    "path": f.relative_to(folder).as_posix(),
                    "kind": "file",
                    "size": f.stat().st_size,
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                    "link_target": "",
                    "archive_attempt": 1,
                }
                for f in sorted(folder.rglob("*"))
                if f.is_file()
            ]
            for row in rows:
                af.append({"kind": "archive_file", "run_id": run_id, "cell_id": cid, **row})
            ev.append({
                "kind": "cell.archived",
                "cell_id": cid,
                "archive_attempt": 1,
                "archive_hash": archive.archive_hash(rows),
            })
            ev.append({"kind": "cell.workspace_deleted", "cell_id": cid})

    runner.run_pass(run_dir, root)
    complete_run(run_dir)
    return run_dir
