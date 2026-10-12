"""Replay a recorded Antigravity stream-json session (ADR-0025 s4): `python replay.py <stream.ndjson>`.

The stream is cut into turns after each `result` line. Each input line read on stdin releases the next turn's lines,
verbatim, so a client that sends its next turn only after the previous turn's result (the stream driver and
coord_transport's agy path both do) reads exactly the recorded bytes. A stream with no `result` in its last turn
releases the rest on its last input line. After the last turn it waits for stdin to close, then exits 0, as agy 1.3.3
does (measured when two-turn.ndjson was recorded: exit 0 after stdin closed).
"""

import json
import sys


def _turns(data: bytes) -> list[bytes]:
    turns, current = [], b""
    for line in data.splitlines(keepends=True):
        current += line
        try:
            event = json.loads(line).get("event")
        except (ValueError, AttributeError):
            event = None
        if event == "result":
            turns.append(current)
            current = b""
    if current:
        turns.append(current)
    return turns


def main() -> int:
    with open(sys.argv[1], "rb") as f:
        turns = _turns(f.read())
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        if not raw.strip():
            continue
        if turns:
            out.write(turns.pop(0))
            out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
