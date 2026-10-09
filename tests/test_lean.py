"""L-SUM-A: the lean summary (ADR-0023) and the numeric views helpers its CLI feeds it.

The helpers are red first on hand-built ledgers: each value is a difference of recorded `mono_ns` readings (or the
earliest recorded instant), and a missing reading is None ("not recorded"), never 0.
"""

from datetime import UTC, datetime
from pathlib import Path

from harness_bench import (
    egress,  # noqa: F401  (first: egress and report.html import each other)
    ledger,
    views,
)
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
