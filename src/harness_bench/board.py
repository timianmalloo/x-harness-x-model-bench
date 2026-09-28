"""Board projection: derived statistics board, pack-effect, and canonical export (S5).

Replaces `views.leaderboard`. Derived at read time, never stored (ADR-0006).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from harness_bench import ledger
from harness_bench.composites import Catalog
from harness_bench.composites import area as compute_area
from harness_bench.composites import gated as compute_gated
from harness_bench.composites import normalise as compute_normalise
from harness_bench.errors import BenchError
from harness_bench.stats import (
    CONTAMINATION_PRONE,
    DEFAULT_SEED,
    METHOD,
    MIN_RESAMPLES,
    Interval,
    Measure,
    Obs,
    Params,
    interval,
    no_detectable_effect,
    paired_delta,
    pass_k,
    rank,
)

DEFAULT_RESAMPLES: int = MIN_RESAMPLES
from harness_bench.views import CellView, RunView


@dataclass
class BoardRow:
    combo: str
    pack: str
    harness: str
    model: str
    n_cells: int
    n_valid: int
    pass_at_1: Interval
    gated: Interval
    pass_at_k: Measure
    pass_hat_k: Measure
    rank: str
    rank_reason: str | None
    tokens: Measure
    wall_ms: Measure
    cost_usd: Measure
    footnote: str | None = None

    @property
    def interval(self) -> str:
        """Compatibility property for report renderers."""
        iv = self.pass_at_1
        if iv.lo is not None and iv.hi is not None:
            return f"[{iv.lo:.2f}, {iv.hi:.2f}]"
        return iv.reason or "interval not computed"


@dataclass
class PackEffectRow:
    combo: str
    measure: str
    delta: Interval
    label: str | None
    reason: str | None = None


@dataclass
class PackEffect:
    status: str | None
    excluded_tasks: tuple[str, ...]
    rows: list[PackEffectRow]

    @property
    def exclusion_line(self) -> str:
        if self.excluded_tasks:
            return f"Excluded as contamination-prone: {', '.join(sorted(self.excluded_tasks))}"
        return "Excluded as contamination-prone: none in this run"


@dataclass
class ComparisonRow:
    combo: str
    pack: str
    measure: str
    delta: Interval
    label: str | None


@dataclass
class Comparison:
    base_run_id: str
    view_run_id: str
    excluded_tasks: tuple[str, ...]
    unshared_tasks: tuple[str, ...]
    rows: list[ComparisonRow]
    same_pack_revision: str | None = None

    @property
    def exclusion_line(self) -> str:
        if self.excluded_tasks:
            return f"Excluded as contamination-prone: {', '.join(sorted(self.excluded_tasks))}"
        return "Excluded as contamination-prone: none in this run"


@dataclass
class Board:
    run_id: str
    catalog_version: str | None
    params: Params
    primary: str
    primary_reason: str | None
    rows: list[BoardRow]
    pack_effect: PackEffect


def _mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal(0)
    return sum(values, Decimal(0)) / Decimal(len(values))


def _cell_task_rep(cell_id: str, plan_by_id: Mapping[str, dict]) -> tuple[str, int, str]:
    rec = plan_by_id.get(cell_id, {})
    return str(rec.get("task", "X1")), int(rec.get("rep", 1)), str(rec.get("task_version", ""))


def build(view: RunView, cat: Catalog, params: Params | None = None) -> Board:
    """Build the statistics projection for one pass of a run."""
    if params is None:
        params = Params(seed=DEFAULT_SEED, resamples=DEFAULT_RESAMPLES)

    # Primary measure determination (DR-S-1 / R-78 condition 3): the CURRENT PASS's catalog decides. A loaded catalog
    # of another version says nothing about the anchors the pass was graded under, so it never makes the primary gated.
    if view.catalog_version != cat.version:
        primary = "pass_at_1"
        primary_reason = (f"the current pass is catalog {view.catalog_version}; anchors are read only from that "
                          f"version (loaded: {cat.version})")
    elif not cat.has_anchors:
        primary = "pass_at_1"
        primary_reason = f"catalog {cat.version} has no normalisation anchors"
    else:
        primary = "gated"
        primary_reason = None
    # the short per-cell form of the cause; the header's primary-measure line carries the full reason (US-27)
    no_anchor_cell = f"no normalisation anchors for catalog {view.catalog_version}"

    plan_cells = (view.plan or {}).get("cells", [])
    plan_by_id = {c["cell_id"]: c for c in plan_cells if isinstance(c, dict) and "cell_id" in c}
    planned_k = int(view.plan.get("matrix", {}).get("repetitions", 1))

    # Group cells by (combo, pack)
    groups: dict[tuple[str, str], list[CellView]] = {}
    for c in view.cells:
        groups.setdefault((c.combo, c.pack), []).append(c)

    rows_dict: dict[tuple[str, str], BoardRow] = {}
    rank_inputs: dict[tuple[str, str], tuple[Interval, Interval]] = {}

    for (combo, pack), cells in groups.items():
        valid_cells = [c for c in cells if c.validity == "valid"]
        n_cells = len(cells)
        n_valid = len(valid_cells)
        first = cells[0]
        harness = first.harness
        model = first.model

        # pass@1 observations from valid cells with a non-NA score
        obs_p1: list[Obs] = []
        na_p1_cells: list[CellView] = []
        for c in valid_cells:
            score = c.scores.get("pass_at_1")
            if score is not None and score.value is not None:
                t, r, _ = _cell_task_rep(c.cell_id, plan_by_id)
                obs_p1.append(Obs(task=t, rep=r, value=Decimal(str(score.value))))
            else:
                na_p1_cells.append(c)

        key_p1 = f"pass_at_1|{combo}|{pack}"
        iv_p1 = interval(obs_p1, params, key_p1)

        # Footnote for NA cells (T-B8)
        if na_p1_cells:
            first_reason = na_p1_cells[0].scores.get("pass_at_1", Measure(None)).reason or "not recorded"
            footnote = f"{len(na_p1_cells)} of {n_valid} valid cells NA: {first_reason}"
        else:
            footnote = None

        # Gated composite
        obs_gated: list[Obs] = []
        if primary == "gated":  # anchors apply only to a pass of the loaded catalog's version (R-78 c3)
            for c in valid_cells:
                t, r, _ = _cell_task_rep(c.cell_id, plan_by_id)
                norm_scores = {
                    mid: compute_normalise(mid, s, cat, view.catalog_version, cat.hash)
                    for mid, s in c.scores.items()
                }
                all_scores = {**c.scores, **norm_scores}
                gated_score = compute_gated(all_scores, cat)
                if gated_score.value is not None:
                    obs_gated.append(Obs(task=t, rep=r, value=Decimal(str(gated_score.value))))
            key_gated = f"gated|{combo}|{pack}"
            iv_gated = interval(obs_gated, params, key_gated)
        else:
            iv_gated = Interval(
                point=None,
                lo=None,
                hi=None,
                n=0,
                reason=no_anchor_cell,
            )

        # pass@k and pass^k per task
        task_outcomes: dict[str, list[int]] = {}
        for c in valid_cells:
            t, _, _ = _cell_task_rep(c.cell_id, plan_by_id)
            score = c.scores.get("pass_at_1")
            if score is not None and score.value is not None:
                task_outcomes.setdefault(t, []).append(int(score.value))

        at_k_vals: list[Decimal] = []
        hat_k_vals: list[Decimal] = []
        for t, outcomes_list in task_outcomes.items():
            at_k, hat_k = pass_k(outcomes_list, planned=planned_k)
            if at_k.value is not None:
                at_k_vals.append(at_k.value)
            if hat_k.value is not None:
                hat_k_vals.append(hat_k.value)

        row_pass_at_k = (
            Measure(_mean(at_k_vals))
            if at_k_vals
            else Measure(None, "no task with pass@k")
        )
        row_pass_hat_k = (
            Measure(_mean(hat_k_vals))
            if hat_k_vals
            else Measure(None, "no task with pass^k")
        )

        # Cost, tokens, wall_ms (moved verbatim from views._row)
        used = [sum(sum(b.values()) for b in c.tokens.values()) for c in valid_cells if c.tokens]
        walls = [c.wall_ms.value for c in valid_cells if c.wall_ms.value is not None]
        no_cost = [c for c in valid_cells if c.scores.get("cost_usd", Measure(None, "not graded")).value is None]

        if not valid_cells:
            cost = Measure(None, "no valid cell")
        elif no_cost:
            reason = no_cost[0].scores.get("cost_usd", Measure(None, "not graded")).reason
            cost = Measure(None, f"{len(no_cost)} of {len(valid_cells)} valid cells have no cost: {reason}")
        else:
            cost = Measure(_mean([Decimal(str(c.scores["cost_usd"].value)) for c in valid_cells]))

        tokens_m = Measure(_mean([Decimal(u) for u in used])) if used else Measure(None, "no valid cell with usage")
        wall_m = Measure(_mean([Decimal(w) for w in walls])) if walls else Measure(None, "no valid cell with wall time")

        primary_iv = iv_p1 if primary == "pass_at_1" else iv_gated
        rank_inputs[(combo, pack)] = (primary_iv, iv_p1)

        row = BoardRow(
            combo=combo,
            pack=pack,
            harness=harness,
            model=model,
            n_cells=n_cells,
            n_valid=n_valid,
            pass_at_1=iv_p1,
            gated=iv_gated,
            pass_at_k=row_pass_at_k,
            pass_hat_k=row_pass_hat_k,
            rank="",
            rank_reason=None,
            tokens=tokens_m,
            wall_ms=wall_m,
            cost_usd=cost,
            footnote=footnote,
        )
        rows_dict[(combo, pack)] = row

    # Ranks
    ranks = rank(rank_inputs)
    ordered_rows: list[BoardRow] = []
    for row_id, (rk, rk_reason) in ranks.items():
        r = rows_dict[row_id]
        r.rank = rk
        r.rank_reason = rk_reason
        ordered_rows.append(r)

    # Pack effect
    pack_effect = _build_pack_effect(view, cat, params, plan_by_id, no_anchor_cell if primary != "gated" else None)

    return Board(
        run_id=view.run_id,
        catalog_version=view.catalog_version,
        params=params,
        primary=primary,
        primary_reason=primary_reason,
        rows=ordered_rows,
        pack_effect=pack_effect,
    )


def _build_pack_effect(
    view: RunView,
    cat: Catalog,
    params: Params,
    plan_by_id: Mapping[str, dict],
    no_anchors: str | None = None,
) -> PackEffect:
    """`no_anchors` is the primary measure's reason when anchors do not apply to this pass (R-78 c3); area rows are
    then NA with that reason, never a composite computed from another catalog version's anchors."""
    pack_settings = sorted({c.pack for c in view.cells})
    tasks_in_run = sorted({_cell_task_rep(c.cell_id, plan_by_id)[0] for c in view.cells})
    excluded_tasks = tuple(t for t in tasks_in_run if t in CONTAMINATION_PRONE)

    if not ({"off", "on"} <= set(pack_settings)):
        return PackEffect(
            status="This run has one pack setting; no effect to show.",
            excluded_tasks=excluded_tasks,
            rows=[],
        )

    combos = sorted({c.combo for c in view.cells})
    pe_rows: list[PackEffectRow] = []

    measures = ["pass_at_1", *cat.areas]

    for combo in combos:
        combo_cells = [c for c in view.cells if c.combo == combo]
        combo_packs = {c.pack for c in combo_cells}
        if not ({"off", "on"} <= combo_packs):
            for m in measures:
                pe_rows.append(
                    PackEffectRow(
                        combo=combo,
                        measure=m,
                        delta=Interval(None, None, None, 0, "Pack effect needs both settings."),
                        label=None,
                        reason="Pack effect needs both settings.",
                    )
                )
            continue

        clean_cells = [
            c for c in combo_cells
            if _cell_task_rep(c.cell_id, plan_by_id)[0] not in CONTAMINATION_PRONE
        ]

        for m in measures:
            if m != "pass_at_1" and no_anchors is not None:
                na = Interval(None, None, None, 0, no_anchors)
                pe_rows.append(PackEffectRow(combo=combo, measure=m, delta=na, label=None, reason=no_anchors))
                continue
            if m == "pass_at_1":
                off_obs = [
                    Obs(
                        _cell_task_rep(c.cell_id, plan_by_id)[0],
                        _cell_task_rep(c.cell_id, plan_by_id)[1],
                        Decimal(str(c.scores["pass_at_1"].value)),
                    )
                    for c in clean_cells
                    if c.pack == "off"
                    and c.validity == "valid"
                    and c.scores.get("pass_at_1", Measure(None)).value is not None
                ]
                on_obs = [
                    Obs(
                        _cell_task_rep(c.cell_id, plan_by_id)[0],
                        _cell_task_rep(c.cell_id, plan_by_id)[1],
                        Decimal(str(c.scores["pass_at_1"].value)),
                    )
                    for c in clean_cells
                    if c.pack == "on"
                    and c.validity == "valid"
                    and c.scores.get("pass_at_1", Measure(None)).value is not None
                ]
            else:
                # Area score
                off_obs = []
                for c in clean_cells:
                    if (
                        c.pack == "off"
                        and c.validity == "valid"
                    ):
                        score = c.scores.get(m)
                        if score is not None and score.value is not None:
                            off_obs.append(
                                Obs(
                                    _cell_task_rep(c.cell_id, plan_by_id)[0],
                                    _cell_task_rep(c.cell_id, plan_by_id)[1],
                                    Decimal(str(score.value)),
                                )
                            )
                on_obs = []
                for c in clean_cells:
                    if (
                        c.pack == "on"
                        and c.validity == "valid"
                    ):
                        score = c.scores.get(m)
                        if score is not None and score.value is not None:
                            on_obs.append(
                                Obs(
                                    _cell_task_rep(c.cell_id, plan_by_id)[0],
                                    _cell_task_rep(c.cell_id, plan_by_id)[1],
                                    Decimal(str(score.value)),
                                )
                            )

            key = f"{m}|{combo}"
            delta_iv, _ = paired_delta(ref=off_obs, treat=on_obs, labels=("off", "on"), params=params, key=key)
            is_nde = no_detectable_effect(delta_iv)
            label = "no detectable effect" if is_nde is True else None
            pe_rows.append(
                PackEffectRow(
                    combo=combo,
                    measure=m,
                    delta=delta_iv,
                    label=label,
                    reason=delta_iv.reason,
                )
            )

    return PackEffect(status=None, excluded_tasks=excluded_tasks, rows=pe_rows)


