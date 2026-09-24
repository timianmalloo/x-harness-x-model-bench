"""The mutation checker counts a kill only when a named test fails (Test Architect review, 2026-09-24).

A collection error, a timeout, or a failure of some other test is not evidence that the guard is tested.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("mutate_check", Path(__file__).resolve().parents[1] / "tools" / "mutate_check.py")
mutate_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mutate_check)

NAMED = ["tests/test_engine.py::test_parallelism_is_never_exceeded"]


@pytest.mark.parametrize(("returncode", "output", "expected"), [
    (1, "FAILED tests/test_engine.py::test_parallelism_is_never_exceeded - assert 3 <= 2\n1 failed", "killed"),
    (1, "FAILED tests/test_engine.py::test_other_thing - boom\n1 failed", "survived"),  # the wrong test failed
    (2, "ERROR tests/test_engine.py - SyntaxError\n1 error", "error"),  # collection error: not a kill
    (0, "1 passed", "survived"),
    (None, "", "timeout"),  # a hang is not a kill
])
def test_only_a_named_failure_is_a_kill(returncode, output, expected):
    assert mutate_check.verdict(returncode, output, NAMED) == expected


def test_a_named_parametrized_test_matches_its_cases():
    output = "FAILED tests/test_grade.py::test_parse[stderr6-None] - assert\n"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse_other"]) == "survived"


def test_a_named_file_matches_any_test_in_it():
    output = "FAILED tests/test_engine.py::test_parallelism_is_never_exceeded - x\n"
    assert mutate_check.verdict(1, output, ["tests/test_engine.py"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_views.py"]) == "survived"


def test_a_same_size_mutation_leaves_no_stale_bytecode(tmp_path, monkeypatch):
    """TOOL-A (found by T10): a mutant compiled to .pyc, restored in the same mtime second with the same size, is
    still what `import` loads, so the next run tests the mutant while `git status` is clean. The race is made
    deterministic here: the restored source is given the mtime recorded in any .pyc the run left behind."""
    (tmp_path / "m.py").write_bytes(b"X = 30.0\n")  # LF, as the repo's sources are: the mutant then has the same size
    (tmp_path / "test_m.py").write_bytes(b"import m\n\n\ndef test_x():\n    assert m.X == 30.0\n")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps([{"name": "cap", "file": "m.py", "find": "X = 30.0", "replace": "X = 60.0",
                                 "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)  # an ambient value would hide a revert of the fix
    assert mutate_check.main([str(spec)]) == 0  # the mutation is killed
    for pyc in (tmp_path / "__pycache__").glob("m.*.pyc"):
        recorded = int.from_bytes(pyc.read_bytes()[8:12], "little")  # PEP 552 header: source mtime at compile time
        os.utime(tmp_path / "m.py", (recorded, recorded))
    loaded = subprocess.run([sys.executable, "-c", "import m; print(m.X)"], cwd=tmp_path, capture_output=True, text=True,
                            timeout=60, check=True)
    assert loaded.stdout.strip() == "30.0"
