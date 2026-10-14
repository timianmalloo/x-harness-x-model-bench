"""R-DERIV: `bench report --cost-compare` end to end (ADR-0027 s1-s5), and the derivations it reads (ADR-0026 s4).

Two archived, graded Copilot fixture runs on R-GOLD's frozen root: `b1` planned behind the local adapter (`copilot -p`,
the plan's build names `adapter_version`), `b2` over ACP, whose cell `a` carries an ACP update timeline. The golden is
the page `build` + `render` write for them; the root it is built on reads nothing from the repository's `bench/`.
"""

import dataclasses
import json
import re
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import GOOD, ROOT, make_root, make_run

from harness_bench import cli, views
from harness_bench import plan as plan_mod
from harness_bench.errors import BenchError
from harness_bench.grade import runner
from harness_bench.report import context_growth, cost_compare, publish, tool_phases

GOLDEN = Path(__file__).parent / "goldens" / "cost-compare.html"
MS = 1_000_000
# cell a of b2: a prompt at 2 s, a tool call at 5 s, its result at 6 s, the turn's end at 10 s (mono clock)
TIMELINE = [
    {"first_mono_ns": 1_500 * MS, "last_mono_ns": 1_500 * MS, "count": 1, "method": "session/new", "update_kind": "sent"},
    {"first_mono_ns": 2_000 * MS, "last_mono_ns": 2_000 * MS, "count": 1, "method": "session/prompt", "update_kind": "sent"},
    {"first_mono_ns": 3_000 * MS, "last_mono_ns": 4_000 * MS, "count": 9, "method": "session/update",
     "update_kind": "agent_message_chunk"},
    {"first_mono_ns": 5_000 * MS, "last_mono_ns": 5_000 * MS, "count": 1, "method": "session/update", "update_kind": "tool_call",
     "tool_call_id": "t1"},
    {"first_mono_ns": 5_500 * MS, "last_mono_ns": 6_000 * MS, "count": 2, "method": "session/update",
     "update_kind": "tool_call_update", "tool_call_id": "t1"},
    {"first_mono_ns": 10_000 * MS, "last_mono_ns": 10_000 * MS, "count": 1, "method": "session/prompt", "update_kind": "response"},
]
HAND_ESTIMATE_MS = (5_000 - 2_000) + (10_000 - 6_000)


def _run(root: Path, tmp: Path, runs: Path, run_id: str, adapter: bool, timeline: bool) -> Path:
    built = make_run(root, tmp, {"a": GOOD, "b": GOOD}, harness="copilot")
    plan = json.loads((built / "plan.json").read_text(encoding="utf-8"))
    plan["run_id"] = run_id
    if adapter:
        plan["builds"] = {"copilot": {"adapter_version": "0.1.0"}}
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (built / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    if timeline:
        home = built / "archive" / "a" / "attempt-1" / "home"
        (home / "acp-timeline.jsonl").write_text("".join(json.dumps(r) + "\n" for r in TIMELINE), encoding="utf-8")
    run_dir = runs / run_id
    shutil.move(str(built), str(run_dir))
    runner.run_pass(run_dir, root)
    return run_dir


@pytest.fixture
def fixture_runs(tmp_path):
    root = make_root(tmp_path / "r")
    runs = tmp_path / "runs"
    runs.mkdir()
    b1 = _run(root, tmp_path / "t1", runs, "b1", adapter=True, timeline=False)
    b2 = _run(root, tmp_path / "t2", runs, "b2", adapter=False, timeline=True)
    return root, runs, [views.load(b1), views.load(b2)]


# --- the derivations ---------------------------------------------------------------------------------------------

def test_acp_intervals_run_from_a_prompt_or_tool_result_to_the_next_tool_call_or_turn_end():
    assert views.acp_intervals(TIMELINE) == [(2_000 * MS, 5_000 * MS), (6_000 * MS, 10_000 * MS)]


def test_the_timeline_labels_are_the_drivers_constants_matched_exactly():
    """J2-FIX item 7 (Leader ruling, R-DERIV seam 3): `views` reads the driver's exported timeline labels, never a
    `/prompt` suffix match that dodges `test_only_driver_speaks_acp`."""
    import ast

    from harness_bench import driver

    assert (driver.TIMELINE_PROMPT, driver.TIMELINE_SENT, driver.TIMELINE_RESPONSE, driver.TIMELINE_TOOL_CALL,
            driver.TIMELINE_TOOL_CALL_UPDATE) == ("session/prompt", "sent", "response", "tool_call", "tool_call_update")
    other = [r | {"method": "session/other/prompt"} if r["method"] == driver.TIMELINE_PROMPT else r for r in TIMELINE]
    assert views.acp_intervals(other) == []  # a method that only ends in /prompt is not the prompt
    source = Path(views.__file__).read_text(encoding="utf-8")
    assert "/prompt" not in {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant)}


