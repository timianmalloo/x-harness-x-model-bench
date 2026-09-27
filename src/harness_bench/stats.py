"""Bootstrap intervals (phase 4, S1). The procedure is the design's; this revision is the red stub."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

METHOD = "percentile bootstrap, 95%, two-stage (task, then repetition), task-balanced mean"
DEFAULT_SEED: int = 20260927
MIN_RESAMPLES, MAX_RESAMPLES = 2000, 100_000
CONTAMINATION_PRONE = ("E1", "E2", "E3")


@dataclass(frozen=True)
class Params:
    seed: int = DEFAULT_SEED
    resamples: int = MIN_RESAMPLES


@dataclass(frozen=True)
class Obs:
    task: str
    rep: int
    value: Decimal


@dataclass(frozen=True)
class Interval:
    point: Decimal | None
    lo: Decimal | None
    hi: Decimal | None
    n: int
    reason: str | None


def interval(obs: Sequence[Obs], params: Params, key: str) -> Interval:
    """Red stub: a zero interval, so T-S1 fails on an assertion rather than on import."""
    del obs, params, key
    return Interval(Decimal(0), Decimal(0), Decimal(0), 0, None)
