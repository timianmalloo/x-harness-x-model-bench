"""Verdicts, pairs and intervals (W1-H section 11.2). Pairs come from real CellViews; goldens come from
an independent naive reference (Fractions, no common-denominator trick), not from verdicts.py."""

import ast
import hashlib
import math
import os
import random
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench import plan, power, stats, verdicts, views
from harness_bench.errors import BenchError
from harness_bench.verdicts import Pair, Ratio, VerdictLabel

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_bench" / "verdicts.py"
D = Decimal
L = VerdictLabel
# The `slow` marker is the dotnet graders' ring (conftest.py gates it on HB_REQUIRE_DOTNET and a dotnet on PATH),
# so the coverage simulations gate on their own switch. Seam request: a `coverage` marker in pyproject.toml.
COVERAGE_RUN = pytest.mark.skipif(os.environ.get("HB_RUN_COVERAGE") != "1", reason="coverage simulation: HB_RUN_COVERAGE=1")


# ---------------------------------------------------------------- builders

def _spec(**kw):
    base = {
        "prop": "security", "harness": "cc", "comparison": ("off", "on"), "tasks": ("a", "b"), "mde": D("0.30"),
        "method": "none", "alpha_per_test": D("0.05"), "level_rule": "alpha (no correction)", "min_pairs": 1,
        "seed": 424242, "resamples": 2000, "required_pairs": None,
    }
    return verdicts.VerdictSpec(**{**base, **kw})


def _pairs(diffs, tokens=None, wall=None):
    """diffs: {task: [-1|0|1]}; tokens: {task: [(ref, treat)]} or None (unrecorded)."""
    out = []
    for task in sorted(diffs):
        for index, d in enumerate(diffs[task]):
            ref, treat = {1: (0, 1), -1: (1, 0), 0: (0, 0)}[d]
            rt, tt = tokens[task][index] if tokens else (None, None)
            rw, tw = wall[task][index] if wall else (None, None)
            out.append(Pair(task, index + 1, D(ref), D(treat), rt, tt, rw, tw))
    return out


def _run(diffs, tokens=None, wall=None, **kw):
    return verdicts.verdict(_spec(**kw), _pairs(diffs, tokens, wall), [], {})


def _tok(n):
    return None if n is None else {"m": {"uncached_input": n, "cache_read": 0, "cache_write": 0, "output": 0}}


def _cell(task, rep, arm, value=1, *, harness="cc", combo="c", outcome="completed", cause=None, validity="valid",
          reason=None, tokens=100, wall=1000, cid=None, label=None):
    na = views.Measure(None, "not graded")
    cell = plan.Cell(task, "v1", 1, combo, harness, "m", arm, rep, 60)
    scores = {} if value == "absent" else {
        "property_check_pass": views.Measure(None if value is None else value, reason if value is None else None)}
    return views.CellView(
        cell_id=cid or f"{task}-{arm}-{rep}", label=label or cell.label, combo=combo, pack=arm, harness=harness,
        model="m", outcome=outcome, cause=cause, code=None, validity=validity, validity_code=None,
        wall_ms=views.Measure(wall) if wall is not None else na, model_ms=na, tool_ms=na, idle_ms=na,
        tokens=_tok(tokens), tokens_reason=None if tokens is not None else "not recorded", scores=scores)


# ---------------------------------------------------------------- rule tables

@pytest.mark.parametrize(
    ("n", "min_pairs", "lo", "hi", "expect"),
    [
        pytest.param(5, 6, "0.10", "0.50", L.NOT_RECORDED, id="L1"),
        pytest.param(6, 6, "0.10", "0.50", L.BETTER, id="L2"),
        pytest.param(6, 6, "0", "0.50", L.UNDERPOWERED, id="L3"),
        pytest.param(6, 6, "-0.50", "0", L.UNDERPOWERED, id="L4"),
        pytest.param(6, 6, "-0.50", "-0.01", L.WORSE, id="L5"),
        pytest.param(6, 6, "0.05", "0.15", L.BETTER, id="L6"),
        pytest.param(6, 6, "-0.15", "-0.05", L.WORSE, id="L7"),
        pytest.param(6, 6, "-0.30", "0.10", L.UNDERPOWERED, id="L8"),
        pytest.param(6, 6, "-0.10", "0.30", L.UNDERPOWERED, id="L9"),
        pytest.param(6, 6, "0", "0", L.NO_DIFFERENCE, id="L10"),
    ],
)
def test_label_for_boundary_table(n, min_pairs, lo, hi, expect):
    assert verdicts.label_for(n, min_pairs, D(lo), D(hi), D("0.30")) == expect


