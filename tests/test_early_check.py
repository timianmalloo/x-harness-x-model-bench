"""`bench status <run> --check-ended`: the early validity check over the ended cells of a live run.

It reads each archived cell's native record as the grading pass does (`runner.read_record`) and judges it with the view's
own rules (`views._cell_view`), in memory, so it agrees with the end-of-run grading and writes nothing.
"""

import hashlib
import json
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run
from test_views import _edit_plan

from harness_bench import cli, early_check, views
from harness_bench.grade import runner

COMBOS = {"a": "ca", "b": "cb"}


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _live_run(root: Path, tmp_path: Path) -> Path:
    """Two ended, archived cells and one cell not yet started; no run.completed and no grading pass (a live run)."""
    return make_run(root, tmp_path, {"a": GOOD, "b": GOOD}, combos=COMBOS, unstarted=("c",))


def _mismatch_b(run_dir: Path, key: str = "model", value: str = "gpt-not-the-pin") -> None:
    """Re-pin cell b so its record (gpt-6-sol, effort medium) no longer serves the pin."""
    _edit_plan(run_dir, lambda p: {**p, "cells": [{**c, key: value} if c["cell_id"] == "b" else c for c in p["cells"]]})


def _tree(run_dir: Path) -> dict[str, str]:
    return {p.relative_to(run_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(run_dir.rglob("*")) if p.is_file()}


def _graded_codes(run_dir: Path, root: Path) -> dict[str, str | None]:
    runner.run_pass(run_dir, root)
    return {c.cell_id: c.validity_code for c in views.load(run_dir).cells if c.outcome != "not started"}


def test_ended_cells_pass_and_the_check_writes_nothing(root, tmp_path):
    run_dir = _live_run(root, tmp_path)
    before = _tree(run_dir)
    result = early_check.check(run_dir)
    assert _tree(run_dir) == before
    assert (result.planned, [c.cell_id for c in result.cells]) == (3, ["a", "b"])
    assert [(c.label, c.validity, c.code) for c in result.cells] == [
        ("X1.ca.pack-off.r1", "valid", None), ("X1.cb.pack-off.r1", "valid", None)]
    assert result.mismatch is False
    assert {c.cell_id: c.code for c in result.cells} == _graded_codes(run_dir, root)


@pytest.mark.parametrize(("key", "value", "validity", "code"), [
    ("model", "gpt-not-the-pin", "invalid (model mismatch)", "HB-VAL-002"),
    ("effort", "high", "invalid (setting mismatch)", "HB-VAL-010"),
])
def test_a_cell_not_serving_its_pin_is_provisionally_invalid_as_grading_finds(root, tmp_path, key, value, validity, code):
    run_dir = _live_run(root, tmp_path)
    _mismatch_b(run_dir, key, value)
    result = early_check.check(run_dir)
    assert [(c.cell_id, c.validity, c.code) for c in result.cells] == [("a", "valid", None), ("b", validity, code)]
    assert result.mismatch is True and result.totals == {code: 1, "ok": 1}
    assert {c.cell_id: c.code for c in result.cells} == _graded_codes(run_dir, root)


def _status(tmp_path: Path, root: Path, *extra: str) -> int:
    return cli.main(["--root", str(root), "--runs", str(tmp_path / "runs"), "status", "r1", "--check-ended", *extra])


def test_the_cli_prints_one_line_per_ended_cell_and_exits_0_when_all_pass(root, tmp_path, capsys):
    _live_run(root, tmp_path)
    assert _status(tmp_path, root) == cli.OK
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["X1.ca.pack-off.r1: ok", "X1.cb.pack-off.r1: ok"]
    assert out[-1] == "ended 2 of 3 cells: ok 2"


def test_the_cli_exits_with_its_own_code_on_a_provisional_mismatch(root, tmp_path, capsys):
    _mismatch_b(_live_run(root, tmp_path))
    assert _status(tmp_path, root) == cli.EARLY_MISMATCH
    out = capsys.readouterr().out.splitlines()
    assert out[1] == "X1.cb.pack-off.r1: HB-VAL-002 invalid (model mismatch)"
    assert out[-1] == "ended 2 of 3 cells: ok 1, HB-VAL-002 1"
    assert cli.EARLY_MISMATCH not in (cli.OK, cli.INVALID, cli.INCOMPLETE, cli.NOT_BUILT, cli.INTEGRITY, cli.ALARM)


def test_the_cli_json_carries_every_ended_cell_and_the_totals(root, tmp_path, capsys):
    _mismatch_b(_live_run(root, tmp_path))
    assert _status(tmp_path, root, "--json") == cli.EARLY_MISMATCH
    doc = json.loads(capsys.readouterr().out)
    assert doc["schema"] == early_check.SCHEMA and (doc["run_id"], doc["planned"], doc["ended"]) == ("r1", 3, 2)
    assert [(c["cell_id"], c["code"]) for c in doc["cells"]] == [("a", None), ("b", "HB-VAL-002")]
    assert (doc["totals"], doc["mismatch"]) == ({"HB-VAL-002": 1, "ok": 1}, True)
