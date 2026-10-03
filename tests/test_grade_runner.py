"""The per-cell grader input and the dispatch by the task's graders (design docs/design/phase3-graders.md, CORE s1).

Each pass test builds a real archived run with `archived_runs` and grades it for real (the X1 hidden tests run). A
grader is replaced only through `runner.GRADERS`, the one seam the design names. The expected metric sets are the
catalog's `kind: score` metrics of each grader, written out here so a catalog edit is visible in this file.
"""

import hashlib
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from archived_runs import (
    CODEX_MODEL,
    GOOD,
    ROOT,
    gate_runs_root,
    make_root,
    make_run,
    pass_rows,
)

from harness_bench import config, ledger, plan, procs, views
from harness_bench.errors import BenchError
from harness_bench.grade import Score, clarify, process, runner

CORRECTNESS = {"pass_at_1", "partial_credit", "build_and_suite_clean", "regression_count", "behavioural_equivalence"}
COST = {"cost_usd", "tokens_per_minute", "output_tokens_per_turn", "cache_hit_ratio", "cache_write_amplification",
        "context_growth", "compactions"}
PROCESS = {"completion_without_intervention", "stuck_loops", "recovery_rate", "tool_error_rate", "planning_ratio",
           "time_to_first_green"}
SCORED_0_3 = {"pass_at_1", "partial_credit", "cost_usd"}  # the metrics the registered graders returned in slice 1
C2 = {"regression_count": (None, "task has no public tests"), "behavioural_equivalence": (None, "not a D-task")}  # X1
BUILT = SCORED_0_3 | {"build_and_suite_clean"} | COST | set(C2)  # GR-CODE c1 build_and_suite_clean; COST phase 2 COST; c2 the two NA rows


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


# --- grading-copy-outside-repo (ADR-0013 Amendment 2): cells_root threaded in, checked before any grader runs -------

