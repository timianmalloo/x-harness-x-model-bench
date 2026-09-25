"""Grading passes (ADR-0006, ADR-0007; design: Data model, Failure-mode analysis T-GRD-*).

Each test builds a real archived run on disk: engine segments written with the real ledger, an archive
folder as the archiver lays it out (`archive/<cell>/attempt-1/{ws,home}`), and the real captured Codex
record as the cell's native record. The grading pass runs for real, including the hidden tests in their
own job.
"""

import hashlib
import json
import re
import shutil
from decimal import Decimal
from types import SimpleNamespace

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
from harness_bench.grade import correctness, cost, runner
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
    ("Ran 9 tests in 0.1s\n\nFAILED (failures=9)\nRan 4 tests in 0.001s\n\nFAILED (failures=1)\n", (4, 3)),  # the last summary
    ("Ran 4 tests in 0.001s\n", None),  # a count with no verdict line
    ("Ran 1 test in 0.0s\n\nFAILED (failures=1, errors=1)\n", (1, 0)),  # never a negative pass count
])
def test_the_unittest_summary_is_parsed_strictly(stderr, expected):
    assert correctness.parse_unittest(stderr) == expected


@pytest.mark.parametrize("oracle", [{"runner": "pytest", "command": ["{python}", "-m", "pytest"]}, {"runner": "unittest"},
                                    {"runner": "zeta", "command": ["{python}", "-c", "pass"]}])
def test_an_oracle_phase_1_cannot_run_is_na_before_anything_runs(tmp_path, oracle):
    result = correctness.grade(tmp_path / "ws", tmp_path / "task", oracle, tmp_path / "out", tmp_path, 10)
    assert (result.passed, result.partial_credit, result.evidence) == (None, None, "")
    assert result.reason == f"oracle runner {oracle['runner']!r} not built (phase 1 runs unittest)"


@pytest.mark.parametrize(("summary", "exit_code", "expected"), [
    ("Ran 0 tests in 0.0s\\n\\nOK\\n", 0, (None, None, "no hidden test ran")),
    ("Ran 2 tests in 0.0s\\n\\nOK\\n", 1, (0, Decimal(1), None)),  # every test passed but the oracle failed: not a pass
    ("Ran 2 tests in 0.0s\\n\\nOK\\n", 0, (1, Decimal(1), None)),
    ("Ran 300 tests in 0.0s\\n\\nOK\\n", 0, (1, Decimal(1), None)),  # counts compared by value, past the small-int cache
])
def test_a_pass_needs_tests_to_run_and_the_oracle_to_exit_0(tmp_path, summary, exit_code, expected):
    (tmp_path / "ws").mkdir()
    (tmp_path / "task" / "tests").mkdir(parents=True)
    oracle = {"runner": "unittest", "command": ["{python}", "-c", f"import sys; sys.stderr.write('{summary}'); sys.exit({exit_code})"]}
    result = correctness.grade(tmp_path / "ws", tmp_path / "task", oracle, tmp_path / "run" / "out", tmp_path / "run", 60)
    assert (result.passed, result.partial_credit, result.reason) == expected


def test_an_oracle_killed_by_a_signal_is_not_a_pass(tmp_path, monkeypatch):  # POSIX gives a negative return code
    (tmp_path / "ws").mkdir()
    (tmp_path / "task" / "tests").mkdir(parents=True)
    done = SimpleNamespace(returncode=-9, stdout="", stderr="Ran 2 tests in 0.0s\n\nOK\n", timed_out=False)
    monkeypatch.setattr(correctness.procs, "run", lambda *a, **k: done)
    oracle = {"runner": "unittest", "command": ["{python}", "-m", "unittest"]}
    result = correctness.grade(tmp_path / "ws", tmp_path / "task", oracle, tmp_path / "run" / "out", tmp_path / "run", 60)
    assert (result.passed, result.partial_credit) == (0, Decimal(1))


def test_only_the_exact_python_placeholder_is_replaced(tmp_path, monkeypatch):  # arguments sorting above it stay (T12)
    import sys

    (tmp_path / "ws").mkdir()
    (tmp_path / "task" / "tests").mkdir(parents=True)
    seen = []
    done = SimpleNamespace(returncode=0, stdout="", stderr="Ran 1 test in 0.0s\n\nOK\n", timed_out=False)
    monkeypatch.setattr(correctness.procs, "run", lambda argv, **k: seen.append(argv) or done)
    oracle = {"runner": "unittest", "command": ["{python}", "-m", "unittest", "{workspace}", "~tests"]}
    correctness.grade(tmp_path / "ws", tmp_path / "task", oracle, tmp_path / "run" / "out", tmp_path / "run", 60)
    assert seen == [[sys.executable, "-m", "unittest", "{workspace}", "~tests"]]


