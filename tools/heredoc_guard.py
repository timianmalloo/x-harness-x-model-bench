"""PreToolUse hook (Bash, PowerShell): block four command shapes that fail silently or destroy work (CT27, CLN-C).

EDIT-B: a heredoc fed to a Python interpreter. A replacement script inside a heredoc corrupts the escapes in
the text it writes: `\\n` arrives as a line break, `\\\\` as one backslash. The damage shows only when the file
is parsed later. Write the program to a file and run it, or change code with the Edit tool.

E2E-E: a gate (pytest, ruff, mutate_check, conductor-join, run-verify-gates) piped into another command. The
pipe's status is the last command's, so a failing gate reads as green. Read the gate's status on its own line,
or set `pipefail`.

CLN-C: `git worktree remove --force` / `-f` and `git branch -D`. The forced forms remove what the plain command
refuses (a dirty tree, an unmerged branch). Three instances by the Leader (2026-09-25, 09-25, 09-27) triggered this
hook. Remove plainly after naming the tree's untracked files, or use the holding scripts.

PROC-A: a process kill by name, pattern or command line (`Stop-Process -Name`, a pipeline or a `Where-Object` filter
into `Stop-Process`, `taskkill /IM` or `/FI`, `pkill`, `killall`, WMI terminate). On 2026-10-03 one such kill, matching
`pytest`, ended three other worktrees' mutation runs and left their mutants applied. Kill only PIDs you started.

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
GIT = r"\bgit(?:\s+-C\s+\S+)?"
FORCED_REMOVAL = (
    re.compile(rf"{GIT}\s+worktree\s+remove\b[^\n;&|]*\s(?:--force|-f)\b"),  # git worktree remove --force <tree>
    re.compile(rf"{GIT}\s+branch\s+(?:[^\n;&|]*\s)?-D\b"),  # git branch -D <branch>
)
STOP = r"(?:Stop-Process|spps)"
KILL_SHAPES = tuple(re.compile(shape, re.IGNORECASE) for shape in (
    rf"\b{STOP}\b[^\n;&|]*\s-(?:Name|ProcessName)\b",  # Stop-Process -Name python
    r"-MethodName\s+Terminate\b",  # Invoke-CimMethod -MethodName Terminate
    r"\bwmic\b[^\n;&|]*\bprocess\b[^\n;&|]*\b(?:delete|call\s+terminate)\b",
    r"\btaskkill(?:\.exe)?\b[^\n;&|]*\s[/-]+(?:IM|FI)\b",  # taskkill /IM x, //FI y (Git Bash doubles the slash)
    r"(?:^|[;&|(\n])\s*(?:sudo\s+)?(?:pkill|killall)\b",
    # a filter on CommandLine/Name feeding a ForEach-Object that stops: a pattern kill through a PID
    rf"\bWhere(?:-Object)?\b[^\n;|]*\b(?:CommandLine|ProcessName|Name)\b[^\n;]*\|\s*(?:ForEach(?:-Object)?\b|%)[^\n]*\b{STOP}\b",
))
PIPED_STOP = re.compile(rf"\|\s*{STOP}\b", re.IGNORECASE)
BY_ID_SOURCE = re.compile(r"\s*(?:Get-Process|gps)\s+-Id\b[^|]*$", re.IGNORECASE)  # the only pipe source that names PIDs


def _pattern_kill(command: str) -> bool:
    if any(shape.search(command) for shape in KILL_SHAPES):
        return True
    for piped in PIPED_STOP.finditer(command):
        statement = re.split(r"[;\n]", command[: piped.start()])[-1]
        if not BY_ID_SOURCE.match(statement):
            return True
    return False


MESSAGES = {
    "heredoc": ("EDIT-B / CT27: a heredoc into Python corrupts escapes in the text it writes. "
                "Change code with the Edit tool, or write the program to a file (scratchpad) and run it."),
    "pipe": ("E2E-E / CT27: a gate piped into another command reports that command's exit status, not the gate's. "
             "Redirect the gate to a log and read `$?` on its own line, or add `set -o pipefail`."),
    "force": ("CLN-C: a forced worktree or branch removal destroys what the plain command would refuse. Name the "
              "tree's untracked files and remove it plainly, or use the holding scripts (cleanup_merged.sh, "
              "coord worktree cleanup --remove)."),
    "kill": ("PROC-A: a kill by process name, pattern or command line reaches other sessions' processes. Kill only "
             "PIDs you started: Stop-Process -Id <pid>, taskkill /PID <pid>, kill <pid>."),
}


def verdict(command: str) -> str | None:
    if any(shape.search(command) for shape in HEREDOC):
        return "heredoc"
    unquoted = QUOTED.sub("''", command)
    if "pipefail" not in command and PIPED_GATE.search(unquoted):
        return "pipe"
    if any(shape.search(unquoted) for shape in FORCED_REMOVAL):
        return "force"
    if _pattern_kill(unquoted):
        return "kill"
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
