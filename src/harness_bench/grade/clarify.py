"""Scripted-user log vs the oracle's annotated clarifications.

Metrics: ask_vs_assume, key_question_recall, key_question_precision.
Spec: S-08d (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("clarify", "S-08d")
