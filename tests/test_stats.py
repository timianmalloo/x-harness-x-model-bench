"""Bootstrap core and ranking (design phase4-statistics, slices S1 and S2).

T-S1 is the red-first test for S1. T-R3 is the red-first test for S2.
T-S3 and T-R12/T-R13 are the hypothesis suites. T-S4 pins the stream and one
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
from harness_bench.stats import Interval, Obs, Params, interval, paired_delta, rank, rng

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


def _iv(lo: int, hi: int, point: int | None = None) -> Interval:
    left, right = Decimal(lo), Decimal(hi)
    mid = (left + right) / 2 if point is None else Decimal(point)
    return Interval(mid, left, right, 2, None)


def _missing(reason: str, n: int, point: int | None = None) -> Interval:
    value = None if point is None else Decimal(point)
    return Interval(value, None, None, n, reason)


def _k3_rows() -> dict:
    """K3: three primaries that pairwise overlap."""
    same = _iv(0, 1)
    return {
        ("A", "off"): (_iv(0, 10), same),
        ("B", "on"): (_iv(4, 14), same),
        ("C", "off"): (_iv(8, 12), same),
    }


def _k4_rows() -> dict:
    """K4: A overlaps B, B overlaps C, A is above C."""
    same = _iv(0, 1)
    return {
        ("A", "off"): (_iv(15, 30), same),
        ("B", "off"): (_iv(5, 20), same),
        ("C", "off"): (_iv(0, 10), same),
    }


def _k9_rows() -> dict:
    """K9: disjoint composites, pass@1 in the same order. No gate conflict."""
    return {
        ("high", "off"): (_iv(20, 30), _iv(20, 30)),
        ("low", "off"): (_iv(0, 10), _iv(0, 10)),
    }


def _nested_rows() -> dict:
    """One wide interval overlaps two that miss each other. One component, no gate conflict."""
    same = _iv(0, 1)
    return {
        ("P", "off"): (_iv(0, 100), same),
        ("Q", "off"): (_iv(10, 20), same),
        ("R", "off"): (_iv(90, 95), same),
    }


def _k7_case() -> tuple:
    """K7: X's composite is above Y's, and X's pass@1 is entirely below Y's."""
    rows = {
        ("X", "off"): (_iv(20, 30), _iv(0, 4)),
        ("Y", "off"): (_iv(0, 10), _iv(5, 9)),
    }
    return rows, ("X", "off"), ("Y", "off")


def _rank_number(label: str) -> int:
    """Competition rank as a number. The tie marker `=` is display, not magnitude."""
    return int(label.removesuffix("="))


def _ranked_only(rows: dict) -> dict:
    return {
        row_id: pair
        for row_id, pair in rows.items()
        if pair[0].lo is not None and pair[0].hi is not None
    }


def _overlap_components(ranked: dict) -> list[set]:
    """Connected components of the overlap graph. Independent of the sweep."""
    parent = {row_id: row_id for row_id in ranked}

    def find(row_id):
        while parent[row_id] != row_id:
            parent[row_id] = parent[parent[row_id]]
            row_id = parent[row_id]
        return row_id

    ids = list(ranked)
    for i, left in enumerate(ids):
        a = ranked[left][0]
        for right in ids[i + 1 :]:
            b = ranked[right][0]
            if a.lo <= b.hi and b.lo <= a.hi:
                parent[find(right)] = find(left)
    groups: dict = {}
    for row_id in ids:
        groups.setdefault(find(row_id), set()).add(row_id)
    return list(groups.values())


def _has_gate_conflict(ranked: dict) -> bool:
    """True when some pair is strictly below on pass@1 and better on the overlap tiers."""
    components = _overlap_components(ranked)
    # Best component first: the one whose primary lo is highest (components are separated).
    def top(component: set):
        return max(ranked[row_id][0].lo for row_id in component)

    ordered = sorted(components, key=top, reverse=True)
    index = {row_id: i for i, component in enumerate(ordered) for row_id in component}
    for x, (_px, ax) in ranked.items():
        if ax.lo is None or ax.hi is None:
            continue
        for y, (_py, ay) in ranked.items():
            if x == y or ay.lo is None or ay.hi is None:
                continue
            if ax.hi < ay.lo and index[x] < index[y]:
                return True
    return False


def _assert_rank_laws(rows: dict, result: dict) -> None:
    """(i), (ii), competition ranks, and components when the gate has nothing to do."""
    assert set(result) == set(rows)
    ranked = _ranked_only(rows)
    for row_id, (primary, _pass) in rows.items():
        label, reason = result[row_id]
        if row_id not in ranked:
            assert label == ""
            assert reason == f"not ranked: {primary.reason}"
            continue
        assert reason is None
        body = label.removesuffix("=")
        assert body.isdigit()
    ids = list(ranked)
    for i, x in enumerate(ids):
        px, ax = ranked[x]
        for y in ids[i + 1 :]:
            py, _ay = ranked[y]
            if px.lo <= py.hi and py.lo <= px.hi:
                assert result[x][0] == result[y][0]
        for y in ids:
            if x == y:
                continue
            ay = ranked[y][1]
            if ax.lo is None or ax.hi is None or ay.lo is None or ay.hi is None:
                continue
            if ax.hi < ay.lo:
                assert _rank_number(result[x][0]) >= _rank_number(result[y][0])
    groups: dict[str, int] = {}
    for row_id in ranked:
        label = result[row_id][0]
        groups[label] = groups.get(label, 0) + 1
    parsed = []
    for label, size in groups.items():
        assert label.endswith("=") == (size > 1)
        parsed.append((_rank_number(label), size))
    parsed.sort()
    expect = 1
    for number, size in parsed:
        assert number == expect
        expect += size
    if ranked and not _has_gate_conflict(ranked):
        got = {
            frozenset(row_id for row_id in ranked if result[row_id][0] == label) for label in groups
        }
        assert got == {frozenset(component) for component in _overlap_components(ranked)}


def test_tr1_k1_no_computed_interval_is_unranked():
    """K1: no primary is computed. The rank is empty and the interval reason is kept."""
    rows = {
        ("b", "on"): (
            _missing("interval not computed (n < 2)", 1, point=1),
            _missing("interval not computed (n < 2)", 1, point=1),
        ),
        ("a", "off"): (
            _missing("not computed (no valid cell with a value)", 0),
            _missing("not computed (no valid cell with a value)", 0),
        ),
    }
    result = rank(rows)
    assert list(result.items()) == [
        (("a", "off"), ("", "not ranked: not computed (no valid cell with a value)")),
        (("b", "on"), ("", "not ranked: interval not computed (n < 2)")),
    ]


def test_tr2_k2_one_ranked_row_is_1():
    """K2: one ranked row prints `1`, with no tie marker."""
    rows = {("only", "off"): (_iv(0, 10), _iv(0, 1))}
    assert rank(rows) == {("only", "off"): ("1", None)}


def test_tr3_k3_every_overlap_is_a_tie():
    """T-R3, K3: every primary interval overlaps, so every row is `1=`."""
    result = rank(_k3_rows())
    assert result[("A", "off")][0] == "1="
    assert result[("B", "on")][0] == "1="
    assert result[("C", "off")][0] == "1="


def test_tr4_k4_overlap_chain_is_one_tier():
    """K4: A overlaps B, B overlaps C, and A is above C. All three are `1=`."""
    result = rank(_k4_rows())
    assert result[("A", "off")][0] == "1="
    assert result[("B", "off")][0] == "1="
    assert result[("C", "off")][0] == "1="


def test_tr5_k5_touching_intervals_tie():
    """K5: `a.hi == b.lo`. Closed intervals overlap, so the rows tie."""
    rows = {
        ("low", "off"): (_iv(0, 10), _iv(0, 1)),
        ("high", "off"): (_iv(10, 20), _iv(0, 1)),
    }
    result = rank(rows)
    assert result[("low", "off")][0] == "1="
    assert result[("high", "off")][0] == "1="


def test_tr6_k6_identical_zero_width_intervals_tie():
    """K6: identical zero-width intervals overlap at that point and tie."""
    rows = {
        ("a", "off"): (_iv(5, 5), _iv(0, 1)),
        ("b", "off"): (_iv(5, 5), _iv(0, 1)),
    }
    result = rank(rows)
    assert result[("a", "off")][0] == "1="
    assert result[("b", "off")][0] == "1="


def test_tr7_k7_pass_at_1_gate_merges_two_tiers():
    """K7: disjoint composites, and the lower row's pass@1 is entirely above. One tie."""
    rows, x, y = _k7_case()
    result = rank(rows)
    assert result[x] == ("1=", None)
    assert result[y] == ("1=", None)


