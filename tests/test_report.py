"""The report: CLI table and the static HTML skeleton (design: UI & interaction design; test plan UI rows).

T-CLI-states, T-CLI-plain, T-CLI-exit (the table's part), T-UI-states, T-UI-NA, T-UI-tokens, T-UI-contrast,
T-UI-keyboard, T-UI-numerics, structural accessibility (lang, title, caption, th scope), no network, and
T-SEC-report (a planted token is found and the report is refused).
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import GOOD, STUB, make_root, make_run
from stats_fixtures import stats_run

from harness_bench import board, ledger, stats, views
from harness_bench.errors import BenchError
from harness_bench.grade import cost as grade_cost
from harness_bench.grade import judge as grade_judge
from harness_bench.grade import runner
from harness_bench.report import (
    cli_table,
    context_growth,
    credentials,
    html,
    html_builder,
)


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
    # DR-R-3: dark mode is a second `:root{...}` inside `@media (prefers-color-scheme: dark)`, so
    # every `:root{...}` block (not only the first, light one `_root_block` returns) is stripped
    # before the stray-literal scan.
    style = re.search(r"<style>(.*)</style>", page, re.DOTALL).group(1)
    outside = re.sub(r":root\s*\{[^}]*\}", "", style)
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
    numeric = re.findall(r'<td class="num"[^>]*>([^<]*)</td>', page)
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


def test_no_cells_in_this_run(root, tmp_path):  # T4-6
    _, view = _graded(root, tmp_path, {})
    assert "No cells in this run." in html.render(view, archive_present=True)


def test_the_incomplete_run_banner_counts_cells_that_never_started(root, tmp_path):  # T4-6
    _, view = _graded(root, tmp_path, {"a": GOOD}, unstarted=("b",))
    doc = html.render(view, archive_present=True)
    assert "The run is incomplete. 1 cells never started." in doc


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
    assert "<dt>Defender real-time exclusion</dt><dd>not recorded</dd>" in doc


def test_the_header_marks_the_pinned_copilot_build_as_prerelease(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "attempt.process_started", "cell_id": "a", "harness": "copilot",
                   "build_version": "1.0.89-1"})
    view = views.load(run_dir)
    view.plan["builds"] = {"copilot": {"version": "1.0.89-1"}}
    doc = html.render(view, archive_present=True)
    assert "<dt>Planned builds</dt><dd>copilot 1.0.89-1 (prerelease)</dd>" in doc
    assert "<dt>Executed builds</dt><dd>copilot 1.0.89-1 (prerelease)</dd>" in doc


def test_the_header_names_the_pinned_pack_revision_and_commit(root, tmp_path):
    view = views.load(make_run(root, tmp_path, {"a": GOOD}))
    view.plan["pack"] = {"revision": 95, "commit": "a" * 40}
    doc = html.render(view, archive_present=True)
    assert "<dt>Pack revision</dt><dd>95</dd>" in doc
    assert f"<dt>Pack commit</dt><dd>{'a' * 40}</dd>" in doc


# --- R-32: the context-window tag is disclosed, in the header and per cell -------------------------------
# `render` reads the tag straight from the run's `attempt.process_ended` events (via `run_dir`), never
# from views.py (ruling R-32 condition 3: views.py carries no wave-1 owner and is not touched).


def test_the_header_and_drill_down_disclose_a_tagged_cells_context_window(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model="claude-opus-5-5",
                        combos={"a": "cc-opus"}, context_window_tag={"a": "1m"})
    doc = html.render(views.load(run_dir), archive_present=True, run_dir=run_dir)
    header = re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0)
    assert "<dt>Context window</dt><dd>Claude Code cells ran with the 1M context window</dd>" in header
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    row = next(r for r in re.findall(r"<tr[^>]*>.*?</tr>", runs, re.DOTALL) if "cc-opus" in r)
    assert "<td>Claude Code cells ran with the 1M context window</td>" in row


def test_the_header_and_drill_down_read_not_recorded_without_a_tag(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"b": GOOD}, harness="codex", combos={"b": "codex-sol"})  # no context_window_tag
    doc = html.render(views.load(run_dir), archive_present=True, run_dir=run_dir)
    header = re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0)
    assert "<dt>Context window</dt><dd>not recorded</dd>" in header
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    row = next(r for r in re.findall(r"<tr[^>]*>.*?</tr>", runs, re.DOTALL) if "codex-sol" in r)
    assert "<td>not recorded</td>" in row


def test_render_without_a_run_dir_reads_not_recorded(root, tmp_path):  # render() stays usable with no ledger access
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model="claude-opus-5-5",
                        context_window_tag={"a": "1m"})
    doc = html.render(views.load(run_dir), archive_present=True)  # no run_dir passed
    header = re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0)
    assert "<dt>Context window</dt><dd>not recorded</dd>" in header


# --- R-34: the effective permission mode of Claude Code cells is in the header ------------------------------
# Read from `attempt.session_opened.permission_mode_effective` (what the session reported), not the profile's
# declared `defaultMode` (dontAsk falls back to default in the ACP session).

PERMISSION_ROW = "<dt>Claude Code permission mode (effective)</dt>"


def _with_modes(run_dir, modes: dict):
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        for cid, mode in modes.items():
            ev.append({"kind": "attempt.session_opened", "cell_id": cid, "session_id": f"sess-{cid}",
                       "permission_mode_effective": mode})
    return run_dir


def _header_of(run_dir):
    doc = html.render(views.load(run_dir), archive_present=True, run_dir=run_dir)
    return re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0)


def test_the_header_shows_the_effective_permission_mode_of_claude_code_cells(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model="claude-opus-5-5", combos={"a": "cc-opus"})
    assert f"{PERMISSION_ROW}<dd>default</dd>" in _header_of(_with_modes(run_dir, {"a": "default"}))


def test_the_header_reads_not_recorded_for_a_claude_code_cell_without_the_mode(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model="claude-opus-5-5")  # pre-R-34 events
    assert f"{PERMISSION_ROW}<dd>not recorded</dd>" in _header_of(run_dir)


def test_the_header_has_no_claude_code_permission_row_without_a_claude_code_cell(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"b": GOOD}, harness="codex", combos={"b": "codex-sol"})
    assert PERMISSION_ROW not in _header_of(_with_modes(run_dir, {"b": "agent-full-access"}))


def test_the_page_makes_no_network_request_and_has_one_inline_script(page):
    """R4: the page now ships exactly one script -- the hashed, inline `report.js` -- and it carries no
    `src` (so loading it is never a network request); every other network-shaped reference stays absent."""
    assert not re.search(r"https?://|@import|url\(|<link", page)
    scripts = re.findall(r"<script[^>]*>", page)
    assert len(scripts) == 1 and "src=" not in scripts[0]


def test_csp_script_hash_pins_the_shipped_report_js(page):
    """R4: the CSP's `script-src` is the sha256 of exactly `report.js`'s own bytes on disk (design
    section 5) -- a mutant that hashes something else, or a stale copy of the file that no longer
    matches what ships, fails this red (the browser ring's UIA-15/UIA-1 tests would then fail too,
    but this one is offline and catches it on every push)."""
    script_text = html.SCRIPT_PATH.read_text(encoding="utf-8")
    assert html_builder.sha256_token(script_text) in page
    assert "script-src &#x27;none&#x27;" not in page  # R1's placeholder is retired now that a script ships


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


# --- exact-value credential scan (HB-SEC-001; T4-1) --------------------------------------------------

FAKE_ROTATED_TOKEN = "ROTATED/9f8e+7d6c=5b4a3210planted"  # a planted fake; never a real credential


def _plant_archived_credential(run_dir, cell_id: str, name: str, value: str) -> None:
    home = run_dir / "archive" / cell_id / "attempt-1" / "home"
    home.mkdir(parents=True, exist_ok=True)
    (home / name).write_text(json.dumps({"accessToken": value}), encoding="utf-8")


def test_the_exact_value_scan_collects_a_leftover_token_from_an_archived_home(root, tmp_path):
    run_dir, _ = _graded(root, tmp_path, {"a": GOOD})
    _plant_archived_credential(run_dir, "a", ".credentials.json", FAKE_ROTATED_TOKEN)
    names = {name for _, name in credentials.credential_files(root).values()}
    assert ".credentials.json" in names  # sanity: the real profile names this file
    assert FAKE_ROTATED_TOKEN in credentials.archived_home_values(run_dir, names)


def test_a_rotated_token_found_only_in_an_archived_home_is_refused(root, tmp_path):  # T4-1 (HB-SEC-001)
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    _plant_archived_credential(run_dir, "a", ".credentials.json", FAKE_ROTATED_TOKEN)
    names = {name for _, name in credentials.credential_files(root).values()}
    values = credentials.archived_home_values(run_dir, names)
    view.cells[0].label = FAKE_ROTATED_TOKEN  # the value leaked into a rendered field
    with pytest.raises(BenchError) as err:
        html.write(run_dir, view, values)
    assert err.value.code == "HB-SEC-001"
    assert FAKE_ROTATED_TOKEN not in str(err.value)  # a hit never names the value, only a count
    assert not (run_dir / "report.html").exists()


def test_the_rotated_tokens_base64_and_url_encoded_forms_are_also_refused(root, tmp_path):
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    _plant_archived_credential(run_dir, "a", ".credentials.json", FAKE_ROTATED_TOKEN)
    names = {name for _, name in credentials.credential_files(root).values()}
    values = credentials.archived_home_values(run_dir, names)
    encoded = credentials.encodings(values) - values
    assert len(encoded) == 2  # base64 and URL-encoded forms of the one planted value
    for form in encoded:
        view.cells[0].label = form
        with pytest.raises(BenchError) as err:
            html.write(run_dir, view, values)
        assert err.value.code == "HB-SEC-001"


def test_a_value_found_only_on_the_host_side_is_refused(root, tmp_path, monkeypatch, tmp_path_factory):
    fake_home = tmp_path_factory.mktemp("fake-home")
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))
    (fake_home / ".claude").mkdir()
    (fake_home / ".claude" / ".credentials.json").write_text(json.dumps({"accessToken": FAKE_ROTATED_TOKEN}), encoding="utf-8")
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    values = credentials.host_values(root)
    assert FAKE_ROTATED_TOKEN in values
    view.cells[0].label = FAKE_ROTATED_TOKEN
    with pytest.raises(BenchError) as err:
        html.write(run_dir, view, values)
    assert err.value.code == "HB-SEC-001"


def test_a_leaked_oauth_token_env_value_is_refused(root, tmp_path, monkeypatch):  # ADR-0003 Am. 2026-09-30
    """HB_CLAUDE_OAUTH_TOKEN (profiles.OAUTH_TOKEN_ENV) replaces the copied credential file for claude-code
    cells; its value must be in the same scan set as a credential file's, so a leak of it is HB-SEC-001 too."""
    from harness_bench import profiles
    monkeypatch.setenv(profiles.OAUTH_TOKEN_ENV, FAKE_ROTATED_TOKEN)
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    values = credentials.host_values(root)
    assert FAKE_ROTATED_TOKEN in values
    view.cells[0].label = FAKE_ROTATED_TOKEN
    with pytest.raises(BenchError) as err:
        html.write(run_dir, view, values)
    assert err.value.code == "HB-SEC-001"


