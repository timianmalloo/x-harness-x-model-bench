"""Conformance of the engine to models/run_lifecycle.tla (US-44 AC3; design T3).

(a) One source of truth: the transition table in lifecycle.py. The engine consults it and refuses to write
    a row it does not own; every engine row of the table is still written by the engine.
(b) Replay: the engine tests replay every run's events against the guards (test_engine.py).
(c) One seeded out-of-order ledger per guard, each rejected by the replay under the rule it names.
"""

import re
from pathlib import Path

import pytest

from harness_bench import engine, ledger, lifecycle

ENGINE_SOURCE = Path(engine.__file__).read_text(encoding="utf-8")

GOOD = [
    {"kind": "run.started"},
    {"kind": "cell.launch_intent", "cell_id": "a"},
    {"kind": "cell.workspace_built", "cell_id": "a"},
    {"kind": "attempt.process_started", "cell_id": "a"},
    {"kind": "attempt.session_opened", "cell_id": "a"},
    {"kind": "cell.prompt_sent", "cell_id": "a"},
    {"kind": "attempt.process_ended", "cell_id": "a"},
    {"kind": "cell.outcome", "cell_id": "a"},
    {"kind": "cell.archived", "cell_id": "a"},
    {"kind": "cell.workspace_deleted", "cell_id": "a"},
    {"kind": "run.completed"},
]


def _swap(k1, k2):
    events = list(GOOD)
    i = next(n for n, e in enumerate(events) if e["kind"] == k1)
    j = next(n for n, e in enumerate(events) if e["kind"] == k2)
    events[i], events[j] = events[j], events[i]
    return events


def _cell(*kinds):
    return [GOOD[0]] + [{"kind": k, "cell_id": "a"} for k in kinds]


def test_the_engine_consults_the_table_and_writes_only_its_own_rows(tmp_path):  # T1-16
    eng = engine.Engine({"parameters": {}, "trace_id": "a" * 32}, None)
    eng.writers["events"] = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    try:
        for kind in ("cell.relaunched", "grading.started"):  # unmapped; mapped but written by the grading pass
            with pytest.raises(lifecycle.ConformanceError, match="not an engine transition"):
                eng._append_now("events", {"kind": kind})
        assert ledger.read_segment(tmp_path / "events" / "engine-1.jsonl") == []
    finally:
        eng.writers["events"].close()


def test_every_engine_row_of_the_table_is_written_by_the_engine():
    # a table cannot show that a row is still written, only the writer's source can: a literal scan, no AST
    written = set(re.findall(r'"kind": "([a-z_]+\.[a-z_.]+)"', ENGINE_SOURCE))  # events kinds are dotted; turn_usage is not
    assert lifecycle.ENGINE_TRANSITIONS == written, sorted(lifecycle.ENGINE_TRANSITIONS ^ written)


def test_each_writer_may_write_its_own_rows_and_only_those():
    for kind, t in lifecycle.TABLE.items():
        lifecycle.check_writer(kind, t.writer)
        for other in {"engine", "grading", "ledger"} - {t.writer}:
            with pytest.raises(lifecycle.ConformanceError):
                lifecycle.check_writer(kind, other)
    with pytest.raises(lifecycle.ConformanceError):
        lifecycle.check_writer(None, "engine")


def test_the_table_is_immutable():
    with pytest.raises(AttributeError):
        lifecycle.TABLE["run.started"].writer = "grading"


def test_a_well_ordered_run_conforms():
    lifecycle.replay(GOOD, parallelism=1)