def test_run_pass_refuses_a_cells_root_under_a_project_file(root, tmp_path):
    """HB-GRD-006: a `cells_root` (so `cells_root/grading`) sitting under a project's own pyproject.toml/.python-
    version is refused before any grader builds a working copy under it (the ORCL-B guard)."""
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    bad_project = tmp_path / "bad-project"
    (bad_project / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (bad_project / "pyproject.toml").write_text("[project]\nname = \"bad\"\n", encoding="utf-8")
    with pytest.raises(BenchError) as e:
        runner.run_pass(run_dir, root, cells_root=bad_project / "bench-cells")
    assert e.value.code == "HB-GRD-006"


# --- dispatch by the task's graders (replaces METRICS) ------------------------------------------------------------


@pytest.mark.parametrize(("names", "expected"), [
    (["cost"], COST),
    (["correctness", "cost"], CORRECTNESS | COST),
    (["process", "correctness", "cost"], CORRECTNESS | COST | PROCESS),
])
def test_the_pass_writes_one_row_per_applicable_metric_of_the_tasks_graders(root, tmp_path, names, expected):
    set_graders(root, names)
    assert sorted(r["metric_id"] for r in graded(root, tmp_path)) == sorted(expected)


COORDINATION = {"model_map_adherence", "per_agent_attribution", "intent_log_completeness", "kg_use",
                "coordination_overhead", "parallel_efficiency", "protocol_conformance"}


def test_an_unbuilt_grader_is_na_not_built_for_each_of_its_metrics_never_0(root, tmp_path):
    # "formal" is now registered (W5-FIMPL); "coordination" (a real catalog grader with no runner.GRADERS entry)
    # stands in for a genuinely unregistered one.
    set_graders(root, ["correctness", "cost", "process", "coordination"])
    got = {r["metric_id"]: (r["value"], r["reason"]) for r in graded(root, tmp_path)}
    assert "coordination" not in runner.GRADERS  # an unregistered grader
    assert {m: got[m] for m in COORDINATION} == {m: (None, "not built") for m in COORDINATION}
    assert {m: v for m, v in got.items() if m not in BUILT | PROCESS | COORDINATION} == \
        {m: (None, "not built") for m in (CORRECTNESS | COST) - BUILT}


def test_formal_on_a_task_with_no_formal_block_is_na_never_0_or_a_crash(root, tmp_path):
    # "formal" is registered but X1 is not a scenario-7 task: every one of its six metrics is a deterministic NA,
    # never a guessed 0 and never an unregistered-grader "not built" (G5/G3; docs/design/formal-grader.md).
    set_graders(root, ["correctness", "cost", "process", "formal"])
    got = {r["metric_id"]: (r["value"], r["reason"]) for r in graded(root, tmp_path)}
    reason = "formal.tool None not in ('tla', 'lean')"
    assert {m: got[m] for m in ("formal_checks_clean", "bugs_confirmed", "bug_claim_precision",
                                "statement_integrity", "model_conformance", "model_non_vacuity")} == \
        {m: (None, reason) for m in ("formal_checks_clean", "bugs_confirmed", "bug_claim_precision",
                                     "statement_integrity", "model_conformance", "model_non_vacuity")}
    missing = (None, "per-call outcome missing on 2 of 2 calls")  # the captured Codex record: every ok is null (DR-G3)
    assert {m: got[m] for m in PROCESS} == {  # process is registered (GR-PROC p1-p3), so measured, never `not built`
        "tool_error_rate": missing, "stuck_loops": missing, "recovery_rate": missing,
        "planning_ratio": (None, "no edit-class tool call (edits through the shell are not classed)"),
        "completion_without_intervention": (None, "no cell outcome"),  # the builder's cell.outcome has no stop_reason
        "time_to_first_green": (None, "test runs not identifiable in the tool record (no command text extracted)")}
    assert (got.get("pass_at_1"), got.get("partial_credit"), got.get("build_and_suite_clean")) == \
        ((1, None), ("1.0000", None), (1, None))  # the built metrics are measured
    assert {m: got.get(m) for m in C2} == C2


def test_a_metric_a_registered_grader_does_not_return_is_na_not_built_never_0(root, tmp_path, monkeypatch):
    # every registered grader now returns all its metrics, so a stub that returns a subset reaches the branch
    set_graders(root, ["cost"])
    with_grader(monkeypatch, "cost", lambda inp: {"cost_usd": Score(None, "a stub reason")})
    got = {r["metric_id"]: (r["value"], r["reason"]) for r in graded(root, tmp_path)}
    assert got["cost_usd"] == (None, "a stub reason")
    assert {m: got[m] for m in COST - {"cost_usd"}} == {m: (None, "not built") for m in COST - {"cost_usd"}}


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


# --- GradedOncePerPass: the completeness check before grading.completed (F2, HB-GRD-004) -----------------------


def failure_code(run_dir, root) -> str | None:
    try:
        runner.run_pass(run_dir, root)
    except BenchError as exc:
        return exc.code
    return None


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra"])
def test_a_missing_duplicate_or_extra_row_fails_the_pass_before_completed(root, tmp_path, monkeypatch, fault):
    if fault == "extra":  # a grader returns a key outside its applicable metrics
        real = getattr(runner, "GRADERS", {}).get("correctness")
        with_grader(monkeypatch, "correctness", lambda inp: {**real(inp), "mutation_score": Score(None, "x")})
    else:  # the writer drops, or doubles, one (cell, metric) row
        write = runner._Pass._score

        def faulty(self, cell, attempt, metric, *rest):
            if metric != "partial_credit" or fault == "duplicate":
                write(self, cell, attempt, metric, *rest)
            if metric == "partial_credit" and fault == "duplicate":
                write(self, cell, attempt, metric, *rest)

        monkeypatch.setattr(runner._Pass, "_score", faulty)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    assert failure_code(run_dir, root) == "HB-GRD-004"
    events = [e for p in (run_dir / "events").glob("grade-*.jsonl") for e in ledger.read_segment(p)]
    assert [e["kind"] for e in events] == ["grading.started"]  # never completed, so views skip the pass
    assert views.completed_passes(run_dir) == set()


# --- duplicate grader names (D&P 2; seam V-3) ---------------------------------------------------------------------


def test_duplicate_graders_write_one_row_each(root, tmp_path):
    set_graders(root, ["correctness", "cost", "correctness"])
    assert sorted(r["metric_id"] for r in graded(root, tmp_path)) == sorted(CORRECTNESS | COST)


def test_validate_task_rejects_a_grader_listed_twice(root):
    set_graders(root, ["correctness", "cost", "cost"])
    entry = next(t for t in config.load_yaml(ROOT / "bench" / "bom.yaml")["tasks"] if t["id"] == "X1")
    p = config.Problems()
    config.validate_task(root / "tasks" / "X1", entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert p.items == ["tasks/X1: grader 'cost' is listed more than once"]


# --- the tasks freeze (R-59 c5; seam V-3) -------------------------------------------------------------------------


def frozen_root(tmp_path, frozen: str | None):
    """A root with the real bench/ and tasks/X1, and a freeze record naming X1 (None: X1's current hash)."""
    r = tmp_path / "frozen"
    shutil.copytree(ROOT / "bench", r / "bench")
    shutil.copytree(ROOT / "tasks" / "X1", r / "tasks" / "X1")
    actual = plan.task_version_hash(r / "tasks" / "X1")
    (r / "bench" / "task-freeze.yaml").write_text(yaml.safe_dump({"schema": "bench-task-freeze/1", "tasks": {"X1": frozen or actual}}),
                                                  encoding="utf-8")
    return r, actual


def test_validate_fails_a_changed_frozen_task(tmp_path):  # F7
    r, actual = frozen_root(tmp_path, "0" * 64)
    assert f"tasks/X1 changed while frozen (R-59 c5): {actual} != {'0' * 64}" in config.validate_repo(r)


def test_validate_passes_an_unchanged_frozen_task(tmp_path):
    r, _ = frozen_root(tmp_path, None)
    assert [p for p in config.validate_repo(r) if "while frozen" in p] == []


def test_the_committed_freeze_record_names_the_frozen_tasks_and_they_are_unchanged():  # L-1 (1c63c42); B1 and F1 added at their joins
    freeze = config.load_yaml(ROOT / "bench" / "task-freeze.yaml")
    assert sorted(freeze["tasks"]) == ["A1", "B1", "C1", "D1", "E6", "F1"]
    assert {t: plan.task_version_hash(ROOT / "tasks" / t) for t in freeze["tasks"]} == freeze["tasks"]


# --- the 0.3 values and exports survive the 0.4.dev dispatch (R-59 c6; design: the byte-identity gate) ------------

MINI_RUNS = Path(__file__).parent / "fixtures" / "ledger"  # two committed X1 runs graded under 0.3 (D6)
GATE_RUNS = gate_runs_root()


@pytest.mark.parametrize("name", ["c44dd2b-no-heads", "heads"])
def test_a_committed_mini_run_regrades_to_its_0_3_values_with_every_other_metric_not_built(tmp_path, name):
    root = make_root(tmp_path)
    run_dir = tmp_path / "runs" / "r1"
    shutil.copytree(MINI_RUNS / name / "run", run_dir)
    before = views.load(run_dir, "0.3")
    export_before = views.export(before)
    result = runner.run_pass(run_dir, root)
    got = {(r["cell_id"], r["metric_id"]): (r["value"], r["reason"]) for r in pass_rows(run_dir, "scores", result.grading_id)}
    was = {(c.cell_id, m): (s.value, s.reason) for c in before.cells for m, s in c.scores.items()}
    assert was == {("a", "pass_at_1"): (1, None), ("a", "partial_credit"): ("1.0000", None),
                   ("b", "pass_at_1"): (0, None), ("b", "partial_credit"): ("0.0000", None),
                   ("a", "cost_usd"): (None, f"no price list entry for {CODEX_MODEL}"),
                   ("b", "cost_usd"): (None, f"no price list entry for {CODEX_MODEL}")}
    assert {k: v for k, v in got.items() if k[1] in SCORED_0_3} == was  # pass_at_1, partial_credit, cost_usd equal 0.3's
    assert {k: v for k, v in got.items() if k[1] == "build_and_suite_clean"} == \
        {("a", "build_and_suite_clean"): (1, None), ("b", "build_and_suite_clean"): (1, None)}  # both compile
    assert {k: v for k, v in got.items() if k[1] in C2} == {(c, m): v for c in "ab" for m, v in C2.items()}
    assert {k: v for k, v in got.items() if k[1] not in BUILT} == \
        {(c, m): (None, "not built") for c in "ab" for m in (CORRECTNESS | COST) - BUILT}
    assert views.export(views.load(run_dir, "0.3")) == export_before  # the 0.3 pass is still the 0.3 export
    released = config.load_yaml(ROOT / "bench" / "metrics.yaml")["version"].removesuffix(".dev")
    assert views.load(run_dir).catalog_version == config.load_yaml(root / "bench" / "metrics.yaml")["version"] == released  # make_root releases the source catalog's .dev version


@pytest.mark.parametrize("name", sorted(config.load_yaml(ROOT / "bench" / "regrade-baseline-0.3.yaml")["runs_export_3"]))
def test_the_gate_runs_0_3_exports_equal_the_committed_baseline(name):  # P5, L-1: read-only; absent runs skip (CI)
    entry = config.load_yaml(ROOT / "bench" / "regrade-baseline-0.3.yaml")["runs_export_3"][name]  # export shape 3 (R-86: no extraction_id)
    if not (GATE_RUNS / name / "plan.json").is_file():
        pytest.skip(f"gate run {name} is not on this host (set HB_GATE_RUNS to the runs folder)")
    view = views.load(GATE_RUNS / name, "0.3")
    data = views.export(view)
    assert (view.grading_id, len(data), hashlib.sha256(data).hexdigest()) == (entry["pass"], entry["bytes"], entry["export_sha256"])


# --- catalog_hash and tool_versions on grading.started (R-59 c1, c4; design: Catalog-version rule 2-3) -------------


def test_grading_started_carries_the_catalog_hash_and_the_measured_tool_versions(root, tmp_path, monkeypatch):
    rubric = root / "bench" / "rubrics" / "adr_quality.md"
    rubric.parent.mkdir()
    rubric.write_bytes(b"# rubric\r\n")
    metrics = (root / "bench" / "metrics.yaml").read_bytes().replace(b"\r\n", b"\n")
    expected = hashlib.sha256(b"metrics.yaml\0" + metrics + b"\0" + b"rubrics/adr_quality.md\0# rubric\n\0").hexdigest()
    empty = tmp_path / "empty-packages"
    empty.mkdir()
    monkeypatch.setenv("NUGET_PACKAGES", str(empty))  # this pass has no cached stryker
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    started = pass_rows(run_dir, "events", runner.run_pass(run_dir, root).grading_id)[0]
    assert (started["kind"], started["catalog_hash"]) == ("grading.started", expected)
    assert started["tool_versions"] == {"python": sys.version.split()[0], "dotnet-stryker": "not recorded"}  # X1 is not dotnet


def test_the_catalog_hash_moves_with_a_weight_or_a_rubric_and_is_plan_tree_hash(root):
    before = runner.catalog_hash(root)
    assert before == plan.tree_hash(root / "bench", [root / "bench" / "metrics.yaml"])  # no bench/rubrics/ yet
    (root / "bench" / "rubrics").mkdir()
    (root / "bench" / "rubrics" / "adr_quality.md").write_text("# rubric\n", encoding="utf-8")
    with_rubric = runner.catalog_hash(root)
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: score, weight: 1, scale: 6", "kind: score, weight: 2, scale: 6"),
                    encoding="utf-8")
    assert len({before, with_rubric, runner.catalog_hash(root)}) == 3


def dotnet_root(tmp_path) -> Path:
    """A root with one dotnet task (T1) and one unittest task (T2)."""
    r = tmp_path / "tools-root"
    for task, kind in (("T1", "dotnet"), ("T2", "unittest")):
        (r / "tasks" / task / "workspace").mkdir(parents=True)
        (r / "tasks" / task / "task.yaml").write_text(yaml.safe_dump({"oracle": {"runner": kind}}), encoding="utf-8")
    return r


def test_tool_versions_measure_dotnet_once_per_dotnet_task_in_its_workspace_with_a_30_s_timeout(tmp_path, monkeypatch):
    r = dotnet_root(tmp_path)
    calls = []

    def fake_run(argv, cwd, env, timeout):
        calls.append((Path(argv[0]).stem.lower(), argv[1:], Path(cwd), timeout))
        return procs.Completed(0, "10.0.100\n", "", False, False, 0.1)

    monkeypatch.setattr(runner.tools.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(runner.tools.procs, "run", fake_run)
    empty = tmp_path / "empty-packages"
    empty.mkdir()
    monkeypatch.setenv("NUGET_PACKAGES", str(empty))  # no cached stryker, so that pin is not probed
    plan_ = {"cells": [{"task": "T2"}, {"task": "T1"}, {"task": "T1"}]}
    assert runner.tool_versions(r, plan_) == {"python": sys.version.split()[0], "dotnet[T1]": "10.0.100",
                                              "dotnet-stryker": "not recorded"}
    assert calls == [("dotnet", ["--version"], r / "tasks" / "T1" / "workspace", 30)]  # global.json there picks the SDK


@pytest.mark.parametrize("fault", ["absent", "exit 1", "timeout", "empty", "oserror"])
def test_a_tool_that_cannot_be_measured_is_not_recorded_never_empty_or_guessed(tmp_path, monkeypatch, fault):
    r = dotnet_root(tmp_path)

    def fake_run(argv, cwd, env, timeout):
        if fault == "oserror":
            raise FileNotFoundError(argv[0])
        return procs.Completed(1 if fault == "exit 1" else 0,  # a timed-out tree is killed: its code proves nothing
                               "" if fault == "empty" else "10.0.100\n", "", fault == "timeout", False, 30.0)

    monkeypatch.setattr(runner.tools.shutil, "which", lambda name: None if fault == "absent" else f"C:/fake/{name}.exe")
    monkeypatch.setattr(runner.tools.procs, "run", fake_run)
    assert runner.tool_versions(r, {"cells": [{"task": "T1"}]})["dotnet[T1]"] == "not recorded"


def test_a_pinned_tool_is_measured_by_its_pinned_command(tmp_path, monkeypatch):
    r = dotnet_root(tmp_path)
    monkeypatch.setattr(runner, "PINNED_TOOLS", {"dotnet-stryker": ["dotnet", "stryker-version-probe"]})
    monkeypatch.setattr(runner.tools.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(runner.tools.procs, "run", lambda argv, cwd, env, timeout: procs.Completed(
        0, "banner\n4.5.0\n" if argv[1:] == ["stryker-version-probe"] else "10.0.100\n", "", False, False, 0.1))
    assert runner.tool_versions(r, {"cells": [{"task": "T2"}]}) == {"python": sys.version.split()[0], "dotnet-stryker": "4.5.0"}


def stryker_cache(packages: Path) -> Path:
    """A dotnet-stryker/4.16.0 layout. The DLL is an empty stand-in; the version comes from the fake probe."""
    dll = packages / "dotnet-stryker" / "4.16.0" / "tools" / "net8.0" / "any" / "Stryker.CLI.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"")
    return dll


def test_tool_versions_records_dotnet_stryker_from_the_nuget_cache_product_version(tmp_path, monkeypatch):
    """R-59 c4, spike c6a: ProductVersion of the cached Stryker.CLI.dll, once, 30 s. An absent package is not recorded.
    `--version` is not the tool version on 4.16.0, so a probe that uses it is not accepted."""
    r = dotnet_root(tmp_path)
    plan_ = {"cells": [{"task": "T2"}]}  # not a dotnet task: the only probe is stryker
    expected = "4.16.0+f9109e24c615a7030a3b33e5532c665c974e4ec5"
    calls = []
    accepted: list[Path] = []

    def fake_run(argv, cwd, env, timeout):
        calls.append((list(argv), timeout))
        script = argv[-1] if argv else ""
        hit = (accepted and ".ProductVersion" in script and "GetVersionInfo" in script
               and str(accepted[0]) in script and "--version" not in script)
        return procs.Completed(0, (expected if hit else "guessed") + "\n", "", False, False, 0.1)

    monkeypatch.setattr(runner.tools.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(runner.tools.procs, "run", fake_run)

    packages = tmp_path / "packages"
    accepted.append(stryker_cache(packages))
    monkeypatch.setenv("NUGET_PACKAGES", str(packages))
    assert runner.tool_versions(r, plan_) == {"python": sys.version.split()[0], "dotnet-stryker": expected}
    exe, *args = calls[0][0]
    assert (Path(exe).stem.lower(), args[:2], calls[0][1]) == ("powershell", ["-NoProfile", "-Command"], 30)
    assert str(accepted[0]) in args[2] and args[2].endswith("ProductVersion")

    calls.clear()
    accepted.clear()
    empty = tmp_path / "empty-packages"
    empty.mkdir()
    monkeypatch.setenv("NUGET_PACKAGES", str(empty))
    assert runner.tool_versions(r, plan_) == {"python": sys.version.split()[0], "dotnet-stryker": "not recorded"}
    assert calls == []  # absent: not probed, not empty, not guessed

    home = tmp_path / "home"
    calls.clear()
    accepted.append(stryker_cache(home / ".nuget" / "packages"))
    monkeypatch.delenv("NUGET_PACKAGES", raising=False)
    monkeypatch.setenv("USERPROFILE", str(home))
    assert runner.tool_versions(r, plan_)["dotnet-stryker"] == expected
    assert str(accepted[0]) in calls[0][0][-1] and calls[0][1] == 30


# --- process and clarify are registered (GR-PROC p1-p3, GR-CLAR l1 built on main) -------------------------------


def test_process_and_clarify_are_registered_graders():
    assert (runner.GRADERS.get("process"), runner.GRADERS.get("clarify")) == (process.grade_cell, clarify.grade_cell)


# --- byte identity: a re-grade of a committed mini-run gives the same export (US-26; design: the gate) ------------


@pytest.mark.parametrize("name", ["c44dd2b-no-heads", "heads"])
def test_grading_a_committed_mini_run_twice_gives_byte_equal_exports(tmp_path, name):
    """Pass B writes no extraction (runner.py: extractions are written once), so its view reads the tool and model
    rows back from the segments pass A sealed: equal exports prove the rebuild from sealed segments."""
    root = make_root(tmp_path)
    run_dir = tmp_path / "runs" / "r1"
    shutil.copytree(MINI_RUNS / name / "run", run_dir)
    version = config.load_yaml(root / "bench" / "metrics.yaml")["version"]
    a = runner.run_pass(run_dir, root).grading_id
    view_a = views.load(run_dir, version)
    b = runner.run_pass(run_dir, root).grading_id
    view_b = views.load(run_dir, version)
    assert (view_a.grading_id, view_b.grading_id, a != b) == (a, b, True)
    assert pass_rows(run_dir, "tool_calls", b) == [] and pass_rows(run_dir, "model_calls", b) == []  # B extracted nothing
    assert {c.cell_id: c.scores["pass_at_1"].value for c in view_b.cells} == {"a": 1, "b": 0}  # not a vacuous export
    assert views.export(view_a) == views.export(view_b)


# --- applicable(): the `property:` narrowing and the owner rule (R-90 c1, R-95; design eval-catalog-0-7 4.2; T-R1..T-R6) ---

PROPERTY_ROWS = {"property_check_pass", "exploit_probes_blocked"}  # the security task's narrowed set (catalog 0.7.dev)


def set_task(root, **keys) -> None:
    path = root / "tasks" / "X1" / "task.yaml"
    task = yaml.safe_load(path.read_text(encoding="utf-8"))
    task.update(keys)
    path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")


def stub_returning(metrics_of_grader: dict[str, Score]):
    def grade(inp):
        return {m: metrics_of_grader.get(m, Score(1)) for m in inp.metrics}
    return grade


def catalog_of(root) -> dict:
    return config.load_yaml(root / "bench" / "metrics.yaml")


def test_a_security_task_graded_by_property_writes_exactly_two_property_rows_and_the_pass_completes(root, tmp_path, monkeypatch):  # T-R1
    set_task(root, graders=["correctness", "property"], property={"name": "security"})
    with_grader(monkeypatch, "property", stub_returning({"exploit_probes_blocked": Score(Decimal("1"))}))
    rows = graded(root, tmp_path)
    assert {r["metric_id"] for r in rows} - CORRECTNESS == PROPERTY_ROWS
    assert sorted(r["metric_id"] for r in rows).count("property_check_pass") == 1


def test_applicable_with_no_prop_keeps_only_untagged_metrics(root, tmp_path, monkeypatch):  # T-R2
    catalog = catalog_of(root)
    assert set(runner.applicable(catalog, ["property"])["property"]) == {"property_check_pass"}  # prop=None: untagged only
    assert set(runner.applicable(catalog, ["property"], "security")["property"]) == PROPERTY_ROWS
    set_task(root, graders=["correctness", "property"], property={"name": "security"})
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    set_task(root, title="changed after the plan")  # the task version no longer matches the plan: the fallback
    with_grader(monkeypatch, "property", stub_returning({}))
    got = {r["metric_id"]: r["reason"] for r in pass_rows(run_dir, "scores", runner.run_pass(run_dir, root).grading_id)}
    assert got["property_check_pass"] == runner.TASK_CHANGED
    assert not {"exploit_probes_blocked", "fault_suite_pass", "rework_ratio", "size_vs_reference"} & got.keys()


def test_pass_at_1_has_one_owner_when_correctness_and_formal_are_both_named(root, tmp_path, monkeypatch):  # T-R3
    catalog = catalog_of(root)
    assert [g for g, ms in runner.applicable(catalog, ["correctness", "formal"]).items() if "pass_at_1" in ms] == ["correctness"]
    assert [g for g, ms in runner.applicable(catalog, ["formal", "correctness"]).items() if "pass_at_1" in ms] == ["formal"]  # first named


def test_a_formal_only_task_gets_pass_at_1_from_formal(root, tmp_path, monkeypatch):  # T-R4
    set_task(root, graders=["formal"])
    with_grader(monkeypatch, "formal", stub_returning({"pass_at_1": Score(1)}))
    rows = graded(root, tmp_path)
    assert [r["metric_id"] for r in rows].count("pass_at_1") == 1
    assert [r["value"] for r in rows if r["metric_id"] == "pass_at_1"] == [1]


def test_the_task_changed_fallback_gives_pass_at_1_to_correctness_as_na_in_the_correctness_folder(root, tmp_path):  # T-R5
    set_task(root, graders=["formal"])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    set_task(root, title="changed after the plan")
    grading_id = runner.run_pass(run_dir, root).grading_id
    got = [r for r in pass_rows(run_dir, "scores", grading_id) if r["metric_id"] == "pass_at_1"]
    assert [(r["value"], r["reason"]) for r in got] == [(None, runner.TASK_CHANGED)]
    every = [m["grader"] for a in catalog_of(root)["areas"].values() for m in a["metrics"]]
    assert "pass_at_1" in runner.applicable(catalog_of(root), every)["correctness"]
    assert "pass_at_1" not in runner.applicable(catalog_of(root), every).get("formal", {})


def test_a_g1_shaped_task_through_a_real_pass_records_one_pass_at_1_row_and_no_hb_grd_004(root, tmp_path):  # T-R6
    set_task(root, graders=["correctness", "formal"], formal={"tool": "tla", "statements": "fixed", "statement_hash": "0" * 64})
    rows = graded(root, tmp_path)  # real run_pass, real formal.grade_cell; HB-GRD-004 would raise here
    assert [r["metric_id"] for r in rows].count("pass_at_1") == 1
    assert [r["value"] for r in rows if r["metric_id"] == "pass_at_1"] == [1]  # correctness's row, not formal's
