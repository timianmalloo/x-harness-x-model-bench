"""R-REPORT-R: `cost_compare.render` (ADR-0027 s0, s3, s7) from hand-built `CostCompare` fixtures.

The fake egress scan below is this test file's own (seam S-1): `render` holds no shape regex; it takes the scan
injected, defaulting to `report.publish.scan_text`.
"""

from __future__ import annotations

import dataclasses
import html
import os
import re
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench.report import cost_compare as cc_mod
from harness_bench.report.cost_compare import (
    KIVIAT_AXES,
    ComboRow,
    ContextCurve,
    CostCompare,
    DriftRow,
    KiviatSeries,
    PromptComposition,
    ReasoningRow,
    SeriesKey,
    TimeAnatomyRow,
    ToolPhaseRow,
)
from harness_bench.views import Measure

GOLDEN = Path(__file__).parent / "goldens" / "cost-compare-render.html"
AXE = Path(__file__).parent / "vendor" / "axe-core" / "axe.min.js"

SECTION_IDS = ["header", "benchmarked", "harnesses", "cost", "observations", "same-model", "reasoning",
               "context-curve", "prompt-composition", "tool-phases", "time-anatomy", "drift", "kiviat"]
NEW_SECTIONS = ["reasoning", "context-curve", "prompt-composition", "tool-phases", "time-anatomy", "drift", "kiviat"]

COMBOS = (
    ("cc-opus", "claude-code", "claude-opus-5-5", "acp"),
    ("codex-sol", "codex", "gpt-6.1-sol", "acp"),
    ("copilot-sol", "copilot", "gpt-6.1-sol", "copilot -p (local adapter)"),
    ("grok", "grok", "grok-4.7", "native stream"),
    ("agy", "agy", "gemini-3.8-flash", "native stream"),
    ("copilot-opus", "copilot", "claude-opus-5-5", "copilot -p (local adapter)"),
)
ARMS = ("off", "on")
EMAIL_EXCERPT = "I will mail someone@example.org about the failing test."
UUID_EXCERPT = "The session 0f8fad5b-d9cb-469f-a165-70867728950e was resumed."
LONG_EXCERPT = "x" * 400
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def fake_scan(text: str) -> list[str]:
    """The test's stand-in for publish.scan_text: an email shape (`@`) and a UUID shape."""
    return (["email shape"] if "@" in text else []) + (["uuid shape"] if _UUID.search(text) else [])


def _series() -> list[SeriesKey]:
    return [SeriesKey(combo, harness, model, arm, transport)
            for arm in ARMS for combo, harness, model, transport in COMBOS]


def _m(v) -> Measure:
    return Measure(v)


def _excerpts(s: SeriesKey) -> tuple[str, ...]:
    if s.harness == "claude-code" and s.arm == "off":
        return ("Read the failing test first.", EMAIL_EXCERPT, UUID_EXCERPT)
    if s.harness == "claude-code":
        return ("Then edit the parser.", LONG_EXCERPT, "Run pytest on the one file.", "A fourth one, over the cap.")
    return (f"{s.harness} {s.arm}: plan the edit.",)


