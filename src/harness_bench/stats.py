"""Two-stage percentile bootstrap, paired differences, pass@k and ranking.

Pure calculation: the standard library and `harness_bench.errors` only. No I/O, no catalog, no views.
Values stay `Decimal`. One keyed `random.Random` stream per quantity; only `random()` is drawn.
Ranking is the overlap components of the primary interval, then one pass@1 gate.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import NamedTuple

from harness_bench.errors import BenchError

METHOD = "percentile bootstrap, 95%, two-stage (task, then repetition), task-balanced mean"
DEFAULT_SEED: int = 20260927
MIN_RESAMPLES, MAX_RESAMPLES = 2000, 100_000
# simplify: task ids, as the spec names them. Ceiling: the public calibration tasks are
# exactly E1-E3. Upgrade trigger: a fourth such task, or any of E1-E3 re-authored as
# private; then this becomes a task.yaml field. R-78 condition 6: the only source of
# the exclusion.
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
    n: int  # tasks (paired: tasks in both arms)
    reason: str | None  # set whenever lo/hi are None


@dataclass(frozen=True)
class Measure:
    """A derived rate, or not recorded (`value` None) with the reason.

    assume: views.Measure has these two fields, and S5 reads them without requiring
    isinstance(..., views.Measure). stats does not import views (module contract, T-B9).
    Confirm: S5 uses `.value` and `.reason`. Breaks if false: S5 must convert.
    """

    value: Decimal | None
    reason: str | None = None


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
    lo, hi = _percentile(statistics, B)
    return Interval(point, lo, hi, n, None)


def _percentile(statistics: list[Decimal], resamples: int) -> tuple[Decimal, Decimal]:
    """No interpolation. lo is the low tail, hi the matching high tail."""
    statistics.sort()
    B = resamples
    j = B * 25 // 1000
    return statistics[j], statistics[B - 1 - j]


def interval(obs: Sequence[Obs], params: Params, key: str) -> Interval:
    """95% two-stage percentile interval of the task-balanced mean."""
    with localcontext(_CONTEXT):
        return _interval(obs, params, key)


def _paired_delta(
    ref: Sequence[Obs],
    treat: Sequence[Obs],
    labels: tuple[str, str],
    params: Params,
    key: str,
) -> tuple[Interval, tuple[str, ...]]:
    """treat − ref over tasks present in both arms. The tuple is tasks in one arm only.

    n == 0 uses the bootstrap's empty reason (step 2). n == 1 keeps the point and
    `interval not computed (n < 2)` (Minimum n).
    """
    ref_tasks, ref_values = _by_task(ref)
    treat_tasks, treat_values = _by_task(treat)
    ref_set = set(ref_tasks)
    treat_set = set(treat_tasks)
    shared = tuple(sorted(ref_set & treat_set))
    only = tuple(sorted(ref_set ^ treat_set))
    n = len(shared)
    if n == 0:
        return Interval(None, None, None, 0, "not computed (no valid cell with a value)"), only
    point = _mean([_mean(treat_values[task]) - _mean(ref_values[task]) for task in shared])
    if n < 2:
        return Interval(point, None, None, n, "interval not computed (n < 2)"), only
    # assume: the stream prefix joins the sorted labels with "|", the separator in
    # `seed|key` and `key|arm|<label>`. The three streams are then `key|tasks` and
    # `key|arm|<label>` after `key` has sorted the two labels. Confirm: a paired
    # golden pins one stream's first draw. Breaks if false: the interval bytes move.
    # Antisymmetry still holds while each arm's stream stays tied to its label.
    label_a, label_b = labels
    left, right = sorted((label_a, label_b))
    base = f"{key}|{left}|{right}"
    rng_t = rng(params.seed, f"{base}|tasks")
    rng_a = rng(params.seed, f"{base}|arm|{label_a}")
    rng_b = rng(params.seed, f"{base}|arm|{label_b}")
    B = params.resamples
    statistics: list[Decimal] = []
    for _ in range(B):
        diffs: list[Decimal] = []
        for _task_draw in range(n):
            task = shared[_draw(rng_t, n)]
            pool_a = ref_values[task]
            pool_b = treat_values[task]
            width_a = len(pool_a)
            width_b = len(pool_b)
            # Draw order: one shared task, then A's repetitions, then B's, then the next task.
            mean_a = _mean([pool_a[_draw(rng_a, width_a)] for _rep in range(width_a)])
            mean_b = _mean([pool_b[_draw(rng_b, width_b)] for _rep in range(width_b)])
            diffs.append(mean_b - mean_a)
        statistics.append(_mean(diffs))
    lo, hi = _percentile(statistics, B)
    return Interval(point, lo, hi, n, None), only


def paired_delta(
    ref: Sequence[Obs],
    treat: Sequence[Obs],
    labels: tuple[str, str],
    params: Params,
    key: str,
) -> tuple[Interval, tuple[str, ...]]:
    """95% paired interval of treat − ref, plus tasks present in one arm only."""
    with localcontext(_CONTEXT):
        return _paired_delta(ref, treat, labels, params, key)


def no_detectable_effect(iv: Interval) -> bool | None:
    """True when a computed interval contains 0, including at either bound.

    None when the interval was not computed. The only definition of the label.
    """
    if iv.lo is None or iv.hi is None:
        return None
    return iv.lo <= 0 <= iv.hi


def pass_k(outcomes: Sequence[int], planned: int) -> tuple[Measure, Measure]:
    """pass@k and pass^k for one task. Points only: 0, 1, or not recorded.

    `outcomes` is the recorded pass@1 indicators. Repetitions that were not recorded
    are absent. `planned` is K. A recorded pass makes pass@k 1, and a recorded
    failure makes pass^k 0, even when other repetitions are missing.

    assume: every outcome is 0 or 1, len(outcomes) <= planned, and planned >= 1.
    Confirm: S5 passes recorded pass_at_1 values and matrix.repetitions.
    Breaks if false: a value other than 0 or 1 is neither a pass nor a failure,
    and a negative missing-count reaches the reason string.
    """
    recorded = len(outcomes)
    missing = planned - recorded
    reason = f"{missing} of {planned} repetitions not recorded"
    any_passed = any(value == 1 for value in outcomes)
    any_failed = any(value == 0 for value in outcomes)
    if any_passed:
        at_k = Measure(Decimal(1))
    elif recorded == planned:
        at_k = Measure(Decimal(0))
    else:
        at_k = Measure(None, reason)
    if recorded == planned and not any_failed:
        hat_k = Measure(Decimal(1))
    elif any_failed:
        hat_k = Measure(Decimal(0))
    else:
        hat_k = Measure(None, reason)
    return at_k, hat_k


# (combo, pack). The contract's RowId.
RowId = tuple[str, str]


class _Ranked(NamedTuple):
    row_id: RowId
    primary: Interval
    pass_at_1: Interval


def _computed(iv: Interval) -> bool:
    return iv.lo is not None and iv.hi is not None


def _below(a: Interval, b: Interval) -> bool:
    """`a` lies entirely under `b`. Touching (`hi == lo`) is not below (K12)."""
    return a.hi < b.lo


def _tiers_by_overlap(ranked: list[_Ranked]) -> list[list[_Ranked]]:
    """Overlap components, lowest `lo` first.

    Sort by primary `lo`, then `hi`, then row id. A row joins the current tier when
    its `lo` is at most the running maximum `hi` (closed intervals: touching joins).
    The running value is the maximum, so a wide interval keeps later rows that overlap
    it and miss each other.
    """
    ordered = sorted(ranked, key=lambda row: (row.primary.lo, row.primary.hi, row.row_id))
    tiers: list[list[_Ranked]] = []
    running_hi: Decimal | None = None
    for row in ordered:
        lo = row.primary.lo
        hi = row.primary.hi
        assert lo is not None and hi is not None
        if running_hi is not None and lo <= running_hi:
            tiers[-1].append(row)
            running_hi = max(running_hi, hi)
        else:
            tiers.append([row])
            running_hi = hi
    return tiers


def _merge_span(tiers: list[list[_Ranked]], ix: int, iy: int) -> list[list[_Ranked]]:
    """Merge every tier from `ix` through `iy` (K8). The tiers between the ends are included."""
    head = tiers[:ix]
    between = tiers[ix + 1 : iy]
    tail = tiers[iy + 1 :]
    merged = [*tiers[ix], *[row for tier in between for row in tier], *tiers[iy]]
    return [*head, merged, *tail]


def _apply_gate(tiers: list[list[_Ranked]]) -> list[list[_Ranked]]:
    """One pass over pairs in row-id order. A merge only coarsens, so it adds no new violation.

    A row whose pass@1 interval is not computed takes part in no check (T-R16).
    """
    by_id = {row.row_id: row for tier in tiers for row in tier}

    def indexes() -> dict[RowId, int]:
        return {row.row_id: i for i, tier in enumerate(tiers) for row in tier}

    for x in sorted(by_id):
        for y in sorted(by_id):
            if x == y:
                continue
            px = by_id[x].pass_at_1
            py = by_id[y].pass_at_1
            if not _computed(px) or not _computed(py):
                continue
            place = indexes()
            if _below(px, py) and place[x] < place[y]:
                tiers = _merge_span(tiers, place[x], place[y])
    return tiers


def rank(
    rows: Mapping[RowId, tuple[Interval, Interval]],
) -> dict[RowId, tuple[str, str | None]]:
    """Competition ranks of the primary-interval tiers after the pass@1 gate.

    Unranked rows (primary not computed) are `("", "not ranked: <reason>")`.
    A tier of one row prints `k`; a tier of more than one prints `k=`.
    The dict is in display order: tier best-first, then primary point descending,
    then row id; unranked rows follow, by row id.

    assume: K1's "-" and the note "No row could be ranked." are the report's
    rendering of an empty rank (section "Where each result reaches the report"),
    not a value this function returns. Confirm: S6 prints that note when every
    rank string is empty.
    assume: a computed primary has a point (`interval` sets one whenever n >= 1).
    Display order sorts by it. Confirm: a computed Interval with point None.
    Breaks if false: sorting the tier raises TypeError.
    """
    ranked: list[_Ranked] = []
    unranked: list[tuple[RowId, str]] = []
    for row_id, (primary, pass_at_1) in rows.items():
        if _computed(primary):
            ranked.append(_Ranked(row_id, primary, pass_at_1))
        else:
            unranked.append((row_id, f"not ranked: {primary.reason}"))
    # Worst-lo first out of the sweep; best (higher interval) first for ranks.
    tiers = list(reversed(_tiers_by_overlap(ranked)))
    tiers = _apply_gate(tiers)
    result: dict[RowId, tuple[str, str | None]] = {}
    placed = 0
    for tier in tiers:
        number = 1 + placed
        label = f"{number}=" if len(tier) > 1 else str(number)
        ordered = sorted(tier, key=lambda row: (-row.primary.point, row.row_id))
        for row in ordered:
            result[row.row_id] = (label, None)
        placed += len(tier)
    for row_id, reason in sorted(unranked, key=lambda item: item[0]):
        result[row_id] = ("", reason)
    return result
