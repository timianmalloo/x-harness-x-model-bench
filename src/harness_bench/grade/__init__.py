"""Graders: one module per metric family; each turns one archived cell into metric values (design phase3-graders).

Rules (proposal, "Grading pipeline"):
- Deterministic before judged. A judge never scores what a script can measure.
- Re-grading an archived run reproduces every score byte-for-byte (judges: pinned model,
  temperature 0, verdicts cached on artifact hashes).
- Every score carries an evidence pointer (file, line, log offset).
- A measurement that does not exist is NA, `Score(None, reason)`, and is excluded from composites. Never 0 (US-27).

The contract (W3-GRADE-CORE slice 1): a grader is `grade_cell(inp: CellInput) -> Mapping[str, Score]`, keyed by the
metric ids in `inp.metrics`. `runner.GRADERS` dispatches by the task's `graders` list; a metric the grader does not
return is NA `not built`, and an unregistered grader is NA `not built` for each of its metrics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench.telemetry import Extraction
from harness_bench.telemetry.normalize import TurnUsage


@dataclass(frozen=True)
class Score:
    """One metric value for one cell. Pattern: Special Case (NA is `Score(None, reason)`, from grader to view)."""

    value: int | Decimal | None  # None <=> NA; a Decimal is written at the catalog scale (no floats, ADR-0006)
    reason: str | None  # set iff value is None (US-27); from the design's closed vocabulary, never agent text or a path
    evidence: str = ""  # a path relative to run_dir, optionally ":line" or "@offset"

    def __post_init__(self) -> None:
        if self.value is not None and (isinstance(self.value, bool) or not isinstance(self.value, int | Decimal)):
            raise TypeError(f"a score value is an int, a Decimal or None, not {type(self.value).__name__}")
        if (self.value is None) != (self.reason is not None):
            raise ValueError("a score is a value with no reason, or NA (None) with a reason")


@dataclass(frozen=True)
class CellInput:
    """Everything a grader may read; nothing else. Pattern: Parameter Object (built once per cell and grader).

    Two fields beyond the design's list, both values the runner already holds for the pass (recorded deviation):
    `extraction` (the HB-TEL-001 missing usage fields are on no ledger row) and `prices` (the price-list check stays
    the runner's, so there is one reader of `bench/prices.yaml` per pass).
    """

    run_dir: Path  # evidence paths are relative to it
    root: Path  # bench root: bench/metrics.yaml, bench/rubrics/
    plan: Mapping  # the confirmed plan (read-only); the grading step timeout is plan["parameters"]
    cell: Mapping  # the plan's cell record
    task: Mapping  # task.yaml as loaded; a grader that reads the task runs only when the task is current
    task_dir: Path
    archive: Path  # run_dir/archive/<cid>/attempt-<n> (READ-ONLY)
    out_dir: Path  # run_dir/grading/<gid>/<cid>/<grader>/: the only place a grader writes
    events: tuple[Mapping, ...]  # this cell's engine events
    record_reason: str | None  # why the native record was missing or unreadable (R-15), or None
    model_calls: tuple[Mapping, ...]  # this cell's rows under the pass's extraction_id (unstamped)
    tool_calls: tuple[Mapping, ...]
    turn_usage: tuple[TurnUsage, ...]
    metrics: Mapping[str, Mapping]  # the catalog entries of this grader's applicable metrics
    allow_model_calls: bool  # R-58 DR-2: False in the in-run pass
    extraction: Extraction | None  # the native record as read, or None when there was none to read
    prices: Mapping | None  # the plan's price list; None when bench/prices.yaml changed since the plan
    # The pass's append, for the facts a grader records beside its scores: the judge grader's `verdict_uses` rows and
    # its calls' `model_calls` rows, principal gateway (ADR-0006 Amendment 3). None outside a grading pass.
    emit: Callable[[str, dict], None] | None = None


GraderFn = Callable[[CellInput], Mapping[str, Score]]

__all__ = ["CellInput", "GraderFn", "Score"]