def full_fixture(excerpts: bool = True) -> CostCompare:
    series = _series()
    combos, reasoning, context, prompt, phases, anatomy, drift, kiviat = [], [], [], [], [], [], [], []
    for i, s in enumerate(series, start=1):
        window = 922000 if s.harness == "agy" else 1000000
        combos.append(ComboRow(
            series=s, cells=20, effort_requested="high", effort_served=_m("high" if i % 2 else "medium"),
            context_requested="default", context_served=_m(window), tokens_per_cell=_m(100000 * i),
            tokens_by_bucket={"fresh input": _m(1000 * i), "cache read": _m(90000 * i), "cache write": _m(5000 * i),
                              "output": _m(4000 * i)},
            wall_ms=_m(60000 + 1000 * i), requests_per_cell=_m(Decimal(f"{i}.5")), tool_calls_per_cell=_m(3 * i)))
        reasoning.append(ReasoningRow(
            series=s, tokens_per_cell=_m(100 * i), tokens_per_request=_m(Decimal(f"{i}.25")),
            visible_chars=_m(250 * i), source_kinds=("summary",) if i % 2 else ("raw", "summary"),
            excerpts=_excerpts(s), excerpts_dropped=1 if s.harness == "claude-code" else 0))
        context.append(ContextCurve(series=s, served_window=_m(window), median=(1000 * i, 2000 * i, 3000 * i),
                                    low=(900 * i, 1800 * i, 2700 * i), high=(1100 * i, 2200 * i, 3300 * i)))
        prompt.append(PromptComposition(
            series=s, chars_by_part={"harness instructions": _m(19000 + i), "tool catalogue": _m(5000 + i),
                                     "AGENTS.md / CLAUDE.md": _m(0 if s.arm == "off" else 27000)},
            instruction_files=_m(0 if s.arm == "off" else 13)))
        phases.append(ToolPhaseRow(series=s, explore=_m(5 + i), edit=_m(2 + i), verify=_m(1 + i), other=_m(i),
                                   bytes_returned=_m(10000 * i)))
        anatomy.append(TimeAnatomyRow(
            series=s, model_ms=_m(40000 + i) if s.transport != "acp" else Measure(None, "ACP carries no model time"),
            model_ms_acp_estimate=_m(39000 + i) if s.transport == "acp" else Measure(None, "native time recorded"),
            tool_ms=_m(9000 + i), hook_ms=_m(100 * i), idle_ms=_m(500 + i)))
        drift.append(DriftRow(series=s, machine_lines=_m(i), task_implied_lines=_m(2 * i),
                              discretionary_lines=_m(3 * i), attention_drift=_m(Decimal(f"0.{i:02d}")),
                              out_of_scope_paths=("README.md", "pyproject.toml") if s.harness == "copilot" else ()))
        axes = {a: str(Decimal(i) * Decimal(j + 1) / Decimal(10)) for j, a in enumerate(KIVIAT_AXES)}
        if i == 1:
            axes["speed"] = None
        kiviat.append(KiviatSeries(series=s, axes=axes))
    return CostCompare(runs=("run-b1", "run-b2"), catalog_version="0.8", excerpts=excerpts, combos=tuple(combos),
                       reasoning=tuple(reasoning), context=tuple(context), prompt_composition=tuple(prompt),
                       tool_phases=tuple(phases), time_anatomy=tuple(anatomy), drift=tuple(drift),
                       kiviat=tuple(kiviat))


def absent_fixture() -> CostCompare:
    """An older run: tokens recorded, every new stream absent."""
    na = Measure(None, "stream absent")
    series = _series()
    return CostCompare(
        runs=("run-old",), catalog_version=None, excerpts=True,
        combos=tuple(ComboRow(series=s, cells=20, effort_requested="default", effort_served=na,
                              context_requested="default", context_served=na, tokens_per_cell=_m(100000),
                              tokens_by_bucket={}, wall_ms=_m(60000), requests_per_cell=_m(10),
                              tool_calls_per_cell=_m(6)) for s in series),
        reasoning=tuple(ReasoningRow(series=s, tokens_per_cell=na, tokens_per_request=na, visible_chars=na,
                                     source_kinds=(), excerpts=(), excerpts_dropped=0) for s in series),
        context=tuple(ContextCurve(series=s, served_window=na, median=(), low=(), high=()) for s in series),
        prompt_composition=tuple(PromptComposition(series=s, chars_by_part={}, instruction_files=na) for s in series),
        tool_phases=tuple(ToolPhaseRow(series=s, explore=na, edit=na, verify=na, other=na, bytes_returned=na)
                          for s in series),
        time_anatomy=tuple(TimeAnatomyRow(series=s, model_ms=na, model_ms_acp_estimate=na, tool_ms=na, hook_ms=na,
                                          idle_ms=na) for s in series),
        drift=tuple(DriftRow(series=s, machine_lines=na, task_implied_lines=na, discretionary_lines=na,
                             attention_drift=na, out_of_scope_paths=()) for s in series),
        kiviat=tuple(KiviatSeries(series=s, axes={a: None for a in KIVIAT_AXES}) for s in series))


def _render(cc: CostCompare) -> str:
    return cc_mod.render(cc, scan=fake_scan)


def _section(doc: str, sid: str) -> str:
    m = re.search(rf'<section id="{sid}">(.*?)</section>', doc, re.DOTALL)
    assert m, f"section {sid} missing"
    return m.group(1)


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment))


# 1 ---------------------------------------------------------------------------------------------------------------
def test_every_adr_0027_section_is_present_by_its_stable_id_in_order():
    doc = _render(full_fixture())
    assert re.findall(r'<section id="([^"]+)">', doc) == SECTION_IDS
    for sid in SECTION_IDS[1:]:
        assert f'<a href="#{sid}">' in doc, sid
    assert "equal setting is not proven equal depth" in _section(doc, "reasoning")
    assert "README.md" in _section(doc, "drift") and "pyproject.toml" in _section(doc, "drift")


