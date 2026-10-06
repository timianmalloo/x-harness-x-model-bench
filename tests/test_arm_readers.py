"""The pack-section readers pair per comparison (W1-A section 5.1, E3): a run whose plan compares `off` with `candidate` is
paired, sampled, rendered and resolved as that pair, never as the legacy `on`/`off` one."""

from __future__ import annotations

from decimal import Decimal

from harness_bench import board as board_mod
from harness_bench import (
    egress,  # noqa: F401  (first: egress and report.html import each other)
    stats,
    views,
)
from harness_bench.report import html
from harness_bench.report import pack_improvement as pi
from harness_bench.report import summaries as s


def _m(value):
    return stats.Measure(Decimal(str(value)) if value is not None else None, None)


def _cell(cid, arm, rep=1, p1=None, combo="c1"):
    na = views.Measure(None, "not graded")
    scores = {} if p1 is None else {"pass_at_1": _m(p1)}
    return views.CellView(
        cell_id=cid, task="X1", rep=rep, label=f"X1.{combo}.arm-{arm}.r{rep}", combo=combo, arm=arm, harness="claude-code",
        model="claude-sonnet-5", outcome="completed", cause=None, code=None, validity="valid", validity_code=None,
        wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na, tokens=None, tokens_reason="not graded", scores=scores,
    )


def _plan_by_id(cells):
    return {c.cell_id: {"task": "X1", "rep": c.rep} for c in cells}


def test_pairs_follow_the_named_arms():
    cells = [_cell("o", "off"), _cell("c", "candidate"), _cell("i", "incumbent")]
    assert pi.pairs(cells, _plan_by_id(cells)) == []  # the legacy off/on default finds no pair here
    (pair,) = pi.pairs(cells, _plan_by_id(cells), ("off", "candidate"))
    assert pair.off.cell_id == "o" and pair.on.cell_id == "c"


def test_sample_cells_follow_the_plan_comparisons():
    cells = [_cell("o1", "off", p1=0.0), _cell("c1", "candidate", p1=1.0), _cell("i1", "incumbent", p1=0.0)]
    view = views.RunView(run_id="r", plan={"arms": {"off": {}, "incumbent": {}, "candidate": {}},
                                           "comparisons": [["off", "candidate"]]},
                         completed=True, grading_id="g", catalog_version="0.5", cells=cells)
    assert s.sample_pack_on_cells(view) == ("c1",)


def test_the_pack_effect_section_names_each_pair():
    def row(pair):
        return board_mod.PackEffectRow(combo="c1", measure="pass_at_1", pair=pair, label=None,
                                       delta=stats.Interval(Decimal("0.1"), Decimal(0), Decimal("0.2"), 4, None))
    rows = [row(("off", "candidate")), row(("off", "incumbent"))]
    b = board_mod.Board(run_id="r", catalog_version="0.5", params=stats.Params(seed=1, resamples=2000), primary="gated",
                        primary_reason=None, rows=[], pack_effect=board_mod.PackEffect(None, (), rows))
    out = str(html._pack_effect(b, {"c1": "c1"}))
    assert "off vs candidate" in out and "off vs incumbent" in out
    assert out.count('id="pack-effect-off-candidate-caption"') == 1 and out.count('id="pack-effect-off-incumbent-caption"') == 1


def test_a_pack_ref_of_a_multi_pair_run_needs_its_pair():
    def row(pair, point):
        return board_mod.PackEffectRow(combo="c1", measure="pass_at_1", pair=pair, label=None,
                                       delta=stats.Interval(Decimal(point), None, None, 4, None))
    rows = [row(("off", "candidate"), "0.1"), row(("off", "incumbent"), "0.2")]
    b = board_mod.Board(run_id="r", catalog_version="0.5", params=stats.Params(seed=1, resamples=2000), primary="gated",
                        primary_reason=None, rows=[], pack_effect=board_mod.PackEffect(None, (), rows))
    view = views.RunView(run_id="r", plan={}, completed=True, grading_id="g", catalog_version="0.5", cells=[])
    assert s.resolve_ref("pack:c1|pass_at_1", b, view) is None
    assert s.resolve_ref("pack:c1|pass_at_1|off>incumbent", b, view).interval.point == Decimal("0.2")
