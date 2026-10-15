"""The task queue an interactive session works through (stdlib only; copied into each arm as `.bench/next.py`).

Run with no argument, it closes the open item (end time; a turn-1 item of a two-turn task also snapshots its task folder
into `.bench/snapshots/<task>/turn-1/`, the tree the rework grader reads) and prints the next item's prompt, or
`ALL DONE`. `--status` prints the open item again without advancing. The queue is `.bench/queue.json` (written by
`bench interactive prepare`); progress is `.bench/state.json`. Each call is a tool call in the session's own record, so
the calls are the task boundaries `bench interactive collect` splits the record on.

The call that closes the last item also starts `.bench/grade.json`'s command (the arm's `bench interactive collect
--open`), detached so it outlives the tool call, its output to the log the file names. It prints nothing about it: the
session is not told it is graded. state.json records the start, or why it did not start.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ARM = BENCH.parent
SKIP = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "node_modules")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load(name: str, default):
    path = BENCH / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _save(state: dict) -> None:
    tmp = BENCH / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(BENCH / "state.json")


def _grade() -> dict:
    """Start the arm's grading detached; returns what state.json records about it."""
    spec = _load("grade.json", None)
    if spec is None:
        return {"note": "no grade.json"}
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}  # a venv the session activated is not the bench's
    if sys.platform == "win32":
        # A new hidden console and process group, out of the CLI's job when the job allows it, so the grading survives
        # the tool call and the CLI's exit. A job that forbids breakaway refuses the flag: start inside it then.
        base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        attempts = [{"creationflags": base | subprocess.CREATE_BREAKAWAY_FROM_JOB}, {"creationflags": base}]
    else:
        attempts = [{"start_new_session": True}]
    error = None
    try:
        with open(spec["log"], "ab") as log:
            for flags in attempts:
                try:
                    proc = subprocess.Popen(spec["argv"], cwd=spec["cwd"], env=env, stdin=subprocess.DEVNULL, stdout=log,
                                            stderr=subprocess.STDOUT, **flags)
                    return {"started": _now(), "pid": proc.pid, "log": spec["log"]}
                except OSError as exc:
                    error = str(exc)
    except OSError as exc:  # the log cannot be opened
        error = str(exc)
    return {"error": error, "log": spec["log"]}


def _show(items: list, i: int) -> None:
    item = items[i]
    folder = ARM / "tasks" / item["task"]
    turn = f" (turn {item['turn']} of {item['turns']})" if item["turns"] > 1 else ""
    print(f"=== TASK {i + 1} of {len(items)}: {item['task']}{turn} ===")
    print(f"Working folder: {folder}")
    print("Treat that folder as the project root for this task. Change files only inside it.")
    print()
    print(item["prompt"].rstrip())
    print()
    print(f"When this task is finished, run: python {BENCH / 'next.py'}")


def main(argv: list[str]) -> int:
    items = _load("queue.json", {})["items"]
    state = _load("state.json", {"done": [], "open": None})
    if argv[1:] == ["--status"]:
        if state["open"] is None:
            print("ALL DONE." if len(state["done"]) == len(items) else "No task is open. Run next.py to start the next one.")
        else:
            _show(items, state["open"]["index"])
        return 0
    if argv[1:]:
        print("usage: python next.py [--status]", file=sys.stderr)
        return 2
    opened = state["open"]
    if opened is not None:
        item = items[opened["index"]]
        if item["turns"] > 1 and item["turn"] < item["turns"]:
            dest = BENCH / "snapshots" / item["task"] / f"turn-{item['turn']}"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(ARM / "tasks" / item["task"], dest, ignore=SKIP)
        state["done"].append(opened | {"end": _now()})
        state["open"] = None
    index = len(state["done"])
    if index >= len(items):
        if opened is not None:  # this call closed the last item: once per arm
            state["grading"] = _grade()
        _save(state)
        print(f"ALL DONE. {len(items)} of {len(items)} tasks finished. Stop here.")
        return 0
    state["open"] = {"index": index, "task": items[index]["task"], "turn": items[index]["turn"], "start": _now()}
    _save(state)
    _show(items, index)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