def test_time_anatomy_keeps_model_time_and_labels_the_acp_estimate_as_its_own_measure(fixture_runs):
    _, _, (v1, v2) = fixture_runs
    a = next(c for c in v2.cells if c.cell_id == "a")
    t = views.time_anatomy(v2, a)
    assert t.model_ms == a.model_ms and t.tool_ms == a.tool_ms  # the native measures keep their meaning
    assert t.model_ms_acp_estimate == views.Measure(HAND_ESTIMATE_MS)
    # the native tool spans are on the epoch clock, the estimate's on the mono clock, and the fixture's process start
    # records no epoch instant: the union is not separable, never a plausible number
    assert t.idle_ms == views.Measure(None, views.NO_ANCHOR)
    plain = views.time_anatomy(v1, next(c for c in v1.cells if c.cell_id == "a"))
    assert plain.model_ms_acp_estimate == views.Measure(None, views.NO_TIMELINE)
    assert plain.idle_ms == views.Measure(None, views.NOT_SEPARABLE)


def test_hook_time_is_the_union_of_hook_spans_and_not_recorded_with_no_hook_row(fixture_runs):
    _, _, (v1, _) = fixture_runs
    cell = v1.cells[0]
    assert views.time_anatomy(v1, cell).hook_ms == views.Measure(None, views.NO_HOOKS)
    hook = {"cell_id": cell.cell_id, "extraction_id": cell.extraction_id, "event": "hook", "start": "2026-09-23T10:00:00+00:00",
            "end": "2026-09-23T10:00:02+00:00"}
    v1.facts["harness_events"] = [hook, hook | {"start": "2026-09-23T10:00:01+00:00", "end": "2026-09-23T10:00:04+00:00"}]
    assert views.time_anatomy(v1, cell).hook_ms == views.Measure(4000)


def test_a_reader_that_records_hook_time_only_for_printing_hooks_says_so_in_the_hook_ms_reason(fixture_runs):
    """W5 decision 3 / W14: Claude Code records a tool hook only when it prints (a `hook_success` attachment), with the
    end and a duration but no start. The reason comes from the reader module's own `HOOK_TIME_REASON`; a harness whose
    reader states none keeps the generic interval reason."""
    from harness_bench.telemetry import claude_code

    _, _, (v1, _) = fixture_runs
    cell = v1.cells[0]
    hook = {"cell_id": cell.cell_id, "extraction_id": cell.extraction_id, "event": "hook", "start": None,
            "end": "2026-09-23T10:00:02+00:00"}
    v1.facts["harness_events"] = [hook]
    assert views.time_anatomy(v1, cell).hook_ms == views.Measure(None, "an interval has no start or end")
    claude = dataclasses.replace(cell, harness="claude-code")
    reason = views.time_anatomy(v1, claude).hook_ms.reason
    assert reason == claude_code.HOOK_TIME_REASON and "only when the hook prints output" in reason


def test_request_series_is_per_request_or_not_recorded_with_its_reason(fixture_runs):
    _, _, (v1, _) = fixture_runs
    cell = v1.cells[0]
    assert context_growth.request_series(v1, cell.cell_id).reason == context_growth.NOT_PER_REQUEST  # 5 requests, 1 row
    grok = dataclasses.replace(v1, cells=[dataclasses.replace(c, harness="grok") for c in v1.cells])
    assert context_growth.request_series(grok, cell.cell_id).reason == "per-turn totals only"
    base = next(r for r in v1.facts["model_calls"] if r["cell_id"] == cell.cell_id)
    v1.facts["model_calls"] = [base | {"native_ordinal": n, "requests": 1, "uncached_input": u, "cache_read": 0,
                                       "cache_write": 0, "start": f"2026-09-23T10:00:0{n}+00:00",
                                       "end": f"2026-09-23T10:00:0{n}+00:00"} for n, u in ((1, 100), (2, 300), (3, 50))]
    v1.facts["harness_events"] = [{"cell_id": cell.cell_id, "extraction_id": cell.extraction_id, "event": "compaction",
                                   "start": "2026-09-23T10:00:02.500+00:00", "end": None}]
    series = context_growth.request_series(v1, cell.cell_id)
    assert (series.inputs, series.compacted_before, series.reason) == ((100, 300, 50), (2,), None)
    assert tool_phases.carry_until_compaction(series.inputs, series.compacted_before) == (100, 400, 50)
    assert context_growth.peak_vs_window(series, views.Measure(1000)) == views.Measure(Decimal("0.3000"))
    assert context_growth.peak_vs_window(series, views.Measure(None, "x")).reason == "x"


