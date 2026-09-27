"""Bootstrap core (design phase4-statistics, slice S1): T-S1 is the red-first test."""

from decimal import Decimal

from harness_bench.stats import Interval, Obs, Params, interval


def test_ts1_fewer_than_two_tasks_is_not_a_zero_interval():
    """T-S1: one task has no interval; no task is a point NA. Never a zero-width interval, never 0."""
    one = interval([Obs("A", 1, Decimal(1)), Obs("A", 2, Decimal(3))], Params(), "k")
    assert one.reason == "interval not computed (n < 2)"
    assert one.lo is None and one.hi is None
    assert one.n == 1
    assert one.point == Decimal(2)
    assert one.point != Decimal(0)
    assert not (one.lo is not None and one.lo == one.hi)

    none = interval([], Params(), "k")
    assert isinstance(none, Interval)
    assert none.point is None
    assert none.lo is None and none.hi is None
    assert none.n == 0
    assert none.reason == "not computed (no valid cell with a value)"
    assert none.point != Decimal(0)
