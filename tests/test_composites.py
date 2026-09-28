"""Tests for composites: normalisation, area composites, overall, and correctness-gated composites (S4).

T-C1 is the red-first test for S4. T-C1 and T-C2 are the hypothesis suites.
T-C1..C5 and the real catalog normalisation test are covered here.
"""

from decimal import Decimal
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st

from harness_bench import config
from harness_bench.composites import (
    Catalog,
    area,
    gated,
    load_catalog,
    normalise,
    overall,
)
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


@settings(max_examples=100)
@given(
    x1=st.integers(min_value=-150, max_value=250).map(Decimal),
    x2=st.integers(min_value=-150, max_value=250).map(Decimal),
)
def _tc2_higher_property(x1: Decimal, x2: Decimal):
    """T-C2: normalisation is monotone in better's direction and bounded to 0-100 (better: higher)."""
    m1_worst = Decimal(0)
    m1_best = Decimal(100)
    n1 = normalise("m1", Measure(x1), TEST_CATALOG).value
    n2 = normalise("m1", Measure(x2), TEST_CATALOG).value
    assert n1 is not None and n2 is not None
    assert Decimal(0) <= n1 <= Decimal(100)
    assert Decimal(0) <= n2 <= Decimal(100)
    if x1 <= x2:
        assert n1 <= n2
    if x1 <= m1_worst:
        assert n1 == Decimal(0)
    if x1 >= m1_best:
        assert n1 == Decimal(100)


@settings(max_examples=100)
@given(
    x1=st.integers(min_value=-20, max_value=30).map(Decimal),
    x2=st.integers(min_value=-20, max_value=30).map(Decimal),
)
def _tc2_lower_property(x1: Decimal, x2: Decimal):
    """T-C2: normalisation is monotone in better's direction and bounded to 0-100 (better: lower)."""
    m_worst = Decimal(10)
    m_best = Decimal(0)
    n1 = normalise("m_low", Measure(x1), TEST_CATALOG).value
    n2 = normalise("m_low", Measure(x2), TEST_CATALOG).value
    assert n1 is not None and n2 is not None
    assert Decimal(0) <= n1 <= Decimal(100)
    assert Decimal(0) <= n2 <= Decimal(100)
    if x1 <= x2:
        assert n1 >= n2
    if x1 >= m_worst:
        assert n1 == Decimal(0)
    if x1 <= m_best:
        assert n1 == Decimal(100)


def test_tc2_normalisation_is_monotone_and_bounded():
    """T-C2: normalisation is monotone in better's direction, bounded to 0-100, saturates at anchors."""
    _tc2_higher_property()
    _tc2_lower_property()


def test_tc3_catalog_hash_mismatch_gives_na_with_both_versions():
    """T-C3: a pass whose catalog_hash differs from the loaded one -> NA with both versions named."""
    res = normalise(
        "m1",
        Measure(Decimal(50)),
        TEST_CATALOG,
        pass_catalog_version="0.4",
        pass_catalog_hash="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
    )
    assert res.value is None
    assert res.reason is not None
    assert "graded under catalog 0.4 (fedcba987654)" in res.reason
    assert f"the loaded catalog is {TEST_CATALOG.version} ({TEST_CATALOG.hash[:12]})" in res.reason


def test_tc4_validate_refuses_worst_equals_best_and_contradictory_direction():
    """T-C4: bench validate refuses worst == best, and refuses a direction that disagrees with better."""
    graders = config.grader_modules(ROOT)
    # worst == best
    cat1 = {
        "schema": "bench-metrics/1",
        "areas": {
            "correctness": {
                "metrics": [
                    {"id": "m_bad", "source": ["D"], "better": "higher", "grader": "correctness", "kind": "score", "weight": 1, "anchor": [10, 10]},
                ]
            },
            "cost": {"metrics": []}, "rigor": {"metrics": []}, "drift": {"metrics": []},
            "specification": {"metrics": []}, "autonomy": {"metrics": []}, "coordination": {"metrics": []},
        },
    }
    p1 = config.Problems()
    config.validate_metrics(cat1, p1, graders, root=ROOT)
    assert any("anchor worst == best" in i for i in p1.items)

    # direction contradicts better: higher with worst > best
    cat2 = {
        "schema": "bench-metrics/1",
        "areas": {
            "correctness": {
                "metrics": [
                    {"id": "m_bad2", "source": ["D"], "better": "higher", "grader": "correctness", "kind": "score", "weight": 1, "anchor": [10, 0]},
                ]
            },
            "cost": {"metrics": []}, "rigor": {"metrics": []}, "drift": {"metrics": []},
            "specification": {"metrics": []}, "autonomy": {"metrics": []}, "coordination": {"metrics": []},
        },
    }
    p2 = config.Problems()
    config.validate_metrics(cat2, p2, graders, root=ROOT)
    assert any("anchor direction contradicts better" in i for i in p2.items)

    # direction contradicts better: lower with worst < best
    cat3 = {
        "schema": "bench-metrics/1",
        "areas": {
            "correctness": {
                "metrics": [
                    {"id": "m_bad3", "source": ["D"], "better": "lower", "grader": "correctness", "kind": "score", "weight": 1, "anchor": [0, 10]},
                ]
            },
            "cost": {"metrics": []}, "rigor": {"metrics": []}, "drift": {"metrics": []},
            "specification": {"metrics": []}, "autonomy": {"metrics": []}, "coordination": {"metrics": []},
        },
    }
    p3 = config.Problems()
    config.validate_metrics(cat3, p3, graders, root=ROOT)
    assert any("anchor direction contradicts better" in i for i in p3.items)


