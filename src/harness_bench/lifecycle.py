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
CONTROL_APPLIED_ONCE = "ControlAppliedOnce"
RUN_STOPPED_ONCE = "RunStoppedOnce"
NO_DECISION_AFTER_STOP = "NoDecisionAfterStop"
DECISION_RESOLVED_ONCE = "DecisionResolvedOnce"
RESOLVED_AFTER_OPENED = "a decision.resolved follows its decision.opened"
NO_LAUNCH_WHILE_DECISION_OPEN = "NoLaunchWhileDecisionOpen"
SKIPPED = "skipped (decision)"  # an outcome written with no launch: the cell's first and only row (design 8.3)
# Design 6.1: each decision kind's closed options and the default applied on timeout. The engine opens decisions from
# this table and bench-status/1 validates against it, so the wire and the engine share one definition (design 4.6).
DECISION_KINDS = {
    "blocked_cell": (("continue", "stop"), "continue"),
    "qualification_gap": (("skip_combo", "stop"), "skip_combo"),
    "spend_cap": (("stop", "continue"), "stop"),
}
DECISION_STATES = ("open", "answered", "default applied (timeout)", "superseded (stop)")
FOLLOWS_INTENT = "every transition follows cell.launch_intent"
AT_MOST_ONCE = "each transition at most once per cell (AtMostOnePrompt, one attempt in phase 1)"
PARALLELISM_BOUND = "ParallelismBound"
NO_OUTCOME_WHILE_RUNNING = "NoOutcomeWhileRunning: kill, confirm, then record"
NO_ARCHIVE_WHILE_LIVE = "NoArchiveWhileLive: archive after the outcome, with no live process"
ARCHIVED_CELLS_GET_GRADED = "ArchivedCellsGetGraded"
GRADED_ONCE_PER_PASS = "GradedOncePerPass"
ARCHIVE_KINDS = ("cell.archived", "cell.archive_failed")
PROMPT_ONCE_PER_TURN = "PromptOncePerTurn"
SNAPSHOT_BEFORE_NEXT_TURN = "SnapshotBeforeNextTurn"
CRASHED_TURN_PREDICATE = "CrashedTurnPredicate"
TURN_KINDS = ("cell.prompt_sent", "cell.turn_ended", "cell.turn_snapshot_archived")


@dataclass(frozen=True)
class Transition:
    action: str  # the model action it implements
    writer: str  # who appends it: "engine", "grading" (a grading pass) or "ledger" (a segment's own writer, incl. the dead-segment marker)
    after: tuple[str, ...] = ()  # this cell's transitions that must already be recorded ...
    after_rule: str = ""  # ... else this guard is named
    not_after: tuple[str, ...] = ()  # this cell's transitions it may not follow ...
    not_after_rule: str = ""  # ... else this guard is named
    turn_keyed: bool = False


