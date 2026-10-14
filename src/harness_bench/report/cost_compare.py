"""`bench report --cost-compare` (ADR-0027): what each harness spends on the same tasks, for an external reader.

The contract only (R-CONTRACT-FACTS): the `CostCompare` dataclasses and the `build`/`render`/`cli_main` signatures.
`build(views) -> CostCompare` is pure and reads only the views and the report derivations (ADR-0026 s4);
`render(CostCompare) -> str`; `cli_main` writes the page through `report.publish`. Every per-combo row carries its
`SeriesKey`, whose `transport` is a plan fact shown beside the row's numbers (ADR-0027 s0, Ruling 120). A value a
stream does not carry is a `Measure` with its `not recorded` reason, never a 0. Tokens only: no price (Ruling 115).
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from harness_bench import views as views_mod
from harness_bench.report import context_growth, model, tool_phases
from harness_bench.report.html_builder import Html, el
from harness_bench.report.tool_phases import PHASES, TRANSPORTS
from harness_bench.views import CellView, Measure, RunView, sum_tokens

# ADR-0027 s0's TRANSPORTS are defined once, in `tool_phases`, beside `tool_phases.transport` (J2-FIX item 1).
# ADR-0027 s3: the kiviat's axes, each normalised over all series so toggling a series never rescales.
KIVIAT_AXES = ("token economy", "speed", "request economy", "tool-call economy", "clean cells", "edit orientation",
               "read orientation", "hidden checks passed")


@dataclass(frozen=True)
class SeriesKey:
    """One series is exactly one (combo, arm); `transport` is one of TRANSPORTS, from the plan."""
    combo: str
    harness: str
    model: str
    arm: str
    transport: str


@dataclass(frozen=True)
class ComboRow:
    """Sections 1-3: requested and served effort and context, and the per-cell cost measures."""
    series: SeriesKey
    cells: int
    effort_requested: str
    effort_served: Measure
    context_requested: str | int
    context_served: Measure  # the served window, shown beside every per-combo number where it differs from 1M
    tokens_per_cell: Measure
    tokens_by_bucket: Mapping[str, Measure]
    wall_ms: Measure
    requests_per_cell: Measure
    tool_calls_per_cell: Measure


@dataclass(frozen=True)
class ReasoningRow:
    """Reasoning: counts, volumes and source kinds; excerpts only with `--excerpts` (each at most 280 characters,
    at most three per harness; an email- or UUID-shaped excerpt is dropped and counted)."""
    series: SeriesKey
    tokens_per_cell: Measure
    tokens_per_request: Measure
    visible_chars: Measure
    source_kinds: tuple[str, ...]
    excerpts: tuple[str, ...]
    excerpts_dropped: int


@dataclass(frozen=True)
class ContextCurve:
    """The per-request context curve: the median cell, with the min-max band, per request index. `reason` (additive,
    R-DERIV) is why the curve is empty; render falls back to the served window's reason without it."""
    series: SeriesKey
    served_window: Measure
    median: tuple[int, ...]
    low: tuple[int, ...]
    high: tuple[int, ...]
    reason: str | None = None


@dataclass(frozen=True)
class PromptComposition:
    """Prompt composition from `prompt_parts`: characters per part kind, and the instruction files sent."""
    series: SeriesKey
    chars_by_part: Mapping[str, Measure]
    instruction_files: Measure


@dataclass(frozen=True)
class ToolPhaseRow:
    """Tool phases (explore, edit, verify, other) per cell, and the bytes the tools returned."""
    series: SeriesKey
    explore: Measure
    edit: Measure
    verify: Measure
    other: Measure
    bytes_returned: Measure


@dataclass(frozen=True)
class TimeAnatomyRow:
    """Time anatomy: native model time, the ACP-arrival estimate as its own labelled measure, tool, hook, idle."""
    series: SeriesKey
    model_ms: Measure
    model_ms_acp_estimate: Measure
    tool_ms: Measure
    hook_ms: Measure
    idle_ms: Measure


@dataclass(frozen=True)
class DriftRow:
    """Drift three ways plus attention drift, with the out-of-scope paths listed."""
    series: SeriesKey
    machine_lines: Measure
    task_implied_lines: Measure
    discretionary_lines: Measure
    attention_drift: Measure
    out_of_scope_paths: tuple[str, ...]


@dataclass(frozen=True)
class KiviatSeries:
    """One kiviat series: axis (KIVIAT_AXES) -> its value normalised over all series; None = not recorded, with the
    axis's reason in `reasons` (additive, R-REPORT-R seam 1; render shows a generic text where none is given)."""
    series: SeriesKey
    axes: Mapping[str, str | None]  # decimal strings, as the ledger writes non-integers
    reasons: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CostCompare:
    runs: tuple[str, ...]
    catalog_version: str | None
    excerpts: bool  # ADR-0027 s0: off by default on this external page
    combos: tuple[ComboRow, ...]
    reasoning: tuple[ReasoningRow, ...]
    context: tuple[ContextCurve, ...]
    prompt_composition: tuple[PromptComposition, ...]
    tool_phases: tuple[ToolPhaseRow, ...]
    time_anatomy: tuple[TimeAnatomyRow, ...]
    drift: tuple[DriftRow, ...]
    kiviat: tuple[KiviatSeries, ...]


# --- build (R-DERIV) -----------------------------------------------------------------------------------------------