def _R(lo, hi, r):
    return Ratio(r=D(r), lo=D(lo), hi=D(hi))


_NONDIR = [pytest.param(L.UNDERPOWERED, id="D5-underpowered"), pytest.param(L.NOT_RECORDED, id="D5-not-recorded")]


@pytest.mark.parametrize(
    ("label", "ratio", "expect"),
    [
        pytest.param(L.BETTER, _R("0.5", "0.99", "0.80"), "on dominates off", id="D1"),
        pytest.param(L.BETTER, _R("0.5", "1.00", "1.00"), "better at ×1.00 tokens", id="D2"),
        pytest.param(L.NO_DIFFERENCE, _R("0.5", "0.99", "0.80"), "on dominates off", id="D3"),
        pytest.param(L.WORSE, _R("0.1", "0.50", "0.30"), None, id="D4"),
        pytest.param(L.BETTER, None, None, id="D6"),
        pytest.param(L.BETTER, _R("0.8", "1.4", "0.9"), "better at ×0.9 tokens", id="D7"),
    ],
)
def test_statement_for_table(label, ratio, expect):
    assert verdicts.statement_for(label, "on", "off", ratio) == expect


@pytest.mark.parametrize("label", _NONDIR)
def test_statement_for_non_directional_is_none(label):
    assert verdicts.statement_for(label, "on", "off", _R("0.1", "0.50", "0.30")) is None


# ---------------------------------------------------------------- level, resamples, seed

def _prereg(method, m=45, alpha="0.05"):
    return {"alpha": D(alpha), "correction": {"method": method, "m": m}}


@pytest.mark.parametrize("method", ["bonferroni", "holm", "none"])
def test_alpha_per_test_reads_the_one_power_table(method):
    prereg = _prereg(method)
    assert verdicts.alpha_per_test(prereg) == power.level_for(method, D("0.05"), 45)[0]
    assert verdicts.alpha_per_test(prereg) == (D("0.05") if method == "none" else D("0.05") / 45)


