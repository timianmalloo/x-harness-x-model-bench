"""Dependency direction, layering and structural checks vs the reference architecture.

Metrics: architecture_conformance.
Reuse pack/evals assertion vocabulary for structural checks.
Spec: S-08d (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("architecture", "S-08d")