DRIFT_METRICS = ("drift_machine_lines", "drift_task_implied_lines", "scope_creep", "attention_drift")
HIDDEN_CHECKS = "pass_at_1"  # the hidden tests' verdict (the correctness grader)
# A built reader writes rows whenever it read the record (an `omitted` reasoning row per request at least), so a cell
# with none and no recorded reason was not read by this pass's reader: not recorded, never a plausible 0.
NO_ROWS = "no rows for this cell; a reader that reads none is not told apart from none"
VISIBLE_KINDS = ("text", "summary")  # reasoning source kinds that carry visible text (ADR-0026 s1)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
_Q = Decimal("0.0001")


def _mean(ms: Sequence[Measure], whole: bool = False) -> Measure:
    """The mean over the cells that record it (an int for tokens and ms when `whole`, else 4 places), or NOT_RECORDED
    with the first cell's reason when none does.

    The rule (Leader ruling on R-DERIV's decision request, option a): a series mean covers every cell of the series
    that records the measure, valid or not; a cell that does not record it is left out, never counted as 0, and an
    invalid cell is not filtered out (validity is its own axis, `clean cells`)."""
    values = [Decimal(m.value) for m in ms if m.value is not None]
    if not values:
        return Measure(None, next((m.reason for m in ms if m.reason), "no cell"))
    mean = sum(values) / len(values)
    return Measure(int(mean.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))) if whole else Measure(_dec(mean))


def _dec(d: Decimal) -> int | Decimal:
    return int(d) if d == d.to_integral_value() else d.quantize(_Q, rounding=ROUND_HALF_EVEN)


@dataclass
class _Cell:
    """One cell's per-cell measures, each a Measure (a value or its reason)."""
    view: RunView
    cell: CellView
    m: dict[str, Measure]
    buckets: dict[str, Measure]
    parts: dict[str, Measure]
    kinds: tuple[str, ...]
    excerpts: tuple[str, ...]
    dropped: int
    series: context_growth.RequestSeries
    paths: tuple[str, ...]


def _served_value(view: RunView, cell: CellView, name: str) -> Measure:
    reason = views_mod.stream_reason(view, "served", cell)
    if reason is not None:
        return Measure(None, reason)
    values = sorted({str(r["value"]) for r in views_mod.cell_rows(view, "served", cell) or []
                     if r.get("field") == name and r.get("value") is not None and r.get("not_recorded") is None})
    return Measure(", ".join(values)) if values else Measure(None, f"no source records the served {name}")


def _outside_paths(view: RunView, cell: CellView) -> tuple[str, ...]:
    """drift.log's outside lines (`grade/drift.py`: `status, path, zone, +a -d[, class]`), as `path (class)`."""
    evidence = cell.evidence.get("scope_creep")
    path = view.run_dir / evidence if evidence and view.run_dir is not None else None
    if path is None or not path.is_file():
        return ()
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 4 and parts[2] == "outside":
            out.append(f"{parts[1]} ({parts[4]})" if len(parts) > 4 else parts[1])
    return tuple(out)


def _cell(view: RunView, cell: CellView) -> _Cell:
    graded = cell.extraction_id is not None
    calls = views_mod.cell_rows(view, "model_calls", cell) or []
    tools = views_mod.cell_rows(view, "tool_calls", cell)
    total = sum_tokens(cell.tokens)
    m: dict[str, Measure] = {
        "tokens": Measure(total) if total is not None else Measure(None, cell.tokens_reason or "not recorded"),
        "wall": cell.wall_ms, "requests": cell.calls_per_cell,
        "tool_calls": Measure(len(tools)) if tools is not None else Measure(None, "not graded"),
        "effort": _served_value(view, cell, "effort"),
        "window": context_growth.served_window(view, cell),
    }
    sums: dict[str, int] = {}
    for per_model in (cell.tokens or {}).values():
        for b, v in per_model.items():
            sums[b] = sums.get(b, 0) + v
    buckets = {b: Measure(v) for b, v in sums.items()}
    # reasoning: tokens from the usage report (model_calls.reasoning); visible text from the `reasoning` stream
    if not graded:
        m["reasoning"] = m["reasoning_per_request"] = Measure(None, "not graded")
    elif not calls or any(r.get("reasoning") is None for r in calls):
        m["reasoning"] = m["reasoning_per_request"] = Measure(None, "the usage report gives no reasoning tokens")
    else:
        tokens = sum(r["reasoning"] for r in calls)
        requests = sum(r.get("requests", 1) for r in calls)
        m["reasoning"] = Measure(tokens)
        m["reasoning_per_request"] = Measure(_dec(Decimal(tokens) / requests)) if requests else Measure(None, "no request")
    items = views_mod.cell_rows(view, "reasoning", cell) or []
    r_reason = views_mod.stream_reason(view, "reasoning", cell) or (None if items else NO_ROWS)
    m["visible"] = Measure(None, r_reason) if r_reason else Measure(
        sum(r.get("chars") or 0 for r in items if r.get("source_kind") in VISIBLE_KINDS))
    texts = [r["text"] for r in sorted(items, key=lambda r: (r["native_ordinal"], r["item_ordinal"]))
             if isinstance(r.get("text"), str) and r["text"].strip()]
    kept = [t[:EXCERPT_CHARS] for t in texts if not (_EMAIL.search(t) or _UUID.search(t))]
    # prompt composition
    rows = views_mod.cell_rows(view, "prompt_parts", cell) or []
    p_reason = views_mod.stream_reason(view, "prompt_parts", cell) or (None if rows else NO_ROWS)
    chars: dict[str, int] = {}
    for r in rows:
        chars[r["part"]] = chars.get(r["part"], 0) + (r.get("chars") or 0)
    parts = {p: Measure(v) for p, v in chars.items()}
    m["instruction_files"] = Measure(None, p_reason) if p_reason else Measure(
        sum(1 for r in rows if r.get("part") == "instruction_file"))
    # tool phases, bytes and re-reads, from the native record's ToolInput sequence
    session = tool_phases.main_session(view, cell)
    trace = tool_phases.cell_trace(view.run_dir, view, cell, session) if view.run_dir is not None else None
    if trace is None:
        why = (f"no tool-input reader for {cell.harness}" if cell.harness not in tool_phases.TRACE_READERS
               else "no native record in the archive")
        for p in (*PHASES, "bytes", "rereads"):
            m[p] = Measure(None, why)
    else:
        m.update({p: Measure(n) for p, n in tool_phases.phase_counts(trace.calls).items()})
        m["bytes"] = tool_phases.bytes_returned(trace.calls)
        m["rereads"] = Measure(tool_phases.rereads(trace.calls))
    anatomy = views_mod.time_anatomy(view, cell)
    m.update({"model_ms": anatomy.model_ms, "acp_ms": anatomy.model_ms_acp_estimate, "tool_ms": anatomy.tool_ms,
              "hook_ms": anatomy.hook_ms, "idle_ms": anatomy.idle_ms})
    for metric in (*DRIFT_METRICS, HIDDEN_CHECKS):
        m[metric] = cell.scores.get(metric, Measure(None, "not graded" if not graded else f"{metric} not in this pass"))
    m["clean"] = Measure(1 if cell.validity == "valid" else 0)
    return _Cell(view, cell, m, buckets, parts, tuple(sorted({r["source_kind"] for r in items})),
                 tuple(kept[:EXCERPT_CAP]), len(texts) - len(kept),
                 context_growth.request_series(view, cell.cell_id), _outside_paths(view, cell))


