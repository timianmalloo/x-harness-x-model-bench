"""R-75 c4/c6 and R-76 c2: the report header discloses the gate allowance and the D1 red baseline,
and every D1 mutation_score carries the cell's initial_failing_tests. Synthetic run dirs only.
"""

import inspect
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from harness_bench import config, egress, views
from harness_bench.report import cli_table, html

# egress must be imported before report.html: egress reads html.SECRET_SHAPES while html is still loading.
_ = egress.CLASSES

ALLOWANCE = (
    "row15-d1-1 criterion 7 - 2 verify errors allowed "
    "(R-76, GATE-RUN-A; ws/.git/index of 35af..., c3d4...; not read by any grader)"
)
BASELINE = "74-75 (vendored subset; AiDe.sln and docs/ absent)"
NOTE = "vendored subset; AiDe.sln and docs/ absent"


def _fact(doc: str, name: str) -> str | None:
    match = re.search(rf"<dt>{re.escape(name)}</dt><dd>(.*?)</dd>", doc)
    return match.group(1) if match else None


def _column(doc: str, header: str) -> list[str] | None:
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL)
    if runs is None:
        return None
    headers = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', runs.group(0))
    if header not in headers:
        return None
    body = re.search(r"<tbody>(.*?)</tbody>", runs.group(0), re.DOTALL).group(1)
    index = headers.index(header)
    return [re.findall(r"<td[^>]*>(.*?)</td>", row)[index] for row in re.findall(r"<tr>(.*?)</tr>", body)]


def _cli(view: views.RunView, run_dir: Path, root: Path) -> str:
    kwargs = {"run_dir": run_dir, "root": root} if "root" in inspect.signature(cli_table.render).parameters else {}
    out, code = cli_table.render(view, True, **kwargs)
    assert code == 0
    return out


def _view(task: str, evidence: str = "grading/grade-1/a/mutation.log") -> views.RunView:
    na = views.Measure(None, "not graded")
    cell = views.CellView(
        cell_id="a", label=f"{task}.c.pack-off.r1", combo="c", pack="off", harness="copilot", model="gpt-6-sol",
        outcome="completed", cause=None, code=None, validity="valid", validity_code=None, wall_ms=na, model_ms=na,
        tool_ms=na, idle_ms=na, tokens=None, tokens_reason="not graded",
        scores={"mutation_score": views.Measure(Decimal("0.8095"), None), "pass_at_1": views.Measure(Decimal(1), None)},
        evidence={"mutation_score": evidence})
    plan = {"cells": [{"cell_id": "a", "task": task, "harness": "copilot"}], "builds": {}}
    return views.RunView("synth", plan, True, "grade-1", "0.4", [cell])


def _baseline(root: Path, low: int, high: int, note: str, flake: int = 1) -> None:
    bench = root / "bench"
    bench.mkdir(parents=True, exist_ok=True)
    (bench / "task-baselines.yaml").write_text(
        "schema: bench-task-baselines/1\n"
        "tasks:\n"
        "  D1:\n"
        "    initial_failing_tests:\n"
        f"      low: {low}\n"
        f"      high: {high}\n"
        f"      flake_band: {flake}\n"
        "      source: synthetic\n"
        f"      note: \"{note}\"\n",
        encoding="utf-8")


def test_task_baselines_records_the_d1_red_baseline():
    path = config.repo_root() / "bench" / "task-baselines.yaml"
    assert path.is_file()
    band = yaml.safe_load(path.read_text(encoding="utf-8"))["tasks"]["D1"]["initial_failing_tests"]
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["schema"] == "bench-task-baselines/1"
    assert (band["low"], band["high"], band["flake_band"]) == (74, 75, 1)
    assert band["source"] == "row15-d1-1, Leader 2026-09-25/26 (R-75 c4)"
    assert band["note"] == NOTE


def test_gate_allowance_quotes_the_committed_allowance(tmp_path):
    root = config.repo_root()
    view = _view("X1")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc = html.render(view, True, run_dir, root=root)
    assert _fact(doc, "Gate allowance") == ALLOWANCE
    assert f"Gate allowance: {ALLOWANCE}" in _cli(view, run_dir, root)


@pytest.mark.parametrize("kind", ["absent", "empty", "no-entries"])
def test_gate_allowance_is_none_when_there_is_no_allowance(tmp_path, kind):
    root = tmp_path / "root"
    (root / "bench").mkdir(parents=True)
    path = root / "bench" / "regrade-allowed-findings.yaml"
    if kind == "empty":
        path.write_text("", encoding="utf-8")
    elif kind == "no-entries":
        path.write_text("schema: bench-regrade-allowed-findings/1\nfindings: []\n", encoding="utf-8")
    view = _view("X1")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc = html.render(view, True, run_dir, root=root)
    assert _fact(doc, "Gate allowance") == "none"
    assert "verify errors allowed" not in doc
    out = _cli(view, run_dir, root)
    assert "Gate allowance: none" in out
    assert "verify errors allowed" not in out


@pytest.mark.parametrize(("task", "low", "high", "note", "expected"), [
    ("D1", 74, 75, NOTE, BASELINE),
    ("X1", 74, 75, NOTE, None),
    ("D1", 10, 12, "other note", "10-12 (other note)"),
])
def test_d1_baseline_row_comes_from_task_baselines_and_only_for_a_d1_cell(tmp_path, task, low, high, note, expected):
    root = tmp_path / "root"
    _baseline(root, low, high, note)
    view = _view(task)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc = html.render(view, True, run_dir, root=root)
    out = _cli(view, run_dir, root)
    assert _fact(doc, "D1 baseline red tests") == expected
    if expected is None:
        assert "D1 baseline red tests" not in out
        assert _column(doc, "mutation_score") is None
    else:
        assert f"D1 baseline red tests: {expected}" in out


@pytest.mark.parametrize(("count", "shown"), [
    ("74", "0.8095 (74)"),
    ("76", "0.8095 (76)"),
    ("77", "red tests added"),
    ("absent-log", "0.8095 (not recorded)"),
    ("absent-line", "0.8095 (not recorded)"),
])
def test_d1_mutation_score_carries_its_initial_failing_tests(tmp_path, count, shown):
    root = tmp_path / "root"
    _baseline(root, 74, 75, NOTE)
    run_dir = tmp_path / "run"
    evidence = "grading/grade-1/a/mutation.log"
    if count != "absent-log":
        log = run_dir / evidence
        log.parent.mkdir(parents=True)
        body = "mutation_score: 0.8095\n" if count == "absent-line" else f"initial_failing_tests: {count}\n"
        log.write_text(body, encoding="utf-8")
    else:
        run_dir.mkdir()
    view = _view("D1", evidence)
    doc = html.render(view, True, run_dir, root=root)
    assert _column(doc, "mutation_score") == [shown]
    out = _cli(view, run_dir, root)
    assert f"{view.cells[0].label}: mutation_score {shown}" in out
    if shown == "red tests added":
        assert "0.8095" not in out.split("mutation_score", 1)[1]
        assert "77" not in _column(doc, "mutation_score")[0]
