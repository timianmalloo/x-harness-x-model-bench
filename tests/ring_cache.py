"""Content-addressed base-tree caches for the task ring tests (defect class CACHE-A).

The ring tests build a task's base tree once into a cache under the system temp dir. A fixed version
string made that cache shared and stale-able: any worktree or run on the machine, whatever its builder
code or task content, read and wrote the same `hb-*-ring/sources/<task>/<key>` folder. The key is now a
hash of the task folder's content and of the code that builds it, so a different tree or a different
builder gets a different folder and a stale build is never served. `workspace.task_source` still lands
each build atomically (temp sibling, then rename; the loser of a race uses the winner's copy).
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from harness_bench import workspace


def ring_root(name: str) -> Path:
    return Path(tempfile.gettempdir()) / f"hb-{name}-ring"


def content_version(task_dir: Path) -> str:
    """16+ hex chars naming exactly this task content and this builder code."""
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                       and not p.relative_to(task_dir).parts[0] in {"oracle", "tests"}):
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    digest.update(Path(workspace.__file__).read_bytes())
    return "c" + digest.hexdigest()


def cached_base(task_dir: Path, name: str) -> Path:
    root = ring_root(name)
    return workspace.task_source(task_dir, content_version(task_dir), root / "sources", root / "upstream")
