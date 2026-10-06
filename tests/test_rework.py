"""Tests for grade/rework.py: measure, ratio, grade, and variant reading / turns discrimination (W1-L §6.1, W0 rev 6.6 §13)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from clean_parent import CLEAN_PARENT

from harness_bench import (
    archive,
    config,
    discriminate,
    plan,
    readiness,
    views,
    workspace,
)
from harness_bench.errors import BenchError
from harness_bench.grade import CellInput, rework
from harness_bench.grade import property as prop
from harness_bench.grade.property import GradeContext
from harness_bench.synthetic_agent import SYNTHETIC_VERSION


def test_rework_ratio_counts_replaced_and_deleted_not_added(tmp_path: Path):
    base = {"pkg/mod.py": "a = 1\n"}
    snap = {"pkg/mod.py": "a = 1\nb = 2\nc = 3\n"}
    final = {"pkg/mod.py": "a = 1\nb = 20\nd = 4\n"}
    radius = ["pkg/*.py"]

    t1, changed = rework.measure(base, snap, final, radius)
    assert t1 == 2
    assert changed == 2
    assert rework.ratio(t1, changed) == Decimal("1.0000")


def test_rework_ratio_ceiling_boundary():
    # Ceiling is 0.3000
    # Exactly at ceiling: 30 / 100 == 0.3000 -> passes ceiling boundary
    r_pass = rework.ratio(100, 30)
    assert r_pass == Decimal("0.3000")
    assert r_pass <= Decimal("0.3000")

    # Above ceiling: 31 / 100 == 0.3100 -> fails ceiling boundary
    r_fail = rework.ratio(100, 31)
    assert r_fail == Decimal("0.3100")
    assert r_fail > Decimal("0.3000")


def test_rework_turn2_not_reached_is_na_and_primary_zero(tmp_path: Path):
    cid = "c1"
    inp = CellInput(
        run_dir=tmp_path / "run",
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": 30.0}, "tasks": {"RW1": {"turns": [{"n": 2, "prompt": "turn2"}]}}},
        cell={"cell_id": cid, "task": "RW1"},
        task={"property": {"name": "rework", "ceilings": {"rework_ratio": "0.3000"}}},
        task_dir=tmp_path / "tasks" / "RW1",
        archive=tmp_path / "run" / "archive" / cid / "attempt-1",
        out_dir=tmp_path / "run" / "grading" / cid / "rework",
        events=(
            {"kind": "cell.turn_ended", "cell_id": cid, "turn": 1, "next": "stop"},
        ),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={"rework_ratio": {}, "property_check_pass": {}, "turn1_tests_pass": {}},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )
    inp.out_dir.mkdir(parents=True, exist_ok=True)
    ctx = GradeContext(30.0)
    scores = rework.grade(inp, ctx)

    assert scores["rework_ratio"].value is None
    assert scores["rework_ratio"].reason == "turn 2 not reached"
    assert scores["property_check_pass"].value == 0
    assert scores["property_check_pass"].reason is None


def test_rework_grade_cell_uses_registered_strategy(tmp_path: Path):
    assert prop.STRATEGIES.get("rework") is rework.grade

    cid = "c2"
    inp = CellInput(
        run_dir=tmp_path / "run",
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": 30.0}, "tasks": {"RW1": {"turns": []}}},
        cell={"cell_id": cid, "task": "RW1"},
        task={"property": {"name": "rework"}},
        task_dir=tmp_path / "tasks" / "RW1",
        archive=tmp_path / "run" / "archive" / cid / "attempt-1",
        out_dir=tmp_path / "run" / "grading" / cid / "property",
        events=(),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={"rework_ratio": {}, "property_check_pass": {}},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )
    inp.out_dir.mkdir(parents=True, exist_ok=True)
    scores = prop.grade_cell(inp)
    assert scores["property_check_pass"].value == 0 or scores["property_check_pass"].value == 1


def _make_task_with_variant(tmp_path: Path, task_id: str, variant_dict: dict, task_yaml_dict: dict | None = None, ref_files: dict[str, str] | None = None) -> Path:
    task_dir = tmp_path / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    y = task_yaml_dict or {"schema": "bench-task/1", "id": task_id}
    (task_dir / "task.yaml").write_text(yaml.safe_dump(y), encoding="utf-8")
    ref_dir = task_dir / "oracle" / "solutions" / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for p, content in (ref_files or {}).items():
        fp = ref_dir / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    variants_file = task_dir / "oracle" / "variants.py"
    variants_file.parent.mkdir(parents=True, exist_ok=True)
    variants_file.write_text(f"VARIANTS = {variant_dict!r}\n", encoding="utf-8")
    return task_dir


def test_variant_reader_create_form_accepted(tmp_path: Path):
    variant_dict = {
        "newfile": {
            "flips": ["property_check_pass"],
            "clauses": {"property_check_pass": "scope"},
            "edits": [{"file": "pkg/new_file.py", "old": "", "new": "x = 1\n"}],
        }
    }
    _make_task_with_variant(tmp_path, "T1", variant_dict, ref_files={"pkg/existing.py": "a = 1\n"})
    try:
        res = readiness.variants(tmp_path, "T1")
        err = None
    except BenchError as exc:
        err = exc
    assert err is None, f"expected create form to be accepted, got: {err}"
    assert "newfile" in res


def test_variant_reader_create_form_refused_when_file_exists(tmp_path: Path):
    variant_dict = {
        "badcreate": {
            "flips": ["property_check_pass"],
            "clauses": {"property_check_pass": "scope"},
            "edits": [{"file": "pkg/existing.py", "old": "", "new": "x = 1\n"}],
        }
    }
    _make_task_with_variant(tmp_path, "T2", variant_dict, ref_files={"pkg/existing.py": "a = 1\n"})
    with pytest.raises(BenchError) as exc_info:
        readiness.variants(tmp_path, "T2")
    assert "create edit cannot replace file already in reference overlay" in str(exc_info.value)


def test_variant_reader_turn_prefix_accepted_for_turns_task(tmp_path: Path):
    variant_dict = {
        "turnvariant": {
            "flips": ["property_check_pass"],
            "clauses": {"property_check_pass": "tests"},
            "edits": [{"file": "turn-2/pkg/mod.py", "old": "x = 1\n", "new": "x = 2\n"}],
        }
    }
    _make_task_with_variant(
        tmp_path,
        "T3",
        variant_dict,
        task_yaml_dict={"schema": "bench-task/1", "id": "T3", "turns": ["turns/2.md"]},
        ref_files={"turn-2/pkg/mod.py": "x = 1\n"},
    )
    try:
        res = readiness.variants(tmp_path, "T3")
        err = None
    except BenchError as exc:
        err = exc
    assert err is None, f"expected turn prefix to be accepted for turns task, got: {err}"
    assert "turnvariant" in res


def test_variant_reader_turn_prefix_refused_when_missing_for_turns_task(tmp_path: Path):
    variant_dict = {
        "noprefix": {
            "flips": ["property_check_pass"],
            "clauses": {"property_check_pass": "tests"},
            "edits": [{"file": "pkg/mod.py", "old": "x = 1\n", "new": "x = 2\n"}],
        }
    }
    _make_task_with_variant(
        tmp_path,
        "T4",
        variant_dict,
        task_yaml_dict={"schema": "bench-task/1", "id": "T4", "turns": ["turns/2.md"]},
        ref_files={"pkg/mod.py": "x = 1\n"},
    )
    with pytest.raises(BenchError) as exc_info:
        readiness.variants(tmp_path, "T4")
    assert "must start with turn-<n>/" in str(exc_info.value)


def test_discriminate_admits_turns_task(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "tasks" / "TURNS"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_yaml = {"schema": "bench-task/1", "id": "TURNS", "turns": ["turns/2.md"]}
    (task_dir / "task.yaml").write_text(yaml.safe_dump(task_yaml), encoding="utf-8")

    try:
        lock = MagicMock()
        discriminate._trial(tmp_path, "TURNS", tmp_path / "runs", tmp_path / "cells", tmp_path / "upstream", lock)
        e1_raised = False
    except BenchError as exc:
        e1_raised = "not built in E1" in str(exc)
    except Exception:  # noqa: BLE001 - any other failure means the E1 refusal is not what stopped the trial
        e1_raised = False

    assert not e1_raised, "discriminate still refused a task with turns (HB-RDY-005: not built in E1)"


def test_rework_task_without_turns_stays_not_built(tmp_path: Path):
    """A task that declares no turns (the E1 single-turn stand-in) keeps the E1 NA, so discriminate's DISC-C fixture holds."""
    cid = "c3"
    inp = CellInput(
        run_dir=tmp_path / "run",
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": 30.0}, "tasks": {"RW0": {}}},
        cell={"cell_id": cid, "task": "RW0"},
        task={"property": {"name": "rework"}},
        task_dir=tmp_path / "tasks" / "RW0",
        archive=tmp_path / "run" / "archive" / cid / "attempt-1",
        out_dir=tmp_path / "run" / "grading" / cid / "rework",
        events=(),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={"rework_ratio": {}, "property_check_pass": {}, "turn1_tests_pass": {}},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )
    scores = rework.grade(inp, GradeContext(30.0))
    assert {k: (s.value, s.reason) for k, s in scores.items()} == dict.fromkeys(inp.metrics, (None, "not built"))


