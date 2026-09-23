"""Hidden tests, partial credit, regressions, pass@k and pass^k across repetitions.

Metrics: pass_at_1, pass_at_k, pass_hat_k, partial_credit, build_and_suite_clean, regression_count, behavioural_equivalence.
Spec: S-08b (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("correctness", "S-08b")
