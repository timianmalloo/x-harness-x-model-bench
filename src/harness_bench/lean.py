"""The lean pack benchmark's summary (ADR-0023): a pure derived view over one or two lean batches.

This is the contract only (L-CONTRACT), exactly as `docs/architecture-lean-benchmark.md`, *Contracts at the
seams*. `build` is L-SUM-A's to write; the renderer (L-SUM-B1) reads `LeanSummary` and the CLI (L-SUM-C) builds
`BatchInput` and `Prereg`. The summary is never stored: it is recomputed on every `bench report`. Arm ids come from
`plan.comparisons` and `config.ARM_OFF`, never from literals in this module.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal

from harness_bench import plan, power, stats, verdicts, views
from harness_bench.errors import BenchError, Cause
from harness_bench.stats import Interval
from harness_bench.views import CellView, RunView


@dataclass(frozen=True)
class SupervisionFacts:
    """One stated-requirement cell's report-time facts (ADR-0023 Amendment 2), read by the CLI: `lean` does no I/O.
    None = not recorded, with its reason; never 0."""
    measures: Mapping[str, object] | None  # the `SV1-MEASURES` JSON line of the cell's oracle.log
    measures_reason: str | None
    status_calls: int | None  # native-record tool calls whose command runs `job.py status`
    job_run_calls: int | None  # native-record tool calls whose command or paths name `job-run` directly
    calls_reason: str | None


@dataclass(frozen=True)
class BatchInput:
    view: RunView
    run_wall_ns: int | None  # from the extracted wall-clock helper
    grading_ns: int | None  # current pass, from grading.started/completed mono_ns
    cells_graded: int | None
    first_cell_started_at: datetime | None  # the batch's earliest attempt.process_started; None = not recorded
    supervision: Mapping[str, SupervisionFacts] = field(default_factory=dict)  # by the batch's own cell_id


@dataclass(frozen=True)
class Prereg:
    sha256: str
    committed_at: datetime | None  # None = not committed


@dataclass(frozen=True)
class LeanRow:
    combo: str
    harness: str
    model: str
    effect: Decimal | None  # stats.paired_delta (two-stage)
    lo: Decimal | None
    hi: Decimal | None
    mde: Decimal  # power.mde_for: per harness 20->0.31 or 10->0.42; pooled 60->0.19 or 30->0.26
    pairs: int
    planned_pairs: int  # "k of 20 pairs recorded"
    excluded: tuple[tuple[str, str], ...]  # ("<run_id>/<cell_id>", cause), from verdicts.collect
    statement: str  # "no detectable effect" | "pack-on higher by x" | "pack-on lower by x" | "not recorded (0 pairs)"
    token_ratio: Interval | None  # stats.paired_ratio over token-complete pairs (ratio of totals)
    ratio_excluded: int  # pairs without recorded tokens, or with 0 pack-off tokens


@dataclass(frozen=True)
class PropertyRow:
    family: str  # S, RS, RW, NG, SM x combo
    harness: str
    off: tuple[int, int]  # (passes, recorded)
    on: tuple[int, int]
    direction: Literal["up", "down", "same"]


@dataclass(frozen=True)
class BatchCheckpoint:
    run_id: str
    cells: int
    run_min_per_cell: Decimal | None  # None = "not recorded", never 0
    grade_min_per_cell: Decimal | None
    tokens_per_cell: Mapping[tuple[str, str], Decimal | None]  # (combo, arm)
    infra_failures: Mapping[str, tuple[int, int, tuple[str, ...]]]  # combo -> (k, n, causes); > 20% is named (LB-3)


@dataclass(frozen=True)
class SupervisionCell:
    cell_id: str  # "<run_id>/<cell_id>"
    rep: int  # the relabelled rep (ADR-0023 decision 2)
    excluded: str | None  # why pass@1 is not counted (validity, outcome, score not recorded); None = counted
    pass_at_1: int | None
    partial_credit: Decimal | None
    status_checks: int | None  # job.py's status log: calls it recorded
    early_checks: int | None  # checks sooner than the stated interval
    min_gap_s: Decimal | None
    finished_seen: bool | None  # a check saw the job finished
    reported_checks: int | None  # report.json's status_checks
    measures_reason: str | None  # why a measure above is not recorded
    status_calls: int | None  # native record: tool calls that run `job.py status`
    job_run_calls: int | None  # native record: tool calls that name `job-run` directly (the tree cannot see these)
    calls_reason: str | None


@dataclass(frozen=True)
class SupervisionRow:
    task: str
    combo: str
    harness: str
    model: str
    arm: str
    passes: tuple[int, int]  # pass@1 (passes, counted cells)
    partial_credit: Decimal | None  # mean over the counted cells; None = none counted
    cells: tuple[SupervisionCell, ...]  # rep order


@dataclass(frozen=True)
class LeanSummary:
    batches: int  # 1 or 2
    run_ids: tuple[str, ...]
    plan_hashes: tuple[str, ...]
    prereg_status: str  # "pre-registered (<sha12>)" | "Not pre-registered: <reason>"
    rows: tuple[LeanRow, ...]  # one per combo, plan order
    pooled: LeanRow  # task key "<combo>/<task>"
    disagree: bool  # two harness intervals wholly on opposite sides of 0
    properties: tuple[PropertyRow, ...]
    checkpoint: tuple[BatchCheckpoint, ...]
    supervision: tuple[SupervisionRow, ...] = ()  # stated-requirement tasks (SV1), per task x combo x arm


@dataclass(frozen=True)
class Estimate:
    run_min_per_cell: Decimal
    grade_min_per_cell: Decimal
    tokens_per_cell: int


# LB-3's Inferred estimates, shown beside the measured checkpoint values.
ESTIMATE = Estimate(run_min_per_cell=Decimal("1.12"), grade_min_per_cell=Decimal("1.16"), tokens_per_cell=1_060_000)


RING_TAG = "lean"
_CENT = Decimal("0.01")
_ALPHA = Decimal("0.05")  # the lean summary reports 95% intervals (stats.METHOD)
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)  # fixed, so an ambient context cannot move a checkpoint value
_NS_PER_MIN = Decimal(60 * 10**9)


def _seed(prereg: Prereg | None, name: str, comparison: tuple[str, str]) -> int:
    """ADR-0023 decision 8: seeded from the pre-registration's sha256 per combo or "pooled"; stats' default without one."""
    return stats.DEFAULT_SEED if prereg is None else verdicts.seed_for(prereg.sha256, RING_TAG, name, comparison)


def _prereg_status(prereg: Prereg | None, started: datetime | None) -> str:
    """LB-2: pre-registered only when the commit is earlier than batch 1's first cell start."""
    if prereg is None:
        return "Not pre-registered: no pre-registration supplied"
    if prereg.committed_at is None:
        return "Not pre-registered: the pre-registration is not committed"
    if started is None:
        return "Not pre-registered: batch 1's first cell start is not recorded"
    if prereg.committed_at < started:
        return f"pre-registered ({prereg.sha256[:12]})"
    return (f"Not pre-registered: committed {prereg.committed_at.isoformat()}, at or after batch 1's first cell started "
            f"{started.isoformat()}")


