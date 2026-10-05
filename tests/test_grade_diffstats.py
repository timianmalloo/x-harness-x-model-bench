"""Tests for grade/diffstats.py skeleton and registration (W1-L rev 2 section 8; X-LG)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from harness_bench import identity
from harness_bench.grade import Score, diffstats
from harness_bench.grade import property as property_grader
from harness_bench.grade.property import GradeContext


def test_diffstats_measure_size():
    """W1-L section 15 K4: size == Decimal('3.5000') fails on -1 by assertion, never KeyError/ImportError."""
    stats = diffstats.measure(
        Path("base"),
        Path("final"),
        ["tinydb/table.py"],
    )
    assert stats["size_vs_reference"] == Decimal("3.5000")


def test_diffstats_strategy_registered():
    """W1-L section 3 K4: STRATEGIES['simplicity'] registered to diffstats.grade."""
    assert "simplicity" in property_grader.STRATEGIES
    assert property_grader.STRATEGIES["simplicity"] is diffstats.grade


def test_identity_planned_diffstats_retired():
    """W0 rev 6.10 R6.10a: grade/diffstats.py is classed and retired from PLANNED."""
    assert "grade/diffstats.py" not in identity.PLANNED
    assert identity.CLASSES["grade/diffstats.py"] == "grade"


def test_diffstats_grade_skeleton_returns_scores():
    """Skeleton grade() returns Score(None, 'not built') for metrics."""
    metrics = ["property_check_pass", "size_vs_reference", "new_abstractions", "new_dependencies"]

    import types

    inp = types.SimpleNamespace(metrics=metrics)
    res = diffstats.grade(inp, GradeContext(30.0))  # type: ignore[arg-type]
    assert set(res.keys()) == set(metrics)
    for score in res.values():
        assert isinstance(score, Score)
        assert score.value is None
        assert score.reason == "not built"
