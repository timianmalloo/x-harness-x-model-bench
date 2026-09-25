"""Rigor grader: static_analysis_delta and NA-by-design metrics (design phase3-graders, section Rigor, GR-CODE c5).

- The D1 fixtures are the frozen tasks/D1/workspace in a temporary git repo that reproduces the archive's commits
  (d1_cell from the correctness tests). Fast tests use a fake dotnet; tests running real dotnet are @pytest.mark.slow.
- Every grade asserts the archive's bytes did not move (F9).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT
from test_grade_correctness import BROKEN, d1_cell, done, tree_digest

from harness_bench import config, plan
from harness_bench.grade import CellInput, Score, rigor
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
METRIC = "static_analysis_delta"
D1 = ROOT / "tasks" / "D1"
D1_VERSION = plan.task_version_hash(D1)

UNUSED_LOCAL = {
    "src/AiDe.Core/Projections/UnusedLocal.cs": (
        "namespace AiDe.Core.Projections;\n\n"
        "public static class UnusedLocal\n"
        "{\n"
        "    public static void Foo()\n"
        "    {\n"
        "        int unused;\n"
        "    }\n"
        "}\n"
    )
}


def encode(score: Score) -> tuple:
    v = score.value
    return (str(v) if isinstance(v, Decimal) else v), score.reason


def rigor_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(
        run_dir=run_dir,
        root=ROOT,
        plan={"parameters": {"grading_step_timeout": timeout}},
        cell=cell,
        task=config.load_yaml(task_dir / "task.yaml"),
        task_dir=task_dir,
        archive=archive,
        out_dir=out_dir,
        events=(),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics=applicable(CATALOG, ["rigor"])["rigor"],
        allow_model_calls=False,
        extraction=None,
        prices=None,
    )


def grade_d1(tmp_path: Path, folder: Path, cell: dict, timeout: int = 900) -> dict[str, tuple]:
    """Every rigor Score of the cell as (value, reason); the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = rigor.grade_cell(
        rigor_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "rigor", timeout=timeout)
    )
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return {m: encode(s) for m, s in out.items()}


# --- the design's seeded fixture (CS0168) ---------------------------------------------------------------------------


@pytest.mark.slow
def test_d1_base_plus_unused_local_gives_static_analysis_delta_plus_1(tmp_path):  # design: Rigor, Fixtures
    got = grade_d1(tmp_path, *d1_cell(tmp_path, UNUSED_LOCAL))
    assert got.get(METRIC) == (1, None)


# --- the design's NA reasons for static_analysis_delta -------------------------------------------------------------


@pytest.mark.slow
def test_d1_syntax_error_is_na_workspace_does_not_build(tmp_path):  # design: Rigor, NA reasons
    got = grade_d1(tmp_path, *d1_cell(tmp_path, BROKEN))
    assert got.get(METRIC) == (None, "workspace does not build")


def test_pre_turn_tree_does_not_build_is_na(tmp_path, monkeypatch):  # design: Rigor, NA reasons
    seen = []
    # Fast test: fake dotnet answers version=0, cell build=0, pre-turn build=1 (compile error)
    queue = [done(0, "10.0.303"), done(0, ""), done(0, "10.0.303"), done(1, "error CS1002: ; expected")]

    def run(argv, **kwargs):
        seen.append(argv)
        return queue.pop(0) if queue else done(0, "")

    from harness_bench import procs
    monkeypatch.setattr(procs, "run", run)
    folder, cell = d1_cell(tmp_path, {})
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "pre-turn tree does not build")


# --- the 4 NA-by-design metrics ------------------------------------------------------------------------------------


NA_BY_DESIGN = {
    "verification_before_done": "test runs not identifiable in the tool record (no command text extracted)",
    "test_quality": "mechanical rung is mutation_score (not counted twice); no rubric for this task",
    "maintainability": "no maintainability tool pinned in this catalog version",
    "style_conformance": (
        "no task-defined style rules (a root .editorconfig exists only in pack-on trees: a treatment); no rubric for"
        " this task"
    ),
}


@pytest.mark.parametrize(("metric", "reason"), list(NA_BY_DESIGN.items()))
def test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim(tmp_path, metric, reason):
    folder, cell = d1_cell(tmp_path, {})
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(metric) == (None, reason)
