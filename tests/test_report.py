"""The report: CLI table and the static HTML skeleton (design: UI & interaction design; test plan UI rows).

T-CLI-states, T-CLI-plain, T-CLI-exit (the table's part), T-UI-states, T-UI-NA, T-UI-tokens, T-UI-contrast,
T-UI-keyboard, T-UI-numerics, structural accessibility (lang, title, caption, th scope), no network, and
T-SEC-report (a planted token is found and the report is refused).
"""

import re

import pytest
from archived_runs import GOOD, STUB, make_root, make_run

from harness_bench import ledger, views
from harness_bench.errors import BenchError
from harness_bench.grade import runner
from harness_bench.report import cli_table, html


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _graded(root, tmp_path, cells, **kw):
    run_dir = make_run(root, tmp_path, cells, **kw)
    runner.run_pass(run_dir, root)
    return run_dir, views.load(run_dir)


# --- CLI table --------------------------------------------------------------------------------------


def test_an_ungraded_run_says_so_and_exits_4(root, tmp_path):
    view = views.load(make_run(root, tmp_path, {"a": GOOD}))
    assert cli_table.render(view, plain=True) == ("Run r1 is not graded yet. Run bench grade r1.\n", 4)


def test_a_run_where_no_cell_completed_says_so(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"}})
    assert cli_table.render(view, plain=True) == ("No cell completed in run r1. Run bench status r1 to see why.\n", 0)


def test_the_plain_table_is_ascii_with_textual_na_and_invalid_marks(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD, "b": STUB, "c": GOOD}, combos={"a": "good", "b": "stub", "c": "broken"},
                      outcomes={"c": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    out, code = cli_table.render(view, plain=True)
    assert code == 0 and out.isascii()
    assert "NA (1 of 1 valid cells have no cost: no price list entry for gpt-6-sol)" in out
    assert "interval not computed (n < 2)" in out
    assert "X1.broken.pack-off.r1: invalid (infrastructure) HB-CELL-108" in out
    good = next(line for line in out.splitlines() if " good " in line)
    assert "1.00" in good and "46,454 tok" in good and "30.0 s" in good


# --- HTML -------------------------------------------------------------------------------------------


@pytest.fixture
def page(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD, "b": STUB, "c": GOOD}, combos={"a": "good", "b": "stub", "c": "broken"},
                      outcomes={"c": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    return html.render(view, archive_present=True)


def _root_block(doc: str) -> str:
    return re.search(r":root\s*\{([^}]*)\}", doc).group(1)


def test_the_page_is_structurally_accessible(page):
    assert '<html lang="en">' in page and "<title>" in page
    tables = page.count("<table")
    assert tables >= 2 and page.count("<caption") == tables
    assert "<th>" not in page  # every header cell carries a scope
    for region in re.findall(r"<div[^>]*role=\"region\"[^>]*>", page):
        assert 'tabindex="0"' in region
        label = re.search(r'aria-labelledby="([^"]+)"', region).group(1)
        assert f'id="{label}"' in page
    for section in ("header", "validity", "leaderboard", "runs"):
        assert f'id="{section}"' in page


def test_no_colour_size_or_radius_literal_outside_root(page):  # T-UI-tokens
    style = re.search(r"<style>(.*)</style>", page, re.DOTALL).group(1)
    outside = style.replace(_root_block(page), "")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|\b\d+(?:\.\d+)?(?:px|rem|em)\b", outside)


def _luminance(hex_colour: str) -> float:
    rgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_text_and_focus_contrast_meet_wcag_aa(page):  # T-UI-contrast
    tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", _root_block(page)))
    for surface in ("bg", "panel"):
        assert _ratio(tokens["ink"], tokens[surface]) >= 4.5
        assert _ratio(tokens["ink-2"], tokens[surface]) >= 4.5
        assert _ratio(tokens["focus"], tokens[surface]) >= 3.0
    assert "color-scheme: light" in page and ":focus-visible" in page


def test_not_recorded_never_renders_as_zero(page):  # T-UI-NA
    assert "NA (1 of 1 valid cells have no cost: no price list entry for gpt-6-sol)" in page
    assert "$0" not in page and "NA (the native record gives no model-call start time)" in page


def test_numeric_cells_are_tabular_right_aligned_and_carry_units(page):  # T-UI-numerics
    assert re.search(r"\.num\s*\{[^}]*text-align:\s*right[^}]*font-variant-numeric:\s*tabular-nums", page)
    numeric = re.findall(r'<td class="num">([^<]*)</td>', page)
    assert numeric and all(v.startswith("NA (") or re.search(r"(tok|s|ms|\$)", v) or re.fullmatch(r"[\d.]+", v)
                           for v in numeric)


def test_the_validity_banner_counts_each_class_and_lists_them(page):
    banner = re.search(r'<section id="validity".*?</section>', page, re.DOTALL).group(0)
    assert "invalid (infrastructure): 1" in banner and "X1.broken.pack-off.r1" in banner


def test_the_banner_says_so_when_every_cell_is_valid(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD})
    assert "All 1 cells completed and are valid." in html.render(view, archive_present=True)


def test_the_leaderboard_empty_state(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"}})
    assert "No cell completed in this run. Run bench status r1 to see why." in html.render(view, archive_present=True)


def test_evidence_without_the_archive_says_so(root, tmp_path):
    _, view = _graded(root, tmp_path, {"a": GOOD})
    doc = html.render(view, archive_present=False)
    assert "This copy doesn&#x27;t include the run archive. Evidence path: grading/" in doc


def test_the_header_shows_recorded_facts_and_not_recorded_for_the_rest(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "attempt.process_started", "cell_id": "zz", "credential_kind": "subscription login (copied)",
                   "network_mode": "unrestricted", "harness": "codex", "build_version": "0.156.0"})
    doc = html.render(views.load(run_dir), archive_present=True)
    assert "subscription login (copied)" in doc and "codex 0.156.0" in doc
    assert "Defender real-time exclusion" in doc and "not recorded" in doc


def test_the_page_makes_no_network_request_and_has_no_script(page):
    assert not re.search(r"https?://|<script|@import|url\(|<link", page)


def test_a_planted_credential_is_found_and_the_report_refused(root, tmp_path):  # T-SEC-report (positive control)
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    view.cells[0].label = "sk-ant-oat01-PLANTEDabcdefghijklmnopqrstuvwxyz0123456789"
    with pytest.raises(BenchError) as err:
        html.write(run_dir, view)
    assert err.value.code == "HB-SEC-001"
    assert not (run_dir / "report.html").exists()


def test_a_clean_report_is_written(root, tmp_path):  # the negative control
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    path = html.write(run_dir, view)
    assert path == run_dir / "report.html" and path.read_text(encoding="utf-8").startswith("<!doctype html>")
