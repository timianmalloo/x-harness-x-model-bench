"""`report.html`: the static phase-1 report skeleton (design: UI & interaction design).

- One static file: pre-rendered, no JavaScript, no network request, light mode only. Every colour, size
  and radius is a token in the one `:root` block (the mockup seed, S-10 produces DESIGN.md).
- Sections with stable ids: `header`, `validity`, `leaderboard`, `runs`. Tables have a caption and scoped
  header cells; each scroll container is a focusable, labelled region. Numbers are right-aligned tabular
  figures with units. NA reads `NA (<reason>)`, never 0.
- Before the file is written, publication egress (US-47 c3) runs each section through `egress.check`: a hit
  replaces that section with `withheld: sensitive content`, and `report-record.json` lists it. Then the page is
  scanned for credential shapes (HB-SEC-001): a match refuses the write and names only the count, never the value.
- The kiviats, frontiers, heatmap, pack effect and summaries of the mockup are later phases (Spec S-10).
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from harness_bench import (
    board,
    composites,
    config,
    egress,
    lean,
    lifecycle,
    profiles,
    report,
    stats,
    views,
)
from harness_bench.errors import BenchError
from harness_bench.grade import judge as grade_judge
from harness_bench.plan import plan_packs, resolved_model_map
from harness_bench.report import (
    campaign_section,
    context_growth,
    html_builder,
    judges,
    lean_section,
    model,
)
from harness_bench.report import pack_improvement as pack_improvement_mod
from harness_bench.report.credentials import encodings

SECRET_SHAPES = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),  # Anthropic keys and OAuth tokens
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),  # OpenAI keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),  # GitHub tokens
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWTs (OAuth access tokens)
)
PUBLICATION = "report"  # the egress destination id of report publication (US-47 c3)
RECORD = "report-record.json"  # beside report.html: what the report withheld (US-47 c3) and flagged (US-46 c2)
PARTIAL = "partial: email not supplied"  # the publication scan without BENCH_OPERATOR_EMAIL (R-80 DR-EG-3)
# The judge gateway's own withholding: gateway/pipeline.py:168 returns Result("failed", "HB-GW-009", ...);
# grade/judge.py's item_score (Verified, :186-200) composes it onto the score's reason as "judge <model>: failed
# HB-GW-009"; ruling R-80 c1 names this as the one definition (never a second copy in the report's own guess).
WITHHELD_CODE = "HB-GW-009"
SCRIPT_PATH = Path(__file__).parent / "assets" / "report.js"  # R4: the one hashed inline script (design section 5)
# One rendered section. Sections never nest, and every value is escaped by `_e`, so "</section>" is only a tag.
_SECTION = re.compile(r'<section id="([a-z0-9-]+)">.*?</section>', re.DOTALL)
_HEADER_END = re.compile(r'(<section id="header">.*?)(</section>)', re.DOTALL)  # where the egress row goes (R-80 c1)

# R1 / R5 (design section 3, DR-R-3): both themes in one style block, dark under `prefers-color-scheme`
# only -- no toggle, no stored preference.
# `--heat-0..9`: verified by the Leader, 2026-09-28, matplotlib 3.11.2, viridis sampled at i/9 (retires R1's linear-RGB interpolation assume:).
STYLE = """
:root{color-scheme: light dark;
  --bg:#f3f5f7; --panel:#ffffff; --ink:#18212b; --ink-2:#4b5563; --ink-3:#7a8491; --rule:#d9dee5;
  --rule-strong:#767f8b; --focus:#1d5fbf; --na:#5f6873; --warn:#8a5a00; --bad:#9b1c1c; --bad-bg:#fbeaea;
  --c1:#0b63a8; --c2:#b35400; --c3:#00795a; --c4:#a3417d; --c5:#5b4bb0; --c6:#7a6400; --c7:#b0303a; --c8:#3d6e8f;
  --div-pos:#5e3c99; --div-neg:#b35806;
  --heat-0:#440154; --heat-1:#482878; --heat-2:#3e4989; --heat-3:#31688e; --heat-4:#26828e; --heat-5:#1f9e89;
  --heat-6:#35b779; --heat-7:#6ece58; --heat-8:#b5de2b; --heat-9:#fde725;
  --on-heat-dark:#ffffff; --on-heat-light:#000000;
  --font:"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --fs:15px; --fs-small:13px; --fs-h1:26px; --fs-h2:19px;
  --s1:4px; --s2:8px; --s3:16px; --s4:24px; --s5:40px;
  --radius:4px; --rule-w:1px; --focus-w:2px; --target:24px; --maxw:1240px; --bar-h:88px; --popover-maxw:360px;}
@media (prefers-color-scheme: dark){
:root{
  --bg:#0e1318; --panel:#151c23; --ink:#e7ecf1; --ink-2:#aab5c1; --ink-3:#76818d; --rule:#2a343f;
  --rule-strong:#6c7784; --focus:#7fb2ff; --na:#98a3ae; --warn:#e3b35a; --bad:#ffb3b3; --bad-bg:#3a1c1f;
  --c1:#5fb0f0; --c2:#f0a050; --c3:#3fc79a; --c4:#e58cc0; --c5:#a79cf2; --c6:#d9c24a; --c7:#ff8a8f; --c8:#8fc3e0;
  --div-pos:#b2abd2; --div-neg:#fdb863;
}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:var(--fs);line-height:1.45}
main{max-width:var(--maxw);margin:0 auto;padding:var(--s4) var(--s3)}
html{scroll-padding-top:var(--bar-h)}
h1{font-size:var(--fs-h1);margin:0 0 var(--s2)}
h2{font-size:var(--fs-h2);margin:var(--s4) 0 var(--s2)}
.muted,dt{color:var(--ink-2)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:var(--s1) var(--s3);margin:0}
dd{margin:0}
.region{overflow-x:auto;max-width:100%;background:var(--panel);border:var(--rule-w) solid var(--rule);border-radius:var(--radius)}
.region:focus-visible{outline:var(--focus-w) solid var(--focus);outline-offset:var(--focus-w)}
nav[aria-label="Sections"]{display:flex;flex-wrap:wrap;gap:var(--s1) var(--s3);font-size:var(--fs-small);padding:var(--s2) 0}
table{border-collapse:collapse;min-width:100%}
caption{text-align:left;font-weight:600;padding:var(--s2)}
th,td{padding:var(--s1) var(--s2);border-top:var(--rule-w) solid var(--rule);text-align:left;vertical-align:top}
.num{text-align: right; font-variant-numeric: tabular-nums; white-space:nowrap}
code,.small{font-size:var(--fs-small)}
.pos{fill:var(--div-pos);stroke:var(--div-pos)}
.neg{fill:var(--div-neg);stroke:var(--div-neg)}
.nde{fill:var(--ink-2);stroke:var(--ink-2)}
.whisk{stroke-width:2}
.axis{stroke:var(--rule-strong);stroke-width:1}
.grid{stroke:var(--rule);stroke-width:1}
svg text{fill:var(--ink-2);font-size:var(--fs-small);font-family:var(--font)}
figure{margin:0}
figcaption{font-size:var(--fs-small);color:var(--ink-2)}
.chart-panels{display:flex;flex-direction:column;gap:var(--s3)}
/* Scenarios heatmap (design s6 row 7, DR-R-1): 10 viridis buckets, each an exact copy of the
   token pair, never a literal colour (UIA-10). The ink per bucket (--on-heat-dark for white text,
   --on-heat-light for black text) is computed from each --heat-N fill's own WCAG relative luminance,
   whichever ink contrasts more -- verified this slice (test_scenarios_heat_ink_meets_wcag_aa)
   against the exact same --heat-0..9 values above, so a future palette change cannot silently drift. */
.heat td.h{text-align:center;white-space:normal}
/* simplify: a repeating-gradient hatch, not an SVG pattern fill -- the smallest correct way to mark
   an NA heat cell as "not a value" without colour alone (design s6 row 7's "NA: hatched"); ceiling:
   an SVG <pattern> tile, if the craft gate ever flags this gradient as too faint. */
.heat td.h.na{background:repeating-linear-gradient(45deg,var(--rule) 0 var(--s1),var(--panel) var(--s1) var(--s2));color:var(--na)}
#controls{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:var(--rule-w) solid var(--rule-strong);padding:var(--s2) 0;display:flex;flex-wrap:wrap;gap:var(--s2) var(--s4);align-items:center}
.tg{font:inherit;font-size:var(--fs-small);min-height:var(--target);min-width:var(--target);padding:0 var(--s2);background:var(--panel);color:var(--ink);border:var(--rule-w) solid var(--rule-strong);border-radius:var(--radius);cursor:pointer}
.tg[aria-pressed="true"]{box-shadow:inset 0 calc(-1 * var(--focus-w)) 0 var(--focus);font-weight:600}
.tg[aria-disabled="true"]{color:var(--ink-2);border-style:dashed;cursor:not-allowed}
.sort{font:inherit;color:inherit;background:none;border:0;padding:0;min-height:var(--target);cursor:pointer;font-weight:600}
.popover{position:absolute;z-index:3;background:var(--panel);color:var(--ink);border:var(--rule-w) solid var(--rule-strong);border-radius:var(--radius);padding:var(--s2) var(--s3);max-width:var(--popover-maxw);font-size:var(--fs-small);overflow-wrap:anywhere}
select{font:inherit;min-height:var(--target)}
.mk-c1{fill:var(--c1);stroke:var(--c1)}.mk-c2{fill:var(--c2);stroke:var(--c2)}.mk-c3{fill:var(--c3);stroke:var(--c3)}
.mk-c4{fill:var(--c4);stroke:var(--c4)}.mk-c5{fill:var(--c5);stroke:var(--c5)}.mk-c6{fill:var(--c6);stroke:var(--c6)}
.mk-c7{fill:var(--c7);stroke:var(--c7)}.mk-c8{fill:var(--c8);stroke:var(--c8)}
.hollow{fill:var(--panel);stroke-width:2}.dash{stroke-dasharray:4 3}
.charts{display:flex;flex-wrap:wrap;gap:var(--s3)}
.step{stroke:var(--rule-strong);stroke-dasharray:2 2}
/* Global filter state (design section 6): classes on <main>, so CSS alone hides matching rows/marks
   at redraw time (no per-node JS). c1..c8 matches the categorical palette's own cap (design section 3). */
