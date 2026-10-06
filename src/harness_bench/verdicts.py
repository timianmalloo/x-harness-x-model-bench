"""Verdicts (W1-H, W0 section 8): pairs, a corrected-level stratified bootstrap, labels and statements.

Pure functions, stdlib only (ADR-0020 section 5). The label is a total function of
(n_pairs, min_pairs, lo, hi, mde) through `label_for` and no other path emits one (W0 section 3: no NA count
and no level rule enters it). The word the dominance rule emits appears in this module only.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from fractions import Fraction

from harness_bench import plan, power, stats, views
from harness_bench.errors import BenchError

PRIMARY = "property_check_pass"
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)
_CENT = Decimal("0.01")
_RATIO_ALPHA = Decimal("0.05")  # EV-19: the token ratio is reported at a fixed 95%


class VerdictLabel(StrEnum):
    BETTER = "better"
    WORSE = "worse"
    NO_DIFFERENCE = "no difference ≥ MDE"
    UNDERPOWERED = "inconclusive (underpowered)"
    NOT_RECORDED = "inconclusive (not recorded)"


@dataclass(frozen=True)
class Pair:
    task: str
    rep: int
    ref: Decimal
    treat: Decimal
    ref_tokens: int | None
    treat_tokens: int | None
    ref_wall_ms: int | None
    treat_wall_ms: int | None


@dataclass(frozen=True)
class Ratio:
    r: Decimal
    lo: Decimal
    hi: Decimal


@dataclass(frozen=True)
class VerdictSpec:
    prop: str
    harness: str
    comparison: tuple[str, str]  # (ref arm, treat arm)
    tasks: tuple[str, ...]  # the admitted tasks of the property: the strata
    mde: Decimal
    method: str
    alpha_per_test: Decimal
    level_rule: str
    min_pairs: int
    seed: int
    resamples: int
    required_pairs: int | None

    def __post_init__(self) -> None:
        if self.min_pairs < 1:
            raise BenchError("HB-USR-002", f"min_pairs must be at least 1, got {self.min_pairs}")


@dataclass(frozen=True)
class Verdict:
    label: VerdictLabel
    effect: Decimal | None
    interval: tuple[Decimal, Decimal] | None  # None when not computed (a not-recorded label)
    per_task: Mapping[str, tuple[Decimal, Decimal | None, Decimal | None]]  # interval only for a directional label
    both_tasks: bool | None
    n_pairs: int
    excluded: Sequence[tuple[str, str]]
    token_ratio: Ratio | None
    wall_ratio: Decimal | None
    statement: str | None
    method: str
    level: Decimal
    alpha_per_test: Decimal
    level_rule: str
    mde: Decimal
    resamples: int
    seed: int
    reason: str | None
    pairs_by_task: Mapping[str, int] = field(default_factory=dict)
    na_counts: Mapping[str, int] = field(default_factory=dict)
    required_pairs: int | None = None


def alpha_per_test(prereg: Mapping) -> Decimal:
    correction = prereg["correction"]
    return power.level_for(correction["method"], power._decimal(prereg["alpha"]), correction["m"])[0]


def resamples_for(alpha_per_test: Decimal) -> int:
    needed = max(stats.MIN_RESAMPLES, power._snap(float(20 / alpha_per_test)))
    if needed > stats.MAX_RESAMPLES:
        raise BenchError("HB-USR-002", f"alpha per test {alpha_per_test} needs {needed} resamples; the cap is {stats.MAX_RESAMPLES}")
    return needed


def seed_for(prereg_hash: str, prop: str, harness: str, comparison: tuple[str, str]) -> int:
    ref, treat = comparison
    return int(hashlib.sha256(f"{prereg_hash}|{prop}|{harness}|{ref}|{treat}".encode()).hexdigest()[:15], 16)


def label_for(n_pairs: int, min_pairs: int, lo: Decimal, hi: Decimal, mde: Decimal) -> VerdictLabel:
    if n_pairs < min_pairs:
        return VerdictLabel.NOT_RECORDED
    if lo > 0:
        return VerdictLabel.BETTER
    if hi < 0:
        return VerdictLabel.WORSE
    if -mde < lo and hi < mde:
        return VerdictLabel.NO_DIFFERENCE
    return VerdictLabel.UNDERPOWERED


def statement_for(label: VerdictLabel, treat: str, ref: str, ratio: Ratio | None) -> str | None:
    if ratio is None or label not in (VerdictLabel.BETTER, VerdictLabel.NO_DIFFERENCE):
        return None
    if ratio.hi < 1:
        return f"{treat} dominates {ref}"
    if label is VerdictLabel.BETTER:
        return f"better at ×{ratio.r} tokens"
    return None


# ---------------------------------------------------------------- collect

def _task_rep(cell, arm: str) -> tuple[str, int]:
    """Compatibility accessor for gate readers; identity is projected from the plan."""
    return cell.task, cell.rep


def _reason(cell, admitted: bool) -> tuple[str, bool] | None:
    """The first matching exclusion reason and whether it is the primary's NA branch."""
    if not admitted:
        return "calibration or non-admitted task", False
    if cell.validity.startswith("invalid"):
        return cell.validity, False
    primary = cell.scores.get(PRIMARY)
    recorded = primary is not None and primary.value is not None
    if cell.outcome != "completed" and not (cell.outcome == "timed_out" and recorded):
        return f"{cell.outcome} ({cell.cause or 'not recorded'})", False
    if not recorded:
        return (primary.reason if primary is not None and primary.reason else f"{PRIMARY} not recorded"), True
    if primary.value not in (0, 1):
        raise BenchError("HB-USR-002", f"cell {cell.cell_id}: {PRIMARY} is {primary.value!r}, E1 accepts 0 or 1")
    return None


