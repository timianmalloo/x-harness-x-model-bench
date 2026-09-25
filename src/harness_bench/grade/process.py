"""Autonomy and process metrics from the normalised trajectory.

Metrics: completion_without_intervention, stuck_loops, recovery_rate, tool_error_rate, planning_ratio, time_to_first_green.
Not in the proposal's grade/ layout; added because area 6 metrics had no owner.
Spec: S-08c (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.process is not built yet; spec S-08c in docs/specs/README.md")