def test_every_na_reason_rework_grade_emits_on_a_turns_task_is_in_na_reasons(tmp_path: Path):
    """K1 control for the two literals in discriminate.NA_REASONS: a turns task whose turn 2 is not reached and whose
    turn-1 snapshot is absent emits both reasons, and a record holding them must not be HB-RDY-011."""
    cid = "c1"
    inp = CellInput(
        run_dir=tmp_path / "run",
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": 30.0}, "tasks": {"RW1": {"turns": [{"n": 2, "prompt": "turn2"}]}}},
        cell={"cell_id": cid, "task": "RW1"},
        task={"property": {"name": "rework"}},
        task_dir=tmp_path / "tasks" / "RW1",
        archive=tmp_path / "run" / "archive" / cid / "attempt-1",
        out_dir=tmp_path / "run" / "grading" / cid / "rework",
        events=({"kind": "cell.turn_ended", "cell_id": cid, "turn": 1, "next": "stop"},),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={"rework_ratio": {}, "property_check_pass": {}, "turn1_tests_pass": {}},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )
    inp.out_dir.mkdir(parents=True, exist_ok=True)
    reasons = {s.reason for s in rework.grade(inp, GradeContext(30.0)).values() if s.reason}
    assert reasons == {"turn 2 not reached", "turn 1 snapshot not archived"}
    assert reasons <= discriminate.NA_REASONS


_spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)  # type: ignore[union-attr]
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="the grader and its host are Windows-only (ADR-0018 s8)")
TURNS_TASK = "DISC-T"


class TurnsRun:
    """One real engine run of the two-turn fixture task: reference and naive complete both turns; `stopped` applies the
    reference's turn 1 and then has its turn-2 overlay refused (a Windows device name), so its turn 2 is not reached."""


@pytest.fixture(scope="module")
def turns_run():
    base = CLEAN_PARENT / uuid.uuid4().hex  # cells cannot be built under the operator's profile (HB-PRE-002)
    base.mkdir(parents=True)
    graded_on: list[Path] = []
    real = rework._run_turn1_hidden_tests

    def spy(inp, snap_ws):
        graded_on.append(snap_ws)
        return real(inp, snap_ws)

    try:
        root = mt.make_root(base)
        task_dir = mt.install(root, "disc_turns")
        overlays = discriminate._overlays(task_dir)
        stopped = base / "stopped"
        shutil.copytree(task_dir / "oracle" / "solutions" / "reference", stopped)
        (stopped / "turn-2" / "CON").write_text("refused by the overlay path rule\n", encoding="utf-8")
        overlays["synthetic-stopped"] = ("stopped", stopped)
        run_id = "disc-dt-j2c"
        p = plan.build_plan(root, discriminate._matrix(run_id, TURNS_TASK, list(overlays)), config.load_yaml(root / "bench" / "bom.yaml"),
                            run_id, {"synthetic": {"version": SYNTHETIC_VERSION}}, parallelism=1, kind="discrimination")
        run_dir = base / "runs" / run_id
        plan.confirm(run_dir, p)
        cells = base / "cells"
        cells.mkdir()
        workspace.check_cells_root(cells)
        with patch.object(rework, "_run_turn1_hidden_tests", spy):
            summary = discriminate._run_engine(root, task_dir, run_dir, p, discriminate._Clock(), overlays, cells, root / ".tools" / "upstream")
        run = TurnsRun()
        run.p, run.run_dir, run.summary, run.graded_on = p, run_dir, summary, graded_on
        run.roles = {c["cell_id"]: overlays[c["combo"]][0] for c in p["cells"]}
        run.events = list(views.rows(run_dir, "events"))
        yield run
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def _cell_of(run: TurnsRun, role: str) -> str:
    return next(cid for cid, r in run.roles.items() if r == role)


