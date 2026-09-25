"""Builders for archived runs on disk, shared by the grading and view tests.

A run is built the way the engine and archiver lay it out: a confirmed plan, engine segments written
with the real ledger, and `archive/<cell>/attempt-1/{ws,home}` holding the cell's final tree and the
real captured Codex record as its native record.
"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from harness_bench import archive, ledger
from harness_bench import plan as plan_mod
from harness_bench.grade import runner

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"


def gate_runs_root() -> Path:
    """The folder of archived gate runs.

    `HB_GATE_RUNS` when that variable is set; otherwise `runs/` of this repository's primary
    checkout (the first entry of `git worktree list --porcelain`); otherwise `ROOT / "runs"`.
    A linked worktree's own `runs/` is empty, so the last fallback skips runs that live on the
    main checkout.
    """
    configured = os.environ.get("HB_GATE_RUNS")
    if configured:
        return Path(configured)
    try:
        listed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ROOT / "runs"
    if listed.returncode != 0:
        return ROOT / "runs"
    for line in (listed.stdout or "").splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")) / "runs"
    return ROOT / "runs"


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

# Where a cell's native record lands under its archive `home/`, and the default fixture copied there,
# by harness (`record_glob` in bench/profiles/*.yaml -- a concrete path this glob must match). A harness
# with no entry here falls back to the Codex shape (unchanged default; existing callers are unaffected).
_RECORD_PATH = {"codex": lambda cid: Path("sessions") / "2026" / "09" / f"rollout-2026-09-23-sess-{cid}.jsonl",
                "copilot": lambda cid: Path("session-state") / f"sess-{cid}" / "events.jsonl"}
_DEFAULT_RECORD = {"codex": FIX / "native" / "codex" / "ok.jsonl",
                    "copilot": next((FIX / "native" / "copilot" / "off").rglob("events.jsonl"))}


def make_root(tmp_path: Path, release: bool = True) -> Path:
    """A bench root with the real X1 task, catalog, profiles and an empty price list.

    With `release` (the default) a `.dev` catalog is relabelled to the version it probes (`0.4.dev` -> `0.4`), so the
    passes a test runs are current in a default view (R-59 DR-4: a probe pass never is). A test of the probe rule, or
    of the real catalog's identity (the US-4 control), passes `release=False` and gets the catalog byte for byte.
    """
    r = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", r / "tasks" / "X1")
    (r / "bench").mkdir()
    shutil.copy(ROOT / "bench" / "metrics.yaml", r / "bench" / "metrics.yaml")
    shutil.copytree(ROOT / "bench" / "profiles", r / "bench" / "profiles")
    version = str(yaml.safe_load((r / "bench" / "metrics.yaml").read_text(encoding="utf-8"))["version"])
    if release and version.endswith(".dev"):
        set_catalog_version(r, version.removesuffix(".dev"))
    set_prices(r, [])
    return r


def set_catalog_version(root: Path, version: str) -> None:
    """Relabel the root's catalog (its `version:` line only), e.g. a release label so a pass is current (R-59 DR-4)."""
    path = root / "bench" / "metrics.yaml"
    text = path.read_text(encoding="utf-8")
    old = f'version: "{yaml.safe_load(text)["version"]}"'
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, f'version: "{version}"'), encoding="utf-8")


def set_prices(root: Path, entries: list[dict]) -> str:
    path = root / "bench" / "prices.yaml"
    path.write_text(json.dumps({"schema": "bench-prices/1", "currency": "USD", "unit": "per_million_tokens",
                                "entries": entries}), encoding="utf-8")
    return runner.file_hash(path)


