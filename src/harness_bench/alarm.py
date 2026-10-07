"""Liveness and alarm check (W1-K §6.2, ADR-0021 §7).

`check` is the pure core `bench status <run_id> --alarm-after <s>` renders. Work left is `resume.has_work` (D-K12, R-102),
imported and never re-implemented here: this module carries no definition of "pending" of its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from harness_bench import oslock, status, views
from harness_bench.plan import DEFAULT_PARAMETERS
from harness_bench.resume import has_work


@dataclass(frozen=True)
class AlarmResult:
    code: str
    cause: str
    last_progress_at: str | None  # None: not recorded (the alarm fails closed)
    age_s: float | None  # ALM-001: the heartbeat age (the gap since progress when the lock is free); ALM-002: the gap; None: not recorded


def _epoch(recorded_at: str) -> float:
    return datetime.fromisoformat(recorded_at).timestamp()


def check(
    run_dir: Path,
    after_s: float,
    now: float | None = None,
    lock_age: float | None = None,
) -> AlarmResult | None:
    """HB-ALM-001 when work is left and the engine is not alive; HB-ALM-002 when it is alive and silent past `after_s`; else None."""
    status.require_known(run_dir)
    plan = views.load(run_dir, any_kind=True).plan  # views owns the stored-plan read (test_discriminate's reader table)
    rows = [row for sid, segment in views.segment_rows(run_dir, "events") if sid.startswith(views.ENGINE_PREFIX) for row in segment]
    if not has_work(plan, rows):
        return None
    now = time.time() if now is None else now
    last = status.last_progress_at(run_dir)
    gap = None if last is None else max(0.0, now - _epoch(last))
    shown = "not recorded" if last is None else last
    lock = run_dir / ".lock"
    if not oslock.is_held(lock):
        return AlarmResult("HB-ALM-001", f"engine not running, last progress {shown}; run: bench run {run_dir.name}", last, gap)
    age = lock_age if lock_age is not None else oslock.heartbeat_age(lock)
    staleness = plan.get("parameters", {}).get("lock_staleness", DEFAULT_PARAMETERS["lock_staleness"])
    if age > staleness:
        return AlarmResult("HB-ALM-001", f"engine stalled, heartbeat {round(age)} s old (limit {staleness} s), last progress {shown}; "
                                         f"run: bench run {run_dir.name}", last, age)
    if gap is None:
        return AlarmResult("HB-ALM-002", f"progress not recorded (threshold {after_s:g} s)", None, None)
    if gap > after_s:
        return AlarmResult("HB-ALM-002", f"no progress for {round(gap)} s (threshold {after_s:g} s), last progress {shown}", last, gap)
    return None
