"""The mutation checker counts a kill only when a named test fails (Test Architect review, 2026-09-24).

A collection error, a timeout, or a failure of some other test is not evidence that the guard is tested.
"""

import importlib.util
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
