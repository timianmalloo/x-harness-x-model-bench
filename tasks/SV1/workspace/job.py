"""A batch job. Start it with `python job.py start`; check it with `python job.py status`.

The job takes DURATION_S seconds from `start`. Its state, its status log and, once it finished, its result are in
the job-run/ folder. Run with no arguments for this help.
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DURATION_S = 180
RECORDS_PER_S = 100
RUN_DIR = "job-run"


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")  # noqa: UP017 - keeps Python 3.10 working


def _result(state: dict) -> dict:
    records = state["duration_s"] * RECORDS_PER_S
    return {"job_id": state["job_id"], "records_processed": records,
            "checksum": hashlib.sha256(f"{state['job_id']}|{records}".encode()).hexdigest()[:16],
            "started_at": _iso(state["started_at"]), "finished_at": _iso(state["started_at"] + state["duration_s"])}


def start(root: Path, now: float) -> int:
    run = root / RUN_DIR
    if (run / "state.json").exists():
        print("the job is already started; check it with: python job.py status")
        return 1
    run.mkdir(exist_ok=True)
    job_id = "job-" + hashlib.sha256(repr(now).encode()).hexdigest()[:8]
    (run / "state.json").write_text(json.dumps({"job_id": job_id, "started_at": now, "duration_s": DURATION_S}),
                                    encoding="utf-8")
    print(f"started {job_id}; it takes about {DURATION_S // 60} minutes")
    return 0


def status(root: Path, now: float) -> int:
    run = root / RUN_DIR
    try:
        state = json.loads((run / "state.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("the job is not started; start it with: python job.py start")
        return 1
    elapsed = now - state["started_at"]
    finished = elapsed >= state["duration_s"]
    with (run / "status.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"at": now, "elapsed_s": round(elapsed, 3), "state": "finished" if finished else "running"}) + "\n")
    if not finished:
        done = max(int(elapsed), 0)
        print(f"{state['job_id']} running: {done * 100 // state['duration_s']}% "
              f"({done} of {state['duration_s']} s, {done * RECORDS_PER_S} records)")
        return 0
    result = _result(state)
    (run / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{state['job_id']} finished. Result (also in {RUN_DIR}/result.json):")
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str]) -> int:
    commands = {"start": start, "status": status}
    if len(argv) != 1 or argv[0] not in commands:
        print(__doc__)
        return 2
    return commands[argv[0]](Path(__file__).resolve().parent, time.time())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
