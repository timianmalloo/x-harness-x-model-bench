"""Grading passes (ADR-0006, ADR-0007; design: Data model, Failure-mode analysis T-GRD-*).

Each test builds a real archived run on disk: engine segments written with the real ledger, an archive
folder as the archiver lays it out (`archive/<cell>/attempt-1/{ws,home}`), and the real captured Codex
record as the cell's native record. The grading pass runs for real, including the hidden tests in their
own job.
"""

import json
import re
import shutil
from decimal import Decimal

import pytest
from archived_runs import (
    CODEX_MODEL,
    FIX,
    GOOD,
    HANG,
    NO_STRIP,
    STUB,
    make_root,
    make_run,
    pass_rows,
    scores,
    set_prices,
)

from harness_bench import ledger, lifecycle, oslock, views
from harness_bench.errors import BenchError
from harness_bench.grade import correctness, runner
from harness_bench.telemetry import codex, normalize


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


# --- correctness (US-28) ---------------------------------------------------------------------------


def test_a_correct_solution_passes_with_full_credit(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    result = runner.run_pass(run_dir, root)
    s = scores(run_dir, result.grading_id)
    assert (s["a", "pass_at_1"]["value"], s["a", "partial_credit"]["value"]) == (1, "1.0000")
    assert s["a", "pass_at_1"]["reason"] is None
    assert (run_dir / s["a", "pass_at_1"]["evidence"]).is_file()


def test_a_near_miss_gets_partial_credit_and_fails(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": NO_STRIP})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "pass_at_1"]["value"], s["a", "partial_credit"]["value"]) == (0, "0.7500")


def test_the_untouched_stub_scores_zero_not_na(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": STUB})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "pass_at_1"]["value"], s["a", "partial_credit"]["value"]) == (0, "0.0000")


def test_a_skipped_hidden_test_is_not_a_pass_even_though_unittest_exits_0(root, tmp_path):
    hidden = root / "tasks" / "X1" / "tests" / "test_slug_hidden.py"
    hidden.write_text(hidden.read_text(encoding="utf-8").replace(
        'if __name__ == "__main__":',
        'class Skipped(unittest.TestCase):\n    @unittest.skip("not applicable")\n    def test_skipped(self):\n        pass\n\n\n'
        'if __name__ == "__main__":'), encoding="utf-8")
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "pass_at_1"]["value"], s["a", "partial_credit"]["value"]) == (0, "0.8000")


def test_hidden_tests_never_enter_the_archive_and_the_grading_copy_is_removed(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert not list((run_dir / "archive").rglob("test_slug_hidden.py"))
    assert not (run_dir / "grading" / gid / "a" / "work").exists()


def test_an_oracle_timeout_is_na_with_hb_grd_002(root, tmp_path):  # T-FI-grading-timeout
    run_dir = make_run(root, tmp_path, {"a": HANG}, timeout=3)
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    for metric in ("pass_at_1", "partial_credit"):
        assert s["a", metric]["value"] is None
        assert s["a", metric]["reason"].startswith("HB-GRD-002")


def test_a_cell_with_no_working_copy_is_na(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": None})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "pass_at_1"] == {**s["a", "pass_at_1"], "value": None, "reason": "no working copy in the archive"}


@pytest.mark.parametrize(("stderr", "expected"), [
    ("Ran 4 tests in 0.001s\n\nOK\n", (4, 4)),
    ("Ran 4 tests in 0.001s\n\nFAILED (failures=1)\n", (4, 3)),
    ("Ran 4 tests in 0.001s\n\nFAILED (failures=1, errors=2)\n", (4, 1)),
    ("Ran 1 test in 0.000s\n\nOK (skipped=1)\n", (1, 0)),
    ("Ran 3 tests in 0.0s\n\nFAILED (errors=1, unexpected successes=1)\n", (3, 1)),
    ("Traceback (most recent call last):\nSyntaxError\n", None),
    ("Ran 4 tests in 0.001s\n\nFAILED (flakes=1)\n", None),
])
def test_the_unittest_summary_is_parsed_strictly(stderr, expected):
    assert correctness.parse_unittest(stderr) == expected


@pytest.mark.parametrize("oracle", [{"runner": "pytest", "command": ["{python}", "-m", "pytest"]}, {"runner": "unittest"}])
def test_an_oracle_phase_1_cannot_run_is_na_before_anything_runs(tmp_path, oracle):
    result = correctness.grade(tmp_path / "ws", tmp_path / "task", oracle, tmp_path / "out", tmp_path, 10)
    assert (result.passed, result.partial_credit, result.evidence) == (None, None, "")
    assert result.reason == f"oracle runner {oracle['runner']!r} not built (phase 1 runs unittest)"


def test_not_recorded_is_one_falsy_sentinel():
    from harness_bench import grade

    assert grade.NOT_RECORDED is grade._NotRecorded() and not grade.NOT_RECORDED and repr(grade.NOT_RECORDED) == "NOT_RECORDED"


# --- cost (US-23) ----------------------------------------------------------------------------------


def test_cost_is_na_without_a_price_entry_and_never_zero(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "cost_usd"]["value"] is None
    assert s["a", "cost_usd"]["reason"] == f"no price list entry for {CODEX_MODEL}"


def test_cost_is_tokens_by_type_times_the_entry_in_force_on_the_run_date(root, tmp_path):
    set_prices(root, [
        {"model": CODEX_MODEL, "effective": "2026-01-01", "source": "https://example.test/old",
         "input": 100, "output": 100, "cache_read": 100, "cache_write": 100},
        {"model": CODEX_MODEL, "effective": "2026-09-01", "source": "https://example.test/p",
         "input": "1.25", "output": 10, "cache_read": "0.125", "cache_write": 0},
        {"model": CODEX_MODEL, "effective": "2026-12-01", "source": "https://example.test/future",
         "input": 999, "output": 999, "cache_read": 999, "cache_write": 999},
    ])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    t = normalize.totals("native_record", codex.read(FIX / "native" / "codex" / "ok.jsonl"), [])[CODEX_MODEL]
    expected = (Decimal(t["uncached_input"]) * Decimal("1.25") + Decimal(t["output"]) * 10
                + Decimal(t["cache_read"]) * Decimal("0.125")) / 1_000_000
    assert s["a", "cost_usd"]["value"] == f"{expected:.6f}"
    assert s["a", "cost_usd"]["evidence"] == f"bench/prices.yaml#{CODEX_MODEL}@2026-09-01"


def test_cost_is_na_when_the_price_list_changed_after_the_plan(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": 1, "output": 1,
                    "cache_read": 1, "cache_write": 1}])
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "cost_usd"]["value"] is None
    assert s["a", "cost_usd"]["reason"] == "price list changed since the plan (hash mismatch)"


