"""PI-T15 (design pack-improvement-section.md section 11, slow/gate ring): the golden characterization
of `report.pack_improvement.assemble()` against the two archived grids the pack on/off analysis used,
`runs/grid-1` and `runs/grid-1-cc`. Skips cleanly (never fails) when the primary checkout's `runs/`
folder is not on this host -- the same pattern `test_grade_drift.py`'s own gate-run test uses via
`archived_runs.gate_runs_root()`.

Deviation from R-85's own PI-T15 text, found and verified this slice (not guessed): two of the four
named grid-1 PK-01 cells (`4a6250261f80ded4`, `c6a763578ef7e110`, both D1 copilot-sol) are NOT
`diverted_and_failed` under design section 4.4's own mechanical rule -- their sibling worktree's
blast-radius files are BYTE-IDENTICAL to `ws` (`diff -rq` over both matched globs, 297 files, zero
differences; read-only, checked against the real archive). The rule compares final file bytes only,
never git history, so a cell that detoured through a worktree and then converged is not "diverted"
by this definition even if an earlier manual read of its transcript called it that. The other two
named cells (`3ff04431d3b5ac27`, `757143056c649892`) DO fire, plus one the design's text does not
name (`35af195cfe821dca`, D1 cc-opus) -- this test pins the verified set, not the design's text, and
the gap is reported to the Leader at the join rather than silently reconciled.

PK-02 re-derivation (2026-09-30, path-relativization fix -- see defect-classes.md and
`report/pack_improvement.py::_relative_to_root`'s own docstring): before the fix, `classify()`
fnmatched a native record's own ABSOLUTE paths against a RELATIVE `blast_radius` glob, so
`product_write` almost never fired outside a bare `**` pattern; `stopped_without_product` ("zero
product_write calls") then read True for any on-cell whose real product write simply failed to
match. Verified by running `assemble()` against this same archive with the pre-fix module
checked out (`git checkout 418f9ff -- src/harness_bench/report/pack_improvement.py
src/harness_bench/telemetry/__init__.py`, then restored) and diffing the per-cell
`stopped_without_product`/`diverted_and_failed` values cell by cell, not by re-reading the new
output as ground truth (a golden pinned from the implementation's own output inherits its bugs --
docs/lessons/defect-classes.md):

- grid-1 PK-02 was hypothesized at the join to become 5 (dropping all 4 of the false-positive
  cells R-85 condition 1 named: `35af195cfe821dca`, `3ff04431d3b5ac27`, `757143056c649892`,
  `c4d05c98231eb3aa`). The verified, re-derived number is **7**, not 5: two of those four
  (`35af195cfe821dca` D1 cc-opus, `3ff04431d3b5ac27` D1 codex-sol) are independently confirmed
  `diverted_and_failed` -- ALL of their product code went to a sibling worktree, none to `ws` --
  so `stopped_without_product`'s own condition ("zero product_write calls in the trace", `ws`-
  relative) is genuinely, mechanically true for them too; diverted and stopped-without-product
  are not mutually exclusive in the design. Only the other two (`757143056c649892` C1 codex-sol,
  `c4d05c98231eb3aa` F1 cc-opus, whose product write DID land inside `ws`) flip from a false
  positive to correctly absent. 9 (before) - 2 (correctly dropped) = 7. The remaining 5 are the
  R-85-verified true positives (`0164cd01031f303f`, `b765f438fb811ea0`, `dfb4ae60b8a3d3a3` --
  F1 copilot-sol; `4a6250261f80ded4`, `c6a763578ef7e110` -- D1 copilot-sol).
- grid-1-cc PK-02 drops from 5 to **0** (the finding is absent, never rendered -- `count == 0` is
  dropped by `rank_findings`, design section 6): every one of its 5 pre-fix cells, including the
  one that is also genuinely `diverted_and_failed` (`c4d05c98231eb3aa`), is now shown to have a
  real, in-`ws` `product_write` once its paths are correctly relativized -- none of grid-1-cc's
  on-cells mechanically satisfy "zero product writes".
- The headline's own "N of M pack-on failures have a pack-attributed cause" is the union of
  PK-01 and PK-02's cell sets, so it moves with them: grid-1 9/11 -> **8/11** (757143056c649892
  leaves the union; the other three flips were already inside it), grid-1-cc 5/5 -> **3/5**.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from archived_runs import gate_runs_root

from harness_bench import board, composites, views
from harness_bench.report import pack_improvement as pi

ROOT = gate_runs_root().parent  # the primary checkout (gate_runs_root() is its own runs/)


def _load(name: str):
    run_dir = gate_runs_root() / name
    if not (run_dir / "plan.json").is_file():
        pytest.skip(f"archived run {name!r} is not on this host (set HB_GATE_RUNS to the runs folder)")
    view = views.load(run_dir)
    cat = composites.load_catalog(ROOT)
    board_obj = board.build(view, cat)
    result = pi.assemble(view, board_obj, run_dir, ROOT, archive_present=(run_dir / "archive").is_dir())
    return result


@pytest.mark.gate
def test_pi_t15_grid_1_cc_golden():
    result = _load("grid-1-cc")
    assert result.state == pi.STATE_FULL
    findings = {f.code: f for f in result.findings}
    # PK-02 is absent (module docstring's re-derivation): every pre-fix "stopped without product"
    # cell here, including the one that is also genuinely diverted, has a real in-`ws` product_write
    # once paths are relativized -- a count of 0 is dropped, never rendered (design section 6).
    assert set(findings) == {"PK-01", "PK-03"}
    assert findings["PK-01"].count == 3
    assert set(findings["PK-01"].evidence_cell_ids) == {"c4d05c98231eb3aa", "050c08027c79a944", "efbedb23da7173d0"}
    assert findings["PK-03"].count == 3
    assert "73c87914995c00a9" in findings["PK-03"].evidence_cell_ids
    assert "escalated" in findings["PK-03"].title  # regression_count 3 on-cell, 0 on its off partner
    assert "2.3x the tokens" in result.headline
    assert "1.3x the wall clock" in result.headline
    assert "3 of 5 pack-on failures have a pack-attributed cause" in result.headline
    assert result.population_caveats == ()  # every combo x arm here has its full planned population


@pytest.mark.gate
def test_pi_t15_grid_1_golden():
    result = _load("grid-1")
    assert result.state == pi.STATE_FULL
    findings = {f.code: f for f in result.findings}
    assert set(findings) >= {"PK-01", "PK-02", "PK-03", "PK-04", "PK-05", "PK-07"}
    # R-85's own named superset, minus the two D1 copilot-sol cells this slice's own forensic check
    # (module docstring above) found are not byte-diverted -- ⊇ {3ff04431d3b5ac27, 757143056c649892}.
    assert {"3ff04431d3b5ac27", "757143056c649892"} <= set(findings["PK-01"].evidence_cell_ids)
    # PK-02 re-derivation (module docstring): 7, not the join's hypothesized 5 -- two of the four
    # originally-named false positives are independently diverted_and_failed too (all their product
    # code went to a sibling worktree, none to ws), so stopped_without_product is genuinely true for
    # them as well. Evidence is capped to 5 (design section 6); this checks the full count and the
    # two cells that correctly flip to absent, not only the capped list.
    assert findings["PK-02"].count == 7
    assert set(findings["PK-02"].evidence_cell_ids) == {
        "0164cd01031f303f", "35af195cfe821dca", "3ff04431d3b5ac27", "4a6250261f80ded4", "b765f438fb811ea0",
    }  # sorted, capped to 5 (design section 6); the uncapped 7 also has c6a763578ef7e110, dfb4ae60b8a3d3a3
    for cid in ("757143056c649892", "c4d05c98231eb3aa"):
        assert cid not in findings["PK-02"].evidence_cell_ids  # their product_write now correctly matches
    assert "6.0x the tokens" in result.headline
    assert "2.3x the wall clock" in result.headline
    assert "8 of 11 pack-on failures have a pack-attributed cause" in result.headline
    # Population caveat (grid-1's own cc-opus case, design's own honesty line): both arms land far
    # short of their 18-cell plan (5 and 6 valid), so both are named, never silently averaged over.
    caveats = " | ".join(result.population_caveats)
    assert "cc-opus (off)" in caveats and "5 of 18" in caveats
    assert "cc-opus (on)" in caveats and "6 of 18" in caveats

    # design section 11's own Codex threshold ("token ratio > 5"), recomputed independently here
    # (per-pair, never re-used from the assembled result) as a real cross-check, not a tautology.
    run_dir = gate_runs_root() / "grid-1"
    view = views.load(run_dir)
    plan_by_id = {c["cell_id"]: c for c in (view.plan.get("cells") or [])}
    all_pairs = pi.pairs(view.cells, plan_by_id)
    codex_token_ratios = [
        ratio.value for p in all_pairs if p.on.harness == "codex"
        for ratio in (pi.tokens_ratio(p),) if ratio.value is not None
    ]
    assert codex_token_ratios and max(codex_token_ratios) > 5


@pytest.mark.gate
def test_pi_t15_design_and_headline_agree_on_pass_counts():
    """A weaker, always-checkable form of the "known differences" note (design section 14): the
    headline's own k/n is bounded by the groups' own summed pass counts and pair counts -- the
    section is internally consistent even where its excluded-task population differs from the
    groups table's (which includes every task, design section 7.3 vs section 4.1's one population)."""
    result = _load("grid-1")
    passes_on = sum(g.passes_on for g in result.groups)
    passes_off = sum(g.passes_off for g in result.groups)
    n_pairs = sum(g.n_pairs for g in result.groups)

    m = re.search(r"pass (\d+)/(\d+) vs (\d+)/(\d+)", result.headline)
    assert m is not None
    on, n1, off, n2 = (int(x) for x in m.groups())
    assert n1 == n2
    assert on <= passes_on
    assert off <= passes_off
    assert Decimal(n1) <= Decimal(n_pairs)
