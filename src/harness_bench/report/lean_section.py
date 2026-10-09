"""The lean summary section (ADR-0023 point 9; spec `docs/specs/lean-pack-benchmark.md` Parts B and C).

The section computes no statistic. It prints the fields of one `lean.LeanSummary` (built by `lean.build`, passed in by
the caller) in the spec's order: the header, the per-harness table with the pooled row, the per-property table
(collapsed) and the limits note. Every statement is `LeanRow.statement`, printed as text; colour and the bars only
repeat what the text says (LBI-2). The bars are the campaign section's (`campaign_section._bar`): an effect mark carries
`data-interval-lo/hi` and `data-mde`, a ratio mark `data-interval-lo/hi` (LBI-3).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from harness_bench import lean
from harness_bench.report import model
from harness_bench.report.campaign_section import _bar
from harness_bench.report.html_builder import Html, el

SECTION_ID = "lean-summary"
TITLE = "Lean summary"
QUESTION = "Does the pack help each harness?"
NOT_RECORDED = "not recorded"
PLANNED_BATCHES = 2
DISAGREE = "harnesses disagree: read the per-harness rows"  # LB-5, exactly
RATIO_LABEL = "token ratio of totals (pack-on / pack-off)"  # ADR-0023 point 9, exactly
RATIO_NOTE = ("The token ratio here is total pack-on tokens over total pack-off tokens across a harness's token-complete "
              "pairs; the Pack improvement section shows the median of per-pair ratios instead, so the two can differ.")
CAVEAT_TWO_BATCHES = ("Repeats of a task are correlated, so the true per-harness MDE lies between 0.31 (20 independent "
                      "pairs) and 0.42 (10 tasks).")
CAVEAT_ONE_BATCH = "Repeats of a task are correlated, so each row's true MDE is larger than the MDE shown."
INFRA_LIMIT = Decimal("0.2")  # LB-3: a combo whose infrastructure failures exceed 20% of its cells is named

# Part C: existing tokens only. The band is a dashed outline (no tint under 3:1), the first column sticks in its region.
STYLE = """#lean-summary th[scope=row]{position:sticky;left:0;background:var(--panel)}
#lean-summary .bar .mde-band{fill:none;stroke:var(--rule-strong);stroke-dasharray:3 2}
#lean-summary .bar .interval{stroke:var(--ink);stroke-width:var(--focus-w)}
#lean-summary .bar .axis{stroke:var(--rule-strong)}
"""


def _signed(value: Decimal) -> str:
    return f"{value:+.2f}"


def _part(name: str, *children) -> Html:
    return el("span", {"data-part": name}, *children)


def _header(summary: lean.LeanSummary, reported_run_id: str) -> Html:
    facts = [
        ("question", "Question", QUESTION),
        ("prereg", "Pre-registration", summary.prereg_status),
        ("batches", "Batches", (f"Batches: {summary.batches} of {PLANNED_BATCHES} "
                                f"({summary.batches} of {PLANNED_BATCHES} batches graded; "
                                f"{summary.pooled.pairs} of {summary.pooled.planned_pairs} pairs recorded)")),
        ("run-ids", "Run ids", ", ".join(summary.run_ids) or NOT_RECORDED),
        ("plan-hashes", "Plan hashes", ", ".join(summary.plan_hashes) or NOT_RECORDED),
    ]
    rows: list[Html] = []
    for key, label, value in facts:
        rows += [el("dt", None, label), el("dd", {"data-field": key}, value)]
    children = [el("dl", {"class": "facts small"}, *rows)]
    if len(summary.run_ids) > 1:
        children.append(el("p", {"data-kind": "scope"}, f"Sections below cover batch {reported_run_id} only"))
    return el("div", {"data-block": "lean-header"}, *children)


def _excluded(excluded: Sequence[tuple[str, str]]) -> list[Html]:
    if not excluded:
        return []
    return [el("details", {"class": "excluded-list"}, el("summary", None, f"excluded cells ({len(excluded)})"),
               el("ul", None, *(el("li", {"data-cell-id": cid}, f"{cid} {cause}") for cid, cause in excluded)))]


def _row(r: lean.LeanRow, note: str | None) -> Html:
    zero = r.pairs == 0
    reason = f"{NOT_RECORDED} — 0 pairs" if zero else f"{NOT_RECORDED} — interval not computed"
    effect = _signed(r.effect) if r.effect is not None else reason
    has_interval = r.lo is not None and r.hi is not None
    interval = f"[{_signed(r.lo)}, {_signed(r.hi)}]" if has_interval else reason
    ratio = r.token_ratio
    has_ratio = ratio is not None and ratio.point is not None and ratio.lo is not None and ratio.hi is not None
    ratio_text = (f"{ratio.point:.2f}× [{ratio.lo:.2f}, {ratio.hi:.2f}]" if has_ratio
                  else f"{NOT_RECORDED} — {ratio.reason if ratio is not None and ratio.reason else 'no token-complete pair'}")
    state = "zero-pairs" if zero else ("partial" if r.pairs < r.planned_pairs else "complete")
    tip = (f"effect {r.effect if r.effect is not None else NOT_RECORDED}, interval "
           f"{f'[{r.lo}, {r.hi}]' if has_interval else NOT_RECORDED}, MDE {r.mde}, n {r.pairs} of {r.planned_pairs}")
    return el(
        "tr", {"data-harness": r.harness, "data-combo": r.combo, "data-state": state},
        el("th", {"scope": "row"}, r.harness, el("span", {"class": "small muted"}, f" {r.model}") if r.model else ""),
        el("td", {"class": "num", "title": tip}, _part("effect", effect)),
        el("td", None, _part("interval", interval), *([_bar("effect", r.lo, r.hi, r.mde)] if has_interval else [])),
        el("td", {"class": "num"}, _part("mde", f"MDE {r.mde}")),
        el("td", None, _part("pairs", f"{r.pairs} of {r.planned_pairs} pairs recorded"), *_excluded(r.excluded)),
        el("td", None, _part("statement", r.statement), *([" ", _part("note", note)] if note else [])),
        el("td", None, _part("token-ratio", ratio_text), " ",
           _part("ratio-excluded", f"{r.ratio_excluded} pairs excluded from the ratio"),
           *([_bar("token-ratio", ratio.lo, ratio.hi, None)] if has_ratio else [])),
    )


def _table(summary: lean.LeanSummary) -> Html:
    heads = ("Harness", "Effect: pack-on − pack-off (property_check_pass)", "95% interval", "MDE", "Pairs", "Statement",
             RATIO_LABEL)
    return el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-label": "Per-harness paired difference"},
        el("table", {"data-table": "per-harness"},
           el("caption", None, "Per-harness paired difference, with the pooled row last"),
           el("thead", None, el("tr", None, *(el("th", {"scope": "col"}, h) for h in heads))),
           el("tbody", None, *(_row(r, None) for r in summary.rows), _row(summary.pooled, DISAGREE if summary.disagree else None))),
    )


def _per_property(summary: lean.LeanSummary) -> Html:
    """LB-6: exploratory, collapsed. The planned pairs per property and harness are a harness's planned pairs over the
    property families (20 over 5 is the spec's 4)."""
    props = summary.properties
    families = len({p.family for p in props})
    planned = summary.rows[0].planned_pairs if summary.rows else 0
    per = f"{planned // families}" if families and planned else NOT_RECORDED
    children: list[Html] = []
    if props:
        rows = []
        for p in props:
            empty = p.off[1] == 0 and p.on[1] == 0
            counts = f"{p.off[0]}/{p.off[1]} → {p.on[0]}/{p.on[1]}" + (f", {NOT_RECORDED}" if empty else "")
            rows.append(el("tr", {"data-family": p.family, "data-harness": p.harness},
                           el("th", {"scope": "row"}, p.family), el("td", None, p.harness), el("td", None, counts),
                           el("td", None, NOT_RECORDED if empty else p.direction)))
        heads = ("Property", "Harness", "pack-off → pack-on (passes/recorded)", "Direction")
        children.append(el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-label": "Per property"},
                           el("table", {"data-table": "per-property"},
                              el("caption", None, f"Exploratory: {per} pairs per harness; not powered for a per-property finding"),
                              el("thead", None, el("tr", None, *(el("th", {"scope": "col"}, h) for h in heads))),
                              el("tbody", None, *rows))))
    else:
        children.append(el("p", None, "No per-property row recorded."))
    label = f"Per property (Exploratory: {per} pairs per harness)" if per != NOT_RECORDED else "Per property (Exploratory)"
    return el("details", {"data-block": "per-property"}, el("summary", None, label), *children)


