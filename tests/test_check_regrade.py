"""tools/check_regrade.py, the wave-3 byte-identity gate (design docs/design/phase3-graders.md, "The byte-identity gate").

The gate run is a committed X1 mini-run (it has a 0.3 pass), copied and graded for real under a released catalog label.
Red first: a dead pass B, a value moved by pass B, a moved 0.3 byte and an all-NA pass each fail the gate (TA 1, TA 4).
"""

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
from archived_runs import ROOT, make_root

from harness_bench import config, views
from harness_bench.errors import BenchError
from harness_bench.grade import Score, runner

_spec = importlib.util.spec_from_file_location("check_regrade", ROOT / "tools" / "check_regrade.py")
check_regrade = importlib.util.module_from_spec(_spec)
sys.modules["check_regrade"] = check_regrade  # dataclasses resolve annotations through the module
_spec.loader.exec_module(check_regrade)

MINI_RUN = Path(__file__).parent / "fixtures" / "ledger" / "heads" / "run"
JUDGE_NOTE = "judge half not exercised: not proven"


@pytest.fixture
def gate_run(tmp_path):
    """(root, run_dir, baseline, expected): the 0.3 baseline and the expected counts are measured on this fixture."""
    root = make_root(tmp_path)  # catalog label 0.4: a released version, as at the gate
    run_dir = tmp_path / "runs" / "heads"
    shutil.copytree(MINI_RUN, run_dir)
    baseline = {"runs": {"heads": {"export_sha256": hashlib.sha256(views.export(views.load(run_dir, "0.3"))).hexdigest()}}}
    calibration = tmp_path / "calibration" / "heads"
    shutil.copytree(MINI_RUN, calibration)
    runner.run_pass(calibration, root)
    view = views.load(calibration, "0.4")
    counts = {m: sum(1 for c in view.cells if m in c.scores and c.scores[m].value is not None) for m in view.cells[0].scores}
    assert (counts["pass_at_1"], counts["partial_credit"], counts["cost_usd"]) == (2, 2, 0)  # a: 1, b: 0; no price entry
    return root, run_dir, baseline, {"counts": counts}


def run_gate(gate_run, grade=None, **over):
    root, run_dir, baseline, expected = gate_run
    args = {"baseline": baseline, "frozen_hash": runner.catalog_hash(root), "expected": expected, "version": "0.4", **over}
    return check_regrade.gate(run_dir, grade or (lambda d: runner.run_pass(d, root).grading_id), **args)


def second_call(root, then):
    """A grade function whose first call is a real pass and whose second call is `then(run_dir)`."""
    calls = []

    def grade(run_dir):
        calls.append(run_dir)
        return runner.run_pass(run_dir, root).grading_id if len(calls) == 1 else then(run_dir)

    return grade


def test_two_real_equal_passes_pass_the_gate_and_the_judge_half_is_not_claimed(gate_run):
    report = run_gate(gate_run)
    assert (report.failures, report.notes) == ([], [JUDGE_NOTE])
    assert len(views.completed_passes(gate_run[1])) == 3  # the 0.3 pass, A and B: both gate passes are real


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
    e03 = gate_run[2]["runs"]["heads"]["export_sha256"]
    report = run_gate(gate_run, baseline={"runs": {"heads": {"export_sha256": "0" * 64}}})
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
