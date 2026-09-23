"""Rubric judging by two blind judges (one per vendor), scored alone, synthesized, disagreements flagged.

Metrics: honest_completion_claims, error_handling, goal_drift_slope, unrequested_behaviour, assumption_disclosure, spec_quality, adr_quality, handoff_fidelity, mast_failure_codes.
Judges never see the harness or model name. Pinned model, temperature 0, verdicts cached on artifact hash.
Spec: S-09 (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("judge", "S-09")
