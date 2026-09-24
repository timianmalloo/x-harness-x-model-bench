"""The EDIT-B / CT27 control: a heredoc fed to a Python interpreter is blocked before it runs.

A replacement script inside a heredoc corrupts escapes in the text it writes (docs/lessons/defect-classes.md,
EDIT-B; four instances on 2026-09-23). The hook blocks the shape; a program is written to a file, then run.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "tools" / "heredoc_guard.py"


def _run(command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30, check=False)


@pytest.mark.parametrize("command", [
    "python - <<'EOF'\nprint(1)\nEOF",
    "cd /c/x && python - <<'EOF'\nprint(1)\nEOF",
    "uv run python - <<EOF\nprint(1)\nEOF",
    "python3 <<'PY'\nprint(1)\nPY",
    "py -3 - <<'EOF'\nprint(1)\nEOF",
    "cat <<'EOF' | python -\nprint(1)\nEOF",
])
def test_a_heredoc_into_python_is_blocked(command):
    result = _run(command)
    assert result.returncode == 2
    assert "EDIT-B" in result.stderr


@pytest.mark.parametrize("command", [
    "git commit -q -F - <<'EOF'\nfeat: x\nEOF",
    "uv run python tools/mutate_check.py tests/mutations/grade.json",
    "python -c \"import sys; print(sys.executable)\"",
    "uv run pytest -q",
])
def test_other_commands_pass(command):
    assert _run(command).returncode == 0


def test_a_malformed_payload_never_blocks():
    result = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0
