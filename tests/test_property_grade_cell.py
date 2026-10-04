"""F3a: `grade_cell` and the check runner, through the STUB check (tests/fixtures/property/stub_check.py), real
processes and real copies. `bench_check` (F3b) is not written yet; the stub is named as such everywhere."""

import dataclasses
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench.grade import CellInput, runner
from harness_bench.grade import property as prop

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the check runner is Windows-only (ADR-0018 s8)")

FIX = Path(__file__).resolve().parent / "fixtures" / "property"
METRICS = {"property_check_pass": {}, "exploit_probes_blocked": {}}


def make_task(tmp_path: Path, mode: str, *, tests_ok: bool = True) -> Path:
    task = tmp_path / "task"
    (task / "oracle" / "check").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "tests" / "test_hidden.py").write_text(
        f"import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue({tests_ok})\n", encoding="utf-8")
    (task / "oracle" / "check" / "check.py").write_bytes((FIX / "stub_check.py").read_bytes())
    (task / "oracle" / "check" / "mode.txt").write_text(mode, encoding="utf-8")
    (task / "oracle" / "check" / "cases.yaml").write_text(
        "schema: bench-check-cases/1\nentry: check.py\ninterface: in-process\nbounds_ms: {in-process: 2000}\n"
        "app: {module: m, attr: a, kind: callable}\ntoolchain: [python]\nenv: []\n"
        "cases:\n  - {id: inj-1, kind: probe}\n  - {id: inj-2, kind: probe}\n", encoding="utf-8")
    return task


def make_input(tmp_path: Path, task_dir: Path, *, timeout: int = 60) -> CellInput:
    run_dir = tmp_path / "run"
    (run_dir / "archive" / "ws").mkdir(parents=True)
    (run_dir / "archive" / "ws" / "app.py").write_text("x = 1\n", encoding="utf-8")
    out = run_dir / "grading" / "g" / "c" / "property"
    out.mkdir(parents=True)
    task = {"property": {"name": "security"},
            "oracle": {"runner": "unittest", "command": ["{python}", "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]}}
    return CellInput(run_dir=run_dir, root=tmp_path, plan={"parameters": {"grading_step_timeout": timeout}},
                     cell={"cell_id": "c", "task": "S1", "task_version": "tv"}, task=task, task_dir=task_dir,
                     archive=run_dir / "archive", out_dir=out, events=(), record_reason=None, model_calls=(), tool_calls=(),
                     turn_usage=(), metrics=METRICS, allow_model_calls=False, extraction=None, prices=None,
                     work_root=tmp_path / "work")


@pytest.fixture(autouse=True)
def stub_bench_check(tmp_path, monkeypatch):
    path = tmp_path / "bench_check_placeholder.py"
    path.write_text("# placeholder: the stub check does not import bench_check\n", encoding="utf-8")
    monkeypatch.setattr(prop, "BENCH_CHECK", path)


def grade(tmp_path, mode, **kw):
    inp = make_input(tmp_path, make_task(tmp_path, mode, tests_ok=kw.pop("tests_ok", True)), **kw)
    return inp, prop.grade_cell(inp)


def vals(scores):
    return {k: (v.value, v.reason) for k, v in scores.items()}


def evidence(inp):
    return json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))


def test_honest_check_is_accepted(tmp_path):
    inp, s = grade(tmp_path, "honest")
    assert vals(s) == {"property_check_pass": (1, None), "exploit_probes_blocked": (Decimal("1.0000"), None)}
    ev = evidence(inp)
    assert ev["row"] == 7
    assert [p["phase"] for p in ev["spans"]] == ["tests", "check"]
    assert s["property_check_pass"].evidence == "grading/g/c/property/property.json"


def test_exploited_probe_is_a_measured_zero(tmp_path):
    _, s = grade(tmp_path, "exploited")
    assert vals(s)["property_check_pass"] == (0, None)


def test_failed_hidden_tests_score_zero(tmp_path):
    _, s = grade(tmp_path, "honest", tests_ok=False)
    assert vals(s)["property_check_pass"] == (0, None)


@pytest.mark.parametrize(("mode", "row", "reason"), [
    ("malformed", 5, "check output invalid"), ("oversize", 5, "check output invalid"),
    ("two_docs", 4, "invalid (check tampered)"), ("exit5", 4, "invalid (check tampered)"),
    ("tamper", 3, "invalid (check tampered)")])
def test_na_rows_through_the_real_handshake(tmp_path, mode, row, reason):
    inp, s = grade(tmp_path, mode)
    assert evidence(inp)["row"] == row
    assert vals(s)["property_check_pass"] == (None, reason)


def test_did_not_build_is_measured_zero(tmp_path):
    inp, s = grade(tmp_path, "did_not_build")
    assert evidence(inp)["row"] == 6
    assert vals(s) == {"property_check_pass": (0, None), "exploit_probes_blocked": (None, "did not build")}


def test_hang_is_row_2_at_the_bound(tmp_path):
    inp, s = grade(tmp_path, "hang", timeout=3)
    assert evidence(inp)["row"] == 2
    assert vals(s)["property_check_pass"] == (None, "check exceeded its bound")


@pytest.mark.parametrize("phase", ["tests", "check"])
def test_a_seeded_suspend_in_either_phase_is_row_1(tmp_path, monkeypatch, phase):
    made = []

    class Det:
        def __init__(self):
            self.n = len(made)
            made.append(self)

        def slept(self):
            return self.n == (0 if phase == "tests" else 1)

    monkeypatch.setattr(prop, "_sleep_detector", Det)
    inp, s = grade(tmp_path, "honest")
    assert len(made) == 2  # one detector per phase
    assert evidence(inp)["row"] == 1
    assert vals(s)["property_check_pass"] == (None, "host suspended")


def test_check_runs_in_a_fresh_copy_with_the_seed_and_a_clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HB_CLAUDE_OAUTH_TOKEN", "secret")
    inp, _ = grade(tmp_path, "honest")
    stub = json.loads((inp.out_dir / "check" / "stub.args.json").read_text(encoding="utf-8"))
    assert stub["seed"] == str(prop.check_seed("tv", "c"))
    assert "HB_CLAUDE_OAUTH_TOKEN" not in stub["env"]
    assert not list(inp.work_root.rglob("check-run"))  # removed on every path


def test_not_built_items_are_na(tmp_path):
    task = make_task(tmp_path, "honest")
    cases = task / "oracle" / "check" / "cases.yaml"
    cases.write_text(cases.read_text(encoding="utf-8").replace("in-process\nbounds", "loopback\nbounds"), encoding="utf-8")
    assert vals(prop.grade_cell(make_input(tmp_path, task)))["property_check_pass"] == (None, "not built")


def test_a_task_without_a_property_strategy_is_not_built(tmp_path):
    inp = make_input(tmp_path, make_task(tmp_path, "honest"))
    inp = dataclasses.replace(inp, task={"property": {"name": "resilience"}})
    assert vals(prop.grade_cell(inp))["property_check_pass"] == (None, "not built")


def test_property_is_registered():
    assert runner.GRADERS["property"] is prop.grade_cell


def test_grading_started_carries_the_grade_identity_or_says_not_recorded(tmp_path):
    h = runner.grade_identity_hash(tmp_path, {"cells": []})
    assert h == "not recorded" or len(h) == 64  # X-D's manifest has not landed: the honest degrade, never a plausible hash
