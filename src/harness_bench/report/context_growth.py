"""`report.context_growth`: the report-only `ContextGrowth` projection (design `phase4-report.md`
section 4, section 6 row 8, slice R6).

Grain: one row is exactly one (combo, pack, task, turn index); measures: median prompt tokens over
repetitions (non-additive) with a min/max band, and a compaction flag.

Source (checked this slice, join R6b's finding resolved): the design named `turn_usage` rows, but
`turn_usage` is one summed row per (run, cell, attempt, model) -- `views.py:57`'s `KEYS` entry is that
four-tuple, and `engine.py`'s `_usage_per_model` sums every turn before it writes one row -- so it
carries no per-turn or per-call grain at all. The `model_calls` fact does: one row is exactly one
model call, keyed `(run_id, extraction_id, principal, native_session_id, native_ordinal, model)`
(`views.py:55`). `views._cell_view` (`views.py:474`) already reads a cell's current-extraction
`model_calls` rows; this module reads the same fact directly through the public `views.rows()` (no new
ledger fact -- ADR-0006 derive, don't store), filtered and ordered itself so a report-only concern
never grows `views.CellView`.

Principal (cited from its producer, `telemetry/normalize.py:135`, `model_call_rows`): an agent's own
call is stamped `principal=cell_id` -- the same value as the row's `cell_id`. A judge or gateway call
is stamped `principal="gateway"`, `cell_id=None` (`gateway/pipeline.py:170`), so it can never match a
real cell id on either field. Filtering on `principal == cell_id` (redundant with, and stated beside,
the existing `cell_id` equality) is the one place this module states that exclusion, rather than
relying on the coincidence silently.

NA rules (grade/cost.py's `_context_growth`, the peak-context-size scorer, already draws them for one
value; this module reuses its reason constants -- one definition, DM7): a cell whose profile
`usage_source` is `acp_turn` reads `ACP_MISSES_CALLS` (the native record misses calls entirely, so a
median is not resilient to the calls it misses); a Copilot cell reads `SESSION_TOTALS` regardless of
source (Copilot's native record is the last shutdown's per-model session total, never per call).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

from harness_bench import views
from harness_bench.grade.cost import ACP_MISSES_CALLS, SESSION_TOTALS

NO_TURNS = "No turns recorded for {task}."


@dataclass(frozen=True)
class TaskSeries:
    """One (combo, pack)'s line for one task: the turn indices it has a point for, the median
    prompt tokens over repetitions at each turn, the min/max band, and which of those turns had a
    compaction (design section 6 row 8: "compaction markers as ▲ plus text in the table")."""

    combo: str
    pack: str
    turns: tuple[int, ...]
    median: tuple[int, ...]
    lo: tuple[int, ...]
    hi: tuple[int, ...]
    compactions: tuple[int, ...] = ()


@dataclass(frozen=True)
class TaskGrowth:
    """One task's selector option (design row 8: "the option stays, with its reason"): its series
    (empty when the task has no turns recorded) and, when empty, the exact reason text."""

    task: str
    series: tuple[TaskSeries, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class ContextGrowthResult:
    tasks: tuple[TaskGrowth, ...] = ()


def _task_id(cell: views.CellView) -> str:
    """A cell's task id, read from its label's own first segment (the one place a label is built,
    `plan.py:78-79`, `f"{task}.{combo}.pack-{pack}.r{rep}"`) -- the same read `report/html.py:_task_id`
    and `_runs`'s `data-task` use, so the selector's tasks and the Runs filter's tasks never drift."""
    return cell.label.split(".", 1)[0]


def _na_reason(view: views.RunView, cell: views.CellView) -> str | None:
    """The same two branches, same order, as `grade/cost.py`'s `_context_growth`: source first (it
    is the stronger claim -- no calls at all), then harness (Copilot's calls are real rows, just not
    per-call totals)."""
    profile = (view.plan.get("profiles") or {}).get(cell.harness) or {}
    if profile.get("usage_source") == "acp_turn":
        return ACP_MISSES_CALLS
    if cell.harness == "copilot":
        return SESSION_TOTALS
    return None