def test_a_clean_report_still_writes_when_credential_values_are_supplied(root, tmp_path):
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    path = html.write(run_dir, view, {FAKE_ROTATED_TOKEN})
    assert path == run_dir / "report.html"


# --- N5: user-config exposed flag (ruling R-5, Coordinator seam request) -----------------------------

N5_FLAG = "user-config exposed (N5)"


def _cell(cid, combo, harness, model):
    na = views.Measure(None, "not graded")
    return views.CellView(cell_id=cid, label=f"X1.{combo}.pack-off.r1", combo=combo, pack="off", harness=harness, model=model,
                          outcome="completed", cause=None, code=None, validity="valid", validity_code=None,
                          wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na, tokens=None, tokens_reason="not graded")


def _mixed_view():
    codex_cell = _cell("a", "codex-sol", "codex", "gpt-6-sol")
    cc_cell = _cell("b", "cc-sonnet", "claude-code", "claude-sonnet-5")
    plan = {"cells": [{"harness": "codex"}, {"harness": "claude-code"}]}
    return views.RunView("r1", plan, True, "grade-1", None, [codex_cell, cc_cell])


def _codex_only_view():
    v = _mixed_view()
    v.cells = [v.cells[0]]
    v.plan = {"cells": [{"harness": "codex"}]}
    return v


def _no_codex_view():
    v = _mixed_view()
    v.cells = [v.cells[1]]
    v.plan = {"cells": [{"harness": "claude-code"}]}
    return v


def test_the_header_flags_a_run_with_a_codex_cell_and_names_the_evidence():
    doc = html.render(_codex_only_view(), archive_present=True)
    assert N5_FLAG in doc
    assert "spike-n5-codex-skill-roots.md" in doc and "US-13" in doc


def test_the_header_has_no_flag_when_the_run_has_no_codex_cell():
    doc = html.render(_no_codex_view(), archive_present=True)
    assert "N5" not in doc


def test_the_leaderboard_and_cells_table_flag_only_the_codex_rows():
    doc = html.render(_mixed_view(), archive_present=True)
    board = re.search(r'<section id="leaderboard".*?</section>', doc, re.DOTALL).group(0)
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    for section in (board, runs):
        rows = re.findall(r"<tr[^>]*>.*?</tr>", section, re.DOTALL)
        codex_row = next(r for r in rows if "codex-sol" in r)
        cc_row = next(r for r in rows if "cc-sonnet" in r)
        assert N5_FLAG in codex_row
        assert N5_FLAG not in cc_row


def test_the_cli_table_prints_the_flag_as_ascii_after_the_table_when_a_codex_cell_is_present():
    out, code = cli_table.render(_codex_only_view(), plain=True)
    # The line itself, not the phrase: a codex model label carries the flag too (TEST-A).
    assert code == 0 and out.isascii() and any(ln.startswith(f"{N5_FLAG}: see ") for ln in out.splitlines())


def test_the_cli_table_has_no_flag_when_no_codex_cell():
    out, code = cli_table.render(_no_codex_view(), plain=True)
    assert code == 0 and "N5" not in out


# --- R-36(a): account context (R1.4) flag on every Claude Code cell (ruling R-36, spike R1.4) ---------

R36_FLAG = "account context (R1.4)"


def test_the_header_flags_a_run_with_a_claude_code_cell_and_names_the_evidence():
    doc = html.render(_no_codex_view(), archive_present=True)  # claude-code only
    assert R36_FLAG in doc
    assert "spike-isolation-permissions.md" in doc


def test_the_header_has_no_account_context_flag_when_the_run_has_no_claude_code_cell():
    doc = html.render(_codex_only_view(), archive_present=True)
    assert R36_FLAG not in doc


def test_the_leaderboard_and_cells_table_flag_only_the_claude_code_rows():
    doc = html.render(_mixed_view(), archive_present=True)
    board = re.search(r'<section id="leaderboard".*?</section>', doc, re.DOTALL).group(0)
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    for section in (board, runs):
        rows = re.findall(r"<tr[^>]*>.*?</tr>", section, re.DOTALL)
        codex_row = next(r for r in rows if "codex-sol" in r)
        cc_row = next(r for r in rows if "cc-sonnet" in r)
        assert R36_FLAG in cc_row
        assert R36_FLAG not in codex_row


def test_the_cli_table_prints_the_account_context_flag_when_a_claude_code_cell_is_present():
    out, code = cli_table.render(_no_codex_view(), plain=True)
    assert code == 0 and out.isascii() and R36_FLAG in out


def test_the_cli_table_has_no_account_context_flag_when_no_claude_code_cell():
    out, code = cli_table.render(_codex_only_view(), plain=True)
    assert code == 0 and R36_FLAG not in out


# --- wave-2 validity states and view warnings (R-15, R-27, R-24/R-26 c5, R-47) on every surface ---------------------

TOKENS_WARNING = views.Finding("HB-VAL-005", "warning", "model_calls tokens differ from the ACP turn total: outputTokens ACP 516, model_calls 515")
BUILD_FLAG = views.Finding("HB-VAL-006", "warning", "executed-build check skipped: no recorded agent_version for copilot")


def _state_view(validity, code, warnings=()):
    cell = _cell("a", "cop-sol", "copilot", "gpt-6-sol")
    cell.validity, cell.validity_code, cell.warnings = validity, code, list(warnings)
    return views.RunView("r1", {"cells": [{"harness": "copilot"}]}, True, "grade-1", None, [cell])


def _lines_after(out: str, heading: str) -> list[str]:
    lines = out.splitlines()
    return lines[lines.index(heading) + 1:]


@pytest.mark.parametrize(("validity", "code"), [("not recorded", "HB-VAL-003"), ("invalid (tools denied by hook)", "HB-VAL-004"),
                                           ("invalid (build mismatch)", "HB-VAL-007")])
def test_the_cli_table_lists_each_wave_two_state_under_the_cells_that_are_not_valid(validity, code):
    out, _ = cli_table.render(_state_view(validity, code), plain=True)
    assert _lines_after(out, "Cells that are not valid:")[0] == f"  X1.cop-sol.pack-off.r1: {validity} {code}"


@pytest.mark.parametrize(("validity", "code"), [("not recorded", "HB-VAL-003"), ("invalid (tools denied by hook)", "HB-VAL-004"),
                                           ("invalid (build mismatch)", "HB-VAL-007")])
def test_the_html_validity_section_counts_and_lists_each_wave_two_state(validity, code):
    banner = re.search(r'<section id="validity".*?</section>', html.render(_state_view(validity, code), archive_present=True),
                       re.DOTALL).group(0)
    assert f"<li>{validity}: 1</li>" in banner and f"<li>X1.cop-sol.pack-off.r1: {validity} {code}</li>" in banner


def _cells_column(doc: str, header: str) -> list[str]:
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    headers = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', runs)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody[^>]*>(.*?)</tbody>", runs, re.DOTALL).group(1))
    return [re.findall(r"<td[^>]*>(.*?)</td>", row)[headers.index(header)] for row in rows]


def test_bench_report_shows_the_codex_q1_cell_as_out_of_profile_on_every_surface(root, tmp_path):  # R-57 gate 3
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    record = next((run_dir / "archive/a/attempt-1/home").rglob("*.jsonl"))
    record.write_bytes((Path(__file__).parent / "fixtures/native/codex/mcp-inside-exec.jsonl").read_bytes())  # R-55
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    out, _ = cli_table.render(view, plain=True)
    assert _lines_after(out, "Cells that are not valid:")[0] == "  X1.c.pack-off.r1: invalid (out-of-profile tool called) HB-VAL-008"
    doc = html.render(view, archive_present=True)
    banner = re.search(r'<section id="validity".*?</section>', doc, re.DOTALL).group(0)
    assert "<li>X1.c.pack-off.r1: invalid (out-of-profile tool called) HB-VAL-008</li>" in banner
    assert _cells_column(doc, "Validity") == ["invalid (out-of-profile tool called) HB-VAL-008"]


def test_the_cli_table_and_the_page_list_the_refused_attempt_warning():  # R-54 (b): a valid cell, disclosed
    refused = views.Finding("HB-VAL-009", "warning", "out-of-profile attempt refused: WebFetch")
    view = _state_view("valid", None, [refused])
    out, _ = cli_table.render(view, plain=True)
    assert _lines_after(out, "Warnings:")[0] == "  X1.cop-sol.pack-off.r1: HB-VAL-009 out-of-profile attempt refused: WebFetch"
    doc = html.render(view, archive_present=True)
    assert re.search(r'<ul id="validity-warnings">(.*?)</ul>', doc, re.DOTALL).group(1) == (
        "<li>X1.cop-sol.pack-off.r1: HB-VAL-009 out-of-profile attempt refused: WebFetch</li>")
    assert _cells_column(doc, "Warnings") == ["HB-VAL-009"]


def test_the_cli_table_lists_each_warning_with_its_code_after_the_table():
    out, _ = cli_table.render(_state_view("valid", None, [TOKENS_WARNING, BUILD_FLAG]), plain=True)
    assert _lines_after(out, "Warnings:")[:2] == [f"  X1.cop-sol.pack-off.r1: HB-VAL-005 {TOKENS_WARNING.message}",
                                                  f"  X1.cop-sol.pack-off.r1: HB-VAL-006 {BUILD_FLAG.message}"]


def test_the_cli_table_has_no_warnings_heading_without_a_warning():
    out, _ = cli_table.render(_state_view("valid", None), plain=True)
    assert "Warnings:" not in out.splitlines()


def test_the_html_validity_section_lists_warnings_even_when_every_cell_is_valid():
    doc = html.render(_state_view("valid", None, [BUILD_FLAG]), archive_present=True)
    warnings = re.search(r'<ul id="validity-warnings">(.*?)</ul>', doc, re.DOTALL).group(1)
    assert warnings == f"<li>X1.cop-sol.pack-off.r1: HB-VAL-006 {BUILD_FLAG.message}</li>"


def test_the_html_cells_table_names_each_cells_warning_codes():
    doc = html.render(_state_view("valid", None, [TOKENS_WARNING, BUILD_FLAG]), archive_present=True)
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    headers = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', runs)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", re.search(r"<tbody[^>]*>(.*?)</tbody>", runs, re.DOTALL).group(1))
    assert cells[headers.index("Warnings")] == "HB-VAL-005, HB-VAL-006"


def test_the_html_cells_table_reads_none_for_a_cell_without_warnings():
    doc = html.render(_state_view("valid", None), archive_present=True)
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    headers = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', runs)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", re.search(r"<tbody[^>]*>(.*?)</tbody>", runs, re.DOTALL).group(1))
    assert cells[headers.index("Warnings")] == "none" and '<ul id="validity-warnings">' not in doc


# --- R3 (design section 15, 6 row 3/10, 7, 10): leaderboard interval bars, the evidence popover, and the
# Runs cell card, built on `html_builder.el` (UIA-15) ----------------------------------------------------

INJECTED_WARNING = views.Finding("HB-VAL-009", "warning",
                                 '<script>alert(1)</script><img src=x onerror="alert(1)">')


