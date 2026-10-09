"""L-SUM-A: stats.paired_ratio is the ratio of totals on paired_delta's draw.

The hand case has two shared tasks. A is ref 1+1 and treat 10; B is ref 10 and
treat 10. C and D sit in one arm only. The point is 20/12. A resample draws two
tasks, and each pool is constant, so the only ratios are 5 (A, A), 1 (B, B) and
20/12 (one of each). With 2,000 resamples the 2.5% tails are 1 and 5. A mean of
per-task ratios would put (A, A) at 10.
"""

from decimal import Context, Decimal, localcontext

import harness_bench.stats as stats
from harness_bench.stats import Interval, Obs, Params

# Shared A, B. C is reference-only, D is treatment-only. Point 20/12, tails 1 and 5.
HAND_REF = [
    Obs("A", 1, Decimal(1)),
    Obs("A", 2, Decimal(1)),
    Obs("B", 1, Decimal(10)),
    Obs("C", 1, Decimal(100)),
]
HAND_TREAT = [
    Obs("A", 1, Decimal(10)),
    Obs("B", 1, Decimal(10)),
    Obs("D", 1, Decimal(100)),
]

# One pair per task. The two tasks differ, so task resampling has nonzero width.
REUSE_REF = [Obs("t1", 1, Decimal(1)), Obs("t2", 1, Decimal(4))]
REUSE_TREAT = [Obs("t1", 1, Decimal(2)), Obs("t2", 1, Decimal(4))]


def test_paired_ratio_matches_a_hand_computed_reference():
    """Point 20/12, interval [1, 5]. Swapping the arms takes the reciprocal."""
    assert hasattr(stats, "paired_ratio")
    forward = stats.paired_ratio(HAND_REF, HAND_TREAT, ("a", "b"), Params(), "lean|ratio")
    assert isinstance(forward, Interval)
    assert forward.n == 2
    assert forward.reason is None
    assert forward.point == Decimal(20) / Decimal(12)
    assert forward.lo == Decimal(1)
    assert forward.hi == Decimal(5)
    assert forward.lo != forward.hi
    backward = stats.paired_ratio(HAND_TREAT, HAND_REF, ("b", "a"), Params(), "lean|ratio")
    assert backward.point == Decimal(12) / Decimal(20)
    assert backward.lo == Decimal(1) / Decimal(5)
    assert backward.hi == Decimal(1)
    again = stats.paired_ratio(HAND_REF, HAND_TREAT, ("a", "b"), Params(), "lean|ratio")
    assert again == forward


def test_paired_ratio_interval_has_nonzero_width_when_tasks_differ():
    """REUSE-A: one pair per task, differing tasks, the interval is not a point."""
    assert hasattr(stats, "paired_ratio")
    iv = stats.paired_ratio(REUSE_REF, REUSE_TREAT, ("a", "b"), Params(), "lean|reuse")
    assert isinstance(iv, Interval)
    assert iv.n == 2
    assert iv.reason is None
    assert iv.point == Decimal(6) / Decimal(5)
    assert iv.lo == Decimal(1)
    assert iv.hi == Decimal(2)
    assert iv.lo != iv.hi


def test_paired_ratio_fewer_than_two_shared_tasks_is_not_a_zero_interval():
    """One shared task keeps the point and no interval. No shared task is not recorded."""
    assert hasattr(stats, "paired_ratio")
    params = Params()
    one = stats.paired_ratio(
        [Obs("A", 1, Decimal(2)), Obs("A", 2, Decimal(4)), Obs("Z", 1, Decimal(9))],
        [Obs("A", 1, Decimal(3)), Obs("Y", 1, Decimal(8))],
        ("a", "b"),
        params,
        "one",
    )
    assert one.n == 1
    assert one.point == Decimal(3) / Decimal(6)
    assert one.lo is None and one.hi is None
    assert one.reason == "interval not computed (n < 2)"
    assert one.point != Decimal(0)
    assert not (one.lo is not None and one.lo == one.hi)
    none = stats.paired_ratio(
        [Obs("A", 1, Decimal(1))],
        [Obs("B", 1, Decimal(2))],
        ("a", "b"),
        params,
        "none",
    )
    assert none.point is None
    assert none.lo is None and none.hi is None
    assert none.n == 0
    assert none.reason == "not computed (no valid cell with a value)"
    assert none.point != Decimal(0)


def test_paired_ratio_ignores_the_ambient_decimal_context():
    """A caller's precision cannot move the point (the same rule as paired_delta)."""
    assert hasattr(stats, "paired_ratio")
    with localcontext(Context(prec=6)):
        iv = stats.paired_ratio(HAND_REF, HAND_TREAT, ("a", "b"), Params(), "lean|ratio")
    assert format(iv.point, "f") == "1.666666666666666666666666667"
    assert iv.lo == Decimal(1)
    assert iv.hi == Decimal(5)
