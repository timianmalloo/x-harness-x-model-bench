"""Read the model Grok served for one dispatch from its session store (R-92 condition 1).

    python tools/grok_served_model.py <session dir>
    python tools/grok_served_model.py --tree <worker tree path> [--session <id>] [--root <sessions root>]

The served id is read from the `model_id` field of each `assistant` row in chat_history.jsonl, never from
argv, a model list, the summary, or any text a worker read (a `git log` line naming grok-4.6 is not a served id).
Prints ids and counts only.

Exit 0: every response id starts with the pin and at least one response was read.
Exit 1: a response id does not (each is named with its count), or a response row has no id.
Exit 2: chat_history.jsonl is missing, unreadable or holds no assistant row ("not recorded", never a plausible
pass), a present file is not JSON, or the arguments are bad.
--first [--wait SECONDS] (R-103 condition 3, the fast kill): reads only the FIRST assistant row of
chat_history.jsonl (never usage.json or summary.json, never past that row) and prints
`first response: <model_id> (row <n>; ...)`. The rows carry no time field, so the file mtime is printed and said so.
Exit 0: the id starts with the pin. Exit 1: it does not, or the row has no id (`FAIL: pin ...`).
Exit 2: the file is missing or holds no assistant row yet. --wait polls every 2 s while the result would be 2,
for at most SECONDS (default 0); `--first --wait 120` is the Leader's one-line read. This is the fast check, not
the proof: the join mode above stays the proof and is unchanged.

usage.json and summary.json are cross-checks: when absent (a deadline-killed session writes no usage.json) the
line says "(absent)" and the response rows still decide.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

POLL_SECONDS = 2
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


def first_response(history: Path) -> tuple[int, str | None] | None:
    """(row number, model_id or None) of the first assistant row, or None; reads no further."""
    try:
        with history.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a half-written last line; the next poll sees it whole
                if isinstance(row, dict) and row.get("type") == "assistant":
                    model = row.get("model_id")
                    return number, model if isinstance(model, str) and model else None
    except OSError:
        return None
    return None


def first_check(session_dir: Path, pin: str, wait: float = 0) -> tuple[int, str]:
    history = session_dir / "chat_history.jsonl"
    deadline = time.monotonic() + wait
    found = first_response(history)
    while found is None and time.monotonic() < deadline:
        time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))
        found = first_response(history)
    if found is None:
        return 2, "not recorded: no assistant row in chat_history.jsonl yet\n"
    number, model = found
    # The rows carry no time field (fixtures are copies of the real shape), so the file mtime stands in.
    stamp = datetime.fromtimestamp(history.stat().st_mtime, UTC).isoformat(timespec="seconds")
    line = f"first response: {model or NONE} (row {number}; no time field in row, file mtime {stamp})\n"
    if model is None or not model.startswith(pin):
        return 1, line + f"FAIL: pin {pin}; first response {model or NONE}\n"
    return 0, line


def _same_path(left: str, right: str) -> bool:
    """True when both spellings are one path after URL-decoding.

    Grok names the store folder with the tree path's backslashes, URL-encoded.
    ``--tree`` may use forward slashes. Both sides go through
    ``os.path.normcase(os.path.normpath(unquote(name)))``.
    """
    return os.path.normcase(os.path.normpath(unquote(left))) == os.path.normcase(os.path.normpath(unquote(right)))


def _summary(folder: Path) -> dict | None:
    path = folder / "summary.json"
    if not path.is_file():
        return None
    try:
        return _json(path)
    except NotRecorded:
        return None


def resolve_tree_session(root: Path, tree: str, session: str | None) -> Path | None:
    """The session folder Grok keyed by its own path and its own id.

    A ``--session`` that names a folder under that key is that folder. Any other
    id, including none, is the newest session whose ``summary.json`` ``info.cwd``
    is this tree (``updated_at``, UTC ISO-8601). A folder with no summary is skipped.
    """
    if not root.is_dir():
        return None
    key_dir = None
    for child in root.iterdir():
        if child.is_dir() and _same_path(child.name, tree):
            key_dir = child
            break
    if key_dir is None:
        return None
    if session:
        named = key_dir / session
        if named.is_dir():
            return named
    best: Path | None = None
    best_stamp = ""
    for child in key_dir.iterdir():
        if not child.is_dir():
            continue
        summary = _summary(child)
        if summary is None:
            continue
        info = summary.get("info")
        cwd = info.get("cwd") if isinstance(info, dict) else None
        if not isinstance(cwd, str) or not _same_path(cwd, tree):
            continue
        stamp = summary.get("updated_at")
        stamp_s = stamp if isinstance(stamp, str) else ""
        if best is None or stamp_s > best_stamp:
            best = child
            best_stamp = stamp_s
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session_dir", nargs="?", type=Path)
    parser.add_argument("--tree", help="worker tree path, as grok recorded it")
    parser.add_argument("--session", help="session folder under the tree (optional; else the newest)")
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
    elif args.tree:
        found = resolve_tree_session(args.root, args.tree, args.session)
        if found is None:
            sys.stdout.write("not recorded: no session store for this tree\n")
            return 2
        directory = found
    else:
        sys.stderr.write("need <session dir>, or --tree\n")
        return 2
    if args.first:
        code, text = first_check(directory, args.pin, args.wait)
    else:
        code, text = check(directory, args.pin)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
