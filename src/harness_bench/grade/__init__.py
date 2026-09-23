"""Graders: one module per metric family, each a pure function of an archived run.

Rules (proposal, "Grading pipeline"):
- Deterministic before judged. A judge never scores what a script can measure.
- Re-grading an archived run reproduces every score byte-for-byte (judges: pinned model,
  temperature 0, verdicts cached on artifact hashes).
- Every score carries an evidence pointer (file, line, log offset).
- A measurement that does not exist is NOT_RECORDED and is excluded from composites. Never 0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Score:
    value: float
    evidence: str  # "path[:line]" or "path@offset", relative to the run directory
    unit: str = ""


class _NotRecorded:
    """Sentinel: the metric was not measured for this run. Excluded from composites."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NOT_RECORDED"

    def __bool__(self) -> bool:
        return False


NOT_RECORDED = _NotRecorded()

Result = dict[str, "Score | _NotRecorded"]


def not_built(module: str, spec: str) -> NotImplementedError:
    return NotImplementedError(f"grade.{module} is not built yet; spec {spec} in docs/specs/README.md")


__all__ = ["NOT_RECORDED", "Result", "Score", "not_built"]
