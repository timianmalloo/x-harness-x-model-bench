"""The model's phase-1 guards, transcribed for conformance replay (US-44 AC3; design T3).

MAPPING binds every ledger transition the engine can write to the model action it implements
(docs/design/run-lifecycle-model.md, mapping table). `replay(events)` checks a run's `events` in ledger
order against the phase-1 guards of `models/run_lifecycle.tla`; a violation is a ConformanceError
naming the guard. An unmapped transition is itself a violation, so the engine cannot drift from the
table silently.
"""

from __future__ import annotations

from collections import defaultdict

# transition -> (model action, phase)
MAPPING: dict[str, tuple[str, int]] = {
    "run.started": ("(run start: Init)", 1),
    "cell.launch_intent": ("WriteIntent", 1),
    "cell.workspace_built": ("(internal progress)", 1),
    "attempt.process_started": ("StartCell", 1),
    "attempt.session_opened": ("(internal progress)", 1),
    "cell.prompt_sent": ("PersistPromptSent (then SendPrompt)", 1),
    "attempt.process_ended": ("CellExits / CellDies (confirmed)", 1),
    "cell.outcome": ("RecordExit / StartFails", 1),
    "cell.archived": ("Archive", 1),
    "cell.workspace_deleted": ("DeleteWorkspace", 1),
    "cell.workspace_kept": ("(delete refused: archive kept, workspace kept)", 1),
    "run.launch_stopped": ("(no further WriteIntent)", 1),
    "grading.started": ("GradeStart", 1),
    "grading.completed": ("GradeEnd", 1),
    "run.completed": ("(run end)", 1),
    "ledger.tail_repaired": ("(ledger)", 1),
}


class ConformanceError(Exception):
    pass


def replay(events: list[dict], parallelism: int) -> None:
    seen: dict[str, list[str]] = defaultdict(list)
    running: set[str] = set()
    stopped = False

    def fail(cell: str, rule: str, kind: str) -> None:
        raise ConformanceError(f"{rule}: {kind} for cell {cell} after {seen[cell]}")

    for e in events:
        kind = e.get("kind")
        if kind not in MAPPING:
            raise ConformanceError(f"unmapped transition {kind!r} (not in the phase-1 mapping table)")
        if kind == "run.launch_stopped":
            stopped = True
        cell = e.get("cell_id")
        if cell is None:
            continue
        done = seen[cell]
        if kind == "cell.launch_intent":
            if done:
                fail(cell, "WriteIntent: exactly once, first", kind)
            if stopped:
                fail(cell, "NoLaunchAfterStop", kind)
        elif not done or done[0] != "cell.launch_intent":
            fail(cell, "every transition follows cell.launch_intent", kind)
        if kind in done and kind != "cell.launch_intent":
            fail(cell, "each transition at most once per cell (AtMostOnePrompt, one attempt in phase 1)", kind)
        if kind == "cell.workspace_built" and "attempt.process_started" in done:
            fail(cell, "workspace before process", kind)
        if kind == "attempt.process_started":
            if "cell.outcome" in done:
                fail(cell, "NoPromptAfterOutcome / no launch after an outcome", kind)
            running.add(cell)
            if len(running) > parallelism:
                raise ConformanceError(f"ParallelismBound: {len(running)} cells running > {parallelism}")
        if kind == "attempt.session_opened" and "attempt.process_started" not in done:
            fail(cell, "session after process", kind)
        if kind == "cell.prompt_sent" and (
            "attempt.session_opened" not in done or "cell.outcome" in done or "attempt.process_ended" in done
        ):
            fail(cell, "prompt_sent needs an open session and no outcome (NoPromptAfterOutcome)", kind)
        if kind == "attempt.process_ended":
            if "attempt.process_started" not in done:
                fail(cell, "process_ended after process_started", kind)
            running.discard(cell)
        if kind == "cell.outcome" and cell in running:
            fail(cell, "NoOutcomeWhileRunning: kill, confirm, then record", kind)
        if kind == "cell.archived" and ("cell.outcome" not in done or cell in running):
            fail(cell, "NoArchiveWhileLive: archive after the outcome, with no live process", kind)
        if kind in ("cell.workspace_deleted", "cell.workspace_kept") and "cell.archived" not in done:
            fail(cell, "NothingDeletedUnarchived", kind)
        done.append(kind)