# --- build -------------------------------------------------------------------------------------------------------

def test_build_fills_each_combo_transport_from_the_plan(fixture_runs):
    _, _, vs = fixture_runs
    cc = cost_compare.build(vs)
    assert [(r.series.transport, r.cells) for r in cc.combos] == [("copilot -p (local adapter)", 2), ("acp", 2)]


def _measures(obj):
    if isinstance(obj, views.Measure):
        yield obj
    elif dataclasses.is_dataclass(obj):
        for f in dataclasses.fields(obj):
            yield from _measures(getattr(obj, f.name))
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _measures(v)
    elif isinstance(obj, tuple):
        for v in obj:
            yield from _measures(v)


def test_every_number_on_the_page_traces_to_a_view_field(fixture_runs):
    _, _, vs = fixture_runs
    cc = cost_compare.build(vs)
    cells = [c for v in vs for c in v.cells]
    # the cost figures, against the views' own fields
    for row in cc.combos:
        mine = [c for v in vs for c in v.cells if (v.plan["run_id"] == "b1") == (row.series.transport != "acp")]
        assert row.tokens_per_cell.value == round(sum(views.sum_tokens(c.tokens) for c in mine) / len(mine))
        assert row.wall_ms.value == round(sum(c.wall_ms.value for c in mine) / len(mine))
        assert row.requests_per_cell.value == cost_compare._dec(Decimal(sum(c.calls_per_cell.value for c in mine)) / len(mine))
    # every number in a table cell is one of the build's measures (or a count), formatted as render formats it
    page = cost_compare.render(cc)
    allowed = {cost_compare._fmt(m) for m in _measures(cc) if m.value is not None} | {f"{r.cells:,}" for r in cc.combos}
    allowed |= {f"{n:,}" for c in cc.context for n in (len(c.median), *c.median, *c.high)}
    table_numbers = re.findall(r'<td class="num">([0-9][0-9,.]*)</td>', page)
    assert table_numbers and set(table_numbers) <= allowed, set(table_numbers) - allowed
    assert all(c.extraction_id is not None for c in cells)


def test_a_series_mean_covers_the_cells_that_record_the_measure_valid_or_not(fixture_runs):
    """The stated rule (Leader ruling, R-DERIV DR option a): a cell that does not record a measure is left out of
    the series mean, never counted as 0; an invalid cell that records it stays in."""
    _, _, (v1, _) = fixture_runs
    a, b = v1.cells
    want = views.sum_tokens(a.tokens)
    assert want  # non-zero, so a counted 0 would move the mean
    v1.cells = [a, dataclasses.replace(b, tokens=None, tokens_reason="no usage record")]
    row = cost_compare.build([v1]).combos[0]
    assert row.tokens_per_cell == views.Measure(want)  # over a alone, never (want + 0) / 2
    v1.cells = [a, dataclasses.replace(b, validity="invalid", validity_code="HB-VAL-001")]
    assert cost_compare.build([v1]).combos[0].tokens_per_cell == views.Measure(
        round((want + views.sum_tokens(b.tokens)) / 2))


def test_a_cell_with_no_prompt_part_rows_and_no_reason_is_not_recorded_never_zero(fixture_runs):
    """A pass that wrote the stream but holds no row for a cell, and no reader reason, reads NO_ROWS: the instruction
    files and every part kind are not recorded for that cell, never a plausible 0."""
    _, _, (v1, _) = fixture_runs
    done = next(e for e in v1.facts["events"] if e.get("kind") == "grading.completed" and e["grading_id"] == v1.grading_id)
    done["streams_not_recorded"] = {}
    a, b = v1.cells
    v1.facts["prompt_parts"] = [{"cell_id": a.cell_id, "extraction_id": a.extraction_id, "native_ordinal": 0,
                                 "part": "system", "chars": 40}]
    p = cost_compare.build([v1]).prompt_composition[0]
    assert p.chars_by_part == {"system": views.Measure(40)}  # b's parts are not read: left out of the mean, not a 0
    v1.cells = [b]
    p = cost_compare.build([v1]).prompt_composition[0]
    assert p.instruction_files == views.Measure(None, cost_compare.NO_ROWS) and p.chars_by_part == {}


