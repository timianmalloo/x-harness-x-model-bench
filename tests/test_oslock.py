"""The run lock (ADR-0007): one engine per run; released by the OS when the process dies; mtime heartbeat."""

import multiprocessing
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness_bench import oslock
from harness_bench.errors import BenchError

_PAYLOAD = b"payload-v1"
_RACES = 8


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


def test_runlock_held_is_true_only_while_this_object_holds_the_fd(tmp_path):
    path = tmp_path / ".lock"
    lock = oslock.RunLock.acquire(path)
    assert lock.held is True
    lock.release()
    assert lock.held is False


def test_acquire_refuses_a_non_regular_lock(tmp_path):
    path = tmp_path / "lockdir"
    path.mkdir()
    with pytest.raises(Exception) as ei:
        oslock.RunLock.acquire(path, "HB-CMP-001")
    assert isinstance(ei.value, BenchError)
    assert ei.value.code == "HB-CMP-001"
    assert "not a regular file" in ei.value.message


def _file_bytes(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(folder.iterdir()) if path.is_file()}


def _acquire_then_probe_side(
    own: str,
    own_code: str,
    other: str,
    other_code: str,
    barrier: multiprocessing.Barrier,
    queue: multiprocessing.Queue,
) -> None:
    """One side of the handshake. `between` is the barrier, after acquire and before probe."""
    own_path = Path(own)
    payload = own_path.parent / "payload"
    try:
        lock = oslock.acquire_then_probe(
            own_path,
            own_code,
            [(Path(other), other_code)],
            between=lambda: barrier.wait(timeout=10),
        )
    except BenchError as exc:
        queue.put({
            "proceeded": False,
            "code": exc.code,
            "message": exc.message,
            "own_held": oslock.is_held(own_path),
            "payload": payload.read_bytes(),
            "error": None,
        })
        return
    except (OSError, multiprocessing.BrokenBarrierError) as exc:
        body = payload.read_bytes() if payload.is_file() else None
        queue.put({
            "proceeded": False,
            "code": None,
            "message": None,
            "own_held": None,
            "payload": body,
            "error": f"{type(exc).__name__}: {exc}",
        })
        return
    held = lock.held
    lock.release()
    queue.put({
        "proceeded": True,
        "code": None,
        "message": None,
        "own_held": held,
        "payload": payload.read_bytes(),
        "error": None,
    })


def test_acquire_then_probe_never_lets_both_proceed(tmp_path):
    """Mutant "swap acquire and probe": probe `others` before `RunLock.acquire`, with `between`
    still between those two operations. Both sides pass the barrier before either holds, so
    both proceed on every race. The red skeleton acquires and does not probe, so both proceed.

    Both refusing is allowed. When it happens, every file's bytes are unchanged.
    """
    ctx = multiprocessing.get_context("spawn")
    own_a = tmp_path / "a.lock"
    own_b = tmp_path / "b.lock"
    payload = tmp_path / "payload"
    own_a.write_bytes(b"")
    own_b.write_bytes(b"")
    payload.write_bytes(_PAYLOAD)
    before = _file_bytes(tmp_path)
    for _ in range(_RACES):
        barrier = ctx.Barrier(2)
        queue = ctx.Queue()
        left = ctx.Process(
            target=_acquire_then_probe_side,
            args=(str(own_a), "HB-GRD-001", str(own_b), "HB-CMP-004", barrier, queue),
        )
        right = ctx.Process(
            target=_acquire_then_probe_side,
            args=(str(own_b), "HB-CMP-001", str(own_a), "HB-GRD-007", barrier, queue),
        )
        left.start()
        right.start()
        pids = (left.pid, right.pid)
        left.join(30)
        right.join(30)
        for proc in (left, right):
            if proc.is_alive():
                proc.terminate()
                proc.join(5)
        assert left.exitcode == 0, (left.exitcode, pids)
        assert right.exitcode == 0, (right.exitcode, pids)
        results = [queue.get(timeout=5), queue.get(timeout=5)]
        assert not (results[0]["proceeded"] and results[1]["proceeded"])
        for item in results:
            assert item["error"] is None, item["error"]
            assert item["payload"] == _PAYLOAD
            if not item["proceeded"]:
                assert item["code"] in {"HB-CMP-004", "HB-GRD-007"}
                assert item["message"] is not None and "retry" in item["message"]
                assert item["own_held"] is False
        if not results[0]["proceeded"] and not results[1]["proceeded"]:
            assert _file_bytes(tmp_path) == before


def test_acquire_then_probe_refuses_a_held_other_and_says_retry(tmp_path):
    """Mutant "probe others[0] before acquiring": `is_held(others[0])` runs before
    `RunLock.acquire`, and `between` still sits between those two operations, so `between`
    does not observe `own` held. The red skeleton does not probe and does not call `between`.

    `others[0]` is free, `others[1]` is held, and `others[2]` is a directory (`is_held` raises).
    The first held entry is refused; the directory is not probed.
    """
    own = tmp_path / "own.lock"
    free = tmp_path / "free.lock"
    held = tmp_path / "held.lock"
    folder = tmp_path / "not-a-file"
    payload = tmp_path / "payload"
    own.write_bytes(b"")
    free.write_bytes(b"")
    held.write_bytes(b"")
    folder.mkdir()
    payload.write_bytes(_PAYLOAD)
    # A held lock denies reads on Windows (mandatory byte lock), so the snapshot is taken
    # before acquire and compared after release.
    before = _file_bytes(tmp_path)
    seen: list[bool] = []

    def between() -> None:
        seen.append(oslock.is_held(own))

    raised: BenchError | None = None
    returned = None
    with oslock.RunLock.acquire(held, "HB-CMP-001"):
        try:
            returned = oslock.acquire_then_probe(
                own,
                "HB-GRD-001",
                [(free, "HB-GRD-007"), (held, "HB-CMP-004"), (folder, "HB-CMP-001")],
                between=between,
            )
        except BenchError as exc:
            raised = exc
        finally:
            if returned is not None:
                returned.release()
    assert _file_bytes(tmp_path) == before
    assert isinstance(raised, BenchError)
    assert raised.code == "HB-CMP-004"
    assert "retry" in raised.message
    assert seen == [True]
    assert not oslock.is_held(own)


def test_acquire_then_probe_releases_own_when_the_probe_raises(tmp_path):
    """The probe loop is in `try/finally`. A directory probe raises from `is_held` and still
    releases `own`. Dropping the `finally` leaves `own` held. The red skeleton does not probe,
    so nothing is raised and `own` stays held until the caller releases it.
    """
    own = tmp_path / "own.lock"
    folder = tmp_path / "folder"
    folder.mkdir()
    raised = False
    returned = None
    try:
        returned = oslock.acquire_then_probe(own, "HB-GRD-001", [(folder, "HB-CMP-004")])
    except OSError:
        raised = True
    finally:
        if returned is not None:
            returned.release()
    assert raised
    assert not oslock.is_held(own)
