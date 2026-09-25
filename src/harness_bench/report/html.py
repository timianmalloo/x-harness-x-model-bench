"""`report.html`: the static phase-1 report skeleton (design: UI & interaction design).

- One static file: pre-rendered, no JavaScript, no network request, light mode only. Every colour, size
  and radius is a token in the one `:root` block (the mockup seed, S-10 produces DESIGN.md).
- Sections with stable ids: `header`, `validity`, `leaderboard`, `runs`. Tables have a caption and scoped
  header cells; each scroll container is a focusable, labelled region. Numbers are right-aligned tabular
  figures with units. NA reads `NA (<reason>)`, never 0.
- Before the file is written, the page is scanned for credential shapes (HB-SEC-001): a match refuses the
  write and names only the count, never the value.
- The kiviats, frontiers, heatmap, pack effect and summaries of the mockup are later phases (Spec S-10).
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

from harness_bench import report, views
from harness_bench.errors import BenchError
from harness_bench.report.credentials import encodings

SECRET_SHAPES = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),  # Anthropic keys and OAuth tokens
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),  # OpenAI keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),  # GitHub tokens
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWTs (OAuth access tokens)
)

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


def _table(tid: str, caption: str, headers: list[tuple[str, bool]], rows: list[list[tuple[str, bool]]]) -> str:
    head = "".join(f'<th scope="col"{" class=\"num\"" if num else ""}>{_e(h)}</th>' for h, num in headers)
    body = "".join("<tr>" + "".join(f'<td class="num">{v}</td>' if num else f"<td>{v}</td>" for v, num in row) + "</tr>"
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


def _header(view: views.RunView, tags: dict[str, str]) -> str:
    plan = view.plan
    planned = ", ".join(f"{h} {b.get('version', '')}".strip() for h, b in sorted((plan.get("builds") or {}).items()))
    facts = [("Run", view.run_id), ("State", "complete" if view.completed else "incomplete"),
             ("Plan hash", (plan.get("plan_hash") or "")[:12]), ("Catalog version", view.catalog_version),
             ("Pack revision", (plan.get("pack") or {}).get("revision")),
             ("Pack commit", (plan.get("pack") or {}).get("commit")), ("Planned builds", planned),
             ("Executed builds", view.header.get("executed_builds")), ("Credential kind", view.header.get("credential_kind")),
             ("Network mode", view.header.get("network_mode")), ("Defender real-time exclusion", None),
             ("Context window", _context_window_fact(view.cells, tags)),
             ("Price list hash", (plan.get("price_list_hash") or "")[:12])]
    if report.has_codex_cell(plan):
        facts.append((report.N5_FLAG, f"see {report.N5_EVIDENCE}"))
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
    return f'<section id="validity"><h2>Validity</h2>{body}</section>'


def _leaderboard(view: views.RunView) -> str:
    if not any(c.outcome == "completed" for c in view.cells):
        return (f'<section id="leaderboard"><h2>Leaderboard</h2><p>No cell completed in this run. '
                f"Run bench status {_e(view.run_id)} to see why.</p></section>")
    headers = [("Rank", False), ("Combo", False), ("Pack", False), ("Valid cells", True), ("pass@1", True), ("Interval", False),
               ("Tokens per cell", True), ("Wall per cell", True), ("Cost per cell", True)]
    rows = [[(_e(r.rank or "unranked"), False), (_e(report.flag_if_codex(r.combo, r.harness)), False), (_e(r.pack), False),
             (f"{r.n_valid}/{r.n_cells} cells", True),
             (_e(report.rate(r.pass_at_1)), True), (_e(r.interval), False), (_e(report.tokens(r.tokens)), True),
             (_e(report.seconds(r.wall_ms)), True), (_e(report.usd(r.cost_usd)), True)] for r in views.leaderboard(view)]
    return f'<section id="leaderboard"><h2>Leaderboard</h2>{_table("leaderboard", "One row per combo and pack", headers, rows)}</section>'


def _evidence(c: views.CellView, archive_present: bool) -> str:
    pointer = c.evidence.get("pass_at_1")
    if not pointer:
        return "none"
    if archive_present:
        return f"<code>{_e(pointer)}</code>"
    return _e(f"This copy doesn't include the run archive. Evidence path: {pointer}.")


def _runs(view: views.RunView, archive_present: bool, tags: dict[str, str]) -> str:
    if not view.cells:
        return '<section id="runs"><h2>Cells</h2><p>No cells in this run.</p></section>'
    headers = [("Cell", False), ("Outcome", False), ("Validity", False), ("pass@1", True), ("Partial credit", True), ("Tokens", True),
               ("Wall", True), ("Tool time", True), ("Model time", True), ("Idle", True), ("Cost", True), ("Context window", False),
               ("Evidence", False)]
    na = views.Measure(None, "not graded")
    rows = [[(_e(report.flag_if_codex(c.label, c.harness)), False), (_e(c.outcome + (f" ({c.cause}, {c.code})" if c.code else "")), False),
             (_e(c.validity + (f" {c.validity_code}" if c.validity_code else "")), False),
             (_e(report.rate(c.scores.get("pass_at_1", na))), True), (_e(report.rate(c.scores.get("partial_credit", na))), True),
             (_e(report.cell_tokens(c.tokens, c.tokens_reason)), True), (_e(report.seconds(c.wall_ms)), True),
             (_e(report.millis(c.tool_ms)), True), (_e(report.millis(c.model_ms)), True), (_e(report.millis(c.idle_ms)), True),
             (_e(report.usd(c.scores.get("cost_usd", na))), True), (_e(report.context_window(c.harness, tags.get(c.cell_id))), False),
             (_evidence(c, archive_present), False)] for c in view.cells]
    return f'<section id="runs"><h2>Cells</h2>{_table("runs", "Every cell of the run", headers, rows)}</section>'


def render(view: views.RunView, archive_present: bool, run_dir: Path | None = None) -> str:
    tags = _context_window_tags(run_dir)  # R-32: read from events, not from views.py (ruling R-32 condition 3)
    return ("<!doctype html>\n"
            f'<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>harness-bench run {_e(view.run_id)}</title><style>{STYLE}</style></head>"
            f"<body><main>{_header(view, tags)}{_validity(view)}{_leaderboard(view)}{_runs(view, archive_present, tags)}"
            f"</main></body></html>\n")


def scan(text: str, credential_values: set[str] = frozenset()) -> int:
    """How many credential-shaped strings the text holds, plus (supplementing the shapes) exact
    matches of any known credential value or its base64/URL-encoded form (HB-SEC-001)."""
    found = sum(len(p.findall(text)) for p in SECRET_SHAPES)
    if credential_values:
        found += sum(1 for v in encodings(credential_values) if v and v in text)
    return found


def write(run_dir: Path, view: views.RunView, credential_values: set[str] = frozenset()) -> Path:
    doc = render(view, archive_present=(run_dir / "archive").is_dir(), run_dir=run_dir)
    found = scan(doc, credential_values)
    if found:
        raise BenchError("HB-SEC-001", f"{found} credential-shaped string(s) in the report; nothing was written")
    path = run_dir / "report.html"
    path.write_text(doc, encoding="utf-8", newline="\n")
    return path
