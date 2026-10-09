"""The lean pack benchmark's summary (ADR-0023): a pure derived view over one or two lean batches.

This is the contract only (L-CONTRACT), exactly as `docs/architecture-lean-benchmark.md`, *Contracts at the
seams*. `build` is L-SUM-A's to write; the renderer (L-SUM-B1) reads `LeanSummary` and the CLI (L-SUM-C) builds
`BatchInput` and `Prereg`. The summary is never stored: it is recomputed on every `bench report`. Arm ids come from
`plan.comparisons` and `config.ARM_OFF`, never from literals in this module.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from harness_bench import plan, power, stats, verdicts
from harness_bench.errors import BenchError
from harness_bench.stats import Interval
from harness_bench.views import CellView, RunView


@dataclass(frozen=True)
class BatchInput:
    view: RunView
    run_wall_ns: int | None  # from the extracted wall-clock helper
    grading_ns: int | None  # current pass, from grading.started/completed mono_ns
    cells_graded: int | None
    first_cell_started_at: datetime | None  # the batch's earliest attempt.process_started; None = not recorded


@dataclass(frozen=True)
class Prereg:
    sha256: str
    committed_at: datetime | None  # None = not committed


@dataclass(frozen=True)
class LeanRow:
    combo: str
    harness: str
    model: str
    effect: Decimal | None  # stats.paired_delta (two-stage)
    lo: Decimal | None
    hi: Decimal | None
    mde: Decimal  # power.mde_for: per harness 20->0.31 or 10->0.42; pooled 60->0.19 or 30->0.26
    pairs: int
    planned_pairs: int  # "k of 20 pairs recorded"
    excluded: tuple[tuple[str, str], ...]  # ("<run_id>/<cell_id>", cause), from verdicts.collect
    statement: str  # "no detectable effect" | "pack-on higher by x" | "pack-on lower by x" | "not recorded (0 pairs)"
    token_ratio: Interval | None  # stats.paired_ratio over token-complete pairs (ratio of totals)
    ratio_excluded: int  # pairs without recorded tokens, or with 0 pack-off tokens


@dataclass(frozen=True)
class PropertyRow:
    family: str  # S, RS, RW, NG, SM x combo
    harness: str
    off: tuple[int, int]  # (passes, recorded)
    on: tuple[int, int]
    direction: Literal["up", "down", "same"]


@dataclass(frozen=True)
class BatchCheckpoint:
    run_id: str
    cells: int
    run_min_per_cell: Decimal | None  # None = "not recorded", never 0
    grade_min_per_cell: Decimal | None
    tokens_per_cell: Mapping[tuple[str, str], Decimal | None]  # (combo, arm)
    infra_failures: Mapping[str, tuple[int, int, tuple[str, ...]]]  # combo -> (k, n, causes); > 20% is named (LB-3)


@dataclass(frozen=True)
class LeanSummary:
    batches: int  # 1 or 2
    run_ids: tuple[str, ...]
    plan_hashes: tuple[str, ...]
    prereg_status: str  # "pre-registered (<sha12>)" | "Not pre-registered: <reason>"
    rows: tuple[LeanRow, ...]  # one per combo, plan order
    pooled: LeanRow  # task key "<combo>/<task>"
    disagree: bool  # two harness intervals wholly on opposite sides of 0
    properties: tuple[PropertyRow, ...]
    checkpoint: tuple[BatchCheckpoint, ...]


@dataclass(frozen=True)
class Estimate:
    run_min_per_cell: Decimal
    grade_min_per_cell: Decimal
    tokens_per_cell: int


# LB-3's Inferred estimates, shown beside the measured checkpoint values.
ESTIMATE = Estimate(run_min_per_cell=Decimal("1.12"), grade_min_per_cell=Decimal("1.16"), tokens_per_cell=1_060_000)


RING_TAG = "lean"
_CENT = Decimal("0.01")
_ALPHA = Decimal("0.05")  # the lean summary reports 95% intervals (stats.METHOD)


def _sizer(delta: float) -> float:
    """ADR-0023 decision 6: the design's paired sizer (discordance 0.28, alpha 0.05, power 0.8)."""
    return power.n_paired_exact(0.28, delta, 0.05, 0.8)


