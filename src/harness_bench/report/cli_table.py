"""`bench report <run_id>`: the CLI leaderboard (design: CLI states; T-CLI-plain, T-CLI-states).

One row per combo x pack from `board.py`. `plain` (NO_COLOR or redirected stdout) gives ASCII
with no colour; NA and invalid marks are text. States, in order:
- not graded: `Run <id> is not graded yet. Run bench grade <id>.` (exit 4);
- no completed cell: `No cell completed in run <id>. Run bench status <id> to see why.`;
- otherwise the table, the pack-effect table, then one ASCII headline line per (combo, pack,
  scenario) (design s6 row 7, R6), then the invalid and the "not recorded" cells with their validity
  and code (R-15, R-27), then each view warning with its code (R-24/R-26 c5, R-28), each list only
  when it has a line.
The seven area composites are a later phase (Spec S-10).
"""

from __future__ import annotations

import io
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from harness_bench import board, composites, config, report, stats, views
from harness_bench.errors import BenchError

NOT_GRADED_EXIT = 4


def render(
    view: views.RunView,
    plain: bool,
    run_dir: Path | None = None,
    root: Path | None = None,
    board_obj: board.Board | None = None,
    params: stats.Params | None = None,
    comparison_obj: board.Comparison | None = None,
) -> tuple[str, int]:
    rid = view.run_id
    if view.grading_id is None:
        return f"Run {rid} is not graded yet. Run bench grade {rid}.\n", NOT_GRADED_EXIT
    if not any(c.outcome == "completed" for c in view.cells):
        return f"No cell completed in run {rid}. Run bench status {rid} to see why.\n", 0

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
                version=view.catalog_version or "0.4",
                hash="",
                metrics={},
                areas={},
                has_anchors=False,
            )
        board_obj = board.build(view, cat, params=params)

    box_style = box.ASCII if plain else box.SIMPLE_HEAVY
    table = Table(box=box_style, title=f"Run {rid} (catalog {view.catalog_version})")
    for name, right in (
        ("Rank", False),
        ("Combo", False),
        ("Pack", False),
        ("Valid", True),
        ("pass@1", True),
        ("pass@1 95%", False),
        ("Gated", True),
        ("Gated 95%", False),
        ("Tokens/cell", True),
        ("Wall/cell", True),
        ("Cost/cell", True),
    ):
        table.add_column(name, justify="right" if right else "left", no_wrap=True, overflow="fold")

    for r in board_obj.rows:
        p1_pt = f"{r.pass_at_1.point:.2f}" if r.pass_at_1.point is not None else f"NA ({r.pass_at_1.reason})"
        if r.pass_at_1.lo is not None and r.pass_at_1.hi is not None:
            p1_iv = f"[{r.pass_at_1.lo:.2f}, {r.pass_at_1.hi:.2f}]"
        else:
            p1_iv = r.pass_at_1.reason or "interval not computed"

        gated_pt = f"{r.gated.point:.1f}" if r.gated.point is not None else f"NA ({r.gated.reason})"
        if r.gated.lo is not None and r.gated.hi is not None:
            gated_iv = f"[{r.gated.lo:.1f}, {r.gated.hi:.1f}]"
        else:
            gated_iv = r.gated.reason or "interval not computed"

        table.add_row(
            r.rank or "-",
            report.flag_if_claude_code(report.flag_if_codex(r.combo, r.harness), r.harness),
            r.pack,
            f"{r.n_valid}/{r.n_cells}",
            p1_pt,
            p1_iv,
            gated_pt,
            gated_iv,
            report.tokens(r.tokens),
            report.seconds(r.wall_ms),
            report.usd(r.cost_usd),
        )

    buf = io.StringIO()
    console = Console(file=buf, width=400, color_system=None if plain else "auto", legacy_windows=False, highlight=False)
    for label, value in report.disclosure_rows(root, view.plan, run_dir, view, board_obj=board_obj, params=params):  # same rows as the HTML header
        console.print(f"{label}: {value}", markup=False)
    console.print(table)

    for r in board_obj.rows:
        if not r.rank and r.rank_reason:
            console.print(f"{r.combo} {r.pack}: {r.rank_reason}", markup=False)  # rank_reason starts "not ranked: " (stats.rank)
        if r.footnote:
            console.print(f"{r.combo} {r.pack}: {r.footnote}", markup=False)

    pe = board_obj.pack_effect
    console.print(pe.exclusion_line, markup=False)
    if pe.status is not None:
        console.print(pe.status, markup=False)
    elif pe.rows:
        pe_table = Table(box=box_style, title="Pack effect")
        show_pair = any(pr.pair != board.LEGACY_PAIR for pr in pe.rows)  # a legacy run has one pair; naming it adds nothing
        for name, right in (("Pair", False), ("Combo", False), ("Measure", False), ("Delta", True), ("95% Interval", False), ("Label", False)):
            if name == "Pair" and not show_pair:
                continue
            pe_table.add_column(name, justify="right" if right else "left", no_wrap=True, overflow="fold")
        for pr in pe.rows:
            is_p1 = pr.measure == "pass_at_1"
            if pr.delta.point is not None:
                delta_str = f"{pr.delta.point:+.2f}" if is_p1 else f"{pr.delta.point:+.1f}"
            else:
                delta_str = pr.reason or "NA"
            if pr.delta.lo is not None and pr.delta.hi is not None:
                iv_str = f"[{pr.delta.lo:.2f}, {pr.delta.hi:.2f}]" if is_p1 else f"[{pr.delta.lo:.1f}, {pr.delta.hi:.1f}]"
            else:
                iv_str = pr.reason or pr.delta.reason or "interval not computed"
            label_str = pr.label or ""
            pe_table.add_row(*([" vs ".join(pr.pair)] if show_pair else []), pr.combo, pr.measure, delta_str, iv_str, label_str)
        console.print(pe_table)

    # R6 (design s6 row 7, s12 UIA-11): one ASCII headline line per (combo, pack, scenario) --
    # the plain-output rule, so this reads with NO_COLOR=1 and a redirected stdout the same as the
    # rest of the table (`console.print(..., markup=False)`, the same call every other CLI row uses).
    for sr in board_obj.scenarios:
        gated, p1 = sr.gated, sr.pass_at_1
        if gated.point is not None:
            iv_str = f"[{gated.lo:.1f}, {gated.hi:.1f}]" if gated.lo is not None and gated.hi is not None else (
                gated.reason or "interval not computed")
            p1_str = f"pass@1 {p1.point:.2f}" if p1.point is not None else f"pass@1 {p1.reason or 'NA'}"
            line = f"{sr.combo} {sr.pack} scenario {sr.scenario}: {gated.point:.1f} {iv_str} {p1_str}"
        else:
            line = f"{sr.combo} {sr.pack} scenario {sr.scenario}: {gated.reason or 'NA'}"
        console.print(line, markup=False)

    if comparison_obj is not None:
        console.print(comparison_obj.exclusion_line, markup=False)
        if comparison_obj.same_pack_revision is not None:
            console.print(f"same pack revision ({comparison_obj.same_pack_revision}): a replication", markup=False)
        if comparison_obj.unshared_tasks:
            console.print(f"Tasks in one run only: {', '.join(sorted(comparison_obj.unshared_tasks))}", markup=False)
        if comparison_obj.rows:
            comp_table = Table(box=box_style, title=f"Comparison: {comparison_obj.view_run_id} vs baseline {comparison_obj.base_run_id}")
            for name, right in (("Combo", False), ("Pack", False), ("Measure", False), ("Delta", True), ("95% Interval", False), ("Label", False)):
                comp_table.add_column(name, justify="right" if right else "left", no_wrap=True, overflow="fold")
            for cr in comparison_obj.rows:
                is_p1 = cr.measure == "pass_at_1"
                if cr.delta.point is not None:
                    delta_str = f"{cr.delta.point:+.2f}" if is_p1 else f"{cr.delta.point:+.1f}"
                else:
                    delta_str = cr.delta.reason or "NA"
                if cr.delta.lo is not None and cr.delta.hi is not None:
                    iv_str = f"[{cr.delta.lo:.2f}, {cr.delta.hi:.2f}]" if is_p1 else f"[{cr.delta.lo:.1f}, {cr.delta.hi:.1f}]"
                else:
                    iv_str = cr.delta.reason or "interval not computed"
                label_str = cr.label or ""
                comp_table.add_row(cr.combo, cr.pack, cr.measure, delta_str, iv_str, label_str)
            console.print(comp_table)

    if board_obj.areas:
        combos_packs: list[tuple[str, str]] = []
        areas_by_cp: dict[tuple[str, str], list[board.AreaRow]] = {}
        for ar in board_obj.areas:
            key = (ar.combo, ar.pack)
            if key not in areas_by_cp:
                combos_packs.append(key)
                areas_by_cp[key] = []
            areas_by_cp[key].append(ar)
        for combo, pack in combos_packs:
            row_areas = areas_by_cp[(combo, pack)]
            parts = []
            for ar in row_areas:
                if ar.interval.point is not None:
                    parts.append(f"{ar.area} {ar.interval.point:.1f}")
                else:
                    reason = ar.interval.reason or "not recorded"
                    parts.append(f"{ar.area} NA ({reason})")
            line = f"Areas ({combo} {pack}): {', '.join(parts)}"
            line = line.replace("—", "-").replace("−", "-")
            console.print(line, markup=False)

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
    labels = {c.cell_id: c.label for c in view.cells}
    for cell_id, text in report.d1_mutation_values(root, run_dir, view).items():
        console.print(f"{labels[cell_id]}: mutation_score {text}", markup=False)
    return buf.getvalue(), 0
