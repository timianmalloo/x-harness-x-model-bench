"""Mutation score of agent-written tests: Stryker.NET for C#, mutmut for Python (design phase3-graders, Mutation).

- Metrics: mutation_score (scale 4, non-additive).
- Runs Stryker.NET in a grading copy (_changes.grading_copy; never in the archive).
- Mutates non-test .cs files added or changed relative to pre-turn tree.
- Tests with test projects added or changed relative to pre-turn tree.
- NA reasons: "no tests written", "no non-test source changed", "no mutants generated",
  "mutation tool not available", "mutation run failed: <exit code>".
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from harness_bench.grade import CellInput, Score

METRIC = "mutation_score"
SCALE = Decimal("0.0001")

__all__ = ["METRIC", "SCALE", "grade_cell"]


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    return {METRIC: Score(None, "not built")}
