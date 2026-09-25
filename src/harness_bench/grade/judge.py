"""Rubric judging by two blind judges (one per vendor), scored alone, synthesized, disagreements flagged.

Metrics: honest_completion_claims, error_handling, goal_drift_slope, unrequested_behaviour, assumption_disclosure, spec_quality, adr_quality, handoff_fidelity, mast_failure_codes.
Judges never see the harness or model name. Pinned model, temperature 0, verdicts cached on artifact hash.
Spec: S-09 (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.judge is not built yet; spec S-09 in docs/specs/README.md")
