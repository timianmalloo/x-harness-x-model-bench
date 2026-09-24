"""Views: pure projections over the verified facts (ADR-0006; design: Data model, Rules; spec US-11, US-23, US-24, US-27).

Runs are built with the shared archived-run builder and graded for real, then projected.
"""

from decimal import Decimal

import pytest
from archived_runs import (
    CODEX_MODEL,
    GOOD,
    STUB,
    complete_run,
    make_root,
    make_run,
    pass_rows,
    set_prices,
)

from harness_bench import ledger, views
from harness_bench.errors import BenchError
from harness_bench.grade import cost, runner
from harness_bench.telemetry import normalize

SONNET = "claude-sonnet-5"


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _usage(cell_id: str, model: str, output: int = 50) -> dict:
    return {"kind": "turn_usage", "run_id": "r1", "cell_id": cell_id, "attempt": 1, "model": model,
            "uncached_input": 100, "cache_read": 1000, "cache_write": 10, "output": output, "reasoning": 0}


def _cell(view: views.RunView, cell_id: str) -> views.CellView:
    return next(c for c in view.cells if c.cell_id == cell_id)


# --- current pass, verified reads, duplicate refusal (ADR-0006) ------------------------------------


def test_an_ungraded_run_has_no_scores_and_says_so(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    view = views.load(run_dir)
    assert view.grading_id is None
    a = _cell(view, "a")
    assert a.scores == {} and a.validity == "not graded" and a.tokens is None  # never {} or 0
    assert a.tokens_reason == "not graded"
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    assert a.tokens and a.tokens_reason is None


def test_a_pass_is_current_only_for_its_catalog_version(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    assert (views.load(run_dir).grading_id, views.load(run_dir).catalog_version) == (done.grading_id, "0.3")
    assert views.load(run_dir, "0.3").grading_id == done.grading_id
    assert (views.load(run_dir, "9.9").grading_id, views.load(run_dir, "9.9").catalog_version) == (None, "9.9")


@pytest.mark.parametrize("second", ["0" * 64, "f" * 64])  # a new normaliser's id sorting below, or above, the first
def test_a_cell_reads_only_the_current_extraction(root, tmp_path, monkeypatch, second):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    before = _cell(views.load(run_dir), "a")
    monkeypatch.setattr(normalize, "extraction_id", lambda: second)
    runner.run_pass(run_dir, root)
    after = _cell(views.load(run_dir), "a")
    assert after.extraction_id == second and (after.tokens, after.tool_ms) == (before.tokens, before.tool_ms)


@pytest.mark.parametrize("second", ["0" * 64, "f" * 64])
def test_a_new_extraction_with_other_tool_times_replaces_the_old(root, tmp_path, monkeypatch, second):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    record = next((run_dir / "archive" / "a" / "attempt-1" / "home").rglob("*.jsonl"))  # a normaliser that reads other times
    record.write_text(record.read_text(encoding="utf-8").replace('"timestamp": "2026-', '"timestamp": "2027-'), encoding="utf-8")
    monkeypatch.setattr(normalize, "extraction_id", lambda: second)
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tool_ms == views.Measure(592)  # never the union of both extractions


def test_a_cell_reads_only_its_own_tool_calls(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD})
    record = next((run_dir / "archive" / "b" / "attempt-1" / "home").rglob("*.jsonl"))
    record.write_text(record.read_text(encoding="utf-8").replace('"timestamp": "2026-', '"timestamp": "2027-'), encoding="utf-8")
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tool_ms == views.Measure(592)  # b's calls, a year later, are not a's


def test_the_header_reads_only_process_starts(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "attempt.process_started", "cell_id": "a", "credential_kind": "subscription", "network_mode": "open",
                   "harness": "codex", "build_version": "0.156.0"})
        for kind in ("attempt.process_ended", "cell.prompt_sent", "agent.x"):  # kinds sorting before and after it
            ev.append({"kind": kind, "cell_id": "z", "credential_kind": "leak", "network_mode": "leak", "harness": "x", "build_version": "1"})
    assert views.load(run_dir).header == {"credential_kind": "subscription", "network_mode": "open", "executed_builds": "codex 0.156.0"}