def test_injection_fixture_renders_inert():
    """UIA-15: the injection fixture's `<script>` and `onerror` reach the report only inside the cell
    card (design section 10's STRIDE row), as inert text -- never a real `<script>` element (the CSP's
    `script-src` stays `'none'` until R4 anyway, but escaping is the first-line control, section 5)."""
    view = _state_view("valid", None, [INJECTED_WARNING])
    doc = html.render(view, archive_present=True)
    # R4: the page now carries exactly one real <script> element -- the hashed report.js -- and its
    # content is our own vendored source, never the injection fixture's text (which stays inert below).
    assert doc.count("<script>") == 1
    script_body = re.search(r"<script>(.*?)</script>", doc, re.DOTALL).group(1)
    assert "alert(1)" not in script_body and "onerror" not in script_body
    cell_id = view.cells[0].cell_id
    match = re.search(rf'<tr id="cell-{re.escape(cell_id)}"[^>]*>.*?</tr>', doc, re.DOTALL)
    assert match is not None, "no row carries id=\"cell-<id>\" (design section 15 R3)"
    row = match.group(0)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in row
    assert "onerror" in row and "<img" not in row


def test_every_interval_element_has_bounds_or_reason(root, tmp_path):
    """UIA-5, with the design section 12 cardinality floor: the count of interval-or-reason elements in
    the DOM equals the count the leaderboard's own rows demand (two per row: pass@1 and gated), and that
    count is never zero -- so an absent element can never satisfy this test."""
    _, view = _graded(root, tmp_path, {"a": GOOD, "b": GOOD}, combos={"a": "c1", "b": "c2"})
    doc = html.render(view, archive_present=True)
    section = re.search(r'<section id="leaderboard".*?</section>', doc, re.DOTALL).group(0)
    row_count = len(re.findall(r"<tr[^>]*>.*?</tr>",
                               re.search(r"<tbody[^>]*>(.*?)</tbody>", section, re.DOTALL).group(1), re.DOTALL))
    marks = re.findall(
        r'<svg[^>]*class="[^"]*\bivmark\b[^"]*"[^>]*>.*?</svg>|<span[^>]*class="[^"]*\bivmark\b[^"]*"[^>]*>[^<]*</span>',
        section, re.DOTALL)
    assert row_count > 0
    assert len(marks) == 2 * row_count  # the cardinality floor: never satisfied by zero elements
    for mark in marks:
        if mark.startswith("<svg"):
            assert 'data-interval-lo="' in mark and 'data-interval-hi="' in mark
        else:
            text = re.search(r">([^<]*)</span>", mark)
            assert text is not None and text.group(1).strip() != "", mark  # the reason, never blank


def test_archive_absent_copy(root, tmp_path):
    """US-41, TEST-A-safe: the exact section 9 copy is scoped to the cell's own row (its evidence column
    and its cell card), not a whole-page substring another part of the page could also satisfy."""
    _, view = _graded(root, tmp_path, {"a": GOOD})
    doc = html.render(view, archive_present=False)
    cell_id = view.cells[0].cell_id
    match = re.search(rf'<tr id="cell-{re.escape(cell_id)}"[^>]*>.*?</tr>', doc, re.DOTALL)
    assert match is not None, "no row carries id=\"cell-<id>\" (design section 15 R3)"
    row = match.group(0)
    assert "This copy doesn&#x27;t include the run archive. Evidence path: grading/" in row


def test_the_canonical_export_carries_a_build_mismatch():  # R-47 c2
    cell = json.loads(views.export(_state_view("invalid (build mismatch)", "HB-VAL-007")))["cells"][0]
    assert (cell["validity"], cell["validity_code"]) == ("invalid (build mismatch)", "HB-VAL-007")


def _header_fact(doc: str, name: str) -> str:
    return re.search(rf"<dt>{re.escape(name)}</dt><dd>(.*?)</dd>", doc).group(1)


def test_the_header_names_the_skipped_executed_build_check():  # R-47 c3: HB-VAL-006 is the disclosed state
    doc = html.render(_state_view("valid", None, [BUILD_FLAG]), archive_present=True)
    assert _header_fact(doc, "Executed-build check") == "skipped for 1 of 1 cells (HB-VAL-006): no recorded agent_version"


def test_the_header_says_the_executed_build_check_ran_when_no_cell_skipped_it():
    doc = html.render(_state_view("valid", None), archive_present=True)
    assert _header_fact(doc, "Executed-build check") == "checked against the recorded agent_version (HB-VAL-007 on a mismatch)"


def test_the_canonical_export_carries_each_cells_warnings():
    cell = json.loads(views.export(_state_view("valid", None, [BUILD_FLAG])))["cells"][0]
    assert cell["warnings"] == [{"code": "HB-VAL-006", "level": "warning", "message": BUILD_FLAG.message}]


def test_no_connector_name_is_hard_coded_in_the_report_source():  # R-36 condition 3, R-6 condition 4
    from pathlib import Path

    import harness_bench.report as report_module

    sources = sorted(Path(report_module.__file__).parent.glob("*.py"))
    assert {p.name for p in sources} >= {"__init__.py", "html.py", "cli_table.py"}
    for path in sources:
        src = path.read_text(encoding="utf-8")
        assert "mcp__claude_ai" not in src and "Claude_Docs" not in src, path.name


# --- S6 report wiring (T-U1..U3) -------------------------------------------------------------------


def test_tu1_cli_prints_columns_and_header_row(root, tmp_path):
    """T-U1 (red first for S6): the CLI prints the columns and the header row.

    Shows the board's rows (rank with ties, pass@1 or gated with its interval,
    the primary-measure line, seed, resamples and METHOD in the header,
    the pack effect with `no detectable effect` where the interval touches zero,
    and the E1-E3 exclusion statement or `none in this run`).
    """
    import yaml
    m_path = root / "bench" / "metrics.yaml"
    cat_data = yaml.safe_load(m_path.read_text(encoding="utf-8"))
    cat_data["version"] = "0.4"
    for area in cat_data.get("areas", {}).values():
        for m in area.get("metrics", []):
            m.pop("anchor", None)
            m.pop("anchor_note", None)
    m_path.write_text(yaml.dump(cat_data), encoding="utf-8")

    outcomes = {
        ("A1", 1, "off"): 1,
        ("A1", 2, "off"): 1,
        ("A1", 1, "on"): 1,
        ("A1", 2, "on"): 1,
        ("B1", 1, "off"): 1,
        ("B1", 2, "off"): 1,
        ("B1", 1, "on"): 1,
        ("B1", 2, "on"): 1,
    }
    run_dir = stats_run(
        root, tmp_path, run_id="r-tu1", tasks=("A1", "B1"), reps=2, arms=("off", "on"), combos=["c1"], outcomes=outcomes
    )
    view = views.load(run_dir)
    out, code = cli_table.render(view, plain=True, run_dir=run_dir, root=root)
    assert code == 0

    # Header rows: primary measure and statistics with METHOD, seed, resamples
    assert "primary measure: pass@1 (catalog 0.4 has no normalisation anchors)" in out
    assert "statistics: percentile bootstrap, 95%, two-stage (task, then repetition), task-balanced mean" in out
    assert "2000 resamples" in out
    assert "seed 20260927" in out

    # CLI leaderboard columns: pass@1 95%, Gated, Gated 95%, NO Interval column
    assert "pass@1 95%" in out
    assert "Gated" in out
    assert "Gated 95%" in out
    header_line = next(line for line in out.splitlines() if "Rank" in line and "Combo" in line)
    assert "Interval" not in header_line.split()

    # Pack effect section and exclusion statement
    assert "Excluded as contamination-prone: none in this run" in out
    assert "no detectable effect" in out


def test_tu2_html_intervals_carry_data_attributes(root, tmp_path):
    """T-U2: HTML intervals carry data-interval-lo/-hi, absent when not computed."""
    # Run with 2 tasks: computed intervals
    run_dir = stats_run(root, tmp_path, run_id="r-tu2-comp", tasks=("A1", "B1"), reps=2, arms=("off", "on"), combos=["c1"])
    view = views.load(run_dir)
    doc = html.render(view, archive_present=True, run_dir=run_dir, root=root)
    assert 'data-interval-lo="' in doc
    assert 'data-interval-hi="' in doc

    # Run with 1 task: interval not computed (n < 2)
    run_dir_1 = stats_run(root, tmp_path, run_id="r-tu2-nocomp", tasks=("A1",), reps=2, arms=("off", "on"), combos=["c1"])
    view_1 = views.load(run_dir_1)
    doc_1 = html.render(view_1, archive_present=True, run_dir=run_dir_1, root=root)
    lb_1 = re.search(r'<section id="leaderboard".*?</section>', doc_1, re.DOTALL).group(0)
    assert "interval not computed (n &lt; 2)" in lb_1
    assert "data-interval-lo" not in lb_1
    assert "data-interval-hi" not in lb_1


def test_tu3_cli_resamples_and_seed(root, tmp_path, capsys):
    """T-U3: combo flags stay green, --resamples < 2000 exits invalid input, and seed/resamples are recorded."""
    run_dir = stats_run(root, tmp_path, run_id="r-tu3", tasks=("A1", "B1"), reps=2, arms=("off", "on"), combos=["c1"])
    from harness_bench import cli

    # 1. --resamples < 2000 exits invalid input (exit 1) with HB-STA-003
    exit_code = cli.main(["--root", str(root), "--runs", str(tmp_path / "runs"), "report", "r-tu3", "--resamples", "1999"])
    assert exit_code == cli.INVALID
    captured = capsys.readouterr()
    assert "HB-STA-003" in captured.err

    # 2. --resamples 2500 and --seed 12345 reach report and are recorded
    view = views.load(run_dir)
    params = stats.Params(seed=12345, resamples=2500)
    out, code = cli_table.render(view, plain=True, run_dir=run_dir, root=root, params=params)
    assert code == 0
    assert "2500 resamples" in out
    assert "seed 12345" in out

    doc = html.render(view, archive_present=True, run_dir=run_dir, root=root, params=params)
    assert "2500 resamples" in doc
    assert "seed 12345" in doc


# --- S7 run comparison (T-M1..M3) ------------------------------------------------------------------


def test_tm1_comparison_refusal_end_to_end_cli_and_html(root, tmp_path, capsys):
    """T-M1 (red first for S7): the refusal naming each difference, end to end through the CLI exit code.

    The HTML section reads `Runs not comparable: <each difference>`.
    """
    from harness_bench import cli

    # Run A has combo c1, Run B has combo c2
    stats_run(root, tmp_path, run_id="r-tm1-a", tasks=("A1",), reps=1, arms=("off",), combos=["c1"])
    run_b = stats_run(root, tmp_path, run_id="r-tm1-b", tasks=("A1",), reps=1, arms=("off",), combos=["c2"])

    # 1. CLI end-to-end: bench report r-tm1-b --baseline r-tm1-a
    exit_code = cli.main([
        "--root", str(root),
        "--runs", str(tmp_path / "runs"),
        "report", "r-tm1-b",
        "--baseline", "r-tm1-a",
    ])
    assert exit_code == cli.INVALID
    captured = capsys.readouterr()
    assert "HB-STA-002" in captured.err
    assert "combos differ: only in A: c1; only in B: c2" in captured.err

    # 2. HTML section: reads `Runs not comparable: <each difference>`
    view_b = views.load(run_b)
    doc = html.render(
        view_b,
        archive_present=True,
        run_dir=run_b,
        root=root,
        comparison_obj="combos differ: only in A: c1; only in B: c2",
    )
    assert '<section id="comparison">' in doc
    assert "Runs not comparable: combos differ: only in A: c1; only in B: c2" in doc