def test_tr8_k8_gate_merges_the_middle_tier():
    """K8: the only gate pair spans a middle tier, so all three tiers become one.

    Z's pass@1 touches X's and overlaps Y's, so it is not below either. Merging
    only the two ends would leave Z at its own rank.
    """
    rows = {
        ("X", "a"): (_iv(40, 50), _iv(0, 10)),
        ("Z", "a"): (_iv(20, 30), _iv(10, 20)),
        ("Y", "a"): (_iv(0, 10), _iv(12, 22)),
    }
    result = rank(rows)
    assert result[("X", "a")][0] == "1="
    assert result[("Z", "a")][0] == "1="
    assert result[("Y", "a")][0] == "1="


def test_tr9_k9_disjoint_tiers_without_a_gate_conflict():
    """K9: two tiers and no gate conflict. Ranks `1` and `2`."""
    result = rank(_k9_rows())
    assert result[("high", "off")] == ("1", None)
    assert result[("low", "off")] == ("2", None)


def test_tr10_k10_n_below_2_is_unranked_and_ignored():
    """K10: an n < 2 row is unranked. The others are ranked as if it were absent."""
    rows = {
        ("high", "off"): (_iv(20, 30), _iv(0, 1)),
        ("low", "off"): (_iv(0, 10), _iv(0, 1)),
        ("gap", "on"): (_missing("interval not computed (n < 2)", 1, point=3), _iv(0, 1)),
    }
    result = rank(rows)
    assert result[("high", "off")] == ("1", None)
    assert result[("low", "off")] == ("2", None)
    assert result[("gap", "on")] == ("", "not ranked: interval not computed (n < 2)")


