"""Archive a cell, verify it, then delete its workspace (US-19; ADR-0006; ADR-0010).

- The archive copies the cell's working copy and harness home, never following a link or junction:
  a link is recorded as a row (`kind: link`, its target) and not copied.
- Credential files are never copied (they are also deleted from the home before archiving).
- Each file or link is an `archive_files` row keyed by (cell, attempt, path); `archive_hash` is the
  sha256 of the canonical sorted rows, a commitment that `verify` recomputes (HB-LED-005).
- The workspace is deleted only after the archive verifies; a Windows sharing violation is retried a
  bounded number of times, and on failure the workspace is kept and reported.
- `teardown` removes what a run left under the cells root, but only the folders of archived cells: an
  unarchived cell's folder is the only copy of its work, so it is kept and reported.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from harness_bench import atomic, oslock
from harness_bench.atomic import make_writable
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

ROW_FIELDS = ("path", "kind", "size", "sha256", "link_target")


@dataclass
class ArchiveResult:
    folder: Path
    rows: list[dict]
    archive_hash: str
    total_bytes: int
    duration_ms: int | None = None


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def archive_hash(rows: list[dict]) -> str:
    body = sorted(({k: r.get(k) for k in ROW_FIELDS} for r in rows), key=lambda r: r["path"])
    return hashlib.sha256(canonical({"files": body})).hexdigest()


def snapshot_folder(run_dir: Path, cell_id: str, turn: int) -> Path:
    return run_dir / "archive" / cell_id / f"turn-{turn}"


def snapshot_of(row: dict) -> str:
    """Absent snapshot reads final; shared reader predicate (W1-J D-J2)."""
    return row.get("snapshot", "final")


def snapshot_cell(cell_dir: Path, dest_root: Path, turn: int, exclude_names: set[str],
                  cancel=None, *, run_lock: oslock.RunLock | None = None) -> ArchiveResult:
    """Publish ws only; the engine supplies its held run lock for temp cleanup.

    Standalone callers own the same run lock for this call. An existing folder
    is never adopted by a fresh call; the engine alone recovers its own publish.
    """
    folder = snapshot_folder(dest_root.parent.parent, dest_root.name, turn)
    folder.parent.mkdir(parents=True, exist_ok=True)
    owned_lock = run_lock is None
    if owned_lock:
        run_lock = oslock.RunLock.acquire(dest_root.parent.parent / ".lock", code="HB-RUN-005")
    try:
        if run_lock.path.resolve() != (dest_root.parent.parent / ".lock").resolve():
            raise ValueError("snapshot sweep needs this run's lock")
        atomic.sweep_temps(dest_root, run_lock)
        if owned_lock and os.path.lexists(folder):
            raise BenchError("HB-LED-008", f"unrecorded snapshot {folder} already exists")
        copy = _Copy(cell_dir, exclude_names, include_names={"ws"}, cancel=cancel)
        start_time = time.perf_counter()
        try:
            atomic.publish_dir(folder, copy.fill, copy.verify)
        except Exception:
            atomic.sweep_temps(dest_root, run_lock)
            raise
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        for r in copy.rows:
            r.update(archive_attempt=1, snapshot=f"turn-{turn}")
        return ArchiveResult(folder, copy.rows, archive_hash(copy.rows), copy.total_bytes, duration_ms)
    finally:
        if owned_lock:
            run_lock.release()


def append_missing_rows(folder: Path, rows: list[dict], present: list[dict], code: str) -> list[dict]:
    """Return missing keys only; reject conflicting immutable facts for this folder."""
    def key(r: dict) -> tuple:
        return (r.get("run_id"), r.get("cell_id"), r.get("archive_attempt"), snapshot_of(r), r["path"])

    expected = {key(r): r for r in rows}
    seen = set()
    for r in present:
        k = key(r)
        want = expected.get(k)
        if want is None or any(r.get(field) != want.get(field) for field in ROW_FIELDS):
            raise BenchError(code, f"{folder}: present archive row differs at {r['path']}")
        seen.add(k)
    return [r for r in rows if key(r) not in seen]


def _copy_hashed(src: Path, dest: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with src.open("rb") as s, dest.open("wb") as d:
        for chunk in iter(lambda: s.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
            d.write(chunk)
    return size, h.hexdigest()


def attempt_dirs(run_dir: Path, cell_id: str) -> list[Path]:
    base = run_dir / "archive" / cell_id
    if not base.is_dir():
        return []
    matches: list[tuple[int, Path]] = []
    for p in base.iterdir():
        m = re.fullmatch(r"attempt-(\d+)", p.name)
        if m and p.is_dir():
            matches.append((int(m.group(1)), p))
    matches.sort(key=lambda t: t[0])
    return [p for _, p in matches]


class _Copy:
    def __init__(self, cell_dir: Path, exclude_names: set[str], *, include_names: set[str] | None = None,
                 cancel=None) -> None:
        self.cell_dir = cell_dir
        self.exclude_names = exclude_names
        self.rows: list[dict] = []
        self.total_bytes = 0
        self.include_names = include_names
        self.cancel = cancel

    def fill(self, tmp: Path) -> None:
        exclude_names = self.exclude_names
        for top in sorted(p for p in self.cell_dir.iterdir()):
            if self.include_names is not None and top.name not in self.include_names:
                continue
            stack = [top]
            while stack:
                if self.cancel is not None and self.cancel.is_set():
                    raise InterruptedError("snapshot cancelled between files")
                src = stack.pop()
                rel = src.relative_to(self.cell_dir).as_posix()
                dest = tmp / rel
                if _is_link(src):
                    self.rows.append({
                        "path": rel,
                        "kind": "link",
                        "size": 0,
                        "sha256": "",
                        "link_target": os.readlink(src),
                    })
                elif src.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    stack.extend(sorted(src.iterdir(), reverse=True))
                elif src.is_file() and src.name not in exclude_names:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    size, sha256 = _copy_hashed(src, dest)
                    self.total_bytes += size
                    self.rows.append({
                        "path": rel,
                        "kind": "file",
                        "size": size,
                        "sha256": sha256,
                        "link_target": "",
                    })

    def verify(self, tmp: Path) -> None:
        verify(tmp, self.rows)


def archive_cell(cell_dir: Path, dest_root: Path, attempt: int, exclude_names: set[str]) -> ArchiveResult:
    folder = dest_root / f"attempt-{attempt}"
    if os.path.lexists(folder):
        raise BenchError("HB-USR-002", f"{folder} already exists; an archive attempt is written once")
    dest_root.mkdir(parents=True, exist_ok=True)
    copy = _Copy(cell_dir, exclude_names)
    start_time = time.perf_counter()
    atomic.publish_dir(folder, copy.fill, copy.verify)
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    for r in copy.rows:
        r["archive_attempt"] = attempt
    return ArchiveResult(folder, copy.rows, archive_hash(copy.rows), copy.total_bytes, duration_ms)


def verify(folder: Path, rows: list[dict]) -> None:
    """Every file row matches the archived bytes (HB-LED-005 otherwise)."""
    if not folder.is_dir():
        raise BenchError("HB-LED-005", f"archive folder {folder} does not exist")

    expected_files: set[str] = set()
    for r in rows:
        if r["kind"] == "file":
            expected_files.add(r["path"])
            path = folder / r["path"]
            if not path.is_file() or path.stat().st_size != r["size"] or _sha(path) != r["sha256"]:
                raise BenchError("HB-LED-005", f"archived file {r['path']} does not match its archive_files row")
        elif r["kind"] == "link":
            if os.path.lexists(folder / r["path"]):
                raise BenchError("HB-LED-005", f"archived file exists at link row path {r['path']}")

    actual_files = {
        p.relative_to(folder).as_posix()
        for p in folder.rglob("*")
        if p.is_file() and not _is_link(p)
    }
    if actual_files != expected_files:
        extra = sorted(actual_files - expected_files)
        missing = sorted(expected_files - actual_files)
        raise BenchError(
            "HB-LED-005",
            f"archived files set does not match archive_files rows: extra={extra}, missing={missing}",
        )


def delete_after_verify(cell_dir: Path, folder: Path, rows: list[dict], retries: int = 5, wait: float = 1.0) -> bool:
    """Delete the workspace only after the archive verifies. False (workspace kept) if it stays locked."""
    verify(folder, rows)
    for attempt in range(retries + 1):
        try:
            shutil.rmtree(cell_dir, onexc=make_writable)
            return True
        except OSError:
            if attempt == retries:
                return False
            time.sleep(wait * (attempt + 1))
    return False


def teardown(run_cells: Path, archived: set[str]) -> tuple[list[str], list[str]]:
    """Remove the archived cells' folders under `run_cells`; return (removed, kept) cell ids."""
    removed, kept = [], []
    if not run_cells.is_dir():
        return removed, kept
    for folder in sorted(p for p in run_cells.iterdir() if p.is_dir()):
        if folder.name in archived:
            shutil.rmtree(folder, onexc=make_writable)
            removed.append(folder.name)
        else:
            kept.append(folder.name)
    if not any(run_cells.iterdir()):
        run_cells.rmdir()
    return removed, kept
