"""Ring gates (W1-H section 11.3): one red fixture per kind, the regression signal and admission."""

from __future__ import annotations

import random
import re
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench import gates, plan, verdicts, views
from harness_bench.errors import BenchError
from harness_bench.gates import GateKind

D = Decimal
PRIMARY = "property_check_pass"
TAMPERED = "invalid (check tampered)"
GRADER = "HB-GRD-003 grader property failed: ValueError"


# ---------------------------------------------------------------- builders

def _cell(task, rep, arm="off", *, harness="cc", combo="c", outcome="completed", cause=None, code=None,
          primary=1, reason=None, extra=None, cid=None, tokens=100):
    """`primary`: 0, 1, None (an NA row carrying `reason`) or "absent" (no property_check_pass row at all)."""
    na = views.Measure(None, "not graded")
    scores = dict(extra or {})
    if primary != "absent":
        scores[PRIMARY] = views.Measure(primary, reason if primary is None else None)
    label = plan.Cell(task, "v1", 1, combo, harness, "m", arm, rep, 60).label
    return views.CellView(
        cell_id=cid or f"{task}-{arm}-{rep}", label=label, combo=combo, pack=arm, harness=harness, model="m",
        outcome=outcome, cause=cause, code=code, validity="valid", validity_code=None,
        wall_ms=views.Measure(1000), model_ms=na, tool_ms=na, idle_ms=na,
        tokens={"m": {"uncached_input": tokens, "cache_read": 0, "cache_write": 0, "output": 0}},
        tokens_reason=None, scores=scores)


def _view(cells, tasks=("a", "b"), ring=True):
    body = {"tasks": {t: {} for t in tasks}}
    if ring:
        body["ring"] = {"tag": "r1", "hash": "ab" * 32}
    return views.RunView(run_id="r", plan=body, completed=True, grading_id="g", catalog_version=None,
                         cells=list(cells))


def _clean_cells(tasks=("a", "b"), reps=(1, 2)):
    return [_cell(t, r, arm, primary=(1 if arm == "on" else 0), extra={"m2": views.Measure(5)})
            for t in tasks for r in reps for arm in ("off", "on")]


def _kinds(items):
    return [(i.kind, i.ident) for i in items]


def _pilot(cells, hidden=(), unbiased=(), **kw):
    return gates.pilot(_view(cells), list(hidden), list(unbiased), **kw)


# ---------------------------------------------------------------- one red fixture per kind (TA 4)

def _fx_cell_lost():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", outcome="failed", code="HB-CELL-199", primary=None,
                                         reason="x")], (), ()


def _fx_bnd_a():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", outcome="failed", code="HB-CELL-107", primary=None,
                                         reason="x")], (), ()


def _fx_grader_error():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason=GRADER)], (), ()


def _fx_metric_unrecorded():
    cells = [_cell(t, r, arm, extra={"m2": views.Measure(None, "not graded")})
             for t in ("a",) for r in (1, 2) for arm in ("off", "on")]
    return cells, (), ()


def _fx_primary_unrecorded():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason="check exceeded its bound")], (), ()


def _fx_task_no_primary():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", primary="absent")], (), ()


def _fx_tampered():
    return _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason=TAMPERED)], (), ()


def _fx_suspend():
    return _clean_cells(("a",)), (), ["c5"]


def _fx_hidden():
    return _clean_cells(("a",)), ["c3"], ()


FIXTURES = {
    GateKind.CELL_LOST: _fx_cell_lost,
    GateKind.BND_A: _fx_bnd_a,
    GateKind.GRADER_ERROR: _fx_grader_error,
    GateKind.METRIC_UNRECORDED: _fx_metric_unrecorded,
    GateKind.PRIMARY_UNRECORDED: _fx_primary_unrecorded,
    GateKind.TASK_NO_PRIMARY: _fx_task_no_primary,
    GateKind.CHECK_TAMPERED: _fx_tampered,
    GateKind.SUSPEND_BLIND: _fx_suspend,
    GateKind.HIDDEN_NONDETERMINISTIC: _fx_hidden,
}


def test_every_gate_kind_has_a_red_fixture():
    assert len(GateKind) == 9
    assert set(FIXTURES) == set(GateKind)
    for kind, build in FIXTURES.items():
        cells, hidden, unbiased = build()
        assert {i.kind for i in _pilot(cells, hidden, unbiased)} == {kind.value}, kind