TABLE: dict[str, Transition] = {
    "run.started": Transition("(run start: Init)", "engine"),
    "run.resumed": Transition("Resume", "engine"),
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
                                   not_after_rule="NoPromptAfterOutcome: no prompt once the process ended or the outcome is in",
                                   turn_keyed=True),
    "cell.turn_ended": Transition("TurnEnd", "engine", after=("cell.prompt_sent",),
                                  after_rule="turn_ended follows its prompt_sent", turn_keyed=True),
    "cell.turn_snapshot_archived": Transition("SnapRecord", "engine", after=("cell.turn_ended",),
                                              after_rule="SnapshotAfterTurnEnd", turn_keyed=True),
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
    "control.applied": Transition("ApplyStop / ApplyAnswer (controlApplied)", "engine"),
    "run.stopped": Transition("ApplyStop", "engine"),
    "decision.opened": Transition("RaiseDecision", "engine"),
    "decision.resolved": Transition("ApplyAnswer / TimeoutDefault / ApplyStop (supersede)", "engine"),
    "run.completed": Transition("(run end)", "engine"),
    "grading.started": Transition("GradeStart", "grading"),
    "grading.completed": Transition("GradeEnd", "grading"),
    "segment.abandoned": Transition("(ledger: a dead pass named by the next, HB-LED-004)", "ledger"),
    "ledger.tail_repaired": Transition("(ledger)", "ledger"),
}
ENGINE_TRANSITIONS = frozenset(k for k, t in TABLE.items() if t.writer == "engine")
RULES = (UNMAPPED, WRITE_INTENT_ONCE, NO_LAUNCH_AFTER_STOP, CONTROL_APPLIED_ONCE, RUN_STOPPED_ONCE,
         NO_DECISION_AFTER_STOP, DECISION_RESOLVED_ONCE, RESOLVED_AFTER_OPENED, NO_LAUNCH_WHILE_DECISION_OPEN,
         FOLLOWS_INTENT, AT_MOST_ONCE, PARALLELISM_BOUND,
         PROMPT_ONCE_PER_TURN, SNAPSHOT_BEFORE_NEXT_TURN, CRASHED_TURN_PREDICATE,
         NO_OUTCOME_WHILE_RUNNING, NO_ARCHIVE_WHILE_LIVE, ARCHIVED_CELLS_GET_GRADED, GRADED_ONCE_PER_PASS,
         *sorted({r for t in TABLE.values() for r in (t.after_rule, t.not_after_rule) if r}))


class ConformanceError(ValueError):
    pass


def completed(events: list[dict]) -> bool:
    """D-K5, the one definition: complete iff a completion row follows the last resume row (or no resume row exists)."""
    for row in reversed(events):
        if row["kind"] == "run.completed":
            return True
        if row["kind"] == "run.resumed":
            return False
    return False


def is_cell_start(row: dict) -> bool:
    """The first prompt starts the cell clock; legacy rows have turn 1."""
    return row.get("turn", 1) == 1


def check_writer(kind: str | None, writer: str) -> None:
    """Refuse a transition the table does not give this writer (the engine calls it before every events append)."""
    t = TABLE.get(kind or "")
    if t is None or t.writer != writer:
        raise ConformanceError(f"{kind!r} is not an {writer} transition in the lifecycle table")