def collect(cells: Sequence, spec: VerdictSpec) -> tuple[list[Pair], list[tuple[str, str]], dict[str, int]]:
    """Every in-scope cell lands in exactly one place: a pair half or `excluded` with its reason."""
    ref, treat = spec.comparison
    admitted = set(spec.tasks)
    ids: dict[tuple[str, int, str], str] = {}
    halves: dict[tuple[str, int, str], object] = {}
    excluded: list[tuple[str, str]] = []
    na_counts: dict[str, int] = {}
    for cell in cells:
        if cell.harness != spec.harness:
            continue
        arm = plan.cell_arm(vars(cell))
        if arm not in (ref, treat):
            continue
        task, rep = cell.task, cell.rep
        key = (task, rep, arm)
        if key in ids:
            raise BenchError("HB-USR-002", f"cells {ids[key]} and {cell.cell_id} are both {task} rep {rep} arm {arm}")
        ids[key] = cell.cell_id
        found = _reason(cell, task in admitted)
        if found is None:
            halves[key] = cell
            continue
        reason, is_na = found
        excluded.append((cell.cell_id, reason))
        if is_na:
            na_counts[reason] = na_counts.get(reason, 0) + 1
    pairs: list[Pair] = []
    for task, rep, arm in sorted(halves):
        mate = (task, rep, treat if arm == ref else ref)
        if arm == ref and mate in halves:
            a, b = halves[(task, rep, ref)], halves[mate]
            pairs.append(Pair(task, rep, Decimal(str(a.scores[PRIMARY].value)), Decimal(str(b.scores[PRIMARY].value)),
                              views.sum_tokens(a.tokens), views.sum_tokens(b.tokens), _wall(a), _wall(b)))
        elif mate not in halves:
            excluded.append((halves[(task, rep, arm)].cell_id, f"pair partner not recorded ({ids.get(mate, 'absent')})"))
    return pairs, sorted(excluded), na_counts


def _wall(cell) -> int | None:
    value = cell.wall_ms.value
    return value if isinstance(value, int) else None


# ---------------------------------------------------------------- bootstrap

def _tail(resamples: int, alpha_per_test: Decimal) -> int:
    # The epsilon snaps decimal noise on an exact index (B * 0.05/45 / 2 lands at 9.999...), the `_snap` idea.
    return int(Decimal(resamples) * alpha_per_test / 2 + Decimal("1e-9"))


def _quotient(numerator: int, denominator: int) -> Decimal:
    with localcontext(_CONTEXT):
        return Decimal(numerator) / Decimal(denominator)


