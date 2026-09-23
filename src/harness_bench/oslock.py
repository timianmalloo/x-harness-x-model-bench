"""The run lock: one engine per run, released by the OS when the process dies (ADR-0007).

Pattern: Mutual Exclusion. Liveness is tested by trying the lock, never by PID. The lock file's
mtime is the heartbeat: the engine touches it every scheduler loop, so `bench status` can tell a
live engine from a stalled one without heartbeat rows in the ledger.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Self

from harness_bench.errors import BenchError

if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class RunLock:
    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self._fd = fd

    @classmethod
    def acquire(cls, path: Path, code: str = "HB-GRD-001") -> Self:
        """Take the lock or raise BenchError(code). `code` names what a held lock means to the caller."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        if not _try_lock(fd):
            os.close(fd)
            raise BenchError(code, f"{path} is held by another process")
        lock = cls(path, fd)
        lock.heartbeat()
        return lock

    def heartbeat(self) -> None:
        os.utime(self.path, None)

    def release(self) -> None:
        if self._fd >= 0:
            _unlock(self._fd)
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def is_held(path: Path) -> bool:
    if not path.exists():
        return False
    fd = os.open(path, os.O_RDWR)
    try:
        if _try_lock(fd):
            _unlock(fd)
            return False
        return True
    finally:
        os.close(fd)


def heartbeat_age(path: Path) -> float:
    return time.time() - path.stat().st_mtime
