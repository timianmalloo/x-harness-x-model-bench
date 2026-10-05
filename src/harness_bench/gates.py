"""Ring gates (W1-H, W0 section 8): pilot items, the pack-regression signal and task admission.

Pure functions, stdlib only (ADR-0020 section 5). Skeleton: every function returns a value outside its domain.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

EMPTY: Mapping[str, frozenset[str]] = MappingProxyType({})


class GateKind(StrEnum):
    CELL_LOST = "cell-lost"
    BND_A = "bnd-a-loss"
    GRADER_ERROR = "grader-error"
    METRIC_UNRECORDED = "metric-not-recorded"
    PRIMARY_UNRECORDED = "primary-not-recorded"
    TASK_NO_PRIMARY = "task-no-primary"
    CHECK_TAMPERED = "check-tampered"
    SUSPEND_BLIND = "suspend-detector-blind"
    HIDDEN_NONDETERMINISTIC = "hidden-tests-nondeterministic"


@dataclass(frozen=True)
class GateItem:
    kind: str
    ident: str
    detail: str = ""


def ring_items(view, expected_na: Mapping[str, frozenset[str]]) -> list[GateItem]:
    return [GateItem("unimplemented", "")]


def pilot(
    view,
    hidden_test_disagreements: Sequence[str],
    unbiased_failures: Sequence[str],
    *,
    expected_na: Mapping[str, frozenset[str]] = EMPTY,
) -> list[GateItem]:
    return [GateItem("unimplemented", "")]


def pack_regression(view, mde: Mapping[str, Decimal]) -> Mapping[str, str]:
    return {"": "unimplemented"}


def admission(view, tasks: Sequence[str], off_arm: str = "off") -> Mapping[str, tuple[int, str]]:
    return {task: (-1, "unimplemented") for task in tasks}