SEEDED = {  # name -> (events, scores, the rule the replay must name)
    "an unmapped transition": (GOOD[:3] + [{"kind": "cell.relaunched", "cell_id": "a"}], [], "unmapped transition"),
    "prompt_sent before process_started (WriteIntent/StartCell order)":
        (_swap("attempt.process_started", "cell.prompt_sent"), [], "StartCell"),
    "a second prompt (AtMostOnePrompt)":
        (GOOD[:6] + [{"kind": "cell.prompt_sent", "cell_id": "a"}] + GOOD[6:], [], "AtMostOnePrompt"),
    "outcome before the process is confirmed gone (NoOutcomeWhileRunning)":
        (_swap("attempt.process_ended", "cell.outcome"), [], "NoOutcomeWhileRunning"),
    "archived before the outcome (NoArchiveWhileLive)": (_swap("cell.outcome", "cell.archived"), [], "NoArchiveWhileLive"),
    "archive failed before the outcome (NoArchiveWhileLive)":
        (_cell("cell.launch_intent", "cell.archive_failed"), [], "NoArchiveWhileLive"),
    "deleted before archived (NothingDeletedUnarchived)":
        (_swap("cell.archived", "cell.workspace_deleted"), [], "NothingDeletedUnarchived"),
    "a transition before the launch intent": ([GOOD[0], GOOD[2], GOOD[1]] + GOOD[3:], [], "follows cell.launch_intent"),
    "prompt after the outcome (NoPromptAfterOutcome)":
        (GOOD[:4] + [GOOD[4], GOOD[6], GOOD[7], {"kind": "cell.prompt_sent", "cell_id": "a"}], [], "NoPromptAfterOutcome"),
    "launch after a stop (NoLaunchAfterStop)": ([GOOD[0], {"kind": "run.launch_stopped"}, GOOD[1]], [], "NoLaunchAfterStop"),
    "launch after a run stop (NoLaunchAfterStop)":
        ([GOOD[0], {"kind": "run.stopped", "code": "HB-RUN-006"}, GOOD[1]], [], "NoLaunchAfterStop"),
    "a control applied twice (ControlAppliedOnce)":
        ([GOOD[0], {"kind": "control.applied", "uuid": "f" * 32}] * 2, [], "ControlAppliedOnce"),
    "a run stopped twice (RunStoppedOnce)":
        ([GOOD[0], {"kind": "run.stopped", "code": "HB-RUN-006"}] * 2, [], "RunStoppedOnce"),
    "a second launch of one cell": (GOOD[:3] + [{"kind": "cell.launch_intent", "cell_id": "a"}], [], "WriteIntent"),
    "a working copy built after the process started":
        (_cell("cell.launch_intent", "attempt.process_started", "cell.workspace_built"), [], "workspace before process"),
    "a session before the process": (_cell("cell.launch_intent", "attempt.session_opened"), [], "session after process"),
    "a process end with no start": (_cell("cell.launch_intent", "attempt.process_ended"), [], "process_ended after process_started"),
    "a process started after the outcome":
        (_cell("cell.launch_intent", "cell.outcome", "attempt.process_started"), [], "no launch after an outcome"),
    "two cells running at parallelism 1 (ParallelismBound)":
        ([GOOD[0]] + [{"kind": k, "cell_id": c} for c in ("a", "b") for k in ("cell.launch_intent", "attempt.process_started")],
         [], "ParallelismBound"),
    "a score for a cell not archived when its pass started (ArchivedCellsGetGraded)":
        (GOOD[:8] + [{"kind": "grading.started", "grading_id": "g"}] + GOOD[8:],
         [{"grading_id": "g", "cell_id": "a", "metric_id": "pass_at_1"}], "ArchivedCellsGetGraded"),
    "a cell scored twice in one pass (GradedOncePerPass)":
        (GOOD[:10] + [{"kind": "grading.started", "grading_id": "g"}],
         [{"grading_id": "g", "cell_id": "a", "metric_id": "pass_at_1"}] * 2, "GradedOncePerPass"),
}


@pytest.mark.parametrize("name", sorted(SEEDED))
def test_each_seeded_out_of_order_ledger_is_rejected_under_its_rule(name):
    events, scores, rule = SEEDED[name]
    with pytest.raises(lifecycle.ConformanceError, match=re.escape(rule)):
        lifecycle.replay(events, parallelism=1, scores=scores)


def test_every_guard_of_the_table_has_a_seeded_case():
    seeded = {rule for _, _, rule in SEEDED.values()}
    assert {r for r in lifecycle.RULES if not any(s in r for s in seeded)} == set()


STOPPED = GOOD[:6] + [  # golden (design 16.3 D6): an operator stop of a running cell, then a control after grading
    {"kind": "control.applied", "uuid": "a" * 32, "control": "stop", "decision_id": None, "effect": "applied"},
    {"kind": "run.launch_stopped", "code": "HB-RUN-006", "reason": "bench stop"},
    {"kind": "run.stopped", "code": "HB-RUN-006", "decision_id": None},
    {"kind": "control.applied", "uuid": "b" * 32, "control": "stop", "decision_id": None, "effect": "no-op (already stopped)"},
    {"kind": "attempt.process_ended", "cell_id": "a", "ended_by": "terminate"},
    {"kind": "cell.outcome", "cell_id": "a", "outcome": "stopped", "cause": None},
    {"kind": "cell.archived", "cell_id": "a"},
    {"kind": "cell.workspace_deleted", "cell_id": "a"},
    {"kind": "control.applied", "uuid": "c" * 32, "control": "stop", "decision_id": None, "effect": "no-op (run ending)"},
    {"kind": "run.completed"},
]


