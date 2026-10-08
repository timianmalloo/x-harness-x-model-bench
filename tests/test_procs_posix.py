"""POSIX process-group control (ADR-0013 Amendment 1, section 5: the macOS port): kill -> confirm,
the watchdog standing in for kill-on-close, containment. The POSIX mirror of test_procs.py.

`pytest.mark.posix` (module-level): skipped on Windows (explicit, printed reason; conftest.py), where
`os.killpg`/`os.setsid`/`pgrep` are not available. Run for real only by the macos-latest CI job -- the
only proof of this file, per the brief's own allowance for an assume: on this Windows host.
"""

import json
import os
import subprocess
import sys
import time

import pytest

from harness_bench import procs
from harness_bench.errors import Cause

pytestmark = pytest.mark.posix

# A tree: child starts a grandchild, prints the grandchild's pid, then sleeps. Identical to
# test_procs.py's TREE: the same script works unmodified on POSIX.
TREE = ("import subprocess,sys,time;"
        "g=subprocess.Popen([sys.executable,'-c','import time;time.sleep(600)']);"
        "print(g.pid,flush=True);time.sleep(600)")

OWNER = """
import json, sys, time
sys.path.insert(0, {src!r})
from harness_bench import procs
cell = procs.spawn([sys.executable, "-c", {tree!r}], cwd=None, env=None)
gc = int(cell.proc.stdout.readline())
print(json.dumps([cell.pid, gc]), flush=True)
time.sleep(600)
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # e.g. PermissionError: it exists, just not ours
        return True
    return True


def test_spawned_tree_is_in_the_group_and_terminate_confirms_it_gone():
    """The POSIX mirror of test_procs.py::test_spawned_tree_is_in_the_job_and_terminate_confirms_it_gone:
    a child starts a grandchild (both land in the same process group, `setsid`'s default inheritance);
    terminate_and_confirm reports true only once `pgrep -g` finds neither."""
    cell = procs.spawn([sys.executable, "-c", TREE], cwd=None, env=None)
    grandchild = int(cell.proc.stdout.readline())
    assert {cell.pid, grandchild} <= cell.job.pids()
    assert cell.job.active() >= 2
    assert cell.terminate_and_confirm(timeout=10)
    assert cell.job.active() == 0
    assert not _alive(cell.pid) and not _alive(grandchild)
    cell.close()


def test_engine_crash_kills_every_descendant(tmp_path):
    """The POSIX mirror of test_procs.py::test_engine_crash_kills_every_descendant: there is no kernel
    kill-on-close primitive on POSIX (module doc), so this is what proves the watchdog gives a crashed
    engine's cell tree the same guarantee."""
    src = str(procs.__file__).rsplit("harness_bench", 1)[0]
    script = tmp_path / "owner.py"
    script.write_text(OWNER.format(src=src, tree=TREE), encoding="utf-8")
    owner = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    pids = json.loads(owner.stdout.readline())
    assert all(_alive(p) for p in pids)
    owner.kill()  # a hard kill, no cleanup: the watchdog, not the owner, must reap the tree
    owner.wait()
    deadline = time.monotonic() + 15
    while any(_alive(p) for p in pids) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not any(_alive(p) for p in pids)


def test_spawn_of_a_missing_executable_is_a_spawn_error(tmp_path):
    with pytest.raises(procs.SpawnError) as e:
        procs.spawn([str(tmp_path / "nope")], cwd=None, env=None)
    assert e.value.cause is Cause.spawn and e.value.win32_error


def test_close_kills_whatever_remains_and_stops_the_watchdog():
    cell = procs.spawn([sys.executable, "-c", "import time;time.sleep(30)"], cwd=None, env=None)
    watchdog_pid = cell.job._watchdog.pid
    cell.close()
    assert not _alive(cell.pid)
    assert not _alive(watchdog_pid)  # the watchdog has nothing left to watch and stops with close()


def test_exit_status_is_reported_as_pythons_own_signed_convention():
    """POSIX (unlike Windows) is never masked to unsigned: terminate() is SIGKILL (module doc: the
    Windows Job Object it stands in for has no graceful phase of its own), so the death reads as -9."""
    cell = procs.spawn([sys.executable, "-c", "import time;time.sleep(30)"], cwd=None, env=None)
    cell.terminate_and_confirm(timeout=10)
    assert cell.wait(timeout=10) == -9
    cell.close()