def _effect_interval(groups: list[list[int]], stream, resamples: int, tail: int) -> tuple[Decimal, Decimal]:
    """Percentile interval of the mean of stratum means, held as an exact integer over lcm(widths) * k."""
    widths = [len(g) for g in groups]
    common = math.lcm(*widths)
    scale = [common // w for w in widths]
    draw = stream.random
    totals = []
    for _ in range(resamples):
        total = 0
        for group, width, factor in zip(groups, widths, scale, strict=True):
            total += sum(group[int(draw() * width)] for _ in range(width)) * factor
        totals.append(total)
    totals.sort()
    denominator = common * len(groups)
    return _quotient(totals[tail], denominator), _quotient(totals[resamples - 1 - tail], denominator)


def _ratio(groups: list[list[tuple[int, int]]], stream, resamples: int, point: Fraction) -> Ratio:
    tail = _tail(resamples, _RATIO_ALPHA)
    draw = stream.random
    values = []
    for _ in range(resamples):
        ref_sum = treat_sum = 0
        for group in groups:
            width = len(group)
            for _ in range(width):
                ref_tokens, treat_tokens = group[int(draw() * width)]
                ref_sum += ref_tokens
                treat_sum += treat_tokens
        values.append(Fraction(treat_sum, ref_sum))
    values.sort()
    lo, hi = values[tail], values[resamples - 1 - tail]
    return Ratio(r=_fraction(point).quantize(_CENT), lo=_fraction(lo), hi=_fraction(hi))


def _fraction(value: Fraction) -> Decimal:
    return _quotient(value.numerator, value.denominator)


def _checked(spec: VerdictSpec, pairs: Sequence[Pair]) -> list[Pair]:
    seen: set[tuple[str, int]] = set()
    for pair in pairs:
        if pair.ref not in (0, 1) or pair.treat not in (0, 1):
            raise BenchError("HB-USR-002", f"{pair.task} rep {pair.rep}: E1 accepts 0 or 1, got {pair.ref}, {pair.treat}")
        if pair.task not in spec.tasks:
            raise BenchError("HB-USR-002", f"pair for task {pair.task!r} is outside the strata {list(spec.tasks)}")
        if (pair.task, pair.rep) in seen:
            raise BenchError("HB-USR-002", f"duplicate pair {pair.task} rep {pair.rep}")
        seen.add((pair.task, pair.rep))
    return sorted(pairs, key=lambda p: (p.task, p.rep))


def _ratios(ordered: Sequence[Pair], groups: list[list[Pair]], spec: VerdictSpec) -> tuple[Ratio | None, Decimal | None]:
    tokens = [(p.ref_tokens, p.treat_tokens) for p in ordered]
    wall = [(p.ref_wall_ms, p.treat_wall_ms) for p in ordered]
    token_ratio = wall_ratio = None
    # simplify: a pair with zero reference tokens makes the whole ratio not recorded. Ceiling: a recorded cell
    # always has tokens. Upgrade trigger: a task whose agent legitimately uses none.
    if all(r is not None and t is not None and r > 0 for r, t in tokens):
        point = Fraction(sum(t for _, t in tokens), sum(r for r, _ in tokens))
        token_ratio = _ratio([[(p.ref_tokens, p.treat_tokens) for p in g] for g in groups],
                             stats.rng(spec.seed, "ratio"), spec.resamples, point)
    if all(r is not None and t is not None for r, t in wall) and sum(r for r, _ in wall) > 0:
        wall_ratio = _fraction(Fraction(sum(t for _, t in wall), sum(r for r, _ in wall))).quantize(_CENT)
    return token_ratio, wall_ratio


def verdict(
    spec: VerdictSpec,
    pairs: Sequence[Pair],
    excluded: Sequence[tuple[str, str]],
    na_counts: Mapping[str, int],
) -> Verdict:
    stats.Params(seed=spec.seed, resamples=spec.resamples)  # the real class refuses an illegal seed or count
    ordered = _checked(spec, pairs)
    tasks = sorted(spec.tasks)
    groups = [[p for p in ordered if p.task == task] for task in tasks]
    counts = {task: len(group) for task, group in zip(tasks, groups, strict=True)}
    empty = next((task for task, n in counts.items() if n == 0), None)
    n_for_rule = 0 if empty is not None else len(ordered)
    diffs = [[int(p.treat - p.ref) for p in group] for group in groups]
    interval = effect = None
    per_task: dict[str, tuple[Decimal, Decimal | None, Decimal | None]] = {}
    token_ratio = wall_ratio = None
    both_tasks = None
    reason = None
    if empty is not None:
        reason = f"task {empty}: 0 pairs recorded"
    elif n_for_rule < spec.min_pairs:
        reason = f"{n_for_rule} pairs recorded, {spec.min_pairs} required"
    if empty is None:
        effect = _fraction(sum((Fraction(sum(d), len(d)) for d in diffs), Fraction(0)) / len(diffs))
        per_task = {t: (_fraction(Fraction(sum(d), len(d))), None, None) for t, d in zip(tasks, diffs, strict=True)}
    if empty is None and n_for_rule >= spec.min_pairs:
        tail = _tail(spec.resamples, spec.alpha_per_test)
        interval = _effect_interval(diffs, stats.rng(spec.seed, "effect"), spec.resamples, tail)
        token_ratio, wall_ratio = _ratios(ordered, groups, spec)
    lo, hi = interval if interval is not None else (Decimal(0), Decimal(0))
    label = label_for(n_for_rule, spec.min_pairs, lo, hi, spec.mde)
    if interval is not None and label in (VerdictLabel.BETTER, VerdictLabel.WORSE):
        bounds = {t: _effect_interval([d], stats.rng(spec.seed, f"task|{t}"), spec.resamples, tail)
                  for t, d in zip(tasks, diffs, strict=True)}
        per_task = {t: (per_task[t][0], *bounds[t]) for t in tasks}
        if label is VerdictLabel.BETTER:
            both_tasks = all(len(d) >= 2 and bounds[t][0] > 0 for t, d in zip(tasks, diffs, strict=True))
        else:
            both_tasks = all(len(d) >= 2 and bounds[t][1] < 0 for t, d in zip(tasks, diffs, strict=True))
    return Verdict(
        label=label,
        effect=effect,
        interval=interval,
        per_task=per_task,
        both_tasks=both_tasks,
        n_pairs=len(ordered),
        excluded=list(excluded),
        token_ratio=token_ratio,
        wall_ratio=wall_ratio,
        statement=statement_for(label, spec.comparison[1], spec.comparison[0], token_ratio),
        method=spec.method,
        level=1 - spec.alpha_per_test,
        alpha_per_test=spec.alpha_per_test,
        level_rule=spec.level_rule,
        mde=spec.mde,
        resamples=spec.resamples,
        seed=spec.seed,
        reason=reason,
        pairs_by_task=counts,
        na_counts=dict(na_counts),
        required_pairs=spec.required_pairs,
    )
