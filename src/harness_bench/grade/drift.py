"""Blast-radius diff, convention rules, MTAC-IFBench constraint checklists, instruction re-read rate.

Metrics: spec_coverage, scope_creep, constraint_violations, convention_drift, instruction_reread_rate.
Spec: S-08c (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    return {m: Score(None, "not built") for m in inp.metrics}  # GR-CODE c3 red: what the runner writes today
