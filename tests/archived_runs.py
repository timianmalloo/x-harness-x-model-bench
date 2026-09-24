"""Builders for archived runs on disk, shared by the grading and view tests.

A run is built the way the engine and archiver lay it out: a confirmed plan, engine segments written
with the real ledger, and `archive/<cell>/attempt-1/{ws,home}` holding the cell's final tree and the
real captured Codex record as its native record.
"""

import json
import shutil
from pathlib import Path

from harness_bench import ledger
from harness_bench import plan as plan_mod
from harness_bench.grade import runner

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
GOOD = '''import re


def slugify(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower()))
'''
NO_STRIP = '''import re


def slugify(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if text.startswith("-"):
        return "-" + "-".join(words)
    return "-".join(words)
'''
STUB = "def slugify(text):\n    raise NotImplementedError\n"
HANG = "while True:\n    pass\n"
CODEX_MODEL = "gpt-6-sol"  # the model in the captured Codex record


def make_root(tmp_path: Path) -> Path:
    """A bench root with the real X1 task, catalog, profiles and an empty price list."""
    r = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", r / "tasks" / "X1")
    (r / "bench").mkdir()
    shutil.copy(ROOT / "bench" / "metrics.yaml", r / "bench" / "metrics.yaml")
    shutil.copytree(ROOT / "bench" / "profiles", r / "bench" / "profiles")
    set_prices(r, [])
    return r


def set_prices(root: Path, entries: list[dict]) -> str:
    path = root / "bench" / "prices.yaml"
    path.write_text(json.dumps({"schema": "bench-prices/1", "currency": "USD", "unit": "per_million_tokens",
                                "entries": entries}), encoding="utf-8")
    return runner.file_hash(path)


def make_run(root: Path, tmp_path: Path, cells: dict[str, str | None], harness: str = "codex", archived: set[str] | None = None,
             timeout: int = 900, turn_usage: list[dict] | None = None, outcomes: dict[str, dict] | None = None,
             model: str = CODEX_MODEL, combos: dict[str, str] | None = None, unstarted: tuple[str, ...] = ()) -> Path:
    """An archived run: one cell per entry of `cells` (cell_id -> slug.py source, or None for no working copy).

    `outcomes` overrides a cell's `cell.outcome` fields (default: completed); `combos` names each cell's combo;
    `unstarted` adds plan cells that never started (no events).
    """
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    combos = combos or {}
    plan = {"run_id": "r1", "created_at": "2026-09-23T10:00:00Z", "plan_hash": "",
            "price_list_hash": runner.file_hash(root / "bench" / "prices.yaml"),
            "parameters": {"parallelism": 2, "grading_step_timeout": timeout},
            "profiles": {harness: plan_mod.profile_record(root, harness)},
            "cells": [{"cell_id": cid, "label": f"X1.{combos.get(cid, 'c')}.pack-off.r1", "task": "X1",
                       "task_version": plan_mod.task_version_hash(root / "tasks" / "X1"), "harness": harness, "model": model,
                       "combo": combos.get(cid, "c"), "pack": "off", "rep": 1} for cid in (*cells, *unstarted)]}
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    archived = set(cells) if archived is None else archived
    with ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev:
        ev.append({"kind": "run.started", "run_id": "r1"})
        for cid, source in cells.items():
            for kind in ("cell.launch_intent", "cell.workspace_built"):
                ev.append({"kind": kind, "cell_id": cid})
            ev.append({"kind": "attempt.process_started", "cell_id": cid, "mono_ns": 1_000_000_000})
            ev.append({"kind": "attempt.session_opened", "cell_id": cid, "session_id": f"sess-{cid}"})
            ev.append({"kind": "cell.prompt_sent", "cell_id": cid})
            ev.append({"kind": "attempt.process_ended", "cell_id": cid, "mono_ns": 31_000_000_000})
            ev.append({"kind": "cell.outcome", "cell_id": cid, "outcome": "completed", "cause": None, "code": None,
                       "session_id": f"sess-{cid}", **(outcomes or {}).get(cid, {})})
            if cid not in archived:
                continue
            folder = run_dir / "archive" / cid / "attempt-1"
            if source is not None:
                (folder / "ws").mkdir(parents=True)
                (folder / "ws" / "slug.py").write_text(source, encoding="utf-8")
            record = folder / "home" / "sessions" / "2026" / "09" / f"rollout-2026-09-23-sess-{cid}.jsonl"
            record.parent.mkdir(parents=True)
            shutil.copy(FIX / "native" / "codex" / "ok.jsonl", record)
            ev.append({"kind": "cell.archived", "cell_id": cid, "archive_attempt": 1, "archive_hash": "h"})
            ev.append({"kind": "cell.workspace_deleted", "cell_id": cid})
    if turn_usage is not None:
        with ledger.SegmentWriter.create(run_dir / "turn_usage", "engine-1") as tu:
            for row in turn_usage:
                tu.append(row)
    return run_dir


def pass_rows(run_dir: Path, fact: str, grading_id: str) -> list[dict]:
    return ledger.read_segment(run_dir / fact / f"{grading_id}.jsonl")


def scores(run_dir: Path, grading_id: str) -> dict[tuple[str, str], dict]:
    return {(s["cell_id"], s["metric_id"]): s for s in pass_rows(run_dir, "scores", grading_id)}