def test_tm2_shared_pack_revision_labelled_a_replication(root, tmp_path, capsys):
    """T-M2: a shared pack revision is allowed and labelled `a replication` in CLI and HTML."""
    from harness_bench import cli

    outcomes_a = {
        ("A1", 1, "off"): 1,
        ("B1", 1, "off"): 1,
    }
    outcomes_b = {
        ("A1", 1, "off"): 1,
        ("B1", 1, "off"): 0,
    }
    stats_run(
        root, tmp_path, run_id="r-tm2-a", tasks=("A1", "B1"), reps=1, arms=("off",), combos=["c1"],
        outcomes=outcomes_a, pack_revision="95",
    )
    stats_run(
        root, tmp_path, run_id="r-tm2-b", tasks=("A1", "B1"), reps=1, arms=("off",), combos=["c1"],
        outcomes=outcomes_b, pack_revision="95",
    )

    exit_code = cli.main([
        "--root", str(root),
        "--runs", str(tmp_path / "runs"),
        "report", "r-tm2-b",
        "--baseline", "r-tm2-a",
    ])
    assert exit_code == cli.OK
    captured = capsys.readouterr()
    assert "same pack revision (95): a replication" in captured.out
    assert "Excluded as contamination-prone: none in this run" in captured.out
    assert "Comparison:" in captured.out

    html_file = tmp_path / "runs" / "r-tm2-b" / "report.html"
    assert html_file.is_file()
    doc = html_file.read_text(encoding="utf-8")
    assert '<section id="comparison">' in doc
    assert "same pack revision (95): a replication" in doc
    assert "Excluded as contamination-prone: none in this run" in doc
    assert "data-interval-lo=" in doc


# --- R2 (design phase4-report.md s15, US-43, US-51) ---------------------------------------------------


def test_about_defines_six_terms(root, tmp_path):
    """R2 (design phase4-report.md s15, US-51, s6 row 1a, s9): About this run names pack revision and defines six terms."""
    _, view = _graded(root, tmp_path, {"a": GOOD})
    view.plan["pack"] = {"revision": 95, "commit": "a" * 40}
    doc = html.render(view, archive_present=True)
    assert "<summary>About this run</summary>" in doc
    assert "This run tests the pack <strong>ai-forward revision 95</strong>." in doc
    assert "<dt>combo</dt><dd>A combo is one harness, at one build, driving one model.</dd>" in doc
    assert "<dt>pack on / pack off</dt><dd>Pack on runs the task with the AI-Forward Pack installed in the workspace; pack off runs the same task without it.</dd>" in doc
    assert "<dt>correctness-gated composite</dt><dd>The correctness-gated composite is the mean of the area scores (0-100) a cell recorded, set to 0 when its hidden tests fail.</dd>" in doc
    assert "<dt>pass@1 / pass^k</dt><dd>pass@1 is the share of cells whose hidden tests pass; pass^k is the share of tasks passed in all k repetitions.</dd>" in doc
    assert "<dt>interval</dt><dd>An interval is the 95% bootstrap range of a value over tasks and repetitions; overlapping intervals mean the data cannot tell the values apart.</dd>" in doc
    assert "<dt>not recorded</dt><dd>Not recorded means the value could not be measured, and it is never counted as 0.</dd>" in doc


def make_many_classes_run(root: Path, tmp_path: Path) -> tuple[Path, views.RunView]:
    """Fixture run with 6 exclusion classes each from a real producer (design section 12 row many-classes):
    NA costs (the empty price list, on every cell here), invalid (c1), timed out (c3), stopped (c4), withheld
    (c5, a genuine HB-GW-009 score reason, ruling R-80 c1) and disagreeing judges (c6, grade_judge.DISAGREE
    verbatim). "not applicable" and "low-confidence matchers" have no producer anywhere in this codebase (R2),
    so no fixture can drive them active; c7 stays a plain valid cell.
    """
    cells = {f"c{i}": GOOD for i in range(1, 8)}
    combos = {f"c{i}": f"combo{i}" for i in range(1, 8)}
    outcomes = {
        "c1": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"},
        "c3": {"outcome": "timed_out", "cause": "timed_out", "code": "HB-CELL-301"},
        "c4": {"outcome": "stopped"},
        "c5": {"outcome": "failed", "cause": "unclassified"},
    }
    run_dir = make_run(root, tmp_path, cells, combos=combos, outcomes=outcomes)
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    # c5's judge call was withheld (gateway/pipeline.py:168, grade/judge.py's item_score:186-200); c6's judges
    # disagreed (judge.py:47 DISAGREE, verbatim -- the one constant, never a hand-typed copy of its text).
    c5 = next(c for c in view.cells if c.cell_id == "c5")
    c5.scores["adr_quality"] = views.Measure(None, "judge gpt-5: failed HB-GW-009")  # gateway/pipeline.py:168
    c6 = next(c for c in view.cells if c.cell_id == "c6")
    c6.scores["adr_quality"] = views.Measure(None, grade_judge.DISAGREE)
    return run_dir, view


def test_validity_banner_counts_each_exclusion_class(root, tmp_path):
    """R2 (design phase4-report.md s15, US-43, US-43 no source, s6 row 2):
    validity banner counts each exclusion class, links to runs, handles unrecorded source,
    one-line all-valid form, and the first 5 plus and <k> more form on many-classes.
    """
    # 1. All-valid form
    _, view_valid = _graded(root, tmp_path / "valid", {"a": GOOD})
    doc_valid = html.render(view_valid, archive_present=True)
    assert "All 1 cells completed and are valid." in doc_valid

    # 2. Incomplete run form: the 2 never-started cells also count in the exclusion-class summary
    # (outcome "not started", views.py:507) -- not only the separate incomplete-run sentence above.
    run_dir_inc = make_run(root, tmp_path / "inc", {"a": GOOD}, unstarted=("b", "c"))
    view_inc = views.load(run_dir_inc)
    view_inc.completed = False
    doc_inc = html.render(view_inc, archive_present=True)
    assert "The run is incomplete. 2 cells never started." in doc_inc
    assert "2 stopped / skipped / never started" in doc_inc

    # 3. Class with no source reads not recorded (never 0)
    run_dir_partial = make_run(root, tmp_path / "partial", {"a": GOOD, "b": GOOD},
                               outcomes={"b": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    runner.run_pass(run_dir_partial, root)
    view_partial = views.load(run_dir_partial)
    doc_partial = html.render(view_partial, archive_present=True)
    banner_partial = re.search(r'<section id="validity".*?</section>', doc_partial, re.DOTALL).group(0)
    assert "low-confidence matchers: not recorded" in banner_partial
    assert "0 low-confidence matchers" not in banner_partial
    # no cell was judged in this run: disagreeing judges is unmeasured too, never a bare 0 (the fixed bug)
    assert "disagreeing judges: not recorded" in banner_partial
    assert "0 disagreeing judges" not in banner_partial

    # 4. many-classes fixture run with 6 exclusion classes driving the "and <k> more" form
    _, view_many = make_many_classes_run(root, tmp_path / "many")
    doc_many = html.render(view_many, archive_present=True)
    banner_many = re.search(r'<section id="validity".*?</section>', doc_many, re.DOTALL).group(0)
    assert "and 1 more" in banner_many
    assert '<a href="#runs">' in banner_many
    assert "1 withheld" in banner_many  # c5's genuine HB-GW-009 score, not the old cause/code guess


def test_invalid_count_never_conflates_a_failed_outcome_with_an_invalid_cell(root, tmp_path):
    """R2 fix (design s6 row 2): the bug added `outcome == "failed"` to the invalid count, so an agent- or
    harness-attributed failure -- never scored against a harness are only infrastructure/benchmark causes,
    Cause.invalidates, errors.py:34-38 -- was wrongly counted as invalid even though its own validity stays
    "valid"."""
    _, view = _graded(root, tmp_path, {"a": GOOD, "b": GOOD, "c": GOOD},
                      outcomes={"b": {"outcome": "failed", "cause": "blocked_permission", "code": "HB-CELL-201"},
                                "c": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    b = next(x for x in view.cells if x.cell_id == "b")
    assert b.outcome == "failed" and b.validity == "valid"  # ground: a failed outcome that stays valid exists
    banner = re.search(r'<section id="validity".*?</section>', html.render(view, archive_present=True), re.DOTALL).group(0)
    assert "1 invalid" in banner  # only c (infrastructure); b's failed-but-valid outcome is never counted


def test_judge_spend_says_so_when_no_judging_ran(root, tmp_path):
    """R2 fix: the header's Spend line names judges with judges.py's own NO_CALL wording ("no call in this
    pass") when judging never ran (judges.facts returns [] with no run_dir, judges.py:253), never the old
    invented "0 calls"."""
    _, view = _graded(root, tmp_path, {"a": GOOD})
    doc = html.render(view, archive_present=True)  # no run_dir: judges.facts finds no pass
    spend = re.search(r"<dt>Spend</dt><dd>([^<]*)</dd>", doc).group(1)
    assert "judges no call in this pass" in spend
    assert "judges 0 calls" not in spend


def test_header_wall_clock_is_run_level_not_a_cell_sum(root, tmp_path):
    """R2 fix (design s6 row 1): cells run in parallel, so summing their wall_ms is not the run's wall clock.
    The header now reads run.started/run.completed's own mono_ns (engine.py:382,:425; both stamped,
    ledger.py:70), and keeps the old per-cell sum under its own honest label."""
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD}, run_completed_mono_ns=5_000_000_000)
    view = views.load(run_dir)
    doc = html.render(view, archive_present=True, run_dir=run_dir)
    wall = re.search(r"<dt>Wall clock</dt><dd>([^<]*)</dd>", doc).group(1)
    cell_time = re.search(r"<dt>Cell time \(sum\)</dt><dd>([^<]*)</dd>", doc).group(1)
    assert wall == "5.0 s"  # (5_000_000_000 - 0) ns, the run's own span
    assert cell_time == "60.0 s"  # 2 cells x this fixture's 30s each (mono_ns 1e9..31e9 per cell)
    assert wall != cell_time


def test_header_wall_clock_not_recorded_with_no_run_completed_event(root, tmp_path):
    """A run with no run.completed event (still running, or a ledger from before it was stamped) reads not
    recorded -- never a plausible number (IO)."""
    _, view = _graded(root, tmp_path, {"a": GOOD})
    doc = html.render(view, archive_present=True)  # no run_dir passed: the same "no source" path
    assert re.search(r"<dt>Wall clock</dt><dd>not recorded</dd>", doc)







def test_the_header_names_the_bom_the_plan_froze(root, tmp_path):
    """R2 join: the plan records the BOM as bom_version plus matrix.bom.subset; the header read a `bom` key no plan has
    and printed `not recorded` for a recorded value."""
    _, view = _graded(root, tmp_path, {"a": GOOD})
    view.plan["bom_version"] = "0.3"
    view.plan["matrix"] = {"bom": {"file": "bench/bom.yaml", "subset": ["X1", "A1"]}}
    summary = re.search(r'<section id="header">.*?<p class="muted">(.*?)</p>', html.render(view, archive_present=True), re.DOTALL)
    assert "BOM 0.3 (X1, A1) · " in summary.group(1)


# --- R5 (design phase4-report.md s15, s6 rows 4 and 11, s3, s12 UIA-5, UIA-6, UIA-13) -----------------


def test_crossing_zero_uses_neutral_mark_and_label():
    """R5 (design s15, s6 row 4): a delta whose interval crosses 0 draws the --ink-2 mark and
    the exact label 'no detectable effect (interval crosses 0)'; a positive delta takes --div-pos
    and a negative delta takes --div-neg."""
    view = _state_view("valid", None)
    pe_rows = [
        board.PackEffectRow(
            combo="c1",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.05"), lo=Decimal("-0.10"), hi=Decimal("0.20"), n=6, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo="c2",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.25"), lo=Decimal("0.10"), hi=Decimal("0.40"), n=6, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo="c3",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("-0.25"), lo=Decimal("-0.40"), hi=Decimal("-0.10"), n=6, reason=None),
            label=None,
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=pe_rows),
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj)
    pe_match = re.search(r'<section id="pack-effect".*?</section>', doc, re.DOTALL)
    assert pe_match is not None
    pe_section = pe_match.group(0)

    # 1. The SVG chart must be present and contain inline marks
    assert "<svg" in pe_section

    # 2. Check the neutral mark and label for the crossing-zero row (c1)
    # Class .nde references --ink-2 in STYLE
    assert 'class="nde"' in pe_section or 'class="nde whisk"' in pe_section
    assert "no detectable effect (interval crosses 0)" in pe_section

    # 3. Check that positive delta takes --div-pos (.pos) and negative takes --div-neg (.neg)
    assert re.search(r'<circle[^>]*class="pos"[^>]*data-interval-point="0\.25"', pe_section)
    assert re.search(r'<circle[^>]*class="neg"[^>]*data-interval-point="-0\.25"', pe_section)

    # 4. Token mapping in STYLE: .nde uses var(--ink-2), .pos uses var(--div-pos), .neg uses var(--div-neg)
    assert re.search(r"\.nde\s*\{[^}]*var\(--ink-2\)", html.STYLE)
    assert re.search(r"\.pos\s*\{[^}]*var\(--div-pos\)", html.STYLE)
    assert re.search(r"\.neg\s*\{[^}]*var\(--div-neg\)", html.STYLE)


