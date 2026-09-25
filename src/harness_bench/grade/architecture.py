"""Dependency direction, layering and structural checks vs the reference architecture.

Metrics: architecture_conformance.
Reuse pack/evals assertion vocabulary for structural checks.
Spec: S-08d (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.architecture is not built yet; spec S-08d in docs/specs/README.md")