# 2 ---------------------------------------------------------------------------------------------------------------
def _polygons(doc: str) -> dict[str, dict[str, str]]:
    found = {}
    for tag in re.findall(r"<polygon [^>]*data-kiviat-series=[^>]*>", doc):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        found[attrs["data-kiviat-series"]] = attrs
    return found


def test_the_kiviat_has_12_checkboxes_and_each_axis_is_normalised_over_all_12_series():
    cc = full_fixture()
    doc = _render(cc)
    kv = _section(doc, "kiviat")
    boxes = re.findall(r'<input [^>]*type="checkbox"[^>]*>', kv)
    assert len(boxes) == 12 and all("checked" in b for b in boxes)
    assert len(_polygons(doc)) == 12
    maxes = dict(re.findall(r'<line [^>]*data-axis="([^"]+)" data-max="([^"]+)"', kv))
    assert list(maxes) == list(KIVIAT_AXES)
    on_only = [s for s in cc.kiviat if s.series.arm == "off"]
    for axis in KIVIAT_AXES:
        over_all = max(Decimal(s.axes[axis]) for s in cc.kiviat if s.axes[axis] is not None)
        over_off = max(Decimal(s.axes[axis]) for s in on_only if s.axes[axis] is not None)
        assert over_all != over_off  # the fixture tells "all 12" apart from one arm's six
        assert Decimal(maxes[axis]) == over_all, axis
    polys = _polygons(doc)
    for k, s in enumerate(cc.kiviat):
        norms = polys[str(k)]["data-norm"].split(",")
        for axis, got in zip(KIVIAT_AXES, norms, strict=True):
            raw = s.axes[axis]
            want = "na" if raw is None else f"{Decimal(raw) / Decimal(maxes[axis]):.4f}"
            assert got == want, (k, axis)


# 3 and 2 (the toggle) ---------------------------------------------------------------------------------------------
@pytest.fixture
def cc_page(tmp_path):
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    path = tmp_path / "cost-compare.html"
    path.write_text(_render(full_fixture()), encoding="utf-8", newline="\n")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(path.as_uri())
        yield page
        browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_reports_0_violations_for_the_cost_compare_page_in_light_and_dark(cc_page, scheme):
    assert cc_page.locator("section").count() == len(SECTION_IDS)  # axe ran on the whole page, not a stub
    cc_page.emulate_media(color_scheme=scheme)
    cc_page.evaluate("document.querySelectorAll('details').forEach(d => { d.open = true; })")
    cc_page.evaluate(AXE.read_text(encoding="utf-8"))
    found = cc_page.evaluate(
        "axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']}).then(r =>"
        " ({violations: r.violations.map(v => v.id + ': ' + v.nodes.length), passes: r.passes.length}))")
    assert found["passes"] > 0, "axe ran no rule on the page"
    assert found["violations"] == []


@pytest.mark.browser
def test_toggling_a_kiviat_series_hides_it_and_moves_no_other_series(cc_page):
    read = ("Array.from(document.querySelectorAll('polygon[data-kiviat-series]'))"
            ".map(p => [p.dataset.kiviatSeries, p.getAttribute('points'), p.getBoundingClientRect().width > 0])")
    before = cc_page.evaluate(read)
    assert len(before) == 12 and all(visible for _, _, visible in before)
    cc_page.click("label[for='kv-3']")
    after = cc_page.evaluate(read)
    assert [(k, pts) for k, pts, _ in after] == [(k, pts) for k, pts, _ in before]
    assert [k for k, _, visible in after if not visible] == ["3"]
    cc_page.click("label[for='kv-3']")
    assert all(visible for _, _, visible in cc_page.evaluate(read))


# 4 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("fixture", [full_fixture, absent_fixture])
@pytest.mark.parametrize("excerpts", [True, False])
def test_the_page_carries_no_price(fixture, excerpts):
    cc = fixture()
    doc = _render(dataclasses.replace(cc, excerpts=excerpts))
    assert _section(doc, "cost")
    for refused in ("$", "USD", "cost_usd"):
        assert refused not in doc, refused


# 5 ---------------------------------------------------------------------------------------------------------------
def test_an_email_or_uuid_shaped_excerpt_is_dropped_and_counted_through_the_injected_scan():
    cc = full_fixture(excerpts=True)
    reasoning = _section(_render(cc), "reasoning")
    assert "someone@example.org" not in reasoning and "0f8fad5b" not in reasoning
    built = sum(r.excerpts_dropped for r in cc.reasoning if r.series.harness == "claude-code")
    assert re.search(rf'data-dropped="claude-code" data-count="{built + 2}"', reasoning)
    assert re.search(r'data-dropped="codex" data-count="0"', reasoning)


