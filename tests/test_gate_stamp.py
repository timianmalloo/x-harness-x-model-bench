"""Tests for gate stamp management, digest sensitivity, and default-ring staleness checks."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from archived_runs import ROOT

_spec = importlib.util.spec_from_file_location("gate_stamp", ROOT / "tools" / "gate_stamp.py")
gate_stamp = importlib.util.module_from_spec(_spec)
sys.modules["gate_stamp"] = gate_stamp
_spec.loader.exec_module(gate_stamp)


def test_current_grader_inputs_match_gate_stamp():
    """Fast default-ring test asserting current inputs match the committed gate stamp."""
    target = gate_stamp.stamp_path(ROOT)
    stamp = gate_stamp.read_stamp(target)
    current = gate_stamp.compute_digest(ROOT)
    if current != stamp:
        pytest.fail(
            "grader inputs changed since the gate ring last passed: "
            "run HB_GATE_RUNS=<runs> HB_REQUIRE_DOTNET=1 uv run pytest -m gate, "
            "then python tools/gate_stamp.py --renew"
        )


def _setup_tmp_root(tmp_path: Path) -> Path:
    """Copy digest input files to an isolated tmp root."""
    root = tmp_path / "repo"
    root.mkdir()

    # 1. Graders
    grade_dst = root / "src" / "harness_bench" / "grade"
    grade_dst.mkdir(parents=True)
    grade_src = ROOT / "src" / "harness_bench" / "grade"
    for p in grade_src.glob("*.py"):
        shutil.copy2(p, grade_dst / p.name)

    # 2. D1 task
    d1_dst = root / "tasks" / "D1"
    shutil.copytree(ROOT / "tasks" / "D1", d1_dst)

    # 3. Bench metrics & regrade baseline
    bench_dst = root / "bench"
    bench_dst.mkdir(parents=True)
    shutil.copy2(ROOT / "bench" / "metrics.yaml", bench_dst / "metrics.yaml")
    shutil.copy2(ROOT / "bench" / "regrade-baseline-0.3.yaml", bench_dst / "regrade-baseline-0.3.yaml")

    return root


def test_digest_moves_when_any_input_changes(tmp_path):
    """Proves that mutating 1 byte of any digest input moves the computed digest."""
    root = _setup_tmp_root(tmp_path)
    base_digest = gate_stamp.compute_digest(root)

    # Grader source change
    arch_file = root / "src" / "harness_bench" / "grade" / "architecture.py"
    original_arch = arch_file.read_text(encoding="utf-8")
    arch_file.write_text(original_arch + "\n# byte change\n", encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    arch_file.write_text(original_arch, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest

    # Task D1 change
    d1_spec = root / "tasks" / "D1" / "task.yaml"
    original_d1 = d1_spec.read_text(encoding="utf-8")
    d1_spec.write_text(original_d1 + "\n# byte change\n", encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    d1_spec.write_text(original_d1, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest

    # bench/metrics.yaml change
    metrics_file = root / "bench" / "metrics.yaml"
    original_metrics = metrics_file.read_text(encoding="utf-8")
    metrics_file.write_text(original_metrics + "\n# byte change\n", encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    metrics_file.write_text(original_metrics, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest

    # bench/regrade-baseline-0.3.yaml change
    base_file = root / "bench" / "regrade-baseline-0.3.yaml"
    original_base = base_file.read_text(encoding="utf-8")
    base_file.write_text(original_base + "\n# byte change\n", encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    base_file.write_text(original_base, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest

    # Dotnet SDK version change
    global_json = root / "tasks" / "D1" / "workspace" / "global.json"
    original_global = global_json.read_text(encoding="utf-8")
    global_json.write_text(original_global.replace("10.0.303", "10.0.304"), encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    global_json.write_text(original_global, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest

    # Stryker version change
    mutation_file = root / "src" / "harness_bench" / "grade" / "mutation.py"
    original_mut = mutation_file.read_text(encoding="utf-8")
    mutation_file.write_text(original_mut.replace('STRYKER_VERSION = "4.16.0"', 'STRYKER_VERSION = "4.16.1"'), encoding="utf-8")
    assert gate_stamp.compute_digest(root) != base_digest
    mutation_file.write_text(original_mut, encoding="utf-8")
    assert gate_stamp.compute_digest(root) == base_digest


def test_renew_refuses_when_tests_do_not_run_or_fail(tmp_path, monkeypatch):
    """tools/gate_stamp.py --renew refuses when pytest fails or no tests run."""
    root = _setup_tmp_root(tmp_path)
    stamp_file = gate_stamp.stamp_path(root)

    # Case 1: pytest exit code 5 (no tests ran)
    def fake_run_exit_5(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=5, stdout="", stderr="no tests ran")

    monkeypatch.setattr(subprocess, "run", fake_run_exit_5)
    ret = gate_stamp.renew(root)
    assert ret == 5
    assert not stamp_file.exists()

    # Case 2: pytest exit code 1 (failure)
    def fake_run_exit_1(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="1 failed", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_exit_1)
    ret = gate_stamp.renew(root)
    assert ret == 1
    assert not stamp_file.exists()

    # Case 3: pytest exit code 0 but 0 passed (e.g. all skipped)
    def fake_run_zero_passed(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="6 skipped in 0.5s", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_zero_passed)
    ret = gate_stamp.renew(root)
    assert ret == 1
    assert not stamp_file.exists()

    # Case 4: pytest exit code 0 and tests passed
    def fake_run_passed(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="6 passed in 10.0s", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_passed)
    ret = gate_stamp.renew(root)
    assert ret == 0
    assert stamp_file.exists()
    assert gate_stamp.read_stamp(stamp_file) == gate_stamp.compute_digest(root)