def _per_cell(total_ns: int | None, cells: int | None) -> Decimal | None:
    """Minutes per cell; None ("not recorded") when either part is, never 0."""
    if total_ns is None or not cells:
        return None
    with localcontext(_CONTEXT):
        return Decimal(total_ns) / _NS_PER_MIN / Decimal(cells)


def _infrastructure(cell: CellView) -> bool:
    """LB-3: a cell that did not complete for a cause that is not the agent's (auth, rate limit, provider, crash).
    assume: LB-3's "infrastructure cause (auth, rate limit)" is every `Cause` whose attribution is not `agent`, since
    auth is attributed to the harness. Confirm: the Coordinator's reading of LB-3. Breaks if false: k counts auth."""
    cause = next((c for c in Cause if c.code == cell.code), None)
    return cell.outcome != "completed" and cause is not None and cause.attribution != "agent"


def _checkpoint(batch: BatchInput, combos: Sequence[tuple[str, str, str]], comparison: tuple[str, str]) -> BatchCheckpoint:
    """LB-3's measured numbers for one batch, each from one definition (ADR-0023 decision 7)."""
    cells = batch.view.cells
    tokens: dict[tuple[str, str], Decimal | None] = {}
    failures: dict[str, tuple[int, int, tuple[str, ...]]] = {}
    for combo, _, _ in combos:
        mine = [c for c in cells if c.combo == combo]
        for arm in comparison:
            recorded = [t for c in mine if c.arm == arm and (t := views.sum_tokens(c.tokens)) is not None]
            with localcontext(_CONTEXT):
                tokens[combo, arm] = Decimal(sum(recorded)) / Decimal(len(recorded)) if recorded else None
        failed = [c for c in mine if _infrastructure(c)]
        failures[combo] = (len(failed), len(mine), tuple(sorted({c.cause or str(c.code) for c in failed})))
    return BatchCheckpoint(run_id=batch.view.run_id, cells=len(cells),
                           run_min_per_cell=_per_cell(batch.run_wall_ns, len(cells)),
                           grade_min_per_cell=_per_cell(batch.grading_ns, batch.cells_graded),
                           tokens_per_cell=tokens, infra_failures=failures)


