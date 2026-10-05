"""No-guessing strategy helper (W1-L rev 2 section 7; R-97).

One producer per language (R-97 condition 1): for Python, the static resolver below; for a compiled language,
the correctness grader's build.log (compiler errors naming a missing member). That path is not built in E4
(no compiled no-guessing task exists): such a task scores NA not built for <runner>, never 0.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from harness_bench.grade import CellInput, Score, _changes

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["grade", "unresolved"]


def unresolved(
    tree: Path | str,
    radius: Sequence[str],
    vendor: Path | str,
) -> tuple[int, list[str]]:
    """Return (count, distinct_unresolved_names) for vendored API references inside radius.

    Skeleton implementation returning neutral out-of-range value (-1, []).
    """
    from harness_bench.grade.property import run_child

    _ = (tree, radius, vendor, _changes.in_radius, run_child)
    return -1, []


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade no-guessing property task (W1-L section 7). Skeleton returns NA not built."""
    from harness_bench.grade.property import hidden_tests, write_section

    _ = (ctx, hidden_tests, write_section)
    return dict.fromkeys(inp.metrics, Score(None, "not built"))
