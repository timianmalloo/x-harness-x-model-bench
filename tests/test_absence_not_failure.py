"""Tests for defect class ABS-A: absence read as failure (design eval-catalog-0-7.md §4.4, §11)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_bench"


def _scan_numeric_score_defaults(src_dir: Path) -> set[str]:
    """T-A1: Scan for numeric defaults in score lookups (shape 1)."""
    hits = set()
    for py_file in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if len(node.args) >= 2:
                    default_arg = node.args[1]
                    if isinstance(default_arg, ast.Call):
                        if isinstance(default_arg.func, ast.Name) and default_arg.func.id == "Measure":
                            if default_arg.args and isinstance(default_arg.args[0], ast.Constant) and isinstance(default_arg.args[0].value, (int, float)):
                                rel = py_file.relative_to(src_dir).as_posix()
                                hits.add(f"{rel}:{node.lineno}")
    return hits


def _scan_unrecorded_subtractions(src_dir: Path) -> set[str]:
    """T-A2: Scan for failure counts derived as n_pairs - passes (shape 2)."""
    hits = set()
    for py_file in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
                if isinstance(node.left, ast.Name) and node.left.id == "n_pairs":
                    if isinstance(node.right, ast.Name) and node.right.id.startswith("passes_"):
                        rel = py_file.relative_to(src_dir).as_posix()
                        hits.add(f"{rel}:{node.lineno}")
    return hits


def test_no_score_lookup_has_a_numeric_default(tmp_path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text('c.scores.get("x", Measure(0))\n', encoding="utf-8")
    assert _scan_numeric_score_defaults(tmp_path) == {"bad.py:1"}

    hits = _scan_numeric_score_defaults(SRC)
    assert hits == set(), f"numeric defaults found in score lookups: {hits}"


def test_no_failure_count_is_derived_as_n_minus_passes(tmp_path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text('failed = max(0, n_pairs - passes_on)\n', encoding="utf-8")
    assert _scan_unrecorded_subtractions(tmp_path) == {"bad.py:1"}

    hits = _scan_unrecorded_subtractions(SRC)
    assert hits == set(), f"subtraction of passes from n_pairs found: {hits}"
