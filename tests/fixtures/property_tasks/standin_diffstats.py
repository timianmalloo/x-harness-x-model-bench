"""STAND-IN for X-LG's `diffstats.measure` and X-J2a's `_changes` four (W1-L 5.1, 8.1), for the SM tasks' `draft` ring.

Those functions are not on main yet. This module implements W1-L 5.1 and 8.1 and W0 rev 6.6's `is_test_path` just far
enough to measure the committed reference, naive, alt and variant trees, so every number the task records is observed
(FIXT-A) and not hand-derived. It is a second definition of the counting rule, named as such: the `ready` follow-on
deletes this file and asserts the same numbers through the real functions (HASH-A). `in_radius` is the real
`drift._in_radius`, not a copy.
"""

from __future__ import annotations

import ast
import difflib
import fnmatch
import sys
from decimal import Decimal

from harness_bench.grade.drift import _in_radius

TEST_BASENAMES = ("tests.py", "test.py", "conftest.py")


def is_test_path(path: str, base_paths: frozenset[str]) -> bool:
    """W0 rev 6.6 section 13: a test basename, or a path already in the base tree under a tests/test directory."""
    parts = path.split("/")
    name = parts[-1]
    if fnmatch.fnmatchcase(name, "test_*.py") or fnmatch.fnmatchcase(name, "*_test.py") or name in TEST_BASENAMES:
        return True
    return path in base_paths and any(p in ("tests", "test") for p in parts[:-1])


def product_lines(text: str) -> list[str]:
    """W1-L 5.1: not blank, not comment-only, not part of a docstring (found by ast)."""
    lines = text.replace("\r\n", "\n").split("\n")
    skip: set[int] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    for node in ast.walk(tree) if tree else ():
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                skip.update(range(first.lineno, first.end_lineno + 1))
    return [ln for n, ln in enumerate(lines, 1) if n not in skip and ln.strip() and not ln.strip().startswith("#")]


def added_lines(old: str, new: str) -> int:
    a, b = product_lines(old), product_lines(new)
    return sum(j2 - j1 for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if tag in ("insert", "replace"))


def _classes(text: str) -> set[str]:
    out: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                out.add(prefix + child.name)
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(text), "")
    return out


def _imports(text: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def measure(base: dict[str, str], final: dict[str, str], radius: list[str], package: str, size_reference_lines: int,
            ceilings: dict) -> dict:
    """The simplicity metrics and the primary for two trees given as {path: text} (only .py files matter)."""
    base_paths = frozenset(base)
    py = [p for p in set(base) | set(final) if p.endswith(".py") and not is_test_path(p, base_paths)]
    inside = outside = 0
    abstractions: set[str] = set()
    base_abstractions: set[str] = set()
    imports: set[str] = set()
    base_imports: set[str] = set()
    for path in sorted(py):
        old, new = base.get(path, ""), final.get(path, "")
        n = added_lines(old, new)
        if _in_radius(path, radius):
            inside += n
        else:
            outside += n
        abstractions |= {f"{path}:{c}" for c in _classes(new)} if new else set()
        base_abstractions |= {f"{path}:{c}" for c in _classes(old)} if old else set()
        imports |= _imports(new) if new else set()
        base_imports |= _imports(old) if old else set()
    deps = imports - base_imports - set(sys.stdlib_module_names) - {package}
    values = {
        "size_vs_reference": f"{Decimal(inside) / Decimal(size_reference_lines):.4f}",
        "new_abstractions": len(abstractions - base_abstractions),
        "new_dependencies": len(deps),
    }
    clause = ("size" if Decimal(values["size_vs_reference"]) > Decimal(ceilings["size_vs_reference"])
              else "abstractions" if values["new_abstractions"] > ceilings["new_abstractions"]
              else "dependencies" if values["new_dependencies"] > ceilings["new_dependencies"]
              else "scope" if outside > ceilings["outside_radius_lines"] else None)
    return {**values, "inside_lines": inside, "outside_radius_lines": outside, "clause": clause}