def test_clean_view_passes():
    cells = _clean_cells()
    assert _pilot(cells) == []
    assert gates.pilot(_view(cells), [], []) == []
    assert gates.ring_items(_view(cells), gates.EMPTY) == []
    assert gates.EMPTY is not None and len(gates.EMPTY) == 0
    with pytest.raises(TypeError):
        gates.EMPTY["a"] = frozenset()  # type: ignore[index]


# ---------------------------------------------------------------- cell-level kinds

def test_gate_cell_lost_failed_and_blocked():
    cells = _clean_cells(("a",)) + [
        _cell("b", 1, "off", outcome="failed", code="HB-CELL-199", primary=None, reason="x", cid="f1"),
        _cell("b", 1, "on", outcome="stopped", code="HB-CELL-201", primary=None, reason="x", cid="b1"),
        _cell("b", 2, "off", outcome="completed", code="HB-CELL-202", primary=0, cid="b2"),
    ]
    items = _pilot(cells)
    assert _kinds(items) == [("cell-lost", "b1"), ("cell-lost", "b2"), ("cell-lost", "f1")]


def test_gate_cell_lost_by_infrastructure_cause():
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", outcome="timed_out", code="HB-CELL-112", primary=1,
                                          cid="d1")]
    items = _pilot(cells)
    assert _kinds(items) == [("cell-lost", "d1")]
    assert "HB-CELL-112" in items[0].detail


def test_gate_timed_out_with_primary_is_not_a_loss():
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", outcome="timed_out", code="HB-CELL-301", primary=1)]
    assert _pilot(cells) == []


def test_gate_bnd_a_beats_cell_lost():
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", outcome="failed", code="HB-CELL-107", primary=None,
                                          reason="x", cid="p1")]
    assert _kinds(_pilot(cells)) == [("bnd-a-loss", "p1")]


def test_gate_grader_error_once_per_cell_not_also_primary_unrecorded():
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason=GRADER, cid="g1",
                                          extra={"m2": views.Measure(None, GRADER), "m3": views.Measure(None, GRADER)})]
    assert _kinds(_pilot(cells)) == [("grader-error", "g1")]


def test_gate_check_tampered_beats_primary_unrecorded():
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason=TAMPERED, cid="t1")]
    assert _kinds(_pilot(cells)) == [("check-tampered", "t1")]


@pytest.mark.parametrize("reason", ["check exceeded its bound", "invalid (check output malformed)"])
def test_gate_other_na_is_primary_unrecorded(reason):
    cells = _clean_cells(("a",)) + [_cell("b", 1, "off", primary=None, reason=reason, cid="n1")]
    assert _kinds(_pilot(cells)) == [("primary-not-recorded", "n1")]


def test_gate_metric_not_recorded_with_expected_na_exception():
    na = views.Measure(None, "not graded")
    cells = [_cell("a", r, arm, extra={"m2": na}) for r in (1, 2) for arm in ("off", "on")]
    cells += [_cell("b", 1, "off", extra={"m2": na}), _cell("b", 1, "on", extra={"m2": views.Measure(5)})]
    view = _view(cells)
    first = gates.pilot(view, [], [])
    assert _kinds(first) == [("metric-not-recorded", "a/m2")]
    assert "not graded" in first[0].detail
    assert gates.pilot(view, [], [], expected_na={"a": frozenset({"m2"})}) == []
    assert _kinds(gates.pilot(view, [], [], expected_na={"b": frozenset({"m2"})})) == [("metric-not-recorded", "a/m2")]
    with pytest.raises(TypeError):
        gates.pilot(view, [], [], {"a": frozenset({"m2"})})  # type: ignore[misc]


def test_gate_task_no_primary_means_no_row_not_a_none_value():
    cells = _clean_cells(("a",)) + [_cell("c", 1, "off", primary="absent"), _cell("c", 1, "on", primary="absent"),
                                    _cell("b", 1, "off", primary=None, reason="check exceeded its bound", cid="n1")]
    assert _kinds(_pilot(cells)) == [("primary-not-recorded", "n1"), ("task-no-primary", "c")]


def test_gate_hidden_tests_nondeterministic_one_item_per_id():
    items = _pilot(_clean_cells(), hidden=["c7", "c3", "c3"])
    assert _kinds(items) == [("hidden-tests-nondeterministic", "c3"), ("hidden-tests-nondeterministic", "c7")]


