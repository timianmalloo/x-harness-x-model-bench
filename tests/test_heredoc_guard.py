"""The EDIT-B and E2E-E controls (CT27): two Bash shapes are blocked before they run.

EDIT-B: a replacement script inside a heredoc corrupts escapes in the text it writes (docs/lessons/defect-classes.md;
four instances on 2026-09-23). A program is written to a file, then run.
E2E-E: a gate piped into another command reports that command's exit status, so a failing gate reads as green
(one instance on 2026-09-24). A gate's status is read on its own line, or the pipe carries `pipefail`.
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


@pytest.mark.parametrize("command", [
    "uv run pytest --collect-only -q tests/e2e | tail -1",  # the observed instance, 2026-09-24
    "cd /c/x && uv run pytest -q -p no:cacheprovider | tail -3",
    "python -m pytest -q | head -5",
    "uv run ruff check src tests tools | tail -1",
    "uv run python tools/mutate_check.py tests/mutations/t8.json | tail -2",
    "python docs/ai-forward-pack/scripts/conductor-join.py track/x | tail -20",
])
def test_a_gate_behind_a_pipe_is_blocked(command):  # E2E-E / CT27: a pipe reports the last command's status
    result = _run(command)
    assert result.returncode == 2
    assert "E2E-E" in result.stderr


@pytest.mark.parametrize("command", [
    "set -o pipefail; uv run pytest -q | tail -3",
    "uv run pytest -q > log.txt 2>&1\necho \"exit: $?\"",
    "uv run pytest -q || echo failed",
    "grep -E 'passed|failed' log.txt | tail -1",
    "uv run ruff check src && echo ok",
    'grep -h -E "run:.*(pytest|unittest)" .github/workflows/*.yml | head -5',  # observed false positive, 2026-09-24
    "grep -c 'pytest|ruff check' notes.txt",
])
def test_a_gate_without_a_pipe_passes(command):
    assert _run(command).returncode == 0


def test_a_malformed_payload_never_blocks():
    result = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0