def test_a_measure_is_a_frozen_hashable_value():
    from dataclasses import FrozenInstanceError

    assert {views.Measure(1), views.Measure(1)} == {views.Measure(1)}
    with pytest.raises(FrozenInstanceError):
        views.Measure(1).value = 2  # type: ignore[misc]


def test_the_current_pass_is_the_latest_completed_one_and_an_unfinished_pass_is_ignored(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    second = runner.run_pass(run_dir, root)
    with ledger.SegmentWriter.create(run_dir / "events", "grade-zzzz") as dead:  # newest id, never completed
        dead.append(ledger.stamp({"kind": "grading.started", "grading_id": "grade-zzzz", "catalog_version": "0.3"}))
    view = views.load(run_dir)
    assert view.grading_id == second.grading_id
    assert _cell(view, "a").scores["pass_at_1"] == views.Measure(1)


def test_a_second_outcome_for_a_cell_is_refused(root, tmp_path):  # HB-LED-003, never "latest wins"
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.outcome", "cell_id": "a", "outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"})
    with pytest.raises(BenchError) as err:
        views.load(run_dir)
    assert err.value.code == "HB-LED-003"


def test_a_duplicate_fact_key_is_refused(root, tmp_path):  # HB-LED-003
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    first = runner.run_pass(run_dir, root)
    copy = [{k: v for k, v in r.items() if k not in ledger.CHAIN_FIELDS} for r in pass_rows(run_dir, "model_calls", first.grading_id)]
    with ledger.SegmentWriter.create(run_dir / "model_calls", "grade-copy") as mc:
        for row in copy:
            mc.append(row)
        mc.seal()
    with ledger.SegmentWriter.create(run_dir / "events", "grade-copy") as ev:
        ev.append(ledger.stamp({"kind": "grading.started", "grading_id": "grade-copy", "catalog_version": "0.3"}))
        ev.append(ledger.stamp({"kind": "grading.completed", "grading_id": "grade-copy", "cells_graded": 0}))
        ev.seal()
    with pytest.raises(BenchError) as err:
        views.load(run_dir)
    assert err.value.code == "HB-LED-003"


# --- validity (US-11; errors.Cause) -----------------------------------------------------------------


def test_an_infrastructure_or_benchmark_cause_invalidates_the_cell(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD, "c": GOOD}, outcomes={
        "a": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"},
        "b": {"outcome": "failed", "cause": "model_unavailable", "code": "HB-CELL-116"},
        "c": {"outcome": "timed_out", "cause": "timed_out", "code": "HB-CELL-301"}})
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert [(c.cell_id, c.validity, c.validity_code) for c in view.cells] == [
        ("a", "invalid (infrastructure)", "HB-CELL-108"), ("b", "invalid (benchmark)", "HB-CELL-116"), ("c", "valid", None)]
    assert _cell(view, "c").outcome == "timed_out" and _cell(view, "c").cause == "timed_out"


def test_a_cell_with_no_model_call_is_invalid(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[])
    view = views.load(run_dir)
    assert (_cell(view, "a").validity, _cell(view, "a").validity_code) == ("invalid (no model call)", "HB-VAL-001")


def test_a_served_model_other_than_the_pin_is_a_mismatch(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, model="gpt-other")  # the record serves gpt-6-sol
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert (_cell(view, "a").validity, _cell(view, "a").validity_code) == ("invalid (model mismatch)", "HB-VAL-002")


def test_a_declared_auxiliary_model_is_not_a_mismatch(root, tmp_path):
    usage = [_usage("a", SONNET), _usage("a", "claude-haiku-4-5-20251001")]
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=usage)
    assert _cell(views.load(run_dir), "a").validity == "valid"


def test_a_cell_that_never_started_is_listed_as_not_started(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("z",))
    z = _cell(views.load(run_dir), "z")
    assert (z.outcome, z.validity, z.wall_ms) == ("not started", "not started", views.Measure(None, "cell never started"))


def test_a_launched_cell_with_no_outcome_is_not_called_not_started(root, tmp_path):  # an engine crash (run incomplete)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("z",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.launch_intent", "cell_id": "z"})
    z = _cell(views.load(run_dir), "z")
    assert (z.outcome, z.validity) == ("no outcome", "no outcome")