main.hide-c1 [data-combo="c1"]{display:none}
main.hide-c2 [data-combo="c2"]{display:none}
main.hide-c3 [data-combo="c3"]{display:none}
main.hide-c4 [data-combo="c4"]{display:none}
main.hide-c5 [data-combo="c5"]{display:none}
main.hide-c6 [data-combo="c6"]{display:none}
main.hide-c7 [data-combo="c7"]{display:none}
main.hide-c8 [data-combo="c8"]{display:none}
"""


def _arm_order(present: Sequence[str]) -> tuple[str, ...]:
    """The arm settings a run shows, in display order: the two legacy settings for a legacy-shaped run (so a one-setting run
    still lists the other, disabled), else the reference arm first and the rest by name."""
    if set(present) <= set(config.PACKS):
        return config.PACKS
    return tuple(sorted(present, key=lambda a: (a != config.ARM_OFF, a)))


def _arm_css(present: Sequence[str]) -> str:
    """One hiding rule per ordered pair of arms: `main.pack-<a> [data-pack="<b>"]` hides b while a alone is shown (report.js adds
    the `pack-<a>` class). Arm ids match `config.ARM_ID`, so they are safe inside a selector."""
    arms = _arm_order(present)
    return "".join(f'main.pack-{a} [data-pack="{b}"]{{display:none}}\n' for a in arms for b in arms if a != b)


def _e(value) -> str:
    return _html.escape(str(value), quote=True)


def _context_window_tags(run_dir: Path | None) -> dict[str, str]:
    """R-32: cell_id -> context_window_tag, read straight from `attempt.process_ended` events
    (views.py is not touched for this: the report reads the attribute itself, ruling R-32 condition 3)."""
    if run_dir is None:
        return {}
    return {e["cell_id"]: e["context_window_tag"] for e in views.rows(run_dir, "events")
            if e.get("kind") == "attempt.process_ended" and e.get("context_window_tag")}


def _context_window_fact(cells: list[views.CellView], tags: dict[str, str]) -> str | None:
    """R-32: one disclosure line per harness present, "not recorded" for a harness with no tagged cell
    (a shared "not recorded" is not repeated per harness)."""
    harnesses = sorted({c.harness for c in cells})
    if not harnesses:
        return None
    lines = []
    for h in harnesses:
        tag = next((tags.get(c.cell_id) for c in cells if c.harness == h and tags.get(c.cell_id)), None)
        line = report.context_window(h, tag)
        if line not in lines:
            lines.append(line)
    return "; ".join(lines)


def _run_wall_clock(run_dir: Path | None) -> str:
    """R2 (design section 6 row 1): the run's own wall clock, not a sum over cells that ran in parallel. The number
    is `views.run_wall_ns` (the run's end minus its start `mono_ns`, both from the one engine process a run_dir ever
    has), the one definition the lean summary also reads (ADR-0023 decision 7); this only formats it. A reading it
    cannot make, or no run_dir, reads not recorded -- never a plausible number (IO)."""
    wall_ns = None if run_dir is None else views.run_wall_ns(run_dir)
    return "not recorded" if wall_ns is None else f"{wall_ns / 1_000_000_000:.1f} s"


def _permission_modes(run_dir: Path | None) -> dict[str, str]:
    """R-34: cell_id -> permission_mode_effective, read straight from `attempt.session_opened` events."""
    if run_dir is None:
        return {}
    return {e["cell_id"]: e["permission_mode_effective"] for e in views.rows(run_dir, "events")
            if e.get("kind") == "attempt.session_opened" and e.get("permission_mode_effective")}


def _claude_code_permission_fact(cells: list[views.CellView], modes: dict[str, str]) -> list[tuple[str, str | None]]:
    """R-34: the mode the Claude Code sessions reported (the declared dontAsk falls back to default); no row
    without a Claude Code cell, None ("not recorded") when no Claude Code cell recorded one."""
    claude = [c for c in cells if c.harness == "claude-code"]
    if not claude:
        return []
    seen = sorted({modes[c.cell_id] for c in claude if c.cell_id in modes})
    return [("Claude Code permission mode (effective)", ", ".join(seen) or None)]


def _build_check_fact(cells: list[views.CellView]) -> str:
    """R-47 c3: until each pinned build carries a recorded agent_version, HB-VAL-006 on every cell is the disclosed
    state; the header says how many cells skipped the check."""
    skipped = sum(1 for c in cells if any(w.code == "HB-VAL-006" for w in c.warnings))
    if skipped:
        return f"skipped for {skipped} of {len(cells)} cells (HB-VAL-006): no recorded agent_version"
    return "checked against the recorded agent_version (HB-VAL-007 on a mismatch)"


COORDINATION_BANNER = "coordination: not built in 0.4"  # R-73 c6: grade/coordination.py is not in GRADERS in 0.4


def _allowance() -> str:
    """R-74 c6: the scenario-6 allowance per harness, in the ruling's order, from the profiles' own delegate ids (the
    readers'); a harness with none reads `not qualified`."""
    parts = []
    for harness in ("claude-code", "copilot", "codex"):
        ids = profiles.DELEGATE_IDS.get(harness)
        parts.append(f"{harness} {', '.join(ids)}" if ids else f"{harness} not qualified")
    return " · ".join(parts)


def _scenario6_facts(view: views.RunView) -> list[tuple[str, str | None]]:
    """R-73 c6, R-74 c6: for a run with scenario-6 cells, the coordination banner, the allowance, per combo the resolved
    role -> model map of its vendor (the one resolver) with `non-discriminating` beside a role on the pin, and per cell
    the served-model set. No rows without a scenario-6 cell."""
    plan = view.plan
    cells = [c for c in plan.get("cells", []) if views._scenario(plan, c) == 6]
    if not cells:
        return []
    facts: list[tuple[str, str | None]] = [("Coordination (scenario 6)", COORDINATION_BANNER),
                                           ("Scenario-6 allowance", _allowance())]
    combos: dict[str, dict] = {}
    for c in cells:
        combos.setdefault(c["combo"], c)
    for combo, c in combos.items():
        roles = resolved_model_map(plan, c)
        facts.append((f"Model map ({combo})", ", ".join(
            f"{role} → {model}" + (" (non-discriminating)" if model == c["model"] else "") for role, model in roles.items())))
    served = {v.cell_id: v.served for v in view.cells}
    for c in cells:
        s = served.get(c["cell_id"])
        facts.append((f"Served models ({c['label']})", None if s is None else (", ".join(s) or "none")))
    return facts


def _pack_fact(plan: dict, field: str) -> str | None:
    """The one revision (or commit) of the plan's packs; `several packs` for two or more, None for none (R6-10)."""
    packs = plan_packs(plan)
    if len(packs) > 1:
        return "several packs"
    return next(iter(packs.values()), {}).get(field)


def _header(view: views.RunView, tags: dict[str, str], modes: dict[str, str] | None = None,
            judging: list[tuple[str, str | None]] | None = None, root: Path | None = None,
            run_dir: Path | None = None, board_obj: board.Board | None = None,
            params: stats.Params | None = None, campaign_block: html_builder.Html | None = None) -> html_builder.Html:
    plan = view.plan
    planned = ", ".join(views.build_label(h, str(b.get("version", ""))) for h, b in sorted((plan.get("builds") or {}).items()))
    facts = [("Run", view.run_id), ("State", "complete" if view.completed else "incomplete"),
             ("Plan hash", (plan.get("plan_hash") or "")[:12]), ("Catalog version", view.catalog_version),
             ("Pack revision", _pack_fact(plan, "revision")),
             ("Pack commit", _pack_fact(plan, "commit")), ("Planned builds", planned),
             ("Executed builds", view.header.get("executed_builds")), ("Executed-build check", _build_check_fact(view.cells)),
             ("Credential kind", view.header.get("credential_kind")),
             ("Network mode", view.header.get("network_mode")), ("Defender real-time exclusion", None),
             ("Context window", _context_window_fact(view.cells, tags)),
             *_claude_code_permission_fact(view.cells, modes or {}),
             ("Price list hash", (plan.get("price_list_hash") or "")[:12]), *_scenario6_facts(view),
             *(judging or []),  # Probe versions is the last judge-block row (report/judges.py)
             *report.disclosure_rows(root, plan, run_dir, view, board_obj=board_obj, params=params)]  # R-76 gate allowance; R-77 D1 baseline from this run
    if report.has_codex_cell(plan):
        facts.append((report.N5_FLAG, f"see {report.N5_EVIDENCE}"))
    if report.has_claude_code_cell(plan):
        facts.append((report.R36_FLAG, f"see {report.R36_EVIDENCE}"))

    status_str = "Complete" if view.completed else "Incomplete"
    # The plan freezes the BOM as `bom_version` plus the matrix's `bom.subset` (a task-id list, or smoke / full).
    subset = ((plan.get("matrix") or {}).get("bom") or {}).get("subset")
    subset_str = ", ".join(subset) if isinstance(subset, list) else subset
    bom_str = f"BOM {plan['bom_version']}" if plan.get("bom_version") else "BOM not recorded"
    if plan.get("bom_version") and subset_str:
        bom_str += f" ({subset_str})"
    cat_str = f"catalog {view.catalog_version}" if view.catalog_version else "catalog not recorded"
    pack_rev = _pack_fact(plan, "revision")
    pack_str = ("several packs" if pack_rev == "several packs" else f"pack ai-forward revision {pack_rev}"
                if pack_rev is not None else "pack revision not recorded")
    cells_str = f"{len(view.cells)} cells"

    summary_p = html_builder.el(
        "p", {"class": "muted"},
        f"{status_str} · {bom_str} · {cat_str} · {pack_str} · {cells_str} · ",
        html_builder.el("a", {"href": "#leaderboard"}, "Leaderboard"),
        " · ",
        html_builder.el("a", {"href": "#pack-effect"}, "Pack effect"),
    )

    # 1a. About this run (<details>)
    about_pack_rev = f"ai-forward revision {pack_rev if pack_rev is not None else 'not recorded'}"
    about_intro = html_builder.el(
        "p", None,
        "This run tests the pack ",
        html_builder.el("strong", None, about_pack_rev),
        ".",
    )
    terms = [
        ("combo", "A combo is one harness, at one build, driving one model."),
        ("pack on / pack off", "Pack on runs the task with the AI-Forward Pack installed in the workspace; pack off runs the same task without it."),
        ("correctness-gated composite", "The correctness-gated composite is the mean of the area scores (0-100) a cell recorded, set to 0 when its hidden tests fail."),
        ("pass@1 / pass^k", "pass@1 is the share of cells whose hidden tests pass; pass^k is the share of tasks passed in all k repetitions."),
        ("interval", "An interval is the 95% bootstrap range of a value over tasks and repetitions; overlapping intervals mean the data cannot tell the values apart."),
        ("not recorded", "Not recorded means the value could not be measured, and it is never counted as 0."),
    ]
    about_dl_items = []
    for term, definition in terms:
        about_dl_items.append(html_builder.el("dt", None, term))
        about_dl_items.append(html_builder.el("dd", None, definition))
    about_details = html_builder.el(
        "details", None,
        html_builder.el("summary", None, "About this run"),
        about_intro,
        html_builder.el("dl", {"class": "facts small"}, *about_dl_items),
    )

    header_dl_items = []

    # Judges (only when judging was performed)
    judges_dict = dict(judging or [])
    if judges_dict.get("Judges"):
        j_line = judges_dict["Judges"]
        agr = judges_dict.get("Agreement on this run")
        if agr and not str(agr).startswith("not recorded"):
            judges_text = f"{j_line} · {agr}"
        else:
            judges_text = str(j_line)
        header_dl_items.extend([
            html_builder.el("dt", None, "Judges"),
            html_builder.el("dd", None, judges_text),
        ])

    # Spend: tokens are the cost axis (R-115); the total is the cells' token counts (tokens_by_type)
    cell_totals = [c.tokens for c in view.cells if c.tokens]
    runs_spend = (f"{sum(sum(b.values()) for t in cell_totals for b in t.values()):,} tok"
                  if cell_totals else "not recorded")

    # judges.NO_CALL ("no call in this pass"): the existing judging-facts wording for an absent call
    # (judges.py:40, :179), never an invented "0 calls" when judging did not run at all (judges.facts
    # returns [] with no pass looked up, judges.py:253).
    judge_spend = judges_dict.get("Judge spend") or judges.NO_CALL
    coord_spend = "not recorded"
    spend_text = f"runs {runs_spend} · judges {judge_spend} · coordinator {coord_spend}"

    # Wall clock: the run's own duration (R2), never a sum over cells that ran in parallel.
    wall_text = _run_wall_clock(run_dir)

    # Cell time (sum): the same per-cell sum the old "Wall clock" row carried, honestly labelled (R2).
    wall_measures = [c.wall_ms for c in view.cells if c.wall_ms and c.wall_ms.value is not None]
    if wall_measures:
        total_ms = sum(Decimal(str(m.value)) for m in wall_measures)
        cell_time_text = f"{total_ms / 1000:.1f} s"
    else:
        cell_time_text = "not recorded"

    # Statistics
    if board_obj is not None:
        stat_text = board.header_row(board_obj).removeprefix("statistics: ")
    else:
        stat_text = "not recorded"

    header_dl_items.extend([
        html_builder.el("dt", None, "Spend"), html_builder.el("dd", None, spend_text),
        html_builder.el("dt", None, "Wall clock"), html_builder.el("dd", None, wall_text),
        html_builder.el("dt", None, "Cell time (sum)"), html_builder.el("dd", None, cell_time_text),
        html_builder.el("dt", None, "Statistics"), html_builder.el("dd", None, stat_text),
    ])

    header_dl = html_builder.el("dl", {"class": "facts small"}, *header_dl_items)

    # Provenance details
    prov_dl_items = []
    for k, v in facts:
        prov_dl_items.append(html_builder.el("dt", None, k))
        val_str = str(v) if v not in (None, "") else "not recorded"
        prov_dl_items.append(html_builder.el("dd", None, val_str))
    prov_details = html_builder.el(
        "details", None,
        html_builder.el("summary", None, f"Provenance details ({len(facts)} rows)"),
        html_builder.el("dl", {"class": "facts small"}, *prov_dl_items),
    )

    return html_builder.el(
        "section", {"id": "header"},
        html_builder.el("h1", None, f"harness-bench run {view.run_id}"),
        summary_p,
        about_details,
        header_dl,
        prov_details,
        *([campaign_block] if campaign_block is not None else []),
    )


def _validity(view: views.RunView, campaign_line: html_builder.Html | None = None) -> html_builder.Html:
    n = len(view.cells)
    warned_items = [
        html_builder.el("li", None, f"{c.label}: {w.code} {w.message}")
        for c in view.cells for w in c.warnings
    ]
    if warned_items:  # R-24/R-26 c5, R-28: flags that do not change validity
        warnings_block = [
            html_builder.el("p", None, "Warnings:"),
            html_builder.el("ul", {"id": "validity-warnings"}, *warned_items),
        ]
    else:
        warnings_block = []

    if n and all(c.validity == "valid" for c in view.cells):
        body_elements = [
            html_builder.el("p", None, f"All {n} cells completed and are valid."),
            *warnings_block,
            *([campaign_line] if campaign_line else []),
        ]
        return html_builder.el("section", {"id": "validity"}, html_builder.el("h2", None, "Validity"), *body_elements)

    # Count exclusion classes according to section 6 row 2, each from the source that actually produces it --
    # never a hand-typed guess against a plausible-looking string:
    # NA costs · invalid · not applicable · timed out · stopped / skipped / never started · withheld · low-confidence matchers · disagreeing judges
    na_costs = sum(1 for c in view.cells if "cost_usd" in c.scores and c.scores["cost_usd"].value is None)
    # invalid: validity is the one source (views.py:435,437,441,446,450,454, all prefixed "invalid ("). A failed
    # *outcome* is not itself invalid: Cause.invalidates is true only for infrastructure/benchmark attributions
    # (errors.py:34-38), so an agent- or harness-attributed failure can still be a valid, scored cell.
    invalid = sum(1 for c in view.cells if c.validity.startswith("invalid"))
    # not applicable: no producer of this label exists anywhere in src/harness_bench. validity and outcome are
    # each a closed enumeration (views.py:117, :120) and neither lists it; no Cause label or RUN_CODES entry
    # (errors.py) names it either.
    # assume: the design's "not applicable" row has no current source in this codebase; confirm: a producer is
    # added under a named constant and this match is updated to it, or the design drops the row; breaks: this
    # class silently stays "not recorded" even after a producer exists, until this match is updated to it.
    not_applicable = None
    timed_out = sum(1 for c in view.cells if c.outcome == "timed_out")  # the outcome literal (views.py:117; engine.py:634,670)
    # stopped / skipped / never started: "stopped" (engine.py:634,654,669; status.py:288 checks the same
    # literal), lifecycle.SKIPPED (engine.py:362, a skip_combo decision), and the two never-launched states
    # views.py:507 produces when no cell.outcome was ever recorded ("not started" | "no outcome") -- the old
    # match dropped both never-launched states.
    stopped = sum(1 for c in view.cells if c.outcome in ("stopped", lifecycle.SKIPPED, "not started", "no outcome"))
    # withheld: the judge gateway's own withholding (WITHHELD_CODE == HB-GW-009, ruling R-80 c1), read off the
    # score's reason -- never the cell's own cause/code, which is a Cause label and never carries this text.
    withheld = sum(1 for c in view.cells if any(WITHHELD_CODE in (m.reason or "") for m in c.scores.values()))
    # low-confidence matchers: no producer of this text exists anywhere in src/harness_bench either -- checked
    # directly: scripted_user/matcher.py and grade/clarify.py write no such reason string, and a grep of the
    # whole package for "confidence" finds only this comment and the class label below.
    # assume: no matcher/clarifier grader flags a low-confidence match today; confirm: one is added with a named
    # reason string and this match is updated to it, or the design drops the row; breaks: this class silently
    # stays "not recorded" even after a producer exists, until this match is updated to it.
    lc_matchers = None
    # disagreeing judges: grade_judge.DISAGREE (judge.py:47, "judges disagree by 2 steps"), the one constant
    # metric_score composes into a score's reason (judge.py:200-207). With no such reason anywhere in the view,
    # this run is unmeasured for the class (no cell was judged, or none disagreed where a rubric ran) -- not
    # recorded, matching low-confidence matchers, never a bare 0 (the fixed bug: this used to fall back to 0).
    has_disagree_source = any(grade_judge.DISAGREE in (m.reason or "") for c in view.cells for m in c.scores.values())
    disagreeing_judges = sum(
        1 for c in view.cells if any(grade_judge.DISAGREE in (m.reason or "") for m in c.scores.values())
    ) if has_disagree_source else None

    classes = [
        *([(COST_NOT_COMPUTED, na_costs)] if na_costs else []),
        ("invalid", invalid),
        ("not applicable", not_applicable),
        ("timed out", timed_out),
        ("stopped / skipped / never started", stopped),
        ("withheld", withheld),
        ("low-confidence matchers", lc_matchers),
        ("disagreeing judges", disagreeing_judges),
    ]

    active_classes = [(label, count) for label, count in classes if count is not None and count > 0]

    items_spans = []
    if len(active_classes) > 5:
        for label, count in active_classes[:5]:
            items_spans.append(html_builder.el("a", {"href": "#runs"}, f"{count} {label}"))
        k_more = len(active_classes) - 5
        items_spans.append(f"and {k_more} more")
    else:
        for label, count in classes:
            if count is None:
                items_spans.append(f"{label}: not recorded")
            elif count > 0:
                items_spans.append(html_builder.el("a", {"href": "#runs"}, f"{count} {label}"))
            else:
                items_spans.append(f"0 {label}")

    p_children = []
    for i, item in enumerate(items_spans):
        if i > 0:
            p_children.append(" · ")
        p_children.append(item)
    summary_paragraph = html_builder.el("p", None, *p_children)

    counts: dict[str, int] = {}
    for c in view.cells:
        counts[c.validity] = counts.get(c.validity, 0) + 1
    items = [html_builder.el("li", None, f"{k}: {v}") for k, v in sorted(counts.items())]
    listed = [
        html_builder.el("li", None, f"{c.label}: {c.validity}" + (f" {c.validity_code}" if c.validity_code else ""))
        for c in view.cells if c.validity != "valid"
    ]

    state_elements = []
    if not view.completed:
        never_started = sum(1 for c in view.cells if c.outcome == "not started")
        state_elements.append(
            html_builder.el("p", None, f"The run is incomplete. {never_started} cells never started.")
        )

    body_elements = [
        *state_elements,
        summary_paragraph,
        html_builder.el("ul", None, *items),
        html_builder.el("p", None, "Cells that are not valid:"),
        html_builder.el("ul", None, *listed),
        *warnings_block,
        *([campaign_line] if campaign_line else []),
    ]
    return html_builder.el("section", {"id": "validity"}, html_builder.el("h2", None, "Validity"), *body_elements)


# R3 (design section 15, 6 row 3, 7): leaderboard interval bars, the evidence popover, and the Runs cell
# card, built on `html_builder.el` (escape by construction) rather than the `_e()`-in-f-string pattern
# `_table()` still uses for the sections R5 owns (pack effect, comparison, unchanged this slice).

COST_NOT_COMPUTED = "cost_usd: not computed; tokens are the cost axis (R-115)"

_UNIT = {"pass_at_1": "pass rate, 0-1", "gated": "correctness-gated composite, 0-100",
        "partial_credit": "partial credit, 0-1", "mutation_score": "mutation score, 0-1",
        "pass_hat_k": "pass^k rate, 0-1",
        "tokens_per_solved": "tokens per solved task, integer", "wall_ms": "wall clock, seconds",
        "tokens": "tokens, integer", "tool_ms": "tool time, milliseconds", "model_ms": "model time, milliseconds",
        "idle_ms": "idle time, milliseconds"}
_METRIC_LABEL = {"pass_at_1": "pass@1", "gated": "gated", "partial_credit": "partial credit",
                 "mutation_score": "mutation_score"}


def _popover(value_text: str, unit: str, catalog_version: str | None, evidence_content, cell_id: str | None) -> str:
    """Section 7's popover fields (raw value, unit, catalog version, evidence), plus an in-page link to the
    cell's own row when one exists. `hidden` until R4 wires the open/close behaviour (markup only, R3)."""
    fields = html_builder.el(
        "dl", {"class": "popover-fields"},
        html_builder.el("dt", None, "Value"), html_builder.el("dd", None, value_text),
        html_builder.el("dt", None, "Unit"), html_builder.el("dd", None, unit),
        html_builder.el("dt", None, "Catalog version"), html_builder.el("dd", None, catalog_version or "not recorded"),
        html_builder.el("dt", None, "Evidence"), html_builder.el("dd", None, evidence_content),
    )
    children = [fields]
    if cell_id:
        children.append(html_builder.el("a", {"href": f"#cell-{cell_id}"}, "Show cell"))
    return html_builder.el("span", {"class": "popover", "hidden": True}, *children)


def _ev(value_text: str, na: bool, unit: str, catalog_version: str | None, evidence_content, cell_id: str | None) -> str:
    """One evidence trigger (design section 7): a `button.ev` holding the formatted value, with its popover
    as an adjacent, still-hidden sibling (R4 wires open/close; R3 ships the markup)."""
    btn = html_builder.el("button", {"class": "ev na" if na else "ev", "type": "button"}, value_text)
    pop = _popover(value_text, unit, catalog_version, evidence_content, cell_id)
    return html_builder.trusted(btn + pop)


def _evidence_content(c: views.CellView, metric: str, archive_present: bool):
    """US-41: `<code>` evidence pointer with the archive, the exact section 9 copy without it, `none`
    without a pointer. Returns `Html` or a plain `str` -- either is a safe child of `html_builder.el`."""
    pointer = c.evidence.get(metric)
    if not pointer:
        return "none"
    if archive_present:
        return html_builder.el("code", None, pointer)
    return f"This copy doesn't include the run archive. Evidence path: {pointer}."


def _interval_mark(iv, decimals: int) -> str:
    """UIA-5: one element per (row, measure), carrying `data-interval-lo/hi` when computed or the reason
    text otherwise -- never `0` for missing. The cardinality floor (`ivmark`) is the shared marker class."""
    if iv.lo is not None and iv.hi is not None:
        text = html_builder.el("span", None, f"[{iv.lo:.{decimals}f}, {iv.hi:.{decimals}f}]")
        svg_attrs = {"class": "ivbar ivmark", "width": "64", "height": "12", "viewBox": "0 0 64 12",
                    "aria-hidden": "true", "data-interval-lo": f"{iv.lo:.{decimals}f}",
                    "data-interval-hi": f"{iv.hi:.{decimals}f}"}
        if iv.point is not None:  # never invent a point from lo when none was computed (Leader R3 join note)
            svg_attrs["data-interval-point"] = f"{iv.point:.{decimals}f}"
        bar = html_builder.el("svg", svg_attrs, html_builder.el("line", {"x1": "4", "x2": "60", "y1": "6", "y2": "6"}))
        return html_builder.trusted(text + bar)
    return html_builder.el("span", {"class": "ivbar-reason ivmark"}, iv.reason or "interval not computed")


def _show_cells_link(combo: str, pack: str) -> html_builder.Html:
    """R4: the popover's "Show cells" link, now combo/pack-aware -- `report.js` reads
    `data-runs-combo`/`data-runs-pack` to filter Runs to this row's cells before the in-page jump
    (design section 15 R4's own done-when: "the leaderboard's Show cells link filtering Runs")."""
    return html_builder.el("a", {"href": "#runs", "data-runs-combo": combo, "data-runs-pack": pack}, "Show cells")


def _lb_measure_cells(iv, metric: str, decimals: int, catalog_version: str | None, combo: str, pack: str,
                      sort_key: str | None = None) -> tuple[str, str]:
    """The point cell (an evidence-trigger button; DR-R aggregates have no single cell evidence pointer, so
    its popover's cross-link is `#runs` -- `assume:` a board row's evidence is "the cells behind it", not
    one pointer; confirmed by R4 wiring that link to filter Runs on this row's combo/pack; if false, the
    link is merely inert until R4, no regression, since script-src stays 'none' until then) and the
    interval-or-reason cell (UIA-5). `sort_key`/`data-sort-value` (R4) let `report.js` sort this column
    without re-parsing formatted text; NA carries no `data-sort-value`, so it always sorts last."""
    na = iv.point is None
    text = f"{iv.point:.{decimals}f}" if not na else (f"NA ({iv.reason})" if iv.reason else "NA")
    evidence = _show_cells_link(combo, pack)
    point_attrs: dict[str, object] = {"class": "num"}
    if sort_key:
        point_attrs["data-sort"] = sort_key
        if not na:
            point_attrs["data-sort-value"] = f"{iv.point:.6f}"
    point_td = html_builder.el("td", point_attrs, html_builder.trusted(
        _ev(text, na, _UNIT.get(metric, ""), catalog_version, evidence, None)))
    interval_td = html_builder.el("td", None, html_builder.trusted(_interval_mark(iv, decimals)))
    return point_td, interval_td


def _lb_measure_ev_cell(measure, metric: str, formatter, catalog_version: str | None, combo: str, pack: str,
                        sort_key: str | None = None) -> str:
    """A leaderboard `Measure` column (pass^k, cost-of-pass, tokens per solved, wall per cell) as an
    evidence-trigger button (design section 6 row 3: every displayed score is `.ev`). The cross-link is
    `#runs`, the same board-row-aggregate `assume:` `_lb_measure_cells` documents above."""
    na = measure.value is None
    text = formatter(measure)
    evidence = _show_cells_link(combo, pack)
    attrs: dict[str, object] = {"class": "num"}
    if sort_key:
        attrs["data-sort"] = sort_key
        if not na:
            attrs["data-sort-value"] = str(measure.value)
    return html_builder.el("td", attrs, html_builder.trusted(
        _ev(text, na, _UNIT.get(metric, ""), catalog_version, evidence, None)))


def _rank_cell(r: board.BoardRow) -> str:
    """Design section 6 row 3: a tied rank shows `1=`, with `(intervals overlap)` on focus. Chosen shape:
    the rank cell's own `ev` popover (button.ev holding the rank text, a hidden popover holding the design's
    exact tie copy) -- the same on-focus-reveal pattern every other score uses here, not the generic
    value/unit/catalog-version shape (a tie has no raw value to disclose). An untied rank or the unranked
    mark ("—") is plain text: there is nothing to reveal."""
    if not r.rank:
        return html_builder.el("td", None, "—")
    if r.rank.endswith("="):
        btn = html_builder.el("button", {"class": "ev", "type": "button"}, r.rank)
        pop = html_builder.el("span", {"class": "popover", "hidden": True}, "(intervals overlap)")
        return html_builder.el("td", None, html_builder.trusted(btn + pop))
    return html_builder.el("td", None, r.rank)


def _measure_label(board_obj: board.Board) -> str:
    return "correctness-gated composite" if board_obj.primary == "gated" else "pass@1"


# R4 (design section 15, 5, 6): report.js, its markup (the combo legend, the pack switch, the Runs
# filters, the sort buttons) and the browser ring (DR-R-9).


def _combo_index(board_obj: board.Board) -> dict[str, str]:
    """combo -> "c1".."c8" in first-appearance order over `board_obj.rows` -- the same token
    vocabulary the categorical palette uses (design section 3: "in matrix order"; beyond 8 it
    cycles, so a 9th distinct combo reuses c1's slot for the legend/filter classes only, never for
    colour -- no report renderer paints by this index yet, R5/R6 own colour)."""
    order: dict[str, str] = {}
    for r in board_obj.rows:
        if r.combo not in order:
            order[r.combo] = f"c{len(order) % 8 + 1}"
    return order


def _combo_label(combo: str, harness: str) -> str:
    """The combo's own display label -- exactly the text the leaderboard's Combo column shows
    (`_leaderboard`'s `combo_text`), factored out so the control bar's legend (below) names the same
    thing rather than re-deriving it. Used only inside a real `<section>` (Leaderboard, Runs, and now
    `controls`), so a flagged or canary-shaped combo name stays inside `_publish`'s per-section scan."""
    return report.flag_if_claude_code(report.flag_if_codex(combo, harness), harness)


def _control_bar(board_obj: board.Board, combo_ix: dict[str, str]) -> html_builder.Html:
    """The sticky control bar (design section 6): the combo legend (`aria-pressed`, one button per
    combo, its own label per UXA-5) and the pack switch (`both`/`on`/`off`, `aria-disabled` for a
    setting this run lacks, each with its own reason node -- design gate round 2's UX fix, never one
    shared node). JS (R4) owns the interaction; this function only emits the markup and the initial
    disabled state.

    Rendered as `<section id="controls">` -- the bar's *only* attribute, matching `_SECTION`'s regex
    (`<section id="([a-z0-9-]+)">`, US-47 c3) exactly, the same shape every other section carries --
    so `_publish` scans and, on a hit, withholds it as a unit through the same generic per-section
    path every other section already goes through: no `_publish`/`_SECTION` change needed. It is not a
    `model.Section` (it carries no jump link and never joins the section-id/IA order); `model.page`
    inserts it after the nav, still structurally the "sticky bar right under the header" design
    section 6 asks for. Styling and the `role="group"` landmarks live on its *children*, never on the
    section tag itself, so a second attribute there never breaks the scan (confirmed by
    `tests/test_injection_and_publication.py::test_report_publication_withholds_each_section_carrying_a_planted_canary...`).
    """
    combo_harness: dict[str, str] = {}
    for r in board_obj.rows:
        combo_harness.setdefault(r.combo, r.harness)
    legend_buttons = [
        html_builder.el(
            "button", {"class": "tg", "type": "button", "aria-pressed": "true", "data-combo": ix},
            _combo_label(combo, combo_harness[combo]),
        )
        for combo, ix in combo_ix.items()
    ]
    legend = html_builder.el("div", {"role": "group", "aria-label": "Combos", "id": "legend"}, *legend_buttons)

    packs_present = sorted({r.pack for r in board_obj.rows})
    reason_children: list[html_builder.Html] = []
    pack_buttons = []
    for setting in ("both", *_arm_order(packs_present)):
        attrs: dict[str, object] = {"class": "tg", "type": "button", "data-pack": setting,
                                    "aria-pressed": "true" if setting == "both" else "false"}
        lacks = setting != "both" and setting not in packs_present
        one_setting_only = len(packs_present) == 1 and setting == "both"
        if lacks or one_setting_only:
            only = packs_present[0] if packs_present else "neither"
            reason_id = f"reason-pack-{setting}"
            attrs["aria-disabled"] = "true"
            attrs["aria-describedby"] = reason_id
            reason_children.append(html_builder.el("p", {"id": reason_id}, f"This run has pack {only} only."))
        pack_buttons.append(html_builder.el("button", attrs, setting))
    pack_switch = html_builder.el("div", {"role": "group", "aria-label": "Pack setting", "id": "pack-switch"}, *pack_buttons)
    reasons = html_builder.el("div", {"class": "small", "id": "bar-reasons", "aria-live": "polite"}, *reason_children)

    return html_builder.el(
        "section", {"id": "controls"},
        legend, pack_switch, reasons,
    )


def _leaderboard(view: views.RunView, board_obj: board.Board) -> str:
    if not any(c.outcome == "completed" for c in view.cells):
        return html_builder.el(
            "section", {"id": "leaderboard"}, html_builder.el("h2", None, "Leaderboard"),
            html_builder.el("p", None, f"No cell completed in this run. Run bench status {view.run_id} to see why."),
        )
    caption = f"Ranked on {_measure_label(board_obj)}. Rows that share a rank cannot be separated by this data."
    # Design section 6 row 3's order: rank · combo · pack · gated ± interval · pass@1 ± interval · pass^k ·
    # cost-of-pass · tokens per solved · wall per cell · valid cells (Leader R3 join note).
    # R4: a sort key per sortable column ("Sort buttons sit in the column headers", design section 6 row 3);
    # None for the four columns that are not sortable measures (Rank has its own tie affordance, Combo/Pack
    # are dimensions, not measures).
    headers = [("Rank", False, None), ("Combo", False, None), ("Pack", False, None), ("Gated", True, "gated"),
               ("Gated 95%", False, None), ("pass@1", True, "pass_at_1"), ("pass@1 95%", False, None),
               ("pass^k", True, "pass_hat_k"),
               ("Tokens per solved", True, "tokens_per_solved"), ("Wall per cell", True, "wall_ms"),
               ("Valid cells", True, "n_valid")]
    head_cells = []
    for h, num, sort_key in headers:
        label = html_builder.el("button", {"class": "sort", "type": "button", "data-sort-key": sort_key}, h) if sort_key else h
        head_cells.append(html_builder.el("th", {"scope": "col", "class": "num"} if num else {"scope": "col"}, label))
    head_row = html_builder.el("tr", None, *head_cells)
    frontier_by_key = {(fr.combo, fr.pack): fr for fr in board_obj.frontier}
    no_solved = stats.Measure(None, "not recorded")
    combo_ix = _combo_index(board_obj)

    body_rows = []
    for r in board_obj.rows:
        combo_text = _combo_label(r.combo, r.harness)
        g_td, g_iv_td = _lb_measure_cells(r.gated, "gated", 1, view.catalog_version, r.combo, r.pack, "gated")
        p1_td, p1_iv_td = _lb_measure_cells(r.pass_at_1, "pass_at_1", 2, view.catalog_version, r.combo, r.pack, "pass_at_1")
        tokens_per_solved = frontier_by_key.get((r.combo, r.pack))
        tokens_per_solved = tokens_per_solved.tokens_per_solved if tokens_per_solved is not None else no_solved
        row_attrs = {"data-combo": combo_ix[r.combo], "data-pack": r.pack}
        body_rows.append(html_builder.el(
            "tr", row_attrs,
            _rank_cell(r),
            html_builder.el("td", None, combo_text),
            html_builder.el("td", None, r.pack),
            html_builder.trusted(g_td), html_builder.trusted(g_iv_td),
            html_builder.trusted(p1_td), html_builder.trusted(p1_iv_td),
            html_builder.trusted(_lb_measure_ev_cell(r.pass_hat_k, "pass_hat_k", report.rate, view.catalog_version, r.combo, r.pack, "pass_hat_k")),
            html_builder.trusted(_lb_measure_ev_cell(tokens_per_solved, "tokens_per_solved", report.tokens, view.catalog_version, r.combo, r.pack, "tokens_per_solved")),
            html_builder.trusted(_lb_measure_ev_cell(r.wall_ms, "wall_ms", report.seconds, view.catalog_version, r.combo, r.pack, "wall_ms")),
            html_builder.el("td", {"class": "num", "data-sort": "n_valid", "data-sort-value": str(r.n_valid)}, f"{r.n_valid}/{r.n_cells} cells"),
        ))
    table = html_builder.el(
        "table", {"id": "leaderboard-table"},
        html_builder.el("caption", {"id": "leaderboard-caption"}, caption),
        html_builder.el("thead", None, head_row),
        html_builder.el("tbody", {"id": "leaderboard-body"}, *body_rows),
    )
    region = html_builder.el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "leaderboard-caption"}, table)

    parts = [html_builder.el("h2", None, "Leaderboard")]
    ranked_all_tied = bool(board_obj.rows) and all(r.rank in ("1", "1=") for r in board_obj.rows)  # section 9 copy
    if ranked_all_tied:
        parts.append(html_builder.el(
            "p", None, f"All {len(board_obj.rows)} rows share rank 1: their intervals overlap, "
                       "so this run cannot separate them."))
    parts.append(region)
    for r in board_obj.rows:
        if not r.rank and r.rank_reason:  # unranked row: the design's "—" mark plus this footnote
            parts.append(html_builder.el("p", None, f"{r.combo} {r.pack}: {r.rank_reason}"))
        if r.footnote:
            parts.append(html_builder.el("p", None, f"{r.combo} {r.pack}: {r.footnote}"))
    return html_builder.el("section", {"id": "leaderboard"}, *parts)


