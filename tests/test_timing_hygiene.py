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
_POLL = "bounded poll on a condition (event-driven); the deadline only names the failure"
_HUNG = "a deliberately hung child killed by its own timeout; load lengthens the wait and cannot flip the outcome"
_UPPER = "asserts an elapsed upper bound well above the work's idle time; load-sensitive in principle, none measured (follow-up)"
_UNAUDITED = "real sleep or fake delay whose ordering against other real work is not proven load-safe; none measured failing (TIME-B follow-up)"

TIMING_ALLOWED: Mapping[str, str] = {
    "test_driver.py::_poll_until": _POLL,
    "test_engine.py::_wait": _POLL,
    "test_engine.py::release_when_stopped": _POLL,
    "test_engine.py::test_stop_ends_stubborn_trees_within_30s": _POLL,
    "test_engine.py::test_engine_crash_leaves_no_cell_running": _POLL,
    "test_oslock.py::test_lock_is_released_when_the_holder_dies": _POLL,
    "test_procs.py::test_engine_crash_kills_every_descendant": _POLL,
    "test_procs_posix.py::test_engine_crash_kills_every_descendant": _POLL,
    "test_procs.py::test_run_with_an_unconfirmed_kill_raises_nothing_and_leaks_nothing": _POLL,
    "test_gateway_headless.py::test_t_gw_09_a_timed_out_call_is_unavailable_even_when_it_left_a_record": _HUNG,
    "test_gateway_headless.py::test_t_gw_10_the_credential_is_gone_after_a_timeout_and_after_an_exception_past_the_copy": _HUNG,
    "test_grade_correctness.py::test_rewriting_a_file_with_the_same_size_changes_the_snapshot_through_mtime_ns":
        "a 10 ms sleep so the rewrite's mtime differs; a longer wait only helps",
    "test_engine.py::test_budget_kill_is_timed_out_and_recorded_only_after_the_tree_is_gone": _UPPER,
    "test_engine.py::test_a_drain_with_nothing_queued_returns_at_its_deadline": _UPPER,
    "test_engine.py::test_a_run_with_nothing_left_to_launch_ends_without_an_idle_wait": _UPPER,
    "test_ng_tasks.py::test_ng1_the_default_clock_test_does_not_depend_on_wall_time": _UPPER,
    "test_procs.py::test_run_times_out_and_kills_the_tree": _UPPER,
    "test_engine.py::test_the_engine_loop_passes_every_fifth_of_a_second_and_never_spins": _UPPER,
    "test_engine.py::test_no_launch_after_a_stop_while_another_cell_still_runs": _UNAUDITED,
    "test_engine.py::test_parallelism_is_never_exceeded": _UNAUDITED,
    "test_engine.py::test_after_the_ledger_breaks_no_worker_blocks_forever": _UNAUDITED,
    "test_engine.py::test_record_waits_through_a_full_inbox_and_a_slow_drain": _UNAUDITED,
    "test_engine.py::test_the_heartbeat_keeps_beating_after_a_failed_beat": _UNAUDITED,
    "test_engine.py::test_keep_awake_is_held_through_a_stop": _UNAUDITED,
    "test_engine.py::test_a_worker_still_running_when_the_run_fails_is_refused_at_once_not_left_waiting": _UNAUDITED,
    "test_engine.py::test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running": _UNAUDITED,
    "test_engine.py::test_blocked_cell_default_continues_after_the_timeout": _UNAUDITED,
    "test_engine.py::test_no_decision_after_a_launch_stop": _UNAUDITED,
    "test_engine.py::test_the_run_waits_for_an_open_decision": _UNAUDITED,
    "test_engine.py::grade": _UNAUDITED,
    "test_oslock.py::test_heartbeat_advances_the_mtime": _UNAUDITED,
}


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

def _unnamed(allowed: Mapping[str, str]) -> list[str]:
    return sorted(scan_tree() - set(allowed))


def _stale(allowed: Mapping[str, str]) -> list[str]:
    return sorted(set(allowed) - scan_tree())


def test_every_real_time_dependence_in_the_tests_is_named_and_justified():
    unnamed = _unnamed(TIMING_ALLOWED)
    assert not unnamed, f"real-sleep or wall-clock assertions not in TIMING_ALLOWED (inject a clock or wait on an event): {unnamed}"


def test_no_allowlist_entry_is_stale():
    stale = _stale(TIMING_ALLOWED)
    assert not stale, f"TIMING_ALLOWED entries that no longer match a hit: {stale}"


def test_every_allowlist_entry_has_a_reason():
    assert all(reason.strip() for reason in TIMING_ALLOWED.values())


def test_mutant_removing_an_entry_is_caught():
    victim = next(iter(TIMING_ALLOWED))
    assert _unnamed({k: v for k, v in TIMING_ALLOWED.items() if k != victim}) == [victim]


def test_mutant_a_stale_entry_is_caught():
    assert _stale({**TIMING_ALLOWED, "test_gone.py::test_gone": "x"}) == ["test_gone.py::test_gone"]