def _key(view: RunView, cell: CellView) -> SeriesKey:
    return SeriesKey(cell.combo, cell.harness, cell.model, cell.arm, tool_phases.transport(view.plan, cell.harness, cell.combo))


def _part(c: _Cell, part: str) -> Measure:
    """One cell's characters of one part kind: its recorded sum; a measured 0 when the cell's parts were read and
    hold none of that kind; NOT_RECORDED with the cell's reason when its parts were not read (never a plausible 0)."""
    if part in c.parts:
        return c.parts[part]
    reason = c.m["instruction_files"].reason
    return Measure(None, reason) if c.m["instruction_files"].value is None else Measure(0)


def _curve(key: SeriesKey, cells: Sequence[_Cell], window: Measure) -> ContextCurve:
    """Per request index every cell reached: the median cell's context and the min-max band (`_series`'s rule)."""
    series = [c.series.inputs for c in cells if c.series.reason is None and c.series.inputs]
    if not series:
        reason = next((c.series.reason for c in cells if c.series.reason), context_growth.NO_REQUESTS)
        return ContextCurve(key, window, (), (), (), reason)
    n = min(len(s) for s in series)
    at = [[s[i] for s in series] for i in range(n)]
    return ContextCurve(key, window, tuple(round(statistics.median(v)) for v in at), tuple(min(v) for v in at),
                        tuple(max(v) for v in at))


def _kiviat_series(keys: Sequence[SeriesKey], rows: Mapping[SeriesKey, Mapping[str, Measure]]) -> tuple[KiviatSeries, ...]:
    """ADR-0027 s3's axes, raw (render normalises each over all series): an economy is the best series' mean over
    this series' (lower is better, so the best is 1); the rest are shares in [0, 1]."""
    def best(name: str) -> Decimal | None:
        values = [Decimal(rows[k][name].value) for k in keys if rows[k][name].value is not None]
        return min(values) if values else None

    lows = {n: best(n) for n in ("tokens", "wall", "requests", "tool_calls")}
    out = []
    for k in keys:
        r = rows[k]
        got: list[tuple[str, Decimal | None, str | None]] = []
        for axis, name in (("token economy", "tokens"), ("speed", "wall"), ("request economy", "requests"),
                           ("tool-call economy", "tool_calls")):
            v = r[name]
            got.append((axis, None if v.value is None else Decimal(1) if Decimal(v.value) == 0 else lows[name] / Decimal(v.value),
                        v.reason))
        got.append(("clean cells", None if r["clean"].value is None else Decimal(r["clean"].value), r["clean"].reason))
        phases = [r[p] for p in PHASES]
        total = sum(Decimal(p.value) for p in phases) if all(p.value is not None for p in phases) else None
        why = next((p.reason for p in phases if p.value is None), None) or "no tool calls"
        got.append(("edit orientation", Decimal(r["edit"].value) / total if total else None, why))
        got.append(("read orientation", Decimal(r["explore"].value) / total if total else None, why))
        hidden = r[HIDDEN_CHECKS]
        got.append(("hidden checks passed", None if hidden.value is None else Decimal(hidden.value), hidden.reason))
        axes = {a: None if v is None else str(v.quantize(_Q, rounding=ROUND_HALF_EVEN)) for a, v, _ in got}
        out.append(KiviatSeries(k, axes, {a: why or "not recorded" for a, v, why in got if v is None}))
    return tuple(out)


