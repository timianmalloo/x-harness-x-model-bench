"""Process grader p3: completion_without_intervention and the time_to_first_green NA
(docs/design/phase3-graders.md, Process).

Seeded cells live under tests/fixtures/grade/process/. Calls are counted after tool_class "meta" is
excluded, in native_ordinal order. p1 and p2 stay. A fixture with no cell.outcome is NA
"no cell outcome". time_to_first_green is NA on every cell.
"""

import json
from decimal import Decimal
from pathlib import Path

from harness_bench import config
from harness_bench.grade import CellInput, Score
from harness_bench.grade.process import grade_cell

FIXTURES = Path(__file__).parent / "fixtures" / "grade" / "process"
PROCESS = (
    "completion_without_intervention",
    "stuck_loops",
    "recovery_rate",
    "tool_error_rate",
    "planning_ratio",
    "time_to_first_green",
)
NO_CELL_OUTCOME = "no cell outcome"
STUCK_NOT_MEASURABLE = "stuck-loop count not measurable"
TIME_TO_FIRST_GREEN_NA = "test runs not identifiable in the tool record (no command text extracted)"


def grade_body(body: dict) -> dict[str, Score]:
    """Grade one synthetic cell. `events` carry cell.outcome when the seed has one."""
    scores = grade_cell(CellInput(
        run_dir=Path("."), root=Path("."), plan={}, cell={}, task={}, task_dir=Path("."),
        archive=Path("."), out_dir=Path("."), events=tuple(body.get("events", ())), record_reason=None,
        model_calls=tuple(body.get("model_calls", ())),
        tool_calls=tuple(body["tool_calls"]), turn_usage=(), metrics={}, allow_model_calls=False,
        extraction=None, prices=None,
    ))
    assert set(scores) == set(PROCESS)
    return scores


def grade_fixture(name: str) -> dict[str, Score]:
    """Grade one seeded cell. These fixtures carry no cell outcome."""
    body = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    scores = grade_body(body)
    assert scores["time_to_first_green"] == Score(None, TIME_TO_FIRST_GREEN_NA)
    assert scores["completion_without_intervention"] == Score(None, NO_CELL_OUTCOME)
    return scores


def _call(ordinal: int, name: str, ok: int | None, tool_class: str = "shell") -> dict:
    return {"native_ordinal": ordinal, "name": name, "tool_class": tool_class, "ok": ok}


def grade_with_outcome(tool_calls: list[dict], outcome: str, cause: str | None,
                       stop_reason: str | None) -> dict[str, Score]:
    """A synthetic cell.outcome plus the tool rows the stuck-loop rule reads."""
    return grade_body({
        "tool_calls": tool_calls,
        "events": [{"kind": "cell.outcome", "outcome": outcome, "cause": cause, "stop_reason": stop_reason}],
    })


def test_a_failed_meta_row_leaves_the_rate_unchanged():
    # 3 Bash failures and 1 Read success, plus a failed ToolSearch between them: still 3/4.
    scores = grade_fixture("failed-meta.json")
    assert scores["tool_error_rate"] == Score(Decimal("0.7500"), None)
    assert scores["stuck_loops"] == Score(1, None)


def test_a_two_run_is_not_a_stuck_loop():
    scores = grade_fixture("stuck-two.json")
    assert scores["stuck_loops"] == Score(0, None)
    assert scores["tool_error_rate"] == Score(Decimal("1.0000"), None)


def test_a_three_run_is_one_stuck_loop():
    # Stored out of native_ordinal order: consecutive means that order, not file order.
    scores = grade_fixture("stuck-three.json")
    assert scores["stuck_loops"] == Score(1, None)
    assert scores["tool_error_rate"] == Score(Decimal("0.7500"), None)


def test_a_four_run_is_one_stuck_loop():
    scores = grade_fixture("stuck-four.json")
    assert scores["stuck_loops"] == Score(1, None)
    assert scores["tool_error_rate"] == Score(Decimal("0.8000"), None)


def test_two_separate_three_runs_are_two_stuck_loops():
    scores = grade_fixture("stuck-two-runs.json")
    assert scores["stuck_loops"] == Score(2, None)
    assert scores["tool_error_rate"] == Score(Decimal("0.8571"), None)


def test_one_failure_in_twenty_three_calls_is_0_0435():
    scores = grade_fixture("one-in-twenty-three.json")
    assert scores["tool_error_rate"] == Score(Decimal("0.0435"), None)
    assert scores["stuck_loops"] == Score(0, None)


def test_a_null_ok_is_na_with_the_missing_counts():
    # 2 nulls among 3 counted calls (a null meta row is excluded, and never a partial ratio).
    scores = grade_fixture("null-ok.json")
    reason = "per-call outcome missing on 2 of 3 calls"
    assert scores["tool_error_rate"] == Score(None, reason)
    assert scores["stuck_loops"] == Score(None, reason)


def test_no_tool_call_is_na():
    for name in ("no-tool-call.json", "only-meta.json"):
        scores = grade_fixture(name)
        assert scores["tool_error_rate"] == Score(None, "no tool call")
        assert scores["stuck_loops"] == Score(None, "no tool call")