def test_cost_reads_turn_usage_for_an_acp_turn_harness(root, tmp_path):
    set_prices(root, [{"model": "claude-sonnet-5", "effective": "2026-09-01", "source": "s", "input": 3, "output": 15,
                    "cache_read": "0.3", "cache_write": "3.75"}])
    usage = [{"kind": "turn_usage", "run_id": "r1", "cell_id": "a", "attempt": 1, "model": "claude-sonnet-5",
              "uncached_input": 1000, "cache_read": 10000, "cache_write": 2000, "output": 500, "reasoning": 0}]
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", turn_usage=usage)
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "cost_usd"]["value"] == "0.021000"  # (1000*3 + 10000*0.3 + 2000*3.75 + 500*15) / 1e6


def test_hidden_tests_changed_since_the_plan_are_na_not_graded(root, tmp_path):  # US-26
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    hidden = root / "tasks" / "X1" / "tests" / "test_slug_hidden.py"
    hidden.write_text(hidden.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "pass_at_1"]["value"], s["a", "pass_at_1"]["reason"]) == (None, "task changed since the plan (version hash mismatch)")


def test_grading_reads_the_plan_profile_not_todays_profile_files(root, tmp_path):  # US-26
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    shutil.rmtree(root / "bench" / "profiles")
    result = runner.run_pass(run_dir, root)
    assert len(pass_rows(run_dir, "model_calls", result.grading_id)) == 3


def test_cost_is_na_when_no_usage_was_recorded(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", turn_usage=[])
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "cost_usd"]["value"], s["a", "cost_usd"]["reason"]) == (None, "no usage recorded")


def test_cost_is_na_when_the_native_record_is_missing(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    shutil.rmtree(run_dir / "archive" / "a" / "attempt-1" / "home")
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "cost_usd"]["value"], s["a", "cost_usd"]["reason"]) == (None, "no native record for the session")


