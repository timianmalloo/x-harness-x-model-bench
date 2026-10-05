"""Tests for grade/noguess.py skeleton and registration (W1-L rev 2 section 7; X-LG)."""

from __future__ import annotations

from pathlib import Path

from harness_bench import errors, identity
from harness_bench.grade import Score, noguess
from harness_bench.grade import property as property_grader
from harness_bench.grade.property import GradeContext


def test_noguess_unresolved_count():
    """W1-L section 15 K3: count == 2 fails on -1 by assertion, never KeyError/ImportError."""
    count, unresolved_names = noguess.unresolved(
        Path("workspace"),
        ["src/cachetools/limiter.py"],
        Path("vendor/quotakit"),
    )
    assert count == 2
    assert unresolved_names == ["quotakit.RateLimiter", "quotakit.RateLimitExceeded"]


def test_noguess_strategy_registered():
    """W1-L section 3 K3: STRATEGIES['no-guessing'] registered to noguess.grade."""
    assert "no-guessing" in property_grader.STRATEGIES
    assert property_grader.STRATEGIES["no-guessing"] is noguess.grade


def test_errors_hb_rdy_009_meaning():
    """W0 rev 6.10 section 11: HB-RDY-009 text has the built meaning."""
    assert errors.RUN_CODES["HB-RDY-009"] == (
        "a frozen task value differs from the canonical function's output (HASH-A)"
    )


def test_identity_planned_noguess_retired():
    """W0 rev 6.10 R6.10a: grade/noguess.py is classed and retired from PLANNED."""
    assert "grade/noguess.py" not in identity.PLANNED
    assert identity.CLASSES["grade/noguess.py"] == "grade"


def test_noguess_grade_skeleton_returns_scores():
    """Skeleton grade() returns Score(None, 'not built') for metrics."""
    metrics = ["property_check_pass", "hallucinated_symbol_errors", "verified_before_use"]

    import types

    inp = types.SimpleNamespace(metrics=metrics)
    res = noguess.grade(inp, GradeContext(30.0))  # type: ignore[arg-type]
    assert set(res.keys()) == set(metrics)
    for score in res.values():
        assert isinstance(score, Score)
        assert score.value is None
        assert score.reason == "not built"