def test_gate_suspend_detector_blind_one_item_per_id():
    assert _kinds(_pilot(_clean_cells(), unbiased=["c5"])) == [("suspend-detector-blind", "c5")]


@pytest.mark.parametrize("which", [0, 1])
def test_pilot_refuses_unread_lists(which):
    args = [[], []]
    args[which] = None
    with pytest.raises(BenchError) as raised:
        gates.pilot(_view(_clean_cells()), *args)
    assert raised.value.code == "HB-USR-002"


def _mixed_cells():
    return _clean_cells(("a",)) + [
        _cell("b", 1, "off", outcome="failed", code="HB-CELL-199", primary=None, reason="x", cid="f1"),
        _cell("b", 1, "on", outcome="failed", code="HB-CELL-107", primary=None, reason="x", cid="p1"),
        _cell("b", 2, "off", primary=None, reason=TAMPERED, cid="t1"),
        _cell("b", 2, "on", primary=None, reason=GRADER, cid="g1"),
        _cell("b", 3, "off", primary=None, reason="check exceeded its bound", cid="n1"),
        _cell("c", 1, "off", primary="absent"),
    ]


def test_pilot_output_is_sorted_unique_and_order_independent_baseline():
    items = _pilot(_mixed_cells(), hidden=["h1"], unbiased=["u1"])
    assert _kinds(items) == [
        ("bnd-a-loss", "p1"), ("cell-lost", "f1"), ("check-tampered", "t1"), ("grader-error", "g1"),
        ("hidden-tests-nondeterministic", "h1"), ("primary-not-recorded", "n1"), ("suspend-detector-blind", "u1"),
        ("task-no-primary", "c"),
    ]


@settings(max_examples=40, deadline=None)
@given(st.randoms(use_true_random=False), st.lists(st.sampled_from(["h1", "h2", "h3"]), max_size=6))
def test_pilot_output_is_sorted_unique_and_order_independent(shuffler, hidden):
    cells = _mixed_cells()
    baseline = _pilot(cells, hidden=sorted(hidden), unbiased=["u1"])
    shuffled = list(cells)
    shuffler.shuffle(shuffled)
    again = _pilot(shuffled, hidden=list(reversed(hidden)), unbiased=["u1"])
    keys = _kinds(baseline)
    assert again == baseline
    assert keys == sorted(set(keys))
    assert len(baseline) >= 8


# ---------------------------------------------------------------- pack_regression

def _ring_cells(diffs, task="a", harness="cc"):
    out = []
    for index, d in enumerate(diffs, 1):
        ref, treat = {1: (0, 1), -1: (1, 0), 0: (0, 0)}[d]
        out.append(_cell(task, index, "incumbent", primary=ref, harness=harness))
        out.append(_cell(task, index, "candidate", primary=treat, harness=harness))
    return out


def _regress(diffs, mde="0.30", tasks=("a",), **kw):
    return gates.pack_regression(_view(_ring_cells(diffs, **kw), tasks=tasks), {"security": D(mde)})


@pytest.mark.parametrize(("diffs", "mde", "expect"), [
    pytest.param([-1] * 10, "0.30", "regression signal", id="hi-below-zero"),
    pytest.param([0] * 10, "0.30", "no regression detected at 0.30", id="hi-equals-zero"),
    pytest.param([-1, 1] * 10, "0.30", "no regression detected at 0.30", id="straddle"),
    pytest.param([1] * 10, "0.25", "no regression detected at 0.25", id="good-direction"),
])
def test_pack_regression_table(diffs, mde, expect):
    result = _regress(diffs, mde)
    assert result == {"security": expect}
    assert not re.search(r"better|worse|dominates", result["security"])


def test_pack_regression_missing_arm_is_withheld():
    cells = [c for c in _ring_cells([1, 1, 1]) if "candidate" not in c.label]
    view = _view(cells, tasks=("a",))
    assert gates.pack_regression(view, {"security": D("0.30")}) == {
        "security": "Result withheld: ring is missing candidate."}
    only_candidate = _view([c for c in _ring_cells([1, 1]) if "incumbent" not in c.label], tasks=("a",))
    assert gates.pack_regression(only_candidate, {"security": D("0.30")}) == {
        "security": "Result withheld: ring is missing incumbent."}


