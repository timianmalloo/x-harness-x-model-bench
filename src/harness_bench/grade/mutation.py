"""Mutation score of agent-written tests: Stryker.NET for C#, mutmut for Python, run as external tools.

Metrics: mutation_score.
Spec: S-08b (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.mutation is not built yet; spec S-08b in docs/specs/README.md")
