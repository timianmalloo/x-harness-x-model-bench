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
DIGEST_ALGORITHM = "sha256"
CACHE_CAPACITY = 32

_PRE_TURN_CACHE: dict[tuple[str, str, frozenset[str]], dict[str, str]] = {}

__all__ = [
    "BUILD_OUTPUT",
    "CACHE_CAPACITY",
    "DIGEST_ALGORITHM",
    "NOT_FOUND",
    "change_set",
    "clear_pre_turn_cache",
    "grading_copy",
    "pre_turn_commit",
    "pre_turn_tree",
    "tree_id",
]


class PreTurnPath(type(Path())):
    """A Path carrying its git tree object ID for pre-turn digest cache keying."""

    tree_id: str | None = None


def clear_pre_turn_cache() -> None:
    """Clear the process-scoped pre-turn digest cache."""
    _PRE_TURN_CACHE.clear()


def tree_id(ws: Path, commit: str, timeout: float) -> str | None:
    """The git tree object ID of `commit` (from `git rev-parse <commit>^{tree}`), or None when unreadable."""
    try:
        done = gitsafe.git(["rev-parse", f"{commit}^{{tree}}"], cwd=ws, timeout=timeout, check=False)
        if done.timed_out or done.returncode != 0:
            return None
        tid = done.stdout.strip()
        return tid if tid else None
    except (gitsafe.GitError, OSError):
        return None


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
    tid = tree_id(ws, commit, timeout)
    try:
        dest.mkdir(parents=True)
        gitsafe.git(["archive", "--format=tar", "-o", str(tar), commit], cwd=ws, timeout=timeout)
        with tarfile.open(tar) as t:
            t.extractall(dest, filter="data")
        tar.unlink()
        p = PreTurnPath(dest)
        p.tree_id = tid
        yield p
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


def _pre_turn_digests(before: Path, tid: str | None, bypass_cache: bool) -> dict[str, str]:
    if bypass_cache or tid is None:
        old_files = _files(before)
        return {p: _digest(path) for p, path in old_files.items()}
    key = (tid, DIGEST_ALGORITHM, BUILD_OUTPUT)
    cached = _PRE_TURN_CACHE.get(key)
    if cached is not None:
        return cached
    old_files = _files(before)
    digests = {p: _digest(path) for p, path in old_files.items()}
    if len(_PRE_TURN_CACHE) >= CACHE_CAPACITY:
        _PRE_TURN_CACHE.pop(next(iter(_PRE_TURN_CACHE)))
    _PRE_TURN_CACHE[key] = digests
    return digests


def change_set(
    before: Path,
    after: Path,
    *,
    tree_id: str | None = None,
    bypass_cache: bool = False,
) -> dict[str, str]:
    """path -> added | changed | deleted, from the pre-turn tree `before` to the cell's tree `after`, sorted by path."""
    tid = tree_id if tree_id is not None else getattr(before, "tree_id", None)
    old_digests = _pre_turn_digests(before, tid, bypass_cache)
    new = _files(after)
    old_keys = old_digests.keys()
    out = {p: "added" for p in new.keys() - old_keys}
    out.update({p: "deleted" for p in old_keys - new.keys()})
    out.update({p: "changed" for p in old_keys & new.keys() if old_digests[p] != _digest(new[p])})
    return dict(sorted(out.items()))