def _minutes(value: Decimal | None) -> str:
    return f"{value:.2f}" if value is not None else NOT_RECORDED


def _checkpoint_lines(c: lean.BatchCheckpoint) -> list[Html]:
    est = lean.ESTIMATE
    lines = [
        el("li", None, f"{c.run_id}: run minutes per cell {_minutes(c.run_min_per_cell)} "
                       f"(estimate {est.run_min_per_cell:.2f}, Inferred)"),
        el("li", None, f"{c.run_id}: grading minutes per cell {_minutes(c.grade_min_per_cell)} "
                       f"(estimate {est.grade_min_per_cell:.2f}, Inferred)"),
    ]
    for (combo, arm), tokens in c.tokens_per_cell.items():
        shown = f"{tokens:,.0f}" if tokens is not None else NOT_RECORDED
        lines.append(el("li", None, f"{c.run_id}: tokens per cell, {combo} {arm} {shown} "
                                    f"(estimate {est.tokens_per_cell:,}, Inferred)"))
    for combo, (k, n, causes) in c.infra_failures.items():
        over = n > 0 and Decimal(k) / Decimal(n) > INFRA_LIMIT
        text = f"{c.run_id}: infrastructure failures, {combo} {k} of {n} cells ({', '.join(causes) or 'no cause recorded'})"
        lines.append(el("li", {"data-kind": "infra-over"} if over else None, text + (": over 20%" if over else "")))
    return lines


def _limits(summary: lean.LeanSummary) -> Html:
    caveat = CAVEAT_TWO_BATCHES if summary.batches >= PLANNED_BATCHES else CAVEAT_ONE_BATCH
    checkpoint = ([el("ul", None, *(line for c in summary.checkpoint for line in _checkpoint_lines(c)))]
                  if summary.checkpoint else [el("p", None, "Checkpoint not recorded")])
    return el("div", {"data-block": "limits"}, el("h3", None, "Limits"), el("p", None, caveat), *checkpoint)


def build(summary: lean.LeanSummary, reported_run_id: str) -> model.Section:
    """The lean summary section of the report for the batch `reported_run_id`."""
    empty = [] if summary.rows else [el("p", None, "No per-harness row recorded.")]
    body = el("section", {"id": SECTION_ID}, el("h2", None, TITLE), _header(summary, reported_run_id), *empty,
              _table(summary), el("p", {"data-block": "ratio-note", "class": "small muted"}, RATIO_NOTE),
              _per_property(summary), _limits(summary))
    return model.Section(SECTION_ID, TITLE, body)
