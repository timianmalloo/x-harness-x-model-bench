"""Analyzers (incl. LOA001-LOA102 when pack on), complexity, verification-before-done from the tool log.

Metrics: verification_before_done, test_quality, static_analysis_delta, maintainability, style_conformance.
Spec: S-08c (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    return {m: Score(None, "not built") for m in inp.metrics}  # GR-CODE c5 red: what the runner writes today