def test_an_excerpt_shaped_like_an_email_or_uuid_is_dropped_and_counted(fixture_runs):
    _, _, (v1, _) = fixture_runs
    cell = v1.cells[0]
    row = {"cell_id": cell.cell_id, "extraction_id": cell.extraction_id, "native_ordinal": 1, "source_kind": "summary",
           "chars": 20, "text": "ok"}
    v1.facts["reasoning"] = [row | {"item_ordinal": 1, "text": "plan the slug"},
                             row | {"item_ordinal": 2, "text": "mail ops@example.com"},
                             row | {"item_ordinal": 3, "text": "id 12345678-1234-1234-1234-123456789abc"}]
    r = cost_compare.build([v1]).reasoning[0]
    assert (r.excerpts, r.excerpts_dropped, r.visible_chars.value) == (("plan the slug",), 2, 60)  # 3 summary rows x 20


# --- cli_main: publish, --analysis -------------------------------------------------------------------------------

def test_bench_report_cost_compare_writes_the_page_through_publish(fixture_runs, tmp_path, monkeypatch):
    root, runs, _ = fixture_runs
    calls = []
    monkeypatch.setattr(publish, "publish", lambda html, out, open: calls.append((html, out, open)) or "not opened")
    out = tmp_path / "x.html"
    code = cli.main(["--root", str(root), "--runs", str(runs), "report", "--cost-compare", "b1", "b2", "--out", str(out)])
    assert code == 0 and len(calls) == 1
    html, written, opened = calls[0]
    assert written == out and opened is False and "<h1>What each coding harness costs" in html


def test_the_written_page_passes_the_publish_scan(fixture_runs, tmp_path, monkeypatch):
    root, runs, _ = fixture_runs
    monkeypatch.setenv(publish.OPERATOR_EMAIL_ENV, "operator@example.org")
    out = tmp_path / "cc.html"
    assert cost_compare.cli_main(["b1", "b2", "--runs", str(runs), "--root", str(root), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == cost_compare.render(cost_compare.build(
        [views.load(runs / "b1"), views.load(runs / "b2")]))


def test_analysis_is_checked_against_the_page_numbers_and_embedded(fixture_runs, tmp_path, monkeypatch):
    """The real shared helper (`report.analysis`, R-PACKCOST), no fake (J2-FIX item 3): a cited number in the page's
    tables is embedded under the analyst heading; a number absent from them refuses, and nothing is published."""
    root, runs, _ = fixture_runs
    pages = []
    monkeypatch.setattr(publish, "publish", lambda html, out, open: pages.append(html))
    md = tmp_path / "a.md"
    md.write_text("Each series ran 2 cells.", encoding="utf-8")
    cost_compare.cli_main(["b1", "b2", "--runs", str(runs), "--root", str(root), "--analysis", str(md)])
    (page,) = pages
    assert "<h2>Analysis (written by an analyst, not generated)</h2>" in page and "Each series ran 2 cells." in page
    assert page.index('<section id="analysis">') < page.index("</main>")
    md.write_text("Each series ran 9,731 cells.", encoding="utf-8")
    with pytest.raises(BenchError) as exc:
        cost_compare.cli_main(["b1", "b2", "--runs", str(runs), "--root", str(root), "--analysis", str(md)])
    assert exc.value.code == "HB-USR-002" and "9731" in str(exc.value) and len(pages) == 1


# --- the end-to-end golden, and its root's isolation -------------------------------------------------------------

def _page(fixture_runs) -> str:
    return cost_compare.render(cost_compare.build(fixture_runs[2]))


def test_the_end_to_end_golden_is_byte_equal_on_re_render(fixture_runs):
    page = _page(fixture_runs)
    assert page == _page(fixture_runs)
    assert page.encode("utf-8") == GOLDEN.read_bytes()


_OPENED: list[str] = []
_WATCH = {"on": False}


def _audit(event, args):
    if _WATCH["on"] and event == "open" and isinstance(args[0], str | Path):
        _OPENED.append(str(args[0]))


sys.addaudithook(_audit)


def test_the_golden_root_reads_nothing_from_the_repository_bench(tmp_path):
    repo_bench = (ROOT / "bench").resolve()
    _OPENED.clear()
    _WATCH["on"] = True
    try:
        root = make_root(tmp_path / "r")
        runs = tmp_path / "runs"
        runs.mkdir()
        vs = [views.load(_run(root, tmp_path / "t1", runs, "b1", adapter=True, timeline=False)),
              views.load(_run(root, tmp_path / "t2", runs, "b2", adapter=False, timeline=True))]
        page = cost_compare.render(cost_compare.build(vs))
    finally:
        _WATCH["on"] = False
    assert page.encode("utf-8") == GOLDEN.read_bytes()
    read = [p for p in _OPENED if Path(p).resolve().is_relative_to(repo_bench)]
    assert _OPENED and read == []