def test_cost_is_na_naming_hb_tel_001_when_the_native_record_misses_a_usage_field(root, tmp_path):  # seam T3 -> T2
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": "1.25", "output": 10,
                       "cache_read": "0.125", "cache_write": 0}])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    record = next((run_dir / "archive" / "a" / "attempt-1" / "home").rglob("*.jsonl"))
    lines = []
    for line in record.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        last = ((row.get("payload") or {}).get("info") or {}).get("last_token_usage")
        if isinstance(last, dict):
            last.pop("output_tokens", None)
        lines.append(json.dumps(row))
    record.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "cost_usd"]["value"], s["a", "cost_usd"]["reason"]) == (None, "HB-TEL-001 native-record fields missing: output_tokens")
    assert s["a", "pass_at_1"]["value"] == 1  # only the measures built from usage are NOT_RECORDED


def test_a_grading_id_names_its_utc_start_and_a_random_suffix(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    assert re.fullmatch(r"grade-\d{8}T\d{6}-[0-9a-f]{6}", runner.run_pass(run_dir, root).grading_id)


# --- the pass: lock, segments, extractions, abandoned segments (ADR-0006/0007) ------------------


def test_a_pass_seals_its_own_segments_and_brackets_its_scores(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB})
    result = runner.run_pass(run_dir, root)
    for fact in runner.PASS_FACTS:
        report = ledger.verify_segment(run_dir / fact / f"{result.grading_id}.jsonl")
        assert report.sealed and report.error is None
        assert result.heads[fact] == report.head_hash
    events = pass_rows(run_dir, "events", result.grading_id)
    assert [e["kind"] for e in events] == ["grading.started", "grading.completed"]
    assert events[0]["catalog_version"] == "0.3" and events[0]["grader_build"] == runner.grader_build()
    assert result.grading_id in views.completed_passes(run_dir)
    keys = [(s["cell_id"], s["metric_id"]) for s in pass_rows(run_dir, "scores", result.grading_id)]
    assert len(keys) == len(set(keys)) == 2 * len(runner.METRICS)  # GradedOncePerPass
    assert all(s["archive_attempt"] == 1 for s in pass_rows(run_dir, "scores", result.grading_id))


def test_grading_completed_records_the_sealed_heads_of_its_other_facts(root, tmp_path):  # ruling R-2
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    result = runner.run_pass(run_dir, root)
    completed = pass_rows(run_dir, "events", result.grading_id)[-1]
    assert completed["kind"] == "grading.completed"
    assert completed["heads"] == {fact: result.heads[fact] for fact in ("model_calls", "tool_calls", "scores")}  # never events


def test_a_pass_counts_the_cells_it_graded(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB, "c": GOOD}, archived={"a", "b"})
    result = runner.run_pass(run_dir, root)
    assert result.cells_graded == 2 == pass_rows(run_dir, "events", result.grading_id)[-1]["cells_graded"]
    assert result.summary() == {"grading_id": result.grading_id, "heads": result.heads, "cells_graded": 2}


def test_only_archived_cells_are_graded(root, tmp_path):  # T-GRD-unarchived
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD}, archived={"a"})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert {cid for cid, _ in s} == {"a"}


def test_a_second_pass_while_the_lock_is_held_is_refused(root, tmp_path):  # T-LOCK
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with oslock.RunLock.acquire(run_dir / "grade.lock"), pytest.raises(BenchError) as err:
        runner.run_pass(run_dir, root)
    assert err.value.code == "HB-GRD-001"
    assert not (run_dir / "scores").exists()


def test_a_regrade_with_the_same_normaliser_writes_no_new_calls(root, tmp_path):  # T-GRD-regrade-same
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    first = runner.run_pass(run_dir, root)
    second = runner.run_pass(run_dir, root)
    assert len(pass_rows(run_dir, "model_calls", first.grading_id)) > 0
    assert pass_rows(run_dir, "model_calls", second.grading_id) == []
    assert pass_rows(run_dir, "tool_calls", second.grading_id) == []
    ex = {s["extraction_id"] for s in pass_rows(run_dir, "scores", second.grading_id)}
    assert ex == {normalize.extraction_id()}
    strip = ("grading_id", "evidence", "hash", "prev_hash", "seq", "recorded_at", "mono_ns")
    a = sorted(json.dumps({k: v for k, v in s.items() if k not in strip}, sort_keys=True)
               for s in pass_rows(run_dir, "scores", first.grading_id))
    b = sorted(json.dumps({k: v for k, v in s.items() if k not in strip}, sort_keys=True)
               for s in pass_rows(run_dir, "scores", second.grading_id))
    assert a == b


