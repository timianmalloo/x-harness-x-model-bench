"""Autonomy and process metrics from the normalised trajectory.

Metrics: completion_without_intervention, stuck_loops, recovery_rate, tool_error_rate, planning_ratio, time_to_first_green.
Not in the proposal's grade/ layout; added because area 6 metrics had no owner.
Spec: S-08c (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("process", "S-08c")