def test_tr11_k11_shuffled_rows_keep_ranks_and_display_order():
    """K11: shuffling the input keeps the ranks. Order is step 5, not input order."""
    same = _iv(0, 1)
    rows = {
        ("z", "off"): (_iv(0, 5, point=4), same),
        ("m", "on"): (_iv(20, 30, point=25), same),
        ("b", "off"): (_missing("interval not computed (n < 2)", 1, point=1), same),
        ("a", "on"): (_iv(20, 30, point=28), same),
        ("m", "off"): (_iv(20, 30, point=25), same),
        ("a", "off"): (_missing("not computed (no valid cell with a value)", 0), same),
    }
    order = (("a", "off"), ("m", "off"), ("z", "off"), ("a", "on"), ("b", "off"), ("m", "on"))
    shuffled = {key: rows[key] for key in order}
    assert list(shuffled) != list(rows)
    expected = [
        (("a", "on"), ("1=", None)),
        (("m", "off"), ("1=", None)),
        (("m", "on"), ("1=", None)),
        (("z", "off"), ("4", None)),
        (("a", "off"), ("", "not ranked: not computed (no valid cell with a value)")),
        (("b", "off"), ("", "not ranked: interval not computed (n < 2)")),
    ]
    assert list(rank(rows).items()) == expected
    assert list(rank(shuffled).items()) == expected


def _drawn_interval(draw, computed: bool) -> Interval:
    if not computed:
        reason = draw(
            st.sampled_from(
                [
                    "interval not computed (n < 2)",
                    "not computed (no valid cell with a value)",
                ]
            )
        )
        if reason.startswith("not computed"):
            return _missing(reason, 0)
        return _missing(reason, 1, point=draw(st.integers(min_value=0, max_value=5)))
    lo = draw(st.integers(min_value=0, max_value=40))
    hi = draw(st.integers(min_value=lo, max_value=lo + 20))
    point = draw(st.integers(min_value=lo, max_value=hi))
    return Interval(Decimal(point), Decimal(lo), Decimal(hi), 2, None)