def _method_names_in(source: str) -> set[str]:
    strings = {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return strings & {"bonferroni", "holm"}


def test_verdicts_defines_no_second_level_table():
    assert _method_names_in("TABLE = {'holm': 1}") == {"holm"}  # red fixture: the scan sees a second table
    assert _method_names_in(SRC.read_text(encoding="utf-8")) == set()


def test_resamples_for_tail_depth():
    assert verdicts.resamples_for(D("0.05")) == 2000
    assert verdicts.resamples_for(D("0.05") / 45) == 18000
    assert verdicts.resamples_for(D("0.0002")) == 100000
    with pytest.raises(BenchError) as caught:
        verdicts.resamples_for(D("0.0001"))
    assert caught.value.code == "HB-USR-002"
    for alpha in (D("0.05"), D("0.05") / 45, D("0.0002")):
        assert verdicts.resamples_for(alpha) * alpha / 2 >= 10 - D("1e-9")


@pytest.mark.parametrize(
    ("resamples", "alpha", "expect"),
    [
        pytest.param(18000, D("0.05") / 45, 10, id="snap"),  # 9.99999... in decimal arithmetic; the tail is 10 draws
        pytest.param(2000, D("0.05"), 50, id="exact"),
        pytest.param(2000, D("0.04999"), 49, id="floor"),  # 49.99 floors; a wide epsilon would round it up
    ],
)
def test_tail_index_at_the_decimal_edge(resamples, alpha, expect):
    assert verdicts._tail(resamples, alpha) == expect


S2_HASH = "a182ba2204e318913030a3292bd6a27b3be23d347375158b075c74e0d404752c"


def test_seed_for_is_a_legal_params_seed():
    """The design's S2 hash was elided ("e1746a8b...effc"), so this row is a hash whose first 16 hex digits
    are an illegal seed (>= 2**63), with both values computed by hashlib in the test."""
    digest = hashlib.sha256(f"{S2_HASH}|security|cc-opus|off|candidate".encode()).hexdigest()
    assert int(digest[:16], 16) >= 2**63
    seed = verdicts.seed_for(S2_HASH, "security", "cc-opus", ("off", "candidate"))
    assert seed == 853208829639983637 == int(digest[:15], 16)
    assert stats.Params(seed=seed).seed == seed


@settings(max_examples=60, deadline=None)
@given(st.lists(st.binary(min_size=1, max_size=8), min_size=1, max_size=30))
def test_seed_for_range_over_many_hashes(blobs):
    for blob in blobs:
        seed = verdicts.seed_for(hashlib.sha256(blob).hexdigest(), "p", "h", ("off", "on"))
        assert 0 <= seed < 2**63


@pytest.mark.parametrize("field", ["hash", "prop", "harness", "ref", "treat"])
def test_each_seed_key_field_moves_the_seed(field):
    base = {"hash": S2_HASH, "prop": "security", "harness": "cc-opus", "ref": "off", "treat": "candidate"}
    other = dict(base, **{field: base[field] + "x"})

    def seed(k):
        return verdicts.seed_for(k["hash"], k["prop"], k["harness"], (k["ref"], k["treat"]))

    assert seed(other) != seed(base)


# ---------------------------------------------------------------- spec and refusals

@pytest.mark.parametrize("min_pairs", [0, -1])
def test_min_pairs_below_one_is_refused(min_pairs):
    with pytest.raises(BenchError) as caught:
        _spec(min_pairs=min_pairs)
    assert caught.value.code == "HB-USR-002"
    assert _spec(min_pairs=1).min_pairs == 1


def test_duplicate_pair_key_is_refused():
    twice = _pairs({"a": [1], "b": [1]}) + _pairs({"a": [0]})
    with pytest.raises(BenchError) as caught:
        verdicts.verdict(_spec(), twice, [], {})
    assert caught.value.code == "HB-USR-002"


@pytest.mark.parametrize("bad", ["0.5", "2"])
def test_non_binary_primary_is_refused(bad):
    pairs = _pairs({"a": [1], "b": [1]})
    pairs[0] = Pair("a", 1, D(0), D(bad), None, None, None, None)
    with pytest.raises(BenchError) as caught:
        verdicts.verdict(_spec(), pairs, [], {})
    assert caught.value.code == "HB-USR-002"
    assert _run({"a": [1, 0], "b": [1]}).n_pairs == 3


def test_a_pair_outside_the_strata_is_refused():
    pairs = _pairs({"a": [1], "b": [1], "zz": [1]})
    with pytest.raises(BenchError) as caught:
        verdicts.verdict(_spec(), pairs, [], {})
    assert caught.value.code == "HB-USR-002"


def test_unreadable_seed_is_refused():
    with pytest.raises(BenchError) as caught:
        verdicts.verdict(_spec(seed=2**63), _pairs({"a": [1], "b": [1]}), [], {})
    assert caught.value.code == "HB-USR-002"


# ---------------------------------------------------------------- intervals

def test_normal_approximation_400_pairs():
    """Two tasks of 200 pairs (60 up, 20 down, 120 equal: mean 0.20, variance 0.36). The bootstrap bounds sit
    within 0.005 of the normal interval 0.20 +- 1.96 * 0.03 (observed gap in design S6: 0.0013)."""
    task = [1] * 60 + [-1] * 20 + [0] * 120
    v = _run({"a": task, "b": task})
    se = math.sqrt(0.36 / 200 / 2)
    assert v.effect == D("0.2")
    assert float(v.interval[0]) == pytest.approx(0.2 - 1.959963984540054 * se, abs=0.005)
    assert float(v.interval[1]) == pytest.approx(0.2 + 1.959963984540054 * se, abs=0.005)


GOLD = {"a": [1, 0, 1], "b": [0, -1, 1]}


def test_golden_interval_and_draws():
    """Pins this Python's random stream (T-S4's assumption) and the interval bytes of a 6-pair fixture."""
    r = stats.rng(424242, "effect")
    assert [repr(r.random()) for _ in range(5)] == [
        "0.1990313342853013", "0.14256786527138277", "0.615137149403558", "0.08693591708737214",
        "0.26912979200469334"]
    v = _run(GOLD)
    assert v.effect == D("0.3333333333333333333333333333")
    assert v.interval == (D("-0.1666666666666666666666666667"), D("0.8333333333333333333333333333"))


def test_stratified_equal_task_weight():
    v = _run({"a": [1] * 5 + [0] * 5, "b": [0] * 90})
    assert v.effect == D("0.25")
    assert v.pairs_by_task == {"a": 10, "b": 90}


def test_per_task_and_both_tasks():
    up = [1] * 5
    both = _run({"a": up, "b": up})
    assert both.label == L.BETTER and both.both_tasks is True
    thin = _run({"a": up, "b": [1]})
    assert thin.label == L.BETTER and thin.both_tasks is False
    split = _run({"a": up, "b": [1, 0, -1, 0, 1, 0]})
    assert split.label == L.BETTER and split.both_tasks is False
    down = _run({"a": [-1] * 5, "b": [-1] * 5})
    assert down.label == L.WORSE and down.both_tasks is True
    for diffs in ({"a": [1, -1], "b": [0, 0]}, {"a": [0] * 4, "b": [0] * 4}):
        assert _run(diffs).both_tasks is None


def test_level_uses_corrected_alpha():
    narrow = _run(GOLD)
    wide = _run(GOLD, alpha_per_test=D("0.05") / 45, resamples=18000)
    assert wide.interval == (D("-0.5"), D("1"))
    assert wide.interval[0] < narrow.interval[0] and wide.interval[1] > narrow.interval[1]
    assert wide.level == 1 - D("0.05") / 45


def test_holm_verdict_interval_equals_bonferroni():
    out = {}
    for method in ("bonferroni", "holm", "none"):
        alpha_pt, rule = power.level_for(method, D("0.05"), 45)
        assert verdicts.alpha_per_test(_prereg(method)) == alpha_pt
        out[method] = _run(GOLD, method=method, alpha_per_test=alpha_pt, level_rule=rule,
                           resamples=verdicts.resamples_for(alpha_pt))
    bonf, holm, none = out["bonferroni"], out["holm"], out["none"]
    assert (holm.interval, holm.level, holm.alpha_per_test) == (bonf.interval, bonf.level, bonf.alpha_per_test)
    assert holm.method == "holm" and bonf.method == "bonferroni"
    assert holm.level_rule == "alpha/m (Bonferroni; Holm's first step)" != bonf.level_rule
    assert none.interval[0] > holm.interval[0] and none.interval[1] < holm.interval[1]


# ---------------------------------------------------------------- order, labels, strata

def _expected_label(v, spec, diffs):
    empty = any(not diffs.get(t) for t in spec.tasks)
    n = 0 if empty else v.n_pairs
    lo, hi = v.interval if v.interval is not None else (D(0), D(0))
    return verdicts.label_for(n, spec.min_pairs, lo, hi, spec.mde)


@settings(max_examples=25, deadline=None)
@given(
    st.dictionaries(st.sampled_from(["a", "b"]), st.lists(st.sampled_from([-1, 0, 1]), max_size=6)),
    st.randoms(use_true_random=False),
)
def test_input_order_never_changes_a_verdict(diffs, shuffler):
    spec = _spec(min_pairs=2)
    pairs = _pairs(diffs)
    shuffled = list(pairs)
    shuffler.shuffle(shuffled)
    first = verdicts.verdict(spec, pairs, [], {})
    second = verdicts.verdict(spec, shuffled, [], {})
    assert first == second
    assert first.n_pairs == sum(len(v) for v in diffs.values())
    assert first.label is not None
    assert first.label == _expected_label(first, spec, diffs)  # the label invariant (RV-SIM 4)


def test_empty_stratum_is_not_recorded():
    v = _run({"a": [1, 1, 1]}, min_pairs=3)
    assert v.label == L.NOT_RECORDED
    assert v.reason == "task b: 0 pairs recorded"
    assert v.n_pairs >= 3
    assert v.interval is None


def test_adding_a_quantity_does_not_move_the_effect_interval():
    tokens = {"a": [(100, 120)] * 3, "b": [(100, 90)] * 3}
    assert _run(GOLD, tokens=tokens).interval == _run(GOLD).interval


def test_ratio_reference_and_not_recorded():
    same = {"a": [(100, 200)] * 3, "b": [(50, 100)] * 3}
    got = _run(GOLD, tokens=same).token_ratio
    assert got == Ratio(r=D(2), lo=D(2), hi=D(2))
    zero = _run(GOLD, tokens={"a": [(0, 5)] * 3, "b": [(0, 5)] * 3})
    assert zero.token_ratio is None and zero.statement is None
    assert _run(GOLD).token_ratio is None
    partial = _pairs(GOLD, tokens=same)
    partial[0] = Pair("a", 1, D(0), D(1), None, 200, None, None)
    assert verdicts.verdict(_spec(), partial, [], {}).token_ratio is None
    walls = {"a": [(1000, 1500)] * 3, "b": [(1000, 1500)] * 3}
    assert _run(GOLD, wall=walls).wall_ratio == D("1.5")
    assert _run(GOLD).wall_ratio is None


RATIO_FX = {"a": [(100, 150), (200, 150), (300, 500)], "b": [(100, 80), (100, 120), (100, 100)]}


def test_ratio_interval_golden():
    """Pins the ratio's own stream and its stratified resample (reference: naive Fractions, key "ratio")."""
    v = _run(GOLD, tokens=RATIO_FX)
    assert v.token_ratio == Ratio(r=D("1.22"), lo=D("0.8625"), hi=D("1.49"))


def test_degenerate_sample_is_labelled_by_rule_not_hidden():
    up = _run({"a": [1] * 3, "b": [1] * 3}, min_pairs=7, required_pairs=93)
    assert up.label == L.NOT_RECORDED and up.n_pairs == 6 and up.required_pairs == 93
    up = _run({"a": [1] * 3, "b": [1] * 3}, min_pairs=3, required_pairs=93)
    assert up.label == L.BETTER and up.n_pairs == 6 and up.required_pairs == 93
    flat = _run({"a": [0] * 3, "b": [0] * 3}, min_pairs=3, required_pairs=93)
    assert flat.label == L.NO_DIFFERENCE and flat.n_pairs == 6


def test_e1_demo_shape():
    v = _run({"a": [1, 0, 0], "b": [1, 0, 0]}, min_pairs=3)
    assert v.label == L.UNDERPOWERED and v.n_pairs == 6


# ---------------------------------------------------------------- collect on real CellViews

def _collect(cells, **kw):
    return verdicts.collect(cells, _spec(**kw))


def _full(task="a", reps=(1, 2), **kw):
    return [_cell(task, rep, arm, **kw) for rep in reps for arm in ("off", "on")]


def test_collect_forms_pairs_with_tokens_and_wall():
    cells = [_cell("a", 1, "off", 0, tokens=100, wall=1000), _cell("a", 1, "on", 1, tokens=150, wall=1200)]
    pairs, excluded, na = _collect(cells)
    assert excluded == [] and na == {}
    assert pairs == [Pair("a", 1, D(0), D(1), 100, 150, 1000, 1200)]
    unrecorded = _collect([_cell("a", 1, "off", 0, tokens=None), _cell("a", 1, "on", 1)])[0]
    assert (unrecorded[0].ref_tokens, unrecorded[0].treat_tokens) == (None, 100)


@pytest.mark.parametrize("form", ["arm", "pack"])
def test_collect_reads_task_and_rep_from_either_label_form(form):
    labels = {arm: f"a.c.{form}-{arm}.r2" for arm in ("off", "on")}
    pairs = _collect([_cell("a", 2, arm, 1, label=labels[arm]) for arm in ("off", "on")])[0]
    assert [(p.task, p.rep) for p in pairs] == [("a", 2)]


def test_collect_refuses_an_unparseable_label():
    with pytest.raises(BenchError) as caught:
        _collect([_cell("a", 1, "off", label="nonsense")])
    assert caught.value.code == "HB-USR-002"


def test_collect_refuses_a_second_cell_for_the_same_half():
    with pytest.raises(BenchError) as caught:
        _collect([_cell("a", 1, "off", cid="x"), _cell("a", 1, "off", cid="y")])
    assert caught.value.code == "HB-USR-002"


def test_collect_refuses_a_non_binary_primary():
    with pytest.raises(BenchError) as caught:
        _collect([_cell("a", 1, "off", Decimal("0.5")), _cell("a", 1, "on", 1)])
    assert caught.value.code == "HB-USR-002"


def test_check_tampered_is_listed_not_dropped():
    tampered = _cell("a", 3, "on", None, reason="invalid (check tampered)")
    partner = _cell("a", 3, "off", 0)
    base = _full()
    pairs, excluded, na = _collect(base + [tampered, partner])
    assert na == {"invalid (check tampered)": 1}
    assert ("a-on-3", "invalid (check tampered)") in excluded
    assert ("a-off-3", "pair partner not recorded (a-on-3)") in excluded
    kept = verdicts.verdict(_spec(tasks=("a",)), pairs, excluded, na)
    plain = verdicts.verdict(_spec(tasks=("a",)), *_collect(base)[:2], {})
    assert kept.label == plain.label and kept.interval == plain.interval
    assert kept.na_counts == {"invalid (check tampered)": 1} and kept.excluded == excluded


def test_one_blocked_cell_shows_excluded_1():
    cells = _full() + [_cell("a", 3, "off", 0, outcome="blocked", cause="auth", cid="c-blocked")]
    _, excluded, na = _collect(cells, tasks=("a",))
    assert excluded == [("c-blocked", "blocked (auth)")]
    assert na == {}


def test_collect_reasons_in_first_match_order():
    cells = [
        _cell("E1", 1, "off", 1, cid="cal"),
        _cell("a", 1, "off", 1, validity="invalid (infrastructure)", outcome="failed", cause="x", cid="inv"),
        _cell("a", 2, "off", 1, outcome="failed", cause="agent", cid="failed"),
        _cell("a", 3, "off", None, outcome="timed_out", cid="to", reason="no primary"),
        _cell("a", 4, "off", 1, outcome="timed_out", cid="to-ok"),
        _cell("a", 4, "on", 1, cid="to-ok-partner"),
        _cell("a", 5, "off", None, cid="na", reason="check exceeded its bound"),
        _cell("zz", 1, "off", 1, harness="other", cid="out-of-scope"),
        _cell("a", 6, "other-arm", 1, cid="out-of-scope-arm"),
    ]
    pairs, excluded, na = _collect(cells, tasks=("a",))
    assert dict(excluded) == {
        "cal": "calibration or non-admitted task",
        "inv": "invalid (infrastructure)",
        "failed": "failed (agent)",
        "to": "timed_out (not recorded)",
        "na": "check exceeded its bound",
    }
    assert [(p.task, p.rep) for p in pairs] == [("a", 4)]
    assert na == {"check exceeded its bound": 1}


_KINDS = ["ok0", "ok1", "na", "tamper", "invalid", "blocked", "timeout_ok", "absent", "other_harness"]


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from(_KINDS), min_size=18, max_size=18))
def test_conservation_every_cell_in_a_pair_or_excluded(kinds):
    slots = [(t, r, a) for t in ("a", "b", "cal") for r in (1, 2, 3) for a in ("off", "on")]
    cells, in_scope, na_branch = [], 0, 0
    for (task, rep, arm), kind in zip(slots, kinds, strict=True):
        if kind == "absent":
            continue
        kw = {
            "ok0": {"value": 0}, "ok1": {"value": 1},
            "na": {"value": None, "reason": "check exceeded its bound"},
            "tamper": {"value": None, "reason": "invalid (check tampered)"},
            "invalid": {"value": 1, "validity": "invalid (infrastructure)"},
            "blocked": {"value": None, "outcome": "blocked", "cause": "auth"},
            "timeout_ok": {"value": 1, "outcome": "timed_out"},
            "other_harness": {"value": 1, "harness": "other"},
        }[kind]
        cells.append(_cell(task, rep, arm, **kw))
        if kind != "other_harness":
            in_scope += 1
            if kind in ("na", "tamper") and task != "cal":
                na_branch += 1
    pairs, excluded, na = _collect(cells)
    assert 2 * len(pairs) + len(excluded) == in_scope
    ids = [cid for cid, _ in excluded]
    assert len(ids) == len(set(ids))
    assert sum(na.values()) == na_branch


