"""Crash-atomic publish helpers (W1-B, X-B1). Naive skeleton: public names, wrong bodies."""

from __future__ import annotations

import os
import re
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from harness_bench import oslock
from harness_bench.errors import BenchError

T = TypeVar("T")

TEMP_RE = re.compile(r"^(?P<base>.+)\.tmp-(?P<pid>[0-9]+)-(?P<nonce>[0-9a-f]{32})$")
RENAME_BACKOFF = (0.05, 0.1, 0.2, 0.4, 0.8, None)
_POSIX = os.name == "posix"
O_BINARY = getattr(os, "O_BINARY", 0)


def is_temp_name(name: str) -> bool:
    return bool(TEMP_RE.match(name))


def create_once(path: Path, data: bytes) -> bool:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    os.write(fd, data)
    os.close(fd)
    return True


def publish_dir(final: Path, fill: Callable[[Path], T], verify: Callable[[Path], None]) -> T:
    return fill(final)


def rename_with_retry(
    src: Path,
    dst: Path,
    *,
    replace: bool = False,
    settled: Callable[[], bool] | None = None,
) -> int:
    os.rename(src, dst)
    return 0


def stale_temps(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(folder.glob(f"{folder.name}.tmp-*"))


def sweep_temps(folder: Path, lock: oslock.RunLock) -> list[Path]:
    if not oslock.is_held(lock.path):
        raise ValueError(f"sweep_temps needs the writer lock for {folder}")
    removed: list[Path] = []
    for path in stale_temps(folder):
        if path.is_dir():
            shutil.rmtree(path, onexc=make_writable)
        else:
            os.unlink(path)
        removed.append(path)
    return removed


def make_writable(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _fsync_dir(path: Path) -> None:
    return None


def _discard_temp(tmp: Path) -> None:
    os.unlink(tmp)
