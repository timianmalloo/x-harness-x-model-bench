"""Expand a matrix and a BOM into the run's cells, and freeze them in a content-addressed plan (US-6).

One cell is exactly one (task version, combo, pack, repetition). The order interleaves combos
innermost, so provider load and time-of-day drift affect every combo alike (proposal).

- `cell_id` is a deterministic hash of (task version hash, combo, pack, repetition) (ADR-0006).
- The task version hash covers every file in the task folder, so any edit to the prompt, the base
  tree or the hidden tests is a new version.
- `bench plan --confirm` writes `runs/<run_id>/plan.json` once; `plan_hash` covers every field, and
  loading a confirmed plan re-checks it (an edited plan is an integrity failure).
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

SCHEMA = "bench-plan/1"
PHASE1_MAX_PARALLELISM = 2
# Plan parameters (ADR-0007: shown at confirmation, recorded in the plan). Seconds unless named.
DEFAULT_PARAMETERS = {
    "parallelism": 2,
    "git_timeout": 120,
    "spawn_timeout": 30,
    "handshake_timeout": 60,
    "grading_step_timeout": 900,
    "lock_staleness": 120,
    "kill_escalation": 300,
    "suspend_gap": 60,
    "disk_floor_bytes": 10 * 1024**3,
    "stderr_tail_bytes": 64 * 1024,
}


@dataclass(frozen=True)
class Cell:
    task: str
    task_version: str
    scenario: int
    combo: str
    harness: str
    model: str
    pack: str
    rep: int
    budget_seconds: int

    @property
    def id(self) -> str:
        ingredients = {"task_version": self.task_version, "combo": self.combo, "pack": self.pack, "rep": self.rep}
        return hashlib.sha256(canonical(ingredients)).hexdigest()[:16]

    @property
    def label(self) -> str:
        return f"{self.task}.{self.combo}.pack-{self.pack}.r{self.rep}"


def select_tasks(bom: dict, subset) -> list[dict]:
    tasks = bom["tasks"]
    if subset == "full":
        return [t for t in tasks if not t.get("fixture")]
    if subset == "smoke":
        return [t for t in tasks if t.get("smoke") and not t.get("fixture")]
    wanted = set(subset)
    return [t for t in tasks if t["id"] in wanted]


def task_version_hash(task_dir: Path) -> str:
    """sha256 over every file in the task folder: relative path, NUL, bytes, in sorted path order."""
    h = hashlib.sha256()
    for f in sorted(p for p in task_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(f.relative_to(task_dir).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def expand(matrix: dict, bom: dict, task_versions: dict[str, str] | None = None) -> list[Cell]:
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    versions = task_versions or {}
    cells = []
    for rep in range(1, matrix["repetitions"] + 1):
        for t in tasks:
            for pack in matrix["packs"]:
                for c in matrix["combos"]:
                    cells.append(Cell(t["id"], versions.get(t["id"], t["id"]), t["scenario"], c["id"], c["harness"],
                                      c["model"], pack, rep, t["budget_minutes"] * 60))
    return cells


def envelope_seconds(cells: list[Cell], parallelism: int) -> int:
    """The worst-case wall clock the operator confirms: ceil(sum of budgets / p) + the largest budget."""
    if not cells:
        return 0
    budgets = [c.budget_seconds for c in cells]
    return math.ceil(sum(budgets) / parallelism) + max(budgets)


def _sha(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def plan_hash(plan: dict) -> str:
    return _sha({k: v for k, v in plan.items() if k != "plan_hash"})


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.exists() else ""


def build_plan(root: Path, matrix: dict, bom: dict, run_id: str, builds: dict, pack: dict,
               parallelism: int = DEFAULT_PARAMETERS["parallelism"], parameters: dict | None = None) -> dict:
    if not 1 <= parallelism <= PHASE1_MAX_PARALLELISM:
        raise BenchError("HB-USR-002", f"parallelism must be 1-{PHASE1_MAX_PARALLELISM} in phase 1, got {parallelism}")
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    versions = {t["id"]: task_version_hash(root / "tasks" / t["id"]) for t in tasks}
    cells = expand(matrix, bom, versions)
    harnesses = {c.harness for c in cells}
    missing = harnesses - set(builds)
    if missing:
        raise BenchError("HB-PRE-007", f"no planned build for {sorted(missing)}")
    params = {**DEFAULT_PARAMETERS, **(parameters or {}), "parallelism": parallelism}
    body = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_id": secrets.token_hex(16),
        "matrix": matrix,
        "matrix_hash": _sha(matrix),
        "bom_version": str(bom.get("version")),
        "tasks": {t["id"]: {"version_hash": versions[t["id"]], "scenario": t["scenario"],
                            "budget_seconds": t["budget_minutes"] * 60} for t in tasks},
        "builds": {h: builds[h] for h in sorted(harnesses)},
        "pack": pack,
        "parameters": params,
        "price_list_hash": file_hash(root / "bench" / "prices.yaml"),
        "envelope_seconds": envelope_seconds(cells, parallelism),
        "cells": [{"cell_id": c.id, "label": c.label, **asdict(c)} for c in cells],
    }
    body["plan_hash"] = plan_hash(body)
    return body


def confirm(run_dir: Path, plan: dict) -> Path:
    """Freeze the plan: written once, never overwritten."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "plan.json"
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(json.dumps(plan, indent=2, sort_keys=True))
    except FileExistsError:
        raise BenchError("HB-USR-002", f"{path} already confirmed; a confirmed plan is frozen") from None
    return path


def load_confirmed(run_dir: Path) -> dict:
    path = run_dir / "plan.json"
    if not path.exists():
        raise BenchError("HB-USR-001", f"no confirmed plan at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if plan_hash(data) != data.get("plan_hash"):
        raise BenchError("HB-LED-002", f"{path} was edited after confirmation (plan_hash mismatch)")
    return data
