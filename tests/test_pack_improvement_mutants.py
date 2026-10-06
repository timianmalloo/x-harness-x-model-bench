"""Kill-tests for the mutants `tests/mutations/pack_improvement.json` lists (design
pack-improvement-section.md section 11's seven, plus R-85's two). Four of the nine are already
killed by tests in `test_pack_improvement.py` (swap on/off in the ratio; treat NA as 0; include
invalid cells in pairs; reverse the ranking) and `test_pack_improvement.py`'s own
`test_pi_t4_blast_radius_unreadable_cascades_...` (blast radius unreadable reads as zero product
writes). This file carries the remaining four, each named after the mutant it kills.
"""

from __future__ import annotations

import json
from decimal import Decimal

from harness_bench import views
from harness_bench.report import pack_improvement as pi
from harness_bench.telemetry import codex

# ---------------------------------------------------------------------------------------------------
# "match ws itself as a sibling worktree"
# ---------------------------------------------------------------------------------------------------


def test_ws_itself_is_never_treated_as_a_sibling_worktree_even_with_a_gitdir_marker(tmp_path):
    attempt = tmp_path / "attempt-1"
    ws = attempt / "ws"
    ws.mkdir(parents=True)
    (ws / ".git").write_text("gitdir: /some/path/ws/.git/worktrees/ws\n", encoding="utf-8")
    assert pi.sibling_worktrees(attempt) == []


# ---------------------------------------------------------------------------------------------------
# "drop the Holm step" -- a two-task family where raw Fisher p (0.0286) is significant alone but its
# Holm-adjusted value (m=2, doubled: 0.0571) is not, so the group's classification only differs
# between the two if the adjustment actually ran.
# ---------------------------------------------------------------------------------------------------


def _cell(cid, task, combo, pack, rep, passed, tokens, validity="valid"):
    na = views.Measure(None, "not graded")
    return views.CellView(
        cell_id=cid, task=task, rep=rep, label=f"{task}.{combo}.pack-{pack}.r{rep}", combo=combo, arm=pack, harness="claude-code",
        model="claude-sonnet-5", outcome="completed", cause=None, code=None, validity=validity, validity_code=None,
        wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na,
        tokens={"claude-sonnet-5": {"uncached_input": tokens, "cache_read": 0, "cache_write": 0, "output": 0}},
        tokens_reason=None, scores={"pass_at_1": views.Measure(1 if passed else 0)},
    )


def _holm_view():
    """Task X1: 4 pairs, on 4/4, off 0/4 -- raw Fisher p ~= 0.0286 (verified against
    stats.fisher_exact_two_sided(4, 0, 0, 4)). Task X2: 1 pair, on 1/1, off 1/1 -- a trivial p=1
    member of the same Holm family (m=2), so Holm doubles X1's p to ~0.0571, crossing 0.05."""
    cells = []
    plan_cells = []
    for rep in range(1, 5):
        on = _cell(f"x1-on-{rep}", "X1", "c", "on", rep, True, 100)
        off = _cell(f"x1-off-{rep}", "X1", "c", "off", rep, False, 100)
        cells += [on, off]
        plan_cells += [{"cell_id": on.cell_id, "task": "X1", "rep": rep}, {"cell_id": off.cell_id, "task": "X1", "rep": rep}]
    on2 = _cell("x2-on-1", "X2", "c", "on", 1, True, 100)
    off2 = _cell("x2-off-1", "X2", "c", "off", 1, True, 100)
    cells += [on2, off2]
    plan_cells += [{"cell_id": on2.cell_id, "task": "X2", "rep": 1}, {"cell_id": off2.cell_id, "task": "X2", "rep": 1}]
    plan = {"cells": plan_cells, "profiles": {}}
    return views.RunView("r1", plan, True, "grade-1", None, cells)


def test_holm_adjustment_changes_x1s_classification_from_value_to_neutral():
    """Real code: Holm-adjusted p (~0.0571) is NOT < 0.05, so X1/c reads "neutral" (median token
    ratio 1.0, below WASTE_RATIO). A mutant that drops the Holm step and uses the raw per-task p
    (~0.0286 < 0.05) would read "value" instead -- this test fails under that mutant."""
    result = pi.assemble(_holm_view(), None, None, None, archive_present=False)
    x1 = next(g for g in result.groups if g.task == "X1")
    assert x1.cls == "neutral", f"expected Holm-adjusted p >= 0.05 to give 'neutral', got {x1.cls!r}"


# ---------------------------------------------------------------------------------------------------
# "count pack-off ceremony as pack-on" (PK-05) -- indicators are monkeypatched so the test needs no
# real archive; it exercises assemble()'s own call site, which is what the mutant changes.
# ---------------------------------------------------------------------------------------------------


def _ceremony_view():
    cells = []
    plan_cells = []
    for rep in range(1, 3):
        on = _cell(f"c5-on-{rep}", "T1", "c", "on", rep, False, 200)
        off = _cell(f"c5-off-{rep}", "T1", "c", "off", rep, True, 100)  # off passes every pair -> ceiling_off
        cells += [on, off]
        plan_cells += [{"cell_id": on.cell_id, "task": "T1", "rep": rep}, {"cell_id": off.cell_id, "task": "T1", "rep": rep}]
    plan = {"cells": plan_cells, "profiles": {}}
    return views.RunView("r1", plan, True, "grade-1", None, cells)


def _fake_indicators(run_dir, view, cell, blast_radius, outcome_event, archive_present):
    # on-cells: low ceremony (0.05, below CEREMONY_SHARE_THRESHOLD); off-cells: high (0.90).
    share = Decimal("0.90") if cell.arm == "off" else Decimal("0.05")
    na = views.Measure(None, "x")
    return pi._CellIndicators(None, views.Measure(share), False, na, False, na, na, na, na)


def test_pk05_reads_on_cell_ceremony_share_never_off(monkeypatch, tmp_path):
    """Design section 4.3/PK-05: `ceremony_share_on >= 0.20`. Real code: every on-cell's share is
    0.05 (below threshold), so PK-05 never fires, whatever the off-cells' share is. A mutant that
    reads the off-cell's share at PK-05's call site would see 0.90 and fire -- this test fails
    under that mutant."""
    monkeypatch.setattr(pi, "_cell_indicators", _fake_indicators)
    (tmp_path / "events").mkdir()
    result = pi.assemble(_ceremony_view(), None, tmp_path, None, archive_present=True)
    assert not any(f.code == "PK-05" for f in result.findings)


# ---------------------------------------------------------------------------------------------------
# R-85: "Codex local_shell_call dropped" -- CALL_TYPES must include it, or the trace silently misses
# every Codex shell command PK-01/07's ceremony/git-identity classes read (worktree add, git config).
# ---------------------------------------------------------------------------------------------------


def test_r85_codex_local_shell_call_is_counted_by_tool_inputs(tmp_path):
    row = {"type": "response_item",
           "payload": {"type": "local_shell_call", "call_id": "call_1",
                       "command": ["bash", "-lc", "git worktree add ../wt"]}}
    record = tmp_path / "s.jsonl"
    record.write_text(json.dumps(row) + "\n", encoding="utf-8")
    trace = codex.tool_inputs(record)
    assert [c.name for c in trace.calls] == ["local_shell_call"]