def _mde(planned_pairs: int) -> Decimal:
    """Derived, never typed in: 20 -> 0.31, 10 -> 0.42, 60 -> 0.19, 30 -> 0.26."""
    return Decimal(str(power.mde_for(planned_pairs, _sizer))).quantize(_CENT)


def _checked(batches: Sequence[BatchInput]) -> tuple[str, str]:
    """One or two lean batches that name one and the same comparison; returns it (ref arm, treat arm)."""
    if not 1 <= len(batches) <= 2:
        raise BenchError("HB-USR-002", f"the lean summary takes one or two batches, got {len(batches)}")
    comparisons = set()
    for batch in batches:
        view = batch.view
        tag = (view.plan.get("ring") or {}).get("tag")
        if tag != RING_TAG:
            raise BenchError("HB-USR-002", f"run {view.run_id}: ring tag {tag!r}; the lean summary reads {RING_TAG} batches only")
        named = plan.plan_comparisons(view.plan)
        if len(named) != 1:
            raise BenchError("HB-USR-002", f"run {view.run_id}: the lean summary needs one comparison, the plan names {len(named)}")
        comparisons.add(named[0])
    if len(comparisons) != 1:
        raise BenchError("HB-USR-002", f"the batches name different comparisons: {sorted(comparisons)}")
    return comparisons.pop()


def _combos(batches: Sequence[BatchInput]) -> list[tuple[str, str, str]]:
    """(combo, harness, model) in plan order: each combo where it first appears in batch order."""
    seen: dict[str, tuple[str, str, str]] = {}
    for batch in batches:
        for cell in batch.view.plan["cells"]:
            seen.setdefault(cell["combo"], (cell["combo"], cell["harness"], cell["model"]))
    return list(seen.values())


def _planned(batches: Sequence[BatchInput], combo: str | None, ref: str) -> int:
    """Planned pairs: the planned pack-off cells of `combo` (every combo when None) over the batches."""
    return sum(1 for batch in batches for cell in batch.view.plan["cells"]
               if (combo is None or cell["combo"] == combo) and plan.cell_arm(cell) == ref)


def _relabelled(batches: Sequence[BatchInput]) -> list[CellView]:
    """ADR-0023 decision 2: rep = batch index, cell_id = "<run_id>/<cell_id>", so an excluded cell names its batch."""
    return [dataclasses.replace(cell, rep=index, cell_id=f"{batch.view.run_id}/{cell.cell_id}")
            for index, batch in enumerate(batches, 1) for cell in batch.view.cells]


def _statement(interval: Interval) -> str:
    """ADR-0023 decision 5: `no detectable effect` exactly when `stats.no_detectable_effect` says so."""
    if interval.n == 0:
        return "not recorded (0 pairs)"
    null = stats.no_detectable_effect(interval)
    if null is None:
        # assume: an interval that is not computed (pairs from one task only) states no direction. Confirm: the
        # Coordinator rules the wording (handed back with A3). Breaks if false: only this string changes.
        return f"not recorded ({interval.reason})"
    if null:
        return "no detectable effect"
    size = abs(interval.point).quantize(_CENT)
    return f"pack-on higher by {size}" if interval.lo > 0 else f"pack-on lower by {size}"