def _mark_class_and_label(delta: stats.Interval, raw_label: str | None = None) -> tuple[str, str]:
    """Design section 6 row 4: the dot takes --div-pos or --div-neg by sign, or --ink-2
    when the interval crosses 0 and is then labelled 'no detectable effect (interval crosses 0)'."""
    if delta.lo is not None and delta.hi is not None and delta.lo <= 0 <= delta.hi:
        return "nde", "no detectable effect (interval crosses 0)"
    cls = "pos" if (delta.point is not None and delta.point > 0) else "neg"
    return cls, raw_label or ""


def _whisker_panel(
    panel_id: str,
    cap_id: str,
    panel_label: str,
    rows: list,
    limit: float,
    is_comparison: bool,
    combo_ix: dict[str, str],
) -> html_builder.Html:
    """One unit's dot-and-whisker panel on its own shared zero line (design s6 rows 4 and 11:
    'the marks of one measure family share a zero' -- not a scale shared across incomparable
    units). `limit` is this panel's own axis limit: 1.0 for the pass@1 share, or the panel's own
    0-100+ point scale for everything else (composite/area measures)."""
    if limit <= 1.0:
        ticks = [-1.0, -0.5, 0.5, 1.0]
        tick_labels = ["-1.0", "-0.5", "+0.5", "+1.0"]
    else:
        ticks = [-100.0, -50.0, 50.0, 100.0] if limit == 100.0 else [-limit, -limit / 2, limit / 2, limit]
        tick_labels = [f"{t:+.0f}" for t in ticks]

    x_zero = 300
    scale = 220.0 / limit

    def x(val: Decimal | float) -> float:
        return x_zero + float(val) * scale

    row_height = 32
    y_start = 30
    y_bottom = y_start + len(rows) * row_height
    svg_height = y_bottom + 30

    svg_children: list[html_builder.Html] = []

    # Axis (this panel's own shared zero line)
    svg_children.append(
        html_builder.el("line", {
            "x1": str(x_zero),
            "x2": str(x_zero),
            "y1": "10",
            "y2": str(y_bottom),
            "class": "axis",
        })
    )

    # Grid lines and tick labels
    for t, label in zip(ticks, tick_labels):
        xt = round(x(t), 1)
        svg_children.append(
            html_builder.el("line", {
                "x1": str(xt),
                "x2": str(xt),
                "y1": "10",
                "y2": str(y_bottom),
                "class": "grid",
            })
        )
        svg_children.append(
            html_builder.el("text", {
                "x": str(round(xt - 12, 1)),
                "y": str(y_bottom + 15),
            }, label)
        )

    # Zero label
    svg_children.append(
        html_builder.el("text", {
            "x": str(x_zero - 4),
            "y": str(y_bottom + 15),
        }, "0")
    )

    # Marks for each row in this panel
    for i, r in enumerate(rows):
        y = y_start + i * row_height
        is_p1 = r.measure == "pass_at_1"
        decimals = 2 if is_p1 else 1

        lo_str = f"{r.delta.lo:.{decimals}f}"
        hi_str = f"{r.delta.hi:.{decimals}f}"
        pt_str = f"{r.delta.point:.{decimals}f}"
        cls, _ = _mark_class_and_label(r.delta, getattr(r, "label", None))

        if is_comparison and hasattr(r, "pack"):
            label_text = f"{r.combo} {r.pack} {r.measure}" if r.measure != "pass_at_1" else f"{r.combo} {r.pack}"
        else:
            label_text = f"{r.combo} {r.measure}" if r.measure != "pass_at_1" else r.combo

        # `data-combo` is this combo's legend token (c1..c8 from the map `render` passed in).
        # Comparison marks also carry `data-pack`. Pack effect is the difference of the two
        # settings, so its marks do not: the pack switch disables itself instead of hiding them.
        mark_attrs: dict[str, object] = {}
        token = combo_ix.get(r.combo)
        if token is not None:
            mark_attrs["data-combo"] = token
        if is_comparison and hasattr(r, "pack"):
            mark_attrs["data-pack"] = r.pack

        label_attrs: dict[str, object] = {"x": "4", "y": str(y + 4)}
        label_attrs.update(mark_attrs)
        svg_children.append(html_builder.el("text", label_attrs, label_text))

        x1 = round(x(min(r.delta.lo, r.delta.hi)), 1)
        x2 = round(x(max(r.delta.lo, r.delta.hi)), 1)
        whisker_attrs: dict[str, object] = {
            "x1": str(x1),
            "x2": str(x2),
            "y1": str(y),
            "y2": str(y),
            "class": f"{cls} whisk",
            "data-interval-lo": lo_str,
            "data-interval-hi": hi_str,
            "data-interval-point": pt_str,
        }
        whisker_attrs.update(mark_attrs)
        dot_attrs: dict[str, object] = {
            "cx": str(round(x(r.delta.point), 1)),
            "cy": str(y),
            "r": "5",
            "class": cls,
            "data-interval-lo": lo_str,
            "data-interval-hi": hi_str,
            "data-interval-point": pt_str,
        }
        dot_attrs.update(mark_attrs)
        svg_children.extend([
            html_builder.el("line", whisker_attrs),
            html_builder.el("circle", dot_attrs),
        ])

    return html_builder.el("svg", {
        "id": f"{panel_id}-svg",
        "role": "img",
        "aria-labelledby": cap_id,
        "aria-label": panel_label,
        "viewBox": f"0 0 560 {svg_height}",
        "width": "100%",
    }, *svg_children)


