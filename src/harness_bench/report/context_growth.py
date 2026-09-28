"""`report.context_growth`: the report-only `ContextGrowth` projection (design `phase4-report.md`
section 4, section 6 row 8, slice R6).

Grain: one row is exactly one (combo, pack, task, turn index); measures: median prompt tokens over
repetitions (non-additive) with a min/max band, and a compaction flag. The design names the source as
"`turn_usage` rows, ordered by turn" (section 4).

Checked this slice: `views.turn_usage` maps one `turn_usage` ledger row to one `normalize.TurnUsage`
(`views.py:242-244`), and that fact is written **exactly once** per `(run_id, cell_id, attempt, model)`
-- `views.py:57`'s `KEYS` entry is that four-tuple, and `engine.py:663-666` writes it by first summing
every `normalize.TurnUsage` entry the attempt produced through `_usage_per_model`
(`engine.py:864-871`, "One total per model: a turn_usage row's key is (run, cell, attempt, model), so
entries are summed first") and recording one row per model. No ledger fact carries a turn index or an
ordered per-turn snapshot, for either usage source (`acp_turn` or `native_record`): the trajectory
across turns is lost at record time, not merely unread by the views layer.

assume: a per-turn breakdown would need `engine.py` to write one `turn_usage` row per turn (a new
`turn` field, one `record()` call per entry instead of one call per `_usage_per_model` total) -- a
ledger amendment. That is out of this slice's scope (`board.py`, `board.export` and any dependency are
Not in scope for R6). Confirmed by: that amendment landing as its own dated ledger change, after which
`build()` below gains a real source to read. If false -- if no per-turn source is ever added -- Context
growth stays in its not-recorded state permanently, and the projection should be rebuilt around
whatever source (if any) turns out to carry per-turn usage, rather than `turn_usage`.

`build()` therefore always returns the not-recorded state today (every task reads design row 8's own
"task without turns" copy, verbatim, because every task truly has none). `TaskSeries`/`TaskGrowth` and
`report/html.py`'s renderer are still built to the full design, so a future producer needs only to
fill a `TaskSeries` -- no renderer change.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness_bench import views

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


def build(view: views.RunView) -> ContextGrowthResult:
    """The real projection: always not-recorded today (see the module docstring's `assume:`).
    Enumerates every task this run planned, so the selector still names each one with its own reason,
    never a placeholder and never invented turn data."""
    tasks = sorted({_task_id(c) for c in view.cells})
    return ContextGrowthResult(
        tasks=tuple(TaskGrowth(task=t, series=(), reason=NO_TURNS.format(task=t)) for t in tasks)
    )
