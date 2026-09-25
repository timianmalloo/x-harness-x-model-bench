"""Rigor grader: static_analysis_delta and NA-by-design metrics (design phase3-graders, section Rigor, GR-CODE c5).

- The D1 fixtures are the frozen tasks/D1/workspace in a temporary git repo that reproduces the archive's commits
  (d1_cell from the correctness tests). Fast tests use a fake dotnet; tests running real dotnet are @pytest.mark.slow.
- Every grade asserts the archive's bytes did not move (F9).
"""

from __future__ import annotations

import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT, gate_runs_root
from test_grade_correctness import BROKEN, d1_cell, done, git, tree_digest

from harness_bench import config, plan, views
from harness_bench.archive import make_writable
from harness_bench.grade import CellInput, Score, rigor, runner
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


def fake_dotnet(monkeypatch, *results) -> list[list[str]]:
    """procs.run answers `results` in order for dotnet commands; returns the dotnet argv seen."""
    seen, queue = [], list(results)
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            seen.append(list(argv))
            return queue.pop(0) if len(queue) > 1 else queue[0]
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    return seen


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
    folder, cell = d1_cell(tmp_path, {})
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            cwd = Path(kwargs.get("cwd", ""))
            if cwd.name == "pre-turn" and len(argv) > 1 and argv[1] == "build":
                return done(1, "error CS1002: ; expected")
            if argv[1:] == ["--version"]:
                return done(0, "10.0.303")
            return done(0, "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
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
def test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim(tmp_path, monkeypatch, metric, reason):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(0, "10.0.303"), done(0, ""))
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(metric) == (None, reason)


# --- shared NA reasons ---------------------------------------------------------------------------------------------


def test_static_analysis_delta_no_working_copy_is_na(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    shutil.rmtree(folder / "ws", onexc=make_writable)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "no working copy in the archive")


def test_static_analysis_delta_no_builder_commit_is_na(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    git(folder / "ws", "commit", "-q", "--amend", "-m", f"D1 base ({D1_VERSION[:11]})")
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "pre-turn commit not found in the working copy")


def test_static_analysis_delta_timeout_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(None, timed_out=True))
    got = grade_d1(tmp_path, folder, cell, timeout=60)
    assert got.get(METRIC) == (None, "HB-GRD-002 grading step timeout after 60 s")


def test_static_analysis_delta_restore_failure_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(0, "10.0.303"), done(1, r"C:\p\a.csproj : error NU1101: Unable to find package [x]"))
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "infrastructure failure before build: restore")


def test_static_analysis_delta_sdk_failure_is_na(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(1, "bad sdk"))
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "infrastructure failure before build: sdk")


# --- fast unit tests for static_analysis_delta branches -------------------------------------------------------------


def test_cell_build_failure_is_na_workspace_does_not_build(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(0, "10.0.303"), done(1, "error CS1002: ; expected"))
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "workspace does not build")