def test_not_recorded_is_one_falsy_sentinel_and_scores_and_results_are_frozen():
    from dataclasses import FrozenInstanceError

    from harness_bench import grade

    assert grade.NOT_RECORDED is grade._NotRecorded() and not grade.NOT_RECORDED and repr(grade.NOT_RECORDED) == "NOT_RECORDED"
    with pytest.raises(FrozenInstanceError):
        grade.Score(1.0, "e").value = 2.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        correctness.Result(1, None, None, "").passed = 0  # type: ignore[misc]


def test_the_grader_build_hashes_the_grader_sources():
    assert runner.grader_build() != hashlib.sha256().hexdigest()  # never the hash of nothing


def test_cost_uses_only_the_exact_model_entry_in_force_on_the_run_date():
    prices = {"entries": [{"model": "a-model", "effective": "2026-01-01", "output": 1},
                          {"model": "z-model", "effective": "2026-01-01", "output": 1}]}
    usage = {"m-model": {"uncached_input": 0, "cache_read": 0, "cache_write": 0, "output": 1_000_000}}
    assert cost.cost_usd(usage, prices, "2026-09-23") == (None, "no price list entry for m-model", "")
    prices["entries"].append({"model": "m-model", "effective": "2026-09-23", "output": 10})  # in force on its own date
    assert cost.cost_usd(usage, prices, "2026-09-23") == (Decimal(10), None, "bench/prices.yaml#m-model@2026-09-23")


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


@pytest.mark.parametrize("forged", ["0" * 64, "g" * 64])  # a mismatch that sorts below, or above, the plan's hash
def test_a_changed_price_list_or_task_is_refused_whichever_way_its_hash_sorts(root, tmp_path, monkeypatch, forged):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    monkeypatch.setattr(runner, "file_hash", lambda path: forged)
    monkeypatch.setattr(runner, "task_version_hash", lambda path: forged)
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "cost_usd"]["reason"] == "price list changed since the plan (hash mismatch)"
    assert s["a", "pass_at_1"]["reason"] == "task changed since the plan (version hash mismatch)"


def test_the_run_date_is_the_plan_day_so_an_entry_effective_that_day_applies(root, tmp_path):
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-23", "source": "s", "input": 1, "output": 1,
                       "cache_read": 1, "cache_write": 1}])  # the plan was created 2026-09-23
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert s["a", "cost_usd"]["evidence"] == f"bench/prices.yaml#{CODEX_MODEL}@2026-09-23"


def test_a_pass_closes_every_segment_it_wrote(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    assert not [k for k in ledger._open_writers if done.grading_id in k]  # every writer released its claim
    for fact in runner.PASS_FACTS:
        (run_dir / fact / f"{done.grading_id}.jsonl").unlink()  # Windows refuses to delete a file still open


def test_two_native_records_for_one_session_are_na(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    record = next((run_dir / "archive" / "a" / "attempt-1" / "home").rglob("*.jsonl"))
    shutil.copy(record, record.with_name("rollout-2026-09-23-copy-sess-a.jsonl"))
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "cost_usd"]["value"], s["a", "cost_usd"]["reason"]) == (None, "more than one native record for the session")


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
    assert completed["unreadable_records"] == {}  # R-15: every cell's record was read


def test_grading_completed_names_each_cell_whose_native_record_could_not_be_read(root, tmp_path):  # R-15 (Q5)
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD, "c": GOOD})
    next((run_dir / "archive/b/attempt-1/home").rglob("*.jsonl")).unlink()
    extra = run_dir / "archive/c/attempt-1/home/sessions/2026/09/rollout-2026-09-24-sess-c.jsonl"
    shutil.copy(FIX / "native" / "codex" / "ok.jsonl", extra)  # a second record for the one session is ambiguous
    result = runner.run_pass(run_dir, root)
    completed = pass_rows(run_dir, "events", result.grading_id)[-1]
    assert completed["unreadable_records"] == {"b": "no native record for the session",
                                               "c": "more than one native record for the session"}


def test_a_truncated_record_has_no_cost_from_a_partial_sum(root, tmp_path, monkeypatch):  # R-15 class sweep: never a partial sum
    from harness_bench import profiles
    real = profiles.READERS["codex"]

    def truncated(path):
        ex = real(path)
        ex.truncated = True  # the calls before the size bound were read; the rest were not
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", truncated)
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": 1, "output": 1,
                       "cache_read": 1, "cache_write": 1}])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    s = scores(run_dir, runner.run_pass(run_dir, root).grading_id)
    assert (s["a", "cost_usd"]["value"], s["a", "cost_usd"]["reason"]) == (None, "native record truncated at the size bound")


def test_a_record_level_missing_field_or_a_truncated_record_is_unreadable():  # R-15: a call-level field is not
    from harness_bench.telemetry import Extraction, MissingField
    assert normalize.record_unreadable(Extraction(missing=[MissingField(0, "session.shutdown"), MissingField(0, "events.version")])) \
        == "native record fields missing: events.version, session.shutdown"
    assert normalize.record_unreadable(Extraction(truncated=True)) == "native record truncated at the size bound"
    assert normalize.record_unreadable(Extraction(missing=[MissingField(3, "input_tokens")])) is None
    assert normalize.record_unreadable(Extraction()) is None


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