@st.composite
def _rank_rows(draw):
    """Random interval rows. No `assume`, so nothing is discarded (GATE-A)."""
    n = draw(st.integers(min_value=1, max_value=5))
    rows = {}
    for i in range(n):
        primary = _drawn_interval(draw, computed=draw(st.booleans()))
        pass_at_1 = _drawn_interval(draw, computed=draw(st.booleans()))
        pack = "on" if draw(st.booleans()) else "off"
        rows[(f"c{i}", pack)] = (primary, pass_at_1)
    return rows


@settings(max_examples=40, deadline=None, derandomize=True)
@given(rows=_rank_rows())
@example(rows=_k3_rows())
@example(rows=_k4_rows())
@example(rows=_k9_rows())
@example(rows=_nested_rows())
def tr12_properties(rows):
    """T-R12: overlap ties, the pass@1 gate, competition ranks, and the components."""
    _assert_rank_laws(rows, rank(rows))


def test_tr12_overlap_and_competition_laws():
    """T-R12 runs the property, including the nested-interval example."""
    tr12_properties()


_gate_conflict_hits = 0


@st.composite
def _gate_conflict_case(draw):
    """X's composite is entirely above Y's, and X's pass@1 is entirely below Y's.

    Extra rows sit wholly above X or wholly below Y, so they cannot bridge the pair.
    """
    y_lo = draw(st.integers(min_value=0, max_value=15))
    y_hi = draw(st.integers(min_value=y_lo, max_value=y_lo + 10))
    x_lo = y_hi + draw(st.integers(min_value=1, max_value=8))
    x_hi = draw(st.integers(min_value=x_lo, max_value=x_lo + 10))
    xp_lo = draw(st.integers(min_value=0, max_value=10))
    xp_hi = draw(st.integers(min_value=xp_lo, max_value=xp_lo + 8))
    yp_lo = xp_hi + draw(st.integers(min_value=1, max_value=6))
    yp_hi = draw(st.integers(min_value=yp_lo, max_value=yp_lo + 8))

    def built(lo: int, hi: int) -> Interval:
        return Interval(Decimal(lo + hi) / 2, Decimal(lo), Decimal(hi), 2, None)

    rows = {
        ("X", "off"): (built(x_lo, x_hi), built(xp_lo, xp_hi)),
        ("Y", "off"): (built(y_lo, y_hi), built(yp_lo, yp_hi)),
    }
    for i in range(draw(st.integers(min_value=0, max_value=3))):
        if draw(st.booleans()):
            lo = x_hi + draw(st.integers(min_value=1, max_value=6))
            hi = draw(st.integers(min_value=lo, max_value=lo + 8))
        else:
            hi = y_lo - draw(st.integers(min_value=1, max_value=6))
            lo = hi - draw(st.integers(min_value=0, max_value=8))
        rows[(f"e{i}", "on")] = (built(lo, hi), _drawn_interval(draw, computed=draw(st.booleans())))
    return rows, ("X", "off"), ("Y", "off")


def _pair_is_gate_conflict(rows: dict, x, y) -> bool:
    ranked = _ranked_only(rows)
    if x not in ranked or y not in ranked:
        return False
    ax, ay = ranked[x][1], ranked[y][1]
    if ax.hi is None or ay.lo is None or not ax.hi < ay.lo:
        return False
    components = _overlap_components(ranked)

    def top(component: set):
        return max(ranked[row_id][0].lo for row_id in component)

    ordered = sorted(components, key=top, reverse=True)
    index = {row_id: i for i, component in enumerate(ordered) for row_id in component}
    return index[x] < index[y]


