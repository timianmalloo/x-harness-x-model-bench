"""Task-specific grading. Runs after the shared graders listed in task.yaml.

Contract: a pure function of the archived run directory and this task folder.
Return raw metric values keyed by metric id from bench/metrics.yaml, each with an
evidence pointer. Return NOT_RECORDED for anything this task cannot measure.
"""

from pathlib import Path

from harness_bench.grade import NOT_RECORDED, Score


def grade(run_dir: Path, task_dir: Path) -> dict[str, Score]:
    return {"partial_credit": NOT_RECORDED}