def test_calibration_cells_do_not_change_any_verdict():
    base = _full("a") + _full("b")
    noise = _full("E1", value=0) + _full("E2", value=1, tokens=5)
    spec = _spec()
    plain = verdicts.verdict(spec, *_collect(base)[:2], {})
    noisy_pairs, noisy_excluded, _na = _collect(base + noise)
    noisy = verdicts.verdict(spec, noisy_pairs, [], {})
    assert noisy_pairs == _collect(base)[0]
    assert noisy.effect == plain.effect and noisy.interval == plain.interval and noisy.label == plain.label
    assert len(noisy_excluded) == len(noise)


# ---------------------------------------------------------------- coverage (slow: the method claim)

def _coverage(n_datasets: int, kind: str) -> int:
    """S4 / S5 reconstructed (the original script was not committed): 27 + 26 pairs, reference rate 0.5,
    treatment rate 0.7 (true effect 0.20); the ratio kind adds lognormal tokens with true ratio 1.5.
    Counts how often the 95% interval (B = 2000) covers the truth."""
    gen = random.Random(20261003)
    covered = 0
    for index in range(n_datasets):
        pairs = []
        for task, size in (("a", 27), ("b", 26)):
            for rep in range(1, size + 1):
                ref = D(1 if gen.random() < 0.5 else 0)
                treat = D(1 if gen.random() < 0.7 else 0)
                tokens = (None, None)
                if kind == "ratio":
                    tokens = (round(1000 * math.exp(gen.gauss(0, 0.5))), round(1500 * math.exp(gen.gauss(0, 0.5))))
                pairs.append(Pair(task, rep, ref, treat, tokens[0], tokens[1], None, None))
        v = verdicts.verdict(_spec(seed=index + 1), pairs, [], {})
        if kind == "effect":
            covered += v.interval is not None and v.interval[0] <= D("0.2") <= v.interval[1]
        else:
            ratio = v.token_ratio
            covered += ratio is not None and ratio.lo <= D("1.5") <= ratio.hi
    return covered


# Measured at N = 1,000 with this generator (X-H1b green). The design's 936 and 948 came from the S4 and S5
# scripts, which were never committed; a reconstruction cannot reproduce them (FIXT-A: measured beside the design's).
GOLDEN_COVERAGE = {"effect": 940, "ratio": 932}


@COVERAGE_RUN
@pytest.mark.parametrize("kind", ["effect", "ratio"])
def test_coverage_golden(kind):
    """A regression pin on this Python's random stream, not the method claim. A golden failure with a green band
    is a stream change; a band failure is the R-H2 finding, recorded, never a re-seed."""
    assert _coverage(1000, kind) == GOLDEN_COVERAGE[kind]


@COVERAGE_RUN
@pytest.mark.parametrize("kind", ["effect", "ratio"])
def test_coverage_band(kind):
    """The method claim at N = 4,000 datasets: coverage within [0.93, 0.97]. Below 0.93 is the R-H2 finding
    (BCa or studentised intervals), recorded and never fixed by a re-seed."""
    coverage = _coverage(4000, kind) / 4000
    assert 0.93 <= coverage <= 0.97, f"{kind} coverage {coverage:.4f}"
