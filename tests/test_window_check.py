"""Tests for tools/window_check.py (R6.15a, C-W0).

The windows check tool lists visible top-level windows created after a given
instant by the session's own PIDs.
"""

import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "window_check.py"


@pytest.fixture
def visible_window_child():
    """Starts a child process opening one visible window, and terminates it by PID on teardown."""
    since = datetime.now(UTC).isoformat()
    time.sleep(0.05)
    code = (
        "import tkinter as tk, time\n"
        "root = tk.Tk()\n"
        "root.title('TestWindowCheckTitleSecret')\n"
        "root.update()\n"
        "print('READY', flush=True)\n"
        "time.sleep(30)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    line = proc.stdout.readline().decode().strip()
    assert line == "READY"
    try:
        yield proc, since
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_window_check_lists_visible_window(visible_window_child):
    proc, since = visible_window_child
    res = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--since",
            since,
            "--root-pid",
            str(os.getpid()),
        ],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert res.returncode == 1
    assert str(proc.pid) in res.stdout
    assert "TkTopLevel" in res.stdout
    assert "TestWindowCheckTitleSecret" not in res.stdout


def test_window_check_child_with_flag_lists_nothing():
    since = datetime.now(UTC).isoformat()
    time.sleep(0.05)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        res = subprocess.run(
            [
                sys.executable,
                str(TOOL_PATH),
                "--since",
                since,
                "--root-pid",
                str(proc.pid),
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert res.returncode == 0
        assert res.stdout.strip() == ""
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_window_check_cannot_run():
    res = subprocess.run(
        [sys.executable, str(TOOL_PATH), "--since", "not-a-valid-date"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert res.returncode == 2
