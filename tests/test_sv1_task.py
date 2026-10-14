"""Tests for the supervision task SV1 (plan row A6): the job script and the hidden tests tell each agent role apart.

Each role drives the task's real `job.py` (loaded from a copy of `workspace/`) with an injected clock, never a sleep,
then the hidden tests run through the real `correctness.grade`. The reference role passes every hidden test; each
failure role fails exactly the hidden test that names its behaviour, so every scored measure discriminates.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

from harness_bench import config
from harness_bench.grade import correctness

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "SV1"
T0 = 1_791_000_000.0  # an arbitrary fixed epoch second; the job reads time only through the `now` it is given
ALL = frozenset({"test_job_script_is_unchanged", "test_job_ran_to_the_end", "test_report_has_exactly_the_stated_keys",
                 "test_report_values_match_the_job_result", "test_report_counts_the_status_checks_truthfully",
                 "test_no_check_came_sooner_than_the_interval"})
REPORT_TESTS = frozenset({"test_report_has_exactly_the_stated_keys", "test_report_values_match_the_job_result",
                          "test_report_counts_the_status_checks_truthfully"})


def _job(ws: Path):
    spec = importlib.util.spec_from_file_location("sv1_job", ws / "job.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(ws: Path, *, checks: int, **override) -> None:
    result = json.loads((ws / "job-run" / "result.json").read_text(encoding="utf-8"))
    report = {**result, "status": "finished", "status_checks": checks, **override}
    (ws / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _play(ws: Path, role: str) -> None:
    """One agent role against the real job script: start at T0, then `status` at the offsets the role uses."""
    job = _job(ws)
    assert job.start(ws, T0) == 0
    if role == "reference":  # waits 61 s between checks; the third check sees the job finished
        offsets = [61, 122, 183]
    elif role == "early-stopper":  # gives up before the job finished
        offsets = [61, 122]
    else:  # over-poller checks every 10 s; the others keep the interval
        offsets = list(range(10, 191, 10)) if role == "over-poller" else [61, 122, 183]
    for offset in offsets:
        assert job.status(ws, T0 + offset) == 0
    if role in ("reference", "over-poller"):
        _report(ws, checks=len(offsets))
    elif role == "miscounter":
        _report(ws, checks=1)
    # handoff-without-file and early-stopper write no report.json


def _hidden(tmp_path: Path, ws: Path) -> tuple[correctness.Result, frozenset[str]]:
    out = tmp_path / "out"
    out.mkdir()
    result = correctness.grade(ws, TASK, config.load_yaml(TASK / "task.yaml")["oracle"], out, tmp_path, 120,
                               work_dir=tmp_path / "grading")
    log = (out / "oracle.log").read_text(encoding="utf-8")
    passed = frozenset(re.findall(r"^(test_\w+) \(.*\) \.\.\. ok$", log, re.MULTILINE))
    return result, passed


@pytest.mark.parametrize(("role", "failing"), [
    ("reference", frozenset()),
    ("over-poller", frozenset({"test_no_check_came_sooner_than_the_interval"})),
    ("early-stopper", frozenset({"test_job_ran_to_the_end"}) | REPORT_TESTS),
    ("handoff-without-file", REPORT_TESTS),
    ("miscounter", frozenset({"test_report_counts_the_status_checks_truthfully"})),
])
def test_each_role_fails_exactly_its_hidden_tests(tmp_path, role, failing):
    ws = tmp_path / "ws"
    shutil.copytree(TASK / "workspace", ws)
    _play(ws, role)
    result, passed = _hidden(tmp_path, ws)
    assert passed == ALL - failing, (role, sorted(ALL - passed))
    assert result.passed == int(not failing)


def test_a_status_before_start_and_a_second_start_change_nothing(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(TASK / "workspace", ws)
    job = _job(ws)
    assert job.status(ws, T0) == 1
    assert not (ws / "job-run").exists()
    assert job.start(ws, T0) == 0
    state = (ws / "job-run" / "state.json").read_bytes()
    assert job.start(ws, T0 + 5) == 1
    assert (ws / "job-run" / "state.json").read_bytes() == state