def replay(events: list[dict], parallelism: int, scores: list[dict] = ()) -> None:
    seen: dict[str, list[str | tuple[str, int]]] = defaultdict(list)
    running: set[str] = set()
    stopped = False
    stop_applied = False
    run_stopped = False
    intents: dict[str, int] = defaultdict(int)
    applied_controls: set[str] = set()
    opened: set[str] = set()
    resolved: set[str] = set()
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
        if kind == "run.resumed":
            stopped = stop_applied  # a launch stop can clear; an actual stop cannot (D-K4/D-K10)
        if kind == "control.applied":
            uid = e["uuid"]
            if uid in applied_controls:
                raise ConformanceError(f"{CONTROL_APPLIED_ONCE}: {uid}")
            applied_controls.add(uid)
            if e.get("control") == "stop" and e.get("effect") == "applied":
                stopped = stop_applied = True
        if kind == "run.stopped":
            if run_stopped:
                raise ConformanceError(RUN_STOPPED_ONCE)
            run_stopped = True
            stopped = stop_applied = True
        if kind == "decision.opened":
            if run_stopped:
                raise ConformanceError(f"{NO_DECISION_AFTER_STOP}: {e['decision_id']}")
            opened.add(e["decision_id"])
        if kind == "decision.resolved":
            did = e["decision_id"]
            if did in resolved:
                raise ConformanceError(f"{DECISION_RESOLVED_ONCE}: {did}")
            if did not in opened:
                raise ConformanceError(f"{RESOLVED_AFTER_OPENED}: {did}")
            resolved.add(did)
            if e.get("option") == "stop":
                stopped = stop_applied = True
        if kind == "grading.started":
            archived_at_start[e["grading_id"]] = {c for c, d in seen.items() if "cell.archived" in d}
        cell = e.get("cell_id")
        if cell is None:
            continue
        done = seen[cell]
        skip = kind == "cell.outcome" and e.get("outcome") == SKIPPED and not done  # never launched (design 8.3)
        if kind == "cell.launch_intent":
            if stopped:
                fail(cell, NO_LAUNCH_AFTER_STOP, kind)
            if done:
                if (intents[cell] != 1 or "cell.outcome" in done
                        or any(isinstance(k, tuple) and k[0] == "cell.prompt_sent" for k in done)):
                    fail(cell, WRITE_INTENT_ONCE, kind)
                # R2: the old process is confirmed gone before a never-prompted cell is relaunched.
                done.clear()
                running.discard(cell)
            intents[cell] += 1
            if opened - resolved:
                fail(cell, NO_LAUNCH_WHILE_DECISION_OPEN, kind)
        elif "cell.launch_intent" not in done and not skip:  # the intent is the only first transition but a skip
            fail(cell, FOLLOWS_INTENT, kind)
        turn = e.get("turn", 1)
        key = (kind, turn) if t.turn_keyed else kind
        if key in done:  # a second intent has already failed above
            fail(cell, PROMPT_ONCE_PER_TURN if kind == "cell.prompt_sent" else AT_MOST_ONCE, kind)
        if any(((k, turn) if t.turn_keyed and k in TURN_KINDS else k) not in done for k in t.after):
            fail(cell, t.after_rule, kind)
        if any(k in done for k in t.not_after):
            fail(cell, t.not_after_rule, kind)
        if kind == "cell.prompt_sent" and turn > 1 and ("cell.turn_snapshot_archived", turn - 1) not in done:
            fail(cell, SNAPSHOT_BEFORE_NEXT_TURN, kind)
        if kind == "cell.turn_snapshot_archived" and ("cell.prompt_sent", turn + 1) in done:
            fail(cell, t.after_rule, kind)
        if kind == "cell.outcome" and e.get("code") in {"HB-CELL-118", "HB-CELL-119"}:
            prompts = {n for k, n in (r for r in done if isinstance(r, tuple)) if k == "cell.prompt_sent"}
            ended = {n for k, n in (r for r in done if isinstance(r, tuple)) if k == "cell.turn_ended"}
            snapshots = {n for k, n in (r for r in done if isinstance(r, tuple)) if k == "cell.turn_snapshot_archived"}
            waiting = prompts <= ended and any(n in snapshots and n + 1 not in prompts for n in ended)
            if (e["code"] == "HB-CELL-119") != waiting:
                fail(cell, CRASHED_TURN_PREDICATE, kind)
        if kind == "attempt.process_started":
            running.add(cell)
            if len(running) > parallelism:
                raise ConformanceError(f"{PARALLELISM_BOUND}: {len(running)} cells running > {parallelism}")
        if kind == "attempt.process_ended":
            running.discard(cell)
        if kind == "cell.outcome" and isinstance(e.get("resume"), dict):
            reconciliation = e["resume"]
            if (reconciliation.get("segment_id") and isinstance(reconciliation.get("turn"), int)
                    and reconciliation.get("phase") in {"mid-turn", "between-turns", "turn-complete"}):
                running.discard(cell)  # resume records only after confirming the old process gone (D-K2)
        if kind == "cell.outcome" and cell in running:
            fail(cell, NO_OUTCOME_WHILE_RUNNING, kind)
        if kind in ARCHIVE_KINDS and cell in running:
            fail(cell, NO_ARCHIVE_WHILE_LIVE, kind)
        done.append(key)
    graded: set[tuple[str, str, str]] = set()
    for sc in scores:
        key = (sc["grading_id"], sc["cell_id"], sc["metric_id"])
        if sc["cell_id"] not in archived_at_start.get(sc["grading_id"], set()):
            raise ConformanceError(f"{ARCHIVED_CELLS_GET_GRADED}: score {key} for a cell not archived when its pass started")
        if key in graded:
            raise ConformanceError(f"{GRADED_ONCE_PER_PASS}: score {key} written twice")
        graded.add(key)
