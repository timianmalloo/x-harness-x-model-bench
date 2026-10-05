"""Rework strategy helper (W1-L rev 2 section 6.1; W0 rev 6.6 section 13).

Measures rework_ratio on the turn-1 snapshot and final tree, turn1_tests_pass,
and derives turn 2 not reached from cell.turn_ended events against the plan.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_bench.grade import CellInput, Score, _changes

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["grade", "measure", "ratio"]


def measure(
    base: Path | str | dict[str, str],
    snapshot: Path | str | dict[str, str],
    final: Path | str | dict[str, str],
    radius: Sequence[str],
) -> tuple[int, int]:
    """Return (|T1|, |C|) summed over non-test .py files in radius.

    Skeleton implementation returning neutral values (0, 0).
    """
    _ = (base, snapshot, final, radius, _changes.product_lines, _changes.in_radius, _changes.line_delta, _changes.is_test_path)
    return 0, 0


def ratio(t1_total: int, changed_total: int) -> Decimal | None:
    """rework_ratio at scale 4; None (NA) when turn 1 added no product lines.

    Skeleton implementation returning neutral value None.
    """
    _ = (t1_total, changed_total)
    return None


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade rework property task (W1-L section 6.1). Skeleton returns NA not built."""
    _ = (inp, ctx)
    return dict.fromkeys(inp.metrics, Score(None, "not built"))