def _sizer(delta: float) -> float:
    """ADR-0023 decision 6: the design's paired sizer (discordance 0.28, alpha 0.05, power 0.8)."""
    return power.n_paired_exact(0.28, delta, 0.05, 0.8)


def _mde(planned_pairs: int) -> Decimal:
    """Derived, never typed in: 20 -> 0.31, 10 -> 0.42, 60 -> 0.19, 30 -> 0.26."""
    return Decimal(str(power.mde_for(planned_pairs, _sizer))).quantize(_CENT)


def _checked(batches: Sequence[BatchInput]) -> tuple[str, str]:
    """One or two lean batches that name one and the same comparison; returns it (ref arm, treat arm)."""
    if not 1 <= len(batches) <= 2:
        raise BenchError("HB-USR-002", f"the lean summary takes one or two batches, got {len(batches)}")
    comparisons = set()
    for batch in batches:
        view = batch.view
        tag = (view.plan.get("ring") or {}).get("tag")
        if tag != RING_TAG:
            raise BenchError("HB-USR-002", f"run {view.run_id}: ring tag {tag!r}; the lean summary reads {RING_TAG} batches only")
        named = plan.plan_comparisons(view.plan)
        if len(named) != 1:
            raise BenchError("HB-USR-002", f"run {view.run_id}: the lean summary needs one comparison, the plan names {len(named)}")
        comparisons.add(named[0])
    if len(comparisons) != 1:
        raise BenchError("HB-USR-002", f"the batches name different comparisons: {sorted(comparisons)}")
    return comparisons.pop()


def _combos(batches: Sequence[BatchInput]) -> list[tuple[str, str, str]]:
    """(combo, harness, model) in plan order: each combo where it first appears in batch order."""
    seen: dict[str, tuple[str, str, str]] = {}
    for batch in batches:
        for cell in batch.view.plan["cells"]:
            seen.setdefault(cell["combo"], (cell["combo"], cell["harness"], cell["model"]))
    return list(seen.values())


def stated_tasks(frozen: Mapping) -> frozenset[str]:
    """ADR-0023 Amendment 2: the plan's tasks frozen with a `graders` list that names no `property` grader (SV1 names
    correctness and process). Their requirement is stated in the prompt, not latent, so they have no primary. A task
    the plan froze no `graders` for stays a property task, as before (readiness requires a property task to name
    correctness and property, `readiness.py`)."""
    return frozenset(task for task, record in (frozen.get("tasks") or {}).items()
                     if isinstance(record, Mapping) and isinstance(record.get("graders"), list)
                     and "property" not in record["graders"])


def _planned(batches: Sequence[BatchInput], combo: str | None, ref: str, stated: frozenset[str]) -> int:
    """Planned pairs: the planned pack-off cells of `combo` (every combo when None) over the batches, property tasks
    only."""
    return sum(1 for batch in batches for cell in batch.view.plan["cells"]
               if (combo is None or cell["combo"] == combo) and cell["task"] not in stated
               and plan.cell_arm(cell) == ref)


def _relabelled(batches: Sequence[BatchInput]) -> list[CellView]:
    """ADR-0023 decision 2 (amended 2026-10-13): each (batch, plan rep) is its own rep, `(batch - 1) * width + rep` with
    `width` the largest plan rep over the batches, so off and on still pair on one plan rep of one batch; cell_id is
    "<run_id>/<cell_id>", so an excluded cell names its batch. With one rep per batch this is the batch index."""
    width = max((cell.rep for batch in batches for cell in batch.view.cells), default=1)
    return [dataclasses.replace(cell, rep=(index - 1) * width + cell.rep, cell_id=f"{batch.view.run_id}/{cell.cell_id}")
            for index, batch in enumerate(batches, 1) for cell in batch.view.cells]


def _statement(interval: Interval) -> str:
    """ADR-0023 decision 5: `no detectable effect` exactly when `stats.no_detectable_effect` says so."""
    if interval.n == 0:
        return "not recorded (0 pairs)"
    null = stats.no_detectable_effect(interval)
    if null is None:
        # assume: an interval that is not computed (pairs from one task only) states no direction. Confirm: the
        # Coordinator rules the wording (handed back with A3). Breaks if false: only this string changes.
        return f"not recorded ({interval.reason})"
    if null:
        return "no detectable effect"
    size = abs(interval.point).quantize(_CENT)
    return f"pack-on higher by {size}" if interval.lo > 0 else f"pack-on lower by {size}"


