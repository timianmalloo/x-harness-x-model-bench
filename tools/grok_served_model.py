"""Read the model Grok served for one dispatch from its session store (R-92 condition 1).

    python tools/grok_served_model.py <session dir>
    python tools/grok_served_model.py --tree <worker tree path> --session <id> [--root <sessions root>]

The served id is read from the `model_id` field of each `assistant` row in chat_history.jsonl, never from
argv, a model list, the summary, or any text a worker read (a `git log` line naming grok-4.6 is not a served id).
Prints ids and counts only.

Exit 0: every response id starts with the pin and at least one response was read.
Exit 1: a response id does not (each is named with its count), or a response row has no id.
Exit 2: chat_history.jsonl is missing, unreadable or holds no assistant row ("not recorded", never a plausible
pass), a present file is not JSON, or the arguments are bad.
usage.json and summary.json are cross-checks: when absent (a deadline-killed session writes no usage.json) the
line says "(absent)" and the response rows still decide.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

PIN = "grok-4.7"
NONE = "(none)"
ABSENT = "(absent)"
DEFAULT_ROOT = Path.home() / ".grok" / "sessions"


class NotRecorded(Exception):
    """A session-store file is missing or unreadable."""


def _load(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NotRecorded(f"{path.name}: {exc.strerror or exc}") from exc


def _json(path: Path) -> dict:
    try:
        value = json.loads(_load(path))
    except ValueError as exc:
        raise NotRecorded(f"{path.name}: not JSON") from exc
    if not isinstance(value, dict):
        raise NotRecorded(f"{path.name}: not an object")
    return value


def response_ids(history: Path) -> Counter:
    counts: Counter = Counter()
    for number, line in enumerate(_load(history).splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise NotRecorded(f"{history.name}: line {number} is not JSON") from exc
        if isinstance(row, dict) and row.get("type") == "assistant":
            model = row.get("model_id")
            counts[model if isinstance(model, str) and model else NONE] += 1
    return counts


def usage_ids(usage: Path) -> list[str]:
    session = _json(usage).get("session")
    models = session.get("modelUsage") if isinstance(session, dict) else None
    return sorted(models) if isinstance(models, dict) else []


def check(session_dir: Path, pin: str) -> tuple[int, str]:
    if not session_dir.is_dir():
        return 2, f"not recorded: {session_dir} is not a directory\n"
    usage_path = session_dir / "usage.json"
    summary_path = session_dir / "summary.json"
    try:
        responses = response_ids(session_dir / "chat_history.jsonl")
        # usage.json is written only at a clean end (a deadline kill leaves none); summary.json is a
        # cross-check. Absent is not an error: the response rows decide.
        used = usage_ids(usage_path) if usage_path.exists() else None
        current = _json(summary_path).get("current_model_id") if summary_path.exists() else ABSENT
    except NotRecorded as exc:
        return 2, f"not recorded: {exc}\n"
    if not responses:
        return 2, "not recorded: chat_history.jsonl holds no assistant response\n"
    bad = {model: n for model, n in responses.items() if not model.startswith(pin)}
    lines = []
    if used is None:
        lines.append("source=chat_history (usage.json absent)")
    lines += [f"chat_history.jsonl responses: {', '.join(f'{m} x{n}' for m, n in sorted(responses.items()))}",
              f"usage.json models: {ABSENT if used is None else ', '.join(used) or NONE}",
              f"summary.json current_model_id: {current if isinstance(current, str) else NONE}"]
    if bad:
        lines.append(f"FAIL: pin {pin}; served " + ", ".join(f"{m} x{n}" for m, n in sorted(bad.items())))
        return 1, "\n".join(lines) + "\n"
    lines.append(f"OK: every response served {pin}*")
    return 0, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session_dir", nargs="?", type=Path)
    parser.add_argument("--tree", help="worker tree path, as grok recorded it")
    parser.add_argument("--session", help="session id (with --tree)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="sessions root (default ~/.grok/sessions)")
    parser.add_argument("--pin", default=PIN, help=f"required id prefix (default {PIN})")
    parser.add_argument("--first", action="store_true")
    parser.add_argument("--wait", type=float, default=0)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if args.session_dir is not None:
        directory = args.session_dir
    elif args.tree and args.session:
        directory = args.root / quote(args.tree, safe="") / args.session
    else:
        sys.stderr.write("need <session dir>, or --tree and --session\n")
        return 2
    if args.first:
        sys.stdout.write("first response: skeleton\n")
        return 0
    code, text = check(directory, args.pin)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
