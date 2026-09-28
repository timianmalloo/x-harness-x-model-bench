"""Bootstrap core (design phase4-statistics, slice S1).

T-S1 is the red-first test. T-S3 is the hypothesis suite. T-S4 pins the stream and one
interval as exact strings. T-S8's covered count is a characterization (D6).
"""

import json
import random
from decimal import Decimal, getcontext
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from harness_bench.errors import BenchError
from harness_bench.stats import Interval, Obs, Params, interval, rng

# assume: T-S4 says "a committed 6-task fixture" and names no path. This is that fixture.
# Confirm: replace this path if the Owner names a different one.
SIX_TASKS = Path(__file__).parent / "fixtures" / "stats" / "six_tasks.json"

# First five random() values of rng(20260927, "k"). Each index draw consumes one.
GOLDEN_DRAWS = (
    "0.6935337615930465",
    "0.4450610319205216",
    "0.5944344521296071",
    "0.9352053264904925",
    "0.8350719510902923",
)
# Full interval over SIX_TASKS at seed 20260927, key "k", 2,000 resamples.
GOLDEN_POINT = "0.913888888888888888888888889"
GOLDEN_LO = "0.549074074074074074074074074"
GOLDEN_HI = "1.278703703703703703703703704"

# characterization (D6). Test Architect condition 2: pinned on first green, not a target
# the implementation was tuned to. 200 * 0.93 = 186, so 190 clears the threshold.
COVERED_AT_SIX_BY_THREE = 190
TS8_TRIALS = 200

UNBALANCED = [
    Obs("A", 1, Decimal(1)),
    Obs("B", 1, Decimal(2)),
    Obs("B", 2, Decimal(4)),
    Obs("C", 1, Decimal(3)),
    Obs("C", 2, Decimal(6)),
    Obs("C", 3, Decimal(9)),
]

_unbalanced_hits = 0


def _six_tasks() -> tuple[dict, list[Obs]]:
    payload = json.loads(SIX_TASKS.read_text(encoding="utf-8"))
    obs = [Obs(row["task"], row["rep"], Decimal(row["value"])) for row in payload["observations"]]
    return payload, obs


def _bytes(iv: Interval) -> bytes:
    def part(value: Decimal | None) -> str:
        return "null" if value is None else format(value, "f")

    return f"{part(iv.point)} {part(iv.lo)} {part(iv.hi)} {iv.n} {iv.reason}".encode()


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


def test_ts2_task_balanced_point_weights_tasks_equally():
    """T-S2: 3 tasks with 1, 2 and 3 reps. The point is the mean of the task means, 10/3.

    The pooled cell mean is 25/6. A mean over cells fails this and the task-balanced mean does not.
    """
    obs = [
        Obs("C", 2, Decimal(6)),
        Obs("A", 1, Decimal(1)),
        Obs("C", 3, Decimal(9)),
        Obs("B", 2, Decimal(4)),
        Obs("C", 1, Decimal(3)),
        Obs("B", 1, Decimal(2)),
    ]
    point = interval(obs, Params(), "balanced").point
    assert point == Decimal(10) / Decimal(3)
    assert point != Decimal(25) / Decimal(6)


@st.composite
def _observation_sets(draw):
    """Every draw is unbalanced: task T0 has `base` reps and T1 has `base + 1`.

    No `assume`, so the corpus is not filtered down to empty (GATE-A).
    """
    n_tasks = draw(st.integers(min_value=2, max_value=4))
    base = draw(st.integers(min_value=1, max_value=2))
    counts = [base, base + 1]
    for _extra in range(n_tasks - 2):
        counts.append(draw(st.integers(min_value=1, max_value=3)))
    observations = []
    for index, count in enumerate(counts):
        for rep in range(1, count + 1):
            observations.append(Obs(f"T{index}", rep, Decimal(draw(st.integers(min_value=0, max_value=12)))))
    return observations


@settings(max_examples=40, deadline=None, derandomize=True)
@given(obs=_observation_sets(), seed=st.integers(min_value=0, max_value=2**63 - 1), key=st.text(alphabet="abc", min_size=1, max_size=6))
@example(obs=UNBALANCED, seed=20260927, key="k")
def ts3_properties(obs, seed, key):
    """T-S3 properties. The unbalanced branch increments `_unbalanced_hits`."""
    global _unbalanced_hits
    counts: dict[str, int] = {}
    for item in obs:
        counts[item.task] = counts.get(item.task, 0) + 1
    if len(set(counts.values())) > 1:
        _unbalanced_hits += 1
    params = Params(seed=seed)
    key_a = f"pass_at_1|{key}"
    first = interval(obs, params, key_a)
    assert first.n >= 2 and first.reason is None and first.lo is not None and first.hi is not None
    assert interval(obs, params, key_a) == first
    assert interval(list(reversed(obs)), params, key_a) == first
    interval(obs, params, f"gated|{key}")
    assert interval(obs, params, key_a) == first
    values = [item.value for item in obs]
    assert min(values) <= first.lo <= first.hi <= max(values)
    fixed = values[0]
    constant = [Obs(item.task, item.rep, fixed) for item in obs]
    collapsed = interval(constant, params, key_a)
    assert collapsed.lo == collapsed.hi == collapsed.point == fixed


def test_ts3_unbalanced_branch_is_taken():
    """The property is called, then the unbalanced counter is asserted, as the design requires."""
    global _unbalanced_hits
    _unbalanced_hits = 0
    ts3_properties()
    assert _unbalanced_hits > 0


def test_ts3_same_seed_and_key_are_identical():
    params = Params(seed=11, resamples=2000)
    assert interval(UNBALANCED, params, "m|c|p") == interval(UNBALANCED, params, "m|c|p")


