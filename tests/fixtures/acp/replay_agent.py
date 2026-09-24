"""Replays a recorded ACP transcript to the client, verbatim (design D5-consumer; W1-ACP (b)).

Configuration comes from the REPLAY_ACP environment variable (JSON):
  {"recording": "<an acp-recording/1 file, tests/fixtures/acp/recordings/*.jsonl, or a derived copy>"}

The recorded agent lines are cut at each complete line the client sent in the recording. The agent lines
recorded before the first client line go out at start; each line the client sends now releases the agent
lines recorded after the matching client line. Every agent line goes out exactly as recorded (bytes, order,
newline). Nothing is synthesised, and the client's lines are counted, never parsed.
"""

import base64
import json
import os
import sys

CFG = json.loads(os.environ.get("REPLAY_ACP", "{}"))
OUT = sys.stdout.buffer


def segments(path: str) -> list[bytes]:
    out = [b""]
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("kind") != "line":
                continue
            if r["dir"] == "to_agent":
                if r["nl"]:  # a complete client line ends a segment
                    out.append(b"")
                continue
            data = r["text"].encode("utf-8") if "text" in r else base64.b64decode(r["b64"])
            out[-1] += data + (b"\n" if r["nl"] else b"")
    return out


def send(data: bytes) -> None:
    if data:
        OUT.write(data)
        OUT.flush()


def main() -> int:
    parts = segments(CFG["recording"])
    send(parts[0])
    for i, _ in enumerate(sys.stdin.buffer, start=1):
        if i < len(parts):
            send(parts[i])
    return 0


if __name__ == "__main__":
    sys.exit(main())