def _whisker_chart(
    tid: str,
    title: str,
    rows: Sequence[board.PackEffectRow | board.ComparisonRow],
    combo_ix: dict[str, str],
    is_comparison: bool = False,
) -> html_builder.Html | None:
    computed_rows = [
        r for r in rows
        if r.delta.lo is not None and r.delta.hi is not None and r.delta.point is not None
    ]
    if not computed_rows:
        return None

    # One panel per unit (design s6 rows 4 and 11): pass@1 deltas are shares (-1..1); every other
    # measure (composite/area) is a 0-100-point delta. Incomparable units never share a scale --
    # pass@1 panel first, then the points panel, each on its own axis.
    p1_rows = [r for r in computed_rows if r.measure == "pass_at_1"]
    point_rows = [r for r in computed_rows if r.measure != "pass_at_1"]

    cap_id = f"{tid}-cap"
    panels: list[html_builder.Html] = []
    if p1_rows:
        panels.append(_whisker_panel(f"{tid}-p1", cap_id, "pass@1, as a share of tasks", p1_rows, 1.0, is_comparison, combo_ix))
    if point_rows:
        max_val = max(
            max(abs(float(r.delta.lo)), abs(float(r.delta.hi)), abs(float(r.delta.point)))
            for r in point_rows
        )
        limit = max(100.0, max_val)
        panels.append(_whisker_panel(f"{tid}-pts", cap_id, "composite and area, 0-100 points", point_rows, limit, is_comparison, combo_ix))

    caption = html_builder.el("figcaption", {"id": cap_id}, title)
    return html_builder.el("figure", None, html_builder.el("div", {"class": "chart-panels"}, *panels), caption)