def test_chart_equals_table_uia13():
    """UIA-13 (design s12, s15): each chart's data-attributes equal its table's cells
    (values, intervals)."""
    view = _state_view("valid", None)
    pe_rows = [
        board.PackEffectRow(
            combo="c1",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.15"), lo=Decimal("0.05"), hi=Decimal("0.25"), n=6, reason=None),
            label="pack improves pass@1",
        ),
        board.PackEffectRow(
            combo="c2",
            measure="gated",
            delta=stats.Interval(point=Decimal("-12.5"), lo=Decimal("-25.0"), hi=Decimal("-2.0"), n=6, reason=None),
            label="pack degrades gated",
        ),
        board.PackEffectRow(
            combo="c3",
            measure="pass_at_1",
            delta=stats.Interval(point=None, lo=None, hi=None, n=0, reason="not computed (no area score in pack=off)"),
            label=None,
        ),
    ]
    comp_rows = [
        board.ComparisonRow(
            combo="c1",
            pack="on",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.10"), lo=Decimal("0.02"), hi=Decimal("0.18"), n=6, reason=None),
            label=None,
        ),
        board.ComparisonRow(
            combo="c2",
            pack="off",
            measure="gated",
            delta=stats.Interval(point=Decimal("5.0"), lo=Decimal("-3.0"), hi=Decimal("12.0"), n=6, reason=None),
            label=None,
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=pe_rows),
    )
    comp_obj = board.Comparison(
        base_run_id="r0",
        view_run_id="r1",
        excluded_tasks=(),
        unshared_tasks=(),
        rows=comp_rows,
        same_pack_revision=None,
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj, comparison_obj=comp_obj)

    # 1. Pack effect chart vs table
    pe_match = re.search(r'<section id="pack-effect".*?</section>', doc, re.DOTALL)
    assert pe_match is not None
    pe_sec = pe_match.group(0)

    # Chart marks in pack-effect
    chart_marks = re.findall(
        r'<circle[^>]*data-interval-lo="([^"]+)"[^>]*data-interval-hi="([^"]+)"[^>]*data-interval-point="([^"]+)"',
        pe_sec,
    )
    # Table rows in pack-effect with intervals
    table_rows = re.findall(
        r'<td[^>]*data-interval-point="([^"]+)"[^>]*data-interval-lo="([^"]+)"[^>]*data-interval-hi="([^"]+)"',
        pe_sec,
    )
    assert len(chart_marks) == 2  # c1 and c2 (c3 is not computed, so no chart mark)
    assert len(table_rows) == 2
    for (c_lo, c_hi, c_pt), (t_pt, t_lo, t_hi) in zip(chart_marks, table_rows):
        assert c_lo == t_lo
        assert c_hi == t_hi
        assert c_pt == t_pt

    # Check uncomputed row in table has the reason text and class na
    assert "not computed (no area score in pack=off)" in pe_sec

    # 2. Comparison chart vs table
    comp_match = re.search(r'<section id="comparison".*?</section>', doc, re.DOTALL)
    assert comp_match is not None
    comp_sec = comp_match.group(0)

    comp_chart_marks = re.findall(
        r'<circle[^>]*data-interval-lo="([^"]+)"[^>]*data-interval-hi="([^"]+)"[^>]*data-interval-point="([^"]+)"',
        comp_sec,
    )
    comp_table_rows = re.findall(
        r'<td[^>]*data-interval-point="([^"]+)"[^>]*data-interval-lo="([^"]+)"[^>]*data-interval-hi="([^"]+)"',
        comp_sec,
    )
    assert len(comp_chart_marks) == 2
    assert len(comp_table_rows) == 2
    for (c_lo, c_hi, c_pt), (t_pt, t_lo, t_hi) in zip(comp_chart_marks, comp_table_rows):
        assert c_lo == t_lo
        assert c_hi == t_hi
        assert c_pt == t_pt


