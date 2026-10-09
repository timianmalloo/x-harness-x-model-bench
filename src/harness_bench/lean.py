"""The lean pack benchmark's summary (ADR-0023): a pure derived view over one or two lean batches.

This is the contract only (L-CONTRACT), exactly as `docs/architecture-lean-benchmark.md`, *Contracts at the
seams*. `build` is L-SUM-A's to write; the renderer (L-SUM-B1) reads `LeanSummary` and the CLI (L-SUM-C) builds
`BatchInput` and `Prereg`. The summary is never stored: it is recomputed on every `bench report`. Arm ids come from
`plan.comparisons` and `config.ARM_OFF`, never from literals in this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from harness_bench.stats import Interval
from harness_bench.views import RunView


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


def build(batches: Sequence[BatchInput], prereg: Prereg | None) -> LeanSummary:
    """One or two batches, in batch order, to the lean summary. Pure; raises `BenchError` on a non-lean view."""
    raise NotImplementedError("L-SUM-A")
