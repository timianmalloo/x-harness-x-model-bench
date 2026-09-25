"""Process grader p1: tool_error_rate and stuck_loops (docs/design/phase3-graders.md, Process).

Seeded cells live under tests/fixtures/grade/process/. Calls are counted after tool_class "meta" is
excluded, in native_ordinal order. The other four process metrics are NA "not built" (p2 and p3).
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
NOT_BUILT = tuple(metric for metric in PROCESS if metric not in ("stuck_loops", "tool_error_rate"))


def grade_fixture(name: str) -> dict[str, Score]:
    """Grade one seeded cell. Metrics this slice does not build stay NA."""
    body = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    scores = grade_cell(CellInput(
        run_dir=Path("."), root=Path("."), plan={}, cell={}, task={}, task_dir=Path("."),
        archive=Path("."), out_dir=Path("."), events=(), record_reason=None, model_calls=(),
        tool_calls=tuple(body["tool_calls"]), turn_usage=(), metrics={}, allow_model_calls=False,
        extraction=None, prices=None,
    ))
    assert set(scores) == set(PROCESS)
    for metric in NOT_BUILT:
        assert scores[metric] == Score(None, "not built")
    return scores


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


def test_the_process_ratios_have_a_catalog_scale_of_4():
    # the runner refuses a Decimal for a metric with no catalog scale (grade/runner.py); the design gives 4 places
    catalog = config.load_yaml(Path(__file__).resolve().parents[1] / "bench" / "metrics.yaml")
    scales = {m["id"]: m.get("scale") for a in catalog["areas"].values() for m in a.get("metrics") or []}
    assert [scales[m] for m in ("tool_error_rate", "recovery_rate", "planning_ratio")] == [4, 4, 4]
