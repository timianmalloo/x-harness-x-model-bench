"""Two-stage percentile bootstrap (design: phase4-statistics, The bootstrap).

Pure calculation: the standard library and `harness_bench.errors` only. No I/O, no catalog, no views.
Values stay `Decimal`. One keyed `random.Random` stream per quantity; only `random()` is drawn.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from harness_bench.errors import BenchError

METHOD = "percentile bootstrap, 95%, two-stage (task, then repetition), task-balanced mean"
DEFAULT_SEED: int = 20260927
MIN_RESAMPLES, MAX_RESAMPLES = 2000, 100_000
CONTAMINATION_PRONE = ("E1", "E2", "E3")

# Fixed context so a caller's ambient precision cannot move a result (T-S5).
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


# assume: CPython's random.Random(int).random() sequence is stable across Python versions
# (design Determinism, G16, recalled from the docs). Confirm: T-S4 pins the first five draws
# and one full interval. Breaks if false: the same seed yields different intervals and T-S4 fails.
def rng(seed: int, key: str) -> random.Random:
    """The stream for one quantity. The seed is part of the key material."""
    material = f"{seed}|{key}".encode()
    folded = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return random.Random(folded)


def _draw(stream: random.Random, m: int) -> int:
    """Index in `0 .. m-1`. `int(random() * m)` is the contract; nothing else is drawn."""
    return int(stream.random() * m)


@dataclass(frozen=True)
class Params:
    seed: int = DEFAULT_SEED  # 0 <= seed < 2**63, else BenchError("HB-USR-002")
    resamples: int = MIN_RESAMPLES  # MIN..MAX, else BenchError("HB-USR-002")

    def __post_init__(self) -> None:
        # assume: a non-int seed or resamples is HB-USR-002, the same code as an out-of-range
        # int. The design states the numeric bounds and the int annotation, not the type error.
        # Confirm: the CLI parse (S6) rejects a non-integer flag before Params is built.
        if not isinstance(self.seed, int) or not 0 <= self.seed < 2**63:
            raise BenchError("HB-USR-002", f"seed must satisfy 0 <= seed < 2**63, got {self.seed!r}")
        if not isinstance(self.resamples, int) or not MIN_RESAMPLES <= self.resamples <= MAX_RESAMPLES:
            raise BenchError(
                "HB-USR-002",
                f"resamples must be an integer in {MIN_RESAMPLES}..{MAX_RESAMPLES}, got {self.resamples!r}",
            )


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
    n: int  # tasks
    reason: str | None  # set whenever lo/hi are None


def _mean(values: Sequence[Decimal]) -> Decimal:
    total = Decimal(0)
    for value in values:
        total += value
    return total / Decimal(len(values))


def _by_task(obs: Sequence[Obs]) -> tuple[tuple[str, ...], dict[str, tuple[Decimal, ...]]]:
    """Task ids in string order; within a task, values in `rep` order.

    assume: observations that share a task and a rep are all kept, in input order
    (the sort is stable). Confirm: two observations with the same task and rep, and
    a task mean that changes if either one is dropped.
    """
    buckets: dict[str, list[tuple[int, int, Decimal]]] = {}
    for index, item in enumerate(obs):
        buckets.setdefault(item.task, []).append((item.rep, index, item.value))
    tasks = tuple(sorted(buckets))
    values = {task: tuple(value for _, _, value in sorted(rows)) for task, rows in buckets.items()}
    return tasks, values


def _interval(obs: Sequence[Obs], params: Params, key: str) -> Interval:
    tasks, values = _by_task(obs)
    n = len(tasks)
    if n == 0:
        return Interval(None, None, None, 0, "not computed (no valid cell with a value)")
    point = _mean([_mean(values[task]) for task in tasks])
    if n < 2:
        return Interval(point, None, None, n, "interval not computed (n < 2)")
    stream = rng(params.seed, key)
    B = params.resamples
    statistics: list[Decimal] = []
    for _ in range(B):
        task_means: list[Decimal] = []
        for _task_draw in range(n):
            task = tasks[_draw(stream, n)]
            pool = values[task]
            width = len(pool)
            # Draw order: one task index, then `width` repetition indexes, then the next task.
            drawn = [pool[_draw(stream, width)] for _rep_draw in range(width)]
            task_means.append(_mean(drawn))
        statistics.append(_mean(task_means))
    statistics.sort()
    j = B * 25 // 1000
    return Interval(point, statistics[j], statistics[B - 1 - j], n, None)


def interval(obs: Sequence[Obs], params: Params, key: str) -> Interval:
    """95% two-stage percentile interval of the task-balanced mean."""
    with localcontext(_CONTEXT):
        return _interval(obs, params, key)


# (combo, pack). The contract's RowId.
RowId = tuple[str, str]


def rank(rows: Mapping[RowId, tuple[Interval, Interval]]) -> dict[RowId, tuple[str, str | None]]:
    """Red stub: a lone `1`, so T-R3's `1=` assertion fails."""
    return {
        row_id: ("1", None) if primary.lo is not None else ("", None)
        for row_id, (primary, _pass_at_1) in rows.items()
    }
