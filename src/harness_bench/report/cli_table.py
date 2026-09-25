"""`bench report <run_id>`: the CLI leaderboard (design: CLI states; T-CLI-plain, T-CLI-states).

One row per combo x pack from `views.leaderboard`. `plain` (NO_COLOR or redirected stdout) gives ASCII
with no colour; NA and invalid marks are text. States, in order:
- not graded: `Run <id> is not graded yet. Run bench grade <id>.` (exit 4);
- no completed cell: `No cell completed in run <id>. Run bench status <id> to see why.`;
- otherwise the table, then the invalid and the "not recorded" cells with their validity and code (R-15, R-27),
  then each view warning with its code (R-24/R-26 c5, R-28), each list only when it has a line.
The seven area composites, cost of pass and per-scenario rows are later phases (Spec S-10).
"""

from __future__ import annotations

import io

from rich import box
from rich.console import Console
from rich.table import Table

from harness_bench import report, views

NOT_GRADED_EXIT = 4


def render(view: views.RunView, plain: bool) -> tuple[str, int]:
    rid = view.run_id
    if view.grading_id is None:
        return f"Run {rid} is not graded yet. Run bench grade {rid}.\n", NOT_GRADED_EXIT
    if not any(c.outcome == "completed" for c in view.cells):
        return f"No cell completed in run {rid}. Run bench status {rid} to see why.\n", 0
    table = Table(box=box.ASCII if plain else box.SIMPLE_HEAVY, title=f"Run {rid} (catalog {view.catalog_version})")
    for name, right in (("Rank", False), ("Combo", False), ("Pack", False), ("Valid", True), ("pass@1", True), ("Interval", False),
                        ("Tokens/cell", True), ("Wall/cell", True), ("Cost/cell", True)):
        table.add_column(name, justify="right" if right else "left", no_wrap=True, overflow="fold")
    for r in views.leaderboard(view):
        table.add_row(r.rank or "-", r.combo, r.pack, f"{r.n_valid}/{r.n_cells}", report.rate(r.pass_at_1), r.interval,
                      report.tokens(r.tokens), report.seconds(r.wall_ms), report.usd(r.cost_usd))
    buf = io.StringIO()
    console = Console(file=buf, width=250, color_system=None if plain else "auto", legacy_windows=False, highlight=False)
    console.print(table)
    not_valid = [c for c in view.cells if c.validity.startswith("invalid") or c.validity == "not recorded"]
    if not_valid:
        console.print("Cells that are not valid:")
        for c in not_valid:
            console.print(f"  {c.label}: {c.validity} {c.validity_code}", markup=False)
    warned = [(c, w) for c in view.cells for w in c.warnings]
    if warned:
        console.print("Warnings:")
        for c, w in warned:
            console.print(f"  {c.label}: {w.code} {w.message}", markup=False)
    if report.has_codex_cell(view.plan):
        console.print(f"{report.N5_FLAG}: see {report.N5_EVIDENCE}")
    if report.has_claude_code_cell(view.plan):
        console.print(f"{report.R36_FLAG}: see {report.R36_EVIDENCE}")
    return buf.getvalue(), 0