def _delta_table(
    rows: Sequence[board.PackEffectRow | board.ComparisonRow],
    caption_id: str,
    caption_text: str,
    has_pack: bool,
    combo_ix: dict[str, str],
) -> html_builder.Html:
    """The pack effect and comparison table alternatives share every column but Pack (design
    section 5 names this duplication as the thing the model/builder split removes); `has_pack`
    is the one difference between them."""
    headers = [("Combo", False)]
    if has_pack:
        headers.append(("Pack", False))
    headers += [("Measure", False), ("Delta", True), ("95% Interval", False), ("Label", False)]
    head_tr = html_builder.el("tr", None, *(
        html_builder.el("th", {"scope": "col", "class": "num"} if is_num else {"scope": "col"}, h)
        for h, is_num in headers
    ))
    tr_list = []
    for r in rows:
        is_p1 = r.measure == "pass_at_1"
        decimals = 2 if is_p1 else 1
        row_reason = getattr(r, "reason", None)
        row_cells = [html_builder.el("td", None, r.combo)]
        if has_pack:
            row_cells.append(html_builder.el("td", None, r.pack))
        row_cells.append(html_builder.el("td", None, r.measure))

        if r.delta.point is not None:
            delta_str = f"{r.delta.point:+.{decimals}f}"
            delta_attrs = {"class": "num", "data-interval-point": f"{r.delta.point:.{decimals}f}"}
            if r.delta.lo is not None and r.delta.hi is not None:
                delta_attrs["data-interval-lo"] = f"{r.delta.lo:.{decimals}f}"
                delta_attrs["data-interval-hi"] = f"{r.delta.hi:.{decimals}f}"
            delta_td = html_builder.el("td", delta_attrs, delta_str)
        else:
            delta_str = row_reason or r.delta.reason or "NA"
            delta_td = html_builder.el("td", {"class": "num na"}, delta_str)
        row_cells.append(delta_td)

        if r.delta.lo is not None and r.delta.hi is not None:
            iv_str = f"[{r.delta.lo:.{decimals}f}, {r.delta.hi:.{decimals}f}]"
            iv_attrs = {
                "data-interval-lo": f"{r.delta.lo:.{decimals}f}",
                "data-interval-hi": f"{r.delta.hi:.{decimals}f}",
            }
            if r.delta.point is not None:
                iv_attrs["data-interval-point"] = f"{r.delta.point:.{decimals}f}"
            iv_td = html_builder.el("td", iv_attrs, iv_str)
        else:
            iv_str = row_reason or r.delta.reason or "interval not computed"
            iv_td = html_builder.el("td", {"class": "na"}, iv_str)
        row_cells.append(iv_td)

        _, label_str = _mark_class_and_label(r.delta, r.label)
        row_cells.append(html_builder.el("td", None, label_str))

        row_attrs: dict[str, object] = {}
        row_token = combo_ix.get(r.combo)
        if row_token is not None:
            row_attrs["data-combo"] = row_token
        if has_pack:
            row_attrs["data-pack"] = r.pack
        tr_list.append(html_builder.el("tr", row_attrs, *row_cells))

    table = html_builder.el(
        "table", None,
        html_builder.el("caption", {"id": caption_id}, caption_text),
        html_builder.el("thead", None, head_tr),
        html_builder.el("tbody", None, *tr_list),
    )
    region = html_builder.el(
        "div",
        {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": caption_id},
        table,
    )
    return html_builder.el("details", None, html_builder.el("summary", None, "Table"), region)


def _pack_effect_table(rows: list[board.PackEffectRow], combo_ix: dict[str, str],
                       pair: tuple[str, str] = board.LEGACY_PAIR) -> html_builder.Html:
    if pair == board.LEGACY_PAIR:
        return _delta_table(rows, "pack-effect-caption", "Pack effect per combo and area", has_pack=False, combo_ix=combo_ix)
    ref, treat = pair
    return _delta_table(rows, f"pack-effect-{ref}-{treat}-caption", f"Pack effect per combo and area, {ref} vs {treat}",
                        has_pack=False, combo_ix=combo_ix)


def _pack_effect(board_obj: board.Board, combo_ix: dict[str, str]) -> html_builder.Html:
    pe = board_obj.pack_effect
    excl = html_builder.el("p", None, pe.exclusion_line)
    if pe.status is not None:
        body = html_builder.el("p", None, pe.status)
        return html_builder.el("section", {"id": "pack-effect"}, html_builder.el("h2", None, "Pack effect"), excl, body)
    if not pe.rows:
        body = html_builder.el("p", None, "No pack effect data.")
        return html_builder.el("section", {"id": "pack-effect"}, html_builder.el("h2", None, "Pack effect"), excl, body)

    by_pair: dict[tuple[str, str], list[board.PackEffectRow]] = {}
    for r in pe.rows:
        by_pair.setdefault(r.pair, []).append(r)
    children = [html_builder.el("h2", None, "Pack effect"), excl]
    for pair, rows in by_pair.items():
        legacy = pair == board.LEGACY_PAIR
        ref, treat = pair
        tid = "pack-effect" if legacy else f"pack-effect-{ref}-{treat}"
        title = "Pack effect per combo and area on a shared zero line" + ("" if legacy else f", {ref} vs {treat}")
        chart = _whisker_chart(tid, title, rows, combo_ix)
        if len(by_pair) > 1:
            children.append(html_builder.el("h3", None, f"{ref} vs {treat}"))
        if chart is not None:
            children.append(chart)
        children.append(_pack_effect_table(rows, combo_ix, pair))
    return html_builder.el("section", {"id": "pack-effect"}, *children)


def _marker_shape(
    shape_num: int,
    cx: float,
    cy: float,
    combo_token: str,
    is_hollow: bool,
    attrs: Mapping[str, object] | None = None,
) -> html_builder.Html:
    cls = f"mk-{combo_token}" + (" hollow" if is_hollow else "")
    el_attrs = dict(attrs or {})
    el_attrs["class"] = cls
    s = (shape_num - 1) % 8 + 1
    if s == 1:
        el_attrs["cx"] = str(round(cx, 1))
        el_attrs["cy"] = str(round(cy, 1))
        el_attrs["r"] = "5"
        return html_builder.el("circle", el_attrs)
    if s == 2:
        el_attrs["x"] = str(round(cx - 5, 1))
        el_attrs["y"] = str(round(cy - 5, 1))
        el_attrs["width"] = "10"
        el_attrs["height"] = "10"
        return html_builder.el("rect", el_attrs)
    if s == 3:
        el_attrs["d"] = f"M{round(cx, 1)} {round(cy - 6, 1)} L{round(cx + 6, 1)} {round(cy + 5, 1)} L{round(cx - 6, 1)} {round(cy + 5, 1)} Z"
        return html_builder.el("path", el_attrs)
    if s == 4:
        el_attrs["d"] = f"M{round(cx, 1)} {round(cy - 6, 1)} L{round(cx + 6, 1)} {round(cy, 1)} L{round(cx, 1)} {round(cy + 6, 1)} L{round(cx - 6, 1)} {round(cy, 1)} Z"
        return html_builder.el("path", el_attrs)
    if s == 5:
        el_attrs["d"] = f"M{round(cx - 6, 1)} {round(cy - 5, 1)} L{round(cx + 6, 1)} {round(cy - 5, 1)} L{round(cx, 1)} {round(cy + 6, 1)} Z"
        return html_builder.el("path", el_attrs)
    if s == 6:
        el_attrs["d"] = f"M{round(cx - 5, 1)} {round(cy, 1)} L{round(cx + 5, 1)} {round(cy, 1)} M{round(cx, 1)} {round(cy - 5, 1)} L{round(cx, 1)} {round(cy + 5, 1)}"
        el_attrs["stroke-width"] = "2"
        return html_builder.el("path", el_attrs)
    if s == 7:
        el_attrs["d"] = f"M{round(cx - 4, 1)} {round(cy - 4, 1)} L{round(cx + 4, 1)} {round(cy + 4, 1)} M{round(cx - 4, 1)} {round(cy + 4, 1)} L{round(cx + 4, 1)} {round(cy - 4, 1)}"
        el_attrs["stroke-width"] = "2"
        return html_builder.el("path", el_attrs)
    star_pts = (
        f"{round(cx, 1)},{round(cy - 6, 1)} {round(cx + 2, 1)},{round(cy - 2, 1)} {round(cx + 6, 1)},{round(cy - 2, 1)} "
        f"{round(cx + 3, 1)},{round(cy + 1, 1)} {round(cx + 4, 1)},{round(cy + 5, 1)} {round(cx, 1)},{round(cy + 2, 1)} "
        f"{round(cx - 4, 1)},{round(cy + 5, 1)} {round(cx - 3, 1)},{round(cy + 1, 1)} {round(cx - 6, 1)},{round(cy - 2, 1)} "
        f"{round(cx - 2, 1)},{round(cy - 2, 1)}"
    )
    el_attrs["points"] = star_pts
    return html_builder.el("polygon", el_attrs)


def _cost_frontier_panel(
    panel_title: str,
    metric_label: str,
    rows: Sequence[board.FrontierRow],
    metric_getter: Callable[[board.FrontierRow], tuple[float | None, str | None, str]],
    combo_ix: dict[str, str],
) -> html_builder.Html:
    valid_points: list[tuple[board.FrontierRow, float, str, float]] = []
    for r in rows:
        val, val_raw, _ = metric_getter(r)
        p1 = float(r.pass_at_1.point) if r.pass_at_1.point is not None else None
        if val is not None and p1 is not None:
            valid_points.append((r, val, val_raw, p1))

    if not valid_points:
        return html_builder.el(
            "figure", None,
            html_builder.el("p", {"class": "na"}, f"{metric_label} not recorded for any combo."),
            html_builder.el("figcaption", None, f"pass@1 vs {metric_label} (no axes drawn)"),
        )

    x_vals = [p[1] for p in valid_points]
    min_x = min(x_vals)
    max_x = max(x_vals)
    if min_x == max_x:
        min_x = 0.0
        max_x = max(1.0, max_x * 1.2)

    def x_scale(v: float) -> float:
        return 45.0 + ((v - min_x) / (max_x - min_x)) * 255.0

    def y_scale(p1: float) -> float:
        return 165.0 - (p1 * 145.0)

    svg_children: list[html_builder.Html] = [
        html_builder.el("line", {"x1": "45", "y1": "20", "x2": "45", "y2": "165", "class": "axis"}),
        html_builder.el("line", {"x1": "45", "y1": "165", "x2": "300", "y2": "165", "class": "axis"}),
        html_builder.el("text", {"x": "4", "y": "24"}, "1.00"),
        html_builder.el("text", {"x": "4", "y": "169"}, "0.00"),
        html_builder.el("text", {"x": "45", "y": "185"}, f"{min_x:.1f}"),
        html_builder.el("text", {"x": "250", "y": "185"}, f"{max_x:.1f}"),
    ]

    # Pareto step line: sort by x ascending
    pareto_pts: list[tuple[float, float]] = []
    max_p1 = -1.0
    for _, val, _, p1 in sorted(valid_points, key=lambda p: (p[1], -p[3])):
        if p1 > max_p1:
            max_p1 = p1
            pareto_pts.append((x_scale(val), y_scale(p1)))

    if len(pareto_pts) >= 2:
        step_coords: list[tuple[float, float]] = []
        for i, (cx, cy) in enumerate(pareto_pts):
            if i == 0:
                step_coords.append((cx, cy))
            else:
                _, prev_cy = pareto_pts[i - 1]
                step_coords.append((cx, prev_cy))
                step_coords.append((cx, cy))
        step_points_str = " ".join(f"{round(x, 1)},{round(y, 1)}" for x, y in step_coords)
        svg_children.append(html_builder.el("polyline", {"points": step_points_str, "class": "grid step", "fill": "none", "stroke-width": "1"}))

    # Whiskers and markers
    for r, val, val_raw, p1 in valid_points:
        cx = round(x_scale(val), 1)
        combo_token = combo_ix[r.combo]  # every board combo has a legend token; a miss is a defect, never c1
        p1_pt_str = f"{p1:.2f}"
        lo_str = f"{r.pass_at_1.lo:.2f}" if r.pass_at_1.lo is not None else None
        hi_str = f"{r.pass_at_1.hi:.2f}" if r.pass_at_1.hi is not None else None

        if r.pass_at_1.lo is not None and r.pass_at_1.hi is not None:
            y_lo = round(y_scale(float(r.pass_at_1.lo)), 1)
            y_hi = round(y_scale(float(r.pass_at_1.hi)), 1)
            whisker_attrs = {
                "x1": str(cx),
                "y1": str(min(y_lo, y_hi)),
                "x2": str(cx),
                "y2": str(max(y_lo, y_hi)),
                "class": f"mk-{combo_token} whisk" + (" dash" if r.pack == config.ARM_OFF else ""),
                "data-combo": combo_token,
                "data-pack": r.pack,
                "data-interval-lo": lo_str,
                "data-interval-hi": hi_str,
                "data-interval-point": p1_pt_str,
            }
            svg_children.append(html_builder.el("line", whisker_attrs))

        cy = round(y_scale(p1), 1)
        shape_idx = int(combo_token[1:]) if len(combo_token) > 1 and combo_token[1:].isdigit() else 1
        mark_attrs: dict[str, object] = {
            "data-combo": combo_token,
            "data-pack": r.pack,
            "data-interval-point": p1_pt_str,
            "data-value": val_raw,
        }
        if lo_str is not None and hi_str is not None:
            mark_attrs["data-interval-lo"] = lo_str
            mark_attrs["data-interval-hi"] = hi_str

        svg_children.append(_marker_shape(shape_idx, cx, cy, combo_token, r.pack == config.ARM_OFF, mark_attrs))

    svg = html_builder.el("svg", {
        "role": "img",
        "aria-label": f"pass@1 against {metric_label}",
        "viewBox": "0 0 320 200",
        "width": "100%",
    }, *svg_children)

    fig_children = [svg, html_builder.el("figcaption", None, panel_title)]
    omitted = len(rows) - len(valid_points)
    if omitted > 0:
        fig_children.append(html_builder.el("p", {"class": "small muted"}, f"{omitted} combos not plotted: not recorded"))

    return html_builder.el("figure", None, *fig_children)


def _cost_frontier(view: views.RunView, board_obj: board.Board, combo_ix: dict[str, str]) -> html_builder.Html:
    if not any(c.outcome == "completed" for c in view.cells) or not board_obj.frontier:
        return html_builder.el(
            "section", {"id": "cost-frontier"},
            html_builder.el("h2", None, "Cost frontier"),
            html_builder.el("p", {"class": "st"}, "No completed cells to plot."),
        )

    # 1. Tokens panel (tokens are the cost axis, R-115)
    def get_tokens(r: board.FrontierRow) -> tuple[float | None, str | None, str]:
        v = float(r.tokens_per_solved.value) if r.tokens_per_solved.value is not None else None
        return v, str(r.tokens_per_solved.value) if r.tokens_per_solved.value is not None else None, "tokens"
    tokens_fig = _cost_frontier_panel("pass@1 vs tokens per solved task", "tokens per solved", board_obj.frontier, get_tokens, combo_ix)

    # 2. Wall panel
    def get_wall(r: board.FrontierRow) -> tuple[float | None, str | None, str]:
        if r.wall_per_task.value is not None:
            s_val = float(r.wall_per_task.value) / 1000.0
            return s_val, f"{s_val:.1f}", "wall"
        return None, None, "wall"
    wall_fig = _cost_frontier_panel("pass@1 vs wall per task (s)", "wall per task", board_obj.frontier, get_wall, combo_ix)

    charts_div = html_builder.el("div", {"class": "charts"}, tokens_fig, wall_fig)

    # Table alternative
    headers = [("Combo", False), ("Pack", False), ("pass@1", True), ("95% interval", False),
               ("Tokens per solved", True), ("Wall per task (s)", True)]
    head_tr = html_builder.el("tr", None, *(
        html_builder.el("th", {"scope": "col", "class": "num"} if is_num else {"scope": "col"}, h)
        for h, is_num in headers
    ))

    tr_list = []
    for r in board_obj.frontier:
        combo_token = combo_ix[r.combo]  # every board combo has a legend token; a miss is a defect, never c1
        cells = [html_builder.el("td", None, r.combo), html_builder.el("td", None, r.pack)]

        # pass@1
        if r.pass_at_1.point is not None:
            p1_attrs = {
                "class": "num",
                "data-interval-point": f"{r.pass_at_1.point:.2f}",
            }
            if r.pass_at_1.lo is not None and r.pass_at_1.hi is not None:
                p1_attrs["data-interval-lo"] = f"{r.pass_at_1.lo:.2f}"
                p1_attrs["data-interval-hi"] = f"{r.pass_at_1.hi:.2f}"
            cells.append(html_builder.el("td", p1_attrs, f"{r.pass_at_1.point:.2f}"))
        else:
            cells.append(html_builder.el("td", {"class": "num na"}, "NA"))

        # 95% interval
        if r.pass_at_1.lo is not None and r.pass_at_1.hi is not None:
            cells.append(html_builder.el("td", {"class": "num"}, f"[{r.pass_at_1.lo:.2f}, {r.pass_at_1.hi:.2f}]"))
        else:
            cells.append(html_builder.el("td", {"class": "na"}, r.pass_at_1.reason or "interval not computed"))

        # Tokens
        if r.tokens_per_solved.value is not None:
            cells.append(html_builder.el("td", {"class": "num", "data-value": str(r.tokens_per_solved.value)}, report.tokens(r.tokens_per_solved)))
        else:
            cells.append(html_builder.el("td", {"class": "num na"}, "NA"))

        # Wall
        if r.wall_per_task.value is not None:
            wall_s = float(r.wall_per_task.value) / 1000.0
            cells.append(html_builder.el("td", {"class": "num", "data-value": f"{wall_s:.1f}"}, report.seconds(r.wall_per_task)))
        else:
            cells.append(html_builder.el("td", {"class": "num na"}, "NA"))

        tr_list.append(html_builder.el("tr", {"data-combo": combo_token, "data-pack": r.pack}, *cells))

    table = html_builder.el(
        "table", None,
        html_builder.el("caption", {"id": "cost-frontier-caption"}, "Cost frontier table"),
        html_builder.el("thead", None, head_tr),
        html_builder.el("tbody", None, *tr_list),
    )
    region = html_builder.el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "cost-frontier-caption"}, table)
    details = html_builder.el("details", None, html_builder.el("summary", None, "Table"), region)

    return html_builder.el(
        "section", {"id": "cost-frontier"},
        html_builder.el("h2", None, "Cost frontier"),
        charts_div,
        details,
    )


def _areas(view: views.RunView, board_obj: board.Board, combo_ix: dict[str, str]) -> html_builder.Html:
    if not any(c.outcome == "completed" for c in view.cells) or not board_obj.areas:
        return html_builder.el(
            "section", {"id": "areas"},
            html_builder.el("h2", None, "Areas"),
            html_builder.el("p", {"class": "st"}, "No completed cells to plot."),
        )

    all_na = all(ar.interval.point is None for ar in board_obj.areas)
    if all_na:
        reasons = [ar.interval.reason for ar in board_obj.areas if ar.interval.reason]
        reason = (reasons[0] if reasons else None) or "not recorded"
        return html_builder.el(
            "section", {"id": "areas"},
            html_builder.el("h2", None, "Areas"),
            html_builder.el("p", {"class": "na"}, f"No area composites for this run: {reason}."),
        )

    def _radar_label_pos(ex: float, ey: float) -> dict[str, str]:
        """The full area name just outside its axis end, anchored away from the centre (110, 100)."""
        anchor = "middle" if abs(ex - 110.0) < 8 else ("start" if ex > 110 else "end")
        dx = 0.0 if anchor == "middle" else (4.0 if anchor == "start" else -4.0)
        dy = 12.0 if ey > 100 else -4.0
        return {"x": f"{ex + dx:.1f}", "y": f"{ey + dy:.1f}", "text-anchor": anchor}

    catalog_areas: list[str] = []
    for ar in board_obj.areas:
        if ar.area not in catalog_areas:
            catalog_areas.append(ar.area)
    num_axes = len(catalog_areas) or 7
    angles = [-math.pi / 2 + i * 2 * math.pi / num_axes for i in range(num_axes)]

    combos: list[str] = []
    for ar in board_obj.areas:
        if ar.combo not in combos:
            combos.append(ar.combo)

    radars: list[html_builder.Html] = []
    for combo in combos:
        combo_token = combo_ix[combo]  # every board combo has a legend token; a miss is a defect, never c1
        combo_rows = [ar for ar in board_obj.areas if ar.combo == combo]
        svg_children: list[html_builder.Html] = []

        # Grid circles
        for pct in (25, 50, 75, 100):
            r_circle = (pct / 100.0) * 70.0
            svg_children.append(html_builder.el("circle", {"cx": "110", "cy": "100", "r": str(r_circle), "class": "grid", "fill": "none"}))

        # Axis lines and ticks
        for i, area in enumerate(catalog_areas):
            a = angles[i]
            ex = 110.0 + 70.0 * math.cos(a)
            ey = 100.0 + 70.0 * math.sin(a)
            area_rows = [ar for ar in combo_rows if ar.area == area]
            is_na = all(ar.interval.point is None for ar in area_rows)
            if is_na:
                svg_children.append(html_builder.el("line", {
                    "x1": "110", "y1": "100", "x2": f"{ex:.1f}", "y2": f"{ey:.1f}",
                    "class": "grid na hollow", "stroke-dasharray": "4 3",
                }))
                svg_children.append(html_builder.el("text", {**_radar_label_pos(ex, ey), "class": "na"}, f"{area} NA"))
            else:
                svg_children.append(html_builder.el("line", {
                    "x1": "110", "y1": "100", "x2": f"{ex:.1f}", "y2": f"{ey:.1f}",
                    "class": "grid",
                }))
                svg_children.append(html_builder.el("text", _radar_label_pos(ex, ey), area))

        # Polygons per pack arm
        for arm in _arm_order(sorted({c.arm for c in view.cells})):
            arm_rows = {ar.area: ar for ar in combo_rows if ar.pack == arm}
            pts: list[tuple[float, float, str, stats.Interval]] = []
            hi_pts: list[tuple[float, float]] = []
            lo_pts: list[tuple[float, float]] = []
            for i, area in enumerate(catalog_areas):
                ar = arm_rows.get(area)
                if ar is not None and ar.interval.point is not None:
                    val = float(ar.interval.point)
                    r_pt = (val / 100.0) * 70.0
                    vx = 110.0 + r_pt * math.cos(angles[i])
                    vy = 100.0 + r_pt * math.sin(angles[i])
                    pts.append((vx, vy, area, ar.interval))
                if ar is not None and ar.interval.lo is not None and ar.interval.hi is not None:
                    r_hi = (float(ar.interval.hi) / 100.0) * 70.0
                    r_lo = (float(ar.interval.lo) / 100.0) * 70.0
                    hi_pts.append((110.0 + r_hi * math.cos(angles[i]), 100.0 + r_hi * math.sin(angles[i])))
                    lo_pts.append((110.0 + r_lo * math.cos(angles[i]), 100.0 + r_lo * math.sin(angles[i])))

            if pts:
                if len(hi_pts) == len(pts) and len(hi_pts) >= 3:
                    band_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in hi_pts) + " " + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(lo_pts))
                    svg_children.append(html_builder.el("polygon", {"points": band_pts, "class": f"mk-{combo_token}", "fill-opacity": "0.08", "stroke": "none"}))

                poly_pts = " ".join(f"{vx:.1f},{vy:.1f}" for vx, vy, _, _ in pts)
                poly_cls = f"mk-{combo_token}" + (" dash" if arm == config.ARM_OFF else "")
                svg_children.append(html_builder.el("polygon", {
                    "points": poly_pts,
                    "class": poly_cls,
                    "data-combo": combo_token,
                    "data-pack": arm,
                    "fill-opacity": "0.12",
                    "stroke-width": "2",
                }))

                for vx, vy, area, iv in pts:
                    mark_attrs: dict[str, object] = {
                        "cx": f"{vx:.1f}",
                        "cy": f"{vy:.1f}",
                        "r": "3",
                        "class": f"mk-{combo_token}",
                        "data-combo": combo_token,
                        "data-pack": arm,
                        "data-area": area,
                        "data-value": f"{iv.point:.1f}",
                        "data-interval-point": f"{iv.point:.1f}",
                    }
                    if iv.lo is not None and iv.hi is not None:
                        mark_attrs["data-interval-lo"] = f"{iv.lo:.1f}"
                        mark_attrs["data-interval-hi"] = f"{iv.hi:.1f}"
                    svg_children.append(html_builder.el("circle", mark_attrs))

        svg = html_builder.el("svg", {
            "viewBox": "-70 0 360 200",  # 70-unit margins either side hold the full area names
            "role": "img",
            "aria-label": f"{combo} areas",
            "width": "100%",
        }, *svg_children)
        radars.append(html_builder.el("figure", None, svg, html_builder.el("figcaption", None, f"{combo}: areas radar")))

    radars_div = html_builder.el("div", {"class": "charts"}, *radars)

    # Table alternative
    head_cells = [html_builder.el("th", {"scope": "col"}, "Combo"), html_builder.el("th", {"scope": "col"}, "Pack")]
    for area in catalog_areas:
        head_cells.append(html_builder.el("th", {"scope": "col", "class": "num"}, area))
    head_tr = html_builder.el("tr", None, *head_cells)

    tr_list = []
    # Group by (combo, pack)
    combos_packs: list[tuple[str, str]] = []
    for ar in board_obj.areas:
        key = (ar.combo, ar.pack)
        if key not in combos_packs:
            combos_packs.append(key)

    for combo, pack in combos_packs:
        combo_token = combo_ix[combo]  # every board combo has a legend token; a miss is a defect, never c1
        arm_rows = {ar.area: ar for ar in board_obj.areas if ar.combo == combo and ar.pack == pack}
        row_cells = [html_builder.el("td", None, combo), html_builder.el("td", None, pack)]
        for area in catalog_areas:
            ar = arm_rows.get(area)
            if ar is not None and ar.interval.point is not None:
                td_attrs = {
                    "class": "num",
                    "data-area": area,
                    "data-value": f"{ar.interval.point:.1f}",
                    "data-interval-point": f"{ar.interval.point:.1f}",
                }
                if ar.interval.lo is not None and ar.interval.hi is not None:
                    td_attrs["data-interval-lo"] = f"{ar.interval.lo:.1f}"
                    td_attrs["data-interval-hi"] = f"{ar.interval.hi:.1f}"
                row_cells.append(html_builder.el("td", td_attrs, f"{ar.interval.point:.1f}"))
            else:
                reason = (ar.interval.reason if ar else None) or "not recorded"
                row_cells.append(html_builder.el("td", {"class": "num na", "data-area": area}, f"NA ({reason})"))
        tr_list.append(html_builder.el("tr", {"data-combo": combo_token, "data-pack": pack}, *row_cells))

    table = html_builder.el(
        "table", None,
        html_builder.el("caption", {"id": "areas-caption"}, "Areas table"),
        html_builder.el("thead", None, head_tr),
        html_builder.el("tbody", None, *tr_list),
    )
    region = html_builder.el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "areas-caption"}, table)
    details = html_builder.el("details", None, html_builder.el("summary", None, "Table"), region)

    return html_builder.el(
        "section", {"id": "areas"},
        html_builder.el("h2", None, "Areas"),
        html_builder.el("p", {"class": "small muted"}, f"Fixed axis order: {', '.join(catalog_areas)}. Pack on solid, pack off dashed."),
        radars_div,
        details,
    )

