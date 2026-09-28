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
import re
from collections.abc import Sequence
from pathlib import Path

from harness_bench import (
    board,
    composites,
    config,
    egress,
    profiles,
    report,
    stats,
    views,
)
from harness_bench.errors import BenchError
from harness_bench.plan import resolved_model_map
from harness_bench.report import judges
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
# One rendered section. Sections never nest, and every value is escaped by `_e`, so "</section>" is only a tag.
_SECTION = re.compile(r'<section id="([a-z0-9-]+)">.*?</section>', re.DOTALL)
_HEADER_END = re.compile(r'(<section id="header">.*?)(</section>)', re.DOTALL)  # where the egress row goes (R-80 c1)

STYLE = """
:root{color-scheme: light;
  --bg:#f3f5f7; --panel:#ffffff; --ink:#18212b; --ink-2:#4b5563; --rule:#d9dee5; --focus:#1d6fd6;
  --font:"Segoe UI", system-ui, -apple-system, sans-serif;
  --fs:15px; --fs-small:13px; --fs-h1:26px; --fs-h2:19px;
  --s1:4px; --s2:8px; --s3:16px; --s4:24px; --radius:4px; --rule-w:1px; --focus-w:2px; --maxw:1240px;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:var(--fs);line-height:1.45}
main{max-width:var(--maxw);margin:0 auto;padding:var(--s4) var(--s3)}
h1{font-size:var(--fs-h1);margin:0 0 var(--s2)}
h2{font-size:var(--fs-h2);margin:var(--s4) 0 var(--s2)}
.muted,dt{color:var(--ink-2)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:var(--s1) var(--s3);margin:0}
dd{margin:0}
.region{overflow-x:auto;max-width:100%;background:var(--panel);border:var(--rule-w) solid var(--rule);border-radius:var(--radius)}
.region:focus-visible{outline:var(--focus-w) solid var(--focus);outline-offset:var(--focus-w)}
table{border-collapse:collapse;min-width:100%}
caption{text-align:left;font-weight:600;padding:var(--s2)}
th,td{padding:var(--s1) var(--s2);border-top:var(--rule-w) solid var(--rule);text-align:left;vertical-align:top}
.num{text-align: right; font-variant-numeric: tabular-nums; white-space:nowrap}
code,.small{font-size:var(--fs-small)}
"""


def _e(value) -> str:
    return _html.escape(str(value), quote=True)


def _fact(value) -> str:
    return _e(value) if value not in (None, "") else "not recorded"