def test_tc5_gated_composite_rules():
    """T-C5: the gated composite rules.

    - pass_at_1 = 0 gives 0 even when overall is NA.
    - pass_at_1 = 1 and overall NA gives NA with overall's reason.
    - pass_at_1 NA gives NA with pass_at_1's reason.
    - overall is NA only when all seven areas are NA: six NA and one present gives that one area's value.
    """
    # All areas NA -> overall is NA
    scores_all_na = {
        "pass_at_1": Measure(Decimal(0)),
        "m1": Measure(None, "missing"),
        "m2": Measure(None, "missing"),
        "m3": Measure(None, "missing"),
        "m_low": Measure(None, "missing"),
    }
    ov = overall(scores_all_na, TEST_CATALOG)
    assert ov.value is None

    # Row 1: pass_at_1 = 0 gives 0 even when overall is NA
    g0 = gated(scores_all_na, TEST_CATALOG)
    assert g0.value == Decimal(0)
    assert g0.reason is None

    # Row 2: pass_at_1 = 1 and overall NA gives NA with overall's reason
    scores_p1_one = dict(scores_all_na)
    scores_p1_one["pass_at_1"] = Measure(Decimal(1))
    g1 = gated(scores_p1_one, TEST_CATALOG)
    assert g1.value is None
    assert g1.reason == ov.reason

    # Row 3: pass_at_1 NA gives NA with pass_at_1's reason
    scores_p1_na = dict(scores_all_na)
    scores_p1_na["pass_at_1"] = Measure(None, "untested")
    gna = gated(scores_p1_na, TEST_CATALOG)
    assert gna.value is None
    assert gna.reason == "untested"

    # Six NA and one area present gives that one area's value
    # In TEST_CATALOG, cost has m_low, correctness has m1, m2, m3. Other 5 areas are empty (so NA).
    scores_one_area = {
        "pass_at_1": Measure(Decimal(1)),
        "m1": Measure(Decimal(75)),  # correctness area has value 75
        "m2": Measure(Decimal(75)),
        "m3": Measure(Decimal(75)),
        "m_low": Measure(None, "missing"),  # cost area NA
    }
    ov_one = overall(scores_one_area, TEST_CATALOG)
    assert ov_one.value == Decimal(75)
    g_one = gated(scores_one_area, TEST_CATALOG)
    assert g_one.value == Decimal(75)


def test_real_catalog_every_weighted_score_metric_normalises_without_error():
    """Loads the real bench/metrics.yaml and asserts every kind: score, weight > 0 metric normalises without error."""
    cat = load_catalog(ROOT)
    assert cat.has_anchors
    weighted_score_metrics = [
        m for m in cat.metrics.values()
        if m.get("kind") == "score" and m.get("weight", 0) > 0
    ]
    assert len(weighted_score_metrics) > 0
    for m in weighted_score_metrics:
        mid = m["id"]
        worst, best = Decimal(str(m["anchor"][0])), Decimal(str(m["anchor"][1]))
        res_worst = normalise(mid, Measure(worst), cat)
        res_best = normalise(mid, Measure(best), cat)
        assert res_worst.value == Decimal(0), f"{mid} at worst did not give 0"
        assert res_best.value == Decimal(100), f"{mid} at best did not give 100"
        midpoint = (worst + best) / Decimal(2)
        res_mid = normalise(mid, Measure(midpoint), cat)
        assert res_mid.value == Decimal(50), f"{mid} at midpoint did not give 50"
