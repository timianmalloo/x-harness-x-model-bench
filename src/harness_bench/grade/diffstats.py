"""Simplicity strategy helper (W1-L rev 2 section 8; diffstats).

Measures size_vs_reference, new_abstractions, new_dependencies, and outside_radius_lines
over the non-test files of the tree.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
import tempfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_bench.grade import CellInput, Score, _changes

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["grade", "measure"]


def _classes(text: str) -> set[str]:
    out: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                out.add(prefix + child.name)
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


def _imports(text: str) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _scan(files: Mapping[str, Path], base_paths: frozenset[str]) -> tuple[set[str], set[str]]:
    """(`path:qualified class` keys, top-level imported modules) over the non-test `.py` files of one tree."""
    classes: set[str] = set()
    imports: set[str] = set()
    for rel_path, p in files.items():
        if not rel_path.endswith(".py") or _changes.is_test_path(rel_path, base_paths):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        classes |= {f"{rel_path}:{c}" for c in _classes(text)}
        imports |= _imports(text)
    return classes, imports


def measure(
    base: Path | dict[str, str],
    final: Path | dict[str, str],
    radius: Sequence[str],
    package: str = "",
    size_reference_lines: int = 1,
    ceilings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure simplicity metrics between base and final trees."""
    if isinstance(base, dict) or isinstance(final, dict):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_dir = tmp_path / "base"
            final_dir = tmp_path / "final"
            base_dir.mkdir(parents=True, exist_ok=True)
            final_dir.mkdir(parents=True, exist_ok=True)
            if isinstance(base, Path):
                _changes.copy_tree(base, base_dir, ignore=_changes.BUILD_OUTPUT)
            else:
                for rel, text in base.items():
                    p = base_dir / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(text, encoding="utf-8", newline="\n")
            if isinstance(final, Path):
                _changes.copy_tree(final, final_dir, ignore=_changes.BUILD_OUTPUT)
            else:
                for rel, text in final.items():
                    p = final_dir / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(text, encoding="utf-8", newline="\n")
            return measure(
                base_dir,
                final_dir,
                radius,
                package=package,
                size_reference_lines=size_reference_lines,
                ceilings=ceilings,
            )

    base_files = _changes._files(base)
    base_paths = frozenset(base_files.keys())
    final_files = _changes._files(final)

    changes = _changes.change_set(base, final)

    inside = 0
    outside = 0
    for rel_path, status in changes.items():
        if not rel_path.endswith(".py") or _changes.is_test_path(rel_path, base_paths):
            continue
        old_lines = _changes.product_lines(base / rel_path) if status != "added" else []
        new_lines = _changes.product_lines(final / rel_path) if status != "deleted" else []
        added_indices, _ = _changes.line_delta(old_lines, new_lines)
        n = len(added_indices)
        if _changes.in_radius(rel_path, list(radius)):
            inside += n
        else:
            outside += n

    base_classes, base_imports = _scan(base_files, base_paths)
    final_classes, final_imports = _scan(final_files, base_paths)
    new_abstractions = len(final_classes - base_classes)

    pkg_set = {package} if package else set()
    if not package and radius:
        first_seg = radius[0].replace("\\", "/").split("/")[0]
        if first_seg.isidentifier():
            pkg_set.add(first_seg)

    deps = final_imports - base_imports - set(sys.stdlib_module_names) - pkg_set
    new_dependencies = len(deps)

    size_ref = Decimal(size_reference_lines) if size_reference_lines > 0 else Decimal(1)
    size_vs_ref = Decimal(f"{Decimal(inside) / size_ref:.4f}")

    clause: str | None = None
    if ceilings is not None:
        if "size_vs_reference" in ceilings and size_vs_ref > Decimal(str(ceilings["size_vs_reference"])):
            clause = "size"
        elif "new_abstractions" in ceilings and new_abstractions > int(ceilings["new_abstractions"]):
            clause = "abstractions"
        elif "new_dependencies" in ceilings and new_dependencies > int(ceilings["new_dependencies"]):
            clause = "dependencies"
        elif "outside_radius_lines" in ceilings and outside > int(ceilings["outside_radius_lines"]):
            clause = "scope"

    return {
        "size_vs_reference": size_vs_ref,
        "new_abstractions": new_abstractions,
        "new_dependencies": new_dependencies,
        "outside_radius_lines": outside,
        "inside_lines": inside,
        "clause": clause,
    }


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade simplicity property task (W1-L section 8)."""
    from harness_bench.grade.property import hidden_tests, write_section

    tree = inp.archive / "ws"
    hidden = hidden_tests(inp, tree, "tests")

    timeout = ctx.timeout
    commit = _changes.pre_turn_commit(tree, inp.cell, timeout)
    if commit is None:
        na_score = Score(None, _changes.NOT_FOUND)
        pass_val = 0 if hidden.value == 0 else None
        pass_reason = hidden.reason if hidden.value != 0 else None
        scores = {
            "property_check_pass": Score(pass_val, pass_reason),
            "size_vs_reference": na_score,
            "new_abstractions": na_score,
            "new_dependencies": na_score,
        }
        evidence_ptr = write_section(inp, "simplicity", {
            "hidden_tests_pass": {"value": hidden.value, "reason": hidden.reason},
            "error": _changes.NOT_FOUND,
        })
        scores = {k: dataclasses.replace(v, evidence=evidence_ptr) for k, v in scores.items()}
        return {k: scores[k] for k in inp.metrics if k in scores}

    radius = inp.task.get("blast_radius", [])
    prop = inp.task.get("property") or {}
    ceilings = prop.get("ceilings") or {}
    size_reference_lines = prop.get("size_reference_lines", 1)

    work_root = inp.work_root or inp.out_dir
    with _changes.pre_turn_tree(tree, commit, work_root / "pre-turn", timeout) as base:
        stats = measure(
            base,
            tree,
            radius,
            size_reference_lines=size_reference_lines,
            ceilings=ceilings,
        )

    if hidden.value == 0:
        deciding_clause = "tests"
        pass_score = Score(0, None)
    elif hidden.value is None:
        deciding_clause = "tests"
        pass_score = Score(None, hidden.reason)
    else:
        if stats["clause"] is not None:
            deciding_clause = stats["clause"]
            pass_score = Score(0, None)
        else:
            deciding_clause = None
            pass_score = Score(1, None)

    section_data: dict[str, Any] = {
        "hidden_tests_pass": {"value": hidden.value, "reason": hidden.reason},
        "size_vs_reference": str(stats["size_vs_reference"]),
        "new_abstractions": stats["new_abstractions"],
        "new_dependencies": stats["new_dependencies"],
        "inside_lines": stats["inside_lines"],
        "outside_radius_lines": stats["outside_radius_lines"],
        "clause": deciding_clause,
    }

    evidence_ptr = write_section(inp, "simplicity", section_data)
    scores = {
        "property_check_pass": dataclasses.replace(pass_score, evidence=evidence_ptr),
        "size_vs_reference": Score(stats["size_vs_reference"], None, evidence=evidence_ptr),
        "new_abstractions": Score(stats["new_abstractions"], None, evidence=evidence_ptr),
        "new_dependencies": Score(stats["new_dependencies"], None, evidence=evidence_ptr),
    }
    return {k: scores[k] for k in inp.metrics if k in scores}