def test_a_stopped_run_replays_and_a_second_read_gives_the_same_verdict():  # LC (design 8.3): stop and control rows
    lifecycle.replay(STOPPED, parallelism=1)
    lifecycle.replay(list(STOPPED), parallelism=1)  # the replay keeps no state between reads: a resumed read agrees
    with pytest.raises(lifecycle.ConformanceError, match="NoLaunchAfterStop"):
        lifecycle.replay(STOPPED[:-1] + [{"kind": "cell.launch_intent", "cell_id": "b"}], parallelism=1)


def test_parallelism_bound_is_enforced_by_the_replay():
    events = [{"kind": "cell.launch_intent", "cell_id": c} for c in ("a", "b")]
    events += [{"kind": "cell.workspace_built", "cell_id": c} for c in ("a", "b")]
    events += [{"kind": "attempt.process_started", "cell_id": c} for c in ("a", "b")]
    lifecycle.replay(events, parallelism=2)
    with pytest.raises(lifecycle.ConformanceError, match="ParallelismBound"):
        lifecycle.replay(events, parallelism=1)


OPENED = {"kind": "decision.opened", "decision_id": "D1", "decision_kind": "blocked_cell", "subject": "codex",
          "cause_code": "HB-CELL-202", "options": ["continue", "stop"], "default": "continue"}
RESOLVED = {"kind": "decision.resolved", "decision_id": "D1", "state": "answered", "option": "continue"}
DECISION_SEEDED = {  # design 8.3: the replay rules for decision requests
    "a decision opened after the run stopped (NoDecisionAfterStop)":
        ([GOOD[0], {"kind": "run.stopped", "code": "HB-RUN-006", "decision_id": None}, OPENED], [], "NoDecisionAfterStop"),
    "a decision resolved twice (DecisionResolvedOnce)": ([GOOD[0], OPENED, RESOLVED, RESOLVED], [], "DecisionResolvedOnce"),
    "a resolution before its decision opened": ([GOOD[0], RESOLVED, OPENED], [], "follows its decision.opened"),
    "a launch while a decision is open (NoLaunchWhileDecisionOpen)":
        ([GOOD[0], OPENED, GOOD[1]], [], "NoLaunchWhileDecisionOpen"),
}
SEEDED.update(DECISION_SEEDED)  # test_every_guard_of_the_table_has_a_seeded_case reads SEEDED when it runs


def _verdict(events: list[dict]) -> str | None:
    """The replay's violation for this ledger, or None when it conforms."""
    try:
        lifecycle.replay(events, parallelism=1)
    except lifecycle.ConformanceError as exc:
        return str(exc)
    return None


@pytest.mark.parametrize("name", sorted(DECISION_SEEDED))
def test_each_seeded_decision_ledger_is_rejected_under_its_rule(name):  # LC (design 8.3): decisions
    events, scores, rule = DECISION_SEEDED[name]
    with pytest.raises(lifecycle.ConformanceError, match=re.escape(rule)):
        lifecycle.replay(events, parallelism=1, scores=scores)


DECIDED = [  # golden (design 16.3 D6): a blocked cell's decision answered, then a spend cap's default stops the run
    GOOD[0],
    {"kind": "cell.launch_intent", "cell_id": "a"},
    {"kind": "cell.outcome", "cell_id": "a", "outcome": "failed", "cause": "blocked_auth"},
    OPENED,
    {"kind": "control.applied", "uuid": "d" * 32, "control": "answer", "decision_id": "D1", "effect": "applied"},
    RESOLVED,
    {"kind": "cell.launch_intent", "cell_id": "b"},
    {"kind": "decision.opened", "decision_id": "D2", "decision_kind": "spend_cap", "subject": "r1", "cause_code": "HB-RUN-007",
     "options": ["stop", "continue"], "default": "stop", "spend_tokens": 45, "cells_unmeasured": 0},
    {"kind": "decision.resolved", "decision_id": "D2", "state": "default applied (timeout)", "option": "stop"},
    {"kind": "run.launch_stopped", "code": "HB-RUN-007", "reason": "spend cap"},
    {"kind": "run.stopped", "code": "HB-RUN-007", "decision_id": "D2"},
    {"kind": "cell.outcome", "cell_id": "b", "outcome": "stopped", "cause": None},
    {"kind": "control.applied", "uuid": "e" * 32, "control": "answer", "decision_id": "D2", "effect": "rejected (already resolved)"},
    {"kind": "run.completed"},
]


def test_a_run_with_decisions_replays():  # LC (design 8.3): every decision row is a mapped engine transition
    assert _verdict(DECIDED) is None
    assert {"decision.opened", "decision.resolved"} <= lifecycle.ENGINE_TRANSITIONS
