"""Simplicity strategy helper (W1-L rev 2 section 8; diffstats).

Measures size_vs_reference, new_abstractions, new_dependencies, and outside_radius_lines
over the non-test files of the tree.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_bench.grade import CellInput, Score, _changes

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["grade", "measure"]


def measure(
    base: Path | dict[str, str],
    final: Path | dict[str, str],
    radius: Sequence[str],
    package: str = "",
    size_reference_lines: int = 1,
    ceilings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure simplicity metrics between base and final trees. Skeleton returns -1 per field."""
    _ = (
        base,
        final,
        radius,
        package,
        size_reference_lines,
        ceilings,
        _changes.change_set,
        _changes.product_lines,
        _changes.in_radius,
        _changes.line_delta,
        _changes.is_test_path,
    )
    return {
        "size_vs_reference": Decimal(-1),
        "new_abstractions": -1,
        "new_dependencies": -1,
        "outside_radius_lines": -1,
        "inside_lines": -1,
        "clause": "not built",
    }


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade simplicity property task (W1-L section 8). Skeleton returns NA not built."""
    from harness_bench.grade.property import hidden_tests, write_section

    _ = (ctx, hidden_tests, write_section)
    return dict.fromkeys(inp.metrics, Score(None, "not built"))
