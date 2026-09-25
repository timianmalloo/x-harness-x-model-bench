"""`bench status <run_id> [--json]` (US-20; design: Exposed contracts, CLI states; ADR-0011 C4).

- Liveness comes from the run lock: `alive` (held, heartbeat within the plan's `lock_staleness`),
  `stalled` (held, heartbeat stale), `not running` (free). Completion: `complete` once `run.completed` is
  recorded, `in progress` while the lock is held, otherwise `incomplete`.
- A running cell is one with `attempt.process_started` and no `attempt.process_ended`. Its budget
  clock starts at `cell.prompt_sent` (matching the engine's own kill check), so a cell still
  handshaking shows `elapsed_s` 0 and is never `killing`. One past its budget is being killed (the
  engine kills at the budget and records the end only once the kill is confirmed), shown as
  `killing (unconfirmed, <s> s)`.
- `bench-status/1` is a strict type: `parse` rejects unknown or missing fields, wrong types, unknown
  enum values and malformed ids. It carries enums, ids, counts and times only: no text from a cell.
- Phase 1 has no decision requests, so `decisions` is always empty.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

from harness_bench import oslock, views
from harness_bench.config import CELL_ID, LABEL
from harness_bench.errors import BenchError
from harness_bench.plan import DEFAULT_PARAMETERS

SCHEMA = "bench-status/1"
LIVENESS = ("alive", "stalled", "not running")
COMPLETION = ("complete", "in progress", "incomplete")
OUTCOMES = ("completed", "timed_out", "failed", "no outcome", "not started")
VALIDITY = ("valid", "invalid (infrastructure)", "invalid (benchmark)", "invalid (no model call)", "invalid (model mismatch)",
            "not recorded", "not graded")
RUN_ID = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
# CELL_ID, LABEL: the ids and labels plan.py freezes (config.py owns the one definition; plan.py
# validates every cell against it at plan time, so status never emits what its own parser rejects).
# PHASE (ruling R-3): a closed enum. "starting": launch has begun (cell.launch_intent recorded) but
# no cell has reached attempt.process_started yet. "running": at least one has (a one-way move).
PHASE = ("starting", "running")
CAUSE_CODE = re.compile(r"HB-CELL-[0-9]{3}")
STOP_CODE = re.compile(r"HB-[A-Z]+-[0-9]{3}")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@dataclass(frozen=True)
class RunningCell:
    cell_id: str
    label: str
    elapsed_s: int
    budget_s: int
    killing: bool


@dataclass(frozen=True)
class Status:
    schema: str
    run_id: str
    checked_at: str
    liveness: str
    completion: str
    lock_age_s: int | None
    cells_total: int
    cells_ended: int
    outcomes: dict[str, int]
    validity: dict[str, int]
    causes: dict[str, int]
    running: list[RunningCell]
    decisions: list
    stop_code: str | None  # run.launch_stopped's code; null unless one was recorded (ruling R-3)
    phase: str  # starting | running (ruling R-3)
    graded: bool


def unknown_run_error(run_id: str) -> BenchError:
    return BenchError("HB-USR-001", f"no run {run_id} under runs/. Run bench plan to create one.")


def unknown_run_message(run_id: str) -> str:
    return str(unknown_run_error(run_id))


def require_known(run_dir: Path) -> None:
    """The one definition of "is this a known run" (a frozen plan.json): cli.py's `_run_dir` and
    `build` both call this rather than each re-checking the file (Simplifier: exists once)."""
    if not (run_dir / "plan.json").is_file():
        raise unknown_run_error(run_dir.name)


def _when(recorded_at: str) -> datetime:
    return datetime.fromisoformat(recorded_at)


def build(run_dir: Path, now: datetime | None = None, lock_age: float | None = None) -> Status:
    require_known(run_dir)
    now = now or datetime.now(UTC)
    view = views.load(run_dir)
    events = views.rows(run_dir, "events")
    lock = run_dir / ".lock"
    held = oslock.is_held(lock)
    age = None
    if held:
        age = round(lock_age if lock_age is not None else oslock.heartbeat_age(lock))
    staleness = view.plan.get("parameters", {}).get("lock_staleness", DEFAULT_PARAMETERS["lock_staleness"])
    liveness = "not running" if not held else ("alive" if age <= staleness else "stalled")
    completion = "complete" if view.completed else ("in progress" if held else "incomplete")
    started = {e["cell_id"]: e for e in events if e["kind"] == "attempt.process_started"}
    ended = {e["cell_id"] for e in events if e["kind"] == "attempt.process_ended"}
    prompt_sent = {e["cell_id"]: e for e in events if e["kind"] == "cell.prompt_sent"}
    running = []
    for c in view.plan["cells"]:
        cid = c["cell_id"]
        if cid in started and cid not in ended:
            sent = prompt_sent.get(cid)
            # The budget clock starts at cell.prompt_sent, matching the engine's own kill check
            # (_check_budgets measures from prompt_mono): a cell still handshaking has elapsed 0.
            elapsed = max(0, int((now - _when(sent["recorded_at"])).total_seconds())) if sent else 0
            running.append(RunningCell(cid, c.get("label", cid), elapsed, c["budget_seconds"], bool(sent) and elapsed > c["budget_seconds"]))
    outcomes: dict[str, int] = {}
    validity: dict[str, int] = {}
    causes: dict[str, int] = {}
    for cell in view.cells:
        if cell.cell_id in {r.cell_id for r in running}:
            continue
        outcomes[cell.outcome] = outcomes.get(cell.outcome, 0) + 1
        if cell.validity in VALIDITY:
            validity[cell.validity] = validity.get(cell.validity, 0) + 1
        if cell.code:
            causes[cell.code] = causes.get(cell.code, 0) + 1
    ended_count = sum(1 for c in view.cells if c.outcome in ("completed", "timed_out", "failed"))
    phase = "running" if started else "starting"
    stopped = [e for e in events if e["kind"] == "run.launch_stopped"]
    stop_code = stopped[-1]["code"] if stopped else None
    return Status(SCHEMA, view.run_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"), liveness, completion, age, len(view.cells), ended_count,
                  outcomes, validity, causes, running, [], stop_code, phase, view.grading_id is not None)


def _counts(title: str, order: tuple[str, ...], counts: dict[str, int]) -> str | None:
    parts = [f"{k} {counts[k]}" for k in order if counts.get(k)] + [f"{k} {v}" for k, v in sorted(counts.items()) if k not in order and v]
    return f"{title}: {', '.join(parts)}." if parts else None


def text(s: Status) -> str:
    if s.liveness == "alive":
        lines = [f"Run {s.run_id}: running. {s.cells_ended}/{s.cells_total} cells ended, {len(s.running)} running."]
    elif s.liveness == "stalled":
        lines = [f"Run {s.run_id}: stalled. The engine holds the lock but has not progressed for {s.lock_age_s} s."]
    else:
        lines = [f"Run {s.run_id}: not running ({s.completion}). {s.cells_ended}/{s.cells_total} cells ended."]
    for r in s.running:
        if r.killing:
            lines.append(f"{r.cell_id}: killing (unconfirmed, {r.elapsed_s - r.budget_s} s)")
        else:
            lines.append(f"{r.cell_id} {r.label}: running {r.elapsed_s} s of {r.budget_s} s")
    for line in (_counts("Outcomes", OUTCOMES, s.outcomes), _counts("Validity", VALIDITY, s.validity), _counts("Causes", (), s.causes)):
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def to_json(s: Status) -> str:
    return json.dumps(asdict(s), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require(ok: bool, what: str) -> None:
    if not ok:
        raise ValueError(f"bench-status/1: {what}")


def _int(value, what: str, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{what} must be a non-negative integer")


def _count_map(value, allowed, what: str) -> None:
    _require(isinstance(value, dict), f"{what} must be an object")
    for k, v in value.items():
        _require(k in allowed if isinstance(allowed, tuple) else bool(allowed.fullmatch(k)), f"{what} has an unknown key {k!r}")
        _int(v, f"{what}.{k}")


def _exact(data, cls) -> None:
    _require(isinstance(data, dict), f"{cls.__name__} must be an object")
    names = {f.name for f in fields(cls)}
    _require(set(data) == names, f"{cls.__name__} fields differ: missing {sorted(names - set(data))}, unknown {sorted(set(data) - names)}")


def parse(document: str) -> Status:
    """A `bench-status/1` document, validated strictly (ValueError on any deviation)."""
    data = json.loads(document)
    _exact(data, Status)
    _require(data["schema"] == SCHEMA, f"schema must be {SCHEMA}")
    _require(isinstance(data["run_id"], str) and bool(re.fullmatch(RUN_ID, data["run_id"])), "run_id is malformed")
    _require(isinstance(data["checked_at"], str) and bool(TIME.fullmatch(data["checked_at"])), "checked_at must be UTC ISO time")
    _require(data["liveness"] in LIVENESS, "liveness is not a known value")
    _require(data["completion"] in COMPLETION, "completion is not a known value")
    _int(data["lock_age_s"], "lock_age_s", nullable=True)
    _int(data["cells_total"], "cells_total")
    _int(data["cells_ended"], "cells_ended")
    _count_map(data["outcomes"], OUTCOMES, "outcomes")
    _count_map(data["validity"], VALIDITY, "validity")
    _count_map(data["causes"], CAUSE_CODE, "causes")
    _require(data["decisions"] == [], "decisions must be empty in phase 1")
    _require(data["stop_code"] is None or (isinstance(data["stop_code"], str) and bool(STOP_CODE.fullmatch(data["stop_code"]))),
              "stop_code is malformed")
    _require(data["phase"] in PHASE, "phase is not a known value")
    _require(isinstance(data["graded"], bool), "graded must be a boolean")
    _require(isinstance(data["running"], list), "running must be a list")
    running = []
    for r in data["running"]:
        _exact(r, RunningCell)
        _require(isinstance(r["cell_id"], str) and bool(CELL_ID.fullmatch(r["cell_id"])), "running.cell_id is malformed")
        _require(isinstance(r["label"], str) and bool(LABEL.fullmatch(r["label"])), "running.label is malformed")
        _int(r["elapsed_s"], "running.elapsed_s")
        _int(r["budget_s"], "running.budget_s")
        _require(isinstance(r["killing"], bool), "running.killing must be a boolean")
        running.append(RunningCell(**r))
    return Status(**{**data, "running": running})