# R6 (design section 15, s6 rows 7 and 8, s3 DR-R-1, s12 UIA-13/UXA-8): the Scenarios heatmap and
# the Context growth chart, each with its own table alternative (or, for the heatmap, the heatmap
# *is* the accessible table -- design row 7 names no separate table alternative, unlike rows 5/6/8's
# charts, because a heatmap built as `<table>` already satisfies 1.1.1/1.3.1 on its own).


def _srgb_to_linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a `#rrggbb` colour (design s3 DR-R-1's proof)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def _heat_ink_class(fill_hex: str) -> str:
    """DR-R-1: the text colour is whichever of #000/#fff has the higher contrast with the cell fill,
    computed from the fill's own luminance -- never a fixed per-stop guess (design s3, R-81 R-1)."""
    luminance = _relative_luminance(fill_hex)
    contrast_white = 1.05 / (luminance + 0.05)
    contrast_black = (luminance + 0.05) / 0.05
    return "on-heat-dark" if contrast_white >= contrast_black else "on-heat-light"


def _heat_stop(i: int) -> str:
    return re.search(rf"--heat-{i}:\s*(#[0-9a-fA-F]{{6}})", STYLE).group(1)


# The ten `.h0..h9` heatmap-fill rules (design s6 row 7): generated from `_heat_ink_class` against
# `STYLE`'s own `--heat-0..9` values, so the applied ink can never hand-typed-drift from the DR-R-1
# computation that chose it (test_scenarios_heat_ink_meets_wcag_aa recomputes and checks both).
STYLE += "\n" + "\n".join(
    f".h{i}{{background:var(--heat-{i});color:var(--{_heat_ink_class(_heat_stop(i))})}}" for i in range(10)
) + "\n"

# Report section 3 (X-H2): existing tokens only. The MDE band is tinted and dashed, never colour alone (EVU-5).
STYLE += """p.warn{color:var(--warn);font-weight:600}
.badge{border:var(--rule-w) solid var(--rule-strong);border-radius:var(--radius);font-size:var(--fs-small);color:var(--ink-2)}
.verdict-cell span[data-part]{display:block}
.verdict-cell .glyph{color:var(--ink-2)}
.bar .axis{stroke:var(--rule-strong)}
.bar .mde-band{fill:var(--rule);stroke:var(--rule-strong);stroke-dasharray:3 2}
.bar .interval{stroke:var(--ink);stroke-width:var(--focus-w)}
.scroll{overflow:auto;max-height:calc(var(--target) * 8)}
"""


def _heat_bucket(value) -> int:
    """The composite's 0-100 point maps onto one of the ten `--heat-0..9` viridis stops (design s6
    row 7's legend, "0 … 100, correctness-gated composite"); values outside 0-100 clamp."""
    v = max(Decimal(0), min(Decimal(100), Decimal(str(value))))
    return min(9, int(v // 10))


def _scenario_cell(sr: board.ScenarioRow | None, combo_tok: str, pack: str, scenario: int) -> html_builder.Html:
    attrs = {"data-combo": combo_tok, "data-pack": pack, "data-scenario": str(scenario)}
    if sr is None or (sr.gated.point is None and sr.gated.reason == "no cells in this scenario"):
        return html_builder.el("td", {**attrs, "class": "h"}, "—", html_builder.el("br"),
                               "no cells in this scenario")
    gated = sr.gated
    p1 = sr.pass_at_1
    if gated.point is None:
        reason = gated.reason or "not recorded"
        return html_builder.el("td", {**attrs, "class": "h na"}, "not recorded", html_builder.el("br"),
                               f"— {reason}")
    bucket = _heat_bucket(gated.point)
    value_str = f"{gated.point:.1f}"
    cell_attrs = {**attrs, "class": f"h h{bucket} num", "data-value": value_str}
    if gated.lo is not None and gated.hi is not None:
        lo_str, hi_str = f"{gated.lo:.1f}", f"{gated.hi:.1f}"
        cell_attrs["data-interval-lo"] = lo_str
        cell_attrs["data-interval-hi"] = hi_str
        iv_text = f"[{lo_str}, {hi_str}]"
    else:
        iv_text = gated.reason or "interval not computed"
    p1_str = f"{p1.point:.2f}" if p1.point is not None else (p1.reason or "NA")
    if p1.point is not None:
        cell_attrs["data-pass1"] = p1_str
    return html_builder.el(
        "td", cell_attrs,
        value_str, html_builder.el("br"), iv_text, html_builder.el("br"), f"pass@1 {p1_str}",
    )


def _scenarios(view: views.RunView, board_obj: board.Board, combo_ix: dict[str, str]) -> html_builder.Html:
    # UXA-8: the same "0 completed" check `_leaderboard` uses (design s6 row 3's empty state), not
    # "`board_obj.scenarios` is empty" -- `board.build` still emits a "no cells in this scenario" row
    # per planned (combo, pack, scenario) even when nothing completed, so that check alone would
    # never fire on the design's own `empty` fixture and would draw a table of nothing but dashes.
    if not board_obj.scenarios or not any(c.outcome == "completed" for c in view.cells):
        return html_builder.el(
            "section", {"id": "scenarios"}, html_builder.el("h2", None, "Scenarios"),
            html_builder.el("p", None, f"No cell completed in this run. Run bench status {view.run_id} to see why."),
        )
    scenarios = sorted({sr.scenario for sr in board_obj.scenarios})
    by_key: dict[tuple[str, str], dict[int, board.ScenarioRow]] = {}
    order: list[tuple[str, str]] = []
    for sr in board_obj.scenarios:
        key = (sr.combo, sr.pack)
        if key not in by_key:
            by_key[key] = {}
            order.append(key)
        by_key[key][sr.scenario] = sr

    head_cells = [html_builder.el("th", {"scope": "col"}, "Combo · pack")]
    head_cells += [html_builder.el("th", {"scope": "col", "class": "num"}, f"Scenario {sc}") for sc in scenarios]
    head_row = html_builder.el("tr", None, *head_cells)

    body_rows = []
    for combo, pack in order:
        row_cells = [html_builder.el("th", {"scope": "row"}, f"{combo} · {pack}")]
        for sc in scenarios:
            row_cells.append(_scenario_cell(by_key[combo, pack].get(sc), combo_ix.get(combo, combo), pack, sc))
        body_rows.append(html_builder.el("tr", None, *row_cells))

    table = html_builder.el(
        "table", {"class": "heat"},
        html_builder.el("caption", {"id": "scenarios-caption"},
                        "Combos × scenarios; each cell: the correctness-gated composite, "
                        "0 … 100 (viridis), its [lo, hi], and pass@1"),
        html_builder.el("thead", None, head_row),
        html_builder.el("tbody", None, *body_rows),
    )
    region = html_builder.el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "scenarios-caption"}, table)
    return html_builder.el("section", {"id": "scenarios"}, html_builder.el("h2", None, "Scenarios"), region)


def _context_growth_chart(tid: str, task: context_growth.TaskGrowth, combo_ix: dict[str, str]) -> html_builder.Html | None:
    """One task's line-per-combo chart (design s6 row 8): median over repetitions with a min-max
    band, a ▲ compaction mark at each flagged turn. `None` when the task carries no series --
    its own reason (design row 8: "the option stays, with its reason") stands in its place."""
    all_turns = sorted({t for s in task.series for t in s.turns})
    if not task.series or not all_turns:
        return None
    max_val = max((v for s in task.series for v in s.hi), default=0)
    x_step = 480.0 / max(1, len(all_turns) - 1) if len(all_turns) > 1 else 0.0
    y_scale = 130.0 / max_val if max_val else 0.0

    def x(i: int) -> float:
        return 40 + i * x_step

    def y(v) -> float:
        return 150 - float(v) * y_scale

    svg_children: list[html_builder.Html] = [
        html_builder.el("line", {"x1": "40", "x2": "40", "y1": "10", "y2": "150", "class": "axis"}),
        html_builder.el("line", {"x1": "40", "x2": "520", "y1": "150", "y2": "150", "class": "axis"}),
    ]
    turn_ix = {t: i for i, t in enumerate(all_turns)}
    for s in task.series:
        points: list[str] = []
        for i, turn in enumerate(s.turns):
            xi, yi = round(x(turn_ix[turn]), 1), round(y(s.median[i]), 1)
            points.append(f"{xi},{yi}")
            mark_attrs = {
                "data-combo": combo_ix.get(s.combo, s.combo), "data-pack": s.pack, "data-task": task.task,
                "data-turn": str(turn), "data-value": str(s.median[i]),
                "data-interval-lo": str(s.lo[i]), "data-interval-hi": str(s.hi[i]),
            }
            svg_children.append(html_builder.el("circle", {**mark_attrs, "cx": str(xi), "cy": str(yi), "r": "3"}))
            if turn in s.compactions:
                svg_children.append(html_builder.el("polygon", {
                    **mark_attrs, "data-compaction": "true",
                    "points": f"{xi - 4},{yi + 8} {xi + 4},{yi + 8} {xi},{yi}",
                }))
        svg_children.append(html_builder.el("polyline", {
            "points": " ".join(points), "fill": "none", "class": "axis",
            "data-combo": combo_ix.get(s.combo, s.combo), "data-pack": s.pack, "data-task": task.task,
        }))
    return html_builder.el("svg", {
        "id": f"{tid}-svg", "role": "img", "aria-label": f"Prompt tokens per turn, {task.task}",
        "viewBox": "0 0 560 170", "width": "100%",
    }, *svg_children)


def _context_growth_table(task: context_growth.TaskGrowth) -> html_builder.Html:
    cap_id = f"cg-{task.task}-caption"
    head = html_builder.el(
        "tr", None,
        html_builder.el("th", {"scope": "col"}, "Combo"), html_builder.el("th", {"scope": "col"}, "Pack"),
        html_builder.el("th", {"scope": "col", "class": "num"}, "Turn"),
        html_builder.el("th", {"scope": "col", "class": "num"}, "Prompt tokens (median)"),
        html_builder.el("th", {"scope": "col"}, "Min-max band"),
        html_builder.el("th", {"scope": "col"}, "Compaction"),
    )
    rows = []
    for s in task.series:
        for i, turn in enumerate(s.turns):
            compacted = turn in s.compactions
            rows.append(html_builder.el(
                "tr", None,
                html_builder.el("td", None, s.combo),
                html_builder.el("td", None, s.pack),
                html_builder.el("td", {"class": "num"}, str(turn)),
                html_builder.el("td", {"class": "num", "data-value": str(s.median[i])}, str(s.median[i])),
                html_builder.el("td", {"data-interval-lo": str(s.lo[i]), "data-interval-hi": str(s.hi[i])},
                                f"[{s.lo[i]}, {s.hi[i]}]"),
                html_builder.el("td", {"data-compaction": "true"} if compacted else None,
                                "▲" if compacted else "—"),
            ))
    table = html_builder.el(
        "table", None,
        html_builder.el("caption", {"id": cap_id}, f"Prompt tokens per turn, {task.task}"),
        html_builder.el("thead", None, head),
        html_builder.el("tbody", None, *rows),
    )
    region = html_builder.el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": cap_id}, table)
    return html_builder.el("details", None, html_builder.el("summary", None, "Table"), region)


def _context_growth(view: views.RunView, cg: context_growth.ContextGrowthResult,
                    combo_ix: dict[str, str]) -> html_builder.Html:
    if not cg.tasks or not any(c.outcome == "completed" for c in view.cells):  # UXA-8, the same check as Scenarios
        return html_builder.el(
            "section", {"id": "context-growth"}, html_builder.el("h2", None, "Context growth"),
            html_builder.el("p", None, f"No cell completed in this run. Run bench status {view.run_id} to see why."),
        )
    options = [
        html_builder.el("option", {"value": t.task}, t.task if t.series else f"{t.task}: {t.reason}")
        for t in cg.tasks
    ]
    select = html_builder.el(
        "label", None, "Task ", html_builder.el("select", {"id": "cg-task"}, *options))

    # Design section 13's JS-disabled degrade ("every table and chart shows all series") is this
    # renderer's *only* mode today: `report.js` (out of scope for R6) owns swapping the visible task
    # when JS is present; without it every task's figure and table are simply all in the DOM.
    children = [html_builder.el("h2", None, "Context growth"), select]
    for i, t in enumerate(cg.tasks):
        chart = _context_growth_chart(f"cg-{i + 1}", t, combo_ix)
        if chart is None:
            children.append(html_builder.el("p", {"data-task": t.task}, t.reason or context_growth.NO_TURNS.format(task=t.task)))
            continue
        figcaption = html_builder.el(
            "figcaption", None,
            f"Prompt tokens per turn, {t.task}. ▲ marks a compaction; the table lists each one.")
        children.append(html_builder.el("figure", {"data-task": t.task}, chart, figcaption))
        children.append(_context_growth_table(t))
    return html_builder.el("section", {"id": "context-growth"}, *children)


def _cell_card(c: views.CellView, archive_present: bool, catalog_version: str | None) -> str:
    """Design section 6 row 10: the inline `<details>` cell card -- fields, scores with evidence, and the
    cause for invalid/blocked/failed/stopped/withheld. The one place section 10's STRIDE row names for
    agent-derived text (a warning's message here stands in for the clarifying-question/judge-rationale/test-
    output text R7-R9 add): built on `el()`, so it is inert by construction (UIA-15), never `trusted()`."""
    fields = [("Combo", c.combo), ("Harness", c.harness), ("Model", c.model), ("Outcome", c.outcome),
              ("Validity", c.validity + (f" {c.validity_code}" if c.validity_code else ""))]
    if c.cause:
        fields.append(("Cause", c.cause + (f" ({c.code})" if c.code else "")))
    dl_children: list = []
    for k, v in fields:
        dl_children += [html_builder.el("dt", None, k), html_builder.el("dd", None, v)]
    dl = html_builder.el("dl", {"class": "cell-fields"}, *dl_children)

    score_items = []
    for metric in ("pass_at_1", "partial_credit", "mutation_score"):
        measure = c.scores.get(metric)
        if measure is None:
            continue
        na = measure.value is None
        text = report.rate(measure)
        evidence = _evidence_content(c, metric, archive_present)
        score_items.append(html_builder.el(
            "li", None, html_builder.el("span", {"class": "small"}, f"{_METRIC_LABEL.get(metric, metric)}: "),
            html_builder.trusted(_ev(text, na, _UNIT.get(metric, ""), catalog_version, evidence, c.cell_id))))
    scores_block = (html_builder.el("ul", {"class": "cell-scores"}, *score_items) if score_items
                    else html_builder.el("p", {"class": "small"}, "No scores recorded."))

    children = [html_builder.el("summary", None, "Cell card"), dl, scores_block]
    if c.warnings:  # section 10 STRIDE row: a warning's message is agent-derived-shaped text, escaped by el()
        children.append(html_builder.el("ul", {"class": "cell-warnings"},
                                        *(html_builder.el("li", None, f"{w.code} {w.message}") for w in c.warnings)))
    return html_builder.el("details", None, *children)


def _runs_ev_td(text: str, na: bool, metric: str, c: views.CellView, archive_present: bool,
                catalog_version: str | None) -> str:
    """A Runs numeric cell as an evidence-trigger button (design section 6 preamble: every number is an
    evidence trigger -- not only the cell card's own copies). `_evidence_content` reads `none` for a
    telemetry fact (tokens/wall/tool/model/idle) that carries no per-metric evidence pointer."""
    evidence = _evidence_content(c, metric, archive_present)
    return html_builder.el("td", {"class": "num"}, html_builder.trusted(
        _ev(text, na, _UNIT.get(metric, ""), catalog_version, evidence, c.cell_id)))


def _task_id(c: views.CellView) -> str:
    """The cell's task id: `label`'s own first segment (`plan.py:78-79`, `f"{task}.{combo}.pack-{pack}.r{rep}"`
    -- the one place a label is built, so this is read from the format, never guessed)."""
    return c.label.split(".", 1)[0]


def _runs_filters(view: views.RunView) -> html_builder.Html:
    """R4: the Runs filter controls (design section 6 row 10, section 10 `_runs_filters`): task, combo,
    pack, outcome, validity, each a `<select>` with an "All" default plus every distinct value this run's
    cells carry -- `report.js` reads these five and hides non-matching rows, showing the design's exact
    no-match copy when nothing is left."""
    def select(field_id: str, label: str, values: list[str]) -> html_builder.Html:
        options = [html_builder.el("option", {"value": ""}, f"All ({label.lower()})")]
        options += [html_builder.el("option", {"value": v}, v) for v in values]
        return html_builder.el(
            "label", None, label, " ",
            html_builder.el("select", {"id": field_id}, *options),
        )

    tasks = sorted({_task_id(c) for c in view.cells})
    combos = sorted({c.combo for c in view.cells})
    packs = sorted({c.arm for c in view.cells})
    outcomes = sorted({c.outcome for c in view.cells})
    validities = sorted({c.validity for c in view.cells})
    return html_builder.el(
        "div", {"id": "runs-filters", "class": "small"},
        select("filter-task", "Task", tasks),
        select("filter-combo", "Combo", combos),
        select("filter-pack", "Pack", packs),
        select("filter-outcome", "Outcome", outcomes),
        select("filter-validity", "Validity", validities),
    )


def _runs(view: views.RunView, archive_present: bool, tags: dict[str, str], run_dir: Path | None = None,
          root: Path | None = None, catalog_version: str | None = None,
          combo_ix: dict[str, str] | None = None) -> str:
    if not view.cells:
        return html_builder.el("section", {"id": "runs"}, html_builder.el("h2", None, "Runs"),
                               html_builder.el("p", None, "No cells in this run."))
    show_mutation = report.has_d1_cell(view.plan)
    mutation = report.d1_mutation_values(root, run_dir, view) if show_mutation else {}
    headers = [("Cell", False), ("Outcome", False), ("Validity", False), ("pass@1", True), ("Partial credit", True),
               *((("mutation_score", False),) if show_mutation else ()), ("Tokens", True),
               ("Wall", True), ("Tool time", True), ("Model time", True), ("Idle", True), ("Context window", False),
               ("Warnings", False), ("Evidence", False), ("Cell card", False)]
    head_row = html_builder.el("tr", None, *(
        html_builder.el("th", {"scope": "col", "class": "num"} if num else {"scope": "col"}, h) for h, num in headers))
    na = views.Measure(None, "not graded")

    body_rows = []
    for c in view.cells:
        label_text = report.flag_if_claude_code(report.flag_if_codex(
            c.label + (f" · {COORDINATION_BANNER}" if c.scenario == 6 else ""), c.harness), c.harness)
        p1_m = c.scores.get("pass_at_1", na)
        pc_m = c.scores.get("partial_credit", na)
        row_cells = [
            html_builder.el("td", None, label_text),
            html_builder.el("td", None, c.outcome + (f" ({c.cause}, {c.code})" if c.code else "")),
            html_builder.el("td", None, c.validity + (f" {c.validity_code}" if c.validity_code else "")),
            _runs_ev_td(report.rate(p1_m), p1_m.value is None, "pass_at_1", c, archive_present, catalog_version),
            _runs_ev_td(report.rate(pc_m), pc_m.value is None, "partial_credit", c, archive_present, catalog_version),
        ]
        if show_mutation:
            row_cells.append(html_builder.el("td", None, mutation.get(c.cell_id, "")))
        row_cells += [
            _runs_ev_td(report.cell_tokens(c.tokens, c.tokens_reason), not c.tokens, "tokens", c, archive_present, catalog_version),
            _runs_ev_td(report.seconds(c.wall_ms), c.wall_ms.value is None, "wall_ms", c, archive_present, catalog_version),
            _runs_ev_td(report.millis(c.tool_ms), c.tool_ms.value is None, "tool_ms", c, archive_present, catalog_version),
            _runs_ev_td(report.millis(c.model_ms), c.model_ms.value is None, "model_ms", c, archive_present, catalog_version),
            _runs_ev_td(report.millis(c.idle_ms), c.idle_ms.value is None, "idle_ms", c, archive_present, catalog_version),
            html_builder.el("td", None, report.context_window(c.harness, tags.get(c.cell_id))),
            html_builder.el("td", None, ", ".join(w.code for w in c.warnings) or "none"),
            html_builder.el("td", None, _evidence_content(c, "pass_at_1", archive_present)),
            html_builder.el("td", None, _cell_card(c, archive_present, catalog_version)),
        ]
        # `data-combo` carries the legend's "c1".."c8" token (design section 6: hiding a combo hides its
        # rows "everywhere, except in Validity" -- so Runs shares the same CSS hide-cN vocabulary the
        # leaderboard rows use); `data-combo-name` is the literal combo the Runs filter select matches.
        row_attrs = {"id": f"cell-{c.cell_id}", "data-task": _task_id(c),
                    "data-combo": (combo_ix or {}).get(c.combo, ""), "data-combo-name": c.combo,
                    "data-pack": c.arm, "data-outcome": c.outcome, "data-validity": c.validity}
        body_rows.append(html_builder.el("tr", row_attrs, *row_cells))

    table = html_builder.el(
        "table", None,
        html_builder.el("caption", {"id": "runs-caption"}, "Every cell of the run"),
        html_builder.el("thead", None, head_row),
        html_builder.el("tbody", {"id": "runs-body"}, *body_rows),
    )
    region = html_builder.el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "runs-caption"}, table)
    no_match = html_builder.el("p", {"id": "runs-no-match", "hidden": True}, "No cells match this filter.")
    return html_builder.el("section", {"id": "runs"}, html_builder.el("h2", None, "Runs"), _runs_filters(view),
                           no_match, region)


