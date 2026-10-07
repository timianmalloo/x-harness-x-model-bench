"""W1-K K2 (X-K2b): `bench status <run_id> --alarm-after <s>` through the real `cli.main` (docs/design/eval-resume.md 6.2, 13).

Every fixture is a hand-built ledger over the shared archived-run builder's plan (one or two cells, stamped rows with a chosen
`recorded_at`), a lock that is free, fresh or aged with `os.utime`, and the real clock. The K1 skeleton returns exit 0, so each
alarming test fails on its own assertion (`exit == 6`), never on argparse or an import.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from archived_runs import make_root, make_run

from harness_bench import alarm, cli, ledger, oslock, status

AFTER = 600
TASK = Path(__file__).resolve().parents[1] / "tools" / "alarm-task.ps1"


def _at(age_s: float) -> str:
    """A `recorded_at` string `age_s` seconds before now, in ledger.stamp's shape."""
    when = time.time() - age_s
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(when)) + f".{int(when * 1000) % 1000:03d}Z"


def _row(kind: str, age_s: float, **fields) -> dict:
    return {"kind": kind, "recorded_at": _at(age_s), "mono_ns": 1, **fields}


def _cell_rows(cid: str, upto: str, age_s: float = 7200) -> list[dict]:
    """A cell's rows up to and including `upto`, all stamped `age_s` ago."""
    kinds = ["cell.launch_intent", "cell.workspace_built", "attempt.process_started", "attempt.session_opened", "cell.prompt_sent",
             "cell.turn_ended", "attempt.process_ended", "cell.outcome", "cell.archived", "cell.workspace_deleted"]
    extra = {"cell.turn_ended": {"turn": 1, "next": "final"}, "cell.prompt_sent": {"turn": 1},
             "cell.outcome": {"outcome": "completed", "cause": None, "code": None},
             "cell.archived": {"archive_attempt": 1, "archive_hash": "h"}}
    return [_row(k, age_s, cell_id=cid, **extra.get(k, {})) for k in kinds[:kinds.index(upto) + 1]]


@pytest.fixture
def env(tmp_path):
    return make_run(make_root(tmp_path), tmp_path, {}, unstarted=("a", "b"))


def _events(run_dir: Path, rows: list[dict], name: str = "engine-2") -> None:
    with ledger.SegmentWriter.create(run_dir / "events", name) as w:
        for r in rows:
            w.append(r)


def _alarm(run_dir: Path, capsys, *extra: str, after: int = AFTER) -> tuple[int, str]:
    code = cli.main(["--runs", str(run_dir.parent), "status", run_dir.name, "--alarm-after", str(after), *extra])
    return code, capsys.readouterr().err


def test_stale_progress_exits_6_with_alm_002(env, capsys):
    _events(env, _cell_rows("a", "cell.prompt_sent"))
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-002:")) == (6, True)


def test_free_lock_with_work_exits_6_alm_001(env, capsys):
    _events(env, _cell_rows("a", "cell.prompt_sent", age_s=5))
    code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)
    assert "not running" in err


def test_stalled_heartbeat_exits_6(env, capsys):
    _events(env, _cell_rows("a", "cell.prompt_sent", age_s=5))
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        old = time.time() - 3600
        os.utime(env / ".lock", (old, old))
        code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)
    assert "stalled" in err


def test_complete_run_exits_0(env, capsys):
    _events(env, [*_cell_rows("a", "cell.workspace_deleted"), *_cell_rows("b", "cell.workspace_deleted"),
                  _row("run.completed", 7200, run_id="r1")])
    assert _alarm(env, capsys) == (0, "")


def test_finished_stop_is_silent(env, capsys):  # R-102: a C7 cell, a stop row, run.completed after run.resumed
    _events(env, [_row("run.stopped", 7200, code="HB-RUN-006", decision_id=None)])
    _events(env, [_row("run.resumed", 7000, run_id="r1", segment_id="engine-3"),
                  _row("run.completed", 7000, run_id="r1")], name="engine-3")
    assert _alarm(env, capsys) == (0, "")


def _stop_row(window: str) -> dict:
    if window == "control_applied":
        return _row("control.applied", 7200, uuid="a" * 32, control="stop", decision_id=None, effect="applied")
    if window == "decision_resolved":
        return _row("decision.resolved", 7200, decision_id="D1", state="answered", option="stop")
    return _row("run.stopped", 7200, code="HB-RUN-006", decision_id=None)


@pytest.mark.parametrize("window", ["control_applied", "decision_resolved", "run_stopped"])
def test_mid_stop_crash_alarms(env, capsys, window):
    _events(env, [*_cell_rows("a", "cell.launch_intent"), _stop_row(window)])
    code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)


def test_crash_in_grading_alarms(env, capsys):  # every cell archived, no run.completed: the engine died in grading
    _events(env, [*_cell_rows("a", "cell.workspace_deleted"), *_cell_rows("b", "cell.workspace_deleted")])
    code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)


