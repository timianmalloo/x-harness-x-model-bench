"""The per-cell grader input and the dispatch by the task's graders (design docs/design/phase3-graders.md, CORE s1).

Each pass test builds a real archived run with `archived_runs` and grades it for real (the X1 hidden tests run). A
grader is replaced only through `runner.GRADERS`, the one seam the design names. The expected metric sets are the
catalog's `kind: score` metrics of each grader, written out here so a catalog edit is visible in this file.
"""

from decimal import Decimal

import pytest
import yaml
from archived_runs import CODEX_MODEL, GOOD, make_root, make_run, pass_rows

from harness_bench import views
from harness_bench.grade import Score, runner

CORRECTNESS = {"pass_at_1", "partial_credit", "build_and_suite_clean", "regression_count", "behavioural_equivalence"}
COST = {"cost_usd", "tokens_per_minute", "output_tokens_per_turn", "cache_hit_ratio", "cache_write_amplification",
        "context_growth", "compactions"}
PROCESS = {"completion_without_intervention", "stuck_loops", "recovery_rate", "tool_error_rate", "planning_ratio",
           "time_to_first_green"}
BUILT = {"pass_at_1", "partial_credit", "cost_usd"}  # the metrics the registered graders return in slice 1


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def set_graders(root, names: list[str]) -> None:
    """X1's `graders:` list, set before `make_run` so the plan freezes this task version."""
    path = root / "tasks" / "X1" / "task.yaml"
    task = yaml.safe_load(path.read_text(encoding="utf-8"))
    task["graders"] = names
    path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")


def graded(root, tmp_path) -> list[dict]:
    """The score rows of one pass over a one-cell run whose working copy passes every hidden test."""
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    return pass_rows(run_dir, "scores", runner.run_pass(run_dir, root).grading_id)


# --- dispatch by the task's graders (replaces METRICS) ------------------------------------------------------------


@pytest.mark.parametrize(("names", "expected"), [
    (["cost"], COST),
    (["correctness", "cost"], CORRECTNESS | COST),
    (["process", "correctness", "cost"], CORRECTNESS | COST | PROCESS),
])
def test_the_pass_writes_one_row_per_applicable_metric_of_the_tasks_graders(root, tmp_path, names, expected):
    set_graders(root, names)
    assert sorted(r["metric_id"] for r in graded(root, tmp_path)) == sorted(expected)


def test_an_unbuilt_grader_is_na_not_built_for_each_of_its_metrics_never_0(root, tmp_path):
    set_graders(root, ["correctness", "cost", "process"])
    got = {r["metric_id"]: (r["value"], r["reason"]) for r in graded(root, tmp_path)}
    assert {m: v for m, v in got.items() if m not in BUILT} == {m: (None, "not built") for m in (CORRECTNESS | COST | PROCESS) - BUILT}
    assert (got.get("pass_at_1"), got.get("partial_credit")) == ((1, None), ("1.0000", None))  # the built metrics are measured


# --- a failing or malformed grader is NA HB-GRD-003, and the pass continues (F3) ---------------------------------


def with_grader(monkeypatch, name: str, fn) -> None:
    """Replace one registry entry for this test (`raising=False`: the red commit predates the registry)."""
    monkeypatch.setattr(runner, "GRADERS", {**getattr(runner, "GRADERS", {}), name: fn}, raising=False)


def test_a_raising_grader_is_na_with_its_type_and_the_pass_completes(root, tmp_path, monkeypatch):
    def boom(inp):
        raise RuntimeError(f"agent text and a host path {tmp_path}")  # never reaches a reason

    with_grader(monkeypatch, "correctness", boom)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    result = runner.run_pass(run_dir, root)
    rows = {r["metric_id"]: r for r in pass_rows(run_dir, "scores", result.grading_id)}
    assert {m: (rows[m]["value"], rows[m]["reason"]) for m in CORRECTNESS if m in rows} == \
        {m: (None, "HB-GRD-003 grader correctness failed: RuntimeError") for m in CORRECTNESS}
    assert rows["cost_usd"]["reason"] == f"no price list entry for {CODEX_MODEL}"  # the other graders still ran
    assert result.grading_id in views.completed_passes(run_dir)
    assert rows["pass_at_1"]["evidence"] == f"grading/{result.grading_id}/a/correctness/error.log"
    assert "RuntimeError: agent text" in (run_dir / rows["pass_at_1"]["evidence"]).read_text(encoding="utf-8")  # the traceback


@pytest.mark.parametrize(("output", "exc"), [
    (lambda inp: [("pass_at_1", Score(1, None))], "TypeError"),  # not a mapping
    (lambda inp: {"pass_at_1": 1}, "TypeError"),  # not a Score
    (lambda inp: {"pass_at_1": Score(Decimal("0.5"), None)}, "ValueError"),  # a Decimal for a metric with no catalog scale
])
def test_a_malformed_grader_output_is_na_hb_grd_003(root, tmp_path, monkeypatch, output, exc):
    with_grader(monkeypatch, "correctness", output)
    got = {r["metric_id"]: (r["value"], r["reason"]) for r in graded(root, tmp_path)}
    assert got.get("pass_at_1") == (None, f"HB-GRD-003 grader correctness failed: {exc}")
    assert got.get("partial_credit") == (None, f"HB-GRD-003 grader correctness failed: {exc}")  # every metric of the grader
