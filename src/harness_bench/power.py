"""Power analysis (W1-H). Fleiss unpaired and Connor paired, stdlib only.

`cells` excludes calibration cells. The grid is tasks, harnesses, and the
distinct arms of `comparisons`, times the reps each task needs.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from statistics import NormalDist

from harness_bench.errors import BenchError

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
    divide, rule = LEVEL_RULES[method]
    per_test = alpha / m if divide else alpha
    return (per_test, rule)


def _z_alpha(alpha: float) -> float:
    return NormalDist().inv_cdf(1.0 - alpha / 2.0)


def _z_beta(power: float) -> float:
    return NormalDist().inv_cdf(power)


def n_unpaired_exact(p0: float, p1: float, alpha: float, power: float) -> float:
    """Fleiss, Levin and Paik, no continuity correction. n per arm."""
    delta = p1 - p0
    if delta == 0.0 or p0 < 0.0 or p0 > 1.0 or p1 < 0.0 or p1 > 1.0:
        return math.inf
    pbar = (p0 + p1) / 2.0
    qbar = 1.0 - pbar
    term = _z_alpha(alpha) * math.sqrt(2.0 * pbar * qbar) + _z_beta(power) * math.sqrt(
        p0 * (1.0 - p0) + p1 * (1.0 - p1))
    return (term * term) / (delta * delta)


def n_paired_exact(psi: float, delta: float, alpha: float, power: float) -> float:
    """Connor 1987. n discordant pairs. An impossible delta searches as +inf."""
    if delta <= 0.0 or psi < delta * delta:
        return math.inf
    term = _z_alpha(alpha) * math.sqrt(psi) + _z_beta(power) * math.sqrt(psi - delta * delta)
    return (term * term) / (delta * delta)


def _snap(x: float) -> int:
    return math.ceil(x - 1e-9)


def mde_for(n: int, sizer: Callable[[float], float], lo: float = 0.001, hi: float = 0.999) -> float:
    """Smallest delta whose required n is at most `n`. Sixty bisection steps; return the high end."""
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if sizer(mid) <= n:
            hi = mid
        else:
            lo = mid
    return hi


def _open_unit(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    return 0 < value < 1


def _nonneg(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    return value >= 0


def _reject(ok: bool, field: str) -> None:
    if not ok:
        raise BenchError("HB-PWR-001", field)


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _paired_n(psi: float, alpha: float, power: float, delta: float) -> float:
    return n_paired_exact(psi, delta, alpha, power)


def _unpaired_n(p0: float, alpha: float, power: float, delta: float) -> float:
    return n_unpaired_exact(p0, p0 + delta, alpha, power)


def analyse(inputs: Mapping) -> dict[str, PowerResult]:
    alpha = _decimal(inputs["alpha"])
    power = _decimal(inputs["power"])
    _reject(_open_unit(alpha), "alpha")
    _reject(_open_unit(power), "power")
    correction = inputs["correction"]
    method = correction["method"]
    m = correction["m"]
    _reject(isinstance(m, int) and not isinstance(m, bool) and m >= 1, "m")
    try:
        alpha_pt, level_rule = level_for(method, alpha, m)
    except KeyError:
        raise BenchError("HB-PWR-001", "method") from None
    pairing_unit = inputs["pairing_unit"]
    _reject(pairing_unit in PAIRING, "pairing")
    slots = inputs.get("slots")
    _reject(isinstance(slots, int) and not isinstance(slots, bool) and slots >= 1, "slots")
    if "planned_reps_per_task" in inputs:
        planned = inputs["planned_reps_per_task"]
        _reject(isinstance(planned, int) and not isinstance(planned, bool) and planned >= 1, "planned_reps_per_task")
    else:
        planned = None
    harnesses = list(inputs["harnesses"])
    comparisons = [list(pair) for pair in inputs["comparisons"]]
    arms = {arm for pair in comparisons for arm in pair}
    wall = float(inputs["mean_wall_per_cell_s"])
    token_mean = float(inputs["mean_tokens_per_cell"])
    alpha_f = float(alpha_pt)
    power_f = float(power)
    results: dict[str, PowerResult] = {}
    for name, body in inputs["properties"].items():
        mde = body["mde"]
        _reject(_open_unit(mde), "mde")
        mde_f = float(mde)
        tasks = body["tasks"]
        _reject(isinstance(tasks, list) and len(tasks) > 0, "tasks")
        if "sd" in body:
            _reject(_nonneg(body["sd"]), "sd")
        if "rep_spread" in body:
            _reject(_nonneg(body["rep_spread"]), "rep_spread")
        assumed: list[str] = []
        raw_rate = body.get("control_rate", "assumed")
        if raw_rate == "assumed":
            p0 = 0.5
            assumed.append("control_rate")
        else:
            p0 = float(raw_rate)
        if pairing_unit == "task-harness-rep":
            raw_psi = body.get("discordance", "assumed")
            if raw_psi == "assumed":
                p1 = p0 + mde_f
                psi = p0 * (1.0 - p1) + p1 * (1.0 - p0)
                assumed.append("discordance")
            else:
                psi = float(raw_psi)
            _reject(psi >= mde_f * mde_f, "psi")
            exact = n_paired_exact(psi, mde_f, alpha_f, power_f)
            sizer: Callable[[float], float] = partial(_paired_n, psi, alpha_f, power_f)
        else:
            exact = n_unpaired_exact(p0, p0 + mde_f, alpha_f, power_f)
            sizer = partial(_unpaired_n, p0, alpha_f, power_f)
        n = _snap(exact)
        solved = mde_for(n, sizer)
        reps = math.ceil(n / len(tasks))
        cells = len(tasks) * len(harnesses) * len(arms) * reps
        hours = cells * wall / slots / 3600
        tokens = cells * token_mean
        if planned is not None:
            reachable_mde = mde_for(len(tasks) * planned, sizer)
        else:
            reachable_mde = None
        results[str(name)] = PowerResult(
            alpha=alpha,
            power=power,
            mde=solved,
            pairing_unit=pairing_unit,
            correction={"method": method, "m": m},
            required_pairs=[
                {"harness": harness, "comparison": [pair[0], pair[1]], "n": n}
                for harness in harnesses
                for pair in comparisons
            ],
            reps_per_task=reps,
            cells=cells,
            hours=hours,
            tokens=tokens,
            assumed=assumed,
            alpha_per_test=alpha_pt,
            level_rule=level_rule,
            reachable_mde=reachable_mde,
        )
    return results
