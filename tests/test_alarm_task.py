"""tools/alarm-task.ps1 (X-K2a, W1-K 6.3, W0 rev 6.11 section 13, R6.9b).

Windows only (`native`): every test drives the script under powershell.exe 5.1 with -DryRun, a stub `bench`
(a .cmd that prints a `bench-status/1` object and exits with a chosen code) and a stub `Invoke-RestMethod`.
No test reaches the network: -DryRun shadows the cmdlet before any POST. The clock is injected with -Now,
never slept. The real `bench status --alarm-after` joins this stub in X-K2b's cross-owner test.
"""
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "alarm-task.ps1"
POWERSHELL = shutil.which("powershell.exe")
TOPIC = "tpc-9f3a7c1e5b"
T0 = datetime(2026, 10, 6, 1, 0, 0, tzinfo=UTC)

pytestmark = [
    pytest.mark.native,
    pytest.mark.skipif(POWERSHELL is None, reason="powershell.exe 5.1 not found"),
]

REST_OK = "function Invoke-RestMethod { param($Uri, $Method, $Body) Add-Content -Path $env:HB_TEST_SENT -Value \"$Uri|$Body\" }\n"
REST_THROW = (
    "function Invoke-RestMethod { param($Uri, $Method, $Body)\n"
    "  throw (New-Object System.Net.WebException(\"unable to connect to $Uri\")) }\n"
)


def _alarm_object(code="HB-ALM-001", cause="no progress for 2h", age_s=7300, **extra):
    alarm = {"code": code, "cause": cause, "last_progress_at": "2026-10-05T22:00:00Z", "age_s": age_s}
    alarm.update(extra)
    return {"schema": "bench-status/1", "run_id": "r1", "alarm": alarm}


class Harness:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.runs = tmp_path / "runs"
        self.run_dir = self.runs / "r1"
        self.sent = tmp_path / "sent.txt"
        (tmp_path / "rest_ok.ps1").write_text(REST_OK, encoding="ascii")
        (tmp_path / "rest_throw.ps1").write_text(REST_THROW, encoding="ascii")

    def run(self, exit_code, payload=None, *, at=T0, rest="ok", topic=TOPIC, base_url=None):
        (self.tmp / "out.json").write_text(json.dumps(payload) if payload is not None else "", encoding="ascii")
        (self.tmp / "bench.cmd").write_text(f'@echo off\r\ntype "%~dp0out.json"\r\nexit /b {exit_code}\r\n', encoding="ascii")
        env = {k: v for k, v in os.environ.items() if not k.startswith("HB_ALARM_")}
        env["HB_TEST_SENT"] = str(self.sent)
        if topic is not None:
            env["HB_ALARM_NTFY_TOPIC"] = topic
        if base_url is not None:
            env["HB_ALARM_NTFY_URL"] = base_url
        argv = [
            POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
            "-RunId", "r1", "-AlarmAfter", "7200", "-DryRun",
            "-Bench", str(self.tmp / "bench.cmd"), "-RunsRoot", str(self.runs),
            "-Now", at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ]
        if rest is not None:
            argv += ["-RestStub", str(self.tmp / f"rest_{rest}.ps1")]
        return subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env, check=False)

    def sent_lines(self):
        return self.sent.read_text(encoding="ascii").splitlines() if self.sent.exists() else []

    def delivery_log(self):
        path = self.run_dir / "alarm-delivery.log"
        return path.read_text(encoding="ascii") if path.exists() else ""


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


def test_push_failure_does_not_print_topic(h):
    """The stub throws with the URL (and so the topic) in its message; the catch writes fixed text only."""
    result = h.run(6, _alarm_object(), rest="throw")
    assert TOPIC not in result.stdout
    assert TOPIC not in result.stderr
    assert TOPIC not in h.delivery_log()


def test_two_runs_in_a_row_send_once(h):
    h.run(6, _alarm_object(), at=T0)
    h.run(6, _alarm_object(), at=T0 + timedelta(minutes=15))
    assert len(h.sent_lines()) == 1


