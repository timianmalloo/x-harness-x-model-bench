"""L-SUM-A: the lean summary (ADR-0023) and the numeric views helpers its CLI feeds it.

The helpers are red first on hand-built ledgers: each value is a difference of recorded `mono_ns` readings (or the
earliest recorded instant), and a missing reading is None ("not recorded"), never 0.
"""

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import (
    config,
    egress,  # noqa: F401  (first: egress and report.html import each other)
    lean,
    ledger,
    stats,
    verdicts,
    views,
)
from harness_bench.errors import BenchError
from harness_bench.report import html


def _helper(name: str):
    assert hasattr(views, name), f"views.{name} is absent (L-SUM-A A2)"
    return getattr(views, name)


def _run_dir(tmp_path: Path, engine: list[dict], passes: tuple[tuple[str, list[dict], bool], ...] = ()) -> Path:
    """An events fact only: one engine segment, then each grading pass `(segment_id, rows, sealed)`."""
    run_dir = tmp_path / "run"
    with ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev:
        for row in engine:
            ev.append(row)
    for segment_id, rows, sealed in passes:
        with ledger.SegmentWriter.create(run_dir / "events", segment_id) as writer:
            for row in rows:
                writer.append(row)
            if sealed:
                writer.seal()
    return run_dir


def _pass(gid: str, started_ns: int | None, completed_ns: int | None, cells: int, at: str) -> list[dict]:
    started = {"kind": "grading.started", "grading_id": gid, "catalog_version": "0.7", "recorded_at": at}
    completed = {"kind": "grading.completed", "grading_id": gid, "cells_graded": cells, "recorded_at": at}
    if started_ns is not None:
        started["mono_ns"] = started_ns
    if completed_ns is not None:
        completed["mono_ns"] = completed_ns
    return [started, completed]


# ------------------------------------------------------------------ A2: views.run_wall_ns


def test_run_wall_ns_is_run_completed_minus_run_started_mono_ns(tmp_path):
    run_dir = _run_dir(tmp_path, [{"kind": "run.started", "mono_ns": 5},
                                  {"kind": "run.completed", "mono_ns": 2_500_000_005}])
    assert _helper("run_wall_ns")(run_dir) == 2_500_000_000
    # One definition: the report's formatted wall clock is this number in seconds.
    assert html._run_wall_clock(run_dir) == "2.5 s"


def test_run_wall_ns_is_not_recorded_without_either_reading(tmp_path):
    run_wall_ns = _helper("run_wall_ns")
    assert run_wall_ns(_run_dir(tmp_path / "a", [{"kind": "run.started", "mono_ns": 5}])) is None
    assert run_wall_ns(_run_dir(tmp_path / "b", [{"kind": "run.started"},
                                                 {"kind": "run.completed", "mono_ns": 9}])) is None


# ------------------------------------------------------------------ A2: views.grading_duration


def test_grading_duration_reads_the_current_pass_only(tmp_path):
    run_dir = _run_dir(tmp_path, [{"kind": "run.started", "mono_ns": 0}], (
        ("grade-g1", _pass("grade-g1", 10, 1_010, 3, "2026-10-09T10:00:00.000Z"), True),
        ("grade-g2", _pass("grade-g2", 2_000, 5_000, 4, "2026-10-09T11:00:00.000Z"), True),
        ("grade-g3", _pass("grade-g3", 0, 99_999, 9, "2026-10-09T12:00:00.000Z")[:1], False),  # abandoned
    ))
    assert _helper("grading_duration")(run_dir) == (3_000, 4)


def test_grading_duration_is_not_recorded_without_a_pass_or_a_reading(tmp_path):
    grading_duration = _helper("grading_duration")
    assert grading_duration(_run_dir(tmp_path / "a", [{"kind": "run.started"}])) == (None, None)
    no_start = _run_dir(tmp_path / "b", [{"kind": "run.started"}],
                        (("grade-g1", _pass("grade-g1", None, 5_000, 4, "2026-10-09T10:00:00.000Z"), True),))
    assert grading_duration(no_start) == (None, 4)


# ------------------------------------------------------------------ A2: views.first_cell_started_at