@settings(max_examples=40, deadline=None, derandomize=True)
@given(case=_gate_conflict_case())
@example(case=_k7_case())
def tr13_properties(case):
    """T-R13: a constructed gate conflict. The counter marks that branch."""
    global _gate_conflict_hits
    rows, x, y = case
    if _pair_is_gate_conflict(rows, x, y):
        _gate_conflict_hits += 1
    result = rank(rows)
    _assert_rank_laws(rows, result)
    ax, ay = rows[x][1], rows[y][1]
    if ax.hi is not None and ay.lo is not None and ax.hi < ay.lo and result[x][0] and result[y][0]:
        assert _rank_number(result[x][0]) >= _rank_number(result[y][0])


def test_tr13_gate_conflict_branch_is_taken():
    """The property is called, then the gate-conflict counter is asserted."""
    global _gate_conflict_hits
    _gate_conflict_hits = 0
    tr13_properties()
    assert _gate_conflict_hits > 0


def test_tr14_k12_touching_pass_at_1_is_not_below():
    """K12, T-R14: composites are disjoint and the pass@1 intervals touch. Ranks `1`, `2`.

    `below` is strict (`hi < lo`). Writing it as `<=` merges these into a tie.
    """
    rows = {
        ("X", "off"): (_iv(20, 30), _iv(0, 5)),
        ("Y", "off"): (_iv(0, 10), _iv(5, 10)),
    }
    result = rank(rows)
    assert result[("X", "off")] == ("1", None)
    assert result[("Y", "off")] == ("2", None)


def test_tr15_k13_competition_ranks_print_the_spec_tie():
    """K13, T-R15: four rows give `1`, `2=`, `2=`, `4`, the spec's own `2=`."""
    same = _iv(0, 1)
    rows = {
        ("A", "off"): (_iv(30, 40), same),
        ("B", "off"): (_iv(10, 20), same),
        ("C", "off"): (_iv(12, 18), same),
        ("D", "off"): (_iv(0, 5), same),
    }
    result = rank(rows)
    assert result[("A", "off")][0] == "1"
    assert result[("B", "off")][0] == "2="
    assert result[("C", "off")][0] == "2="
    assert result[("D", "off")][0] == "4"


def test_ts7_swapping_arms_negates_the_interval():
    """T-S7: swapping the arms gives exactly (−hi, −lo).

    The arms are not mirrors, and one task sits in each arm only. The interval
    is not symmetric about zero, so (−hi, −lo) is a different pair from (lo, hi).
    """
    ref = [
        Obs("A", 1, Decimal(0)),
        Obs("B", 1, Decimal(1)),
        Obs("B", 2, Decimal(1)),
        Obs("C", 1, Decimal(10)),
    ]
    treat = [
        Obs("A", 1, Decimal(10)),
        Obs("A", 2, Decimal(10)),
        Obs("A", 3, Decimal(10)),
        Obs("B", 1, Decimal(4)),
        Obs("D", 1, Decimal(9)),
    ]
    params = Params()
    forward, only_forward = paired_delta(ref, treat, ("off", "on"), params, "pack")
    backward, only_backward = paired_delta(treat, ref, ("on", "off"), params, "pack")
    assert forward.lo is not None and forward.hi is not None
    assert forward.lo != -forward.hi
    assert backward.lo == -forward.hi
    assert backward.hi == -forward.lo
    assert backward.point == -forward.point
    assert forward.point == Decimal(13) / Decimal(2)
    assert only_forward == ("C", "D")
    assert only_backward == ("C", "D")


def test_tr16_uncomputed_pass_at_1_is_not_a_gate_check():
    """T-R16: X is ranked with no pass@1 interval. Y's composite is entirely below X's.

    Y's pass@1 is entirely above the other row that has one. There is no merge.
    """
    missing = _missing("interval not computed (n < 2)", 1, point=1)
    rows = {
        ("X", "on"): (_iv(20, 30), missing),
        ("Y", "off"): (_iv(0, 10), _iv(5, 9)),
        ("Z", "off"): (missing, _iv(0, 1)),
    }
    result = rank(rows)
    assert result[("X", "on")] == ("1", None)
    assert result[("Y", "off")] == ("2", None)
    assert result[("Z", "off")] == ("", "not ranked: interval not computed (n < 2)")
