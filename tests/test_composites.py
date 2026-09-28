"""Tests for composites: normalisation, area composites, overall, and correctness-gated composites (S4).

T-C1 is the red-first test for S4. T-C1 and T-C2 are the hypothesis suites.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from harness_bench.composites import Catalog, area, gated, load_catalog, normalise, overall
from harness_bench.stats import Measure

ROOT = Path(__file__).resolve().parents[1]

# Test catalog with anchors (S4 does not depend on Leader's catalog edit)
TEST_CATALOG = Catalog(
    version="0.5.test",
    hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    metrics={
        "m1": {"id": "m1", "kind": "score", "weight": 1, "anchor": [0, 100], "better": "higher"},
        "m2": {"id": "m2", "kind": "score", "weight": 2, "anchor": [0, 100], "better": "higher"},
        "m3": {"id": "m3", "kind": "score", "weight": 1, "anchor": [0, 100], "better": "higher"},
        "m_low": {"id": "m_low", "kind": "score", "weight": 1, "anchor": [10, 0], "better": "lower"},
        "pass_at_1": {"id": "pass_at_1", "kind": "score", "weight": 0, "better": "higher"},
    },
    areas={
        "correctness": ("m1", "m2", "m3", "pass_at_1"),
        "cost": ("m_low",),
        "rigor": (),
        "drift": (),
        "specification": (),
        "autonomy": (),
        "coordination": (),
    },
    has_anchors=True,
)

_zero_differs_hits = 0


@settings(max_examples=100)
@given(
    v1=st.integers(min_value=1, max_value=100).map(Decimal),
    v2=st.integers(min_value=1, max_value=100).map(Decimal),
    v3=st.integers(min_value=1, max_value=100).map(Decimal),
)
@example(v1=Decimal(50), v2=Decimal(80), v3=Decimal(90))
def _tc1_property(v1: Decimal, v2: Decimal, v3: Decimal):
    """T-C1 property over generated score sets."""
    global _zero_differs_hits
    s_na = {
        "m1": Measure(None, "missing"),
        "m2": Measure(v2),
        "m3": Measure(v3),
    }
    s_without_m = {
        "m2": Measure(v2),
        "m3": Measure(v3),
    }
    s_zero = {
        "m1": Measure(Decimal(0)),
        "m2": Measure(v2),
        "m3": Measure(v3),
    }

    comp_na, excluded = area(s_na, "correctness", TEST_CATALOG)
    comp_without, _ = area(s_without_m, "correctness", TEST_CATALOG)
    comp_zero, _ = area(s_zero, "correctness", TEST_CATALOG)

    # composite(S) with m NA equals composite(S without m), weights renormalised
    assert comp_na.value == comp_without.value
    assert ("m1", "missing") in excluded

    # Where that differs from the composite with m's normalised score set to 0,
    # setting m to 0 gives a different result. Count the zero-differs branch.
    if comp_na.value != comp_zero.value:
        _zero_differs_hits += 1


def test_tc1_overlap_composite_renormalises_weights():
    """T-C1 red first: property over generated score sets with counted zero-differs branch."""
    global _zero_differs_hits
    _zero_differs_hits = 0
    _tc1_property()
    assert _zero_differs_hits > 0


def test_tc1_deterministic_example():
    """T-C1 one example test kept: m NA equals m omitted, differs from m=0."""
    s_na = {"m1": Measure(None, "missing"), "m2": Measure(Decimal(80)), "m3": Measure(Decimal(90))}
    s_without = {"m2": Measure(Decimal(80)), "m3": Measure(Decimal(90))}
    s_zero = {"m1": Measure(Decimal(0)), "m2": Measure(Decimal(80)), "m3": Measure(Decimal(90))}

    comp_na, excluded = area(s_na, "correctness", TEST_CATALOG)
    comp_without, _ = area(s_without, "correctness", TEST_CATALOG)
    comp_zero, _ = area(s_zero, "correctness", TEST_CATALOG)

    assert comp_na.value == comp_without.value
    assert comp_zero.value != comp_na.value
    assert ("m1", "missing") in excluded