def test_first_cell_started_at_is_the_earliest_process_start(tmp_path):
    run_dir = _run_dir(tmp_path, [
        {"kind": "run.started", "recorded_at": "2026-10-09T09:00:00.000Z"},
        {"kind": "attempt.process_started", "cell_id": "c2", "recorded_at": "2026-10-09T10:00:05.000Z"},
        {"kind": "attempt.process_started", "cell_id": "c1", "recorded_at": "2026-10-09T10:00:01.500Z"},
    ])
    assert _helper("first_cell_started_at")(run_dir) == datetime(2026, 10, 9, 10, 0, 1, 500_000, tzinfo=UTC)


def test_first_cell_started_at_is_not_recorded_when_any_start_lacks_its_instant(tmp_path):
    first = _helper("first_cell_started_at")
    assert first(_run_dir(tmp_path / "a", [{"kind": "run.started", "recorded_at": "2026-10-09T09:00:00.000Z"}])) is None
    assert first(_run_dir(tmp_path / "b", [
        {"kind": "attempt.process_started", "cell_id": "c1", "recorded_at": "2026-10-09T10:00:01.500Z"},
        {"kind": "attempt.process_started", "cell_id": "c2"},
    ])) is None


# ------------------------------------------------------------------ A3: lean.build's per-harness rows

REF, TREAT = config.ARM_OFF, "on"  # the plan's one comparison; lean.build reads it from plan.comparisons
TASKS = ("S1", "S2", "RS1", "RS2", "RW1", "RW2", "NG1", "NG2", "SM1", "SM2")  # the lean ring's ten tasks
COMBOS = (("cc", "claude_code", "claude-opus-5-5"), ("cx", "codex", "gpt-6.1-sol"), ("cp", "copilot", "gpt-6.1-sol"))
TOKENS = {"m": {"output": 100}}


def _lift(combo: str, task: str, arm: str, batch: int):
    """pack-on passes the first six tasks, pack-off none: a known effect of 0.6."""
    return 1 if arm == TREAT and task in TASKS[:6] else 0


def _cell(combo: str, task: str, arm: str, value, **kw) -> views.CellView:
    harness, model = next((h, m) for c, h, m in COMBOS if c == combo)
    fields = {"outcome": "completed", "cause": None, "validity": "valid", "tokens": TOKENS, "code": None} | kw
    return views.CellView(
        cell_id=f"{combo}-{task}-{arm}", task=task, rep=1, label=f"{task}.{combo}.{arm}.r1", combo=combo, arm=arm,
        harness=harness, model=model, outcome=fields["outcome"], cause=fields["cause"], code=fields["code"],
        validity=fields["validity"], validity_code=None, wall_ms=views.Measure(1000), model_ms=views.Measure(None, "x"),
        tool_ms=views.Measure(None, "x"), idle_ms=views.Measure(None, "x"), tokens=fields["tokens"], tokens_reason=None,
        scores={verdicts.PRIMARY: views.Measure(value, None if value is not None else "no summary")})


def _view(run_id: str, cells: list[views.CellView], tag: str | None = "lean") -> views.RunView:
    plan = {"run_id": run_id, "plan_hash": f"hash-{run_id}", "comparisons": [[REF, TREAT]],
            "cells": [{"cell_id": c.cell_id, "task": c.task, "rep": c.rep, "combo": c.combo, "harness": c.harness,
                       "model": c.model, "arm": c.arm} for c in cells]}
    if tag is not None:
        plan["ring"] = {"tag": tag}
    return views.RunView(run_id, plan, True, "grade-1", "0.7", cells, {})


def _batches(n: int = 2, value=_lift, combos=("cc",), change=None, tag: str | None = "lean") -> list:
    """`n` lean batches (run ids r1, r2): every combo x task x arm, one repetition each, valued by `value`;
    `change(batch, cell)` returns a replacement cell."""
    out = []
    for batch in range(1, n + 1):
        cells = [_cell(combo, task, arm, value(combo, task, arm, batch))
                 for combo in combos for task in TASKS for arm in (REF, TREAT)]
        if change is not None:
            cells = [change(batch, c) for c in cells]
        out.append(lean.BatchInput(_view(f"r{batch}", cells, tag), None, None, None, None))
    return out


def _build(batches: list, prereg: lean.Prereg | None) -> lean.LeanSummary:
    try:
        summary = lean.build(batches, prereg)
    except NotImplementedError as exc:  # L-CONTRACT's placeholder: red on the assert below, not on the raise
        summary = exc
    assert isinstance(summary, lean.LeanSummary), f"lean.build returned no summary: {summary!r}"
    return summary