def test_a_different_name_breaks_the_run():
    scores = grade_fixture("different-names.json")
    assert scores["stuck_loops"] == Score(0, None)
    assert scores["tool_error_rate"] == Score(Decimal("1.0000"), None)


def test_a_failure_later_followed_by_the_same_name_is_1():
    # Stored out of native_ordinal order: the success is later in that order, not in file order.
    scores = grade_fixture("recovered.json")
    assert scores["recovery_rate"] == Score(Decimal("1.0000"), None)


def test_a_failure_never_followed_by_a_success_is_0():
    scores = grade_fixture("unrecovered.json")
    assert scores["recovery_rate"] == Score(Decimal("0.0000"), None)


def test_no_failed_call_is_na():
    # No counted failure: successes only, no calls, or only a failed meta row.
    for name in ("no-failed-call.json", "no-tool-call.json", "only-meta.json"):
        scores = grade_fixture(name)
        assert scores["recovery_rate"] == Score(None, "no failed tool call")


def test_a_null_ok_is_the_missing_outcome_na_for_recovery():
    # Same counted calls as p1: the null meta row is excluded, and never a partial ratio.
    scores = grade_fixture("null-ok.json")
    assert scores["recovery_rate"] == Score(None, "per-call outcome missing on 2 of 3 calls")


def test_a_later_success_of_another_name_is_not_recovery():
    scores = grade_fixture("recovered-other-name.json")
    assert scores["recovery_rate"] == Score(Decimal("0.0000"), None)


def test_a_success_before_the_failure_is_not_recovery():
    # The success has the earlier native_ordinal and is stored after the failure in the file.
    scores = grade_fixture("success-before-failure.json")
    assert scores["recovery_rate"] == Score(Decimal("0.0000"), None)


def test_seven_of_twenty_requests_before_the_first_edit_is_0_3500():
    # 3 requests before any tool call and 4 after a read but before the edit: the boundary is the edit.
    scores = grade_fixture("planning-seven-of-twenty.json")
    assert scores["planning_ratio"] == Score(Decimal("0.3500"), None)


def test_no_edit_class_call_is_na():
    # A shell call is not an edit, even when model calls are itemised in time.
    scores = grade_fixture("no-edit-class.json")
    reason = "no edit-class tool call (edits through the shell are not classed)"
    assert scores["planning_ratio"] == Score(None, reason)


def test_summary_model_call_rows_are_na():
    # An edit is present, so this is the summary-row NA and not the no-edit NA.
    scores = grade_fixture("summary-model-calls.json")
    assert scores["planning_ratio"] == Score(None, "model calls not itemised in time (summary rows)")


def test_a_budget_end_gives_0():
    # The same clean tool record is 1 when the turn ends on end_turn. The budget is what scores 0.
    scores = grade_with_outcome([_call(1, "Read", 1, "read")], "timed_out", "timed_out", "cancelled")
    assert scores["completion_without_intervention"] == Score(0, None)


def test_a_refusal_gives_0():
    # A refusal is a completed turn with no cause. It is 0 even when stuck_loops is 0.
    scores = grade_with_outcome([_call(1, "Read", 1, "read")], "completed", None, "refusal")
    assert scores["completion_without_intervention"] == Score(0, None)


def test_an_infrastructure_cause_is_the_infrastructure_na():
    scores = grade_with_outcome([_call(1, "Read", 1, "read")], "failed", "provider", None)
    assert scores["completion_without_intervention"] == Score(None, "cell ended by infrastructure: provider")


def test_completed_with_a_three_run_of_failures_gives_0():
    calls = [_call(i, "Bash", 0) for i in (1, 2, 3)]
    scores = grade_with_outcome(calls, "completed", None, "end_turn")
    assert scores["completion_without_intervention"] == Score(0, None)


def test_completed_with_no_failures_gives_1():
    scores = grade_with_outcome([_call(1, "Read", 1, "read"), _call(2, "Bash", 1)], "completed", None, "end_turn")
    assert scores["completion_without_intervention"] == Score(1, None)


def test_completed_with_a_null_ok_is_stuck_loop_count_not_measurable():
    scores = grade_with_outcome([_call(1, "Bash", None)], "completed", None, "end_turn")
    assert scores["completion_without_intervention"] == Score(None, STUCK_NOT_MEASURABLE)


def test_time_to_first_green_is_na():
    scores = grade_with_outcome([_call(1, "Read", 1, "read")], "completed", None, "end_turn")
    assert scores["time_to_first_green"] == Score(None, TIME_TO_FIRST_GREEN_NA)


def test_the_process_ratios_have_a_catalog_scale_of_4():
    # the runner refuses a Decimal for a metric with no catalog scale (grade/runner.py); the design gives 4 places
    catalog = config.load_yaml(Path(__file__).resolve().parents[1] / "bench" / "metrics.yaml")
    scales = {m["id"]: m.get("scale") for a in catalog["areas"].values() for m in a.get("metrics") or []}
    assert [scales[m] for m in ("tool_error_rate", "recovery_rate", "planning_ratio")] == [4, 4, 4]
