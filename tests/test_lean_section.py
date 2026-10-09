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
    found = re.search(rf'<span data-part="{name}"[^>]*>(.*?)</span>', row, re.DOTALL)
    assert found is not None, f"no {name} part"
    return _text(found.group(1))


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


# ---------------------------------------------------------------- B2: pooled note, per property, ratio, limits, states

FAMILIES = ("S", "RS", "RW", "NG", "SM")


def _props():
    rows = [lean.PropertyRow(family=f, harness="claude-code", off=(1, 4), on=(3, 4), direction="up") for f in FAMILIES]
    rows.append(lean.PropertyRow(family="S", harness="codex", off=(2, 4), on=(1, 4), direction="down"))
    rows.append(lean.PropertyRow(family="RS", harness="codex", off=(0, 0), on=(0, 0), direction="same"))
    return tuple(rows)


def _block(doc, name):
    found = re.search(rf'<(\w+) data-block="{name}"[^>]*>.*?</\1>', doc, re.DOTALL)
    assert found is not None, f"no {name} block"
    return found.group(0)


def test_the_pooled_row_carries_the_disagreement_note_exactly_when_harnesses_disagree():
    """LB-5: the note text is exactly `harnesses disagree: read the per-harness rows`."""
    note = "harnesses disagree: read the per-harness rows"
    rows = _harness_rows(_render(_pooled_summary(disagree=True)))
    assert _part(rows["pooled"], "note") == note
    assert sum(note in r for r in rows.values()) == 1
    assert note not in _render(_pooled_summary(disagree=False))


def test_the_per_property_table_is_collapsed_exploratory_and_shows_a_over_b_to_c_over_d():
    """LBU-3 and LB-6: collapsed by default, `Exploratory` in its header, `a/b → c/d` with the direction."""
    block = _block(_render(_pooled_summary(properties=_props())), "per-property")
    assert block.startswith("<details") and " open" not in block.split(">", 1)[0]
    summary = _text(re.search(r"<summary>(.*?)</summary>", block, re.DOTALL).group(1))
    assert summary == "Per property (Exploratory: 4 pairs per harness)"
    assert "Exploratory: 4 pairs per harness; not powered for a per-property finding" in _text(block)
    rows = re.findall(r'<tr data-family="([^"]+)" data-harness="([^"]+)">(.*?)</tr>', block, re.DOTALL)
    assert len(rows) == 7
    first = _text(rows[0][2])
    assert first == "S claude-code 1/4 → 3/4 up"
    assert _text(rows[5][2]) == "S codex 2/4 → 1/4 down"
    assert _text(rows[6][2]) == "RS codex 0/0 → 0/0, not recorded not recorded"


def test_the_per_property_text_has_no_verdict_word():
    """LBI-4 / LB-6: 0 matches for better|worse|dominates, case-insensitive."""
    block = _block(_render(_pooled_summary(properties=_props())), "per-property")
    assert re.findall(r"better|worse|dominates", block, re.IGNORECASE) == []


def test_an_empty_per_property_table_says_so():
    block = _block(_render(_pooled_summary(properties=())), "per-property")
    assert "No per-property row recorded." in _text(block)


def test_the_ratio_is_labelled_as_a_ratio_of_totals_with_its_exclusion_count_and_the_median_line():
    """ADR-0023 point 9 and LB-7: the label, one line naming the pack-improvement median, the exclusion count."""
    doc = _render(_pooled_summary())
    heads = [_text(h) for h in re.findall(r'<th scope="col">(.*?)</th>', doc, re.DOTALL)]
    assert heads[-1] == "token ratio of totals (pack-on / pack-off)"
    line = _text(_block(doc, "ratio-note"))
    assert "median" in line and "Pack improvement" in line
    rows = _harness_rows(doc)
    assert _part(rows["codex"], "ratio-excluded") == "2 pairs excluded from the ratio"
    assert _part(rows["claude-code"], "ratio-excluded") == "0 pairs excluded from the ratio"


def test_no_currency_label_anywhere_in_the_section():
    """LB-7 / Ruling 115: 0 `$`, `USD` or `cost_usd` labels."""
    doc = _render(_pooled_summary(properties=_props(), disagree=True))
    assert re.findall(r"\$|USD|cost_usd", doc) == []


def test_the_limits_note_shows_each_checkpoint_value_beside_its_estimate():
    """LB-3: run minutes, grading minutes and tokens per cell, each beside `lean.ESTIMATE`; `not recorded` never 0."""
    over = _checkpoint(RUN_2, run_min=None, tokens=None, infra=(5, 20, ("auth", "rate limit")))
    text = _text(_block(_render(_pooled_summary(checkpoint=(_checkpoint(RUN_1), over))), "limits"))
    assert "repeats of a task are correlated" in text.lower()
    assert f"{RUN_1}: run minutes per cell 1.30 (estimate 1.12, Inferred)" in text
    assert f"{RUN_1}: grading minutes per cell 1.20 (estimate 1.16, Inferred)" in text
    assert f"{RUN_1}: tokens per cell, claude-code-combo arm-b 980,000 (estimate 1,060,000, Inferred)" in text
    assert f"{RUN_2}: run minutes per cell not recorded (estimate 1.12, Inferred)" in text
    assert f"{RUN_2}: tokens per cell, claude-code-combo arm-b not recorded (estimate 1,060,000, Inferred)" in text
    assert f"{RUN_1}: infrastructure failures, claude-code-combo 1 of 20 cells (rate limit)" in text
    assert f"{RUN_2}: infrastructure failures, claude-code-combo 5 of 20 cells (auth, rate limit): over 20%" in text


def test_a_missing_checkpoint_reads_checkpoint_not_recorded():
    assert "Checkpoint not recorded" in _text(_block(_render(_pooled_summary(checkpoint=())), "limits"))


def test_an_empty_summary_renders_its_empty_state_and_the_pooled_row_not_recorded():
    """Part C, empty: no harness row, and a pooled row with 0 pairs reads `not recorded (0 pairs)`."""
    zero = _row("pooled", None, None, None, "not recorded (0 pairs)", mde="0.19", pairs=0, planned=60)
    doc = _render(_pooled_summary(rows=(), pooled=zero, properties=(), checkpoint=()))
    assert "No per-harness row recorded." in _text(doc)
    assert _part(_harness_rows(doc)["pooled"], "statement") == "not recorded (0 pairs)"


def _contrast(a, b):
    def lum(hexv):
        rgb = [int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_bars_and_the_mde_band_are_at_least_3_to_1_against_the_panel_in_both_themes():
    """Part C: every painted part of the section's bars and MDE band reads at 3:1 or more against the panel."""
    style = getattr(_section(), "STYLE", "")
    assert "#lean-summary .bar .mde-band{" in style
    light, dark = html.STYLE.split("@media (prefers-color-scheme: dark){", 1)
    themes = [dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", light))]
    themes.append({**themes[0], **dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", dark.split("}}", 1)[0]))})
    painted = re.findall(r"#lean-summary \.bar [^{]*\{([^}]*)\}", style)
    tokens = {t for body in painted for t in re.findall(r"(?:fill|stroke):var\(--([\w-]+)\)", body)}
    assert tokens, "no painted bar part"
    for theme in themes:
        for token in tokens:
            assert _contrast(theme[token], theme["panel"]) >= 3, token