def build(views: Sequence[RunView]) -> CostCompare:
    """Pure over the views (their rows and archives, ADR-0026 s4's derivations): one series per (combo, arm), each
    figure the mean per cell over the series' cells that record it (`_mean`), a NOT_RECORDED with its reason otherwise.
    Excerpts are collected (email- and UUID-shaped ones dropped and counted); the page shows them only with
    `--excerpts`."""
    grouped: dict[SeriesKey, list[_Cell]] = {}
    for view in views:
        for cell in view.cells:
            grouped.setdefault(_key(view, cell), []).append(_cell(view, cell))
    keys = list(grouped)
    means: dict[SeriesKey, dict[str, Measure]] = {}
    combos, reasoning, context, prompts, phases, anatomy, drift = [], [], [], [], [], [], []
    for k in keys:
        cells = grouped[k]
        names = list(dict.fromkeys(n for c in cells for n in c.m))
        whole = {"tokens", "wall", "model_ms", "acp_ms", "tool_ms", "hook_ms", "idle_ms", "bytes", "reasoning",
                 "visible", "drift_machine_lines", "drift_task_implied_lines", "scope_creep"}
        mean = {n: _mean([c.m[n] for c in cells], whole=n in whole) for n in names if n not in ("effort", "window")}
        mean["effort"] = _same([c.m["effort"] for c in cells])
        mean["window"] = _same([c.m["window"] for c in cells])
        means[k] = mean
        bucket_names = list(dict.fromkeys(b for c in cells for b in c.buckets))
        combos.append(ComboRow(k, len(cells), str(_plan_cell(cells[0]).get("effort", "default")), mean["effort"],
                               _plan_cell(cells[0]).get("context", "default"), mean["window"], mean["tokens"],
                               {b: _mean([c.buckets.get(b, Measure(0) if c.cell.tokens else Measure(
                                   None, c.cell.tokens_reason)) for c in cells], whole=True) for b in bucket_names},
                               mean["wall"], mean["requests"], mean["tool_calls"]))
        reasoning.append(ReasoningRow(k, mean["reasoning"], mean["reasoning_per_request"], mean["visible"],
                                      tuple(sorted({s for c in cells for s in c.kinds})),
                                      tuple(e for c in cells for e in c.excerpts)[:EXCERPT_CAP],
                                      sum(c.dropped for c in cells)))
        context.append(_curve(k, cells, mean["window"]))
        part_names = list(dict.fromkeys(p for c in cells for p in c.parts))
        prompts.append(PromptComposition(k, {p: _mean([_part(c, p) for c in cells], whole=True)
                                             for p in part_names}, mean["instruction_files"]))
        phases.append(ToolPhaseRow(k, mean["explore"], mean["edit"], mean["verify"], mean["other"], mean["bytes"]))
        anatomy.append(TimeAnatomyRow(k, mean["model_ms"], mean["acp_ms"], mean["tool_ms"], mean["hook_ms"],
                                      mean["idle_ms"]))
        drift.append(DriftRow(k, mean["drift_machine_lines"], mean["drift_task_implied_lines"], mean["scope_creep"],
                              mean["attention_drift"], tuple(dict.fromkeys(p for c in cells for p in c.paths))))
    catalogs = sorted({v.catalog_version for v in views if v.catalog_version})
    return CostCompare(tuple(v.run_id for v in views), ", ".join(catalogs) or None, False, tuple(combos),
                       tuple(reasoning), tuple(context), tuple(prompts), tuple(phases), tuple(anatomy), tuple(drift),
                       _kiviat_series(keys, means))


def _plan_cell(c: _Cell) -> dict:
    return next((p for p in c.view.plan.get("cells", ()) if p.get("cell_id") == c.cell.cell_id), {})


def _same(ms: Sequence[Measure]) -> Measure:
    """A setting over the series' cells: the one value they record, the values joined when they differ, or the
    first reason when none records it."""
    values = list(dict.fromkeys(str(m.value) for m in ms if m.value is not None))
    if not values:
        return Measure(None, next((m.reason for m in ms if m.reason), "not recorded"))
    return Measure(int(values[0]) if len(values) == 1 and values[0].isdigit() else ", ".join(values))


# --- render (R-REPORT-R) -------------------------------------------------------------------------------------------

TITLE = "What each coding harness costs in tokens and time"
EQUAL_DEPTH = "Note: equal setting is not proven equal depth."
EXCERPT_CAP = 3  # ADR-0027 s3: at most three short excerpts per harness
EXCERPT_CHARS = 280  # ADR-0027 s3: each at most 280 characters
FULL_WINDOW = "1000000"  # the served window is shown beside a combo's numbers only where it differs from 1M
_R = 150  # kiviat radius, in viewBox units
_C = 200  # kiviat centre

STYLE = """
.series-head{min-width:14em}
.series-head [data-part]{display:block}
.series-head [data-part="transport"],.series-head [data-part="window"]{font-weight:400;font-size:var(--fs-small);color:var(--ink-2)}
.excerpt{margin:var(--s1) 0;padding:var(--s1) var(--s3);border-left:var(--focus-w) solid var(--rule-strong);background:var(--panel)}
.curve .band{fill:var(--rule);stroke:none}
.curve polyline{fill:none;stroke-width:2}
.kiviat .ring{fill:none;stroke:var(--rule);stroke-width:1}
.kiviat polygon.series{fill:none;stroke-width:2}
.kiviat svg{max-width:100%;height:auto}
.kiviat polygon.series.off{display:none}
.kiviat fieldset{border:var(--rule-w) solid var(--rule);border-radius:var(--radius);display:flex;flex-wrap:wrap;gap:var(--s1) var(--s3)}
.kiviat input[type="checkbox"]{width:var(--target);height:var(--target);margin:0 var(--s1) 0 0;vertical-align:middle}
.kiviat label{display:inline-flex;align-items:center;min-height:var(--target)}
"""

# The kiviat's one behaviour: a checkbox hides or shows its own polygon. Every coordinate is computed in Python over
# all series, so toggling never rescales (ADR-0027 s3).
SCRIPT = """document.querySelectorAll('#kiviat input[data-series]').forEach(function (box) {
  box.addEventListener('change', function () {
    var poly = document.querySelector('polygon[data-kiviat-series="' + box.dataset.series + '"]');
    if (poly) { poly.classList.toggle('off', !box.checked); }
  });
});
"""


