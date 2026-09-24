"""Job Object process control (ADR-0013; spikes N2, N4): kill -> confirm, kill-on-close, containment."""

import ctypes
import json
import subprocess
import sys
import time

import pytest

from harness_bench import procs
from harness_bench.errors import Cause

pytestmark = pytest.mark.native

# A tree: child starts a grandchild, prints the grandchild's pid, then sleeps.
TREE = ("import subprocess,sys,time;"
        "g=subprocess.Popen([sys.executable,'-c','import time;time.sleep(600)']);"
        "print(g.pid,flush=True);time.sleep(600)")


def _alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False).stdout
    return str(pid) in out


def test_spawned_tree_is_in_the_job_and_terminate_confirms_it_gone():
    cell = procs.spawn([sys.executable, "-c", TREE], cwd=None, env=None)
    grandchild = int(cell.proc.stdout.readline())
    assert {cell.pid, grandchild} <= cell.job.pids()
    assert cell.job.active() >= 2  # a venv python.exe is a launcher plus the interpreter
    assert cell.terminate_and_confirm(timeout=10)
    assert cell.job.active() == 0
    assert not _alive(cell.pid) and not _alive(grandchild)
    cell.close()


def test_job_limits_are_kill_on_close_without_breakaway():
    cell = procs.spawn([sys.executable, "-c", "import time;time.sleep(30)"], cwd=None, env=None)
    flags = cell.job.limit_flags()
    assert flags & procs.KILL_ON_JOB_CLOSE
    assert not flags & procs.BREAKAWAY_OK and not flags & procs.SILENT_BREAKAWAY_OK
    assert not cell.job.inheritable()
    cell.terminate_and_confirm(timeout=10)
    cell.close()


OWNER = """
import json, sys, time
sys.path.insert(0, {src!r})
from harness_bench import procs
cell = procs.spawn([sys.executable, "-c", {tree!r}], cwd=None, env=None)
gc = int(cell.proc.stdout.readline())
print(json.dumps([cell.pid, gc]), flush=True)
time.sleep(600)
"""


def test_engine_crash_kills_every_descendant(tmp_path):
    src = str(procs.__file__).rsplit("harness_bench", 1)[0]
    script = tmp_path / "owner.py"
    script.write_text(OWNER.format(src=src, tree=TREE), encoding="utf-8")
    owner = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    pids = json.loads(owner.stdout.readline())
    assert all(_alive(p) for p in pids)
    subprocess.run(["taskkill", "/F", "/PID", str(owner.pid)], capture_output=True, check=False)  # hard kill, no cleanup
    deadline = time.monotonic() + 10
    while any(_alive(p) for p in pids) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not any(_alive(p) for p in pids)


def test_failed_assignment_leaves_no_process_and_raises_spawn(monkeypatch):
    seen = []
    real_open = procs._open_process

    def spy(pid):
        seen.append(pid)
        return real_open(pid)

    monkeypatch.setattr(procs, "_open_process", spy)
    monkeypatch.setattr(procs, "_assign", lambda job, handle: False)  # fault seam
    with pytest.raises(procs.SpawnError) as e:
        procs.spawn([sys.executable, "-c", "import time;time.sleep(30)"], cwd=None, env=None)
    assert e.value.cause is Cause.spawn
    assert seen and not _alive(seen[0])


def test_a_failed_job_query_raises_from_the_last_error(monkeypatch):  # never a zeroed struct read as "no processes"
    cell = procs.spawn([sys.executable, "-c", "import time;time.sleep(30)"], cwd=None, env=None)
    try:
        def fail(job, info_class, buf):  # fault seam: QueryInformationJobObject fails with ERROR_INVALID_HANDLE
            ctypes.set_last_error(6)
            return False

        monkeypatch.setattr(procs, "_query", fail)
        for probe in (cell.job.active, cell.job.pids, cell.job.peak_memory, cell.job.cpu_time_ms, cell.job.limit_flags):
            with pytest.raises(OSError) as e:
                probe()
            assert e.value.winerror == 6
        with pytest.raises(OSError):
            cell.terminate_and_confirm(timeout=1)  # an unanswerable query is not a confirmed kill
    finally:
        monkeypatch.undo()
        cell.terminate_and_confirm(timeout=10)
        cell.close()


def test_a_closed_job_is_not_reported_empty():
    job = procs.Job()
    job.close()
    for probe in (job.active, job.inheritable):  # a NULL handle must never answer for the caller's own job
        with pytest.raises(OSError):
            probe()


def test_spawn_of_a_missing_executable_is_a_spawn_error(tmp_path):
    with pytest.raises(procs.SpawnError) as e:
        procs.spawn([str(tmp_path / "nope.exe")], cwd=None, env=None)
    assert e.value.cause is Cause.spawn and e.value.win32_error


def test_exit_status_is_reported_unsigned():
    cell = procs.spawn([sys.executable, "-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000017)"], cwd=None, env=None)
    assert cell.wait(timeout=20) == 0xC0000017
    cell.close()


def test_peak_memory_and_cpu_come_from_job_accounting():
    cell = procs.spawn([sys.executable, "-c", "x=bytearray(64*1024*1024);import time;time.sleep(0.5)"], cwd=None, env=None)
    cell.wait(timeout=30)
    assert cell.job.peak_memory() >= 64 * 1024 * 1024
    assert cell.job.cpu_time_ms() >= 0
    cell.close()


def test_run_times_out_and_kills_the_tree():
    started = time.monotonic()
    result = procs.run([sys.executable, "-c", TREE], cwd=None, env=None, timeout=2)
    assert result.timed_out and time.monotonic() - started < 15
    assert result.returncode is not None


def test_run_bounds_output():
    result = procs.run([sys.executable, "-c", "print('x'*5000000)"], cwd=None, env=None, timeout=30, max_output=1024)
    assert result.returncode == 0 and len(result.stdout) <= 1024 and result.truncated
