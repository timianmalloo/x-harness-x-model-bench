"""One heavy test run on this machine at a time (SUITE-LOCK).

Why: on 2026-10-03/04 parallel agents ran four or five full suites and mutation runs at once, in sibling
worktrees. Each suite spawns thousands of job-wrapped processes. Three times Windows stopped activating
apps (AppModel-Runtime 0x80070005, a terminal failing with 0xc0000142) and only a reboot recovered it.

A heavy run takes this lock first and waits while another process holds it:
  - a pytest run with xdist workers (`-n N`, `-n auto`),
  - a pytest run over the whole suite or a directory,
  - a `tools/mutate_check.py` run.
A light run (named files or node ids, no workers) never takes it, so a red/green check is not queued
behind a seven-minute suite.

The lock is `oslock.RunLock`: an OS byte-range lock, so a killed holder releases it and there is no stale
lock to clean up. It lives outside every worktree so the sibling worktrees share it (HB_SUITE_LOCK
overrides the path). Whoever holds it, or decided not to take it, sets HB_SUITE_LOCK_PARENT=1 in its
environment: a child run (mutate_check's pytest, a test that runs pytest, an xdist worker) inherits it
and never waits on its own parent.
"""

import json
import os
import time
from collections.abc import Callable, MutableMapping, Sequence
from pathlib import Path

from harness_bench import oslock
from harness_bench.errors import BenchError

PATH_ENV = "HB_SUITE_LOCK"
PARENT_ENV = "HB_SUITE_LOCK_PARENT"
POLL_SECONDS = 5.0


def lock_path(env: MutableMapping[str, str]) -> Path:
    return Path(env[PATH_ENV]) if env.get(PATH_ENV) else Path.home() / ".harness-bench" / "suite.lock"


def is_heavy(workers: object, collect_only: bool, args: Sequence[str], from_testpaths: bool, invocation_dir: Path) -> bool:
    """True when a pytest run must take the lock. `workers` is xdist's numprocesses option (None without xdist)."""
    if collect_only:
        return False
    if workers not in (None, 0, "0"):
        return True
    if from_testpaths:
        return True
    return any((invocation_dir / arg.split("::")[0]).is_dir() for arg in args)


def _holder(path: Path) -> str:
    try:
        return path.with_suffix(".owner").read_text(encoding="utf-8").strip()
    except OSError:
        return "holder not recorded"


def acquire(
    env: MutableMapping[str, str],
    what: str,
    on_wait: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
) -> oslock.RunLock | None:
    """Wait for the lock and take it. None when a parent run already decided (PARENT_ENV is set).

    `what` names this run in the owner file a waiter prints. `on_wait` gets one line, once, when the lock is held.
    """
    if env.get(PARENT_ENV) == "1":
        return None
    path = lock_path(env)
    told = False
    while True:
        try:
            lock = oslock.RunLock.acquire(path)
        except BenchError:
            # not a hold: RunLock refused the path itself (not a regular file); waiting would never end
            if path.is_symlink() or not path.is_file() or not oslock.is_held(path):
                raise
            if not told:
                on_wait(f"waiting for the suite lock {path} (one heavy test run at a time); held by: {_holder(path)}")
                told = True
            sleep(POLL_SECONDS)
            continue
        owner = {"pid": os.getpid(), "cwd": os.getcwd(), "run": what, "since": time.strftime("%Y-%m-%d %H:%M:%S")}
        path.with_suffix(".owner").write_text(json.dumps(owner) + "\n", encoding="utf-8")
        env[PARENT_ENV] = "1"
        return lock


def release(lock: oslock.RunLock | None, env: MutableMapping[str, str]) -> None:
    if lock is not None:
        lock.release()
        env.pop(PARENT_ENV, None)