# --- tokens, time split and cost (US-22, US-23, US-24, US-27) ---------------------------------------


def test_tokens_come_from_the_harness_token_source(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tokens == {CODEX_MODEL: {"uncached_input": 4032, "cache_read": 41856,
                                                                      "cache_write": 0, "output": 566}}
    acp = make_run(root, tmp_path / "acp", {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[_usage("a", SONNET)])
    assert _cell(views.load(acp), "a").tokens == {SONNET: {"uncached_input": 100, "cache_read": 1000, "cache_write": 10, "output": 50}}


def test_the_time_split_records_what_the_harness_exposes_and_never_invents_idle(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    assert a.wall_ms == views.Measure(30_000)
    assert a.tool_ms == views.Measure(592)  # 338 + 254 ms, the two tool calls in the Codex record
    assert a.model_ms == views.Measure(None, "the native record gives no model-call start time")
    assert a.idle_ms == views.Measure(None, "needs model time")


@pytest.mark.parametrize(("calls", "expected"), [
    ([{"start": "2026-09-23T10:00:00.000Z", "end": "2026-09-23T10:00:00.500Z"}], views.Measure(500)),
    ([{"start": None, "end": "2026-09-23T10:00:00.500Z"}], views.Measure(None, "the native record gives no model-call start time")),
    ([{"start": "2026-09-23T10:00:00.500Z", "end": "2026-09-23T10:00:00.500Z"}],
     views.Measure(None, "the native record gives no model-call start time")),
    ([], views.Measure(None, "the native record gives no model-call start time")),
    (None, views.Measure(None, "not graded")),
])
def test_model_time_needs_a_real_duration_for_every_call(calls, expected):
    assert views._model_time("native_record", calls) == expected
    assert views._model_time("acp_turn", calls).value is None


@pytest.mark.parametrize(("wall", "model", "tool", "expected"), [
    (1000, 300, 200, views.Measure(500)),
    (1000, 700, 400, views.Measure(None, "model and tool time exceed wall time")),
    (1000, 1000, 0, views.Measure(0)),
    (1000, 700, 301, views.Measure(None, "model and tool time exceed wall time")),  # -1 ms is never idle
])
def test_idle_is_wall_minus_model_minus_tool(wall, model, tool, expected):
    assert views._idle(views.Measure(wall), views.Measure(model), views.Measure(tool)) == expected


@pytest.mark.parametrize("call", [
    {"start": "not a time", "end": "2026-09-23T10:00:01.000Z"},
    {"start": "2026-09-23T10:00:00.000Z", "end": None},
    {"start": "2026-09-23T10:00:02.000Z", "end": "2026-09-23T10:00:01.000Z"},  # ends before it starts
])
def test_a_span_without_both_valid_ends_in_order_is_not_recorded(call):
    assert views.busy_ms([call]) == views.Measure(None, "an interval has no start or end")


@pytest.mark.parametrize("events", [
    {"cell.launch_intent": {}, "attempt.process_started": {"mono_ns": 1}},
    {"cell.launch_intent": {}, "attempt.process_ended": {"mono_ns": 1}},
])
def test_wall_time_needs_both_process_start_and_end(events):
    assert views._wall(events) == views.Measure(None, "no process start or end recorded")


def test_cells_with_long_ids_keep_their_own_events_and_calls(root, tmp_path):  # ids compared by value, never identity
    run_dir = make_run(root, tmp_path, {"cell-alpha-0001": GOOD, "cell-bravo-0002": STUB})
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    for cid in ("cell-alpha-0001", "cell-bravo-0002"):
        c = _cell(view, cid)
        assert (c.outcome, c.validity, c.wall_ms) == ("completed", "valid", views.Measure(30_000))
        assert c.tokens == {CODEX_MODEL: {"uncached_input": 4032, "cache_read": 41856, "cache_write": 0, "output": 566}}  # one record each
        assert c.tool_ms == views.Measure(592)


def test_a_zero_length_tool_call_is_a_measured_zero():  # only model calls need a positive span
    call = {"start": "2026-09-23T10:00:00.500Z", "end": "2026-09-23T10:00:00.500Z"}
    assert views.busy_ms([call]) == views.Measure(0)


def test_a_view_says_whether_the_run_completed(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    assert views.load(run_dir).completed is False
    complete_run(run_dir)
    assert views.load(run_dir).completed is True


def test_an_abandoned_segment_sorted_first_hides_no_completed_pass(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    with ledger.SegmentWriter.create(run_dir / "scores", "grade-0000") as dead:  # sorts before every real pass
        dead.append({"kind": "score"})
    assert _cell(views.load(run_dir), "a").scores["pass_at_1"] == views.Measure(1)


def test_overlapping_tool_calls_are_counted_once():
    calls = [{"start": "2026-09-23T10:00:00.000Z", "end": "2026-09-23T10:00:02.000Z"},
             {"start": "2026-09-23T10:00:01.000Z", "end": "2026-09-23T10:00:03.000Z"},
             {"start": "2026-09-23T10:00:05.000Z", "end": "2026-09-23T10:00:06.000Z"}]
    assert views.busy_ms(calls) == views.Measure(4000)
    assert views.busy_ms([{"start": None, "end": "2026-09-23T10:00:01.000Z"}]).value is None


def test_the_cost_score_equals_a_fresh_derivation(root, tmp_path):  # a stored cost is a rebuildable cache (spec)
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": "1.25", "output": 10,
                       "cache_read": "0.125", "cache_write": 0}])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    fresh, _, _ = cost.cost_usd(a.tokens, {"entries": [{"model": CODEX_MODEL, "effective": "2026-09-01", "input": "1.25",
                                                          "output": 10, "cache_read": "0.125", "cache_write": 0}]}, "2026-09-23")
    assert a.scores["cost_usd"] == views.Measure(f"{fresh:.6f}")


# --- leaderboard (US-39 skeleton; correctness-gated, ties) -----------------------------------------


def test_the_leaderboard_ranks_by_pass_rate_and_shows_ties(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB, "c": GOOD},
                       combos={"a": "good", "b": "stub", "c": "also-good"})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank, r.pass_at_1) for r in rows] == [
        ("also-good", "1=", views.Measure(Decimal(1))), ("good", "1=", views.Measure(Decimal(1))),
        ("stub", "3", views.Measure(Decimal(0)))]
    assert rows[0].interval == "interval not computed (n < 2)"