@windows_only
def test_turn1_snapshot_through_engine(turns_run):
    run = turns_run
    cid = _cell_of(run, "reference")
    archived = [e for e in run.events if e["kind"] == "cell.turn_snapshot_archived" and e["cell_id"] == cid]
    assert [e["turn"] for e in archived] == [1]
    snap_ws = archive.snapshot_folder(run.run_dir, cid, 1) / "ws"
    assert (snap_ws / "app.py").read_text(encoding="utf-8") == mt.TURN1_REF  # turn 1's tree, not the final one
    assert snap_ws in run.graded_on  # the graded copy is the archived snapshot, reached through grade/runner.py
    scores = {r["metric_id"]: r["value"] for r in views.rows(run.run_dir, "scores") if r["cell_id"] == cid}
    assert scores["turn1_tests_pass"] == 1


@windows_only
def test_multi_turn_discrimination_through_engine(turns_run):
    run = turns_run
    (grading_id,) = views.completed_passes(run.run_dir)
    scores, _ = readiness.run_scores(run.run_dir, grading_id, run.roles, set(mt.TURNS_EXPECTED["reference"]))
    planned = len(run.p["tasks"][TURNS_TASK]["turns"]) + 1  # derived by counting, never stored
    reached = {role: sum(1 for e in run.events if e["kind"] == "cell.turn_ended" and e["cell_id"] == cid)
               for cid, role in run.roles.items()}
    assert reached == {"reference": planned, "naive": planned, "stopped": 1}
    expected = dict(mt.TURNS_EXPECTED)
    expected["stopped"] = {"property_check_pass": 0, "turn1_tests_pass": 1, "rework_ratio": {"na": "turn 2 not reached"}}
    assert scores == expected
    assert discriminate._untrustworthy(scores, {}) == []  # K1: the not-reached NA is inside the closed set


@windows_only
def test_discriminate_writes_the_two_turn_record_matching_its_declared_expected():
    base = CLEAN_PARENT / uuid.uuid4().hex
    base.mkdir(parents=True)
    try:
        root = mt.make_root(base)
        mt.install(root, "disc_turns")
        result = discriminate.run(root, TURNS_TASK, runs=base / "runs", cells_root=base / "cells")
        assert result.outcome == "written", result
        record = json.loads(result.record_path.read_text(encoding="utf-8"))
        declared = record["expected"]
        assert declared == mt.TURNS_EXPECTED
        assert {r: {m: record["scores"][r][m] for m in declared[r]} for r in declared} == declared
        assert record["readiness_failures"] == []
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def _evidence_inp(tmp_path: Path, n_turns_ended: int) -> CellInput:
    cid = "c1"
    ended = tuple({"kind": "cell.turn_ended", "cell_id": cid, "turn": n, "next": "stop"} for n in range(1, n_turns_ended + 1))
    inp = CellInput(
        run_dir=tmp_path / "run",
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": 30.0}, "tasks": {"RW1": {"turns": [{"n": 2, "prompt": "turn2"}]}}},
        cell={"cell_id": cid, "task": "RW1"},
        task={"property": {"name": "rework", "ceilings": {"rework_ratio": "0.3000"}}},
        task_dir=tmp_path / "tasks" / "RW1",
        archive=tmp_path / "run" / "archive" / cid / "attempt-1",
        out_dir=tmp_path / "run" / "grading" / cid / "property",
        events=ended,
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={"rework_ratio": {}, "property_check_pass": {}, "turn1_tests_pass": {}, "not_a_rework_score": {}},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )
    inp.out_dir.mkdir(parents=True, exist_ok=True)
    return inp


def _assert_every_score_points_at_the_section(inp: CellInput, scores) -> None:
    pointer = (inp.out_dir / "property.json").relative_to(inp.run_dir).as_posix()
    assert (inp.out_dir / "property.json").is_file()
    assert set(scores) == set(inp.metrics)
    assert {k: v.evidence for k, v in scores.items()} == dict.fromkeys(inp.metrics, pointer)


def test_rework_ratio_branch_scores_carry_the_section_pointer(tmp_path: Path):
    inp = _evidence_inp(tmp_path, 2)
    _assert_every_score_points_at_the_section(inp, rework.grade(inp, GradeContext(30.0)))


def test_rework_turn2_not_reached_scores_carry_the_section_pointer(tmp_path: Path):
    inp = _evidence_inp(tmp_path, 1)
    _assert_every_score_points_at_the_section(inp, rework.grade(inp, GradeContext(30.0)))
