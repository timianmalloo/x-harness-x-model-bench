"""Mutation score of agent-written tests: Stryker.NET for C#, mutmut for Python, run as external tools.

Metrics: mutation_score.
Spec: S-08b (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("mutation", "S-08b")