def header_row(board: Board) -> str:
    """Format disclosure line according to R-78 condition 3."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    if board.primary == "pass_at_1":
        ranked_on = f"pass@1 ({board.primary_reason})"
    else:
        ranked_on = "correctness-gated composite"
    return (
        f"statistics: {METHOD}, {board.params.resamples} resamples, "
        f"seed {board.params.seed}, resampled by task then repetition, "
        f"Python {py_ver} random stream; ranked on {ranked_on}"
    )


def timing_line(intervals: int, seconds: float) -> str:
    """Format the timing telemetry line (US-36, design section Telemetry)."""
    return f"statistics: {intervals} intervals in {seconds:.3f} s"


def compare(base: RunView, view: RunView, cat: Catalog, params: Params | None = None) -> Comparison:
    """Two-run comparison under US-52 preconditions."""
    if params is None:
        params = Params(seed=DEFAULT_SEED, resamples=DEFAULT_RESAMPLES)

    if base.run_id == view.run_id:
        raise BenchError("HB-STA-001", "statistics input spans more than one grading pass of one run")

    diffs: list[str] = []

    # 1. Graded
    if base.grading_id is None:
        diffs.append(f"run {base.run_id} is not graded")
    if view.grading_id is None:
        diffs.append(f"run {view.run_id} is not graded")

    # 2. Combos
    base_combos = {
        (c.get("id"), c.get("harness"), c.get("model"))
        for c in base.plan.get("matrix", {}).get("combos", [])
    }
    view_combos = {
        (c.get("id"), c.get("harness"), c.get("model"))
        for c in view.plan.get("matrix", {}).get("combos", [])
    }
    if base_combos != view_combos:
        only_a = [c[0] for c in sorted(base_combos - view_combos) if c[0]]
        only_b = [c[0] for c in sorted(view_combos - base_combos) if c[0]]
        combo_parts = []
        if only_a:
            combo_parts.append(f"only in A: {', '.join(only_a)}")
        if only_b:
            combo_parts.append(f"only in B: {', '.join(only_b)}")
        diffs.append(f"combos differ: {'; '.join(combo_parts)}")

    # 3. BOM version
    base_bom = base.plan.get("bom_version")
    view_bom = view.plan.get("bom_version")
    if base_bom != view_bom:
        diffs.append(f"BOM version differs: A {base_bom}, B {view_bom}")

    # 4. Catalog version
    if base.catalog_version != view.catalog_version:
        diffs.append(f"catalog version differs: A {base.catalog_version}, B {view.catalog_version}")

    # 5. Task versions
    base_plan_by_id = {c["cell_id"]: c for c in base.plan.get("cells", [])}
    view_plan_by_id = {c["cell_id"]: c for c in view.plan.get("cells", [])}

    base_task_vers = {c.get("task"): c.get("task_version") for c in base_plan_by_id.values()}
    view_task_vers = {c.get("task"): c.get("task_version") for c in view_plan_by_id.values()}

    shared_tasks = sorted(set(base_task_vers) & set(view_task_vers))
    for t in shared_tasks:
        if base_task_vers[t] != view_task_vers[t]:
            diffs.append(f"task version of {t} differs")

    if diffs:
        raise BenchError("HB-STA-002", "; ".join(diffs))

    # Compute deltas treat (view) - ref (base)
    all_tasks = sorted(set(base_task_vers) | set(view_task_vers))
    unshared_tasks = tuple(sorted(set(base_task_vers) ^ set(view_task_vers)))
    excluded_tasks = tuple(t for t in all_tasks if t in CONTAMINATION_PRONE)

    base_rev = (base.plan or {}).get("pack", {}).get("revision")
    view_rev = (view.plan or {}).get("pack", {}).get("revision")
    same_pack_revision = base_rev if base_rev is not None and base_rev == view_rev else None

    # VER-A rule (R-78 c3 / design): area composite deltas computed only when both runs' current
    # passes are of the loaded catalog's version; otherwise area rows are NA with the reason,
    # and pass@1 deltas are still computed.
    if base.catalog_version != cat.version or not cat.has_anchors:
        no_anchors: str | None = f"no normalisation anchors for catalog {base.catalog_version}"
    else:
        no_anchors = None

    combos = sorted({c.get("id") for c in base.plan.get("matrix", {}).get("combos", []) if c.get("id")})
    packs = ("off", "on")
    measures = ["pass_at_1", *cat.areas]

    comp_rows: list[ComparisonRow] = []

    for combo in combos:
        for pack in packs:
            for m in measures:
                if m != "pass_at_1" and no_anchors is not None:
                    delta_iv = Interval(point=None, lo=None, hi=None, n=0, reason=no_anchors)
                    comp_rows.append(
                        ComparisonRow(
                            combo=combo,
                            pack=pack,
                            measure=m,
                            delta=delta_iv,
                            label=None,
                        )
                    )
                    continue

                base_cells = [
                    c for c in base.cells
                    if c.combo == combo
                    and c.pack == pack
                    and c.validity == "valid"
                    and _cell_task_rep(c.cell_id, base_plan_by_id)[0] not in CONTAMINATION_PRONE
                ]
                view_cells = [
                    c for c in view.cells
                    if c.combo == combo
                    and c.pack == pack
                    and c.validity == "valid"
                    and _cell_task_rep(c.cell_id, view_plan_by_id)[0] not in CONTAMINATION_PRONE
                ]

                obs_a: list[Obs] = []
                for c in base_cells:
                    score = c.scores.get(m)
                    if (score is None or score.value is None) and m != "pass_at_1":
                        norm_scores = {
                            mid: compute_normalise(mid, s, cat, base.catalog_version, cat.hash)
                            for mid, s in c.scores.items()
                        }
                        all_scores = {**c.scores, **norm_scores}
                        score, _ = compute_area(all_scores, m, cat)
                    if score is not None and score.value is not None:
                        t, r, _ = _cell_task_rep(c.cell_id, base_plan_by_id)
                        obs_a.append(Obs(task=t, rep=r, value=Decimal(str(score.value))))

                obs_b: list[Obs] = []
                for c in view_cells:
                    score = c.scores.get(m)
                    if (score is None or score.value is None) and m != "pass_at_1":
                        norm_scores = {
                            mid: compute_normalise(mid, s, cat, view.catalog_version, cat.hash)
                            for mid, s in c.scores.items()
                        }
                        all_scores = {**c.scores, **norm_scores}
                        score, _ = compute_area(all_scores, m, cat)
                    if score is not None and score.value is not None:
                        t, r, _ = _cell_task_rep(c.cell_id, view_plan_by_id)
                        obs_b.append(Obs(task=t, rep=r, value=Decimal(str(score.value))))

                key = f"{m}|{combo}|{pack}"
                delta_iv, _ = paired_delta(ref=obs_a, treat=obs_b, labels=(base.run_id, view.run_id), params=params, key=key)
                is_nde = no_detectable_effect(delta_iv)
                label = "no detectable effect" if is_nde is True else None
                comp_rows.append(
                    ComparisonRow(
                        combo=combo,
                        pack=pack,
                        measure=m,
                        delta=delta_iv,
                        label=label,
                    )
                )

    return Comparison(
        base_run_id=base.run_id,
        view_run_id=view.run_id,
        excluded_tasks=excluded_tasks,
        unshared_tasks=unshared_tasks,
        rows=comp_rows,
        same_pack_revision=same_pack_revision,
    )


def _fmt_decimal(val: Any) -> str | None:
    if val is None:
        return None
    d = Decimal(str(val))
    return str(d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _enc_interval(iv: Interval) -> dict[str, Any]:
    return {
        "point": _fmt_decimal(iv.point) if iv.point is not None else None,
        "lo": _fmt_decimal(iv.lo) if iv.lo is not None else None,
        "hi": _fmt_decimal(iv.hi) if iv.hi is not None else None,
        "n": iv.n,
        "reason": iv.reason,
    }


def _enc_measure(m: Measure) -> dict[str, Any]:
    return {
        "value": _fmt_decimal(m.value) if m.value is not None else None,
        "reason": m.reason,
    }


def export(board: Board, comparison: Comparison | None = None) -> bytes:
    """Canonical statistics export bytes (R-78 DR-S-4, DR-S-5).

    Records METHOD, seed, resamples, primary measure, rows and pack-effect.
    Does NOT include Python version or timing line.
    """
    rows_data = [
        {
            "combo": r.combo,
            "pack": r.pack,
            "harness": r.harness,
            "model": r.model,
            "n_cells": r.n_cells,
            "n_valid": r.n_valid,
            "pass_at_1": _enc_interval(r.pass_at_1),
            "gated": _enc_interval(r.gated),
            "pass_at_k": _enc_measure(r.pass_at_k),
            "pass_hat_k": _enc_measure(r.pass_hat_k),
            "rank": r.rank,
            "rank_reason": r.rank_reason,
            "tokens": _enc_measure(r.tokens),
            "wall_ms": _enc_measure(r.wall_ms),
            "cost_usd": _enc_measure(r.cost_usd),
            "footnote": r.footnote,
        }
        for r in board.rows
    ]

    pack_effect_data = {
        "status": board.pack_effect.status,
        "excluded_tasks": list(board.pack_effect.excluded_tasks),
        "rows": [
            {
                "combo": pr.combo,
                "measure": pr.measure,
                "delta": _enc_interval(pr.delta),
                "label": pr.label,
                "reason": pr.reason,
            }
            for pr in board.pack_effect.rows
        ],
    }

    payload: dict[str, Any] = {
        "method": METHOD,
        "seed": board.params.seed,
        "resamples": board.params.resamples,
        "run_id": board.run_id,
        "catalog_version": board.catalog_version,
        "primary": board.primary,
        "primary_reason": board.primary_reason,
        "rows": rows_data,
        "pack_effect": pack_effect_data,
    }

    if comparison is not None:
        payload["comparison"] = {
            "base_run_id": comparison.base_run_id,
            "view_run_id": comparison.view_run_id,
            "excluded_tasks": list(comparison.excluded_tasks),
            "unshared_tasks": list(comparison.unshared_tasks),
            "rows": [
                {
                    "combo": cr.combo,
                    "pack": cr.pack,
                    "measure": cr.measure,
                    "delta": _enc_interval(cr.delta),
                    "label": cr.label,
                }
                for cr in comparison.rows
            ],
        }

    return ledger.canonical(payload)