def test_static_analysis_delta_positive(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            cwd = Path(kwargs.get("cwd", ""))
            if argv[1:] == ["--version"]:
                return done(0, "10.0.303")
            if cwd.name == "cell":
                return done(0, "src/AiDe.Core/Projections/Foo.cs(10,5): warning CS0168: The variable 'unused' is declared but never used\n")
            return done(0, "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (1, None)


def test_static_analysis_delta_can_be_negative(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    from harness_bench import procs
    real_run = procs.run

    def run(argv, *args, **kwargs):
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            cwd = Path(kwargs.get("cwd", ""))
            if argv[1:] == ["--version"]:
                return done(0, "10.0.303")
            if cwd.name == "pre-turn":
                return done(0, "src/AiDe.Core/Projections/Foo.cs(10,5): warning CS0168: The variable 'unused' is declared but never used\n")
            return done(0, "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (-1, None)


def test_warnings_accumulated_across_all_projects(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    from harness_bench import procs
    real_run = procs.run
    seen_builds = 0

    def run(argv, *args, **kwargs):
        nonlocal seen_builds
        executable = Path(argv[0]).name.lower() if argv else ""
        if executable in ("dotnet", "dotnet.exe"):
            cwd = Path(kwargs.get("cwd", ""))
            if argv[1:] == ["--version"]:
                return done(0, "10.0.303")
            if cwd.name == "cell":
                seen_builds += 1
                if seen_builds == 1:
                    return done(0, "src/AiDe.Core/Projections/A.cs(10): warning CS0168: unused\nsrc/AiDe.Core/Projections/B.cs(20): warning CS0219: unused\n")
                if seen_builds == 2:
                    return done(0, "src/AiDe.Core/Projections/B.cs(20): warning CS0219: unused\nsrc/AiDe.Core/Projections/C.cs(30): warning CS0168: unused\n")
            return done(0, "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (3, None)


def test_no_csproj_in_working_copy_is_na_workspace_does_not_build(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    for p in (folder / "ws").rglob("*.csproj"):
        p.unlink()
    git(folder / "ws", "add", "-A")
    git(folder / "ws", "commit", "-q", "-m", "delete all csproj")
    got = grade_d1(tmp_path, folder, cell)
    assert got.get(METRIC) == (None, "workspace does not build")


def test_treat_warnings_as_errors_flag_in_build_flags():
    assert "-p:TreatWarningsAsErrors=false" in rigor.BUILD_FLAGS


def test_rigor_is_registered_in_runner_graders():
    assert runner.GRADERS["rigor"] is rigor.grade_cell


def test_parse_warnings_extracts_file_line_code(tmp_path):
    tree = tmp_path / "ws"
    tree.mkdir()
    (tree / "A.cs").write_text("", encoding="utf-8")
    output = (
        f"{tree / 'A.cs'}(12,34): warning CS0168: variable unused\n"
        f"{tree / 'A.cs'}(56): warning CS0219: assigned unused\n"
        "outside.cs: warning CS8600: converting null\n"
        "invalid line without warning format\n"
    )
    warnings = rigor.parse_warnings(output, tree)
    assert ("A.cs", 12, "CS0168") in warnings
    assert ("A.cs", 56, "CS0219") in warnings
    assert ("outside.cs", 0, "CS8600") in warnings


def test_rigor_evidence_log_written_and_clean_exit(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(0, "10.0.303"), done(0, ""))
    inp = rigor_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "rigor")
    out = rigor.grade_cell(inp)
    assert out[METRIC].evidence == "grading/g/c1/rigor/rigor.log"
    log = tmp_path / "run" / "grading" / "g" / "c1" / "rigor" / "rigor.log"
    assert log.is_file()
    assert "static_analysis_delta: 0" in log.read_text(encoding="utf-8")


def test_rigor_filters_metrics_when_requested(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, {})
    fake_dotnet(monkeypatch, done(0, "10.0.303"), done(0, ""))
    inp = rigor_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "rigor")
    inp_subset = CellInput(
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
        metrics={"verification_before_done": {}},
        allow_model_calls=inp.allow_model_calls,
        extraction=inp.extraction,
        prices=inp.prices,
    )
    out = rigor.grade_cell(inp_subset)
    assert list(out.keys()) == ["verification_before_done"]


def test_rigor_is_in_grader_build():
    assert Path(rigor.__file__).resolve() in {p.resolve() for p in Path(runner.__file__).parent.glob("*.py")}


# --- the gate run row15-d1-1, read-only (HB_GATE_RUNS) ---------------------------------------------------------------

GATE_RUNS = Path(os.environ.get("HB_GATE_RUNS") or gate_runs_root())
D1_GATE = {  # cp = copilot-sol, cx = codex-sol, cc = cc-opus; on/off = the pack
    "2535962f830d7718": (0, None),  # cx off
    "35af195cfe821dca": (0, None),  # cc on
    "3ff04431d3b5ac27": (0, None),  # cx on
    "4a6250261f80ded4": (0, None),  # cp on
    "c3d40fa1377ba0dc": (0, None),  # cc off
    "caa8ca38b1a929a8": (0, None),  # cp off
}


@pytest.mark.slow
def test_the_d1_gate_cells_static_analysis_delta_and_archive_unchanged(tmp_path):
    run = GATE_RUNS / "row15-d1-1"
    if not (run / "plan.json").is_file():
        pytest.skip("gate run row15-d1-1 is not on this host (set HB_GATE_RUNS to the runs folder)")
    attempts = {e["cell_id"]: e["archive_attempt"] for e in views.rows(run, "events") if e["kind"] == "cell.archived"}
    cells = {c["cell_id"]: c for c in plan.load_confirmed(run)["cells"]}
    got = {}
    for cid, attempt in sorted(attempts.items()):
        folder = run / "archive" / cid / f"attempt-{attempt}"
        before = tree_digest(folder)
        out = rigor.grade_cell(rigor_input(tmp_path / "run", folder, cells[cid], tmp_path / "run" / "grading" / cid / "rigor"))
        got[cid] = encode(out[METRIC])
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
    assert got == D1_GATE