def test_uia6_palette_source_scan():
    """UIA-6 (design s12, s3): heatmap tokens equal the published ten viridis stops,
    the diverging tokens are the PuOr ends of section 3, and no jet, rainbow or red-green pair
    appears in report/ source."""
    # 1. Viridis 10 stops
    expected_viridis = [
        "#440154", "#482878", "#3e4989", "#31688e", "#26828e",
        "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725",
    ]
    heat_tokens = [re.search(rf"--heat-{i}:\s*(#[0-9a-fA-F]{{6}})", html.STYLE) for i in range(10)]
    assert all(h is not None for h in heat_tokens), "all 10 heat tokens must be defined"
    actual_viridis = [h.group(1).lower() for h in heat_tokens]
    assert actual_viridis == [c.lower() for c in expected_viridis]

    # 2. Diverging tokens (PuOr ends of section 3)
    # Light mode
    light_pos = re.search(r"--div-pos:\s*(#[0-9a-fA-F]{6})", html.STYLE).group(1).lower()
    light_neg = re.search(r"--div-neg:\s*(#[0-9a-fA-F]{6})", html.STYLE).group(1).lower()
    assert light_pos == "#5e3c99"
    assert light_neg == "#b35806"
    # Dark mode
    dark_pos = re.search(r"@media \(prefers-color-scheme: dark\).*?--div-pos:\s*(#[0-9a-fA-F]{6})", html.STYLE, re.DOTALL).group(1).lower()
    dark_neg = re.search(r"@media \(prefers-color-scheme: dark\).*?--div-neg:\s*(#[0-9a-fA-F]{6})", html.STYLE, re.DOTALL).group(1).lower()
    assert dark_pos == "#b2abd2"
    assert dark_neg == "#fdb863"

    # 3. Source scan: no jet, rainbow, or red-green pairs in report/ source
    import harness_bench.report as report_pkg
    report_dir = Path(report_pkg.__file__).parent
    for py_file in sorted(report_dir.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        assert not re.search(r"\bjet\b", text, re.IGNORECASE), f"forbidden 'jet' in {py_file.name}"
        assert not re.search(r"\brainbow\b", text, re.IGNORECASE), f"forbidden 'rainbow' in {py_file.name}"
        assert not re.search(r"\bred[-_ ]green\b|\bgreen[-_ ]red\b", text, re.IGNORECASE), f"forbidden red-green pair in {py_file.name}"


def test_pack_effect_units_get_separate_panels():
    """R5 join fix (design s6 row 4): pass@1 deltas are shares (-1..1) and area deltas are 0-100
    points. When a pack effect has both a pass_at_1 row and an area row, each unit draws on its
    own panel with its own shared zero line -- the pass@1 whisker must not collapse to the area
    panel's 0-100 scale."""
    view = _state_view("valid", None)
    pe_rows = [
        board.PackEffectRow(
            combo="c1",
            measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.05"), lo=Decimal("-0.10"), hi=Decimal("0.20"), n=6, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo="c1",
            measure="correctness",
            delta=stats.Interval(point=Decimal("20.0"), lo=Decimal("-40.0"), hi=Decimal("60.0"), n=6, reason=None),
            label=None,
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=pe_rows),
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj)
    pe_match = re.search(r'<section id="pack-effect".*?</section>', doc, re.DOTALL)
    assert pe_match is not None
    pe_section = pe_match.group(0)

    whisk = re.search(
        r'<line[^>]*class="[^"]*\bwhisk\b[^"]*"[^>]*x1="([-0-9.]+)"[^>]*x2="([-0-9.]+)"[^>]*'
        r'data-interval-lo="-0\.10"[^>]*data-interval-hi="0\.20"',
        pe_section,
    )
    if whisk is None:
        whisk = re.search(
            r'<line[^>]*x1="([-0-9.]+)"[^>]*x2="([-0-9.]+)"[^>]*class="[^"]*\bwhisk\b[^"]*"[^>]*'
            r'data-interval-lo="-0\.10"[^>]*data-interval-hi="0\.20"',
            pe_section,
        )
    assert whisk is not None, "pass@1 whisker mark not found"
    x1, x2 = float(whisk.group(1)), float(whisk.group(2))
    assert abs(x2 - x1) > 10, (
        f"pass@1 whisker x-extent {abs(x2 - x1)} is not a visible fraction of its panel's width "
        "-- it collapsed onto the area panel's 0-100 scale"
    )


def _legend_board_row(combo: str) -> board.BoardRow:
    """A leaderboard row whose only job is to put `combo` on the legend. `_combo_index` reads
    `board.rows` in first-appearance order; the pack-effect rows alone never mint a cN token."""
    na_iv = stats.Interval(point=None, lo=None, hi=None, n=0, reason="not recorded")
    na = stats.Measure(None, "not recorded")
    return board.BoardRow(
        combo=combo, pack="on", harness="copilot", model="gpt-6-sol",
        n_cells=2, n_valid=2, pass_at_1=na_iv, gated=na_iv,
        pass_at_k=na, pass_hat_k=na, rank="1", rank_reason=None,
        tokens=na, wall_ms=na, cost_usd=na, cost_of_pass=na,
    )


def _attr(attrs: str, name: str) -> str | None:
    found = re.search(rf'\b{name}="([^"]*)"', attrs)
    return found.group(1) if found else None


def _mark_groups(section: str) -> list[dict[str, str]]:
    """Each whisker mark group in document order: the row label, its whisker line, its dot.

    Axis and tick `<text>`/`<line>` elements are not marks of a combo (design section 6: hiding a
    combo hides its rows and marks, not the shared zero)."""
    pattern = re.compile(
        r'<text\b([^>]*)>([^<]*)</text>|<line\b([^/>]*)/>|<circle\b([^/>]*)/>'
    )
    groups: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for match in pattern.finditer(section):
        if match.group(1) is not None:
            attrs, body = match.group(1), match.group(2)
            if _attr(attrs, "x") != "4":
                continue
            assert current is None, f"row label {body!r} started before the previous mark closed"
            current = {"label_attrs": attrs, "label": body}
        elif match.group(3) is not None:
            attrs = match.group(3)
            if "whisk" not in (_attr(attrs, "class") or ""):
                continue
            assert current is not None and "line_attrs" not in current
            current["line_attrs"] = attrs
        else:
            attrs = match.group(4) or ""
            assert current is not None and "line_attrs" in current and "dot_attrs" not in current
            current["dot_attrs"] = attrs
            groups.append(current)
            current = None
    assert current is None, "a mark group closed without its dot"
    return groups


def test_pack_effect_marks_and_rows_carry_the_legend_combo_token():
    """Design section 6: unless a section says otherwise, it follows the combo legend.

    Pack effect is the on-minus-off difference, so the pack switch does not hide it (the disabled
    reason lives in report.js). Every whisker mark (the line, its dot and its row label) and every
    delta-table row carries that combo's `_combo_index` token and never `data-pack`. Comparison rows are one
    pack arm, so the same mark group and each table row carry `data-combo` and `data-pack`.
    Combo names are not the tokens: stamping `data-combo` with the combo's own name cannot pass.
    """
    alpha, beta = "alpha", "beta"
    view = _state_view("valid", None)
    pe_rows = [
        board.PackEffectRow(
            combo=alpha, measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.20"), lo=Decimal("0.05"), hi=Decimal("0.35"), n=4, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo=beta, measure="pass_at_1",
            delta=stats.Interval(point=Decimal("-0.10"), lo=Decimal("-0.30"), hi=Decimal("-0.02"), n=4, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo=alpha, measure="correctness",
            delta=stats.Interval(point=Decimal("8.0"), lo=Decimal("1.0"), hi=Decimal("15.0"), n=4, reason=None),
            label=None,
        ),
        board.PackEffectRow(
            combo=beta, measure="gated",
            delta=stats.Interval(point=None, lo=None, hi=None, n=0, reason="not computed (no area score in pack=off)"),
            label=None,
        ),
    ]
    comp_rows = [
        board.ComparisonRow(
            combo=alpha, pack="on", measure="pass_at_1",
            delta=stats.Interval(point=Decimal("0.10"), lo=Decimal("0.02"), hi=Decimal("0.18"), n=4, reason=None),
            label=None,
        ),
        board.ComparisonRow(
            combo=beta, pack="off", measure="gated",
            delta=stats.Interval(point=Decimal("-4.0"), lo=Decimal("-9.0"), hi=Decimal("-1.0"), n=4, reason=None),
            label=None,
        ),
    ]
    board_obj = board.Board(
        run_id="r1", catalog_version="0.5", params=stats.Params(),
        primary="gated", primary_reason=None,
        rows=[_legend_board_row(alpha), _legend_board_row(beta)],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=pe_rows),
    )
    comparison = board.Comparison(
        base_run_id="r0", view_run_id="r1", excluded_tasks=(), unshared_tasks=(),
        rows=comp_rows, same_pack_revision=None,
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj, comparison_obj=comparison)
    combo_ix = html._combo_index(board_obj)
    assert combo_ix == {alpha: "c1", beta: "c2"}
    legend = re.search(r'id="legend"(.*?)</div>', doc, re.DOTALL)
    assert legend is not None
    for combo, token in combo_ix.items():
        assert re.search(rf'data-combo="{token}"[^>]*>{combo}</button>', legend.group(1)), (
            f"legend button for {combo} is not {token}"
        )

    pe = re.search(r'<section id="pack-effect".*?</section>', doc, re.DOTALL)
    assert pe is not None
    pe_sec = pe.group(0)
    groups = _mark_groups(pe_sec)
    assert len(groups) == 3, "two pass@1 marks and one area mark; the uncomputed row has no mark"
    for group in groups:
        combo = group["label"].split(" ", 1)[0]
        token = combo_ix[combo]
        for part in ("label_attrs", "line_attrs", "dot_attrs"):
            got = _attr(group[part], "data-combo")
            assert got == token, (
                f"pack-effect {part} for {combo!r} ({group['label']!r}) has data-combo {got!r}, "
                f"legend token is {token!r}"
            )
            assert _attr(group[part], "data-pack") is None, (
                f"pack-effect {part} for {combo!r} carries data-pack; a pack effect is both settings"
            )
    assert "data-pack=" not in pe_sec

    tbody = re.search(r"<tbody>(.*?)</tbody>", pe_sec, re.DOTALL)
    assert tbody is not None
    body_rows = re.findall(r"<tr\b([^>]*)>(.*?)</tr>", tbody.group(1), re.DOTALL)
    assert len(body_rows) == 4  # the uncomputed beta row is still a table row
    for attrs, inner in body_rows:
        combo = re.search(r"<td>([^<]*)</td>", inner).group(1)
        got = _attr(attrs, "data-combo")
        assert got == combo_ix[combo], (
            f"pack-effect table row for {combo!r} has data-combo {got!r}, legend token is {combo_ix[combo]!r}"
        )
        assert _attr(attrs, "data-pack") is None

    comp = re.search(r'<section id="comparison".*?</section>', doc, re.DOTALL)
    assert comp is not None
    comp_sec = comp.group(0)
    comp_groups = _mark_groups(comp_sec)
    assert len(comp_groups) == 2
    for group in comp_groups:
        combo, pack = group["label"].split(" ", 2)[:2]
        token = combo_ix[combo]
        for part in ("label_attrs", "line_attrs", "dot_attrs"):
            got = _attr(group[part], "data-combo")
            assert got == token, (
                f"comparison {part} for {combo!r} has data-combo {got!r}, legend token is {token!r}"
            )
            assert _attr(group[part], "data-pack") == pack, (
                f"comparison {part} for {combo!r} has data-pack {_attr(group[part], 'data-pack')!r}, "
                f"row pack is {pack!r}"
            )
    comp_body = re.search(r"<tbody>(.*?)</tbody>", comp_sec, re.DOTALL)
    assert comp_body is not None
    comp_rows_html = re.findall(r"<tr\b([^>]*)>(.*?)</tr>", comp_body.group(1), re.DOTALL)
    assert len(comp_rows_html) == 2
    for attrs, inner in comp_rows_html:
        cells = re.findall(r"<td[^>]*>([^<]*)</td>", inner)
        combo, pack = cells[0], cells[1]
        assert _attr(attrs, "data-combo") == combo_ix[combo]
        assert _attr(attrs, "data-pack") == pack


def test_chart_equals_table():
    """UIA-13 (design s12, s15): each chart's marks carry data-combo (and data-pack where mark
    is per pack) with the legend token and data-interval-* or data-value attributes equal to its table's cells,
    tested for both Cost frontier and Areas."""
    view = _state_view("valid", None)
    frontier_rows = [
        board.FrontierRow(
            combo="c1",
            pack="on",
            pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
            cost_per_task=stats.Measure(Decimal("1.25"), reason=None),
            tokens_per_solved=stats.Measure(Decimal(50000), reason=None),
            wall_per_task=stats.Measure(Decimal(120000), reason=None),
        ),
        board.FrontierRow(
            combo="c1",
            pack="off",
            pass_at_1=stats.Interval(point=Decimal("0.60"), lo=Decimal("0.20"), hi=Decimal("0.90"), n=6, reason=None),
            cost_per_task=stats.Measure(Decimal("0.75"), reason=None),
            tokens_per_solved=stats.Measure(Decimal(30000), reason=None),
            wall_per_task=stats.Measure(Decimal(80000), reason=None),
        ),
    ]
    areas_rows = [
        board.AreaRow(
            combo="c1",
            pack="on",
            area="correctness",
            interval=stats.Interval(point=Decimal("85.0"), lo=Decimal("70.0"), hi=Decimal("95.0"), n=6, reason=None),
        ),
        board.AreaRow(
            combo="c1",
            pack="off",
            area="correctness",
            interval=stats.Interval(point=Decimal("75.0"), lo=Decimal("60.0"), hi=Decimal("90.0"), n=6, reason=None),
        ),
        board.AreaRow(
            combo="c1",
            pack="on",
            area="rigor",
            interval=stats.Interval(point=Decimal("65.0"), lo=Decimal("50.0"), hi=Decimal("80.0"), n=6, reason=None),
        ),
        board.AreaRow(
            combo="c1",
            pack="off",
            area="rigor",
            interval=stats.Interval(point=Decimal("55.0"), lo=Decimal("40.0"), hi=Decimal("70.0"), n=6, reason=None),
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[
            board.BoardRow(
                combo="c1",
                harness="h",
                model="m",
                pack="on",
                rank="1",
                rank_reason=None,
                n_valid=6,
                n_cells=6,
                gated=stats.Interval(point=Decimal("80.0"), lo=Decimal("60.0"), hi=Decimal("95.0"), n=6, reason=None),
                pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
                pass_at_k=stats.Measure(Decimal("0.80")),
                pass_hat_k=stats.Measure(Decimal("0.80")),
                tokens=stats.Measure(Decimal(50000)),
                wall_ms=stats.Measure(Decimal(120000)),
                cost_usd=stats.Measure(Decimal("1.25")),
                cost_of_pass=stats.Measure(Decimal("1.56")),
            ),
            board.BoardRow(
                combo="c1",
                harness="h",
                model="m",
                pack="off",
                rank="2",
                rank_reason=None,
                n_valid=6,
                n_cells=6,
                gated=stats.Interval(point=Decimal("70.0"), lo=Decimal("50.0"), hi=Decimal("85.0"), n=6, reason=None),
                pass_at_1=stats.Interval(point=Decimal("0.60"), lo=Decimal("0.20"), hi=Decimal("0.90"), n=6, reason=None),
                pass_at_k=stats.Measure(Decimal("0.60")),
                pass_hat_k=stats.Measure(Decimal("0.60")),
                tokens=stats.Measure(Decimal(30000)),
                wall_ms=stats.Measure(Decimal(80000)),
                cost_usd=stats.Measure(Decimal("0.75")),
                cost_of_pass=stats.Measure(Decimal("1.25")),
            ),
        ],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
        frontier=frontier_rows,
        areas=areas_rows,
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj)

    # 1. Cost frontier chart vs table
    cf_match = re.search(r'<section id="cost-frontier".*?</section>', doc, re.DOTALL)
    assert cf_match is not None, "cost-frontier section not found"
    cf_sec = cf_match.group(0)

    # Check chart marks and whisker lines have data-combo and data-pack
    cf_whiskers = re.findall(
        r'<line[^>]*class="[^"]*\bwhisk\b[^"]*"[^>]*data-combo="([^"]+)"[^>]*data-pack="([^"]+)"[^>]*data-interval-lo="([^"]+)"[^>]*data-interval-hi="([^"]+)"',
        cf_sec,
    )
    assert len(cf_whiskers) >= 2, "whisker marks with data-combo and data-pack must be present in cost-frontier"
    cf_table_rows = re.findall(
        r'<tr[^>]*data-combo="([^"]+)"[^>]*data-pack="([^"]+)"',
        cf_sec,
    )
    assert len(cf_table_rows) >= 2, "cost-frontier table rows must carry data-combo and data-pack"

    # 2. Areas radar chart vs table
    ar_match = re.search(r'<section id="areas".*?</section>', doc, re.DOTALL)
    assert ar_match is not None, "areas section not found"
    ar_sec = ar_match.group(0)

    ar_marks = re.findall(
        r'<circle[^>]*data-combo="([^"]+)"[^>]*data-pack="([^"]+)"[^>]*data-area="([^"]+)"[^>]*data-value="([^"]+)"',
        ar_sec,
    )
    assert len(ar_marks) >= 4, "area marks must carry data-combo, data-pack, data-area and data-value"
    ar_table_cells = re.findall(
        r'<td[^>]*data-area="([^"]+)"[^>]*data-value="([^"]+)"',
        ar_sec,
    )
    assert len(ar_table_cells) >= 4, "area table cells must carry data-area and data-value"
    for _, _, m_a, m_val in ar_marks:
        assert (m_a, m_val) in ar_table_cells


def test_empty_run_draws_no_axes(root, tmp_path):
    """UXA-8 (design s12, s15): an empty run renders the header, banner and the empty copy,
    and no svg with axes in either cost-frontier or areas section."""
    _, view = _graded(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"}})
    doc = html.render(view, archive_present=True)

    # 1. Header and banner rendered
    assert '<section id="header">' in doc
    assert '<section id="validity">' in doc

    # 2. cost-frontier section rendered with empty copy and no svg with axes
    cf_match = re.search(r'<section id="cost-frontier".*?</section>', doc, re.DOTALL)
    assert cf_match is not None, "cost-frontier section must be present"
    cf_sec = cf_match.group(0)
    assert "No completed cells to plot." in cf_sec
    assert "<svg" not in cf_sec

    # 3. areas section rendered with empty copy and no svg with axes
    ar_match = re.search(r'<section id="areas".*?</section>', doc, re.DOTALL)
    assert ar_match is not None, "areas section must be present"
    ar_sec = ar_match.group(0)
    assert "No completed cells to plot." in ar_sec
    assert "<svg" not in ar_sec


def test_cost_frontier_all_cost_na_renders_sentence_and_no_axes():
    """Design s6 row 5: all cost NA (smoke-1): the cost panel shows 'Cost not recorded for any combo:
    no price list entry for <models>.' with no axes; the other two panels still draw."""
    view = _state_view("valid", None)
    frontier_rows = [
        board.FrontierRow(
            combo="c1",
            pack="on",
            pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
            cost_per_task=stats.Measure(None, reason="no price list entry for gpt-6-sol"),
            tokens_per_solved=stats.Measure(Decimal(50000), reason=None),
            wall_per_task=stats.Measure(Decimal(120000), reason=None),
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[
            board.BoardRow(
                combo="c1",
                harness="h",
                model="m",
                pack="on",
                rank="1",
                rank_reason=None,
                n_valid=6,
                n_cells=6,
                gated=stats.Interval(point=Decimal("80.0"), lo=Decimal("60.0"), hi=Decimal("95.0"), n=6, reason=None),
                pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
                pass_at_k=stats.Measure(Decimal("0.80")),
                pass_hat_k=stats.Measure(Decimal("0.80")),
                tokens=stats.Measure(Decimal(50000)),
                wall_ms=stats.Measure(Decimal(120000)),
                cost_usd=stats.Measure(None, reason="no price list entry for gpt-6-sol"),
                cost_of_pass=stats.Measure(None, reason="no price list entry for gpt-6-sol"),
            ),
        ],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
        frontier=frontier_rows,
        areas=[],
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj)
    cf_match = re.search(r'<section id="cost-frontier".*?</section>', doc, re.DOTALL)
    assert cf_match is not None, "cost-frontier section must be present"
    cf_sec = cf_match.group(0)

    assert "Cost not recorded for any combo: no price list entry for gpt-6-sol." in cf_sec
    # The cost figure must have no svg axes, while tokens and wall figures do have svg
    cost_fig = re.search(r'<figure[^>]*>.*?Cost not recorded.*?</figure>', cf_sec, re.DOTALL)
    assert cost_fig is not None
    assert "<svg" not in cost_fig.group(0)
    assert "<svg" in cf_sec  # other panels still draw


def test_areas_radar_na_axis_drawn_hollow_with_na_tick():
    """Design s6 row 6: an area NA: the axis is drawn hollow with an NA tick; all NA:
    'No area composites for this run: <reason>.'"""
    view = _state_view("valid", None)
    # Case 1: one area NA, one area valid
    areas_rows = [
        board.AreaRow(
            combo="c1",
            pack="on",
            area="correctness",
            interval=stats.Interval(point=Decimal("85.0"), lo=Decimal("70.0"), hi=Decimal("95.0"), n=6, reason=None),
        ),
        board.AreaRow(
            combo="c1",
            pack="on",
            area="cost",
            interval=stats.Interval(point=None, lo=None, hi=None, n=0, reason="not computed"),
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[
            board.BoardRow(
                combo="c1",
                harness="h",
                model="m",
                pack="on",
                rank="1",
                rank_reason=None,
                n_valid=6,
                n_cells=6,
                gated=stats.Interval(point=Decimal("80.0"), lo=Decimal("60.0"), hi=Decimal("95.0"), n=6, reason=None),
                pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
                pass_at_k=stats.Measure(Decimal("0.80")),
                pass_hat_k=stats.Measure(Decimal("0.80")),
                tokens=stats.Measure(Decimal(50000)),
                wall_ms=stats.Measure(Decimal(120000)),
                cost_usd=stats.Measure(Decimal("1.25")),
                cost_of_pass=stats.Measure(Decimal("1.56")),
            ),
        ],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
        frontier=[],
        areas=areas_rows,
    )
    doc = html.render(view, archive_present=True, board_obj=board_obj)
    ar_match = re.search(r'<section id="areas".*?</section>', doc, re.DOTALL)
    assert ar_match is not None, "areas section must be present"
    ar_sec = ar_match.group(0)

    # NA axis is drawn hollow with an NA tick
    assert re.search(r'<line[^>]*class="[^"]*\bna\b[^"]*\bhollow\b[^"]*"', ar_sec) is not None
    assert re.search(r'<text[^>]*class="[^"]*\bna\b[^"]*"[^>]*>.*?NA.*?</text>', ar_sec) is not None
    # The axis labels are the catalog's area names in full, never cut ("corre", "speci")
    assert {t for t in re.findall(r"<text[^>]*>([^<]*)</text>", ar_sec)} >= {"correctness", "cost NA"}

    # Case 2: all NA
    all_na_areas = [
        board.AreaRow(
            combo="c1",
            pack="on",
            area="correctness",
            interval=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no normalisation anchors for catalog 0.4"),
        ),
    ]
    board_all_na = board.Board(
        run_id="r1",
        catalog_version="0.4",
        params=stats.Params(),
        primary="pass_at_1",
        primary_reason="no normalisation anchors",
        rows=board_obj.rows,
        pack_effect=board_obj.pack_effect,
        frontier=[],
        areas=all_na_areas,
    )
    doc_na = html.render(view, archive_present=True, board_obj=board_all_na)
    ar_na_match = re.search(r'<section id="areas".*?</section>', doc_na, re.DOTALL)
    assert ar_na_match is not None
    assert "No area composites for this run: no normalisation anchors for catalog 0.4." in ar_na_match.group(0)
    assert "<svg" not in ar_na_match.group(0)


def test_cli_table_prints_ascii_area_headline_line():
    """UIA-11: report/cli_table.py prints an ASCII area headline line per (combo, pack) that
    passes the plain-output rules."""
    view = _state_view("valid", None)
    areas_rows = [
        board.AreaRow(
            combo="c1",
            pack="on",
            area="correctness",
            interval=stats.Interval(point=Decimal("85.0"), lo=Decimal("70.0"), hi=Decimal("95.0"), n=6, reason=None),
        ),
        board.AreaRow(
            combo="c1",
            pack="on",
            area="cost",
            interval=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no price list entry"),
        ),
    ]
    board_obj = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=stats.Params(),
        primary="gated",
        primary_reason=None,
        rows=[
            board.BoardRow(
                combo="c1",
                harness="h",
                model="m",
                pack="on",
                rank="1",
                rank_reason=None,
                n_valid=6,
                n_cells=6,
                gated=stats.Interval(point=Decimal("80.0"), lo=Decimal("60.0"), hi=Decimal("95.0"), n=6, reason=None),
                pass_at_1=stats.Interval(point=Decimal("0.80"), lo=Decimal("0.40"), hi=Decimal("1.00"), n=6, reason=None),
                pass_at_k=stats.Measure(Decimal("0.80")),
                pass_hat_k=stats.Measure(Decimal("0.80")),
                tokens=stats.Measure(Decimal(50000)),
                wall_ms=stats.Measure(Decimal(120000)),
                cost_usd=stats.Measure(Decimal("1.25")),
                cost_of_pass=stats.Measure(Decimal("1.56")),
            ),
        ],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
        frontier=[],
        areas=areas_rows,
    )
    out, code = cli_table.render(view, plain=True, board_obj=board_obj)
    assert code == 0
    assert out.isascii()
    assert "Areas (c1 on): correctness 85.0, cost NA (no price list entry)" in out

# --- R6 (design phase4-report.md s15, s6 rows 7 and 8, s3 DR-R-1, s12 UIA-11, UIA-13, UXA-8) --------


def _scenario_board(rows, run_id="r1"):
    return board.Board(
        run_id=run_id, catalog_version="0.5", params=stats.Params(), primary="gated", primary_reason=None,
        rows=[], pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]), scenarios=rows,
    )


def _tag(text: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', text)
    return m.group(1) if m else None


def test_scenarios_chart_equals_table_uia13():
    """UIA-13: the heatmap cell IS both the chart and the accessible table (design s6 row 7 names no
    separate table alternative for it, unlike rows 5/6/8's SVG charts) -- so this proves the printed
    composite, [lo, hi] and pass@1 line equal the same cell's own data-* attributes."""
    view = _state_view("valid", None)
    rows = [
        board.ScenarioRow(
            combo="c1", pack="on", scenario=1,
            gated=stats.Interval(point=Decimal("31.0"), lo=Decimal("5.0"), hi=Decimal("66.0"), n=6, reason=None),
            pass_at_1=stats.Interval(point=Decimal("0.72"), lo=Decimal("0.40"), hi=Decimal("0.95"), n=6, reason=None),
        ),
    ]
    doc = html.render(view, archive_present=True, board_obj=_scenario_board(rows))
    section = re.search(r'<section id="scenarios".*?</section>', doc, re.DOTALL).group(0)

    td = re.search(r'<td[^>]*data-scenario="1"[^>]*>.*?</td>', section, re.DOTALL).group(0)
    value, lo, hi, pass1 = _tag(td, "data-value"), _tag(td, "data-interval-lo"), _tag(td, "data-interval-hi"), _tag(td, "data-pass1")
    text = re.search(r">(.*?)</td>$", td, re.DOTALL).group(1)
    assert (value, lo, hi, pass1) == ("31.0", "5.0", "66.0", "0.72")
    assert value in text and f"[{lo}, {hi}]" in text and f"pass@1 {pass1}" in text
    assert 'class="h h3 num"' in td  # bucket 3 (30-39.9) carries the viridis fill class


def test_scenarios_no_cells_and_na_states():
    """Design s6 row 7's two non-computed states: 'no cells in this scenario' (an em dash, no heat
    fill) and NA (hatched, 'not recorded -- <reason>'), never confused with a real composite."""
    view = _state_view("valid", None)
    rows = [
        board.ScenarioRow(
            combo="c1", pack="on", scenario=1,
            gated=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no cells in this scenario"),
            pass_at_1=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no cells in this scenario"),
        ),
        board.ScenarioRow(
            combo="c1", pack="on", scenario=2,
            gated=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no normalisation anchors for catalog 0.4"),
            pass_at_1=stats.Interval(point=Decimal("0.5"), lo=Decimal("0.1"), hi=Decimal("0.9"), n=6, reason=None),
        ),
    ]
    doc = html.render(view, archive_present=True, board_obj=_scenario_board(rows))
    section = re.search(r'<section id="scenarios".*?</section>', doc, re.DOTALL).group(0)

    no_cells_td = re.search(r'<td[^>]*data-scenario="1"[^>]*>.*?</td>', section, re.DOTALL).group(0)
    assert 'class="h"' in no_cells_td and "—" in no_cells_td and "no cells in this scenario" in no_cells_td
    assert "data-value" not in no_cells_td

    na_td = re.search(r'<td[^>]*data-scenario="2"[^>]*>.*?</td>', section, re.DOTALL).group(0)
    assert 'class="h na"' in na_td
    assert "not recorded" in na_td and "no normalisation anchors for catalog 0.4" in na_td
    assert "data-value" not in na_td


def test_scenarios_heat_ink_meets_wcag_aa():
    """Design s3 DR-R-1 / R-81 R-1: the heatmap text ink is whichever of #000/#fff has the higher
    contrast with the cell fill, proven >= 4.5:1 on every one of the ten viridis stops -- recomputed
    here independently from the exact colours in html.STYLE, never a copy of html.py's own table."""
    def luminance(hexcolor: str) -> float:
        def lin(c: int) -> float:
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        h = hexcolor.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    ink_hex = {
        "on-heat-dark": re.search(r"--on-heat-dark:\s*(#[0-9a-fA-F]{6})", html.STYLE).group(1),
        "on-heat-light": re.search(r"--on-heat-light:\s*(#[0-9a-fA-F]{6})", html.STYLE).group(1),
    }
    for i in range(10):
        fill = re.search(rf"--heat-{i}:\s*(#[0-9a-fA-F]{{6}})", html.STYLE).group(1)
        rule = re.search(rf"\.h{i}\{{background:var\(--heat-{i}\);color:var\(--(on-heat-\w+)\)\}}", html.STYLE)
        assert rule is not None, f"no .h{i} rule in STYLE"
        applied = rule.group(1)

        fill_l = luminance(fill)
        c_white = 1.05 / (fill_l + 0.05)
        c_black = (fill_l + 0.05) / 0.05
        expected = "on-heat-dark" if c_white >= c_black else "on-heat-light"
        assert applied == expected, f"h{i} uses {applied}, the higher-contrast ink is {expected}"

        applied_l = luminance(ink_hex[applied])
        lighter, darker = (fill_l, applied_l) if fill_l > applied_l else (applied_l, fill_l)
        contrast = (lighter + 0.05) / (darker + 0.05)
        assert contrast >= 4.5, f"h{i} ink/fill contrast {contrast:.2f} < 4.5"


def test_scenarios_empty_run_draws_no_axes_uxa8():
    """UXA-8, synthetic branch: an injected empty `board_obj.scenarios` (the defensive arm `_runs`'s
    own 'no cells in this run' branch mirrors) shows the empty copy and no heatmap table at all."""
    view = _state_view("valid", None)
    doc = html.render(view, archive_present=True, board_obj=_scenario_board([]))
    section = re.search(r'<section id="scenarios".*?</section>', doc, re.DOTALL).group(0)
    assert "No cell completed in this run. Run bench status r1 to see why." in section
    assert '<table class="heat"' not in section


def test_scenarios_zero_completed_cells_draws_no_heat_table(root, tmp_path):
    """UXA-8, the design's own `empty` fixture (0 completed): `board.build` still emits a 'no cells
    in this scenario' row per planned (combo, pack, scenario) -- so the check that matters is '0
    completed', not 'scenarios list is empty', and the section must still show the empty copy, not a
    heatmap table full of nothing but dashes."""
    _, view = _graded(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"}})
    doc = html.render(view, archive_present=True)
    section = re.search(r'<section id="scenarios".*?</section>', doc, re.DOTALL).group(0)
    assert "No cell completed in this run. Run bench status r1 to see why." in section
    assert '<table class="heat"' not in section


def _cg_series(**kw) -> context_growth.TaskSeries:
    return context_growth.TaskSeries(combo="c1", pack="on", **kw)


def test_context_growth_chart_equals_table_uia13():
    """UIA-13: every mark's data-value/data-interval-lo/hi (plus the compaction mark) equal its
    table row's cells, per (combo, pack, turn)."""
    view = _state_view("valid", None)
    series = (_cg_series(turns=(1, 2, 3), median=(1000, 4000, 9000), lo=(900, 3500, 8000), hi=(1100, 4500, 9800), compactions=(3,)),)
    cg = context_growth.ContextGrowthResult(tasks=(context_growth.TaskGrowth(task="X1", series=series),))
    doc = html.render(view, archive_present=True, context_growth_obj=cg)
    section = re.search(r'<section id="context-growth".*?</section>', doc, re.DOTALL).group(0)

    chart_marks = sorted(re.findall(
        r'<circle[^>]*data-turn="(\d+)"[^>]*data-value="(\d+)"[^>]*data-interval-lo="(\d+)"[^>]*data-interval-hi="(\d+)"',
        section,
    ))
    assert len(chart_marks) == 3
    table_rows = sorted(re.findall(
        r'<td class="num">(\d+)</td><td class="num" data-value="(\d+)">\d+</td>'
        r'<td data-interval-lo="(\d+)" data-interval-hi="(\d+)">',
        section,
    ))
    assert len(table_rows) == 3
    assert chart_marks == table_rows

    assert re.search(r'<polygon[^>]*data-turn="3"[^>]*data-compaction="true"', section) is not None
    assert re.search(r'<circle[^>]*data-turn="1"[^>]*', section) and "data-compaction" not in re.search(
        r'<circle[^>]*data-turn="1"[^>]*/>', section).group(0)
    assert "▲" in section  # the table's own compaction mark text (design s6 row 8)


def test_context_growth_empty_run_draws_no_axes_uxa8():
    """UXA-8: an empty `ContextGrowthResult` (no task carries turns -- today's real state, see
    report/context_growth.py's assume:) shows the empty copy and no `<svg>` chart at all."""
    view = _state_view("valid", None)
    doc = html.render(view, archive_present=True, context_growth_obj=context_growth.ContextGrowthResult(tasks=()))
    section = re.search(r'<section id="context-growth".*?</section>', doc, re.DOTALL).group(0)
    assert "No cell completed in this run. Run bench status r1 to see why." in section
    assert "<svg" not in section


def test_context_growth_copilot_cell_reads_session_totals_reason():
    """One of the two NA rules (design phase4-report.md section 4): a Copilot cell's native record
    is the last shutdown's session total per model, never per call, so `build()` reads
    `grade/cost.py`'s own `SESSION_TOTALS` reason constant (DM7: one definition, not a second copy of
    the text) -- never the generic 'no turns recorded' placeholder, which is for a task with no
    model_calls rows at all."""
    view = _state_view("valid", None)
    result = context_growth.build(view)
    assert len(result.tasks) == 1
    task = result.tasks[0]
    assert task.task == "X1" and task.series == () and task.reason == grade_cost.SESSION_TOTALS


def test_context_growth_series_follows_model_calls_in_ordinal_order(root, tmp_path):
    """R6c: the series is the cell's own `model_calls` rows' context size (uncached_input +
    cache_read + cache_write, `grade/cost.py`'s `_context_growth` formula), in native_ordinal order.
    The real X1/codex fixture (`tests/fixtures/native/codex/ok.jsonl`) records three calls whose
    context size grows monotonically (14920, 15372, 15596), so the series equals those sizes in
    order and flags no compaction."""
    run_dir, view = _graded(root, tmp_path, {"a": GOOD})
    result = context_growth.build(view, run_dir)
    task = next(t for t in result.tasks if t.task == "X1")
    assert task.reason is None
    assert len(task.series) == 1
    s = task.series[0]
    assert s.combo == "c" and s.pack == "off"
    assert s.turns == (1, 2, 3)
    assert s.median == (14920, 15372, 15596)
    assert s.lo == s.median and s.hi == s.median  # a single repetition: no band
    assert s.compactions == ()  # monotonically increasing


def test_cli_table_prints_scenario_headline_line_uia11():
    """UIA-11 (design s6 row 7): one ASCII headline line per (combo, pack, scenario), computed
    (no colour), NA and 'no cells' read as text -- the same plain-output rule the rest of the CLI
    table follows."""
    view = _state_view("valid", None)
    board_obj = _scenario_board([
        board.ScenarioRow(
            combo="cop-sol", pack="off", scenario=1,
            gated=stats.Interval(point=Decimal("55.2"), lo=Decimal("20.1"), hi=Decimal("88.0"), n=6, reason=None),
            pass_at_1=stats.Interval(point=Decimal("0.67"), lo=Decimal("0.33"), hi=Decimal("1.00"), n=6, reason=None),
        ),
        board.ScenarioRow(
            combo="cop-sol", pack="off", scenario=6,
            gated=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no cells in this scenario"),
            pass_at_1=stats.Interval(point=None, lo=None, hi=None, n=0, reason="no cells in this scenario"),
        ),
    ])
    out, _ = cli_table.render(view, plain=True, board_obj=board_obj)
    assert out.isascii()
    assert "cop-sol off scenario 1: 55.2 [20.1, 88.0] pass@1 0.67" in out
    assert "cop-sol off scenario 6: no cells in this scenario" in out