def test_an_invalid_cell_never_counts_toward_its_combo(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    runner.run_pass(run_dir, root)
    (row,) = views.leaderboard(views.load(run_dir))
    assert (row.n_cells, row.n_valid, row.rank) == (1, 0, "")
    assert row.pass_at_1 == views.Measure(None, "no valid graded cell")


def test_an_unranked_combo_sorts_last_and_two_valid_cells_still_get_no_interval(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a1": GOOD, "a2": GOOD, "b1": GOOD}, combos={"a1": "a-two", "a2": "a-two", "b1": "b-bad"},
                       outcomes={"b1": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank) for r in rows] == [("a-two", "1"), ("b-bad", "")]
    assert rows[0].interval == "interval not computed (statistics are phase 4)"


def test_cost_is_na_for_a_combo_when_any_valid_cell_has_no_cost(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    (row,) = views.leaderboard(views.load(run_dir))
    assert row.cost_usd == views.Measure(None, f"1 of 1 valid cells have no cost: no price list entry for {CODEX_MODEL}")


# --- canonical export (the byte-identical re-grade, US-26) -----------------------------------------


def test_a_higher_pass_rate_sorts_first_whatever_the_combo_name(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a1": GOOD, "a2": STUB, "b1": GOOD},
                       combos={"a1": "a-half", "a2": "a-half", "b1": "b-full"})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank, r.pass_at_1) for r in rows] == [("b-full", "1", views.Measure(Decimal(1))),
                                                              ("a-half", "2", views.Measure(Decimal("0.5")))]


def test_a_regrade_gives_a_byte_identical_canonical_export(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB})
    runner.run_pass(run_dir, root)
    first = views.export(views.load(run_dir))
    runner.run_pass(run_dir, root)
    second = views.export(views.load(run_dir))
    assert first == second
    assert b"grade-" not in first  # the pass's identity is not part of the result
