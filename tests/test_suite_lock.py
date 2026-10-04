"""SUITE-LOCK: one heavy test run per machine (tests/suite_lock.py).

Parallel agents ran four or five full suites at once on 2026-10-03/04 and Windows stopped activating apps three
times. A heavy run now waits for the run ahead of it; a light run and a holder's own children never wait.
"""

import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import suite_lock

from harness_bench import oslock
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]


def _env(tmp_path) -> dict[str, str]:
    return {suite_lock.PATH_ENV: str(tmp_path / "suite.lock")}


def _never_sleep(seconds):
    raise AssertionError("waited although nothing held the lock")


def test_a_second_heavy_run_waits_until_the_holder_releases(tmp_path):
    first_env, second_env = _env(tmp_path), _env(tmp_path)
    first = suite_lock.acquire(first_env, "pytest -n 4", lambda line: None, _never_sleep)
    told, slept = [], []

    def sleep(seconds):
        assert not slept, "still held after the holder released"
        slept.append(seconds)
        suite_lock.release(first, first_env)

    second = suite_lock.acquire(second_env, "mutate_check x.json", told.append, sleep)
    try:
        assert slept == [suite_lock.POLL_SECONDS]
        assert len(told) == 1 and '"run": "pytest -n 4"' in told[0], told  # the waiter names the holder
        assert second.held and second_env[suite_lock.PARENT_ENV] == "1"
    finally:
        suite_lock.release(second, second_env)
    assert not oslock.is_held(tmp_path / "suite.lock")
    assert suite_lock.PARENT_ENV not in second_env


def test_a_child_of_a_holder_never_waits(tmp_path):
    env = {**_env(tmp_path), suite_lock.PARENT_ENV: "1"}
    assert suite_lock.acquire(env, "pytest", lambda line: None, _never_sleep) is None
    assert not (tmp_path / "suite.lock").exists()


def test_a_lock_path_that_is_not_a_file_raises_instead_of_waiting(tmp_path):
    (tmp_path / "suite.lock").mkdir()
    with pytest.raises(BenchError, match="not a regular file"):
        suite_lock.acquire(_env(tmp_path), "pytest", lambda line: None, _never_sleep)


def test_the_default_lock_is_outside_every_worktree():
    assert suite_lock.lock_path({}) == Path.home() / ".harness-bench" / "suite.lock"


@pytest.mark.parametrize(("workers", "collect_only", "args", "from_testpaths", "heavy"), [
    (4, False, ["tests/test_atomic.py"], False, True),            # xdist workers
    ("auto", False, [], True, True),
    (None, False, [], True, True),                                 # the whole suite, serially
    (None, False, ["tests"], False, True),                         # a directory is a suite
    (None, False, ["tests/e2e"], False, True),
    (None, False, ["tests/test_atomic.py"], False, False),         # named files and node ids are light
    (None, False, ["tests/test_atomic.py::test_x", "tests/test_oslock.py"], False, False),
    (0, False, ["tests/test_atomic.py"], False, False),            # -n 0 runs no workers
    (4, True, [], True, False),                                    # --collect-only starts no test
])
def test_heavy_rule(workers, collect_only, args, from_testpaths, heavy):
    assert suite_lock.is_heavy(workers, collect_only, args, from_testpaths, ROOT) is heavy


def test_pytest_with_workers_waits_for_the_lock_end_to_end(tmp_path):
    """The conftest wiring: a real `pytest -n 1` waits while another process holds the lock, then runs."""
    env = _env(tmp_path)
    hold = suite_lock.acquire(env, "this test", lambda line: None, _never_sleep)
    child_env = {k: v for k, v in os.environ.items() if k != suite_lock.PARENT_ENV}
    child_env[suite_lock.PATH_ENV] = env[suite_lock.PATH_ENV]
    child = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "1",
         "tests/test_suite_lock.py::test_the_default_lock_is_outside_every_worktree"],
        cwd=ROOT, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace")
    lines: queue.Queue[str | None] = queue.Queue()

    def pump():
        for line in child.stdout:
            lines.put(line)
        lines.put(None)  # the child ended

    threading.Thread(target=pump, daemon=True).start()
    try:
        seen = []
        while not any("waiting for the suite lock" in line for line in seen):
            line = lines.get(timeout=120)
            assert line is not None, f"the child ran without waiting: {seen}"
            seen.append(line)
        assert child.poll() is None, seen  # still waiting: no test ran while the lock was held
        assert '"run": "this test"' in seen[-1]
        suite_lock.release(hold, env)
        assert child.wait(timeout=300) == 0, seen
    finally:
        suite_lock.release(hold, env)
        if child.poll() is None:
            child.kill()


def test_a_mutation_run_holds_the_lock(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("mutate_check", ROOT / "tools" / "mutate_check.py")
    mutate_check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mutate_check)
    (tmp_path / "m.py").write_bytes(b"X = 1\n")
    (tmp_path / "test_m.py").write_text("import m\n\ndef test_x():\n    assert m.X == 1\n", encoding="utf-8")
    mutations = tmp_path / "spec.json"
    mutations.write_text(json.dumps([{"name": "cap", "file": "m.py", "find": "X = 1", "replace": "X = 2",
                                      "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    lock = tmp_path / "lock" / "suite.lock"
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    monkeypatch.delenv(suite_lock.PARENT_ENV, raising=False)
    monkeypatch.setenv(suite_lock.PATH_ENV, str(lock))
    assert mutate_check.main([str(mutations)]) == 0, capsys.readouterr().out
    owner = json.loads(lock.with_suffix(".owner").read_text(encoding="utf-8"))
    assert owner["run"] == f"mutate_check {mutations}"
    assert not oslock.is_held(lock)
    assert suite_lock.PARENT_ENV not in os.environ