def test_payload_is_only_run_code_cause_age(h):
    payload = _alarm_object(cause="no progress for 2h", age_s=7300, task_path="C:\\leak\\task", cell_id="cell-secret")
    result = h.run(6, payload)
    assert result.returncode == 6
    assert h.sent_lines() == [f"https://ntfy.sh/{TOPIC}|run r1 HB-ALM-001 no progress for 2h: age 7300s"]


@pytest.mark.parametrize("exit_code", [1, 5])
def test_any_other_nonzero_exit_is_a_check_error(h, exit_code):
    result = h.run(exit_code, None)
    assert result.returncode == exit_code
    (line,) = h.sent_lines()
    assert "run r1 check-error" in line
    assert f"bench status exited {exit_code}" in line


def test_exit_zero_with_no_prior_alarm_sends_nothing(h):
    result = h.run(0, None)
    assert result.returncode == 0
    assert h.sent_lines() == []


def test_dry_run_without_a_stub_still_never_reaches_the_network(h):
    result = h.run(6, _alarm_object(), rest=None)
    assert result.returncode == 6
    assert TOPIC not in result.stdout + result.stderr


def test_unset_topic_refuses_with_the_fixed_line(h):
    result = h.run(0, None, topic=None)
    assert result.returncode != 0
    assert "alarm channel not configured: set HB_ALARM_NTFY_TOPIC (runbook)" in result.stdout + result.stderr


def test_delivery_log_has_one_line_per_run_and_no_topic_or_uri(h):
    h.run(6, _alarm_object(), at=T0)
    h.run(6, _alarm_object(), at=T0 + timedelta(hours=1), rest="throw")
    lines = h.delivery_log().splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("exit=6 push ok")
    assert "push failed: WebException" in lines[1]
    log = h.delivery_log()
    assert TOPIC not in log
    assert "http" not in log


def test_a_new_code_sends_again(h):
    h.run(6, _alarm_object(code="HB-ALM-001"), at=T0)
    h.run(6, _alarm_object(code="HB-ALM-002"), at=T0 + timedelta(minutes=15))
    assert len(h.sent_lines()) == 2


def test_resend_is_hourly_on_an_injected_clock(h):
    h.run(6, _alarm_object(), at=T0)
    h.run(6, _alarm_object(), at=T0 + timedelta(minutes=59, seconds=59))
    assert len(h.sent_lines()) == 1
    h.run(6, _alarm_object(), at=T0 + timedelta(hours=1))
    assert len(h.sent_lines()) == 2


def test_recovery_sends_once_and_clears_the_edge(h):
    h.run(6, _alarm_object(), at=T0)
    h.run(0, None, at=T0 + timedelta(minutes=15))
    assert len(h.sent_lines()) == 2
    assert not (h.run_dir / ".alarm_edge").exists()
    h.run(0, None, at=T0 + timedelta(minutes=30))
    assert len(h.sent_lines()) == 2


def test_edge_state_file_holds_only_code_and_times(h):
    h.run(6, _alarm_object(), at=T0)
    state = json.loads((h.run_dir / ".alarm_edge").read_text(encoding="ascii")) if (h.run_dir / ".alarm_edge").exists() else {}
    assert set(state) == {"code", "first_sent_at", "last_sent_at"}
    assert state["code"] == "HB-ALM-001"


def test_a_failed_push_keeps_the_edge_so_the_next_run_retries(h):
    h.run(6, _alarm_object(), at=T0, rest="throw")
    h.run(6, _alarm_object(), at=T0 + timedelta(minutes=15))
    assert len(h.sent_lines()) == 1


def test_optional_base_url_replaces_the_default_host(h):
    h.run(6, _alarm_object(), base_url="https://ntfy.example.test")
    assert h.sent_lines()[0].startswith(f"https://ntfy.example.test/{TOPIC}|")