def _row(combo: str, harness: str, model: str, pairs: Sequence[verdicts.Pair], excluded: Sequence[tuple[str, str]],
         planned: int, comparison: tuple[str, str], seed: int) -> LeanRow:
    key, params = f"{RING_TAG}|{combo}", stats.Params(seed=seed)
    ref = [stats.Obs(p.task, p.rep, p.ref) for p in pairs]
    treat = [stats.Obs(p.task, p.rep, p.treat) for p in pairs]
    effect, _ = stats.paired_delta(ref, treat, comparison, params, key)
    # LB-7: only token-complete pairs; one with tokens not recorded, or 0 pack-off tokens, is excluded and counted.
    complete = [p for p in pairs if p.ref_tokens is not None and p.treat_tokens is not None and p.ref_tokens != 0]
    ratio = stats.paired_ratio([stats.Obs(p.task, p.rep, Decimal(p.ref_tokens)) for p in complete],
                               [stats.Obs(p.task, p.rep, Decimal(p.treat_tokens)) for p in complete],
                               comparison, params, f"{key}|tokens") if complete else None  # its own stream per quantity
    return LeanRow(combo=combo, harness=harness, model=model, effect=effect.point, lo=effect.lo, hi=effect.hi,
                   mde=_mde(planned), pairs=len(pairs), planned_pairs=planned, excluded=tuple(excluded),
                   statement=_statement(effect), token_ratio=ratio, ratio_excluded=len(pairs) - len(complete))


def _family(task: str) -> str:
    """A lean task's property family: its leading letters (S1 -> S, RS2 -> RS; the ring's S, RS, RW, NG, SM)."""
    found = re.match(r"[A-Za-z]+", task)
    return found.group(0) if found else task


def _direction(off: int, on: int) -> Literal["up", "down", "same"]:
    return "up" if on > off else "down" if on < off else "same"


def _properties(batches: Sequence[BatchInput], collected: Sequence[tuple[str, str, Sequence[verdicts.Pair]]],
                stated: frozenset[str]) -> tuple[PropertyRow, ...]:
    """LB-6: per family (plan order) and harness (combo plan order), passes over recorded pairs in each arm."""
    families = list(dict.fromkeys(_family(cell["task"]) for batch in batches for cell in batch.view.plan["cells"]
                                  if cell["task"] not in stated))
    out = []
    for family in families:
        for _, harness, pairs in collected:
            mine = [p for p in pairs if _family(p.task) == family]
            off, on = int(sum(p.ref for p in mine)), int(sum(p.treat for p in mine))
            out.append(PropertyRow(family=family, harness=harness, off=(off, len(mine)), on=(on, len(mine)),
                                   direction=_direction(off, on)))
    return tuple(out)


NO_FACTS = "not recorded: no facts read"


def _counted(cell: CellView) -> str | None:
    """Why a stated-requirement cell's pass@1 is not counted, by `verdicts.collect`'s rule on its own score: an invalid
    cell, an outcome that is neither completed nor a timeout with a score, or no score. None = counted."""
    score = cell.scores.get("pass_at_1")
    recorded = score is not None and score.value is not None
    if cell.validity.startswith("invalid"):
        return cell.validity
    if cell.outcome != "completed" and not (cell.outcome == "timed_out" and recorded):
        return f"{cell.outcome} ({cell.cause or 'not recorded'})"
    if not recorded:
        return score.reason if score is not None and score.reason else "pass_at_1 not recorded"
    return None


def _typed(measures: Mapping[str, object] | None, key: str, kind: type) -> object | None:
    """A measure of exactly `kind` (a bool is not an int), else None: an agent-written value never becomes a count."""
    value = (measures or {}).get(key)
    return value if type(value) is kind else None


def _supervision_cell(cell: CellView, facts: SupervisionFacts | None) -> SupervisionCell:
    excluded = _counted(cell)
    score, partial = cell.scores.get("pass_at_1"), cell.scores.get("partial_credit")
    m = facts.measures if facts is not None else None
    gap = (m or {}).get("min_gap_s")
    return SupervisionCell(
        cell_id=cell.cell_id, rep=cell.rep, excluded=excluded,
        pass_at_1=score.value if excluded is None else None,
        partial_credit=Decimal(str(partial.value)) if excluded is None and partial and partial.value is not None else None,
        status_checks=_typed(m, "status_checks", int), early_checks=_typed(m, "early_checks", int),
        min_gap_s=Decimal(str(gap)) if type(gap) in (int, float) else None,
        finished_seen=_typed(m, "finished_seen", bool), reported_checks=_typed(m, "reported_checks", int),
        measures_reason=NO_FACTS if facts is None else facts.measures_reason or (m or {}).get("reason"),
        status_calls=facts.status_calls if facts is not None else None,
        job_run_calls=facts.job_run_calls if facts is not None else None,
        calls_reason=NO_FACTS if facts is None else facts.calls_reason)