def _refused(batches: list) -> BenchError:
    try:
        lean.build(batches, None)
    except Exception as exc:  # noqa: BLE001 - any other outcome fails the assert below
        caught = exc
    else:
        caught = None
    assert isinstance(caught, BenchError), f"lean.build did not refuse with BenchError: {caught!r}"
    return caught


def _obs(batches: list, combo: str, arm: str, task=lambda c: c.task) -> list[stats.Obs]:
    return [stats.Obs(task(c), index, Decimal(str(c.scores[verdicts.PRIMARY].value)))
            for index, b in enumerate(batches, 1) for c in b.view.cells
            if c.combo == combo and c.arm == arm and c.scores[verdicts.PRIMARY].value is not None]


def test_a_row_is_stats_paired_delta_on_the_same_obs():
    batches = _batches()
    row = _build(batches, None).rows[0]
    expected, _ = stats.paired_delta(_obs(batches, "cc", REF), _obs(batches, "cc", TREAT), (REF, TREAT),
                                     stats.Params(), "lean|cc")
    assert (row.combo, row.harness, row.model) == ("cc", "claude_code", "claude-opus-5-5")
    assert (row.effect, row.lo, row.hi) == (expected.point, expected.lo, expected.hi)
    assert row.effect == Decimal("0.6") and row.lo > 0
    assert (row.pairs, row.planned_pairs, row.excluded) == (20, 20, ())
    assert row.statement == "pack-on higher by 0.60"


def test_a_lower_and_a_null_effect_read_by_the_one_definition():
    lower = _build(_batches(value=lambda combo, task, arm, b: 0 if arm == TREAT and task in TASKS[:6] else 1),
                       None).rows[0]
    assert lower.statement == "pack-on lower by 0.60"
    null = _build(_batches(value=lambda combo, task, arm, b: 1 if task in TASKS[:5] else 0), None).rows[0]
    assert stats.no_detectable_effect(stats.Interval(null.effect, null.lo, null.hi, 10, None)) is True
    assert null.statement == "no detectable effect"


def test_a_short_harness_shows_k_of_20_and_the_excluded_cells_with_causes():
    def change(batch, cell):
        if batch == 2 and cell.task == "RS1" and cell.arm == TREAT:
            return dataclasses.replace(cell, outcome="failed", cause="rate limit")
        if batch == 1 and cell.task == "NG1" and cell.arm == REF:
            return dataclasses.replace(cell, scores={verdicts.PRIMARY: views.Measure(None, "no summary")})
        return cell

    row = _build(_batches(change=change), None).rows[0]
    assert (row.pairs, row.planned_pairs) == (18, 20)
    assert row.excluded == (
        (f"r1/cc-NG1-{REF}", "no summary"),
        (f"r1/cc-NG1-{TREAT}", f"pair partner not recorded (r1/cc-NG1-{REF})"),
        (f"r2/cc-RS1-{REF}", f"pair partner not recorded (r2/cc-RS1-{TREAT})"),
        (f"r2/cc-RS1-{TREAT}", "failed (rate limit)"),
    )


def test_zero_pairs_reads_not_recorded_never_zero():
    row = _build(_batches(value=lambda combo, task, arm, b: None if arm == TREAT else 0), None).rows[0]
    assert (row.pairs, row.effect, row.lo, row.hi) == (0, None, None, None)
    assert row.statement == "not recorded (0 pairs)"


def test_the_per_harness_mde_is_derived_from_the_planned_pairs():
    assert _build(_batches(2), None).rows[0].mde == Decimal("0.31")
    one = _build(_batches(1), None).rows[0]
    assert (one.planned_pairs, one.mde) == (10, Decimal("0.42"))


def test_rows_are_one_per_combo_in_plan_order():
    rows = _build(_batches(combos=("cx", "cc")), None).rows
    assert [(r.combo, r.harness, r.model) for r in rows] == [("cx", "codex", "gpt-6.1-sol"),
                                                             ("cc", "claude_code", "claude-opus-5-5")]


def test_one_pair_per_task_with_differing_tasks_has_a_nonzero_effect_interval():  # REUSE-A's control
    row = _build(_batches(1, value=lambda combo, task, arm, b: 1 if arm == TREAT and task in TASKS[:4] else 0),
                     None).rows[0]
    assert row.pairs == 10 and row.lo < row.hi


@pytest.mark.parametrize("tag", ["pilot", None])
def test_a_view_whose_ring_is_not_lean_is_refused(tag):
    assert "lean" in _refused(_batches(tag=tag)).message


