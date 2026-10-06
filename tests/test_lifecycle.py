"""W1-K K3: resume rows preserve the stop and write-intent invariants."""

import pytest

from harness_bench import lifecycle


def _stop_rows(window):
    if window == "control":
        return [{"kind": "control.applied", "uuid": "stop-1", "control": "stop", "effect": "applied"}]
    if window == "decision":
        return [{"kind": "decision.opened", "decision_id": "d"},
                {"kind": "decision.resolved", "decision_id": "d", "option": "stop"}]
    return [{"kind": "run.stopped"}]


def _error(rows):
    try:
        lifecycle.replay(rows, parallelism=1)
    except lifecycle.ConformanceError as exc:
        return str(exc)
    return None


@pytest.mark.parametrize("window", ["control", "decision", "run"])
def test_launch_intent_after_a_stop_row_is_rejected(window):
    rows = [{"kind": "run.started"}, *_stop_rows(window), {"kind": "cell.launch_intent", "cell_id": "a"}]
    assert lifecycle.NO_LAUNCH_AFTER_STOP in (_error(rows) or ""), rows


@pytest.mark.parametrize("window", ["control", "decision", "run"])
def test_run_resumed_after_a_stop_row_is_accepted(window):
    rows = [{"kind": "run.started"}, *_stop_rows(window), {"kind": "run.resumed", "segment_id": "engine-1-r001"}]
    assert _error(rows) is None
    assert lifecycle.TABLE["run.resumed"].writer == "engine"
    assert lifecycle.NO_LAUNCH_AFTER_STOP in (_error([*rows, {"kind": "cell.launch_intent", "cell_id": "a"}]) or "")


def test_second_launch_intent_only_before_first_prompt():
    intent = {"kind": "cell.launch_intent", "cell_id": "a"}
    progress = [{"kind": "cell.workspace_built", "cell_id": "a"},
                {"kind": "attempt.process_started", "cell_id": "a"},
                {"kind": "attempt.session_opened", "cell_id": "a"}]
    rows = [{"kind": "run.started"}, intent, *progress]
    assert _error([*rows, intent, *progress, {"kind": "cell.prompt_sent", "cell_id": "a"}]) is None
    assert lifecycle.WRITE_INTENT_ONCE in (_error([*rows, intent, intent]) or "")
    assert lifecycle.WRITE_INTENT_ONCE in (_error([*rows, {"kind": "cell.prompt_sent", "cell_id": "a"}, intent]) or "")
    assert lifecycle.WRITE_INTENT_ONCE in (_error([*rows, {"kind": "attempt.process_ended", "cell_id": "a"},
                                                  {"kind": "cell.outcome", "cell_id": "a"}, intent]) or "")


def test_resume_outcome_confirms_the_old_process_is_gone():
    rows = [{"kind": "run.started"}, {"kind": "cell.launch_intent", "cell_id": "a"},
            {"kind": "attempt.process_started", "cell_id": "a"},
            {"kind": "attempt.session_opened", "cell_id": "a"},
            {"kind": "cell.prompt_sent", "cell_id": "a", "turn": 1},
            {"kind": "cell.outcome", "cell_id": "a", "outcome": "failed", "code": "HB-CELL-118",
             "resume": {"segment_id": "engine-1-r001", "turn": 1, "phase": "mid-turn"}},
            {"kind": "cell.archived", "cell_id": "a"}]
    assert _error(rows) is None


def test_resume_clears_a_launch_stop_only():
    rows = [{"kind": "run.started"}, {"kind": "run.launch_stopped"}, {"kind": "run.completed"},
            {"kind": "run.resumed"}, {"kind": "cell.launch_intent", "cell_id": "a"}]
    assert _error(rows) is None
