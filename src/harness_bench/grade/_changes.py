"""The shared change reader: a cell's pre-turn commit and its change set (design phase3-graders, GR-CODE c1).

- The archive is immutable (F9). Git runs read-only through `gitsafe` (no host config, hooks or fsmonitor): one
  `git log` to find the pre-turn commit and one `git archive` to materialise it. Neither touches the index, and
  `git status` / `git diff` never run against the archived work tree.
- The tamper rule (STRIDE T): the base is the root of the first-parent chain and carries the builder's exact message
  `<task> base (<ver12>)`. A pack-on cell's pre-turn commit is the root's first-parent child, whose message is exactly
  `ai-forward pack revision <n>`; a pack-off cell's is the root. A later look-alike commit is ignored, and a missing
  or rewritten builder commit is NA `pre-turn commit not found in the working copy` (F11).
- The change set compares the materialised pre-turn tree with a grading copy of the working tree, by content with
  CRLF normalised, build output excluded on both sides (Simplifier 4). Files are hashed in bounded chunks and a
  symlink is compared by its target, never followed (F17).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tarfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from harness_bench import archive, gitsafe

NOT_FOUND = "pre-turn commit not found in the working copy"
PACK_SUBJECT = re.compile(r"ai-forward pack revision \d+")  # workspace.install_pack's message
BUILD_OUTPUT = frozenset({".git", "bin", "obj", "TestResults", "__pycache__"})  # never part of a tree, on either side
CHUNK = 1 << 20

__all__ = ["BUILD_OUTPUT", "NOT_FOUND", "change_set", "grading_copy", "pre_turn_commit", "pre_turn_tree"]


def pre_turn_commit(ws: Path, cell: Mapping, timeout: float) -> str | None:
    """The commit the agent's turn started from, or None when the builder's commits are not where the rule puts them."""
    if not (ws / ".git").exists():
        return None
    done = gitsafe.git(["log", "--first-parent", "--reverse", "--format=%H%x00%s"], cwd=ws, timeout=timeout, check=False)
    if done.timed_out or done.returncode != 0:
        return None
    chain = [line.split("\0", 1) for line in done.stdout.splitlines()[:2]]
    if not chain or chain[0][1:] != [f"{cell['task']} base ({cell['task_version'][:12]})"]:  # workspace.task_source
        return None
    if cell.get("pack") != "on":
        return chain[0][0]
    if len(chain) < 2 or len(chain[1]) != 2 or not PACK_SUBJECT.fullmatch(chain[1][1]):
        return None
    return chain[1][0]


@contextmanager
def pre_turn_tree(ws: Path, commit: str, dest: Path, timeout: float) -> Iterator[Path]:
    """`commit`'s tree at `dest` (from `git archive`, extracted with the tarfile data filter), removed on exit."""
    tar = dest.with_name(dest.name + ".tar")
    try:
        dest.mkdir(parents=True)
        gitsafe.git(["archive", "--format=tar", "-o", str(tar), commit], cwd=ws, timeout=timeout)
        with tarfile.open(tar) as t:
            t.extractall(dest, filter="data")
        tar.unlink()
        yield dest
    finally:
        tar.unlink(missing_ok=True)
        if dest.exists():
            shutil.rmtree(dest, onexc=archive.make_writable)


@contextmanager
def grading_copy(ws: Path, dest: Path) -> Iterator[Path]:
    """A disposable copy of the working tree at `dest`, without .git or build output, symlinks kept; removed on exit.

    Lifted here from the design's `grade/__init__.py` home (CORE s1 did not build it); a recorded deviation.
    """
    try:
        shutil.copytree(ws, dest, symlinks=True, ignore=shutil.ignore_patterns(*BUILD_OUTPUT))
        yield dest
    finally:
        if dest.exists():
            shutil.rmtree(dest, onexc=archive.make_writable)


def _files(root: Path) -> dict[str, Path]:
    out = {}
    for folder, dirs, names in os.walk(root):  # a symlinked folder is listed, never entered
        dirs[:] = [d for d in dirs if d not in BUILD_OUTPUT and not Path(folder, d).is_symlink()]
        for name in names:
            path = Path(folder, name)
            out[path.relative_to(root).as_posix()] = path
    return out


def _digest(path: Path) -> str:
    """sha256 of the content with CRLF read as LF, in bounded chunks; a symlink's digest is its target's text."""
    h = hashlib.sha256()
    if path.is_symlink():
        h.update(b"symlink\0" + os.readlink(path).encode())
        return h.hexdigest()
    carry = b""
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            chunk = carry + chunk
            carry = b"\r" if chunk.endswith(b"\r") else b""  # a CRLF split across two chunks
            h.update((chunk[:-1] if carry else chunk).replace(b"\r\n", b"\n"))
    h.update(carry)
    return h.hexdigest()


def change_set(before: Path, after: Path) -> dict[str, str]:
    """path -> added | changed | deleted, from the pre-turn tree `before` to the cell's tree `after`, sorted by path."""
    old, new = _files(before), _files(after)
    out = {p: "added" for p in new.keys() - old.keys()}
    out.update({p: "deleted" for p in old.keys() - new.keys()})
    out.update({p: "changed" for p in old.keys() & new.keys() if _digest(old[p]) != _digest(new[p])})
    return dict(sorted(out.items()))
