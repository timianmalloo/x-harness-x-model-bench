"""Blast-radius diff, convention rules, MTAC-IFBench constraint checklists, instruction re-read rate.

Metrics: spec_coverage, scope_creep, constraint_violations, convention_drift, instruction_reread_rate.
Spec: S-08c (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("drift", "S-08c")
