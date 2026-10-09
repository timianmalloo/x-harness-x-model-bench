"""The lean summary section (ADR-0023 point 9; spec `docs/specs/lean-pack-benchmark.md` Parts B and C).

The section computes no statistic. It prints the fields of one `lean.LeanSummary` (built by `lean.build`, passed in by
the caller) in the spec's order: the header, the per-harness table with the pooled row, the per-property table
(collapsed) and the limits note. Every statement is `LeanRow.statement`, printed as text; colour and the bars only
repeat what the text says (LBI-2).
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


def _row(r: lean.LeanRow, pooled: bool) -> Html:
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
        "tr", {"data-harness": r.harness, "data-combo": r.combo, "data-state": state, "data-row": "pooled" if pooled else "harness"},
        el("th", {"scope": "row"}, r.harness, el("span", {"class": "small muted"}, f" {r.model}") if r.model else ""),
        el("td", {"class": "num", "title": tip}, _part("effect", effect)),
        el("td", None, _part("interval", interval), *([_bar("effect", r.lo, r.hi, r.mde)] if has_interval else [])),
        el("td", {"class": "num"}, _part("mde", f"MDE {r.mde}")),
        el("td", None, _part("pairs", f"{r.pairs} of {r.planned_pairs} pairs recorded"), *_excluded(r.excluded)),
        el("td", None, _part("statement", r.statement)),
        el("td", None, _part("token-ratio", ratio_text), *([_bar("token-ratio", ratio.lo, ratio.hi, None)] if has_ratio else [])),
    )


def _table(summary: lean.LeanSummary) -> Html:
    heads = ("Harness", "Effect: pack-on − pack-off (property_check_pass)", "95% interval", "MDE", "Pairs", "Statement",
             "Token ratio")
    return el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-label": "Per-harness paired difference"},
        el("table", {"data-table": "per-harness"},
           el("caption", None, "Per-harness paired difference, with the pooled row last"),
           el("thead", None, el("tr", None, *(el("th", {"scope": "col"}, h) for h in heads))),
           el("tbody", None, *(_row(r, False) for r in summary.rows), _row(summary.pooled, True))),
    )


def build(summary: lean.LeanSummary, reported_run_id: str) -> model.Section:
    """The lean summary section of the report for the batch `reported_run_id`."""
    body = el("section", {"id": SECTION_ID}, el("h2", None, TITLE), _header(summary, reported_run_id), _table(summary))
    return model.Section(SECTION_ID, TITLE, body)