def test_a_new_normaliser_writes_a_new_extraction_beside_the_old(root, tmp_path, monkeypatch):  # T-GRD-regrade-new
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    first = runner.run_pass(run_dir, root)
    monkeypatch.setattr(normalize, "extraction_id", lambda: "e" * 64)
    second = runner.run_pass(run_dir, root)
    rows = pass_rows(run_dir, "model_calls", second.grading_id)
    assert len(rows) == len(pass_rows(run_dir, "model_calls", first.grading_id)) > 0
    assert {r["extraction_id"] for r in rows} == {"e" * 64}


def test_an_abandoned_pass_does_not_hold_an_extraction(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "grade-dead") as dead:  # started, never completed
        dead.append({"kind": "grading.started", "grading_id": "grade-dead"})
    with ledger.SegmentWriter.create(run_dir / "model_calls", "grade-dead") as dead:
        dead.append({"kind": "model_call", "cell_id": "a", "extraction_id": normalize.extraction_id()})
    result = runner.run_pass(run_dir, root)
    assert "grade-dead" not in views.completed_passes(run_dir)
    assert len(pass_rows(run_dir, "model_calls", result.grading_id)) > 0


def test_an_abandoned_segment_is_named_once_in_the_next_pass_own_segment(root, tmp_path):  # T-GRD-abandoned
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "scores", "grade-dead") as dead:
        dead.append({"kind": "score", "cell_id": "a", "metric_id": "pass_at_1", "value": 1})
    torn = run_dir / "scores" / "grade-dead.jsonl"
    with torn.open("ab") as f:
        f.write(b'{"kind":"sco')
    before = torn.read_bytes()
    first = runner.run_pass(run_dir, root)
    named = [e for e in pass_rows(run_dir, "events", first.grading_id) if e["kind"] == "segment.abandoned"]
    assert [(e["fact"], e["segment_id"], e["line_count"]) for e in named] == [("scores", "grade-dead", 1)]
    assert torn.read_bytes() == before  # nobody writes into another writer's file
    assert first.abandoned == ["scores/grade-dead"]
    second = runner.run_pass(run_dir, root)
    assert second.abandoned == []
    assert "grade-dead" not in views.completed_passes(run_dir)


# --- conformance: the grading pass against the model's guards (US-44 AC3) --------------------------


def test_engine_and_grading_events_replay_against_the_guards(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB})
    runner.run_pass(run_dir, root)
    lifecycle.replay(views.rows(run_dir, "events"), parallelism=2, scores=views.rows(run_dir, "scores"))


def test_a_score_for_an_unarchived_cell_is_rejected_by_the_replay():
    events = [{"kind": "run.started"}, {"kind": "cell.launch_intent", "cell_id": "a"},
              {"kind": "grading.started", "grading_id": "g"}, {"kind": "grading.completed", "grading_id": "g"}]
    with pytest.raises(lifecycle.ConformanceError, match="ArchivedCellsGetGraded"):
        lifecycle.replay(events, parallelism=1, scores=[{"grading_id": "g", "cell_id": "a", "metric_id": "pass_at_1"}])


def test_a_cell_graded_twice_in_one_pass_is_rejected_by_the_replay():
    cell = ["cell.launch_intent", "attempt.process_started", "attempt.process_ended", "cell.outcome", "cell.archived"]
    events = ([{"kind": "run.started"}] + [{"kind": k, "cell_id": "a"} for k in cell]
              + [{"kind": "grading.started", "grading_id": "g"}, {"kind": "grading.completed", "grading_id": "g"}])
    score = {"grading_id": "g", "cell_id": "a", "metric_id": "pass_at_1"}
    lifecycle.replay(events, parallelism=1, scores=[score])
    with pytest.raises(lifecycle.ConformanceError, match="GradedOncePerPass"):
        lifecycle.replay(events, parallelism=1, scores=[score, score])