def _comparison_table(comparison_obj: board.Comparison, combo_ix: dict[str, str]) -> html_builder.Html:
    caption_text = f"Comparison: {comparison_obj.view_run_id} vs baseline {comparison_obj.base_run_id}"
    return _delta_table(comparison_obj.rows, "comparison-caption", caption_text, has_pack=True, combo_ix=combo_ix)


def _comparison(comparison_obj: board.Comparison | str | None, combo_ix: dict[str, str]) -> html_builder.Html | None:
    if comparison_obj is None:
        return None
    if isinstance(comparison_obj, str):
        diff_text = comparison_obj
        if not diff_text.startswith("Runs not comparable:"):
            diff_text = f"Runs not comparable: {diff_text}"
        return html_builder.el(
            "section", {"id": "comparison"},
            html_builder.el("h2", None, "Comparison"),
            html_builder.el("p", None, diff_text),
        )

    elements = [html_builder.el("h2", None, "Comparison")]
    elements.append(html_builder.el("p", None, comparison_obj.exclusion_line))
    if comparison_obj.same_pack_revision:
        elements.append(html_builder.el("p", None, f"same pack revision ({comparison_obj.same_pack_revision}): a replication"))
    if comparison_obj.unshared_tasks:
        elements.append(html_builder.el("p", None, f"Tasks in one run only: {', '.join(sorted(comparison_obj.unshared_tasks))}"))

    if comparison_obj.rows:
        chart = _whisker_chart(
            "comparison",
            f"Comparison: {comparison_obj.view_run_id} vs baseline {comparison_obj.base_run_id} on a shared zero line",
            comparison_obj.rows,
            combo_ix,
            is_comparison=True,
        )
        if chart is not None:
            elements.append(chart)
        elements.append(_comparison_table(comparison_obj, combo_ix))
    else:
        elements.append(html_builder.el("p", None, "No comparison data."))

    return html_builder.el("section", {"id": "comparison"}, *elements)


# R7 (design section 15, 6 row 9, 8): the Summaries section, built on `html_builder.el`. Reads
# `summary_records` through `report.summaries` only (a lazy import: `summaries` imports `egress`, which
# already imports this module -- see `egress.py`'s own module docstring on that existing cycle -- so the
# import is deferred to call time here rather than added at module top).


_SUMMARY_TITLES = {"ranking": "1 Ranking and insights", "pack": "2 Pack observations"}


def _citations(refs: tuple[str, ...], run_id: str) -> html_builder.Html:
    """section 8: a run id or cell id is a link (UXA-6); a metric reference is shown as its own text.
    simplify: a metric ref does not yet open its evidence popover (that needs the catalog version and an
    evidence pointer this section does not carry); upgrade trigger: R9's publication polish wires `_ev()`
    the way the leaderboard's cells already do."""
    children: list = []
    for i, r in enumerate(refs):
        if i:
            children.append(", ")
        if r == run_id:
            children.append(html_builder.el("a", {"href": "#runs"}, r))
        elif r.startswith(("board:", "pack:", "cmp:")):
            children.append(html_builder.el("span", {"class": "small citation"}, r))
        else:
            children.append(html_builder.el("a", {"href": f"#cell-{r}"}, r))
    return html_builder.el("span", {"class": "citations"}, *children)


def _claim_item(claim: dict, run_id: str) -> html_builder.Html:
    return html_builder.el("li", None, str(claim.get("text", "")), " ",
                           _citations(tuple(claim.get("refs") or ()), run_id))


def _published_block(row, run_id: str) -> html_builder.Html:
    from harness_bench.report import summaries

    label = html_builder.el("p", None, summaries.PUB_LABEL.format(model=row.model))
    manifest_items: list = []
    for e in row.manifest:
        manifest_items += [html_builder.el("dt", None, str(e.get("id", ""))),
                           html_builder.el("dd", None, str(e.get("sha256") or e.get("withheld") or ""))]
    manifest_details = html_builder.el(
        "details", None, html_builder.el("summary", None, "Manifest"),
        html_builder.el("dl", {"class": "small"}, *manifest_items),
    )
    claims = html_builder.el("ul", None, *(_claim_item(c, run_id) for c in row.claims))
    return html_builder.el("div", None, label, manifest_details, claims)


def _summary_block(kind: str, run_dir: Path | None, view: views.RunView, current_manifest_sha256: str | None) -> html_builder.Html:
    from harness_bench.report import summaries

    row = summaries.latest_row(run_dir, view.run_id, kind) if run_dir is not None else None
    state = summaries.state_for(row, current_manifest_sha256)
    heading = html_builder.el("h3", None, _SUMMARY_TITLES[kind])
    if state == "S-PUB":
        body = _published_block(row, view.run_id)
    elif state == "S-NOTPUB":
        body = html_builder.el("p", None, summaries.STATE_COPY[state].format(n=len(row.failing_claims)))
    else:
        body = html_builder.el("p", None, summaries.STATE_COPY[state].format(run_id=view.run_id))
    return html_builder.el("div", {"id": f"summary-{kind}"}, heading, body)


def _summaries(run_dir: Path | None, view: views.RunView, board_obj: board.Board) -> html_builder.Html:
    """design section 6 row 9 (US-42): both summary blocks, each reading `summary_records` independently.
    The ranking block's current manifest is recomputed here (deterministic, board-only) so a regraded pass
    reads S-STALE; the pack block's manifest also depends on the archive and egress (DR-R-4), which this
    read-only render path does not have wired through it yet -- simplify: the pack block never reads
    S-STALE in R7 (it still reads every other state correctly from the stored row); upgrade trigger: R9
    threads `operator`/`secrets` into this call the way `_header`'s judge block already does."""
    from harness_bench.report import summaries

    ranking_sha = summaries.manifest_digest(summaries.build_ranking_request(view, board_obj).manifest)
    blocks = [
        _summary_block("ranking", run_dir, view, ranking_sha),
        _summary_block("pack", run_dir, view, None),
    ]
    return html_builder.el("section", {"id": "summaries"}, html_builder.el("h2", None, "Summaries"), *blocks)


def _pi_ratio_cell(m) -> str:
    return "NA" if m.value is None else f"{m.value:.2f}x"


EXPLORATORY_BADGE = "exploratory — not pre-registered"


