"""`bench status` (US-20; design: Exposed contracts, CLI states; ADR-0011 C4 typed boundaries).

The JSON form is `bench-status/1`: a strict type (unknown or missing fields rejected), with no free text
from cells. The text form uses the exact strings of the design's CLI state table.
"""

import dataclasses
import json
from datetime import UTC, datetime

import pytest
from archived_runs import GOOD, make_root, make_run
from hypothesis import given
from hypothesis import strategies as st

from harness_bench import ledger, oslock, status
from harness_bench.errors import BenchError
from harness_bench.grade import runner

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _live_run(root, tmp_path):
    """A run whose engine segment shows cell `a` ended and cell `b` still running since 11:59:00
    (process started and its prompt sent at the same instant, so old and new budget math agree)."""
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("b",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.launch_intent", "cell_id": "b"})
        ev.append({"kind": "attempt.process_started", "cell_id": "b", "recorded_at": "2026-09-23T11:59:00.000Z"})
        ev.append({"kind": "attempt.session_opened", "cell_id": "b"})
        ev.append({"kind": "cell.prompt_sent", "cell_id": "b", "recorded_at": "2026-09-23T11:59:00.000Z"})
    return run_dir


def _handshaking_run(root, tmp_path):
    """Cell `b`'s process started at 11:58:00 (handshake) but its prompt was only sent at 11:59:00."""
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("b",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.launch_intent", "cell_id": "b"})
        ev.append({"kind": "attempt.process_started", "cell_id": "b", "recorded_at": "2026-09-23T11:58:00.000Z"})
        ev.append({"kind": "attempt.session_opened", "cell_id": "b"})
        ev.append({"kind": "cell.prompt_sent", "cell_id": "b", "recorded_at": "2026-09-23T11:59:00.000Z"})
    return run_dir


def test_a_finished_run_is_not_running_and_complete(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "run.completed", "run_id": "r1"})
    s = status.build(run_dir, now=NOW)
    assert (s.liveness, s.completion, s.cells_ended, s.cells_total) == ("not running", "complete", 1, 1)
    assert status.text(s) == "Run r1: not running (complete). 1/1 cells ended.\nOutcomes: completed 1.\nValidity: not graded 1.\n"


def test_a_cell_whose_native_record_is_unreadable_is_counted_as_not_recorded(root, tmp_path):  # R-15, seam S2
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    next((run_dir / "archive/a/attempt-1/home").rglob("*.jsonl")).unlink()
    runner.run_pass(run_dir, root)
    s = status.build(run_dir, now=NOW)
    assert s.validity == {"not recorded": 1}
    assert status.parse(status.to_json(s)) == s  # bench-status/1 accepts the state


@pytest.mark.parametrize("state", ["invalid (tools denied by hook)", "invalid (build mismatch)",  # R-27, R-47; seam S2
                                   "invalid (out-of-profile tool called)"])  # R-45 item 2, R-54
def test_bench_status_accepts_the_wave_two_invalid_states(root, tmp_path, state):
    s = dataclasses.replace(status.build(make_run(root, tmp_path, {"a": GOOD}), now=NOW), validity={state: 1})
    assert status.parse(status.to_json(s)) == s


def test_a_dead_engine_leaves_the_run_incomplete(root, tmp_path):
    s = status.build(_live_run(root, tmp_path), now=NOW)
    assert (s.liveness, s.completion) == ("not running", "incomplete")
    assert status.text(s).startswith("Run r1: not running (incomplete). 1/2 cells ended.\n")


def test_a_live_engine_is_alive_and_lists_its_running_cells(root, tmp_path):
    run_dir = _live_run(root, tmp_path)
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        s = status.build(run_dir, now=NOW)
    assert (s.liveness, s.completion) == ("alive", "in progress")
    assert s.running == [status.RunningCell("b", "X1.c.pack-off.r1", 60, 300, False)]
    assert status.text(s).splitlines()[:2] == ["Run r1: running. 1/2 cells ended, 1 running.",
                                               "b X1.c.pack-off.r1: running 60 s of 300 s"]


def test_a_held_lock_with_a_stale_heartbeat_is_stalled(root, tmp_path):
    run_dir = _live_run(root, tmp_path)
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        s = status.build(run_dir, now=NOW, lock_age=500.0)
    assert s.liveness == "stalled"
    assert status.text(s).splitlines()[0] == "Run r1: stalled. The engine holds the lock but has not progressed for 500 s."


def test_a_cell_past_its_budget_is_being_killed(root, tmp_path):
    run_dir = _live_run(root, tmp_path)
    later = datetime(2026, 9, 23, 12, 5, 30, tzinfo=UTC)  # 390 s after start, budget 300 s
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        s = status.build(run_dir, now=later)
    assert s.running[0].killing
    assert "b: killing (unconfirmed, 90 s)" in status.text(s).splitlines()


def test_a_running_cells_budget_is_measured_from_prompt_sent_not_process_started(root, tmp_path):  # T4-3
    run_dir = _handshaking_run(root, tmp_path)
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        s = status.build(run_dir, now=NOW)  # NOW 12:00:00; process_started 11:58 (120s), prompt_sent 11:59 (60s)
    assert s.running[0].elapsed_s == 60
    assert not s.running[0].killing  # budget 300s: 60s elapsed, not 120s


def test_phase_is_starting_before_any_cell_process_has_started(root, tmp_path):  # T4-4 (ruling R-3)
    run_dir = make_run(root, tmp_path, {}, unstarted=("b",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.launch_intent", "cell_id": "b"})
    s = status.build(run_dir, now=NOW)
    assert s.phase == "starting"
    assert s.stop_code is None


def test_phase_is_running_once_a_cell_process_has_started(root, tmp_path):
    s = status.build(_live_run(root, tmp_path), now=NOW)
    assert s.phase == "running"


def test_stop_code_is_set_only_when_run_launch_stopped_was_recorded(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "run.launch_stopped", "code": "HB-RUN-004", "reason": "disk floor"})
    s = status.build(run_dir, now=NOW)
    assert s.stop_code == "HB-RUN-004"


def test_an_unknown_run_is_hb_usr_001(tmp_path):
    with pytest.raises(BenchError) as err:
        status.build(tmp_path / "runs" / "nope", now=NOW)
    assert err.value.code == "HB-USR-001"
    assert status.unknown_run_message("nope") == "HB-USR-001: no run nope under runs/. Run bench plan to create one."


def test_no_free_text_from_cells_reaches_status(root, tmp_path):  # ADR-0011 C4 / B2; T-LOG-nosecret
    secret = "sk-ant-PLANTED-0123456789"
    run_dir = make_run(root, tmp_path, {"a": GOOD}, outcomes={"a": {"detail": secret, "stop_reason": secret}})
    s = status.build(run_dir, now=NOW)
    assert secret not in status.to_json(s) and secret not in status.text(s)


def test_the_json_form_round_trips_and_is_strict(root, tmp_path):
    s = status.build(_live_run(root, tmp_path), now=NOW)
    doc = status.to_json(s)
    assert status.parse(doc) == s
    data = json.loads(doc)
    for broken in ({**data, "extra": 1}, {k: v for k, v in data.items() if k != "graded"}, {**data, "schema": "bench-status/2"},
                   {**data, "liveness": "sleeping"}, {**data, "cells_ended": -1}, {**data, "graded": 1},
                   {**data, "outcomes": {**data["outcomes"], "exploded": 1}},
                   {**data, "running": [{**data["running"][0], "cell_id": "not a cell id"}]},
                   {**data, "phase": "grading"}, {**data, "stop_code": "not-a-code"}):
        with pytest.raises(ValueError):
            status.parse(json.dumps(broken))


_ids = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16)
_running = st.builds(status.RunningCell, cell_id=_ids, label=st.from_regex(r"[A-Za-z0-9.\-]{1,40}", fullmatch=True),
                     elapsed_s=st.integers(0, 10**6), budget_s=st.integers(1, 10**6), killing=st.booleans())
_statuses = st.builds(
    status.Status, schema=st.just(status.SCHEMA), run_id=st.from_regex(status.RUN_ID, fullmatch=True),
    checked_at=st.just("2026-09-23T12:00:00Z"), liveness=st.sampled_from(status.LIVENESS),
    completion=st.sampled_from(status.COMPLETION), lock_age_s=st.none() | st.integers(0, 10**6),
    cells_total=st.integers(0, 600), cells_ended=st.integers(0, 600),
    outcomes=st.dictionaries(st.sampled_from(status.OUTCOMES), st.integers(0, 600)),
    validity=st.dictionaries(st.sampled_from(status.VALIDITY), st.integers(0, 600)),
    causes=st.dictionaries(st.from_regex(r"HB-CELL-[0-9]{3}", fullmatch=True), st.integers(0, 600)),
    running=st.lists(_running, max_size=4), decisions=st.just([]),
    stop_code=st.none() | st.from_regex(r"HB-[A-Z]+-[0-9]{3}", fullmatch=True), phase=st.sampled_from(status.PHASE),
    graded=st.booleans())


@given(_statuses)
def test_every_valid_status_round_trips(s):  # design T2: bench-status/1 round trip
    assert status.parse(status.to_json(s)) == s