def _size(call: dict) -> int:
    """Peak-context-size's own formula (`grade/cost.py`'s `_context_growth`): one call's prompt is
    everything it sent -- uncached input, cache read and cache write are disjoint buckets (ADR-0006)."""
    return call["uncached_input"] + call["cache_read"] + call["cache_write"]


def _cell_calls(run_dir: Path, cid: str, extraction_id: str) -> list[dict]:
    """This cell's own model calls, current extraction only, ordered by native_ordinal (the call's
    real sequence -- never the ledger row order, which the fact does not promise)."""
    rows = [r for r in views.rows(run_dir, "model_calls")
            if r["cell_id"] == cid and r["extraction_id"] == extraction_id and r["principal"] == cid]
    return sorted(rows, key=lambda r: r["native_ordinal"])


def _series(combo: str, pack: str, per_rep: list[list[dict]]) -> TaskSeries:
    """`per_rep`: each repetition's own ordered calls, at least one call each. The series only ever
    plots the indices every repetition reached, so a median at a plotted index is always over the
    full repetition set, never a partial one."""
    n = min(len(calls) for calls in per_rep)
    sizes = [[_size(calls[i]) for calls in per_rep] for i in range(n)]
    turns = tuple(range(1, n + 1))
    median = tuple(round(statistics.median(s)) for s in sizes)
    lo = tuple(min(s) for s in sizes)
    hi = tuple(max(s) for s in sizes)
    # assume: a compaction is flagged on the series' own (already-aggregated) median -- index i (i>0)
    # is flagged when median[i] < median[i-1] -- because the chart and table draw one line and one
    # compaction flag per (combo, pack, call index), never one per repetition. Confirmed by: a design
    # amendment naming the rule against the rendered series explicitly (design section 6 row 8 names
    # only "a line per combo", not per repetition). If false -- if a compaction is meant per
    # repetition -- a repetition whose own drop the median smooths over goes unflagged here, and the
    # ▲ mark under-reports real compactions; the fix is to flag index i whenever any repetition's own
    # call dropped, not only the median.
    compactions = tuple(turns[i] for i in range(1, n) if median[i] < median[i - 1])
    return TaskSeries(combo=combo, pack=pack, turns=turns, median=median, lo=lo, hi=hi, compactions=compactions)


def build(view: views.RunView, run_dir: Path | None = None) -> ContextGrowthResult:
    """Per (combo, pack, task): the per-call context-size series from the cell's current-extraction
    `model_calls` rows, ordered by native_ordinal, over the task's repetitions -- or, when the source
    or harness rules it out, or no call was ever recorded, the task's own NA reason (never a
    fabricated trajectory). A task with at least one plottable (combo, pack) series shows only that
    series (design section 4/6 row 8 give `TaskGrowth` one reason slot, for the whole task, not one
    per excluded combo; a task mixing a plottable combo with an NA one shows the plottable one only)."""
    task_ids = sorted({_task_id(c) for c in view.cells})
    groups: dict[tuple[str, str, str], list[views.CellView]] = {}
    for c in view.cells:
        groups.setdefault((_task_id(c), c.combo, c.pack), []).append(c)

    series_by_task: dict[str, list[TaskSeries]] = {t: [] for t in task_ids}
    reason_by_task: dict[str, str] = {}
    for (task, combo, pack), cells in groups.items():
        reason = _na_reason(view, cells[0])
        if reason is not None or run_dir is None:
            reason_by_task.setdefault(task, reason or NO_TURNS.format(task=task))
            continue
        per_rep = [calls for c in cells if c.extraction_id is not None
                   for calls in (_cell_calls(run_dir, c.cell_id, c.extraction_id),) if calls]
        if not per_rep:
            reason_by_task.setdefault(task, NO_TURNS.format(task=task))
            continue
        series_by_task[task].append(_series(combo, pack, per_rep))

    tasks = tuple(
        TaskGrowth(task=t, series=tuple(series_by_task[t]))
        if series_by_task[t]
        else TaskGrowth(task=t, series=(), reason=reason_by_task.get(t, NO_TURNS.format(task=t)))
        for t in task_ids
    )
    return ContextGrowthResult(tasks=tasks)
