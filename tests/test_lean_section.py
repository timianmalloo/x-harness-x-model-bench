"""Tests for the lean summary report section (ADR-0023, spec Part B & Part C)."""

import dataclasses
import importlib
import re
from decimal import Decimal as D
from pathlib import Path

from archived_runs import make_root
from test_report import _arms_view

from harness_bench import lean, stats
from harness_bench.report import html

MODULE = "harness_bench.report.lean_section"
RUN_1, RUN_2 = "lean-batch-1", "lean-batch-2"
HASH_1, HASH_2 = "1a" * 32, "2b" * 32
PREREG = "pre-registered (0123456789ab)"


def test_nonlean_report_golden(tmp_path):
    """LBU-5: a non-lean run renders byte-equal to its golden captured before html.py was touched."""
    root = make_root(tmp_path)
    view = _arms_view(root, tmp_path, {"off": None, "on": {"revision": 95, "commit": "a" * 40}})
    run_dir = tmp_path / "runs" / "r1"
    path = html.write(run_dir, view)
    golden = (Path(__file__).parent / "goldens" / "report-nonlean-arms.html").read_bytes()
    assert path.read_bytes() == golden


# ---------------------------------------------------------------- hand-built LeanSummary fixtures

def _section():
    assert importlib.util.find_spec(MODULE) is not None, f"{MODULE} is absent (L-SUM-B1)"
    return importlib.import_module(MODULE)


def _iv(point, lo, hi, n=10):
    return stats.Interval(D(point), D(lo), D(hi), n, None)


def _row(harness, effect, lo, hi, statement, *, mde="0.31", pairs=20, planned=20, excluded=(), ratio=None,
         ratio_excluded=0):
    return lean.LeanRow(
        combo=f"{harness}-combo", harness=harness, model=f"{harness}-model",
        effect=None if effect is None else D(effect), lo=None if lo is None else D(lo), hi=None if hi is None else D(hi),
        mde=D(mde), pairs=pairs, planned_pairs=planned, excluded=tuple(excluded), statement=statement,
        token_ratio=ratio, ratio_excluded=ratio_excluded)


def _checkpoint(run_id, run_min="1.30", grade_min="1.20", tokens="980000", infra=(1, 20, ("rate limit",))):
    return lean.BatchCheckpoint(
        run_id=run_id, cells=60, run_min_per_cell=None if run_min is None else D(run_min),
        grade_min_per_cell=None if grade_min is None else D(grade_min),
        tokens_per_cell={("claude-code-combo", "arm-b"): None if tokens is None else D(tokens)},
        infra_failures={"claude-code-combo": infra})


def _pooled_summary(**over):
    rows = (
        _row("claude-code", "0.25", "0.05", "0.45", "pack-on higher by 0.25", ratio=_iv("2.1", "1.8", "2.5")),
        _row("codex", "0.05", "-0.15", "0.25", "no detectable effect", ratio=_iv("3.0", "2.4", "3.7"), ratio_excluded=2),
        _row("copilot", "-0.30", "-0.50", "-0.10", "pack-on lower by 0.30", pairs=17,
             excluded=((f"{RUN_1}/cell-07", "auth"), (f"{RUN_2}/cell-11", "rate limit"), (f"{RUN_2}/cell-12", "rate limit")),
             ratio=_iv("1.4", "1.1", "1.9")),
    )
    pooled = _row("pooled", "0.12", "0.01", "0.23", "pack-on higher by 0.12", mde="0.19", pairs=57, planned=60,
                  ratio=_iv("2.0", "1.7", "2.4", 30))
    summary = lean.LeanSummary(batches=2, run_ids=(RUN_1, RUN_2), plan_hashes=(HASH_1, HASH_2), prereg_status=PREREG,
                               rows=rows, pooled=pooled, disagree=False, properties=(),
                               checkpoint=(_checkpoint(RUN_1), _checkpoint(RUN_2)))
    return dataclasses.replace(summary, **over)


def _one_batch_summary():
    rows = (
        _row("claude-code", "0.20", "-0.10", "0.50", "no detectable effect", mde="0.42", pairs=10, planned=10),
        _row("codex", "0.10", "-0.20", "0.40", "no detectable effect", mde="0.42", pairs=10, planned=10),
    )
    pooled = _row("pooled", "0.15", "-0.05", "0.35", "no detectable effect", mde="0.26", pairs=20, planned=20)
    return lean.LeanSummary(batches=1, run_ids=(RUN_1,), plan_hashes=(HASH_1,), prereg_status=PREREG, rows=rows,
                            pooled=pooled, disagree=False, properties=(), checkpoint=(_checkpoint(RUN_1),))


def _render(summary, reported=RUN_2):
    return str(_section().build(summary, reported).body)


def _text(markup):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup)).strip()


