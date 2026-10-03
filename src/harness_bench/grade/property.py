"""Property grader (ADR-0018, ADR-0019): property_check_pass and the property-tagged metrics.

Design: docs/design/eval-property-grader.md (W1-F rev 3); seams: docs/design/eval-seam-contracts.md (W0 rev 6.9).
This module holds the pure core first (F2): `at_scale`, `check_segment`, the result-line validator, the ordered
outcome table `_classify` (W0 section 3, rows 1-7: the first match decides) and the scoring of an accepted run.
The check runner, the probe host and `grade_cell` follow in their own commits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from harness_bench.grade import Score

__all__ = ["Classification", "Facts", "at_scale", "check_segment", "parse_result", "score_run"]

MAX_RESULT_BYTES = 64 * 1024
PROBE_OUTCOMES = frozenset({"blocked", "exploited", "timeout"})
DELIVERABLES = frozenset({"ran", "did not build", "did not start"})


@dataclass(frozen=True)
class Classification:
    row: int  # W0 section 3's row (1-7); every precedence test asserts it
    code: str | None  # HB-CHK-00n, or None for rows 6 and 7
    reason: str | None  # the NA reason (rows 1-5) or the deliverable text (row 6)


@dataclass(frozen=True)
class Facts:
    """What `_classify` reads. The defaults are an honest, clean run."""

    tests_suspended: bool = False
    check_suspended: bool = False
    bound_fired: bool = False
    hash_before: str = "h"
    hash_after: str = "h"
    alone_at_arrival: bool = True  # the first-byte job view was exactly the check
    documents: int = 1
    trailing_bytes: int = 0
    exit_before_line: bool = False  # exit_ft <= first_byte_ft
    has_line: bool = True
    exit_code: int | None = 0
    line_valid: bool = True  # the row-5 verdict of `parse_result`
    deliverable: str = "ran"


def at_scale(value, scale):
    return value


def check_segment(kind: str, name: str, rx: re.Pattern[str]) -> None:
    return None


def parse_result(line: bytes, declared: list[str], allowed_measures: frozenset[str], scales: dict[str, int | None]):
    return None


def _classify(facts: Facts) -> Classification:
    return Classification(7, None, None)


def score_run(cls: Classification, hidden_tests: Score, outcomes: list[str]) -> dict[str, Score]:
    return {}


_ = (Decimal, DELIVERABLES, PROBE_OUTCOMES, MAX_RESULT_BYTES)
