"""Tests for mutation grader: mutation_score (design phase3-graders, section Mutation, W3-GR-CODE c6b-1).

Fast tests only (fake Stryker, conftest fails any unmarked test that starts dotnet).
"""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT, gate_runs_root
from test_grade_correctness import d1_cell, git, tree_digest

from harness_bench import config, plan, views
from harness_bench.archive import make_writable
from harness_bench.grade import CellInput, Score, mutation, runner
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
                 timed_out: bool = False, stdout: str = "", stderr: str = "",
                 configs: list[dict] | None = None) -> list[list[str]]:
    seen = []
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            seen.append(list(argv))
            if timed_out:
                return procs.Completed(None, "", "", True, False, 0.0)
            cwd = Path(kwargs.get("cwd", ""))
            if configs is not None:
                cfg_path = cwd / "stryker-config.json"
                if cfg_path.is_file():
                    configs.append(json.loads(cfg_path.read_text(encoding="utf-8")))
            if report_content is not None and returncode == 0:
                report_dir = cwd / "StrykerOutput" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                (report_dir / "mutation-report.json").write_text(report_content, encoding="utf-8")
            return procs.Completed(returncode, stdout or "The final mutation score is 85.71 %\n", stderr, False, False, 0.0)
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


def test_mutation_score_with_timeout_and_no_coverage(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    report = {
        "schemaVersion": "2",
        "thresholds": {},
        "files": {
            "f.cs": {
                "mutants": [
                    *([{"status": "Killed"}] * 10),
                    *([{"status": "Timeout"}] * 2),
                    *([{"status": "Survived"}] * 2),
                    *([{"status": "NoCoverage"}] * 2),
                ]
            }
        },
    }
    fake_stryker(monkeypatch, returncode=0, report_content=json.dumps(report))
    inp = mutation_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "mutation")
    out = mutation.grade_cell(inp)
    assert out[METRIC].value == Decimal("0.7500")


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


# --- Red 3: shared NA reasons ---------------------------------------------------------------------------------------


def test_no_working_copy_is_na(tmp_path):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    shutil.rmtree(folder / "ws", onexc=make_writable)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "no working copy in the archive")


def test_no_builder_commit_is_na(tmp_path):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    git(folder / "ws", "commit", "-q", "--amend", "-m", "broken commit message")
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "pre-turn commit not found in the working copy")


def test_mutation_timeout_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    fake_stryker(monkeypatch, timed_out=True)
    got = grade_d1(tmp_path, folder, cell, timeout=60)
    assert got.get(METRIC) == (None, "HB-GRD-002 grading step timeout after 60 s")


# --- Red 4: stryker config, runner registration and metric filter ---------------------------------------------------


def test_stryker_config_json_pinned_timeout_and_command_args(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    configs = []
    seen_calls = fake_stryker(monkeypatch, returncode=0, report_content=REPORT_FIXTURE, configs=configs)
    inp = mutation_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "mutation")
    out = mutation.grade_cell(inp)
    assert out[METRIC].value == Decimal("0.8571")
    assert len(seen_calls) == 1
    call = seen_calls[0]
    assert call[0] in ("dotnet", "dotnet.exe")
    assert call[1] == "exec"
    assert "Stryker.CLI.dll" in call[2]
    assert "--skip-version-check" in call
    assert "--break-on-initial-test-failure" not in call
    assert "--config-file" in call
    assert "stryker-config.json" in call
    assert len(configs) == 1
    assert configs[0]["stryker-config"]["additional-timeout"] == 5000
    assert configs[0]["stryker-config"]["project"] == "AiDe.Core.csproj"