def _row(combo: str, harness: str, model: str, pairs: Sequence[verdicts.Pair], excluded: Sequence[tuple[str, str]],
         planned: int, comparison: tuple[str, str], seed: int) -> LeanRow:
    ref = [stats.Obs(p.task, p.rep, p.ref) for p in pairs]
    treat = [stats.Obs(p.task, p.rep, p.treat) for p in pairs]
    effect, _ = stats.paired_delta(ref, treat, comparison, stats.Params(seed=seed), f"{RING_TAG}|{combo}")
    return LeanRow(combo=combo, harness=harness, model=model, effect=effect.point, lo=effect.lo, hi=effect.hi,
                   mde=_mde(planned), pairs=len(pairs), planned_pairs=planned, excluded=tuple(excluded),
                   statement=_statement(effect), token_ratio=None, ratio_excluded=0)


def _family(task: str) -> str:
    """A lean task's property family: its leading letters (S1 -> S, RS2 -> RS; the ring's S, RS, RW, NG, SM)."""
    found = re.match(r"[A-Za-z]+", task)
    return found.group(0) if found else task


def _direction(off: int, on: int) -> Literal["up", "down", "same"]:
    return "up" if on > off else "down" if on < off else "same"


def _properties(batches: Sequence[BatchInput], collected: Sequence[tuple[str, str, Sequence[verdicts.Pair]]]
                ) -> tuple[PropertyRow, ...]:
    """LB-6: per family (plan order) and harness (combo plan order), passes over recorded pairs in each arm."""
    families = list(dict.fromkeys(_family(cell["task"]) for batch in batches for cell in batch.view.plan["cells"]))
    out = []
    for family in families:
        for _, harness, pairs in collected:
            mine = [p for p in pairs if _family(p.task) == family]
            off, on = int(sum(p.ref for p in mine)), int(sum(p.treat for p in mine))
            out.append(PropertyRow(family=family, harness=harness, off=(off, len(mine)), on=(on, len(mine)),
                                   direction=_direction(off, on)))
    return tuple(out)


def _disagree(rows: Sequence[LeanRow]) -> bool:
    """LB-5: one harness interval wholly above 0 and another wholly below it."""
    return (any(r.lo is not None and r.lo > 0 for r in rows)
            and any(r.hi is not None and r.hi < 0 for r in rows))


def build(batches: Sequence[BatchInput], prereg: Prereg | None) -> LeanSummary:
    """One or two batches, in batch order, to the lean summary. Pure; raises `BenchError` on a non-lean view."""
    comparison = _checked(batches)
    ref, _ = comparison
    cells = _relabelled(batches)
    tasks = tuple(sorted({cell["task"] for batch in batches for cell in batch.view.plan["cells"]}))
    seed = stats.DEFAULT_SEED
    rows, collected, pooled_pairs, pooled_excluded = [], [], [], []
    for combo, harness, model in _combos(batches):
        spec = verdicts.VerdictSpec(prop=verdicts.PRIMARY, harness=harness, comparison=comparison, tasks=tasks,
                                    mde=Decimal(0), method=stats.METHOD, alpha_per_test=_ALPHA, level_rule="not used",
                                    min_pairs=1, seed=seed, resamples=stats.MIN_RESAMPLES, required_pairs=None)
        pairs, excluded, _ = verdicts.collect([c for c in cells if c.combo == combo], spec)
        rows.append(_row(combo, harness, model, pairs, excluded, _planned(batches, combo, ref), comparison, seed))
        collected.append((combo, harness, pairs))
        pooled_pairs += [dataclasses.replace(p, task=f"{combo}/{p.task}") for p in pairs]
        pooled_excluded += excluded
    pooled = _row("pooled", "pooled", "pooled", pooled_pairs, sorted(pooled_excluded), _planned(batches, None, ref),
                  comparison, seed)
    return LeanSummary(batches=len(batches), run_ids=tuple(b.view.run_id for b in batches),
                       plan_hashes=tuple(str(b.view.plan["plan_hash"]) for b in batches),
                       prereg_status="Not pre-registered: no pre-registration supplied", rows=tuple(rows), pooled=pooled,
                       disagree=_disagree(rows), properties=_properties(batches, collected), checkpoint=())