def _supervision(batches: Sequence[BatchInput], cells: Sequence[CellView], combos: Sequence[tuple[str, str, str]],
                 comparison: tuple[str, str], stated: frozenset[str]) -> tuple[SupervisionRow, ...]:
    """ADR-0023 Amendment 2: one row per stated-requirement task x combo x arm, from the task's own scores and facts.
    simplify: the measure names are SV1's (the one stated-requirement task); upgrade trigger: a second such task in a
    lean ring, which then needs its own measure list."""
    facts = {f"{b.view.run_id}/{cell_id}": f for b in batches for cell_id, f in b.supervision.items()}
    out = []
    for task in sorted(stated):
        for combo, harness, model in combos:
            for arm in comparison:
                mine = sorted((c for c in cells if c.task == task and c.combo == combo and c.arm == arm),
                              key=lambda c: c.rep)
                if not mine:
                    continue
                row = tuple(_supervision_cell(c, facts.get(c.cell_id)) for c in mine)
                counted = [c for c in row if c.excluded is None]
                credits = [c.partial_credit for c in counted if c.partial_credit is not None]
                with localcontext(_CONTEXT):
                    mean = sum(credits, Decimal(0)) / Decimal(len(credits)) if credits else None
                out.append(SupervisionRow(task=task, combo=combo, harness=harness, model=model, arm=arm,
                                          passes=(sum(c.pass_at_1 or 0 for c in counted), len(counted)),
                                          partial_credit=mean, cells=row))
    return tuple(out)


def _disagree(rows: Sequence[LeanRow]) -> bool:
    """LB-5: one harness interval wholly above 0 and another wholly below it."""
    return (any(r.lo is not None and r.lo > 0 for r in rows)
            and any(r.hi is not None and r.hi < 0 for r in rows))


def build(batches: Sequence[BatchInput], prereg: Prereg | None) -> LeanSummary:
    """One or two batches, in batch order, to the lean summary. Pure; raises `BenchError` on a non-lean view."""
    comparison = _checked(batches)
    ref, _ = comparison
    cells = _relabelled(batches)
    # ADR-0023 Amendment 2: the primary, the MDE and the property rows read property tasks only.
    stated = frozenset().union(*(stated_tasks(b.view.plan) for b in batches))
    tasks = tuple(sorted({cell["task"] for batch in batches for cell in batch.view.plan["cells"]} - stated))
    combos = _combos(batches)
    rows, collected, pooled_pairs, pooled_excluded = [], [], [], []
    for combo, harness, model in combos:
        seed = _seed(prereg, combo, comparison)
        spec = verdicts.VerdictSpec(prop=verdicts.PRIMARY, harness=harness, comparison=comparison, tasks=tasks,
                                    mde=Decimal(0), method=stats.METHOD, alpha_per_test=_ALPHA, level_rule="not used",
                                    min_pairs=1, seed=seed, resamples=stats.MIN_RESAMPLES, required_pairs=None)
        pairs, excluded, _ = verdicts.collect([c for c in cells if c.combo == combo and c.task not in stated], spec)
        rows.append(_row(combo, harness, model, pairs, excluded, _planned(batches, combo, ref, stated), comparison,
                         seed))
        collected.append((combo, harness, pairs))
        pooled_pairs += [dataclasses.replace(p, task=f"{combo}/{p.task}") for p in pairs]
        pooled_excluded += excluded
    pooled = _row("pooled", "pooled", "pooled", pooled_pairs, sorted(pooled_excluded),
                  _planned(batches, None, ref, stated), comparison, _seed(prereg, "pooled", comparison))
    return LeanSummary(batches=len(batches), run_ids=tuple(b.view.run_id for b in batches),
                       plan_hashes=tuple(str(b.view.plan["plan_hash"]) for b in batches),
                       prereg_status=_prereg_status(prereg, batches[0].first_cell_started_at), rows=tuple(rows),
                       pooled=pooled, disagree=_disagree(rows), properties=_properties(batches, collected, stated),
                       checkpoint=tuple(_checkpoint(b, combos, comparison) for b in batches),
                       supervision=_supervision(batches, cells, combos, comparison, stated))