def test_three_batches_are_refused():
    assert "one or two batches" in _refused(_batches(3)).message


def test_build_is_pure():
    assert repr(_build(_batches(), None)) == repr(_build(_batches(), None))


# ------------------------------------------------------------------ A4: the pooled row, disagree, PropertyRows

ALL = ("cc", "cx", "cp")


def test_the_pooled_row_is_paired_delta_over_every_harness_with_combo_task_keys():
    batches = _batches(combos=ALL)
    pooled = _build(batches, None).pooled
    key = lambda c: f"{c.combo}/{c.task}"
    ref = [o for combo in ALL for o in _obs(batches, combo, REF, key)]
    treat = [o for combo in ALL for o in _obs(batches, combo, TREAT, key)]
    expected, _ = stats.paired_delta(ref, treat, (REF, TREAT), stats.Params(), "lean|pooled")
    assert expected.n == 30
    assert (pooled.effect, pooled.lo, pooled.hi) == (expected.point, expected.lo, expected.hi)
    assert (pooled.combo, pooled.pairs, pooled.planned_pairs, pooled.mde) == ("pooled", 60, 60, Decimal("0.19"))
    assert pooled.statement == "pack-on higher by 0.60"


def test_the_pooled_mde_at_one_batch_and_its_excluded_cells():
    def change(batch, cell):
        return dataclasses.replace(cell, outcome="failed", cause="auth") if cell.cell_id == f"cx-S1-{TREAT}" else cell

    pooled = _build(_batches(1, combos=ALL, change=change), None).pooled
    assert (pooled.pairs, pooled.planned_pairs, pooled.mde) == (29, 30, Decimal("0.26"))
    assert pooled.excluded == ((f"r1/cx-S1-{REF}", f"pair partner not recorded (r1/cx-S1-{TREAT})"),
                               (f"r1/cx-S1-{TREAT}", "failed (auth)"))


def test_harnesses_disagree_only_when_two_intervals_lie_wholly_on_opposite_sides_of_zero():
    def split(combo, task, arm, batch):  # cc up, cx down, cp null
        passed = arm == TREAT if combo == "cc" else arm == REF if combo == "cx" else False
        return 1 if passed and task in TASKS[:6] else 0

    summary = _build(_batches(combos=ALL, value=split), None)
    assert [r.lo > 0 for r in summary.rows] == [True, False, False] and summary.rows[1].hi < 0
    assert summary.disagree is True
    same_side = _build(_batches(combos=ALL), None)
    assert same_side.disagree is False
    one_side = _build(_batches(combos=ALL, value=lambda combo, task, arm, b: split(combo, task, arm, b)
                               if combo != "cx" else 0), None)
    assert one_side.disagree is False


def test_property_rows_count_passes_over_recorded_pairs_per_family_and_harness():
    def value(combo, task, arm, batch):
        if task.startswith("NG"):
            return 1 if arm == REF else 0  # down
        if task.startswith("SM"):
            return 1  # same, both pass
        return _lift(combo, task, arm, batch)  # S, RS, RW up

    def change(batch, cell):  # one RW pair lost: its family reads 3 recorded
        return dataclasses.replace(cell, outcome="failed", cause="auth") if batch == 2 and cell.cell_id == f"cc-RW2-{REF}" else cell

    rows = _build(_batches(value=value, change=change), None).properties
    assert [(r.family, r.harness, r.off, r.on, r.direction) for r in rows] == [
        ("S", "claude_code", (0, 4), (4, 4), "up"),
        ("RS", "claude_code", (0, 4), (4, 4), "up"),
        ("RW", "claude_code", (0, 3), (3, 3), "up"),
        ("NG", "claude_code", (4, 4), (0, 4), "down"),
        ("SM", "claude_code", (4, 4), (4, 4), "same"),
    ]


def test_property_rows_are_family_major_over_harnesses():
    rows = _build(_batches(combos=("cc", "cx")), None).properties
    assert [(r.family, r.harness) for r in rows][:4] == [("S", "claude_code"), ("S", "codex"),
                                                          ("RS", "claude_code"), ("RS", "codex")]
    assert len(rows) == 10


# ------------------------------------------------------------------ A5: token ratio, checkpoints, pre-registration


def _priced(batch, cell):
    """Tokens that differ by task: pack-off 100 + 10 i, pack-on 100 + 30 i (i = the task's index)."""
    i = TASKS.index(cell.task)
    return dataclasses.replace(cell, tokens={"m": {"output": 100 + (30 if cell.arm == TREAT else 10) * i}})