def make_run(root: Path, tmp_path: Path, cells: dict[str, str | None], harness: str = "codex", archived: set[str] | None = None,
             timeout: int = 900, turn_usage: list[dict] | None = None, outcomes: dict[str, dict] | None = None,
             model: str = CODEX_MODEL, combos: dict[str, str] | None = None, unstarted: tuple[str, ...] = (),
             context_window_tag: dict[str, str] | None = None, native_record: Path | None = None) -> Path:
    """An archived run: one cell per entry of `cells` (cell_id -> slug.py source, or None for no working copy).

    `outcomes` overrides a cell's `cell.outcome` fields (default: completed); `combos` names each cell's combo;
    `unstarted` adds plan cells that never started (no events); `context_window_tag` sets a cell's
    `attempt.process_ended.context_window_tag` (R-32; default None, as engine.py records for an untagged cell);
    `native_record` overrides the default fixture copied to each archived cell's native record path
    (`_DEFAULT_RECORD[harness]`, Codex when `harness` names none), for a test that needs a mutated record.
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
                       "combo": combos.get(cid, "c"), "pack": "off", "rep": 1, "budget_seconds": 300}
                      for cid in (*cells, *unstarted)]}
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    archived = set(cells) if archived is None else archived
    with ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev, \
            ledger.SegmentWriter.create(run_dir / "archive_files", "engine-1") as af:
        ev.append({"kind": "run.started", "run_id": "r1"})
        for cid, source in cells.items():
            for kind in ("cell.launch_intent", "cell.workspace_built"):
                ev.append({"kind": kind, "cell_id": cid})
            ev.append({"kind": "attempt.process_started", "cell_id": cid, "mono_ns": 1_000_000_000})
            ev.append({"kind": "attempt.session_opened", "cell_id": cid, "session_id": f"sess-{cid}"})
            ev.append({"kind": "cell.prompt_sent", "cell_id": cid})
            ev.append({"kind": "attempt.process_ended", "cell_id": cid, "mono_ns": 31_000_000_000,
                       "context_window_tag": (context_window_tag or {}).get(cid)})
            ev.append({"kind": "cell.outcome", "cell_id": cid, "outcome": "completed", "cause": None, "code": None,
                       "session_id": f"sess-{cid}", **(outcomes or {}).get(cid, {})})
            if cid not in archived:
                continue
            folder = run_dir / "archive" / cid / "attempt-1"
            if source is not None:
                (folder / "ws").mkdir(parents=True)
                (folder / "ws" / "slug.py").write_text(source, encoding="utf-8")
            record = folder / "home" / _RECORD_PATH.get(harness, _RECORD_PATH["codex"])(cid)
            record.parent.mkdir(parents=True)
            shutil.copy(native_record or _DEFAULT_RECORD.get(harness, _DEFAULT_RECORD["codex"]), record)
            rows = [{"path": f.relative_to(folder).as_posix(), "kind": "file", "size": f.stat().st_size,
                     "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "link_target": "", "archive_attempt": 1}
                    for f in sorted(folder.rglob("*")) if f.is_file()]
            for row in rows:
                af.append({"kind": "archive_file", "run_id": "r1", "cell_id": cid, **row})
            ev.append({"kind": "cell.archived", "cell_id": cid, "archive_attempt": 1, "archive_hash": archive.archive_hash(rows)})
            ev.append({"kind": "cell.workspace_deleted", "cell_id": cid})
    if turn_usage is not None:
        with ledger.SegmentWriter.create(run_dir / "turn_usage", "engine-1") as tu:
            for row in turn_usage:
                tu.append(row)
    return run_dir


ENGINE_FACTS = ("events", "turn_usage", "archive_files")  # engine.FACTS: the engine writes one segment per fact


def complete_run(run_dir: Path, grading: dict | None = None, events_head: str | None = None) -> dict:
    """Close the engine segments the way `Engine.run` does: seal every other fact, append `run.completed` with
    `segment_heads` (events: the head before `run.completed`) and `grading` (a pass summary), then seal events.
    `events_head` overrides the recorded events head (a forged record). Returns the `run.completed` row."""
    for fact in ENGINE_FACTS:
        if not (run_dir / fact / "engine-1.jsonl").exists():
            ledger.SegmentWriter.create(run_dir / fact, "engine-1").close()
    ended = sum(1 for e in ledger.read_segment(run_dir / "events" / "engine-1.jsonl") if e["kind"] == "cell.outcome")
    writers = {fact: ledger.SegmentWriter.reopen(run_dir / fact / "engine-1.jsonl") for fact in ENGINE_FACTS}
    try:
        heads = {fact: w.seal() for fact, w in writers.items() if fact != "events"}
        ev = writers["events"]
        done = ev.append(ledger.stamp({"kind": "run.completed", "run_id": "r1",
                                       "segment_heads": {**heads, "events": events_head or ev.head_hash},
                                       "cells_ended": ended, "grading": grading}))
        ev.seal()
    finally:
        for w in writers.values():
            w.close()
    return done


def pass_rows(run_dir: Path, fact: str, grading_id: str) -> list[dict]:
    return ledger.read_segment(run_dir / fact / f"{grading_id}.jsonl")


def scores(run_dir: Path, grading_id: str) -> dict[tuple[str, str], dict]:
    return {(s["cell_id"], s["metric_id"]): s for s in pass_rows(run_dir, "scores", grading_id)}
