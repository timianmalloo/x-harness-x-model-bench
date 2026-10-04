"""Crash-atomic publish helpers (W1-B, X-B1a)."""

from __future__ import annotations

import errno
import logging
import os
import re
import shutil
import stat
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from harness_bench import oslock
from harness_bench.errors import BenchError

TEMP_RE = re.compile(r"^(?P<base>.+)\.tmp-(?P<pid>[0-9]+)-(?P<nonce>[0-9a-f]{32})$")
RENAME_BACKOFF = (0.05, 0.1, 0.2, 0.4, 0.8, None)
_POSIX = os.name == "posix"
O_BINARY = getattr(os, "O_BINARY", 0)
_REPARSE = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
log = logging.getLogger("harness_bench.atomic")


def is_temp_name(name: str) -> bool:
    return TEMP_RE.fullmatch(name) is not None


def _is_link_entry(st: os.stat_result) -> bool:
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        offset += os.write(fd, view[offset:])


def _read_all(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _hardlink(src: Path, dst: Path) -> None:
    kwargs = {}
    if os.link in getattr(os, "supports_follow_symlinks", ()):
        kwargs["follow_symlinks"] = False
    os.link(src, dst, **kwargs)


def _discard_temp(tmp: Path) -> None:
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        return
    except OSError as exc:
        log.warning(
            "atomic.temp_leaked",
            extra={"path": str(tmp), "exc_type": type(exc).__name__},
        )


def _conflict(path: Path, message: str) -> None:
    log.warning(
        "atomic.create_once",
        extra={"path": str(path), "outcome": "conflict", "error_code": "HB-LED-007"},
    )
    raise BenchError("HB-LED-007", message)


def _must_be_regular(path: Path) -> os.stat_result:
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or _is_link_entry(st):  # M7
        raise BenchError("HB-LED-007", f"{path} exists and is not a regular file")
    return st


def _existing_equal(path: Path, data: bytes) -> bool:
    lst = _must_be_regular(path)
    flags = os.O_RDONLY | O_BINARY | getattr(os, "O_NOFOLLOW", 0)
    try:
        rfd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise BenchError("HB-LED-007", f"{path} exists and is not a regular file") from exc
        raise
    try:
        st = os.fstat(rfd)
        if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != (lst.st_dev, lst.st_ino):
            raise BenchError("HB-LED-007", f"{path} exists and is not a regular file")
        existing = _read_all(rfd, st.st_size)
    finally:
        os.close(rfd)
    if existing == data:
        return False
    _conflict(path, f"{path} exists with different bytes")
    return False


def _exists_non_regular(path: Path) -> bool:
    try:
        _must_be_regular(path)
    except FileNotFoundError:
        return False
    except BenchError:
        return True
    return False


def create_once(path: Path, data: bytes) -> bool:
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    fd = -1
    try:
        fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | O_BINARY, 0o644)
        _write_all(fd, data)
        os.fsync(fd)
        if _exists_non_regular(path):
            raise BenchError("HB-LED-007", f"{path} exists and is not a regular file")
        try:
            _hardlink(tmp, path)
        except FileExistsError:
            return _existing_equal(path, data)
        got = os.fstat(fd)
        listed = os.lstat(path)
        if (got.st_dev, got.st_ino) != (listed.st_dev, listed.st_ino):
            os.unlink(path)
            _conflict(path, f"{path} was replaced between write and link")
        return True
    finally:
        if fd >= 0:
            os.close(fd)
            _discard_temp(tmp)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _publish_failed(final: Path, phase: str, exc: BaseException) -> None:
    extra: dict[str, object] = {"final": str(final), "phase": phase, "exc_type": type(exc).__name__}
    if isinstance(exc, BenchError):
        extra["error_code"] = exc.code
    log.error("atomic.publish_failed", extra=extra)


def _regular_files(root: Path) -> list[Path]:
    found: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = os.scandir(current)
        except FileNotFoundError:
            continue
        with entries:
            for entry in entries:
                try:
                    st = os.lstat(entry.path)
                except FileNotFoundError:
                    continue
                if _is_link_entry(st):
                    continue
                path = Path(entry.path)
                if stat.S_ISDIR(st.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(st.st_mode):
                    found.append(path)
    return found


def _fsync_files(root: Path) -> tuple[int, int]:
    files = _regular_files(root)
    total = 0
    for path in files:
        total += os.lstat(path).st_size
        wfd = os.open(path, os.O_RDWR | O_BINARY)
        try:
            os.fsync(wfd)
        finally:
            os.close(wfd)
    return len(files), total


def publish_dir[T](final: Path, fill: Callable[[Path], T], verify: Callable[[Path], None]) -> T:
    if os.path.lexists(final):
        raise FileExistsError(errno.EEXIST, "File exists", str(final))
    tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}-{uuid4().hex}")
    os.mkdir(tmp)
    phase = "fill"
    try:
        started = time.perf_counter()
        result = fill(tmp)
        fill_ms = _elapsed_ms(started)
        phase = "fsync"
        started = time.perf_counter()
        files, nbytes = _fsync_files(tmp)
        if _POSIX:
            _fsync_dir(tmp)
        fsync_ms = _elapsed_ms(started)
        phase = "verify"
        started = time.perf_counter()
        verify(tmp)
        verify_ms = _elapsed_ms(started)
        phase = "rename"
        started = time.perf_counter()
        retries = rename_with_retry(tmp, final)
        rename_ms = _elapsed_ms(started)
        if _POSIX:
            _fsync_dir(final.parent)
    except Exception as exc:
        _publish_failed(final, phase, exc)
        raise
    log.info(
        "atomic.publish",
        extra={
            "final": str(final),
            "files": files,
            "bytes": nbytes,
            "fill_ms": fill_ms,
            "fsync_ms": fsync_ms,
            "verify_ms": verify_ms,
            "rename_ms": rename_ms,
            "rename_retries": retries,
        },
    )
    return result


def rename_with_retry(
    src: Path,
    dst: Path,
    *,
    replace: bool = False,
    settled: Callable[[], bool] | None = None,
) -> int:
    op = os.replace if replace else os.rename
    retries = 0
    for delay in RENAME_BACKOFF:
        try:
            op(src, dst)
            return retries
        except PermissionError:
            if settled is not None and settled():
                return retries
            if delay is None:
                raise
            time.sleep(delay)
            retries += 1
    return retries


def stale_temps(folder: Path) -> list[Path]:
    try:
        entries = os.scandir(folder)
    except FileNotFoundError:
        return []
    found: list[Path] = []
    with entries:
        for entry in entries:
            if is_temp_name(entry.name):
                found.append(Path(entry.path))
    return sorted(found)


def _sweep_one(path: Path, st: os.stat_result) -> str:
    if _is_link_entry(st):
        os.unlink(path)
        return "link"
    if stat.S_ISDIR(st.st_mode):
        shutil.rmtree(path, onexc=make_writable)
        return "dir"
    os.unlink(path)
    return "file"


def sweep_temps(folder: Path, lock: oslock.RunLock) -> list[Path]:
    if not lock.held:
        raise ValueError(f"sweep_temps needs the writer lock for {folder}")
    swept: list[Path] = []
    for path in stale_temps(folder):
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            continue
        try:
            kind = _sweep_one(path, st)
        except FileNotFoundError:
            continue
        log.warning("atomic.temp_swept", extra={"path": str(path), "kind": kind})
        swept.append(path)
    return swept


def make_writable(func, path, _exc) -> None:
    st = os.lstat(path)
    if not _is_link_entry(st):
        os.chmod(path, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)
    func(path)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | O_BINARY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
