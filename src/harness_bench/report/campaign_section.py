"""Report section 3 (X-H2; W1-H design section 6): the campaign block, the property verdicts or the ring check,
the legend, the exclusions block with the R-93 line, and the validity line.

The section computes no statistic. It reads the campaign through `campaign.latest` over the real `CampaignState.rows`,
asks `verdicts` and `gates` for every value, and prints their fields. The word the dominance rule emits comes from
`Verdict.statement` only (sweep S-2).
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from harness_bench import campaign, gates, plan, power, verdicts
from harness_bench.errors import BenchError
from harness_bench.report import html_builder, model
from harness_bench.report.html_builder import Html, el

log = logging.getLogger("harness_bench.report.campaign_section")

PROPERTY_VERDICTS = "property-verdicts"
REGRESSION_CHECK = "regression-check"
EMPTY_DOMINANCE = "No arm dominates another."
NOT_RECORDED = "not recorded"
_GLYPH = {verdicts.VerdictLabel.BETTER: "▲", verdicts.VerdictLabel.WORSE: "▼", verdicts.VerdictLabel.NO_DIFFERENCE: "═",
          verdicts.VerdictLabel.UNDERPOWERED: "○", verdicts.VerdictLabel.NOT_RECORDED: "○"}
_BAR_W, _BAR_H = 120, 16


@dataclass(frozen=True)
class CampaignInput:
    """What `bench report` binds for a campaign run (the brief's fixture points 1-4 are its inputs)."""

    state: campaign.CampaignState
    prereg: Mapping  # bench-prereg/1 (fixture point 1)
    power_inputs: Mapping  # bench-power-inputs/1 (fixture point 2)
    power_result: Mapping[str, power.PowerResult]  # power.analyse of the inputs (fixture point 2)
    eligibility: campaign.Eligibility  # campaign.eligibility(...), computed by the caller
    expected_na: Mapping[str, frozenset[str]]  # fixture point 3
    read_disagreements: Callable[[], Sequence[str]]  # lambda: readiness.hidden_test_disagreements(run_dir, grading_id)


@dataclass(frozen=True)
class Built:
    section: model.Section
    header_block: Html  # the EV-20 campaign block, part of the header section
    validity_line: Html  # the third place of EV-18, part of the validity section; empty when nothing was excluded


# ---------------------------------------------------------------- the campaign facts

def section_id(state: campaign.CampaignState, run_id: str) -> str:
    attach = max((r for r in state.rows if r["kind"] in ("ring_run.attached", "grid.attached") and r["run_id"] == run_id),
                 key=lambda r: r["seq"], default=None)
    return REGRESSION_CHECK if attach is not None and attach["kind"] == "ring_run.attached" else PROPERTY_VERDICTS


def _short(value: str | None) -> Html | str:
    return el("span", {"title": value}, value[:12]) if value else NOT_RECORDED


def _arms_text(view) -> str:
    packs = plan.plan_packs(view.plan)
    arms = list(view.plan.get("arms") or packs)
    return ", ".join(f"{aid} (no pack)" if packs.get(aid) is None else f"{aid} (revision {packs[aid].get('revision', NOT_RECORDED)})"
                     for aid in arms) or NOT_RECORDED


def _mde_of(obj: CampaignInput, prop: str) -> Decimal:
    given = obj.prereg.get("mde", {}).get(prop)
    return Decimal(str(given if given is not None else obj.power_inputs["properties"][prop]["mde"]))


def _header_block(view, obj: CampaignInput) -> Html:
    state = obj.state
    created, baseline, registered = (campaign.latest(state, k) for k in ("campaign.created", "baseline.recorded", "registered"))
    power_row = campaign.latest(state, "power.recorded", role="final") or campaign.latest(state, "power.recorded", role="prior")
    fixes = [r for r in state.rows if r["kind"] == "defect_fix.admitted"]
    mde = obj.prereg.get("mde") or {}
    facts = [
        ("question", "Question", created["question"] if created else NOT_RECORDED),
        ("arms", "Arms", _arms_text(view)),
        ("prereg-hash", "Pre-registration hash", _short(registered["prereg_hash"] if registered else None)),
        ("baseline", "Engine baseline", _short(baseline["identity_hash"] if baseline else None)),
        ("defect-fixes", "Recorded defect fixes",
         "; ".join(f"{r['defect_class']} {r['commit'][:12]} ({r['scope']})" for r in fixes) or NOT_RECORDED),
        ("mde", "MDE per property", "; ".join(f"{p} {v}" for p, v in mde.items()) or NOT_RECORDED),
        ("power-analysis", "Power analysis",
         NOT_RECORDED if power_row is None
         else el("span", {"title": power_row["input_hash"]}, f"{power_row['input_hash'][:12]} ({power_row['role']})")),
    ]
    rows: list[Html] = []
    for key, label, value in facts:
        rows += [el("dt", None, label), el("dd", {"data-field": key}, value)]
    return el("div", {"data-block": "campaign"}, el("h2", None, "Campaign"), el("dl", {"class": "facts small"}, *rows))


# ---------------------------------------------------------------- the verdict cell

def _two(value: Decimal) -> str:
    return f"{value:.2f}"


def _bar(mark: str, lo: Decimal, hi: Decimal, mde: Decimal | None) -> Html:
    """An interval bar, `aria-hidden` (its values are in the parts beside it). Effect: diverging axis on [-1, 1] with the
    MDE band; ratio: log axis centred on 1."""
    if mark == "effect":
        place = lambda v: (max(-1.0, min(1.0, float(v))) + 1) / 2 * _BAR_W
    else:
        place = lambda v: (math.log(max(0.25, min(4.0, float(v)))) / math.log(4) + 1) / 2 * _BAR_W
    attrs = {"class": "bar", "aria-hidden": "true", "data-mark": mark, "data-interval-lo": _two(lo), "data-interval-hi": _two(hi),
             "width": _BAR_W, "height": _BAR_H, "viewBox": f"0 0 {_BAR_W} {_BAR_H}"}
    if mde is not None:
        attrs["data-mde"] = _two(mde)
    mid = _BAR_H / 2
    parts = [el("line", {"class": "axis", "x1": _BAR_W / 2, "x2": _BAR_W / 2, "y1": 0, "y2": _BAR_H})]
    if mde is not None:
        left, right = place(-mde), place(mde)
        parts.append(el("rect", {"class": "mde-band", "x": left, "y": 2, "width": right - left, "height": _BAR_H - 4}))
    parts.append(el("line", {"class": "interval", "x1": place(lo), "x2": max(place(hi), place(lo) + 1), "y1": mid, "y2": mid}))
    return el("svg", attrs, *parts)


def _na_text(na_counts: Mapping[str, int]) -> str:
    return "not recorded by reason: " + ("; ".join(f"{reason} {n}" for reason, n in sorted(na_counts.items())) or "none")


def _state(v: verdicts.Verdict) -> str:
    if v.n_pairs == 0:
        return "zero-pairs"
    return v.label.name.lower().replace("_", "-")


def _verdict_word(v: verdicts.Verdict, min_pairs: int) -> str:
    if v.label is not verdicts.VerdictLabel.NOT_RECORDED:
        return v.label.value
    if v.n_pairs == 0:
        return f"{v.label.value} — 0 pairs recorded; excluded {len(v.excluded)}"
    if v.n_pairs >= min_pairs and v.reason:
        return f"{v.label.value} — {v.reason}"
    return f"{v.label.value} — {v.n_pairs} of {min_pairs} pairs recorded"


def _part(name: str, label: str, *children) -> Html:
    return el("span", {"data-part": name, "aria-label": label}, *children)


def _excluded_items(excluded: Sequence[tuple[str, str]], arms: Mapping[str, str]) -> list[Html]:
    return [el("li", {"data-cell-id": cid}, f"{cid} ({arms.get(cid, NOT_RECORDED)}) {reason}") for cid, reason in excluded]


def _verdict_cell(v: verdicts.Verdict, min_pairs: int, arms: Mapping[str, str], cell_id: str) -> Html:
    marks: list[Html] = []
    if v.interval is not None:
        marks.append(_bar("effect", v.interval[0], v.interval[1], v.mde))
    effect = _part("effect", "effect", f"effect {v.effect:+.2f}" if v.effect is not None else f"effect {NOT_RECORDED}")
    interval = _part("interval", "interval", f"interval {v.level:.4f}: {_two(v.interval[0])} to {_two(v.interval[1])}"
                     if v.interval is not None else f"interval {NOT_RECORDED}")
    per_task = [el("span", {"data-task": t}, f"task {t}: {e:+.2f}" + (f" [{_two(lo)}, {_two(hi)}]" if lo is not None else ""))
                for t, (e, lo, hi) in sorted(v.per_task.items())]
    ratio = v.token_ratio
    if ratio is not None:
        marks.append(_bar("token-ratio", ratio.lo, ratio.hi, None))
    required = f" of {v.required_pairs}" if v.required_pairs else ""
    tip = (f"effect {v.effect if v.effect is not None else NOT_RECORDED}, interval level {v.level:.4f} ({v.level_rule}), "
           f"MDE {v.mde}, n {v.n_pairs}{required}, resamples {v.resamples}, seed {v.seed}")
    na_line = _na_text(v.na_counts)
    return el(
        "td", {"class": "verdict-cell", "id": cell_id, "data-state": _state(v), "title": tip},
        el("span", {"class": "glyph", "aria-hidden": "true"}, _GLYPH[v.label]),
        _part("verdict", "verdict", _verdict_word(v, min_pairs)),
        effect, interval,
        _part("mde", "MDE", f"MDE {v.mde}"),
        _part("per-task", "per-task effects", *(per_task or [f"per-task effects {NOT_RECORDED}"])),
        _part("token-ratio", "token ratio", f"tokens ×{ratio.r} [{_two(ratio.lo)}, {_two(ratio.hi)}]" if ratio is not None
              else f"tokens {NOT_RECORDED}"),
        _part("pairs", "pairs", f"n {v.n_pairs}{required}"),
        _part("excluded", "excluded cells", f"excluded {len(v.excluded)}",
              *([el("details", {"class": "excluded-list"}, el("summary", None, "excluded cells"),
                    el("div", {"class": "scroll"}, el("ul", None, *_excluded_items(v.excluded, arms))))] if v.excluded else []),
              f" · {na_line}"),
        *marks,
        *([el("span", {"class": "statement"}, v.statement)] if v.statement else []),
    )


# ---------------------------------------------------------------- R-93: the three states

def _hidden_test_line(read: Callable[[], Sequence[str]]) -> tuple[int | str, Html | None]:
    """Calls the reader once. A list gives its length (and the element when non-empty); the reader's HB-USR-002 is converted
    here, with its reason, into the not-recorded element (R-96 ruling 2). Any other exception propagates."""
    try:
        ids = list(read())
    except BenchError as exc:
        if exc.code != "HB-USR-002":
            raise
        return NOT_RECORDED, el("p", {"class": "warn", "data-kind": "hidden-test-agreement-not-recorded"},
                                f"Hidden-test agreement not recorded: {exc.message}.")
    if len(ids) > 0:
        return len(ids), el("p", {"class": "warn", "data-kind": "hidden-test-disagreement", "data-count": len(ids)},
                            f"Hidden tests disagreed with pass@1 in {len(ids)} cells: {', '.join(ids)}. "
                            "These cells' hidden-test results are not deterministic. No verdict, exclusion or eligibility changed.")
    return 0, None


# ---------------------------------------------------------------- the grid section

def _cell_arms(view) -> dict[str, str]:
    return {c.cell_id: plan.cell_arm(vars(c)) for c in view.cells}


def _admitted(state: campaign.CampaignState, tasks: Sequence[str]) -> tuple[str, ...]:
    out = []
    for task in tasks:
        row = campaign.latest(state, "admission.decided", task=task)
        if row is not None and row["admitted"] == 1:
            out.append(task)
    return tuple(out)


def _compute(view, obj: CampaignInput) -> tuple[list[tuple], int]:
    """(property, harness, ref, treat, spec, verdict-or-None, missing arm) per row, and the resamples used."""
    registered = campaign.latest(obj.state, "registered")
    prereg_hash = registered["prereg_hash"] if registered else NOT_RECORDED
    alpha = verdicts.alpha_per_test(obj.prereg)
    method = obj.prereg["correction"]["method"]
    rule = power.level_for(method, Decimal(str(obj.prereg["alpha"])), obj.prereg["correction"]["m"])[1]
    arms = set(view.plan.get("arms") or {}) or set(_cell_arms(view).values())
    out: list[tuple] = []
    for prop, body in obj.power_inputs["properties"].items():
        tasks = _admitted(obj.state, body["tasks"])
        if not tasks:
            continue
        in_scope = [c for c in view.cells if verdicts._task_rep(c, plan.cell_arm(vars(c)))[0] in body["tasks"]]
        for harness in obj.power_inputs["harnesses"]:
            for ref, treat in (tuple(pair) for pair in obj.power_inputs["comparisons"]):
                missing = next((a for a in (ref, treat) if a not in arms), None)
                if missing is not None:
                    out.append((prop, harness, ref, treat, None, None, missing))
                    continue
                required = next((r["n"] for r in obj.power_result[prop].required_pairs
                                 if r["harness"] == harness and tuple(r["comparison"]) == (ref, treat)), None)
                spec = verdicts.VerdictSpec(
                    prop=prop, harness=harness, comparison=(ref, treat), tasks=tasks, mde=_mde_of(obj, prop), method=method,
                    alpha_per_test=alpha, level_rule=rule, min_pairs=obj.prereg["min_pairs"],
                    seed=verdicts.seed_for(prereg_hash, prop, harness, (ref, treat)), resamples=verdicts.resamples_for(alpha),
                    required_pairs=required)
                pairs, excluded, na_counts = verdicts.collect(in_scope, spec)
                out.append((prop, harness, ref, treat, spec, verdicts.verdict(spec, pairs, excluded, na_counts), None))
    return out, (verdicts.resamples_for(alpha) if out else 0)


def _row(prop, harness, ref, treat, spec, v, missing, arms) -> Html:
    cid = f"verdict-{prop}-{harness}-{ref}-{treat}"
    cell = (el("td", {"data-state": "no-arm"}, f"This grid has no {missing}.") if v is None
            else _verdict_cell(v, spec.min_pairs, arms, cid))
    return el("tr", {"data-property": prop, "data-harness": harness, "data-comparison": f"{ref}-{treat}"},
              el("th", {"scope": "row"}, prop), el("th", {"scope": "row"}, harness), el("th", {"scope": "row"}, f"{ref} vs {treat}"),
              cell)


def _dominance(rows: Sequence[tuple]) -> Html:
    lines = []
    for prop, harness, ref, treat, _spec, v, _missing in rows:
        # a statement that is not a costly-gain line is the dominance rule's; the word is never typed here (sweep S-2)
        if v is not None and v.statement and not v.statement.startswith("better at "):
            lines.append(el("li", None, el("a", {"href": f"#verdict-{prop}-{harness}-{ref}-{treat}"}, v.statement),
                            f" on {prop} ({harness})"))
    return el("div", {"data-block": "dominance"}, el("ul", None, *lines) if lines else el("p", None, EMPTY_DOMINANCE))


def _legend(v: verdicts.Verdict) -> Html:
    return el("p", {"data-block": "legend", "data-method": v.method, "data-alpha-per-test": str(v.alpha_per_test),
                    "data-level-rule": v.level_rule},
              f"Interval level: {v.level:.4f} ({v.level_rule}). ",
              "▲ better · ▼ worse · ═ no difference ≥ MDE · ○ inconclusive. The dashed band is the MDE.")


def _exclusions(rows: Sequence[tuple], arms: Mapping[str, str], reader_line: Html | None) -> tuple[Html, list[tuple[str, str]], Mapping]:
    unique: dict[str, str] = {}
    na: dict[str, int] = {}
    for *_head, v, _missing in rows:
        if v is None:
            continue
        unique.update({cid: reason for cid, reason in v.excluded})
        for reason, n in v.na_counts.items():
            na[reason] = na.get(reason, 0) + n
    listed = sorted(unique.items())
    block = el("div", {"data-block": "exclusions"},
               el("p", {"data-kind": "excluded-total"}, f"excluded {len(listed)} cells in total"),
               *([el("details", None, el("summary", None, "excluded cells"),
                     el("div", {"class": "scroll"}, el("ul", None, *_excluded_items(listed, arms))))] if listed else []),
               el("p", {"data-kind": "na-counts"}, _na_text(na)),
               *([reader_line] if reader_line is not None else []))
    return block, listed, na


def _ineligible(obj: CampaignInput, title: str, sid: str) -> Html:
    return el("section", {"id": sid}, el("h2", None, title),
              el("p", {"class": "warn", "data-kind": "ineligible"}, "No verdicts: " + "; ".join(obj.eligibility.reasons) + "."))


def _grid(view, obj: CampaignInput, hidden_read: Callable) -> tuple[Html, Html]:
    started = time.perf_counter()
    rows, resamples = _compute(view, obj)
    ms = round((time.perf_counter() - started) * 1000)
    arms = _cell_arms(view)
    counted = [r[5] for r in rows if r[5] is not None]
    labels: dict[str, int] = {}
    for v in counted:
        labels[v.label.value] = labels.get(v.label.value, 0) + 1
    log.info("verdicts.computed", extra={"verdicts": len(counted), "resamples_total": resamples * len(counted), "ms": ms,
                                         "excluded_total": sum(len(v.excluded) for v in counted),
                                         "na_total": sum(sum(v.na_counts.values()) for v in counted), "labels": labels})
    count, line = _hidden_test_line(hidden_read)
    log.info("section.built", extra={"hidden_disagreements": count})
    block, listed, _na = _exclusions(rows, arms, line)
    children: list[Html] = [el("h2", None, "Property verdicts")]
    if counted:
        children.append(_legend(counted[0]))
    children.append(block)
    if rows:
        table = el("table", None,
                   el("caption", None, "Property verdicts by property, harness and comparison"),
                   el("thead", None, el("tr", None, *(el("th", {"scope": "col"}, h) for h in ("Property", "Harness", "Comparison", "Verdict")))),
                   el("tbody", None, *(_row(*r, arms) for r in rows)))
        children += [el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-label": "Property verdicts"}, table),
                     _dominance(rows)]
    else:
        children.append(el("p", None, "No property task was admitted. See the campaign record."))
    children.append(el("details", {"data-block": "exploratory"}, el("summary", None, "Exploratory results"),
                       el("p", None, "Exploratory: not in the pre-registration.")))
    banner = (el("p", {"data-block": "campaign-excluded"}, f"Campaign verdicts: excluded {len(listed)} cells in total"
                 + "".join(f"; {cid} ({arms.get(cid, NOT_RECORDED)}) {reason}" for cid, reason in listed))
              if listed else html_builder.trusted(""))
    return el("section", {"id": PROPERTY_VERDICTS}, *children), banner


# ---------------------------------------------------------------- the ring section

def _ring(view, obj: CampaignInput) -> Html:
    started = time.perf_counter()
    items = gates.ring_items(view, obj.expected_na)
    kinds: dict[str, int] = {}
    for item in items:
        kinds[item.kind] = kinds.get(item.kind, 0) + 1
    log.info("gate.evaluated", extra={"tag": (view.plan.get("ring") or {}).get("tag", NOT_RECORDED), "items": kinds,
                                      "ms": round((time.perf_counter() - started) * 1000)})
    log.info("section.built", extra={"hidden_disagreements": NOT_RECORDED})
    children: list[Html] = [el("h2", None, "Regression check")]
    properties = list(obj.power_inputs["properties"])
    if not properties:
        children.append(el("p", None, "This ring has no property tasks."))
    else:
        withheld = f"Result withheld: ring gate failed ({', '.join(f'{i.kind} {i.ident}' for i in items)})."
        rows = []
        for prop in properties:
            text = withheld if items else gates.pack_regression(view, {prop: _mde_of(obj, prop)})[prop]
            if text == "regression signal":
                state = "signal"
            elif text.startswith("no regression detected at"):
                state, text = "no-signal", f"{text} — this ring cannot see smaller effects."
            else:
                state = "withheld"
            rows.append(el("tr", {"data-property": prop}, el("th", {"scope": "row"}, prop), el("td", {"data-state": state}, text)))
        children.append(el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-label": "Regression check"},
                           el("table", None, el("caption", None, "Regression check by property"),
                              el("thead", None, el("tr", None, el("th", {"scope": "col"}, "Property"), el("th", {"scope": "col"}, "Result"))),
                              el("tbody", None, *rows))))
    if sum(1 for r in obj.state.rows if r["kind"] == "ring_run.attached") <= 1:
        children.append(el("p", None, "No earlier ring result for this pack."))
    return el("section", {"id": REGRESSION_CHECK}, *children)


# ---------------------------------------------------------------- entry point

def build(view, campaign_obj: CampaignInput) -> Built:
    """The three blocks of one campaign report: the section, the header's campaign block and the validity line."""
    sid = section_id(campaign_obj.state, view.run_id)
    title = "Regression check" if sid == REGRESSION_CHECK else "Property verdicts"
    header = _header_block(view, campaign_obj)
    none = html_builder.trusted("")
    if not campaign_obj.eligibility.eligible:
        if sid == PROPERTY_VERDICTS:
            log.info("verdicts.computed", extra={k: NOT_RECORDED for k in
                                                 ("verdicts", "resamples_total", "ms", "excluded_total", "na_total", "labels")})
        log.info("section.built", extra={"hidden_disagreements": NOT_RECORDED})
        return Built(model.Section(sid, title, _ineligible(campaign_obj, title, sid)), header, none)
    if sid == REGRESSION_CHECK:
        return Built(model.Section(sid, title, _ring(view, campaign_obj)), header, none)
    body, banner = _grid(view, campaign_obj, campaign_obj.read_disagreements)
    return Built(model.Section(sid, title, body), header, banner)