def _fmt(m: Measure) -> str:
    """A Measure as text: `not recorded (<reason>)` for None, never 0 or blank; a reader's reason that already reads
    `not recorded: ...` is shown as it is (never `not recorded (not recorded: ...)`)."""
    if m.value is None:
        if m.reason and m.reason.startswith("not recorded"):
            return m.reason
        return f"not recorded ({m.reason})" if m.reason else "not recorded"
    if isinstance(m.value, int):
        return f"{m.value:,}"
    return str(m.value)


def _sid(s: SeriesKey) -> str:
    return f"{s.combo}/{s.arm}"


def _label(s: SeriesKey) -> str:
    return f"{s.harness} · {s.model} · {s.arm}"


class _Page:
    """Shared per-render state: the served window per series and the table-caption counter."""

    def __init__(self, cc: CostCompare):
        self.windows = {_sid(r.series): r.context_served for r in cc.combos}
        self.combo_index: dict[str, int] = {}
        for s in (k.series for k in cc.kiviat) if cc.kiviat else (r.series for r in cc.combos):
            self.combo_index.setdefault(s.combo, len(self.combo_index) % 8 + 1)

    def head(self, s: SeriesKey) -> Html:
        """The row header every per-combo row carries: the series, its transport (Ruling 120), and the served
        window where it differs from 1M (ADR-0027 s3)."""
        parts = [el("span", {"data-part": "series"}, _label(s)),
                 el("span", {"data-part": "transport"}, f"transport: {s.transport}")]
        window = self.windows.get(_sid(s))
        if window is not None and window.value is not None and str(window.value) != FULL_WINDOW:
            parts.append(el("span", {"data-part": "window"}, f"served window {_fmt(window)}"))
        return el("th", {"scope": "row", "class": "series-head"}, *parts)

    def table(self, cap_id: str, caption: str, headers: Sequence[str],
              rows: Sequence[tuple[SeriesKey, Sequence[str | Html]]]) -> Html:
        head = el("tr", None, el("th", {"scope": "col"}, "Series"),
                  *(el("th", {"scope": "col"}, h) for h in headers))
        body = [el("tr", {"data-series": _sid(s)}, self.head(s),
                   *(el("td", None if isinstance(c, Html) else {"class": "num"}, c) for c in cells))
                for s, cells in rows]
        table = el("table", None, el("caption", {"id": cap_id}, caption), el("thead", None, head),
                   el("tbody", None, *body))
        return el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": cap_id}, table)


def _section(sid: str, title: str, *children: str) -> model.Section:
    return model.Section(sid, title, el("section", {"id": sid}, el("h2", None, title), *children))


def _keys(maps: Sequence[Mapping[str, Measure]]) -> list[str]:
    seen: dict[str, None] = {}
    for m in maps:
        seen.update(dict.fromkeys(m))
    return list(seen)


def _mapped(rows: Sequence[Mapping[str, Measure]], keys: Sequence[str], missing: str) -> list[list[str]]:
    return [[_fmt(r.get(k, Measure(None, missing))) for k in keys] for r in rows]


def _header(cc: CostCompare) -> model.Section:
    excerpts = "on (--excerpts)" if cc.excerpts else "off (the default; --excerpts turns them on)"
    facts = [("Runs", ", ".join(cc.runs) or "not recorded"),
             ("Catalog version", cc.catalog_version or "not recorded (no catalog version in the views)"),
             ("Reasoning excerpts", excerpts),
             ("Transports", "; ".join(TRANSPORTS))]
    dl = el("dl", None, *(x for k, v in facts for x in (el("dt", None, k), el("dd", None, v))))
    body = el("section", {"id": "header"}, el("h1", None, TITLE),
              el("p", {"class": "muted"}, "Tokens are the only cost unit on this page. Every number comes from the "
                 "run records; a value a stream does not carry reads not recorded, with its reason."), dl)
    return model.Section("header", TITLE, body)


def _benchmarked(cc: CostCompare, pg: _Page) -> model.Section:
    total = sum(r.cells for r in cc.combos)
    return _section("benchmarked", "What was benchmarked",
                    el("p", None, f"{len(cc.combos)} series (combo and arm) over {len(cc.runs)} run(s), "
                       f"{total:,} cells in all."),
                    pg.table("benchmarked-caption", "Cells per series", ["Cells"],
                             [(r.series, [f"{r.cells:,}"]) for r in cc.combos]))


def _harnesses(cc: CostCompare, pg: _Page) -> model.Section:
    rows = [(r.series, [r.effort_requested, _fmt(r.effort_served), str(r.context_requested), _fmt(r.context_served)])
            for r in cc.combos]
    return _section("harnesses", "Harnesses and models",
                    pg.table("harnesses-caption", "Requested and served effort and context per series",
                             ["Effort requested", "Effort served", "Context requested", "Context served"], rows))


def _cost(cc: CostCompare, pg: _Page) -> model.Section:
    buckets = _keys([r.tokens_by_bucket for r in cc.combos])
    headers = ["Tokens per cell", *(f"Tokens per cell: {b}" for b in buckets)] if buckets else \
        ["Tokens per cell", "Tokens per cell by type"]
    by_bucket = _mapped([r.tokens_by_bucket for r in cc.combos], buckets, "bucket absent") if buckets else \
        [["not recorded (no token types in the record)"] for _ in cc.combos]
    rows = [(r.series, [_fmt(r.tokens_per_cell), *b, _fmt(r.wall_ms), _fmt(r.requests_per_cell),
                        _fmt(r.tool_calls_per_cell)]) for r, b in zip(cc.combos, by_bucket, strict=True)]
    return _section("cost", "Cost per harness and model",
                    pg.table("cost-caption", "Tokens, wall clock, requests and tool calls per cell (means)",
                             [*headers, "Wall clock per cell (ms)", "Requests per cell", "Tool calls per cell"],
                             rows))


