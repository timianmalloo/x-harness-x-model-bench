"""Verdicts (W1-H, W0 section 8). Skeleton: final signatures, values outside the expected domain."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


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
    tasks: tuple[str, ...]
    mde: Decimal
    method: str
    alpha_per_test: Decimal
    level_rule: str
    min_pairs: int
    seed: int
    resamples: int
    required_pairs: int | None


@dataclass(frozen=True)
class Verdict:
    label: VerdictLabel | None
    effect: Decimal | None
    interval: tuple[Decimal, Decimal] | None
    per_task: Mapping[str, tuple[Decimal, Decimal, Decimal]]
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
    return Decimal(-1)


def resamples_for(alpha_per_test: Decimal) -> int:
    return -1


def seed_for(prereg_hash: str, prop: str, harness: str, comparison: tuple[str, str]) -> int:
    return -1


def label_for(n_pairs: int, min_pairs: int, lo: Decimal, hi: Decimal, mde: Decimal) -> VerdictLabel:
    return None  # type: ignore[return-value]


def statement_for(label: VerdictLabel, treat: str, ref: str, ratio: Ratio | None) -> str | None:
    return "unimplemented"


def collect(cells: Sequence, spec: VerdictSpec) -> tuple[list[Pair], list[tuple[str, str]], dict[str, int]]:
    return ([], [("unimplemented", "")], {})


def verdict(
    spec: VerdictSpec,
    pairs: Sequence[Pair],
    excluded: Sequence[tuple[str, str]],
    na_counts: Mapping[str, int],
) -> Verdict:
    return Verdict(
        label=None,
        effect=Decimal(0),
        interval=(Decimal(1), Decimal(-1)),
        per_task={},
        both_tasks=None,
        n_pairs=-1,
        excluded=[],
        token_ratio=None,
        wall_ratio=None,
        statement="unimplemented",
        method="unimplemented",
        level=Decimal(-1),
        alpha_per_test=Decimal(-1),
        level_rule="unimplemented",
        mde=Decimal(-1),
        resamples=-1,
        seed=-1,
        reason=None,
    )
