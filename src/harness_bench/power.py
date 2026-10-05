"""Power analysis skeleton (W1-H). Final signatures; values sit outside the result domain.

`cells` excludes calibration cells. The green commit replaces these bodies.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal

PAIRING = ("unpaired", "task-harness-rep")

# The one table (R-96). level_for is its only reader.
LEVEL_RULES: dict[str, tuple[bool, str]] = {
    "bonferroni": (True, "alpha/m (Bonferroni)"),
    "holm": (True, "alpha/m (Bonferroni; Holm's first step)"),
    "none": (False, "alpha (no correction)"),
}


@dataclass(frozen=True)
class PowerResult:
    alpha: Decimal
    power: Decimal
    mde: float
    pairing_unit: str
    correction: dict
    required_pairs: list
    reps_per_task: int
    cells: int
    hours: float
    tokens: float
    assumed: list
    alpha_per_test: Decimal
    level_rule: str
    reachable_mde: float | None


def level_for(method: str, alpha: Decimal, m: int) -> tuple[Decimal, str]:
    return (Decimal(-1), "unimplemented")


def n_unpaired_exact(p0: float, p1: float, alpha: float, power: float) -> float:
    return -1.0


def n_paired_exact(psi: float, delta: float, alpha: float, power: float) -> float:
    return -1.0


def _snap(x: float) -> int:
    return -1


def mde_for(n: int, sizer: Callable[[float], float], lo: float = 0.001, hi: float = 0.999) -> float:
    return 0.0


def _sentinel() -> PowerResult:
    return PowerResult(
        alpha=Decimal(0),
        power=Decimal(0),
        mde=0.0,
        pairing_unit="unimplemented",
        correction={"method": "unimplemented", "m": -1},
        required_pairs=[{"harness": "", "comparison": ["", ""], "n": -1}],
        reps_per_task=-1,
        cells=-1,
        hours=-1.0,
        tokens=-1.0,
        assumed=["unimplemented"],
        alpha_per_test=Decimal(-1),
        level_rule="unimplemented",
        reachable_mde=-1.0,
    )


def analyse(inputs: Mapping) -> dict[str, PowerResult]:
    properties = inputs.get("properties") if isinstance(inputs, Mapping) else None
    names = tuple(properties) if isinstance(properties, Mapping) and properties else ("_",)
    return {str(name): _sentinel() for name in names}
