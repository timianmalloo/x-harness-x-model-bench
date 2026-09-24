"""Conformance of the engine to models/run_lifecycle.tla (US-44 AC3; design T3).

(a) Enumeration, both directions: every transition the engine can write is in the phase-1 mapping
    table, and every phase-1 row of the table is a transition the engine writes.
(b) Replay: the engine tests replay every run's events against the guards (test_engine.py).
(c) One seeded out-of-order ledger per phase-1 guard, each rejected by the replay.
"""

import pytest

from harness_bench import engine, lifecycle

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


def _without(kind):
    return [e for e in GOOD if e["kind"] != kind]


def _swap(k1, k2):
    events = list(GOOD)
    i = next(n for n, e in enumerate(events) if e["kind"] == k1)
    j = next(n for n, e in enumerate(events) if e["kind"] == k2)
    events[i], events[j] = events[j], events[i]
    return events


def test_the_engine_writes_exactly_the_phase1_transitions_of_the_mapping_table():
    phase1 = {k for k, (_, phase) in lifecycle.MAPPING.items() if phase == 1}
    grading = {"grading.started", "grading.completed", "segment.abandoned", "ledger.tail_repaired"}  # grading pass / ledger
    assert engine.ENGINE_TRANSITIONS <= phase1, sorted(engine.ENGINE_TRANSITIONS - phase1)
    assert phase1 - grading <= engine.ENGINE_TRANSITIONS, sorted(phase1 - grading - engine.ENGINE_TRANSITIONS)


def test_a_well_ordered_run_conforms():
    lifecycle.replay(GOOD, parallelism=1)


SEEDED = {
    "an unmapped transition": GOOD[:3] + [{"kind": "cell.relaunched", "cell_id": "a"}],
    "prompt_sent before process_started (WriteIntent/StartCell order)": _swap("attempt.process_started", "cell.prompt_sent"),
    "a second prompt (AtMostOnePrompt)": GOOD[:6] + [{"kind": "cell.prompt_sent", "cell_id": "a"}] + GOOD[6:],
    "outcome before the process is confirmed gone (NoOutcomeWhileRunning)": _swap("attempt.process_ended", "cell.outcome"),
    "archived before the outcome (NoArchiveWhileLive)": _swap("cell.outcome", "cell.archived"),
    "deleted before archived (NothingDeletedUnarchived)": _swap("cell.archived", "cell.workspace_deleted"),
    "a transition before the launch intent": [GOOD[0], GOOD[2], GOOD[1]] + GOOD[3:],
    "prompt after the outcome (NoPromptAfterOutcome)": GOOD[:4] + [GOOD[4], GOOD[6], GOOD[7], {"kind": "cell.prompt_sent", "cell_id": "a"}],
    "launch after a stop (NoLaunchAfterStop)": [GOOD[0], {"kind": "run.launch_stopped"}, GOOD[1]],
    "a second launch of one cell": GOOD[:3] + [{"kind": "cell.launch_intent", "cell_id": "a"}],
}


@pytest.mark.parametrize("name", sorted(SEEDED))
def test_each_seeded_out_of_order_ledger_is_rejected(name):
    with pytest.raises(lifecycle.ConformanceError):
        lifecycle.replay(SEEDED[name], parallelism=1)


def test_parallelism_bound_is_enforced_by_the_replay():
    events = [{"kind": "cell.launch_intent", "cell_id": c} for c in ("a", "b")]
    events += [{"kind": "cell.workspace_built", "cell_id": c} for c in ("a", "b")]
    events += [{"kind": "attempt.process_started", "cell_id": c} for c in ("a", "b")]
    lifecycle.replay(events, parallelism=2)
    with pytest.raises(lifecycle.ConformanceError, match="ParallelismBound"):
        lifecycle.replay(events, parallelism=1)
