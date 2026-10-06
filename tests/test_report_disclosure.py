"""R-76 c2 and R-77: the report header discloses the gate allowance, and the D1 red baseline is
derived per run from the run's own Stryker cells. Every D1 mutation_score carries the cell's
initial_failing_tests. Synthetic run dirs only; no file under runs/.
"""

import inspect
import re
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import config, egress, views
from harness_bench.report import cli_table, html

# egress must be imported before report.html: egress reads html.SECRET_SHAPES while html is still loading.
_ = egress.CLASSES

ALLOWANCE = (
    "row15-d1-1 criterion 7 - 2 verify errors allowed "
    "(R-76, GATE-RUN-A; ws/.git/index of 35af..., c3d4...; not read by any grader)"
)
# R-77 item 3, verbatim, beside the derivation.
ASSUME = (
    "assume: at least one Stryker cell in the run added no red test; confirmed by the TRX diff of "
    "Conditions 4; if false, the flag under-reports by the smallest added count, never over-reports."
)
FLAKE_BAND = 1


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
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", runs.group(0), re.DOTALL).group(1)
    index = headers.index(header)
    # R3: a Runs row now carries `id="cell-<id>"` (the cell card's anchor); tolerate any `<tr>` attributes.
    return [re.findall(r"<td[^>]*>(.*?)</td>", row)[index] for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body)]


def _cli(view: views.RunView, run_dir: Path, root: Path) -> str:
    kwargs = {"run_dir": run_dir, "root": root} if "root" in inspect.signature(cli_table.render).parameters else {}
    out, code = cli_table.render(view, True, **kwargs)
    assert code == 0
    return out


def _cell(cell_id: str, task: str, *, score: Decimal | None = Decimal("0.8095"), evidence: str | None = None,
          reason: str | None = None) -> views.CellView:
    na = views.Measure(None, "not graded")
    scores = {"pass_at_1": views.Measure(Decimal(1), None)}
    if score is not None or reason is not None:
        scores["mutation_score"] = views.Measure(score, reason)
    return views.CellView(
        cell_id=cell_id, task=task, rep=None, label=f"{task}.c.pack-off.{cell_id}", combo="c", pack="off", harness="copilot",
        model="gpt-6-sol", outcome="completed", cause=None, code=None, validity="valid", validity_code=None,
        wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na, tokens=None, tokens_reason="not graded",
        scores=scores, evidence={"mutation_score": evidence} if evidence else {})


def _view_of(cells: list[views.CellView], tasks: dict[str, str]) -> views.RunView:
    plan = {"cells": [{"cell_id": c, "task": t, "harness": "copilot"} for c, t in tasks.items()], "builds": {}}
    return views.RunView("synth", plan, True, "grade-1", "0.4", cells)


def _view(task: str, evidence: str = "grading/grade-1/a/mutation.log") -> views.RunView:
    return _view_of([_cell("a", task, evidence=evidence)], {"a": task})


def _write_counts(run_dir: Path, counts: list[int | str | None]) -> tuple[views.RunView, list[str]]:
    """One D1 cell per count. An int is a Stryker cell; \"not recorded\" has no line; None is NA."""
    cells = []
    tasks = {}
    for i, count in enumerate(counts):
        cell_id = chr(ord("a") + i)
        tasks[cell_id] = "D1"
        evidence = f"grading/grade-1/{cell_id}/mutation.log"
        if count is None:
            cells.append(_cell(cell_id, "D1", score=None, reason="no tests written", evidence=evidence))
            body = None
        else:
            cells.append(_cell(cell_id, "D1", evidence=evidence))
            body = "mutation_score: 0.8095\n" if count == "absent-line" else f"initial_failing_tests: {count}\n"
        if body is not None:
            log = run_dir / evidence
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(body, encoding="utf-8")
    if not run_dir.is_dir():
        run_dir.mkdir()
    return _view_of(cells, tasks), [c.label for c in cells]