def test_the_default_scan_is_publish_scan_text(monkeypatch):
    from harness_bench.report import publish
    seen: list[str] = []
    monkeypatch.setattr(publish, "scan_text", lambda text: seen.append(text) or [])
    cc_mod.render(full_fixture(excerpts=True))
    assert EMAIL_EXCERPT in seen


# 6 ---------------------------------------------------------------------------------------------------------------
def test_excerpts_are_absent_by_default_and_capped_when_on():
    off = _render(full_fixture(excerpts=False))
    assert "data-excerpt" not in off
    for r in full_fixture().reasoning:
        for e in r.excerpts:
            assert html.escape(e, quote=True) not in off
    assert "--excerpts" in _section(off, "reasoning")
    on = _section(_render(full_fixture(excerpts=True)), "reasoning")
    quoted = re.findall(r'<blockquote class="excerpt" data-excerpt="([^"]+)">(.*?)</blockquote>', on, re.DOTALL)
    by_harness: dict[str, list[str]] = {}
    for harness, text in quoted:
        by_harness.setdefault(harness, []).append(html.unescape(text))
    assert sorted(by_harness) == ["agy", "claude-code", "codex", "copilot", "grok"]
    assert all(len(v) <= 3 for v in by_harness.values())
    assert all(len(t) <= 280 for v in by_harness.values() for t in v)
    assert len(by_harness["claude-code"]) == 3 and len(by_harness["copilot"]) == 3


def test_every_excerpt_and_nothing_else_carries_class_excerpt():
    """R-VALIDITY's seam: `publish.publish` drops excerpts by element marking, so class="excerpt" marks exactly the
    rendered excerpts (any element), and no other element."""
    on = _render(full_fixture(excerpts=True))
    marked = re.findall(r'<(\w+) [^>]*class="[^"]*\bexcerpt\b[^"]*"', on)
    assert marked == ["blockquote"] * len(re.findall(r"data-excerpt=", on)) and len(marked) == 12
    off = _render(full_fixture(excerpts=False))
    assert not re.search(r'class="[^"]*\bexcerpt\b', off)


# 7 ---------------------------------------------------------------------------------------------------------------
def test_every_combo_row_shows_its_transport_and_the_served_window_where_it_is_not_1m():
    cc = full_fixture()
    doc = _render(cc)
    by_id = {f"{s.combo}/{s.arm}": s for s in (k.series for k in cc.kiviat)}
    rows = re.findall(r'<tr data-series="([^"]+)">(.*?)</tr>', doc, re.DOTALL)
    assert len(rows) >= 12 * 8
    for sid, body in rows:
        s = by_id[sid]
        assert s.transport in _text(body), sid
        assert ("served window" in _text(body)) == (s.harness == "agy"), sid  # only where it differs from 1M
        assert ("served window 922,000" in _text(body)) == (s.harness == "agy"), sid
    copilot = [body for sid, body in rows if by_id[sid].harness == "copilot"]
    assert copilot and all("copilot -p (local adapter)" in _text(b) for b in copilot)


# 8 ---------------------------------------------------------------------------------------------------------------
def test_absent_streams_render_not_recorded_with_the_reason_in_every_new_section_never_blank_or_0():
    doc = _render(absent_fixture())
    for sid in NEW_SECTIONS:
        body = _section(doc, sid)
        # KiviatSeries carries no reason (axis -> None), so its section names the absent value, not the stream.
        reason = "not recorded (no value for this axis)" if sid == "kiviat" else "not recorded (stream absent)"
        assert reason in _text(body), sid
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", body, re.DOTALL):
            assert _text(cell).strip() not in ("", "0"), (sid, cell)
    assert "not recorded" in _text(_section(doc, "header"))  # catalog version None


# 9 ---------------------------------------------------------------------------------------------------------------
def test_the_golden_is_byte_equal_on_re_render():
    page = _render(full_fixture(excerpts=True)).encode("utf-8")
    if os.environ.get("HB_UPDATE_COST_COMPARE_RENDER_GOLDEN") == "1":
        GOLDEN.write_bytes(page)
    assert b"\r\n" not in page
    assert page == GOLDEN.read_bytes()
    assert page == _render(full_fixture(excerpts=True)).encode("utf-8")
