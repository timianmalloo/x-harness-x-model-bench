"""Replays a recorded ACP `session/prompt` result to the driver (design D5-consumer).

Configuration comes from the REPLAY_ACP environment variable (JSON):
  {"prompt_result": "<a recorded result file in this folder>",
   "drop": [<top-level keys removed from the recorded result, for a derived variant>],
   "before_result": [<messages sent before the result, e.g. a seeded notification>]}

Only the prompt result is recorded bytes (see provenance.json). The initialize and session/new replies
here are the minimal shapes the ACP schema requires: they were not captured, and nothing here claims they were.
"""

import json
import os
import sys

CFG = json.loads(os.environ.get("REPLAY_ACP", "{}"))
OUT = sys.stdout.buffer


def send(obj: dict) -> None:
    OUT.write(json.dumps(obj).encode("utf-8") + b"\n")
    OUT.flush()


def main() -> int:
    with open(CFG["prompt_result"], encoding="utf-8") as f:
        recorded = json.load(f)
    for key in CFG.get("drop", []):
        recorded.pop(key, None)
    for raw in sys.stdin.buffer:
        msg = json.loads(raw)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1, "agentCapabilities": {}}})
        elif method == "session/new":
            send({"jsonrpc": "2.0", "id": mid, "result": {"sessionId": "replay-session"}})
        elif method == "session/set_mode":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "session/prompt":
            for extra in CFG.get("before_result", []):
                send(extra)
            send({"jsonrpc": "2.0", "id": mid, "result": recorded})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "not in the replay"}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