def test_outcome_without_archive_alarms(env, capsys):  # run.completed present, one outcome never archived
    _events(env, [*_cell_rows("a", "cell.outcome"), *_cell_rows("b", "cell.workspace_deleted"), _row("run.completed", 7200, run_id="r1")])
    code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)


def test_launch_stop_alarms(env, capsys):  # a launch stop is not a stop (D-K4): the never-launched cells are work
    _events(env, [*_cell_rows("a", "cell.workspace_deleted"),
                  _row("run.launch_stopped", 7200, code="HB-IDN-001", reason="drift", diff=[])])
    code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-001:")) == (6, True)


def test_pending_zero_does_not_raise_alm_002(env, capsys):  # a long grading pass: work only by clause 4, gap under after_s
    _events(env, [*_cell_rows("a", "cell.workspace_deleted", age_s=60), *_cell_rows("b", "cell.workspace_deleted", age_s=60)])
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        assert _alarm(env, capsys) == (0, "")


def test_unreadable_progress_fails_closed(env, capsys):  # make_run's rows carry no recorded_at: not recorded, so the alarm raises
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        code, err = _alarm(env, capsys)
    assert (code, err.startswith("HB-ALM-002:")) == (6, True)
    assert "not recorded" in err


def test_gap_equal_to_the_threshold_is_silent(env):  # M-GE: "exceeds after_s" is strict, on an injected clock (W1-K 6.2)
    _events(env, _cell_rows("a", "cell.prompt_sent", age_s=5))
    last = datetime.fromisoformat(status.last_progress_at(env)).timestamp()
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        assert alarm.check(env, AFTER, now=last + AFTER) is None
        late = alarm.check(env, AFTER, now=last + AFTER + 1)
    assert late is not None and late.code == "HB-ALM-002"


def test_json_form_carries_the_alarm_object(env, capsys):
    _events(env, _cell_rows("a", "cell.prompt_sent"))
    with oslock.RunLock.acquire(env / ".lock", "HB-RUN-003"):
        code = cli.main(["--runs", str(env.parent), "status", env.name, "--alarm-after", str(AFTER), "--json"])
    out = capsys.readouterr().out
    assert code == 6
    data = json.loads(out)
    assert set(data["alarm"]) == {"code", "cause", "last_progress_at", "age_s"} and data["alarm"]["code"] == "HB-ALM-002"


def test_alarm_has_no_pending_logic_of_its_own():  # M-ALARMPENDING: the work definition is resume.has_work, imported
    source = Path(alarm.__file__).read_text(encoding="utf-8")
    assert "from harness_bench.resume import has_work" in source and "has_work(" in source
    for private in ("cell.outcome", "cell.archived", "cell.launch_intent", "stop_recorded", "run.stopped", "classify"):
        assert private not in source, f"alarm.py carries its own pending logic ({private})"


@pytest.mark.native
@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe 5.1 not found")
def test_real_status_command_feeds_the_real_alarm_task(env, tmp_path):  # INT-A control (W0 13, alarm-task row): K2a's stub cannot drift
    _events(env, _cell_rows("a", "cell.prompt_sent", age_s=5))  # ADR-0021 7 fixture: work left, no engine holds the lock
    runs = env.parent
    bench = tmp_path / "bin" / "bench.cmd"
    bench.parent.mkdir()
    bench.write_text(f'@echo off\r\n"{sys.executable}" -c "import sys; from harness_bench.cli import main; sys.exit(main(sys.argv[1:]))" '
                     f'--runs "{runs}" %*\r\n', encoding="ascii")  # stderr passes through, as in the scheduled task
    real = subprocess.run([str(bench), "status", env.name, "--alarm-after", "600", "--json"], capture_output=True, text=True, timeout=120,
                          check=False)
    printed = real.stderr.split(":", 1)[0]
    assert (real.returncode, printed) == (6, "HB-ALM-001")
    sent = tmp_path / "sent.txt"
    (tmp_path / "rest.ps1").write_text('function Invoke-RestMethod { param($Uri, $Method, $Body) Add-Content -Path $env:HB_TEST_SENT -Value "$Uri|$Body" }\n',
                                       encoding="ascii")
    task_env = {k: v for k, v in os.environ.items() if not k.startswith("HB_ALARM_")} | {"HB_TEST_SENT": str(sent), "HB_ALARM_NTFY_TOPIC": "tpc-fake-0001"}
    task = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TASK), "-RunId", env.name, "-AlarmAfter", "600",
                           "-DryRun", "-Bench", str(bench), "-RunsRoot", str(runs), "-RestStub", str(tmp_path / "rest.ps1")],
                          capture_output=True, text=True, timeout=120, env=task_env, check=False)
    assert task.returncode == 6
    assert f"run {env.name} {printed} " in sent.read_text(encoding="ascii")  # the payload's code is the one the command printed