def test_pack_regression_empty_stratum_is_withheld_with_the_reason():
    view = _view(_ring_cells([-1, -1]), tasks=("a", "b"))
    assert gates.pack_regression(view, {"security": D("0.30")}) == {
        "security": "Result withheld: task b: 0 pairs recorded."}


def test_pack_regression_seed_is_the_ring_seed(monkeypatch):
    seen = []
    real = verdicts.verdict

    def spy(spec, pairs, excluded, na_counts):
        seen.append(spec)
        return real(spec, pairs, excluded, na_counts)

    monkeypatch.setattr(verdicts, "verdict", spy)
    _regress([-1] * 5)
    assert len(seen) == 1
    spec = seen[0]
    assert spec.seed == verdicts.seed_for("ab" * 32, "security", "ring", ("incumbent", "candidate"))
    assert (spec.comparison, spec.method, spec.alpha_per_test, spec.min_pairs) == (
        ("incumbent", "candidate"), "none", D("0.05"), 1)
    assert spec.resamples == verdicts.resamples_for(D("0.05"))
    assert spec.tasks == ("a",) and spec.mde == D("0.30")


def test_pack_regression_without_a_ring_raises():
    with pytest.raises(BenchError) as raised:
        gates.pack_regression(_view(_ring_cells([1]), ring=False), {"security": D("0.30")})
    assert raised.value.code == "HB-USR-002"


def test_pack_regression_refuses_more_than_one_property_or_harness():
    with pytest.raises(BenchError) as many:
        gates.pack_regression(_view(_ring_cells([1])), {"p": D("0.3"), "q": D("0.3")})
    assert many.value.code == "HB-USR-002"
    two = _ring_cells([1], harness="cc") + _ring_cells([1], harness="cx", task="a")
    with pytest.raises(BenchError) as harnesses:
        gates.pack_regression(_view(two, tasks=("a",)), {"security": D("0.3")})
    assert harnesses.value.code == "HB-USR-002"
    assert "cc" in str(harnesses.value) and "cx" in str(harnesses.value)


# ---------------------------------------------------------------- admission (EV-8, W0 section 8)

def _off(values, arm="off", task="a"):
    return [_cell(task, i, arm, primary=v) for i, v in enumerate(values, 1)]


@pytest.mark.parametrize(("values", "expect"), [
    pytest.param([1, 1, 1], (0, "saturated"), id="A1"),
    pytest.param([0, 0, 0], (0, "floor"), id="A2"),
    pytest.param([1, 1, 0], (1, ""), id="A3"),
    pytest.param([0, 0, 1], (1, ""), id="A4"),
])
def test_admission_table(values, expect):
    assert gates.admission(_view(_off(values)), ["a"]) == {"a": expect}


def test_admission_honours_the_off_arm_argument_a5():
    cells = _off([1, 0, 1]) + _off([1, 1, 1], arm="on") + _off([1, 1, 1], arm="base", task="a")
    view = _view(cells)
    assert gates.admission(view, ["a"]) == {"a": (1, "")}
    assert gates.admission(view, ["a"], off_arm="on") == {"a": (0, "saturated")}
    assert gates.admission(view, ["a"], off_arm="base") == {"a": (0, "saturated")}


def test_admission_decides_each_task_alone():
    cells = _off([1, 1], task="a") + _off([0, 0], task="b") + _off([0, 1], task="c")
    assert gates.admission(_view(cells), ["a", "b", "c"]) == {
        "a": (0, "saturated"), "b": (0, "floor"), "c": (1, "")}


def test_admission_na_primary_raises():
    cells = _off([1, 1]) + [_cell("a", 3, "off", primary=None, reason="check exceeded its bound")]
    with pytest.raises(BenchError) as raised:
        gates.admission(_view(cells), ["a"])
    assert raised.value.code == "HB-USR-002"


def test_admission_task_with_no_off_arm_cell_raises():
    cells = _off([1, 1], arm="on")
    with pytest.raises(BenchError) as raised:
        gates.admission(_view(cells), ["a"])
    assert raised.value.code == "HB-USR-002"
    assert "a" in str(raised.value)


def test_admission_is_stable_under_input_order():
    cells = _off([1, 0, 1, 1])
    shuffled = list(cells)
    random.Random(7).shuffle(shuffled)
    assert gates.admission(_view(shuffled), ["a"]) == gates.admission(_view(cells), ["a"]) == {"a": (1, "")}
