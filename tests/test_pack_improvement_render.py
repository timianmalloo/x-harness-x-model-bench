"""Rendering-level tests for the pack-improvement section (design pack-improvement-section.md
section 11, slice S5): PI-T1 (always last), PI-T2 (one-pack state line) and PI-T14 (no transcript
text leaks into the HTML). The pure-function coverage (S3/S4, plus this hand-off's PK-03/4.6 readers)
lives in `test_pack_improvement.py`; this file is the `html.render()` integration, the pattern
`test_report_builder.py`'s own header comment names for a concern that is new rather than folded into
`test_report.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from archived_runs import GOOD, make_root, make_run

from harness_bench import board, views
from harness_bench.grade import runner
from harness_bench.report import html

FIX = Path(__file__).parent / "fixtures" / "native" / "codex" / "ok.jsonl"
CANARY = "CANARY-PI-T14-3f7a9c2e"


def _last_section_id(doc: str) -> str:
    return re.findall(r'<section id="([a-z0-9-]+)">', doc)[-1]


# ---------------------------------------------------------------------------------------------------
# PI-T1: the rendered report's last <section> has id pack-improvement, with and without a comparison.
# ---------------------------------------------------------------------------------------------------


def test_pi_t1_pack_improvement_is_the_last_section_without_a_comparison(tmp_path):
    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root_dir)
    doc = html.render(views.load(run_dir), archive_present=True)
    assert _last_section_id(doc) == "pack-improvement"


def test_pi_t1_pack_improvement_is_the_last_section_with_a_comparison(tmp_path):
    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root_dir)
    comparison_obj = board.Comparison(
        base_run_id="r0", view_run_id="r1", excluded_tasks=(), unshared_tasks=(), rows=[], same_pack_revision=None,
    )
    doc = html.render(views.load(run_dir), archive_present=True, comparison_obj=comparison_obj)
    ids = re.findall(r'<section id="([a-z0-9-]+)">', doc)
    assert ids[-1] == "pack-improvement"
    assert "comparison" in ids  # the comparison section is present and still not last


# ---------------------------------------------------------------------------------------------------
# PI-T2: a one-pack run renders the "one pack setting" state line.
# ---------------------------------------------------------------------------------------------------


def test_pi_t2_a_one_pack_run_renders_the_one_pack_state_line(tmp_path):
    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD})  # archived_runs.make_run: every cell is pack "off"
    runner.run_pass(run_dir, root_dir)
    doc = html.render(views.load(run_dir), archive_present=True)
    section = re.search(r'<section id="pack-improvement">.*', doc, re.DOTALL).group(0)
    assert "Not applicable: this run has one pack setting." in section
    assert "<table>" not in section  # no group/findings table in this state


# ---------------------------------------------------------------------------------------------------
# PI-T14: a canary planted in fixture transcript text and in a command is absent from the HTML.
# ---------------------------------------------------------------------------------------------------


def test_pi_t14_a_planted_canary_never_reaches_the_rendered_page(tmp_path):
    """The canary sits in the native record's own first assistant text block AND inside a tool call's
    command text -- both of exactly the two fields `report.pack_improvement._cell_indicators` reads
    off a `ProcessTrace` (`trace.first_assistant_text` for `goal_state_present`, `call.command` for
    `classify`/`ceremony_share`/`test_first`). Design section 8: only a derived boolean ever leaves
    the module, so the literal string must never appear in the published page."""
    record_text = FIX.read_text(encoding="utf-8")
    anchor = "run the command and write its stdout bytes"
    assert anchor in record_text and "print(6*7)" in record_text  # pin the fixture shape
    canary_record = record_text.replace(anchor, f"Goal: {CANARY} do the thing. Done when finished.") \
        .replace("print(6*7)", f"print('{CANARY}')")
    assert CANARY in canary_record
    canary_path = tmp_path / "canary.jsonl"
    canary_path.write_text(canary_record, encoding="utf-8")

    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD, "b": GOOD}, harness="codex", native_record=canary_path)
    runner.run_pass(run_dir, root_dir)
    view = views.load(run_dir)
    for c in view.cells:  # archived_runs.make_run plans every cell pack "off"; flip one so a pair forms
        if c.cell_id == "a":
            c.pack = "on"

    doc = html.render(view, archive_present=True, run_dir=run_dir, root=root_dir)
    assert CANARY not in doc


# ---------------------------------------------------------------------------------------------------
# PI-T16: the "Value vs waste" group table's Combo column shows the real combo id (the same text the
# leaderboard, pack-effect and runs sections show, via `_combo_label`), never the c1..c8 CSS-filter
# token `_combo_index` hands out -- that vocabulary drives the legend's `hide-cN` classes
# (html.py:134-142) and is otherwise an internal id, not a display label. No rule in
# docs/design/pack-improvement-section.md or docs/notes/rulings.md requires blinding the combo
# identity in this section.
# ---------------------------------------------------------------------------------------------------


def test_pi_t16_group_table_shows_the_real_combo_name_not_the_cn_token(tmp_path):
    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD, "b": GOOD}, harness="codex",
                        combos={"a": "copilot-sol", "b": "copilot-sol"})
    runner.run_pass(run_dir, root_dir)
    view = views.load(run_dir)
    for c in view.cells:  # make_run plans every cell pack "off"; flip one so a pair forms
        if c.cell_id == "a":
            c.pack = "on"

    doc = html.render(view, archive_present=True, run_dir=run_dir, root=root_dir)
    section = re.search(r'<section id="pack-improvement">.*', doc, re.DOTALL).group(0)
    assert "copilot-sol" in section
    assert re.search(r"<td>c[1-8]</td>", section) is None
