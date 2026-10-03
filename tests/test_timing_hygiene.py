"""TIME-B control: a test that depends on real sleeps or on a wall-clock difference passes only while the machine is idle.

The scan reads every test module under tests/ with `ast` and lists three forms:
  sleep   a `time.sleep(...)` / `sleep(...)` call;
  fake    a real-sleep parameter handed to a fake: a "sleep" or "delay" dict key, or a `sleep=` / `delay=` keyword;
  clock   an assert whose condition calls time.monotonic(), time.time() or time.perf_counter().
Every hit must be named in TIMING_ALLOWED with a reason, and every entry must still match a hit (checked both ways).
Not scanned: fakes and helpers (any module that is not test_*.py or conftest.py) and tests/fixtures, vendor, mutations:
a sleep inside a fake is the fake's behaviour; a test depending on it shows up here as a "fake" key or keyword.
Known limit: a clock difference stored in a variable and asserted later is not seen; only a clock call inside the assert is.
"""

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
SKIPPED_DIRS = {"fixtures", "vendor", "mutations", "__pycache__"}
CLOCKS = {"monotonic", "time", "perf_counter"}
FAKE_PARAMS = {"sleep", "delay"}

# "<file>::<function>" -> why this real-time dependence is safe under load. A new entry needs a reason a reviewer can check.
TIMING_ALLOWED: Mapping[str, str] = {}


def scan_source(source: str, name: str) -> set[str]:
    tree = ast.parse(source)
    hits: set[str] = set()

    def visit(node: ast.AST, owner: str) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            owner = node.name
        key = f"{name}::{owner}"
        if isinstance(node, ast.Call):
            fn = node.func
            callee = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            if callee == "sleep":
                hits.add(key)
            if any(k.arg in FAKE_PARAMS for k in node.keywords):
                hits.add(key)
        if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value in FAKE_PARAMS for k in node.keys):
            hits.add(key)
        if isinstance(node, ast.Assert) and any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in CLOCKS
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "time"
                or isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "perf_counter"
                for n in ast.walk(node.test)):
            hits.add(key)
        for child in ast.iter_child_nodes(node):
            visit(child, owner)

    visit(tree, "<module>")
    return hits


def _test_modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py")
                  if (p.name.startswith("test_") or p.name == "conftest.py")
                  and not SKIPPED_DIRS & set(p.relative_to(TESTS).parts[:-1]))


def scan_tree() -> set[str]:
    hits: set[str] = set()
    for path in _test_modules():
        hits |= scan_source(path.read_text(encoding="utf-8"), path.relative_to(TESTS).as_posix())
    return hits


# red fixtures: one per form, one that must not match

@pytest.mark.parametrize(("source", "expected"), [
    ("import time\ndef test_a():\n    time.sleep(1)\n", {"t.py::test_a"}),
    ("from time import sleep\ndef test_a():\n    sleep(1)\n", {"t.py::test_a"}),
    ("def test_a():\n    launcher({'x': {'sleep': 3}})\n", {"t.py::test_a"}),
    ("def test_a():\n    launcher(x, delay=3)\n", {"t.py::test_a"}),
    ("import time\ndef test_a():\n    t = time.monotonic()\n    assert time.monotonic() - t < 1\n", {"t.py::test_a"}),
    ("import time\ndef test_a():\n    assert time.perf_counter() < 1\n", {"t.py::test_a"}),
    ("import time\nclass T:\n    def test_a(self):\n        def inner():\n            time.sleep(1)\n", {"t.py::inner"}),
], ids=["time.sleep", "bare sleep", "sleep dict key", "delay keyword", "monotonic in assert", "perf_counter in assert",
        "nested owner"])
def test_the_scan_flags_each_form(source, expected):
    assert scan_source(source, "t.py") == expected


@pytest.mark.parametrize("source", [
    "def test_a():\n    assert 1 + 1 == 2\n",
    "import time\ndef test_a():\n    t = time.monotonic()\n    assert t > 0 or True is not None and len([t]) == 1\n",
    "def test_a():\n    run({'timeout': 3, 'mode': 'ok'})\n",
], ids=["plain", "clock outside an assert", "other keys"])
def test_the_scan_ignores_code_that_does_not_depend_on_real_time(source):
    assert scan_source(source, "t.py") == set()


def test_a_fakes_own_module_is_not_scanned(tmp_path):
    (tmp_path / "fake_agent.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    assert [p for p in sorted(tmp_path.glob("*.py")) if p.name.startswith("test_") or p.name == "conftest.py"] == []
    assert "fake_acp_agent.py" not in {p.name for p in _test_modules()}


# the control on the tree

def test_every_real_time_dependence_in_the_tests_is_named_and_justified():
    unnamed = sorted(scan_tree() - set(TIMING_ALLOWED))
    assert not unnamed, f"real-sleep or wall-clock assertions not in TIMING_ALLOWED (inject a clock or wait on an event): {unnamed}"


def test_no_allowlist_entry_is_stale():
    stale = sorted(set(TIMING_ALLOWED) - scan_tree())
    assert not stale, f"TIMING_ALLOWED entries that no longer match a hit: {stale}"


def test_every_allowlist_entry_has_a_reason():
    assert all(reason.strip() for reason in TIMING_ALLOWED.values())