def _token_obs(batches: list, combo: str, arm: str, keep=lambda b, task: True, task=lambda c: c.task) -> list:
    return [stats.Obs(task(c), index, Decimal(views.sum_tokens(c.tokens)))
            for index, b in enumerate(batches, 1) for c in b.view.cells
            if c.combo == combo and c.arm == arm and keep(index, c.task)]


def test_the_token_ratio_is_paired_ratio_over_token_complete_pairs():
    batches = _batches(change=_priced)
    row = _build(batches, None).rows[0]
    expected = stats.paired_ratio(_token_obs(batches, "cc", REF), _token_obs(batches, "cc", TREAT), (REF, TREAT),
                                  stats.Params(), "lean|cc|tokens")
    assert row.token_ratio == expected and row.ratio_excluded == 0
    assert row.token_ratio.point == Decimal(sum(100 + 30 * i for i in range(10))) / Decimal(sum(100 + 10 * i for i in range(10)))
    assert row.token_ratio.lo < row.token_ratio.hi


def test_pairs_without_tokens_or_with_zero_pack_off_tokens_are_excluded_and_counted():
    def change(batch, cell):
        cell = _priced(batch, cell)
        if batch == 1 and cell.task == "S2" and cell.arm == TREAT:
            return dataclasses.replace(cell, tokens=None)  # not recorded: never 0
        if batch == 2 and cell.task == "RW1" and cell.arm == REF:
            return dataclasses.replace(cell, tokens={"m": {"output": 0}})
        return cell

    batches = _batches(change=change)
    row = _build(batches, None).rows[0]
    lost = {(1, "S2"), (2, "RW1")}
    keep = lambda b, task: (b, task) not in lost
    expected = stats.paired_ratio(_token_obs(batches, "cc", REF, keep), _token_obs(batches, "cc", TREAT, keep),
                                  (REF, TREAT), stats.Params(), "lean|cc|tokens")
    assert (row.pairs, row.ratio_excluded) == (20, 2)
    assert row.token_ratio == expected


def test_no_token_complete_pair_reads_not_recorded():
    row = _build(_batches(change=lambda b, c: dataclasses.replace(c, tokens=None)), None).rows[0]
    assert (row.token_ratio, row.ratio_excluded) == (None, 20)


def test_the_pooled_token_ratio_and_its_nonzero_width_at_one_pair_per_task():  # REUSE-A's control
    batches = _batches(1, combos=ALL, change=_priced)
    pooled = _build(batches, None).pooled
    key = lambda c: f"{c.combo}/{c.task}"
    ref = [o for combo in ALL for o in _token_obs(batches, combo, REF, task=key)]
    treat = [o for combo in ALL for o in _token_obs(batches, combo, TREAT, task=key)]
    assert pooled.token_ratio == stats.paired_ratio(ref, treat, (REF, TREAT), stats.Params(), "lean|pooled|tokens")
    assert pooled.token_ratio.lo < pooled.token_ratio.hi
    one = _build(batches, None).rows[0]
    assert one.pairs == 10 and one.token_ratio.lo < one.token_ratio.hi


def test_a_checkpoint_reports_measured_minutes_and_tokens_per_cell():
    def change(batch, cell):
        cell = _priced(batch, cell)
        if cell.task in ("S1", "S2", "RS1") and cell.arm == TREAT or cell.cell_id == f"cc-RS2-{TREAT}":
            return dataclasses.replace(cell, outcome="failed", cause="failed (provider)", code="HB-CELL-108")
        if cell.cell_id == f"cc-RW1-{TREAT}":
            return dataclasses.replace(cell, outcome="failed", cause="blocked (auth)", code="HB-CELL-202")
        if cell.cell_id == f"cc-NG1-{TREAT}":
            return dataclasses.replace(cell, outcome="timed_out", cause="timed_out", code="HB-CELL-301")  # the agent's
        return cell

    first, second = _batches(change=change)
    first = dataclasses.replace(first, run_wall_ns=20 * 90 * 10**9, grading_ns=10 * 60 * 10**9, cells_graded=20)
    checkpoint = _build([first, second], None).checkpoint
    assert [c.run_id for c in checkpoint] == ["r1", "r2"]
    one = checkpoint[0]
    assert (one.cells, one.run_min_per_cell, one.grade_min_per_cell) == (20, Decimal("1.5"), Decimal("0.5"))
    assert dict(one.tokens_per_cell) == {("cc", REF): Decimal(145), ("cc", TREAT): Decimal(235)}
    assert dict(one.infra_failures) == {"cc": (5, 20, ("blocked (auth)", "failed (provider)"))}
    k, n, _ = one.infra_failures["cc"]
    assert Decimal(k) / n > Decimal("0.2")  # LB-3: over 20% is named, with its causes
    # LB-3's projections are computable from the fields alone: batch 2's run time and its tokens.
    assert one.run_min_per_cell * len(second.view.plan["cells"]) / 60 == Decimal("0.5")  # hours
    assert sum(one.tokens_per_cell.values()) * 10 == Decimal(3800)


