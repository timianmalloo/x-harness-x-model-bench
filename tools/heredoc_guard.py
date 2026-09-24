"""PreToolUse hook (Bash): block two command shapes that fail silently (CT27).

EDIT-B: a heredoc fed to a Python interpreter. A replacement script inside a heredoc corrupts the escapes in
the text it writes: `\\n` arrives as a line break, `\\\\` as one backslash. The damage shows only when the file
is parsed later. Write the program to a file and run it, or change code with the Edit tool.

E2E-E: a gate (pytest, ruff, mutate_check, conductor-join, run-verify-gates) piped into another command. The
pipe's status is the last command's, so a failing gate reads as green. Read the gate's status on its own line,
or set `pipefail`.

Reads the hook payload (JSON) on stdin. Exit 2 blocks the call and shows stderr to the agent; any other
input, including a payload that does not parse, passes (exit 0), so the guard never blocks by accident.
"""

from __future__ import annotations

import json
import re
import sys

PYTHON = r"(?:uv\s+run\s+)?(?:python3?|py)(?:\.exe)?"
HEREDOC = (
    re.compile(rf"(?:^|[\s;&|(]){PYTHON}\b[^\n|;&]*<<"),  # python - <<'EOF'
    re.compile(rf"<<-?\s*['\"]?\w+['\"]?[^\n]*\|\s*{PYTHON}\b"),  # cat <<'EOF' | python -
)
GATE = r"(?:\bpytest\b|\bruff\s+check\b|\b(?:mutate_check|conductor-join|run-verify-gates)\.py\b)"
PIPED_GATE = re.compile(rf"(?:^|[\s;&(/\\]){GATE}[^\n;&|]*(?<!\|)\|(?!\|)")  # uv run pytest -q | tail -1
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a quoted argument: a | inside it is data, not a pipe
MESSAGES = {
    "heredoc": ("EDIT-B / CT27: a heredoc into Python corrupts escapes in the text it writes. "
                "Change code with the Edit tool, or write the program to a file (scratchpad) and run it."),
    "pipe": ("E2E-E / CT27: a gate piped into another command reports that command's exit status, not the gate's. "
             "Redirect the gate to a log and read `$?` on its own line, or add `set -o pipefail`."),
}


def verdict(command: str) -> str | None:
    if any(shape.search(command) for shape in HEREDOC):
        return "heredoc"
    if "pipefail" not in command and PIPED_GATE.search(QUOTED.sub("''", command)):
        return "pipe"
    return None


def main() -> int:
    try:
        command = json.loads(sys.stdin.read())["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return 0
    found = verdict(command) if isinstance(command, str) else None
    if found:
        print(MESSAGES[found], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