def _ordered(rows: Sequence[ComboRow], value: Callable[[ComboRow], Measure]) -> Html:
    recorded = sorted((r for r in rows if value(r).value is not None), key=lambda r: Decimal(value(r).value))
    absent = [r for r in rows if value(r).value is None]
    items = [el("li", None, f"{_label(r.series)} ({r.series.transport}): {_fmt(value(r))}") for r in recorded]
    items += [el("li", None, f"{_label(r.series)} ({r.series.transport}): {_fmt(value(r))}") for r in absent]
    return el("ol", None, *items)


def _observations(cc: CostCompare) -> model.Section:
    children: list[str] = [el("p", {"class": "muted"}, "Each list orders the series of one arm by a section-3 "
                              "figure, lowest first. The page adds no classification of its own.")]
    for arm in dict.fromkeys(r.series.arm for r in cc.combos):
        rows = [r for r in cc.combos if r.series.arm == arm]
        children += [el("h3", None, f"Arm {arm}: tokens per cell"), _ordered(rows, lambda r: r.tokens_per_cell),
                     el("h3", None, f"Arm {arm}: wall clock per cell (ms)"), _ordered(rows, lambda r: r.wall_ms)]
    return _section("observations", "Observations", *children)


def _same_model(cc: CostCompare, pg: _Page) -> model.Section:
    files = {_sid(p.series): p.instruction_files for p in cc.prompt_composition}
    harnesses: dict[str, dict[str, None]] = {}
    for r in cc.combos:
        harnesses.setdefault(r.series.model, {})[r.series.harness] = None
    shared = [m for m, hs in harnesses.items() if len(hs) > 1]
    children: list[str] = []
    for i, m in enumerate(shared, start=1):
        rows = [(r.series, [_fmt(r.effort_served), _fmt(r.requests_per_cell), _fmt(r.tool_calls_per_cell),
                            _fmt(r.tokens_per_cell),
                            _fmt(files.get(_sid(r.series), Measure(None, "no prompt composition")))])
                for r in cc.combos if r.series.model == m]
        children.append(pg.table(f"same-model-{i}-caption", f"{m}: {', '.join(harnesses[m])}",
                                 ["Effort served", "Requests per cell", "Tool calls per cell", "Tokens per cell",
                                  "Instruction files sent"], rows))
    if not shared:
        children.append(el("p", None, "No model ran in more than one harness in these runs."))
    return _section("same-model", "Why same-model harnesses differ", *children)


def _excerpts(cc: CostCompare, scan: Callable[[str], list[str]]) -> list[str]:
    """ADR-0027 s0, s6; seam S-1: an excerpt the injected scan flags is dropped and counted, never redacted."""
    if not cc.excerpts:
        return [el("p", None, "Reasoning excerpts are off on this page; --excerpts turns them on. This external "
                   "page carries reasoning counts, volumes and source kinds, not reasoning text.")]
    out: list[str] = []
    for harness in dict.fromkeys(r.series.harness for r in cc.reasoning):
        rows = [r for r in cc.reasoning if r.series.harness == harness]
        dropped = sum(r.excerpts_dropped for r in rows)
        kept: list[str] = []
        for text in (e for r in rows for e in r.excerpts):
            if scan(text):
                dropped += 1
            elif len(kept) < EXCERPT_CAP:
                kept.append(text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1] + "…")
        out += [el("h3", None, f"Excerpts: {harness}"),
                el("p", {"data-dropped": harness, "data-count": str(dropped)},
                   f"Dropped by the egress scan (email or UUID shape): {dropped:,}")]
        out += [el("blockquote", {"class": "excerpt", "data-excerpt": harness}, t) for t in kept] or \
            [el("p", None, "No excerpt recorded.")]
    return out


def _reasoning(cc: CostCompare, pg: _Page, scan: Callable[[str], list[str]]) -> model.Section:
    rows = [(r.series, [_fmt(r.tokens_per_cell), _fmt(r.tokens_per_request), _fmt(r.visible_chars),
                        ", ".join(r.source_kinds) or _fmt(Measure(None, r.tokens_per_cell.reason
                                                                  or "no source kind"))])
            for r in cc.reasoning]
    return _section("reasoning", "Reasoning", el("p", None, EQUAL_DEPTH),
                    pg.table("reasoning-caption", "Reasoning tokens, visible characters and source kinds",
                             ["Reasoning tokens per cell", "Reasoning tokens per request", "Visible characters",
                              "Source kinds"], rows),
                    *_excerpts(cc, scan))


def _curve_svg(c: ContextCurve, top: int, combo: int) -> Html:
    w, h = 160, 40
    n = len(c.median)

    def pt(i: int, v: int) -> str:
        x = w / 2 if n == 1 else w * i / (n - 1)
        return f"{x:.2f},{h - h * v / top:.2f}"

    band = " ".join([pt(i, v) for i, v in enumerate(c.high)] + [pt(i, v) for i, v in reversed(list(enumerate(c.low)))])
    label = (f"{_label(c.series)}: {n} requests, median context {c.median[0]:,} at the first and "
             f"{c.median[-1]:,} at the last, band top {max(c.high):,}")
    return el("svg", {"class": "curve", "viewBox": f"0 0 {w} {h}", "width": str(w), "height": str(h), "role": "img",
                      "aria-label": label},
              el("polygon", {"class": "band", "points": band}),
              el("polyline", {"class": f"mk-c{combo}", "points": " ".join(pt(i, v) for i, v in enumerate(c.median))}))