def _single(checkpoint: tuple) -> tuple:
    assert len(checkpoint) == 1, f"one batch gives one checkpoint, got {checkpoint!r}"
    return checkpoint


def test_a_checkpoint_value_not_recorded_is_none_never_zero():
    batch = dataclasses.replace(_batches(1)[0], run_wall_ns=None, grading_ns=600, cells_graded=0)
    (one,) = _single(_build([batch], None).checkpoint)
    assert (one.run_min_per_cell, one.grade_min_per_cell) == (None, None)
    (no_tokens,) = _single(_build(_batches(1, change=lambda b, c: dataclasses.replace(c, tokens=None)), None).checkpoint)
    assert dict(no_tokens.tokens_per_cell) == {("cc", REF): None, ("cc", TREAT): None}
    assert dict(no_tokens.infra_failures) == {"cc": (0, 20, ())}


T = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
SHA = "ab" * 32


def _timed(started_1: datetime | None, started_2: datetime | None = None) -> list:
    first, second = _batches()
    return [dataclasses.replace(first, first_cell_started_at=started_1),
            dataclasses.replace(second, first_cell_started_at=started_2)]


def test_a_pre_registration_committed_before_batch_ones_first_cell_counts_and_seeds_the_rows():
    batches = _timed(T, T - timedelta(days=1))  # batch 2's start is not the one compared
    summary = _build(batches, lean.Prereg(SHA, T - timedelta(seconds=1)))
    assert summary.prereg_status == f"pre-registered ({SHA[:12]})"
    seeded = stats.Params(seed=verdicts.seed_for(SHA, "lean", "cc", (REF, TREAT)))
    expected, _ = stats.paired_delta(_obs(batches, "cc", REF), _obs(batches, "cc", TREAT), (REF, TREAT), seeded, "lean|cc")
    row = summary.rows[0]
    assert (row.effect, row.lo, row.hi) == (expected.point, expected.lo, expected.hi)
    pooled_seed = verdicts.seed_for(SHA, "lean", "pooled", (REF, TREAT))
    key = lambda c: f"{c.combo}/{c.task}"
    pooled, _ = stats.paired_delta(_obs(batches, "cc", REF, key), _obs(batches, "cc", TREAT, key), (REF, TREAT),
                                   stats.Params(seed=pooled_seed), "lean|pooled")
    assert (summary.pooled.lo, summary.pooled.hi) == (pooled.lo, pooled.hi)


@pytest.mark.parametrize("committed", [T, T + timedelta(seconds=1)])
def test_a_pre_registration_committed_at_or_after_batch_ones_first_cell_is_not_pre_registered(committed):
    status = _build(_timed(T, T + timedelta(days=1)), lean.Prereg(SHA, committed)).prereg_status
    assert status.startswith("Not pre-registered: committed ")
    assert "after batch 1's first cell started" in status


@pytest.mark.parametrize(("prereg", "started", "reason"), [
    (None, T, "Not pre-registered: no pre-registration supplied"),
    (lean.Prereg(SHA, None), T, "Not pre-registered: the pre-registration is not committed"),
    (lean.Prereg(SHA, T - timedelta(days=1)), None, "Not pre-registered: batch 1's first cell start is not recorded"),
])
def test_a_missing_side_of_the_timing_is_not_pre_registered(prereg, started, reason):
    summary = _build(_timed(started), prereg)
    assert summary.prereg_status == reason
    if prereg is None:  # stats' default seed
        expected, _ = stats.paired_delta(_obs(_timed(started), "cc", REF), _obs(_timed(started), "cc", TREAT),
                                         (REF, TREAT), stats.Params(), "lean|cc")
        assert (summary.rows[0].lo, summary.rows[0].hi) == (expected.lo, expected.hi)