def _pi_group_row(g, combo_ix: dict[str, str], combo_harness: dict[str, str], campaign: bool = False) -> html_builder.Html:
    # The Combo column shows the real combo id (`_combo_label`, same text the leaderboard, pack-effect
    # and runs sections show), never the c1..c8 legend/filter token `combo_ix` hands out -- that token
    # vocabulary exists only to drive the control bar's `hide-cN` classes (CSS above, design section 6),
    # and is otherwise an internal id, not a display label; a reader could not tell which harness a row
    # named. `data-combo` still carries the token so this row still obeys the combo legend's filter.
    label = _combo_label(g.combo, combo_harness.get(g.combo, ""))
    flag = " (ceiling_off)" if g.is_ceiling_off else ""
    token = combo_ix.get(g.combo)
    row_attrs = {"data-combo": token} if token is not None else None
    return html_builder.el(
        "tr", row_attrs,
        html_builder.el("td", None, g.task),
        html_builder.el("td", None, label),
        html_builder.el("td", {"class": "num"}, f"{g.passes_on}/{g.n_pairs} · {g.passes_off}/{g.n_pairs}"),
        html_builder.el("td", {"class": "num"},
                        f"{_pi_ratio_cell(g.median_token_ratio)} ({g.n_token_above} of {g.n_token_valid} pairs > 1)"),
        html_builder.el("td", {"class": "num"}, _pi_ratio_cell(g.median_wall_ratio)),
        (html_builder.el("td", {"data-verdict": "intention"}, g.cls + flag, " ",
                         html_builder.el("span", {"class": "badge"}, EXPLORATORY_BADGE))
         if campaign else html_builder.el("td", None, g.cls + flag)),
    )


def _pi_finding_row(f, combo_ix: dict[str, str]) -> html_builder.Html:
    links = []
    for i, cid in enumerate(f.evidence_cell_ids):
        if i:
            links.append(", ")
        links.append(html_builder.el("a", {"href": f"#cell-{cid}"}, cid))
    return html_builder.el(
        "tr", None,
        html_builder.el("td", None, f.code),
        html_builder.el("td", None, f.title),
        html_builder.el("td", {"class": "num"}, str(f.count)),
        html_builder.el("td", None, f.detail or "—"),
        html_builder.el("td", None, f.pack_area),
        html_builder.el("td", None, f.confidence),
        html_builder.el("td", None, *links) if links else html_builder.el("td", None, "—"),
    )


def _pack_improvement(view: views.RunView, board_obj: board.Board | None, run_dir: Path | None, root: Path | None,
                      archive_present: bool, combo_ix: dict[str, str], campaign_section_id: str | None = None) -> html_builder.Html:
    """Design section 2/7: the always-last, always-present "Pack on vs pack off -- where to improve
    the pack" section. Every table sits in the existing horizontally scrolling wrapper. Only counts,
    ratios, verdict codes, metric/task/cell ids and the Method text leave `pack_improvement.assemble`
    (design section 8) -- no transcript text, no command text, no path other than a repo-relative
    pack prefix reaches this renderer to begin with."""
    result = pack_improvement_mod.assemble(view, board_obj, run_dir, root, archive_present=archive_present)
    combo_harness: dict[str, str] = {}
    if board_obj is not None:
        for r in board_obj.rows:
            combo_harness.setdefault(r.combo, r.harness)
    heading = html_builder.el("h2", None, "Pack on vs pack off — where to improve the pack")
    children: list[html_builder.Html] = [heading]
    if campaign_section_id is not None:  # EVX-7: every path to an intention verdict passes the exploratory label
        children.append(html_builder.el("p", {"data-kind": "exploratory-header"}, "Exploratory — see §3 ",
                                        html_builder.el("a", {"href": f"#{campaign_section_id}"}, "Property verdicts"),
                                        " for the pre-registered result"))
    if result.state != pack_improvement_mod.STATE_FULL and result.state != pack_improvement_mod.STATE_PARTIAL:
        children.append(html_builder.el("p", None, result.state_line))
        method = html_builder.el(
            "details", None, html_builder.el("summary", None, "Method"),
            html_builder.el("ul", None, *(html_builder.el("li", None, ln) for ln in result.method_lines)),
        )
        children.append(method)
        return html_builder.el("section", {"id": "pack-improvement"}, *children)

    children.append(html_builder.el("p", None, result.headline or "No pack-attributable waste or harm was detected in this run."))
    children.extend(html_builder.el("p", None, line) for line in result.population_caveats)

    group_table = html_builder.el(
        "table", None,
        html_builder.el("caption", None, "Value vs waste, by task and combo"),
        html_builder.el("thead", None, html_builder.el(
            "tr", None, *(html_builder.el("th", {"scope": "col"}, h) for h in
                          ("Task", "Combo", "Pass on · off", "Median token ratio", "Median wall ratio", "Class")))),
        html_builder.el("tbody", None, *(_pi_group_row(g, combo_ix, combo_harness, campaign_section_id is not None) for g in result.groups)),
    )
    children.append(html_builder.el(
        "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "pi-groups-caption"},
        group_table,
    ))

    if result.findings:
        finding_table = html_builder.el(
            "table", None,
            html_builder.el("caption", None, "Where to improve the pack"),
            html_builder.el("thead", None, html_builder.el(
                "tr", None, *(html_builder.el("th", {"scope": "col"}, h) for h in
                              ("Code", "Finding", "Count", "Waste", "Pack area", "Confidence", "Evidence")))),
            html_builder.el("tbody", None, *(_pi_finding_row(f, combo_ix) for f in result.findings)),
        )
        children.append(html_builder.el(
            "div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": "pi-findings-caption"},
            finding_table,
        ))
    else:
        children.append(html_builder.el("p", None, "No pack-attributable waste or harm was detected in this run."))

    inconclusive_items = [
        html_builder.el("li", None, f"{t.task}: {', '.join(t.reasons)}") for t in result.inconclusive
    ]
    if result.pk08 is not None:
        on_text = "NA" if result.pk08.mean_on is None else f"{result.pk08.mean_on:.4f}"
        off_text = "NA" if result.pk08.mean_off is None else f"{result.pk08.mean_off:.4f}"
        inconclusive_items.append(html_builder.el(
            "li", None,
            f"PK-08 watch: mean ask_vs_assume on {on_text} (n={result.pk08.n_on}) vs off {off_text} "
            f"(n={result.pk08.n_off}) -- Inferred, never ranked.",
        ))
    children.append(html_builder.el(
        "div", None, html_builder.el("h3", None, "Inconclusive"),
        html_builder.el("ul", None, *inconclusive_items) if inconclusive_items
        else html_builder.el("p", None, "No task is flagged inconclusive."),
    ))

    method = html_builder.el(
        "details", None, html_builder.el("summary", None, "Method"),
        html_builder.el("ul", None, *(html_builder.el("li", None, ln) for ln in result.method_lines)),
    )
    children.append(method)
    return html_builder.el("section", {"id": "pack-improvement"}, *children)


def render(view: views.RunView, archive_present: bool, run_dir: Path | None = None, root: Path | None = None,
           operator: egress.Operator | None = None, board_obj: board.Board | None = None,
           params: stats.Params | None = None, comparison_obj: board.Comparison | str | None = None,
           context_growth_obj: context_growth.ContextGrowthResult | None = None,
           campaign_obj: campaign_section.CampaignInput | None = None, lean_obj: lean.LeanSummary | None = None) -> str:
    """The page; `root` (the bench root) adds the judge block for a pass that looked up judge verdicts, and
    `operator` (read at run time, never committed) lets it name the classes each judge CLI added. `lean_obj` (a lean
    run's summary, built by the caller) adds the lean summary section at the campaign section's slot (ADR-0023 point 9);
    without it the page is byte-identical to a non-lean run's (LBU-5)."""
    tags = _context_window_tags(run_dir)  # R-32: read from events, not from views.py (ruling R-32 condition 3)
    judging = judges.facts(root, run_dir, view, operator)

    if board_obj is None:
        r = root if root is not None else (config.repo_root() if (config.repo_root() / "bench" / "metrics.yaml").is_file() else None)
        cat = None
        if r is not None and (r / "bench" / "metrics.yaml").is_file():
            try:
                cat = composites.load_catalog(r)
            except (BenchError, OSError, KeyError, ValueError):
                cat = None
        if cat is None:
            cat = composites.Catalog(
                version=getattr(view, "catalog_version", None) or "0.4",
                hash="",
                metrics={},
                areas={},
                has_anchors=False,
            )
        board_obj = board.build(view, cat, params=params)

    # R1: the shell (head, CSP, nav/jump-links, section order) goes through html_builder + model
    # (design section 5); header, validity (R2), leaderboard, runs (R3), pack effect and comparison (R5)
    # are built on `html_builder.el` end to end, so no section is trusted()-marked at the seam.
    # One c1..c8 map (design section 6). Every section that follows the legend receives it; none
    # builds a second one. The leaderboard reads the same function on this board.
    combo_ix = _combo_index(board_obj)
    comparison_sec = _comparison(comparison_obj, combo_ix)
    cost_frontier_sec = _cost_frontier(view, board_obj, combo_ix)
    areas_sec = _areas(view, board_obj, combo_ix)
    # R6: report-only projection, built from the cell's own model_calls rows (report/context_growth.py's
    # module docstring); a caller (a test, or a future producer) may pass `context_growth_obj` directly,
    # the same seam `comparison_obj` uses.
    cg = context_growth_obj if context_growth_obj is not None else context_growth.build(view, run_dir)
    built = campaign_section.build(view, campaign_obj) if campaign_obj is not None else None
    sections = [
        model.Section("header", "Run header",
                      _header(view, tags, _permission_modes(run_dir), judging, root, run_dir, board_obj=board_obj, params=params,
                              campaign_block=built.header_block if built else None)),
        model.Section("validity", "Validity", _validity(view, built.validity_line if built else None)),
        *([built.section] if built else []),
        *([lean_section.build(lean_obj, view.run_id)] if lean_obj is not None else []),
        model.Section("leaderboard", "Leaderboard", _leaderboard(view, board_obj)),
        model.Section("pack-effect", "Pack effect", _pack_effect(board_obj, combo_ix)),
        model.Section("cost-frontier", "Cost frontier", cost_frontier_sec),
        model.Section("areas", "Areas", areas_sec),
        model.Section("scenarios", "Scenarios", _scenarios(view, board_obj, combo_ix)),
        model.Section("context-growth", "Context growth", _context_growth(view, cg, combo_ix)),
        model.Section("summaries", "Summaries", _summaries(run_dir, view, board_obj)),  # design section 6 order 9
        model.Section("runs", "Runs", _runs(view, archive_present, tags, run_dir, root,
                                            catalog_version=view.catalog_version, combo_ix=combo_ix)),
    ]
    if comparison_sec is not None:
        sections.append(model.Section("comparison", "Comparison", comparison_sec))
    # Design section 2: always the LAST section, after `runs` and after `comparison` when present.
    sections.append(model.Section(
        "pack-improvement", "Pack improvement",
        _pack_improvement(view, board_obj, run_dir, root, archive_present, combo_ix, built.section.id if built else None),
    ))
    # R4: the one hashed inline script (design section 5) plus the sticky control bar it drives.
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    bar = _control_bar(board_obj, combo_ix)
    style = STYLE + _arm_css(sorted({c.arm for c in view.cells})) + (lean_section.STYLE if lean_obj is not None else "")
    return model.page(model.ReportModel(run_id=view.run_id, sections=tuple(sections)), style=style, script=script_text, bar=bar)


def scan(text: str, credential_values: set[str] = frozenset()) -> int:
    """How many credential-shaped strings the text holds, plus (supplementing the shapes) exact
    matches of any known credential value or its base64/URL-encoded form (HB-SEC-001)."""
    found = sum(len(p.findall(text)) for p in SECRET_SHAPES)
    if credential_values:
        found += sum(1 for v in encodings(credential_values) if v and v in text)
    return found


def _publish(doc: str, operator: egress.Operator, secrets: set[str], canaries: Sequence[str]) -> tuple[str, dict]:
    """US-47 c3: every section through `egress.check` (destination `report`), always (R-80 c4). A withheld section is
    replaced by `withheld: sensitive content`; a hit outside every section writes nothing (HB-SEC-001). Returns the page
    to publish and the record: each section's verdict record (digest and class names, never content), the withheld
    ids, and `egress` (`scanned`, or `partial: email not supplied` when the operator gave no email)."""
    sections: list[dict] = []

    def one(m: re.Match) -> str:
        verdict = egress.check(m.group(0), destination=PUBLICATION, operator=operator, secrets=sorted(secrets),
                               canaries=canaries)
        sections.append({"section": m.group(1), **verdict.record()})
        return f'<section id="{m.group(1)}"><p>{egress.WITHHELD}</p></section>' if verdict.withheld else m.group(0)

    published = _SECTION.sub(one, doc)
    if egress.check(_SECTION.sub("", doc), destination=PUBLICATION, operator=operator, secrets=sorted(secrets),
                    canaries=canaries).withheld:
        raise BenchError("HB-SEC-001", f"the page outside its sections is {egress.WITHHELD}; nothing was written")
    return published, {"egress": "scanned" if operator.email is not None else PARTIAL, "sections": sections,
                       "withheld": [s["section"] for s in sections if s["classes"]]}


def _egress_row(record: dict) -> str:
    """R-80 c1: the header's publication-egress row names the scan status, the withheld count and the record. It is
    added after the section scan and holds only bench-authored text (a status, two counts, a file name); the
    HB-SEC-001 shape pass still reads it."""
    text = f"{record['egress']}; {len(record['withheld'])} of {len(record['sections'])} sections withheld; record {RECORD}"
    return f"<dl><dt>Publication egress</dt><dd>{_e(text)}</dd></dl>"


def write(run_dir: Path, view: views.RunView, credential_values: set[str] = frozenset(), root: Path | None = None,
          operator: egress.Operator | None = None, board_obj: board.Board | None = None,
          params: stats.Params | None = None, comparison_obj: board.Comparison | str | None = None,
          canaries: Sequence[str] = (), campaign_obj: campaign_section.CampaignInput | None = None,
          lean_obj: lean.LeanSummary | None = None) -> Path:
    """report.html, after publication egress (`_publish`) and the credential scan (HB-SEC-001), and beside it the run
    record of what the report withheld and flagged (`RECORD`). The record is the publication record, a derived
    artifact regenerated with the report and never a ledger fact (R-80 DR-EG-1, ADR-0006 amendment); `report_sha256`
    binds it to the report.html written beside it (R-80 c1). Without an `operator`, this login's user name and home are
    scanned and the email is not (R-80 c4)."""
    operator = operator if operator is not None else egress.Operator.from_os()
    doc = render(view, archive_present=(run_dir / "archive").is_dir(), run_dir=run_dir, root=root, operator=operator,
                 board_obj=board_obj, params=params, comparison_obj=comparison_obj, campaign_obj=campaign_obj,
                 lean_obj=lean_obj)
    # The rendered page, before any section is withheld: a credential refuses the whole write, never only its section,
    # so `bench report` never prints a table that carries it either (residual 5; R-80 c4 made the section scan run).
    found = scan(doc, credential_values)
    if found:
        raise BenchError("HB-SEC-001", f"{found} credential-shaped string(s) in the report; nothing was written")
    published, record = _publish(doc, operator, set(credential_values), canaries)
    # R-80 c3: the set scanned for, by version; a caller that left the production set out reads "not scanned".
    record["canaries"] = {"version": egress.CANARIES_VERSION if set(egress.CANARIES) <= set(canaries) else "not scanned",
                          "us48": egress.CANARIES_US48}
    record["injection"] = {"patterns_version": views.INJECTION_PATTERNS_VERSION,
                           "items": [{"cell_id": c, "metric": m, "patterns": list(p)}
                                     for c, m, p in judges.injection_items(root, run_dir, view)]}
    published = _HEADER_END.sub(lambda m: m.group(1) + _egress_row(record) + m.group(2), published, count=1)
    path = run_dir / "report.html"
    path.write_text(published, encoding="utf-8", newline="\n")
    record["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run_dir / RECORD).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path