def _context(cc: CostCompare, pg: _Page) -> model.Section:
    top = max((v for c in cc.context for v in c.high), default=0) or 1
    rows = []
    for c in cc.context:
        if not c.median:
            na = _fmt(Measure(None, c.reason or c.served_window.reason or "no requests recorded"))
            rows.append((c.series, [_fmt(c.served_window), na, na, na, na, na]))
            continue
        rows.append((c.series, [_fmt(c.served_window), f"{len(c.median):,}", f"{c.median[0]:,}", f"{c.median[-1]:,}",
                                f"{max(c.high):,}", _curve_svg(c, top, pg.combo_index.get(c.series.combo, 1))]))
    return _section("context-curve", "Context per request",
                    el("p", {"class": "muted"}, "The median cell's context per request, with the min-max band over "
                       "cells; every curve shares one vertical scale."),
                    pg.table("context-caption", "Per-request context curve per series (tokens)",
                             ["Served window", "Requests", "Median context, first request",
                              "Median context, last request", "Band top", "Curve"], rows))


def _prompt(cc: CostCompare, pg: _Page) -> model.Section:
    parts = _keys([p.chars_by_part for p in cc.prompt_composition])
    if parts:
        cells = _mapped([p.chars_by_part for p in cc.prompt_composition], parts, "part absent")
        headers = [f"Characters: {p}" for p in parts]
    else:
        cells = [[_fmt(Measure(None, p.instruction_files.reason or "no prompt parts recorded"))]
                 for p in cc.prompt_composition]
        headers = ["Characters by part"]
    rows = [(p.series, [*c, _fmt(p.instruction_files)]) for p, c in zip(cc.prompt_composition, cells, strict=True)]
    return _section("prompt-composition", "Prompt composition",
                    pg.table("prompt-caption", "What each series sends before the task, from prompt_parts",
                             [*headers, "Instruction files sent"], rows))


def _phases(cc: CostCompare, pg: _Page) -> model.Section:
    rows = [(t.series, [_fmt(t.explore), _fmt(t.edit), _fmt(t.verify), _fmt(t.other), _fmt(t.bytes_returned)])
            for t in cc.tool_phases]
    return _section("tool-phases", "Tool phases",
                    pg.table("phases-caption", "Tool calls per cell by phase, and the bytes the tools returned",
                             ["Explore", "Edit", "Verify", "Other", "Bytes returned per cell"], rows))


def _anatomy(cc: CostCompare, pg: _Page) -> model.Section:
    rows = [(t.series, [_fmt(t.model_ms), _fmt(t.model_ms_acp_estimate), _fmt(t.tool_ms), _fmt(t.hook_ms),
                        _fmt(t.idle_ms)]) for t in cc.time_anatomy]
    return _section("time-anatomy", "Time anatomy",
                    pg.table("anatomy-caption", "Where each cell's time went (ms per cell)",
                             ["Model", "Model, ACP-arrival estimate", "Tool", "Hook", "Idle"], rows))


def _drift(cc: CostCompare, pg: _Page) -> model.Section:
    def paths(d: DriftRow) -> str | Html:
        if d.out_of_scope_paths:
            return el("ul", None, *(el("li", None, el("code", None, p)) for p in d.out_of_scope_paths))
        return _fmt(d.discretionary_lines) if d.discretionary_lines.value is None else "none"

    rows = [(d.series, [_fmt(d.machine_lines), _fmt(d.task_implied_lines), _fmt(d.discretionary_lines),
                        _fmt(d.attention_drift), paths(d)]) for d in cc.drift]
    return _section("drift", "Drift",
                    pg.table("drift-caption", "Changed lines three ways, attention drift, and the out-of-scope paths",
                             ["Machine lines", "Task-implied lines", "Discretionary lines", "Attention drift",
                              "Out-of-scope paths"], rows))


