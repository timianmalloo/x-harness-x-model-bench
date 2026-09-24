"""PreToolUse hook (Bash): block a heredoc fed to a Python interpreter (defect class EDIT-B; CT27).

A replacement script inside a heredoc corrupts the escapes in the text it writes: `\\n` arrives as a line
break, `\\\\` as one backslash. The damage shows only when the file is parsed later. So the shape is
blocked: write the program to a file and run it, or change code with the Edit tool.

Reads the hook payload (JSON) on stdin. Exit 2 blocks the call and shows stderr to the agent; any other
input, including a payload that does not parse, passes (exit 0), so the guard never blocks by accident.
"""

from __future__ import annotations

import json
import re
import sys

PYTHON = r"(?:uv\s+run\s+)?(?:python3?|py)(?:\.exe)?"
SHAPES = (
    re.compile(rf"(?:^|[\s;&|(]){PYTHON}\b[^\n|;&]*<<"),  # python - <<'EOF'
    re.compile(rf"<<-?\s*['\"]?\w+['\"]?[^\n]*\|\s*{PYTHON}\b"),  # cat <<'EOF' | python -
)
MESSAGE = ("EDIT-B / CT27: a heredoc into Python corrupts escapes in the text it writes. "
           "Change code with the Edit tool, or write the program to a file (scratchpad) and run it.")


def main() -> int:
    try:
        command = json.loads(sys.stdin.read())["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return 0
    if isinstance(command, str) and any(shape.search(command) for shape in SHAPES):
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
