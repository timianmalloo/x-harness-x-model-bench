"""Archive a cell, verify it, then delete its workspace (US-19; ADR-0006; ADR-0010).

- The archive copies the cell's working copy and harness home, never following a link or junction:
  a link is recorded as a row (`kind: link`, its target) and not copied.
- Credential files are never copied (they are also deleted from the home before archiving).
- Each file or link is an `archive_files` row keyed by (cell, attempt, path); `archive_hash` is the
  sha256 of the canonical sorted rows, a commitment that `verify` recomputes (HB-LED-005).
- The workspace is deleted only after the archive verifies; a Windows sharing violation is retried a
  bounded number of times, and on failure the workspace is kept and reported.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

ROW_FIELDS = ("path", "kind", "size", "sha256", "link_target")


@dataclass
class ArchiveResult:
    folder: Path
    rows: list[dict]
    archive_hash: str
    total_bytes: int


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


def archive_cell(cell_dir: Path, dest_root: Path, attempt: int, exclude_names: set[str]) -> ArchiveResult:
    folder = dest_root / f"attempt-{attempt}"
    if folder.exists():
        raise BenchError("HB-USR-002", f"{folder} already exists; an archive attempt is written once")
    rows: list[dict] = []
    total = 0
    for top in sorted(p for p in cell_dir.iterdir()):
        stack = [top]
        while stack:
            src = stack.pop()
            rel = src.relative_to(cell_dir).as_posix()
            dest = folder / rel
            if _is_link(src):
                rows.append({"path": rel, "kind": "link", "size": 0, "sha256": "", "link_target": os.readlink(src)})
            elif src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                stack.extend(sorted(src.iterdir(), reverse=True))
            elif src.is_file() and src.name not in exclude_names:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                size = dest.stat().st_size
                total += size
                rows.append({"path": rel, "kind": "file", "size": size, "sha256": _sha(dest), "link_target": ""})
    for r in rows:
        r["archive_attempt"] = attempt
    return ArchiveResult(folder, rows, archive_hash(rows), total)


def verify(folder: Path, rows: list[dict]) -> None:
    """Every file row matches the archived bytes (HB-LED-005 otherwise)."""
    for r in rows:
        if r["kind"] != "file":
            continue
        path = folder / r["path"]
        if not path.is_file() or path.stat().st_size != r["size"] or _sha(path) != r["sha256"]:
            raise BenchError("HB-LED-005", f"archived file {r['path']} does not match its archive_files row")


def make_writable(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


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
