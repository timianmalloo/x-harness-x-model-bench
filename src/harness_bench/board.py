"""Board projection: derived statistics board, pack-effect, and canonical export (S5).

Replaces `views.leaderboard`. Derived at read time, never stored (ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from harness_bench.composites import Catalog
from harness_bench.stats import Interval, Measure, Params
from harness_bench.views import RunView


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
class Comparison:
    diffs: tuple[str, ...] = ()


@dataclass
class Board:
    run_id: str
    catalog_version: str | None
    params: Params
    primary: str
    primary_reason: str | None
    rows: list[BoardRow]
    pack_effect: PackEffect


def build(view: RunView, cat: Catalog, params: Params) -> Board:
    """Build the statistics projection for one pass of a run."""
    # Stub: fails T-B1 assertion red-first
    dummy_iv = Interval(point=Decimal("0.99"), lo=None, hi=None, n=1, reason="stub")
    dummy_row = BoardRow(
        combo="c",
        pack="off",
        harness="codex",
        model="gpt-6-sol",
        n_cells=2,
        n_valid=2,
        pass_at_1=dummy_iv,
        gated=dummy_iv,
        pass_at_k=Measure(Decimal(0)),
        pass_hat_k=Measure(Decimal(0)),
        rank="1",
        rank_reason=None,
        tokens=Measure(Decimal(46454)),
        wall_ms=Measure(Decimal(30000)),
        cost_usd=Measure(None),
    )
    dummy_pe = PackEffect(status=None, excluded_tasks=(), rows=[])
    return Board(
        run_id=view.run_id,
        catalog_version=view.catalog_version,
        params=params,
        primary="pass_at_1",
        primary_reason=None,
        rows=[dummy_row],
        pack_effect=dummy_pe,
    )


def compare(base: RunView, view: RunView, cat: Catalog, params: Params) -> Comparison:
    raise NotImplementedError


def export(board: Board, comparison: Comparison | None = None) -> bytes:
    raise NotImplementedError
