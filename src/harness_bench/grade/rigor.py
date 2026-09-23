"""Analyzers (incl. LOA001-LOA102 when pack on), complexity, verification-before-done from the tool log.

Metrics: verification_before_done, test_quality, static_analysis_delta, maintainability, style_conformance.
Spec: S-08c (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("rigor", "S-08c")
