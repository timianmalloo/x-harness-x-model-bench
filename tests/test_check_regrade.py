"""tools/check_regrade.py, the wave-3 byte-identity gate (design docs/design/phase3-graders.md, "The byte-identity gate").

The gate run is a committed X1 mini-run (it has a 0.3 pass), copied and graded for real under a released catalog label.
Red first: a dead pass B, a value moved by pass B, a moved 0.3 byte and an all-NA pass each fail the gate (TA 1, TA 4).
"""

import hashlib
import importlib.util
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest
import yaml
from archived_runs import ROOT, gate_runs_root, make_root

from harness_bench import config, plan, views
from harness_bench.errors import BenchError
from harness_bench.grade import Score, _changes, runner

_spec = importlib.util.spec_from_file_location("check_regrade", ROOT / "tools" / "check_regrade.py")
check_regrade = importlib.util.module_from_spec(_spec)
sys.modules["check_regrade"] = check_regrade  # dataclasses resolve annotations through the module
_spec.loader.exec_module(check_regrade)

MINI_RUN = Path(__file__).parent / "fixtures" / "ledger" / "heads" / "run"
JUDGE_NOTE = "judge half not exercised: not proven"


@pytest.fixture
def gate_run(tmp_path):
    """(root, run_dir, baseline, expected): the 0.3 baseline and the expected counts are measured on this fixture."""
    root = make_root(tmp_path)  # a released version (the .dev suffix stripped), as at the gate
    run_dir = tmp_path / "runs" / "heads"
    shutil.copytree(MINI_RUN, run_dir)
    baseline = {check_regrade.BASELINE_KEY: {"heads": {"export_sha256": hashlib.sha256(views.export(views.load(run_dir, "0.3"))).hexdigest()}}}
    calibration = tmp_path / "calibration" / "heads"
    shutil.copytree(MINI_RUN, calibration)
    runner.run_pass(calibration, root)
    view = views.load(calibration, config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    counts = {m: sum(1 for c in view.cells if m in c.scores and c.scores[m].value is not None) for m in view.cells[0].scores}
    assert (counts["pass_at_1"], counts["partial_credit"], counts["cost_usd"]) == (2, 2, 0)  # a: 1, b: 0; no price entry
    return root, run_dir, baseline, {"counts": counts}


def run_gate(gate_run, grade=None, **over):
    root, run_dir, baseline, expected = gate_run
    release = config.load_yaml(root / "bench" / "metrics.yaml")["version"]
    args = {"baseline": baseline, "frozen_hash": runner.catalog_hash(root), "expected": expected, "version": release, **over}
    return check_regrade.gate(run_dir, grade or (lambda d: runner.run_pass(d, root).grading_id), **args)


def second_call(root, then):
    """A grade function whose first call is a real pass and whose second call is `then(run_dir)`."""
    calls = []

    def grade(run_dir):
        calls.append(run_dir)
        return runner.run_pass(run_dir, root).grading_id if len(calls) == 1 else then(run_dir)

    return grade


def test_two_real_equal_passes_pass_the_gate_and_the_judge_half_is_not_claimed(gate_run):
    before = views.completed_passes(gate_run[1])
    report = run_gate(gate_run)
    assert (report.failures, report.notes) == ([], [JUDGE_NOTE])
    assert len(views.completed_passes(gate_run[1]) - before) == 2  # A and B: both gate passes are real and completed


def test_a_dead_pass_b_fails_the_gate(gate_run, monkeypatch):
    root = gate_run[0]

    def incomplete(self):
        raise BenchError("HB-GRD-004", "pass B killed before grading.completed")

    def killed(run_dir):
        monkeypatch.setattr(runner._Pass, "_check_complete", incomplete)
        return runner.run_pass(run_dir, root).grading_id

    report = run_gate(gate_run, second_call(root, killed))
    assert report.failures == ["criterion 1: pass B did not complete (BenchError)",
                               f"criterion 4: pass B catalog_hash not recorded != frozen {runner.catalog_hash(root)}"]


def test_a_value_moved_by_pass_b_fails_the_gate(gate_run, monkeypatch):
    root = gate_run[0]

    def moved(run_dir):
        real = runner.GRADERS["correctness"]
        monkeypatch.setitem(runner.GRADERS, "correctness", lambda inp: {**real(inp), "partial_credit": Score(0, None)})
        return runner.run_pass(run_dir, root).grading_id

    assert run_gate(gate_run, second_call(root, moved)).failures == ["criterion 2: pass B's export differs from pass A's"]


def test_a_moved_0_3_byte_fails_the_gate(gate_run):
    e03 = gate_run[2][check_regrade.BASELINE_KEY]["heads"]["export_sha256"]
    report = run_gate(gate_run, baseline={check_regrade.BASELINE_KEY: {"heads": {"export_sha256": "0" * 64}}})
    assert report.failures == [f"criterion 3: the 0.3 export {e03} before, {e03} after, baseline {'0' * 64}"]


def test_an_all_na_pass_fails_the_gate(gate_run, monkeypatch):
    for name in ("correctness", "cost"):
        monkeypatch.setitem(runner.GRADERS, name, lambda inp: {m: Score(None, "not measured") for m in inp.metrics})
    counts = gate_run[3]["counts"]
    report = run_gate(gate_run)
    assert report.failures == [  # both passes agree, so only non-vacuity sees it
        "criterion 5: partial_credit of cell a is (None, 'not measured'), expected ('1.0000', None)",
        "criterion 5: pass_at_1 of cell a is (None, 'not measured'), expected (1, None)",
        "criterion 5: partial_credit of cell b is (None, 'not measured'), expected ('0.0000', None)",
        "criterion 5: pass_at_1 of cell b is (None, 'not measured'), expected (0, None)",
        *[f"criterion 5: {m} non-NA count 0 != expected {n}" for m, n in sorted(counts.items()) if n]]


def test_a_run_with_no_expected_counts_or_no_frozen_catalog_fails_the_gate(gate_run):
    report = run_gate(gate_run, expected=None, frozen_hash=None)
    assert report.failures == ["criterion 4: pass A catalog_hash " + runner.catalog_hash(gate_run[0]) + " != frozen none (P1)",
                               "criterion 4: pass B catalog_hash " + runner.catalog_hash(gate_run[0]) + " != frozen none (P1)",
                               f"criterion 5: no expected counts for this run in {check_regrade.EXPECTED}"]


def test_the_committed_expected_counts_name_both_gate_runs_and_every_applicable_metric():
    runs = config.load_yaml(ROOT / check_regrade.EXPECTED)["runs"]
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    for run, task, cells in (("row15-d1-1", "D1", 6), ("a1-capture-1", "A1", 3)):
        graders = config.load_yaml(ROOT / "tasks" / task / "task.yaml")["graders"]
        metrics = {m for ms in runner.applicable(catalog, graders).values() for m in ms}
        assert set(runs[run]["counts"]) == metrics, run
        assert all(n is None or 0 <= n <= cells for n in runs[run]["counts"].values()), run


# --- R-76: criterion 7's pinned allowance of exact (run, code, cell, path) verify errors ---------------------------

_CELL = "35af195cfe821dca"
_PATH = "ws/.git/index"
_CODE = "HB-LED-005"


def _finding_message(cell: str, path: str) -> str:
    return f"{cell}: archived file {path} does not match its archive_files row"


def _allowance_entry(run: str, cell: str = _CELL, path: str = _PATH, code: str = _CODE) -> dict:
    return {"run": run, "code": code, "cell": cell, "path": path, "ruling": "R-76", "class": "GATE-RUN-A",
            "recorded": "2026-09-25",
            "register": "docs/lessons/defect-classes.md GATE-RUN-A: .git/index of cells 35af… and c3d4… (2026-09-25)"}


def _write_allowance(directory: Path, entries: list[dict]) -> Path:
    path = directory / "regrade-allowed-findings.yaml"
    path.write_text(yaml.safe_dump({"findings": entries}, sort_keys=False), encoding="utf-8")
    return path


def _verify_returns(monkeypatch, findings):
    monkeypatch.setattr(views, "verify", lambda _run_dir: findings)


def test_an_allowed_verify_tuple_is_a_note_not_a_failure(gate_run, tmp_path, monkeypatch):
    run = gate_run[1].name
    message = _finding_message(_CELL, _PATH)
    monkeypatch.setattr(check_regrade, "ALLOWANCE", _write_allowance(tmp_path, [_allowance_entry(run)]), raising=False)
    _verify_returns(monkeypatch, [views.Finding(_CODE, "error", message)])
    report = run_gate(gate_run)
    note = f"verify error allowed (R-76): {_CODE} {message}"
    assert report.failures == []
    assert report.notes == [JUDGE_NOTE, note]


@pytest.mark.parametrize("part", ["run", "cell", "path"])
def test_the_same_tuple_with_a_different_run_cell_or_path_is_a_failure(gate_run, tmp_path, monkeypatch, part):
    entry_run, cell, path = gate_run[1].name, _CELL, _PATH
    if part == "run":
        entry_run = entry_run + "-other"
    elif part == "cell":
        cell = "0000000000000000"
    else:
        path = "ws/bin/dropped.dll"
    message = _finding_message(cell, path)
    entry = _allowance_entry(entry_run)
    monkeypatch.setattr(check_regrade, "ALLOWANCE", _write_allowance(tmp_path, [entry]), raising=False)
    _verify_returns(monkeypatch, [views.Finding(_CODE, "error", message)])
    report = run_gate(gate_run)
    assert report.failures == [f"criterion 7: {_CODE} {message}"]
    assert report.notes == [JUDGE_NOTE]


def test_an_allowance_entry_outside_build_output_fails_at_load(gate_run, tmp_path, monkeypatch):
    entry = _allowance_entry(gate_run[1].name, path="ws/src/Program.cs")
    monkeypatch.setattr(check_regrade, "ALLOWANCE", _write_allowance(tmp_path, [entry]), raising=False)
    report = run_gate(gate_run)
    assert report.failures == ["criterion 7: allowance names a graded path"]


def test_an_empty_allowance_passes(gate_run, tmp_path, monkeypatch):
    path = _write_allowance(tmp_path, [])
    monkeypatch.setattr(check_regrade, "ALLOWANCE", path, raising=False)
    loaded = getattr(check_regrade, "load_allowance", lambda _p: None)(path)
    assert loaded == []
    report = run_gate(gate_run)
    assert (report.failures, report.notes) == ([], [JUDGE_NOTE])


def _file_hashes(tree: Path) -> dict[str, str]:
    return {p.relative_to(tree).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in tree.rglob("*") if p.is_file()}


def test_a_junk_git_index_leaves_the_pre_turn_commit_and_file_hash_map_unchanged(tmp_path):
    """R-76 item 4. Copy one row15-d1-1 D1 cell's ws/; never write under the gate run."""
    run = gate_runs_root() / "row15-d1-1"
    if not (run / "plan.json").is_file():
        pytest.skip("gate run row15-d1-1 is not on this host (set HB_GATE_RUNS to the runs folder)")
    cell_id = "c3d40fa1377ba0dc"
    cell = next(c for c in plan.load_confirmed(run)["cells"] if c["cell_id"] == cell_id)
    attempt = next(e["archive_attempt"] for e in views.rows(run, "events")
                   if e["kind"] == "cell.archived" and e["cell_id"] == cell_id)
    src = run / "archive" / cell_id / f"attempt-{attempt}" / "ws"
    source_index = (src / ".git" / "index").read_bytes()
    clean, junk = tmp_path / "clean", tmp_path / "junk"
    shutil.copytree(src, clean, symlinks=True)
    shutil.copytree(src, junk, symlinks=True)
    index = junk / ".git" / "index"
    os.chmod(index, stat.S_IWRITE)
    index.write_bytes(b"junk")
    commit = _changes.pre_turn_commit(clean, cell, 120)
    assert _changes.pre_turn_commit(junk, cell, 120) == commit
    assert commit

    def hashes(ws: Path, dest: Path) -> dict[str, str]:
        with _changes.pre_turn_tree(ws, commit, dest, 120) as tree:
            return _file_hashes(tree)

    assert hashes(junk, tmp_path / "junk-tree") == hashes(clean, tmp_path / "clean-tree")
    assert (src / ".git" / "index").read_bytes() == source_index
