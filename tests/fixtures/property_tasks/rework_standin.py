"""STAND-IN for the E2 rework measure (W1-L sections 5.1 and 6.1; W0 rev 6.6 section 13).

`grade/_changes.py` (`product_lines`, `line_delta`, `is_test_path`, `in_radius`) and `grade/rework.py` are X-J2's and have
not joined. X-RW's task tests need the numbers now, so this module implements the same published rules on plain text. It is
not the grader: a number it produces is Inferred, never provenance (FIXT-A). The `ready` follow-on deletes this file and
points the tests at the real functions once X-J2a and X-J2b have joined.
"""

from __future__ import annotations

import ast
import difflib
import fnmatch
import posixpath
from decimal import ROUND_HALF_EVEN, Decimal

TEST_NAMES = ("test_*.py", "*_test.py", "tests.py", "test.py", "conftest.py")


def product_lines(text: str) -> list[str]:
    """W1-L 5.1: lines that are not blank, not comment-only and not part of a docstring (found by `ast`)."""
    lines = text.replace("\r\n", "\n").split("\n")
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
    return [line for number, line in enumerate(lines, 1)
            if number not in skip and line.strip() and not line.strip().startswith("#")]


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


def is_test_path(path: str, base_paths: frozenset[str]) -> bool:
    """W0 rev 6.6 section 13: a test basename, or a path already in the base tree under a `tests`/`test` directory."""
    if any(fnmatch.fnmatchcase(posixpath.basename(path), pattern) for pattern in TEST_NAMES):
        return True
    return path in base_paths and any(part in ("tests", "test") for part in path.split("/")[:-1])


def measure(base: dict[str, str], snapshot: dict[str, str], final: dict[str, str], radius: list[str]) -> tuple[int, int]:
    """(|T1|, |C|) summed over the non-test `.py` files in the radius: W1-L 6.1 step 3."""
    base_paths = frozenset(base)
    t1_total = changed_total = 0
    for path in sorted(set(base) | set(snapshot) | set(final)):
        if not path.endswith(".py") or is_test_path(path, base_paths):
            continue
        if not any(fnmatch.fnmatchcase(path, pattern) for pattern in radius):
            continue
        before, after, last = (product_lines(tree.get(path, "")) for tree in (base, snapshot, final))
        t1 = set(line_delta(before, after)[0])
        removed = set(line_delta(after, last)[1])
        t1_total += len(t1)
        changed_total += len(t1 & removed)
    return t1_total, changed_total


def ratio(t1_total: int, changed_total: int) -> Decimal | None:
    """`rework_ratio` at scale 4; None (NA) when turn 1 added no product lines."""
    if t1_total == 0:
        return None
    return (Decimal(changed_total) / Decimal(t1_total)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
