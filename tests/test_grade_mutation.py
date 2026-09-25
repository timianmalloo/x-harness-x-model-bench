"""Tests for mutation grader: mutation_score (design phase3-graders, section Mutation, W3-GR-CODE c6b-1).

Fast tests only (fake Stryker, conftest fails any unmarked test that starts dotnet).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from archived_runs import ROOT
from test_grade_correctness import d1_cell, tree_digest

from harness_bench import config
from harness_bench.grade import CellInput, Score, mutation
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
METRIC = "mutation_score"
D1 = ROOT / "tasks" / "D1"
PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
REFERENCE = (D1 / "oracle" / "reference" / PROJECTION).read_text(encoding="utf-8")
TEST_FILE = "tests/AiDe.Core.Tests/EvidenceCensusProjectionTests.cs"
TEST_CODE = (
    "namespace AiDe.Core.Tests;\n\n"
    "public class EvidenceCensusProjectionTests\n"
    "{\n"
    "    [Fact]\n"
    "    public void DummyTest() {}\n"
    "}\n"
)
REPORT_FIXTURE = (ROOT / "tests" / "fixtures" / "grade" / "mutation" / "mutation-report.json").read_text(encoding="utf-8")


def encode(score: Score) -> tuple:
    v = score.value
    return (str(v) if isinstance(v, Decimal) else v), score.reason


def mutation_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
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
        metrics=applicable(CATALOG, ["mutation"])["mutation"],
        allow_model_calls=False,
        extraction=None,
        prices=None,
    )


def grade_d1(tmp_path: Path, folder: Path, cell: dict, timeout: int = 900) -> dict[str, tuple]:
    before = tree_digest(folder)
    out = mutation.grade_cell(
        mutation_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "mutation", timeout=timeout)
    )
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return {m: encode(s) for m, s in out.items()}


def fake_stryker(monkeypatch, returncode: int = 0, report_content: str | None = None,
                 timed_out: bool = False, stdout: str = "", stderr: str = "") -> list[list[str]]:
    seen = []
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            seen.append(list(argv))
            if timed_out:
                return procs.Completed(returncode=None, stdout="", stderr="", timed_out=True)
            cwd = Path(kwargs.get("cwd", ""))
            if report_content is not None and returncode == 0:
                report_dir = cwd / "StrykerOutput" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                (report_dir / "mutation-report.json").write_text(report_content, encoding="utf-8")
            return procs.Completed(returncode=returncode, stdout=stdout or "The final mutation score is 85.71 %\n", stderr=stderr)
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    return seen


# --- Red 1: exact score calculation from report fixture -------------------------------------------------------------


def test_mutation_score_computed_from_stryker_report_fixture(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    fake_stryker(monkeypatch, returncode=0, report_content=REPORT_FIXTURE)
    inp = mutation_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "mutation")
    out = mutation.grade_cell(inp)
    score = out[METRIC]
    assert score.value == Decimal("0.8571")
    assert score.reason is None
    assert score.evidence == "grading/g/c1/mutation/mutation.log"


# --- Red 2: mutation-specific NA reasons ----------------------------------------------------------------------------


def test_no_tests_written_when_only_source_changed_is_na(tmp_path):
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {PROJECTION: REFERENCE}))
    assert got.get(METRIC) == (None, "no tests written")


def test_no_tests_written_when_nothing_changed_is_na(tmp_path):
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {}))
    assert got.get(METRIC) == (None, "no tests written")


def test_no_non_test_source_changed_is_na(tmp_path):
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {TEST_FILE: TEST_CODE}))
    assert got.get(METRIC) == (None, "no non-test source changed")


def test_no_mutants_generated_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    empty_report = '{"schemaVersion": "2", "thresholds": {}, "files": {}}'
    fake_stryker(monkeypatch, returncode=0, report_content=empty_report)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "no mutants generated")


def test_mutation_tool_not_available_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    monkeypatch.setattr(mutation, "find_stryker_dll", lambda: None)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "mutation tool not available")


def test_mutation_run_failed_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    fake_stryker(monkeypatch, returncode=1, stderr="Stryker failed to analyze project")
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "mutation run failed: 1")
