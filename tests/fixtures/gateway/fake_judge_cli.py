"""A fake Claude Code judge CLI for the headless backend's contract tests: no model, no network, no real home.

It replays one recorded turn from `records/` in place of `claude.exe -p ... --session-id <uuid>`:
- reads the whole request from stdin (the gateway's delivery, design section 8.1);
- writes the recorded native record to `$CLAUDE_CONFIG_DIR/projects/C--cells-work/<session>.jsonl`, with the
  record's placeholder session id replaced by the one in argv, so the real reader finds and decides it;
- prints the recorded stdout (session id replaced the same way);
- optionally sleeps (a timeout) and exits with a given status.

Configured by `HB_FAKE_JUDGE` (JSON): record, stdout (file paths), capture (a folder: one JSON file per call with
the argv, the stdin text, whether the credential copy was present, the working folder and USERPROFILE), sleep,
exit. The environment it reads is the one the backend built, under the test's tmp_path.
"""

import json
import os
import sys
import time
from pathlib import Path

PLACEHOLDER_SESSION = "00000000-0000-4000-8000-000000000001"


def main() -> int:
    cfg = json.loads(os.environ["HB_FAKE_JUDGE"])
    argv = sys.argv[1:]
    session = argv[argv.index("--session-id") + 1]
    request = sys.stdin.buffer.read().decode("utf-8")
    home = Path(os.environ["CLAUDE_CONFIG_DIR"])
    if cfg.get("capture"):
        seen = {"argv": argv, "stdin": request, "credential_present": (home / ".credentials.json").is_file(),
                "cwd": os.getcwd(), "userprofile": os.environ.get("USERPROFILE")}
        Path(cfg["capture"]).mkdir(parents=True, exist_ok=True)
        (Path(cfg["capture"]) / f"{session}.json").write_text(json.dumps(seen), encoding="utf-8")
    record = Path(cfg["record"]).read_text(encoding="utf-8").replace(PLACEHOLDER_SESSION, session)
    out = home / "projects" / "C--cells-work" / f"{session}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(record, encoding="utf-8")
    stdout = Path(cfg["stdout"]).read_text(encoding="utf-8").replace(PLACEHOLDER_SESSION, session)
    sys.stdout.buffer.write(stdout.encode("utf-8"))
    sys.stdout.flush()
    time.sleep(float(cfg.get("sleep", 0)))
    return int(cfg.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main())
