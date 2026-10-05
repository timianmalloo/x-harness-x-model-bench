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

import ast
import difflib
import hashlib
import os
import re
import shutil
import tarfile
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from fnmatch import fnmatchcase
from pathlib import Path

from harness_bench import archive, config, gitsafe
from harness_bench.plan import cell_arm

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
    "copy_tree",
    "grading_copy",
    "in_radius",
    "is_test_path",
    "line_delta",
    "pre_turn_commit",
    "pre_turn_tree",
    "product_lines",
    "remove_tree",
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
    if cell_arm(cell) == config.ARM_OFF:
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


def copy_tree(src: Path, dest: Path, *, ignore: Iterable[str] = BUILD_OUTPUT, dirs_exist_ok: bool = False) -> list[str]:
    """Copy `src` to `dest` without entering a directory junction (RF-9, G16); the skipped paths, relative to `src`.

    `shutil.copytree` follows a junction and copies its target's files. A symlink is kept as a link; a junction (the
    one reparse point that is not a symlink) is left out and named in the returned list.
    """
    skipped: list[str] = []
    patterns = shutil.ignore_patterns(*ignore)

    def leave_out(folder: str, names: list[str]) -> set[str]:
        hit = set(patterns(folder, names))
        for name in names:
            if name not in hit and os.path.isjunction(os.path.join(folder, name)):
                hit.add(name)
                skipped.append(Path(folder, name).relative_to(src).as_posix())
        return hit

    shutil.copytree(src, dest, symlinks=True, ignore=leave_out, dirs_exist_ok=dirs_exist_ok)
    return skipped


def remove_tree(path: Path) -> None:
    """Remove a grading copy; a reparse point is unlinked and never chmod-ed or entered (RF-9)."""

    def force(func, target, _exc) -> None:
        if os.path.islink(target) or os.path.isjunction(target):
            try:
                os.unlink(target)
            except OSError:
                os.rmdir(target)
            return
        archive.make_writable(func, target, _exc)

    shutil.rmtree(path, onexc=force)


@contextmanager
def grading_copy(ws: Path, dest: Path) -> Iterator[Path]:
    """A disposable copy of the working tree at `dest`, without .git or build output, symlinks kept; removed on exit.

    Lifted here from the design's `grade/__init__.py` home (CORE s1 did not build it); a recorded deviation.
    """
    try:
        copy_tree(ws, dest)
        yield dest
    finally:
        if dest.exists():
            remove_tree(dest)


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


def product_lines(path: Path | str) -> list[str]:
    """W1-L 5.1: lines that are not blank, not comment-only, and not part of a docstring (found by ast)."""
    p = Path(path)
    if p.suffix != ".py" or not p.is_file():
        return []
    try:
        raw = p.read_bytes()
    except OSError:
        return []
    text = raw.replace(b"\r\n", b"\n").decode("utf-8")
    lines = text.split("\n")
    skip: set[int] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    skip.update(range(first.lineno, first.end_lineno + 1))
    return [
        line for number, line in enumerate(lines, 1)
        if number not in skip and line.strip() and not line.strip().startswith("#")
    ]


def in_radius(path: str, radius: list[str]) -> bool:
    # simplify: fnmatch, where `*` also crosses `/`, so `dir/**` is every file under dir; ceiling: the task globs are
    # `**`, `<dir>/**` or one file; upgrade trigger: a glob with a `*` inside a path segment.
    return any(fnmatchcase(path.replace("\\", "/"), glob) for glob in radius)


def line_delta(old: list[str], new: list[str]) -> tuple[list[int], list[int]]:
    """Indices of `new` lines added or replaced, and of `old` lines removed or replaced (SequenceMatcher, autojunk off)."""
    added: list[int] = []
    removed: list[int] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            added.extend(range(j1, j2))
        if tag in ("replace", "delete"):
            removed.extend(range(i1, i2))
    return added, removed


TEST_BASENAMES = ("tests.py", "test.py", "conftest.py")


def is_test_path(path: str, base_paths: frozenset[str]) -> bool:
    """W0 rev 6.6 section 13: a test basename, or a path already in the base tree under a tests/test directory."""
    norm = path.replace("\\", "/")
    parts = norm.split("/")
    name = parts[-1]
    if fnmatchcase(name, "test_*.py") or fnmatchcase(name, "*_test.py") or name in TEST_BASENAMES:
        return True
    return (norm in base_paths or path in base_paths) and any(part in ("tests", "test") for part in parts[:-1])