def _table(tid: str, caption: str, headers: list[tuple[str, bool]], rows: list[list[tuple]]) -> str:
    head = "".join(f'<th scope="col"{" class=\"num\"" if num else ""}>{_e(h)}</th>' for h, num in headers)
    body = "".join("<tr>" + "".join(
        (f'<td class="num"{cell[2]}>{cell[0]}</td>' if cell[1] else f'<td{cell[2]}>{cell[0]}</td>')
        if len(cell) > 2 else
        (f'<td class="num">{cell[0]}</td>' if cell[1] else f'<td>{cell[0]}</td>')
        for cell in row) + "</tr>"
                   for row in rows)
    return (f'<div class="region" role="region" tabindex="0" aria-labelledby="{tid}-caption">'
            f'<table><caption id="{tid}-caption">{_e(caption)}</caption><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


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


def _header(view: views.RunView, tags: dict[str, str], modes: dict[str, str] | None = None,
            judging: list[tuple[str, str | None]] | None = None, root: Path | None = None,
            run_dir: Path | None = None, board_obj: board.Board | None = None,
            params: stats.Params | None = None) -> str:
    plan = view.plan
    planned = ", ".join(views.build_label(h, str(b.get("version", ""))) for h, b in sorted((plan.get("builds") or {}).items()))
    facts = [("Run", view.run_id), ("State", "complete" if view.completed else "incomplete"),
             ("Plan hash", (plan.get("plan_hash") or "")[:12]), ("Catalog version", view.catalog_version),
             ("Pack revision", (plan.get("pack") or {}).get("revision")),
             ("Pack commit", (plan.get("pack") or {}).get("commit")), ("Planned builds", planned),
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
    rows = "".join(f"<dt>{_e(k)}</dt><dd>{_fact(v)}</dd>" for k, v in facts)
    return f'<section id="header"><h1>harness-bench run {_e(view.run_id)}</h1><dl>{rows}</dl></section>'


def _validity(view: views.RunView) -> str:
    n = len(view.cells)
    if n and all(c.validity == "valid" for c in view.cells):
        body = f"<p>All {n} cells completed and are valid.</p>"
    else:
        counts: dict[str, int] = {}
        for c in view.cells:
            counts[c.validity] = counts.get(c.validity, 0) + 1
        items = "".join(f"<li>{_e(k)}: {v}</li>" for k, v in sorted(counts.items()))
        listed = "".join(f"<li>{_e(c.label)}: {_e(c.validity)}{' ' + _e(c.validity_code) if c.validity_code else ''}</li>"
                         for c in view.cells if c.validity != "valid")
        state = "" if view.completed else f"<p>The run is incomplete. {sum(1 for c in view.cells if c.outcome == 'not started')} cells never started.</p>"
        body = f"{state}<ul>{items}</ul><p>Cells that are not valid:</p><ul>{listed}</ul>"
    warned = "".join(f"<li>{_e(c.label)}: {_e(w.code)} {_e(w.message)}</li>" for c in view.cells for w in c.warnings)
    if warned:  # R-24/R-26 c5, R-28: flags that do not change validity
        body += f'<p>Warnings:</p><ul id="validity-warnings">{warned}</ul>'
    return f'<section id="validity"><h2>Validity</h2>{body}</section>'


def _leaderboard(view: views.RunView, board_obj: board.Board) -> str:
    if not any(c.outcome == "completed" for c in view.cells):
        return (f'<section id="leaderboard"><h2>Leaderboard</h2><p>No cell completed in this run. '
                f"Run bench status {_e(view.run_id)} to see why.</p></section>")
    headers = [("Rank", False), ("Combo", False), ("Pack", False), ("Valid cells", True), ("pass@1", True), ("pass@1 95%", False),
               ("Gated", True), ("Gated 95%", False), ("Tokens per cell", True), ("Wall per cell", True), ("Cost per cell", True)]
    rows = []
    for r in board_obj.rows:
        p1_pt = f"{r.pass_at_1.point:.2f}" if r.pass_at_1.point is not None else f"NA ({r.pass_at_1.reason})"
        if r.pass_at_1.lo is not None and r.pass_at_1.hi is not None:
            p1_attr = f' data-interval-lo="{r.pass_at_1.lo:.2f}" data-interval-hi="{r.pass_at_1.hi:.2f}"'
            p1_iv = f"[{r.pass_at_1.lo:.2f}, {r.pass_at_1.hi:.2f}]"
        else:
            p1_attr = ""
            p1_iv = _e(r.pass_at_1.reason or "interval not computed")

        gated_pt = f"{r.gated.point:.1f}" if r.gated.point is not None else f"NA ({r.gated.reason})"
        if r.gated.lo is not None and r.gated.hi is not None:
            gated_attr = f' data-interval-lo="{r.gated.lo:.1f}" data-interval-hi="{r.gated.hi:.1f}"'
            gated_iv = f"[{r.gated.lo:.1f}, {r.gated.hi:.1f}]"
        else:
            gated_attr = ""
            gated_iv = _e(r.gated.reason or "interval not computed")

        combo_cell = (_e(report.flag_if_claude_code(report.flag_if_codex(r.combo, r.harness), r.harness)), False)

        row = [
            (_e(r.rank or "unranked"), False),
            combo_cell,
            (_e(r.pack), False),
            (f"{r.n_valid}/{r.n_cells} cells", True),
            (_e(p1_pt), True, p1_attr),
            (p1_iv, False, p1_attr),
            (_e(gated_pt), True, gated_attr),
            (gated_iv, False, gated_attr),
            (_e(report.tokens(r.tokens)), True),
            (_e(report.seconds(r.wall_ms)), True),
            (_e(report.usd(r.cost_usd)), True),
        ]
        rows.append(row)

    table_html = _table("leaderboard", "One row per combo and pack", headers, rows)
    footnotes = []
    for r in board_obj.rows:
        if not r.rank and r.rank_reason:
            footnotes.append(f"<p>{_e(r.combo)} {_e(r.pack)}: {_e(r.rank_reason)}</p>")  # rank_reason carries "not ranked: "
        if r.footnote:
            footnotes.append(f"<p>{_e(r.combo)} {_e(r.pack)}: {_e(r.footnote)}</p>")
    fn_html = "".join(footnotes)
    return f'<section id="leaderboard"><h2>Leaderboard</h2>{table_html}{fn_html}</section>'


def _pack_effect(board_obj: board.Board) -> str:
    pe = board_obj.pack_effect
    excl = f"<p>{_e(pe.exclusion_line)}</p>"
    if pe.status is not None:
        body = f"<p>{_e(pe.status)}</p>"
    elif pe.rows:
        headers = [("Combo", False), ("Measure", False), ("Delta", True), ("95% Interval", False), ("Label", False)]
        rows = []
        for pr in pe.rows:
            is_p1 = pr.measure == "pass_at_1"
            if pr.delta.point is not None:
                delta_str = f"{pr.delta.point:+.2f}" if is_p1 else f"{pr.delta.point:+.1f}"
            else:
                delta_str = pr.reason or "NA"
            if pr.delta.lo is not None and pr.delta.hi is not None:
                iv_attr = f' data-interval-lo="{pr.delta.lo:.2f}" data-interval-hi="{pr.delta.hi:.2f}"' if is_p1 else f' data-interval-lo="{pr.delta.lo:.1f}" data-interval-hi="{pr.delta.hi:.1f}"'
                iv_str = f"[{pr.delta.lo:.2f}, {pr.delta.hi:.2f}]" if is_p1 else f"[{pr.delta.lo:.1f}, {pr.delta.hi:.1f}]"
            else:
                iv_attr = ""
                iv_str = _e(pr.reason or pr.delta.reason or "interval not computed")
            label_str = _e(pr.label or "")
            row = [
                (_e(pr.combo), False),
                (_e(pr.measure), False),
                (_e(delta_str), True, iv_attr),
                (iv_str, False, iv_attr),
                (label_str, False),
            ]
            rows.append(row)
        body = _table("pack-effect", "Pack effect per combo and area", headers, rows)
    else:
        body = "<p>No pack effect data.</p>"
    return f'<section id="pack-effect"><h2>Pack effect</h2>{excl}{body}</section>'


def _evidence(c: views.CellView, archive_present: bool) -> str:
    pointer = c.evidence.get("pass_at_1")
    if not pointer:
        return "none"
    if archive_present:
        return f"<code>{_e(pointer)}</code>"
    return _e(f"This copy doesn't include the run archive. Evidence path: {pointer}.")


def _runs(view: views.RunView, archive_present: bool, tags: dict[str, str], run_dir: Path | None = None,
          root: Path | None = None) -> str:
    if not view.cells:
        return '<section id="runs"><h2>Cells</h2><p>No cells in this run.</p></section>'
    show_mutation = report.has_d1_cell(view.plan)
    mutation = report.d1_mutation_values(root, run_dir, view) if show_mutation else {}
    headers = [("Cell", False), ("Outcome", False), ("Validity", False), ("pass@1", True), ("Partial credit", True),
               *((("mutation_score", False),) if show_mutation else ()), ("Tokens", True),
               ("Wall", True), ("Tool time", True), ("Model time", True), ("Idle", True), ("Cost", True), ("Context window", False),
               ("Warnings", False), ("Evidence", False)]
    na = views.Measure(None, "not graded")
    rows = [[(_e(report.flag_if_claude_code(report.flag_if_codex(
                c.label + (f" · {COORDINATION_BANNER}" if c.scenario == 6 else ""), c.harness), c.harness)), False),
             (_e(c.outcome + (f" ({c.cause}, {c.code})" if c.code else "")), False),
             (_e(c.validity + (f" {c.validity_code}" if c.validity_code else "")), False),
             (_e(report.rate(c.scores.get("pass_at_1", na))), True), (_e(report.rate(c.scores.get("partial_credit", na))), True),
             *([(_e(mutation.get(c.cell_id, "")), False)] if show_mutation else []),
             (_e(report.cell_tokens(c.tokens, c.tokens_reason)), True), (_e(report.seconds(c.wall_ms)), True),
             (_e(report.millis(c.tool_ms)), True), (_e(report.millis(c.model_ms)), True), (_e(report.millis(c.idle_ms)), True),
             (_e(report.usd(c.scores.get("cost_usd", na))), True), (_e(report.context_window(c.harness, tags.get(c.cell_id))), False),
             (_e(", ".join(w.code for w in c.warnings) or "none"), False),
             (_evidence(c, archive_present), False)] for c in view.cells]
    return f'<section id="runs"><h2>Cells</h2>{_table("runs", "Every cell of the run", headers, rows)}</section>'


def _comparison(comparison_obj: board.Comparison | str | None) -> str:
    if comparison_obj is None:
        return ""
    if isinstance(comparison_obj, str):
        diff_text = comparison_obj
        if not diff_text.startswith("Runs not comparable:"):
            diff_text = f"Runs not comparable: {diff_text}"
        return f'<section id="comparison"><h2>Comparison</h2><p>{_e(diff_text)}</p></section>'

    excl = f"<p>{_e(comparison_obj.exclusion_line)}</p>"
    rep = (
        f"<p>same pack revision ({_e(comparison_obj.same_pack_revision)}): a replication</p>"
        if comparison_obj.same_pack_revision
        else ""
    )
    unshared = (
        f"<p>Tasks in one run only: {_e(', '.join(sorted(comparison_obj.unshared_tasks)))}</p>"
        if comparison_obj.unshared_tasks
        else ""
    )
    if comparison_obj.rows:
        headers = [
            ("Combo", False),
            ("Pack", False),
            ("Measure", False),
            ("Delta", True),
            ("95% Interval", False),
            ("Label", False),
        ]
        rows = []
        for cr in comparison_obj.rows:
            is_p1 = cr.measure == "pass_at_1"
            if cr.delta.point is not None:
                delta_str = f"{cr.delta.point:+.2f}" if is_p1 else f"{cr.delta.point:+.1f}"
            else:
                delta_str = cr.delta.reason or "NA"
            if cr.delta.lo is not None and cr.delta.hi is not None:
                iv_attr = (
                    f' data-interval-lo="{cr.delta.lo:.2f}" data-interval-hi="{cr.delta.hi:.2f}"'
                    if is_p1
                    else f' data-interval-lo="{cr.delta.lo:.1f}" data-interval-hi="{cr.delta.hi:.1f}"'
                )
                iv_str = (
                    f"[{cr.delta.lo:.2f}, {cr.delta.hi:.2f}]"
                    if is_p1
                    else f"[{cr.delta.lo:.1f}, {cr.delta.hi:.1f}]"
                )
            else:
                iv_attr = ""
                iv_str = _e(cr.delta.reason or "interval not computed")
            label_str = _e(cr.label or "")
            row = [
                (_e(cr.combo), False),
                (_e(cr.pack), False),
                (_e(cr.measure), False),
                (_e(delta_str), True, iv_attr),
                (iv_str, False, iv_attr),
                (label_str, False),
            ]
            rows.append(row)
        body = _table(
            "comparison",
            f"Comparison: {comparison_obj.view_run_id} vs baseline {comparison_obj.base_run_id}",
            headers,
            rows,
        )
    else:
        body = "<p>No comparison data.</p>"
    return f'<section id="comparison"><h2>Comparison</h2>{excl}{rep}{unshared}{body}</section>'


def render(view: views.RunView, archive_present: bool, run_dir: Path | None = None, root: Path | None = None,
           operator: egress.Operator | None = None, board_obj: board.Board | None = None,
           params: stats.Params | None = None, comparison_obj: board.Comparison | str | None = None) -> str:
    """The page; `root` (the bench root) adds the judge block for a pass that looked up judge verdicts, and
    `operator` (read at run time, never committed) lets it name the classes each judge CLI added."""
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

    return ("<!doctype html>\n"
            f'<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>harness-bench run {_e(view.run_id)}</title><style>{STYLE}</style></head>"
            f"<body><main>{_header(view, tags, _permission_modes(run_dir), judging, root, run_dir, board_obj=board_obj, params=params)}{_validity(view)}{_leaderboard(view, board_obj)}{_pack_effect(board_obj)}{_runs(view, archive_present, tags, run_dir, root)}{_comparison(comparison_obj)}"
            f"</main></body></html>\n")


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
          canaries: Sequence[str] = ()) -> Path:
    """report.html, after publication egress (`_publish`) and the credential scan (HB-SEC-001), and beside it the run
    record of what the report withheld and flagged (`RECORD`). The record is the publication record, a derived
    artifact regenerated with the report and never a ledger fact (R-80 DR-EG-1, ADR-0006 amendment); `report_sha256`
    binds it to the report.html written beside it (R-80 c1). Without an `operator`, this login's user name and home are
    scanned and the email is not (R-80 c4)."""
    operator = operator if operator is not None else egress.Operator.from_os()
    doc = render(view, archive_present=(run_dir / "archive").is_dir(), run_dir=run_dir, root=root, operator=operator,
                 board_obj=board_obj, params=params, comparison_obj=comparison_obj)
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
