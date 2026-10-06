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

    # Case 3b: some gate tests passed and one skipped (e.g. HB_GATE_RUNS unset for a run): a skip proved nothing
    def fake_run_partly_skipped(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="5 passed, 1 skipped in 9.0s", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_partly_skipped)
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


# ---------------------------------------------------------------- the stamped tier (`-m stamped`)

def _copy_stamped_extras(root: Path) -> None:
    for rel in gate_stamp.STAMPED_EXTRA_INPUTS:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)


def test_stamped_digest_moves_with_each_extra_input_and_the_gate_digest_does_not(tmp_path):
    root = _setup_tmp_root(tmp_path)
    _copy_stamped_extras(root)
    base, gate_base = gate_stamp.compute_stamped_digest(root), gate_stamp.compute_digest(root)
    for rel in gate_stamp.STAMPED_EXTRA_INPUTS:
        path = root / rel
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\n# byte change\n", encoding="utf-8")
        assert gate_stamp.compute_stamped_digest(root) != base, rel
        assert gate_stamp.compute_digest(root) == gate_base, rel  # the 77-minute gate ring is not retriggered
        path.write_text(original, encoding="utf-8")
    grader = root / "src" / "harness_bench" / "grade" / "architecture.py"
    grader.write_text(grader.read_text(encoding="utf-8") + "\n# byte change\n", encoding="utf-8")
    assert gate_stamp.compute_stamped_digest(root) != base  # every gate input is a stamped input too


def test_stamped_stale_names_why_the_stamped_ring_must_run(tmp_path):
    root = _setup_tmp_root(tmp_path)
    _copy_stamped_extras(root)
    now = gate_stamp.datetime.datetime(2026, 10, 6, 12, tzinfo=gate_stamp.datetime.UTC)
    target = gate_stamp.stamped_stamp_path(root)
    assert gate_stamp.stamped_stale(root, now) == "no readable stamped stamp"
    gate_stamp.write_stamp(target, "0" * 64, now.isoformat())
    assert gate_stamp.stamped_stale(root, now) == "stamped inputs changed"
    gate_stamp.write_stamp(target, gate_stamp.compute_stamped_digest(root), now.isoformat())
    assert gate_stamp.stamped_stale(root, now) is None
    assert gate_stamp.stamped_stale(root, now + gate_stamp.datetime.timedelta(hours=23)) is None
    assert gate_stamp.stamped_stale(root, now + gate_stamp.datetime.timedelta(hours=25)) == "daily full run due"


def test_renew_stamped_runs_the_stamped_marker_with_dotnet_required_and_refuses_a_skip(tmp_path, monkeypatch):
    root = _setup_tmp_root(tmp_path)
    _copy_stamped_extras(root)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["env"] = cmd, kwargs["env"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=seen["out"], stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    seen["out"] = "20 passed, 1 skipped in 9.0s"
    assert gate_stamp.renew(root, stamped=True) == 1
    assert not gate_stamp.stamped_stamp_path(root).exists()
    seen["out"] = "21 passed in 9.0s"
    assert gate_stamp.renew(root, stamped=True) == 0
    assert seen["cmd"][-4:] == ["-m", "stamped", "-n", "4"] and seen["env"]["HB_REQUIRE_DOTNET"] == "1"
    assert gate_stamp.stamped_stale(root) is None


# The control: a `stamped` test is skipped when no input moved, so every harness_bench module its file imports must
# be an input of the stamped digest or a named glue module. A new import fails here until someone decides which.
# Glue = imported to build cells, plans and paths; it is not graded behaviour. Its own fast tests run at every join.
STAMPED_GLUE = {
    "harness_bench.archive": "make_writable, to clean up grading copies",
    "harness_bench.config": "loads the plan config that d1_cell builds on",
    "harness_bench.plan": "task_version_hash and cell identity for d1_cell (D1's hash is a digest input)",
    "harness_bench.gitsafe": "git helper for the fixtures' scratch repos",
    "harness_bench.host": "host lookups the dotnet oracle tests read",
    "harness_bench.procs": "process-tree helpers (leftover-process checks)",
    "harness_bench.profiles": "CELL_ENV, the pinned cell environment constant",
    "harness_bench.views": "cell and token projections the fixtures read",
}


def _stamped_test_files() -> list[Path]:
    files = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if "mark.stamped" in path.read_text(encoding="utf-8"):
            files.append(path)
    return files


def _harness_bench_imports(path: Path) -> set[str]:
    import ast

    modules = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "harness_bench":
            modules |= {f"{node.module}.{a.name}" if node.module == "harness_bench" else node.module for a in node.names}
        elif isinstance(node, ast.Import):
            modules |= {a.name for a in node.names if a.name.split(".")[0] == "harness_bench"}
    return modules


def test_every_module_a_stamped_test_file_imports_is_a_stamped_input_or_named_glue():
    digested = {rel.removeprefix("src/").removesuffix(".py").replace("/", ".") for rel in gate_stamp.STAMPED_EXTRA_INPUTS}
    files = _stamped_test_files()
    assert files, "no stamped test file found: the marker was removed or renamed"
    for path in files:
        for module in sorted(_harness_bench_imports(path)):
            covered = module in digested or module in STAMPED_GLUE or module.startswith("harness_bench.grade")
            assert covered, f"{path.name} imports {module}: add it to STAMPED_EXTRA_INPUTS or name it in STAMPED_GLUE"