def test_ts3_shuffling_the_input_keeps_the_interval():
    params = Params(seed=11)
    shuffled = list(reversed(UNBALANCED))
    assert shuffled != UNBALANCED
    assert interval(shuffled, params, "m|c|p") == interval(UNBALANCED, params, "m|c|p")


def test_ts3_adding_another_quantity_does_not_move_this_interval():
    """Key isolation: another quantity's stream does not move this one, and the seed is in the key."""
    _, obs = _six_tasks()
    params = Params()
    this = interval(obs, params, "pass_at_1|cc|on")
    interval(obs, params, "gated|cc|off")
    assert interval(obs, params, "pass_at_1|cc|on") == this
    other_seed = interval(obs, Params(seed=params.seed + 1), "pass_at_1|cc|on")
    assert (this.lo, this.hi) != (other_seed.lo, other_seed.hi)


def test_ts3_the_interval_lies_inside_the_observations():
    iv = interval(UNBALANCED, Params(seed=11), "m|c|p")
    values = [item.value for item in UNBALANCED]
    assert min(values) <= iv.lo <= iv.hi <= max(values)


def test_ts3_constant_data_collapses_to_the_value():
    constant = [Obs(item.task, item.rep, Decimal(4)) for item in UNBALANCED]
    iv = interval(constant, Params(seed=11), "m|c|p")
    assert iv.lo == iv.hi == iv.point == Decimal(4)


def test_ts4_golden_stream_and_six_task_interval():
    """T-S4: the draws and the interval are exact strings in this source."""
    payload, obs = _six_tasks()
    assert (payload["seed"], payload["key"], payload["resamples"]) == (20260927, "k", 2000)
    assert len({row["task"] for row in payload["observations"]}) == 6
    stream = rng(20260927, "k")
    assert tuple(repr(stream.random()) for _ in range(5)) == GOLDEN_DRAWS
    iv = interval(obs, Params(seed=payload["seed"], resamples=payload["resamples"]), payload["key"])
    assert str(iv.point) == GOLDEN_POINT
    assert str(iv.lo) == GOLDEN_LO
    assert str(iv.hi) == GOLDEN_HI
    assert iv.n == 6 and iv.reason is None


def test_ts5_ambient_decimal_context_does_not_change_the_bytes():
    """T-S5: prec=5 around the call leaves the interval bytes unchanged."""
    obs = [Obs("A", 1, Decimal(1)), Obs("B", 1, Decimal(2)), Obs("C", 1, Decimal(4))]
    params = Params()
    ambient = interval(obs, params, "prec")
    context = getcontext()
    saved = context.prec
    context.prec = 5
    try:
        narrowed = interval(obs, params, "prec")
    finally:
        context.prec = saved
    assert _bytes(ambient) == _bytes(narrowed)
    assert ambient.point == Decimal(7) / Decimal(3)


@pytest.mark.parametrize(("seed", "resamples"), [(20260927, 1999), (20260927, 100_001), (-1, 2000), (2**63, 2000)])
def test_ts6_params_refuses_out_of_range(seed, resamples):
    """T-S6: resamples 1999 and 100001, seed -1 and seed 2**63, each HB-USR-002."""
    with pytest.raises(BenchError) as err:
        Params(seed, resamples)
    assert err.value.code == "HB-USR-002"


@pytest.mark.parametrize(("seed", "resamples"), [(20260927, 2000), (20260927, 100_000), (2**63 - 1, 2000)])
def test_ts6_params_accepts_the_inclusive_bounds(seed, resamples):
    """T-S6: 2000, 100000 and 2**63 - 1 are accepted."""
    assert (Params(seed, resamples).seed, Params(seed, resamples).resamples) == (seed, resamples)


def test_ts8_two_stage_coverage_at_six_tasks_by_three_reps():
    """T-S8. characterization (D6): the exact covered count is pinned on first green.

    Appendix A's simulation at 6 tasks x 3 reps, true rate 0.5, cut to 200 trials. Coverage >= 0.93
    separates two-stage (this count) from the rejected cluster-only variant.

    assume: the design files T-S8 on the `slow` ring. This repo's `slow` marker is the dotnet gate
    (`tests/conftest.py` calls `dotnet_gate` for every slow test): without HB_REQUIRE_DOTNET=1 the
    test skips, and with it a missing dotnet fails the test. T-S8 runs no dotnet, so it is unmarked
    and its assertions actually run. Confirm: a statistics slow marker that does not call dotnet_gate.

    assume: one `random.Random(20260927)` draws every trial in order, `p = betavariate(2, 2)`,
    a cell is 1 when `random() < p` else 0, and trial `i` is `interval(..., Params(), f"coverage|{i}")`.
    The estimand is `2 / (2 + 2) = 0.5`. Confirm: the author's uncommitted spike, on this stream,
    covers the same count. Breaks if false: this characterization moves and the test fails.
    """
    data = random.Random(20260927)
    truth = Decimal("0.5")
    covered = 0
    for trial in range(TS8_TRIALS):
        obs = []
        for task_i in range(6):
            probability = data.betavariate(2, 2)
            for rep in range(1, 4):
                obs.append(Obs(f"T{task_i}", rep, Decimal(1) if data.random() < probability else Decimal(0)))
        iv = interval(obs, Params(), f"coverage|{trial}")
        if iv.lo is not None and iv.lo <= truth <= iv.hi:
            covered += 1
    assert covered / TS8_TRIALS >= 0.93
    assert covered == COVERED_AT_SIX_BY_THREE, (
        "characterization (D6): exact covered count pinned on first green"
    )
