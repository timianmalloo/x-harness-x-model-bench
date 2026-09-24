"""The model's phase-1 guards, transcribed for conformance replay (US-44 AC3; design T3).

TABLE is the one source of truth for the ledger's transitions: for every transition, the model action it
implements (docs/design/run-lifecycle-model.md, mapping table), who writes it, and the per-cell order it
must keep. The engine consults it before every `events` append (`check_writer`), so it cannot write a
row the table does not give it. `replay(events)` checks a run's `events` in ledger order, and a run's
`scores` against the grading guards, per the phase-1 guards of `models/run_lifecycle.tla`; a violation is
a ConformanceError naming the guard. An unmapped transition is itself a violation, so neither the engine
nor the replay can drift from the table silently.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

UNMAPPED = "unmapped transition"
WRITE_INTENT_ONCE = "WriteIntent: exactly once, first"
NO_LAUNCH_AFTER_STOP = "NoLaunchAfterStop"
FOLLOWS_INTENT = "every transition follows cell.launch_intent"
AT_MOST_ONCE = "each transition at most once per cell (AtMostOnePrompt, one attempt in phase 1)"
PARALLELISM_BOUND = "ParallelismBound"
NO_OUTCOME_WHILE_RUNNING = "NoOutcomeWhileRunning: kill, confirm, then record"
NO_ARCHIVE_WHILE_LIVE = "NoArchiveWhileLive: archive after the outcome, with no live process"
ARCHIVED_CELLS_GET_GRADED = "ArchivedCellsGetGraded"
GRADED_ONCE_PER_PASS = "GradedOncePerPass"
ARCHIVE_KINDS = ("cell.archived", "cell.archive_failed")


@dataclass(frozen=True)
class Transition:
    action: str  # the model action it implements
    writer: str  # who appends it: "engine", "grading" (a grading pass) or "ledger" (a segment's own writer)
    after: tuple[str, ...] = ()  # this cell's transitions that must already be recorded ...
    after_rule: str = ""  # ... else this guard is named
    not_after: tuple[str, ...] = ()  # this cell's transitions it may not follow ...
    not_after_rule: str = ""  # ... else this guard is named


TABLE: dict[str, Transition] = {
    "run.started": Transition("(run start: Init)", "engine"),
    "cell.launch_intent": Transition("WriteIntent", "engine"),
    "cell.workspace_built": Transition("(internal progress)", "engine",
                                       not_after=("attempt.process_started",), not_after_rule="workspace before process"),
    "attempt.process_started": Transition("StartCell", "engine", not_after=("cell.outcome",),
                                          not_after_rule="NoPromptAfterOutcome / no launch after an outcome"),
    "attempt.session_opened": Transition("(internal progress)", "engine", after=("attempt.process_started",),
                                         after_rule="session after process"),
    "cell.prompt_sent": Transition("PersistPromptSent (then SendPrompt)", "engine",
                                   after=("attempt.process_started", "attempt.session_opened"),
                                   after_rule="PersistPromptSent needs StartCell and an open session",
                                   not_after=("attempt.process_ended", "cell.outcome"),
                                   not_after_rule="NoPromptAfterOutcome: no prompt once the process ended or the outcome is in"),
    "attempt.process_ended": Transition("CellExits / CellDies (confirmed)", "engine", after=("attempt.process_started",),
                                        after_rule="process_ended after process_started"),
    "cell.outcome": Transition("RecordExit / StartFails", "engine"),
    "cell.archived": Transition("Archive", "engine", after=("cell.outcome",), after_rule=NO_ARCHIVE_WHILE_LIVE),
    "cell.archive_failed": Transition("(archive refused: workspace kept, run incomplete)", "engine",
                                      after=("cell.outcome",), after_rule=NO_ARCHIVE_WHILE_LIVE),
    "cell.workspace_deleted": Transition("DeleteWorkspace", "engine", after=("cell.archived",),
                                         after_rule="NothingDeletedUnarchived"),
    "cell.workspace_kept": Transition("(delete refused: archive kept, workspace kept)", "engine", after=("cell.archived",),
                                      after_rule="NothingDeletedUnarchived"),
    "run.launch_stopped": Transition("(no further WriteIntent)", "engine"),
    "run.completed": Transition("(run end)", "engine"),
    "grading.started": Transition("GradeStart", "grading"),
    "grading.completed": Transition("GradeEnd", "grading"),
    "segment.abandoned": Transition("(ledger: a dead pass named by the next, HB-LED-004)", "grading"),
    "ledger.tail_repaired": Transition("(ledger)", "ledger"),
}
ENGINE_TRANSITIONS = frozenset(k for k, t in TABLE.items() if t.writer == "engine")
RULES = (UNMAPPED, WRITE_INTENT_ONCE, NO_LAUNCH_AFTER_STOP, FOLLOWS_INTENT, AT_MOST_ONCE, PARALLELISM_BOUND,
         NO_OUTCOME_WHILE_RUNNING, NO_ARCHIVE_WHILE_LIVE, ARCHIVED_CELLS_GET_GRADED, GRADED_ONCE_PER_PASS,
         *sorted({r for t in TABLE.values() for r in (t.after_rule, t.not_after_rule) if r}))


class ConformanceError(ValueError):
    pass


def check_writer(kind: str | None, writer: str) -> None:
    """Refuse a transition the table does not give this writer (the engine calls it before every events append)."""
    t = TABLE.get(kind or "")
    if t is None or t.writer != writer:
        raise ConformanceError(f"{kind!r} is not an {writer} transition in the lifecycle table")


def replay(events: list[dict], parallelism: int, scores: list[dict] = ()) -> None:
    seen: dict[str, list[str]] = defaultdict(list)
    running: set[str] = set()
    stopped = False
    archived_at_start: dict[str, set[str]] = {}  # grading_id -> cells archived when the pass started

    def fail(cell: str, rule: str, kind: str) -> None:
        raise ConformanceError(f"{rule}: {kind} for cell {cell} after {seen[cell]}")

    for e in events:
        kind = e.get("kind")
        t = TABLE.get(kind)
        if t is None:
            raise ConformanceError(f"{UNMAPPED} {kind!r} (not in the lifecycle table)")
        if kind == "run.launch_stopped":
            stopped = True
        if kind == "grading.started":
            archived_at_start[e["grading_id"]] = {c for c, d in seen.items() if "cell.archived" in d}
        cell = e.get("cell_id")
        if cell is None:
            continue
        done = seen[cell]
        if kind == "cell.launch_intent":
            if done:
                fail(cell, WRITE_INTENT_ONCE, kind)
            if stopped:
                fail(cell, NO_LAUNCH_AFTER_STOP, kind)
        elif not done:  # the intent is the only first transition, so a cell's record always starts with it
            fail(cell, FOLLOWS_INTENT, kind)
        if kind in done:  # a second intent has already failed above
            fail(cell, AT_MOST_ONCE, kind)
        if any(k not in done for k in t.after):
            fail(cell, t.after_rule, kind)
        if any(k in done for k in t.not_after):
            fail(cell, t.not_after_rule, kind)
        if kind == "attempt.process_started":
            running.add(cell)
            if len(running) > parallelism:
                raise ConformanceError(f"{PARALLELISM_BOUND}: {len(running)} cells running > {parallelism}")
        if kind == "attempt.process_ended":
            running.discard(cell)
        if kind == "cell.outcome" and cell in running:
            fail(cell, NO_OUTCOME_WHILE_RUNNING, kind)
        if kind in ARCHIVE_KINDS and cell in running:
            fail(cell, NO_ARCHIVE_WHILE_LIVE, kind)
        done.append(kind)
    graded: set[tuple[str, str, str]] = set()
    for sc in scores:
        key = (sc["grading_id"], sc["cell_id"], sc["metric_id"])
        if sc["cell_id"] not in archived_at_start.get(sc["grading_id"], set()):
            raise ConformanceError(f"{ARCHIVED_CELLS_GET_GRADED}: score {key} for a cell not archived when its pass started")
        if key in graded:
            raise ConformanceError(f"{GRADED_ONCE_PER_PASS}: score {key} written twice")
        graded.add(key)
