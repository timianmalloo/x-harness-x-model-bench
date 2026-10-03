"""Property grader tests (design: docs/design/eval-property-grader.md, W1-F rev 3). F0: the skeleton exists."""

import importlib.util
import inspect

import harness_bench.grade as grade


def test_property_module_exists_as_docstring_only_skeleton():
    spec = importlib.util.find_spec("harness_bench.grade.property")
    assert spec is not None, "grade/property.py is missing (W0 section 7: X-G1 needs the module)"
    module = importlib.import_module("harness_bench.grade.property")
    assert inspect.getdoc(module), "the skeleton carries a docstring"
    public = [n for n in vars(module) if not n.startswith("_")]
    assert public == [], f"F0 is a docstring only; found {public}"
    assert grade.__name__ == "harness_bench.grade"
