"""A fake `copilot` exe for the copilot -p adapter tests (ADR-0028 s1), driven by FAKE_COPILOT (JSON).

`--version` prints the pinned build's banner. Any other launch appends {argv, pid} to cfg["log"], then by
cfg["mode"]: "replay" (default) writes a real, scrubbed `copilot -p --output-format json` stdout unchanged and exits 0
(turn1-stdout.jsonl for --session-id, turn2-resume-stdout.jsonl for --resume); "hang" writes one line and sleeps;
"fail" writes one non-result line and exits 3; "noresult" exits 0 without a result object; "tokens" ends with a result
whose usage carries ACP token counts.
"""

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
argv = sys.argv[1:]
if argv == ["--version"]:
    print("GitHub Copilot CLI 1.0.89-1. Run 'copilot update' to check for updates.")
    sys.exit(0)
cfg = json.loads(os.environ.get("FAKE_COPILOT") or "{}")
with open(cfg["log"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": argv, "pid": os.getpid()}) + "\n")
out = sys.stdout.buffer
mode = cfg.get("mode", "replay")
first = b'{"type":"session.info","data":{"infoType":"configuration","message":"fake"}}\n'
if mode == "replay":
    out.write((HERE / ("turn1-stdout.jsonl" if "--session-id" in argv else "turn2-resume-stdout.jsonl")).read_bytes())
elif mode == "hang":
    out.write(first)
    out.flush()
    time.sleep(120)
elif mode == "fail":
    out.write(first)
    sys.exit(3)
elif mode == "tokens":
    out.write(first + json.dumps({"type": "result", "exitCode": 0, "usage": {
        "premiumRequests": 1, "inputTokens": 11, "outputTokens": 2, "cachedReadTokens": 5,
        "cachedWriteTokens": 0}}).encode("utf-8") + b"\n")
out.flush()
