"""The run lock (ADR-0007): one engine per run; released by the OS when the process dies; mtime heartbeat."""

import subprocess
import sys
import time

import pytest

from harness_bench import oslock
from harness_bench.errors import BenchError


def test_second_holder_is_refused(tmp_path):
    path = tmp_path / ".lock"
    with oslock.RunLock.acquire(path):
        assert oslock.is_held(path)
        with pytest.raises(BenchError):
            oslock.RunLock.acquire(path)
    assert not oslock.is_held(path)


def test_lock_is_released_when_the_holder_dies(tmp_path):
    path = tmp_path / ".lock"
    src = str(oslock.__file__).rsplit("harness_bench", 1)[0]
    code = (f"import sys,time;sys.path.insert(0,{src!r});from harness_bench import oslock;"
            f"l=oslock.RunLock.acquire(__import__('pathlib').Path({str(path)!r}));print('held',flush=True);time.sleep(600)")
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "held"
    assert oslock.is_held(path)
    holder.kill()
    holder.wait()
    deadline = time.monotonic() + 5
    while oslock.is_held(path) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not oslock.is_held(path)


def test_heartbeat_advances_the_mtime(tmp_path):
    path = tmp_path / ".lock"
    with oslock.RunLock.acquire(path) as lock:
        before = path.stat().st_mtime_ns
        time.sleep(0.05)
        lock.heartbeat()
        assert path.stat().st_mtime_ns > before
        assert oslock.heartbeat_age(path) < 5