def _kiviat(cc: CostCompare, pg: _Page) -> model.Section:
    """ADR-0027 s3: one checkbox per series; each axis normalised over all series, so toggling never rescales."""
    maxes: dict[str, Decimal | None] = {}
    for a in KIVIAT_AXES:
        values = [Decimal(k.axes[a]) for k in cc.kiviat if k.axes.get(a) is not None]
        maxes[a] = max(values) if values else None

    def norm(k: KiviatSeries, a: str) -> Decimal | None:
        raw, top = k.axes.get(a), maxes[a]
        if raw is None or top is None:
            return None
        return Decimal(raw) / top if top else Decimal(0)

    def at(j: int, r: float) -> tuple[float, float]:
        theta = 2 * math.pi * j / len(KIVIAT_AXES)
        return _C + _R * r * math.sin(theta), _C - _R * r * math.cos(theta)

    def pts(rs: Sequence[float]) -> str:
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in (at(j, r) for j, r in enumerate(rs)))

    marks: list[str] = [el("polygon", {"class": "ring", "points": pts([f] * len(KIVIAT_AXES))})
                        for f in (0.25, 0.5, 0.75, 1.0)]
    for j, a in enumerate(KIVIAT_AXES):
        x, y = at(j, 1.0)
        marks.append(el("line", {"class": "axis", "x1": str(_C), "y1": str(_C), "x2": f"{x:.2f}", "y2": f"{y:.2f}",
                                 "data-axis": a, "data-max": "not recorded" if maxes[a] is None else str(maxes[a])}))
        lx, ly = at(j, 1.12)
        anchor = "middle" if abs(lx - _C) < 1 else ("start" if lx > _C else "end")
        marks.append(el("text", {"x": f"{lx:.2f}", "y": f"{ly:.2f}", "text-anchor": anchor}, a))
    arms = list(dict.fromkeys(k.series.arm for k in cc.kiviat))
    boxes: list[str] = []
    for i, k in enumerate(cc.kiviat):
        ns = [norm(k, a) for a in KIVIAT_AXES]
        dashed = bool(arms) and k.series.arm != arms[0]
        cls = f"series mk-c{pg.combo_index.get(k.series.combo, 1)}" + (" dash" if dashed else "")
        marks.append(el("polygon", {"class": cls, "points": pts([float(n or 0) for n in ns]),
                                    "data-kiviat-series": str(i),
                                    "data-norm": ",".join("na" if n is None else f"{n:.4f}" for n in ns)}))
        boxes.append(el("label", {"for": f"kv-{i}"},
                        el("input", {"type": "checkbox", "id": f"kv-{i}", "data-series": str(i), "checked": True}),
                        f"{_label(k.series)} ({'dashed' if dashed else 'solid'}; {k.series.transport})"))
    svg = el("svg", {"viewBox": "-110 -20 620 440", "width": "620", "height": "440", "role": "img",
                     "aria-labelledby": "kiviat-desc"}, *marks)

    def cell(k: KiviatSeries, a: str) -> str:
        n = norm(k, a)
        if n is None:
            return _fmt(Measure(None, k.reasons.get(a) or "no value for this axis"))
        return f"{k.axes[a]} ({n:.4f} of the max)"

    table = pg.table("kiviat-caption", "Kiviat values per series: the value, then its share of the axis maximum "
                     "over all series", list(KIVIAT_AXES), [(k.series, [cell(k, a) for a in KIVIAT_AXES])
                                                             for k in cc.kiviat])
    return _section("kiviat", "All measures at once",
                    el("p", {"id": "kiviat-desc"}, f"Kiviat of {len(cc.kiviat)} series on {len(KIVIAT_AXES)} axes. "
                       "Each axis is normalised over all series, so the outer ring is the largest value of any "
                       "series and showing or hiding a series never rescales the rest. The table below carries "
                       "every value."),
                    el("div", {"class": "kiviat"},
                       el("fieldset", None, el("legend", None, "Series shown"), *boxes), svg),
                    table)


def render(cc: CostCompare, scan: Callable[[str], list[str]] | None = None) -> str:
    """The page's HTML (ADR-0027 s0, s3, s7). `scan` is the one egress scan (seam S-1): None means
    `report.publish.scan_text`, looked up when render is called; an excerpt it flags is dropped and counted."""
    # report.html and egress import each other; importing egress first is the order that resolves the cycle.
    from harness_bench import egress  # noqa: F401
    from harness_bench.report import html as report_html

    if scan is None:
        from harness_bench.report import publish
        scan = publish.scan_text
    pg = _Page(cc)
    sections = (_header(cc), _benchmarked(cc, pg), _harnesses(cc, pg), _cost(cc, pg), _observations(cc),
                _same_model(cc, pg), _reasoning(cc, pg, scan), _context(cc, pg), _prompt(cc, pg), _phases(cc, pg),
                _anatomy(cc, pg), _drift(cc, pg), _kiviat(cc, pg))
    return model.page(model.ReportModel(run_id=", ".join(cc.runs), sections=sections),
                      style=report_html.STYLE + STYLE, script=SCRIPT)


DEFAULT_OUT = "cost-compare.html"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bench report --cost-compare")
    p.add_argument("cost_compare", nargs="+", metavar="RUN")
    p.add_argument("--out", default=None)
    p.add_argument("--analysis", default=None)
    p.add_argument("--open", action="store_true")
    p.add_argument("--excerpts", action="store_true")
    p.add_argument("--root", default=".")
    p.add_argument("--runs", default=None)
    return p


def load_views(args: argparse.Namespace) -> list[RunView]:
    """Each named run's view, from `--runs` (default `<root>/runs`), in the order named."""
    runs = Path(args.runs) if getattr(args, "runs", None) else Path(args.root) / "runs"
    return [views_mod.load(runs / run_id) for run_id in args.cost_compare]


def embed(page: str, section: str) -> str:
    """The analyst section (ADR-0029 s7, the Leader's ruling for this page) as the page's last section."""
    assert page.count("</main>") == 1
    return page.replace("</main>", f"{section}</main>")


def cli_main(argv: Sequence[str]) -> int:
    """`bench report --cost-compare RUN [RUN ...] --out PATH [--open] [--excerpts] [--analysis MD]`, written through
    `publish`. `argv` is the CLI's parsed namespace (`cli.cmd_report`), or a list of strings for a direct call. With
    `--analysis`, the analyst's Markdown is checked and rendered by `report.analysis` (R-PACKCOST's shared helper):
    every number it cites must be in the page's generated tables, or nothing is written."""
    from harness_bench.report import publish

    args = argv if isinstance(argv, argparse.Namespace) else _parser().parse_args(list(argv))
    cc = build(load_views(args))
    if getattr(args, "excerpts", False):
        cc = replace(cc, excerpts=True)
    page = render(cc)
    if args.analysis:
        # R-PACKCOST's helper, imported only when --analysis is given
        from harness_bench.report import analysis

        md = Path(args.analysis).read_text(encoding="utf-8")
        page = embed(page, analysis.check_and_render(md, analysis.table_numbers(page)))
    out = Path(args.out) if args.out else Path(args.root) / DEFAULT_OUT
    publish.publish(page, out, bool(args.open))
    return 0
