"""The report: CLI table and the static HTML skeleton (design: UI & interaction design; test plan UI rows).

T-CLI-states, T-CLI-plain, T-CLI-exit (the table's part), T-UI-states, T-UI-NA, T-UI-tokens, T-UI-contrast,
T-UI-keyboard, T-UI-numerics, structural accessibility (lang, title, caption, th scope), no network, and
T-SEC-report (a planted token is found and the report is refused).
"""

import json
import re

import pytest
from archived_runs import GOOD, STUB, make_root, make_run

from harness_bench import ledger, views
from harness_bench.errors import BenchError
from harness_bench.grade import runner
from harness_bench.report import cli_table, credentials, html


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
    row = next(r for r in re.findall(r"<tr>.*?</tr>", runs, re.DOTALL) if "cc-opus" in r)
    assert "<td>Claude Code cells ran with the 1M context window</td>" in row


def test_the_header_and_drill_down_read_not_recorded_without_a_tag(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"b": GOOD}, harness="codex", combos={"b": "codex-sol"})  # no context_window_tag
    doc = html.render(views.load(run_dir), archive_present=True, run_dir=run_dir)
    header = re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0)
    assert "<dt>Context window</dt><dd>not recorded</dd>" in header
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    row = next(r for r in re.findall(r"<tr>.*?</tr>", runs, re.DOTALL) if "codex-sol" in r)
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
        rows = re.findall(r"<tr>.*?</tr>", section, re.DOTALL)
        codex_row = next(r for r in rows if "codex-sol" in r)
        cc_row = next(r for r in rows if "cc-sonnet" in r)
        assert N5_FLAG in codex_row
        assert N5_FLAG not in cc_row


def test_the_cli_table_prints_the_flag_as_ascii_after_the_table_when_a_codex_cell_is_present():
    out, code = cli_table.render(_codex_only_view(), plain=True)
    assert code == 0 and out.isascii() and N5_FLAG in out


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
        rows = re.findall(r"<tr>.*?</tr>", section, re.DOTALL)
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
    cells = re.findall(r"<td[^>]*>(.*?)</td>", re.search(r"<tbody>(.*?)</tbody>", runs, re.DOTALL).group(1))
    assert cells[headers.index("Warnings")] == "HB-VAL-005, HB-VAL-006"


def test_the_html_cells_table_reads_none_for_a_cell_without_warnings():
    doc = html.render(_state_view("valid", None), archive_present=True)
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    headers = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', runs)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", re.search(r"<tbody>(.*?)</tbody>", runs, re.DOTALL).group(1))
    assert cells[headers.index("Warnings")] == "none" and '<ul id="validity-warnings">' not in doc


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