def test_initial_failing_tests_parsed_from_stryker_warning(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    stdout = "[12:00:00 WRN] 75 tests are failing. Stryker will continue but outcome will be impacted.\n"
    fake_stryker(monkeypatch, returncode=0, report_content=REPORT_FIXTURE, stdout=stdout)
    out_dir = tmp_path / "run" / "grading" / "g" / "c1" / "mutation"
    out = mutation.grade_cell(mutation_input(tmp_path / "run", folder, cell, out_dir))
    assert out[METRIC].value == Decimal("0.8571")
    assert out[METRIC].reason is None
    log = (out_dir / "mutation.log").read_text(encoding="utf-8")
    assert "initial_failing_tests: 75\n" in log


def test_initial_failing_tests_not_recorded_when_the_line_is_absent(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    fake_stryker(monkeypatch, returncode=0, report_content=REPORT_FIXTURE, stdout="The final mutation score is 85.71 %\n")
    out_dir = tmp_path / "run" / "grading" / "g" / "c1" / "mutation"
    out = mutation.grade_cell(mutation_input(tmp_path / "run", folder, cell, out_dir))
    assert out[METRIC].value == Decimal("0.8571")
    log = (out_dir / "mutation.log").read_text(encoding="utf-8")
    assert "initial_failing_tests: not recorded\n" in log
    assert "initial_failing_tests: 0\n" not in log


def test_mutation_is_registered_in_runner_graders():
    assert "mutation" in runner.GRADERS and runner.GRADERS["mutation"] is mutation.grade_cell


def test_mutation_filters_metrics_when_requested(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {PROJECTION: REFERENCE, TEST_FILE: TEST_CODE})
    fake_stryker(monkeypatch, returncode=0, report_content=REPORT_FIXTURE)
    inp = mutation_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "mutation")
    inp_empty = CellInput(
        run_dir=inp.run_dir,
        root=inp.root,
        plan=inp.plan,
        cell=inp.cell,
        task=inp.task,
        task_dir=inp.task_dir,
        archive=inp.archive,
        out_dir=inp.out_dir,
        events=inp.events,
        record_reason=inp.record_reason,
        model_calls=inp.model_calls,
        tool_calls=inp.tool_calls,
        turn_usage=inp.turn_usage,
        metrics={"other_metric": {}},
        allow_model_calls=inp.allow_model_calls,
        extraction=inp.extraction,
        prices=inp.prices,
    )
    out = mutation.grade_cell(inp_empty)
    assert list(out.keys()) == []


def test_mutation_score_has_its_catalog_scale_of_4():
    # the runner refuses a Decimal for a metric with no catalog scale (HB-GRD-003 in a real pass); the design gives scale 4
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    scales = {m["id"]: m.get("scale") for a in catalog["areas"].values() for m in a.get("metrics") or []}
    assert scales["mutation_score"] == 4


# --- Slow ring (real dotnet and real Stryker.NET 4.16.0, W3-GR-CODE c6b-3) -------------------------------------------

NEW_TEST_PROJ = "tests/D1.SeedTests/D1.SeedTests.csproj"
NEW_TEST_CODE = "tests/D1.SeedTests/SeedTest.cs"
NEW_TEST_PROJ_CONTENT = (
    '<Project Sdk="Microsoft.NET.Sdk">\n'
    "  <PropertyGroup>\n"
    "    <TargetFramework>net10.0</TargetFramework>\n"
    "    <Nullable>enable</Nullable>\n"
    "    <ImplicitUsings>enable</ImplicitUsings>\n"
    "    <IsPackable>false</IsPackable>\n"
    "  </PropertyGroup>\n"
    "  <ItemGroup>\n"
    '    <PackageReference Include="Microsoft.NET.Test.Sdk" />\n'
    '    <PackageReference Include="xunit" />\n'
    '    <PackageReference Include="xunit.runner.visualstudio" />\n'
    '    <ProjectReference Include="../../src/AiDe.Core/AiDe.Core.csproj" />\n'
    "  </ItemGroup>\n"
    "  <ItemGroup>\n"
    '    <Using Include="Xunit" />\n'
    "  </ItemGroup>\n"
    "</Project>\n"
)
NEW_TEST_CODE_CONTENT = (
    "namespace D1.SeedTests;\n\n"
    "public class SeedTest\n"
    "{\n"
    "    [Fact]\n"
    "    public void DoesNotCallCompute()\n"
    "    {\n"
    "        Assert.True(true);\n"
    "    }\n"
    "}\n"
)


@pytest.mark.slow
def test_d1_reference_plus_new_test_project_seed_or_no_compute_scores_zero(tmp_path):
    folder, cell = d1_cell(
        tmp_path,
        {
            PROJECTION: REFERENCE,
            NEW_TEST_PROJ: NEW_TEST_PROJ_CONTENT,
            NEW_TEST_CODE: NEW_TEST_CODE_CONTENT,
        },
    )
    before = tree_digest(folder)
    inp = mutation_input(tmp_path, folder, cell, tmp_path / "grading" / "c1" / "mutation")
    out = mutation.grade_cell(inp)
    assert tree_digest(folder) == before, "grading wrote under the archive"
    assert out[METRIC].value == Decimal("0.0000")
    assert out[METRIC].reason is None


RED_TEST_PROJ = "tests/D1.RedBaselineTests/D1.RedBaselineTests.csproj"
RED_TEST_CODE = "tests/D1.RedBaselineTests/RedBaselineTest.cs"
# Stryker 4.16.0 exits 1 when at least half the initial tests fail
# ("Initial testrun has more than 50% failing tests"). One failing test out of two hits that bail,
# so the project also holds a second test that never calls Compute. The red count stays 1.
RED_TEST_CODE_CONTENT = (
    "namespace D1.RedBaselineTests;\n\n"
    "public class RedBaselineTest\n"
    "{\n"
    "    [Fact]\n"
    "    public void AlwaysFails()\n"
    "    {\n"
    "        var result = AiDe.Core.Projections.EvidenceCensusProjection.Compute(\n"
    "            new List<AiDe.Core.Facts.EvidenceAssertion>(), new AiDe.Core.Projections.EvidenceCensusQuery(), \"rev\");\n"
    "        Assert.Null(result);\n"
    "    }\n\n"
    "    [Fact]\n"
    "    public void DoesNotCallCompute()\n"
    "    {\n"
    "        Assert.True(true);\n"
    "    }\n\n"
    "    [Fact]\n"
    "    public void AlsoDoesNotCallCompute()\n"
    "    {\n"
    "        Assert.True(true);\n"
    "    }\n"
    "}\n"
)


@pytest.mark.slow
def test_d1_reference_plus_seed_or_no_compute_one_always_failing_scores_zero(tmp_path):
    folder, cell = d1_cell(
        tmp_path,
        {
            PROJECTION: REFERENCE,
            RED_TEST_PROJ: NEW_TEST_PROJ_CONTENT,
            RED_TEST_CODE: RED_TEST_CODE_CONTENT,
        },
    )
    before = tree_digest(folder)
    out_dir = tmp_path / "grading" / "c1" / "mutation"
    out = mutation.grade_cell(mutation_input(tmp_path, folder, cell, out_dir))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    assert out[METRIC].value == Decimal("0.0000")
    assert out[METRIC].reason is None
    log = (out_dir / "mutation.log").read_text(encoding="utf-8")
    assert "\nexit 0\n" in log
    assert "initial_failing_tests: 1\n" in log
    report = json.loads((out_dir / "mutation-report.json").read_text(encoding="utf-8"))
    names = {t["id"]: t["name"] for f in report.get("testFiles", {}).values() for t in f.get("tests", [])}
    mutants = [m for f in report["files"].values() for m in f["mutants"]]
    # AlwaysFails calls Compute, so it covers the reference's mutants and fails with or without them: a mutant it
    # covers is Survived when Stryker ignores an initially failing test, and would be Killed if it did not (R-75 c3).
    assert sum(m["status"] == "Survived" for m in mutants) >= 1, "the failing test covered no mutant: the seed proves nothing"
    assert sum(m["status"] == "Killed" for m in mutants) == 0
    killers = {names.get(k, k) for m in mutants for k in m.get("killedBy") or []}
    assert not any("AlwaysFails" in k for k in killers)


# The 6 row15-d1-1 cells graded through mutation_score (design: phase3-graders.md, section Mutation).
# 35af195cfe821dca wrote no tests; the other five are characterization values under R-75 (Stryker runs over the red
# vendored baseline, initial_failing_tests 74 on each cell and run; graded twice by the Leader 2026-09-25, equal).
GATE_D1_MUTATION: dict[str, tuple[str | None, str | None]] = {
    "2535962f830d7718": ("0.9286", None),
    "35af195cfe821dca": (None, "no tests written"),
    "3ff04431d3b5ac27": ("0.9286", None),
    "4a6250261f80ded4": ("0.9286", None),
    "c3d40fa1377ba0dc": ("0.8095", None),
    "caa8ca38b1a929a8": ("0.9286", None),
}


@pytest.mark.slow
def test_row15_d1_cells_graded_twice_give_characterization_values_and_leave_archives_unchanged(tmp_path):
    gate_root = gate_runs_root()
    run = gate_root / "row15-d1-1"
    if not (run / "plan.json").is_file():
        pytest.skip("gate run row15-d1-1 is not on this host (set HB_GATE_RUNS to the runs folder)")
    attempts = {e["cell_id"]: e["archive_attempt"] for e in views.rows(run, "events") if e["kind"] == "cell.archived"}
    cells = {c["cell_id"]: c for c in plan.load_confirmed(run)["cells"]}

    for cid in sorted(cells.keys()):
        attempt = attempts[cid]
        folder = run / "archive" / cid / f"attempt-{attempt}"
        before = tree_digest(folder)

        out1 = mutation.grade_cell(
            mutation_input(tmp_path, folder, cells[cid], tmp_path / "grading" / cid / "run_1")
        )
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
        score1 = encode(out1[METRIC])

        if cid == "35af195cfe821dca":
            assert score1 == (None, "no tests written")
            assert score1 == GATE_D1_MUTATION[cid]
            continue

        out2 = mutation.grade_cell(
            mutation_input(tmp_path, folder, cells[cid], tmp_path / "grading" / cid / "run_2")
        )
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
        score2 = encode(out2[METRIC])

        assert score1 == score2, f"Cell {cid} repeated runs produced different scores: {score1} vs {score2}"
        assert score1 == GATE_D1_MUTATION[cid]


