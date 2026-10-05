"""Ring gates (W1-H, W0 section 8): pilot items, the pack-regression signal and task admission.

Pure functions, stdlib only (ADR-0020 section 5). Every pilot item is one (kind, ident) with a detail; the
output is sorted and unique. A cell that is lost (`bnd-a-loss` or `cell-lost`) yields that one item only: its
missing scores are the consequence, not a second finding. The regression signal reuses `verdicts.collect` and
`verdicts.verdict`; this module runs no bootstrap of its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from harness_bench import errors, plan, power, verdicts
from harness_bench.errors import BenchError

EMPTY: Mapping[str, frozenset[str]] = MappingProxyType({})

_BND_A_CODE = errors.Cause.protocol.code
_BLOCKED_CODES = frozenset({errors.Cause.blocked_permission.code, errors.Cause.blocked_auth.code})
_CAUSES = {cause.code: cause for cause in errors.Cause}
_TAMPERED = errors.RUN_CODES["HB-CHK-002"]
_GRADER_ERROR = "HB-GRD-003"
_REGRESSION_ALPHA = Decimal("0.05")  # simplify: fixed 95 %, uncorrected; ceiling: one comparison per property per ring; upgrade trigger: a ring with more than one candidate
_ARMS = ("incumbent", "candidate")


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


def _task(cell) -> str:
    return verdicts._task_rep(cell, plan.cell_arm(vars(cell)))[0]


def _lost(cell) -> str | None:
    """The detail naming why the cell is lost, or None."""
    cause = _CAUSES.get(cell.code)
    if cell.outcome == "failed" or cell.code in _BLOCKED_CODES or (cause is not None and cause.invalidates):
        return f"outcome {cell.outcome}, cause {cell.cause or 'not recorded'}, code {cell.code or 'none'}"
    return None


def _cell_items(cell, task_has_primary: bool) -> list[GateItem]:
    if cell.code == _BND_A_CODE and cell.outcome == "failed":
        return [GateItem(GateKind.BND_A, cell.cell_id, f"code {cell.code}, outcome {cell.outcome}")]
    lost = _lost(cell)
    if lost is not None:
        return [GateItem(GateKind.CELL_LOST, cell.cell_id, lost)]
    items: list[GateItem] = []
    grader = next((m.reason for m in cell.scores.values() if (m.reason or "").startswith(_GRADER_ERROR)), None)
    if grader is not None:
        items.append(GateItem(GateKind.GRADER_ERROR, cell.cell_id, grader))
    primary = cell.scores.get(verdicts.PRIMARY)
    if task_has_primary and (primary is None or primary.value is None):
        reason = primary.reason if primary is not None else None
        if reason == _TAMPERED:
            items.append(GateItem(GateKind.CHECK_TAMPERED, cell.cell_id, reason))
        elif not (reason or "").startswith(_GRADER_ERROR):
            items.append(GateItem(GateKind.PRIMARY_UNRECORDED, cell.cell_id, reason or "no reason recorded"))
    return items


def ring_items(view, expected_na: Mapping[str, frozenset[str]]) -> list[GateItem]:
    """The cell-level items (shared by `pilot` and the regression ring's withheld text), unsorted."""
    by_task: dict[str, list] = {}
    for cell in view.cells:
        by_task.setdefault(_task(cell), []).append(cell)
    items: list[GateItem] = []
    for task, cells in by_task.items():
        task_has_primary = any(verdicts.PRIMARY in c.scores for c in cells)
        if not task_has_primary:
            items.append(GateItem(GateKind.TASK_NO_PRIMARY, task, f"no {verdicts.PRIMARY} row in {len(cells)} cells"))
        for cell in cells:
            items += _cell_items(cell, task_has_primary)
        for metric in sorted({m for c in cells for m in c.scores} - {verdicts.PRIMARY} - set(expected_na.get(task, ()))):
            rows = [c.scores[metric] for c in cells if metric in c.scores]
            if all(row.value is None for row in rows):
                reasons = ", ".join(sorted({row.reason or "no reason recorded" for row in rows}))
                items.append(GateItem(GateKind.METRIC_UNRECORDED, f"{task}/{metric}", reasons))
    return items


def pilot(
    view,
    hidden_test_disagreements: Sequence[str],
    unbiased_failures: Sequence[str],
    *,
    expected_na: Mapping[str, frozenset[str]] = EMPTY,
) -> list[GateItem]:
    for name, listed in (("hidden_test_disagreements", hidden_test_disagreements),
                         ("unbiased_failures", unbiased_failures)):
        if listed is None:
            raise BenchError("HB-USR-002", f"pilot: {name} was not read (a None list); the caller reads it or raises")
    items = ring_items(view, expected_na)
    items += [GateItem(GateKind.HIDDEN_NONDETERMINISTIC, ident, "double-run hidden-test pass disagrees")
              for ident in hidden_test_disagreements]
    items += [GateItem(GateKind.SUSPEND_BLIND, ident, "the suspend detector could not read the unbiased clock")
              for ident in unbiased_failures]
    return sorted(set(items), key=lambda i: (i.kind, i.ident))


def pack_regression(view, mde: Mapping[str, Decimal]) -> Mapping[str, str]:
    """Per property: `regression signal` iff the 95 % interval of candidate minus incumbent has hi < 0.

    assume: each key of `mde` is a property whose strata are all tasks in `view.plan["tasks"]`, and the view has
    one harness. Confirm: the first `pack_regression` caller (none in E1; a pack-regression ring). Breaks if
    false: a view with more than one `mde` key or more than one harness raises HB-USR-002, never a wrong signal.

    assume: a verdict with `interval is None` (a stratum with 0 pairs) gives `Result withheld: <reason>.`.
    Confirm: as above. Breaks if false: the text changes; no signal is emitted either way.
    """
    ring = view.plan.get("ring")
    if ring is None:
        raise BenchError("HB-USR-002", "pack_regression: the view's plan has no ring")
    if len(mde) > 1:
        raise BenchError("HB-USR-002", f"pack_regression: one property per ring, got {sorted(mde)}")
    present = {plan.cell_arm(vars(cell)) for cell in view.cells}
    missing = next((arm for arm in _ARMS if arm not in present), None)
    if missing is not None:
        return {prop: f"Result withheld: ring is missing {missing}." for prop in mde}
    harnesses = sorted({cell.harness for cell in view.cells})
    if len(harnesses) > 1:
        raise BenchError("HB-USR-002", f"pack_regression: one harness per ring, got {harnesses}")
    out: dict[str, str] = {}
    for prop, bound in mde.items():
        spec = verdicts.VerdictSpec(
            prop=prop, harness=harnesses[0], comparison=_ARMS, tasks=tuple(view.plan["tasks"]), mde=bound,
            method="none", alpha_per_test=_REGRESSION_ALPHA,
            level_rule=power.level_for("none", _REGRESSION_ALPHA, 1)[1], min_pairs=1,
            seed=verdicts.seed_for(ring["hash"], prop, "ring", _ARMS),
            resamples=verdicts.resamples_for(_REGRESSION_ALPHA), required_pairs=None)
        pairs, excluded, na_counts = verdicts.collect(view.cells, spec)
        result = verdicts.verdict(spec, pairs, excluded, na_counts)
        if result.interval is None:
            out[prop] = f"Result withheld: {result.reason}."
        elif result.interval[1] < 0:
            out[prop] = "regression signal"
        else:
            out[prop] = f"no regression detected at {bound}"
    return out


def admission(view, tasks: Sequence[str], off_arm: str = "off") -> Mapping[str, tuple[int, str]]:
    """EV-8: per task, the `off_arm` cells' primary. All 1 is saturated, all 0 is the floor, else admitted.

    assume: a task with no `off_arm` cell also raises HB-USR-002. Confirm: X-C's `admit` pre-check (W1-C
    section 5). Breaks if false: such a task is admitted with no data.
    """
    values: dict[str, list] = {task: [] for task in tasks}
    for cell in view.cells:
        if plan.cell_arm(vars(cell)) != off_arm:
            continue
        task = _task(cell)
        if task not in values:
            continue
        primary = cell.scores.get(verdicts.PRIMARY)
        if primary is None or primary.value is None:
            reason = primary.reason if primary is not None else "no row"
            raise BenchError("HB-USR-002", f"admission: task {task} cell {cell.cell_id} has no primary ({reason})")
        values[task].append(primary.value)
    out: dict[str, tuple[int, str]] = {}
    for task, found in values.items():
        if not found:
            raise BenchError("HB-USR-002", f"admission: task {task} has no {off_arm} cell to decide on")
        if all(v == 1 for v in found):
            out[task] = (0, "saturated")
        elif all(v == 0 for v in found):
            out[task] = (0, "floor")
        else:
            out[task] = (1, "")
    return out