def _harness_rows(doc):
    """{harness: row markup} for the per-harness table (the pooled row included)."""
    table = re.search(r'<table data-table="per-harness">.*?</table>', doc, re.DOTALL).group(0)
    return dict(re.findall(r'<tr data-harness="([^"]+)"[^>]*>(.*?)</tr>', table, re.DOTALL))


def _part(row, name):
    return _text(re.search(rf'<span data-part="{name}"[^>]*>(.*?)</span>', row, re.DOTALL).group(1))


# ---------------------------------------------------------------- B1: the header and the per-harness table

def test_header_carries_the_question_prereg_batches_both_run_ids_and_hashes_and_the_scope_line():
    """ADR-0023 point 9: the question, the pre-registration status, `Batches: n of 2`, both run ids and plan hashes, and on
    a pooled summary the scope line."""
    doc = _render(_pooled_summary())
    text = _text(doc)
    assert doc.startswith('<section id="lean-summary">')
    assert "Does the pack help each harness?" in text
    assert PREREG in text
    assert "Batches: 2 of 2" in text
    for value in (RUN_1, RUN_2, HASH_1, HASH_2):
        assert value in text
    assert f"Sections below cover batch {RUN_2} only" in text


def test_one_batch_renders_1_of_2_batches_its_own_mde_and_no_scope_line():
    """LBU-4: one graded batch renders `1 of 2 batches` and the 1-batch MDE (0.42), never the 2-batch MDE."""
    doc = _render(_one_batch_summary(), RUN_1)
    text = _text(doc)
    assert "1 of 2 batches" in text
    assert {_part(r, "mde") for h, r in _harness_rows(doc).items() if h != "pooled"} == {"MDE 0.42"}
    assert "0.31" not in text
    assert "Sections below cover" not in text


def test_the_per_harness_table_is_the_first_table_of_the_section():
    """LBU-1: the per-harness table comes first, straight after the header."""
    doc = _render(_pooled_summary())
    assert re.search(r"<table[^>]*>", doc).group(0) == '<table data-table="per-harness">'
    assert doc.index('data-table="per-harness"') < doc.index("<details")


def test_every_per_harness_row_shows_all_six_fields_never_blank():
    """LBU-2: effect, interval, MDE, pairs, statement and token ratio on every row; a missing one reads
    `not recorded — <reason>`."""
    zero = _row("grok", None, None, None, "not recorded (0 pairs)", pairs=0,
                excluded=((f"{RUN_1}/cell-01", "auth"),))
    summary = _pooled_summary(rows=_pooled_summary().rows + (zero,))
    rows = _harness_rows(_render(summary))
    assert list(rows) == ["claude-code", "codex", "copilot", "grok", "pooled"]
    for harness, row in rows.items():
        for name in ("effect", "interval", "mde", "pairs", "statement", "token-ratio"):
            assert _part(row, name), f"{harness} {name} is blank"
    assert _part(rows["grok"], "effect") == "not recorded — 0 pairs"
    assert _part(rows["grok"], "interval") == "not recorded — 0 pairs"
    assert _part(rows["grok"], "token-ratio").startswith("not recorded — ")


def test_a_row_shows_its_effect_interval_mde_pairs_and_statement_text():
    rows = _harness_rows(_render(_pooled_summary()))
    row = rows["claude-code"]
    assert _part(row, "effect") == "+0.25"
    assert _part(row, "interval") == "[+0.05, +0.45]"
    assert _part(row, "mde") == "MDE 0.31"
    assert _part(row, "pairs") == "20 of 20 pairs recorded"
    assert _part(row, "statement") == "pack-on higher by 0.25"
    assert _part(rows["codex"], "statement") == "no detectable effect"
    assert _part(rows["pooled"], "mde") == "MDE 0.19"


def test_a_partial_row_shows_k_of_20_and_each_excluded_cell_with_its_cause():
    """LB-4: fewer than 20 recorded pairs shows `k of 20 pairs recorded` and the excluded cells with their causes."""
    row = _harness_rows(_render(_pooled_summary()))["copilot"]
    assert _part(row, "pairs") == "17 of 20 pairs recorded"
    text = _text(row)
    for cell, cause in ((f"{RUN_1}/cell-07", "auth"), (f"{RUN_2}/cell-11", "rate limit"), (f"{RUN_2}/cell-12", "rate limit")):
        assert f"{cell} {cause}" in text


def test_a_zero_pair_row_says_not_recorded_and_names_the_causes_never_a_0():
    """LB-4 / Part C empty state: `not recorded (0 pairs)` with the causes, never a 0."""
    zero = _row("grok", None, None, None, "not recorded (0 pairs)", pairs=0, excluded=((f"{RUN_1}/cell-01", "auth"),))
    row = _harness_rows(_render(_pooled_summary(rows=(zero,))))["grok"]
    assert _part(row, "statement") == "not recorded (0 pairs)"
    assert f"{RUN_1}/cell-01 auth" in _text(row)
    assert "+0.00" not in row and "<svg" not in row