def _stale_task_constant(root: Path) -> None:
    """A leftover per-task file with numbers other than the cells'. No reader may consult it."""
    bench = root / "bench"
    bench.mkdir(parents=True, exist_ok=True)
    (bench / "task-baselines.yaml").write_text(
        "schema: bench-task-baselines/1\n"
        "tasks:\n"
        "  D1:\n"
        "    initial_failing_tests:\n"
        "      low: 74\n"
        "      high: 75\n"
        "      flake_band: 1\n"
        "      source: synthetic leftover\n"
        "      note: \"vendored subset; AiDe.sln and docs/ absent\"\n",
        encoding="utf-8")


def _surfaces(view: views.RunView, run_dir: Path, root: Path) -> tuple[str, str]:
    return html.render(view, True, run_dir, root=root), _cli(view, run_dir, root)


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


def test_no_d1_cell_omits_the_baseline_row(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    view = _view("X1")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc, out = _surfaces(view, run_dir, root)
    assert _fact(doc, "D1 baseline red tests") is None
    assert "D1 baseline red tests" not in out
    assert _column(doc, "mutation_score") is None


def _derived(low: int, high: int, n: int) -> str:
    text = f"{low}-{high} over {n} cells (derived from this run, R-77)"
    if high - low > FLAKE_BAND:
        text += f" - baseline unstable within run (spread {high - low})"
    return text


@pytest.mark.parametrize(("counts", "header", "flags"), [
    ([69, 69, 69, 71], _derived(69, 71, 4), {3: "red tests added"}),
    ([69, 70, 71], _derived(69, 71, 3), {1: "0.8095 (70)", 2: "red tests added"}),
    ([69], "not derived (1 cell)", {0: "0.8095 (69) - not checked"}),
    ([74, 74, 74, 74, 74], _derived(74, 74, 5), {}),
])
def test_d1_baseline_is_derived_from_this_runs_stryker_cells(tmp_path, counts, header, flags):
    root = tmp_path / "root"
    root.mkdir()
    run_dir = tmp_path / "run"
    view, labels = _write_counts(run_dir, counts)
    doc, out = _surfaces(view, run_dir, root)
    assert _fact(doc, "D1 baseline red tests") == header
    assert f"D1 baseline red tests: {header}" in out
    column = _column(doc, "mutation_score")
    assert column is not None and len(column) == len(counts)
    for i, count in enumerate(counts):
        shown = flags.get(i, f"0.8095 ({count})")
        assert column[i] == shown
        assert f"{labels[i]}: mutation_score {shown}" in out
    if "red tests added" not in flags.values():
        assert "red tests added" not in doc
        assert "red tests added" not in out
    if "baseline unstable" not in header:
        assert "baseline unstable" not in doc
        assert "baseline unstable" not in out


def test_a_na_cell_is_excluded_from_the_derived_baseline(tmp_path):
    """A cell whose mutation_score has no value is not a Stryker cell (R-77)."""
    root = tmp_path / "root"
    root.mkdir()
    run_dir = tmp_path / "run"
    view, _ = _write_counts(run_dir, [69, 69, None])
    doc, out = _surfaces(view, run_dir, root)
    header = _derived(69, 69, 2)
    assert _fact(doc, "D1 baseline red tests") == header
    assert f"D1 baseline red tests: {header}" in out
    assert "baseline unstable" not in header
    column = _column(doc, "mutation_score")
    assert column[0] == "0.8095 (69)"
    assert column[1] == "0.8095 (69)"
    assert column[2].startswith("NA (")


def test_a_stored_task_baseline_does_not_change_the_derived_row(tmp_path):
    root = tmp_path / "root"
    _stale_task_constant(root)
    run_dir = tmp_path / "run"
    view, labels = _write_counts(run_dir, [69, 69, 69, 71])
    doc, out = _surfaces(view, run_dir, root)
    header = _derived(69, 71, 4)
    assert _fact(doc, "D1 baseline red tests") == header
    assert f"D1 baseline red tests: {header}" in out
    assert "74-75" not in doc
    assert "74-75" not in out
    column = _column(doc, "mutation_score")
    assert column == ["0.8095 (69)", "0.8095 (69)", "0.8095 (69)", "red tests added"]
    assert f"{labels[3]}: mutation_score red tests added" in out


def test_the_r77_assume_sits_beside_the_derivation():
    text = (config.repo_root() / "src" / "harness_bench" / "report" / "__init__.py").read_text(encoding="utf-8")
    assert ASSUME in text
