"""The scripted-user log (design section 8), schema bench-scripted-user-log/1: one file per scenario-1 cell.

Grain: one `call` row is exactly one `ask_user` call in one cell. The server writes `header`, `initialize`,
`tools_listed` and one `call` row per call, each flushed before its reply is sent, under one lock that also assigns
`seq`. The server gets no clean EOF, so the engine closes the log after the turn with `close_log`, which writes the
`end` row: "no question asked" (the tool was listed, nothing was asked: an assume, scored) is kept apart from "tool not
reached" (never listed: the clarification metrics are NOT_RECORDED, never 0). Rows are JSON with ensure_ascii, so a
question holding a lone surrogate is still written.

In wave 2 the log is also the match store (section 7.3): a re-grade under the same matcher version reads the stored
decision for its (question hash, clarification-set hash, matcher version) key and never re-matches (R-39 c3, R-53).
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

from harness_bench.errors import BenchError
from harness_bench.scripted_user import matcher
from harness_bench.scripted_user.matcher import MATCHER_VERSION, MatchResult

SCHEMA = "bench-scripted-user-log/1"
LOG_ENV = "SCRIPTED_USER_LOG"


def _line(row: dict) -> str:
    return json.dumps(row, ensure_ascii=True) + "\n"


def header_row(task: str | None, clarifications_sha256: str, matcher_version: str = MATCHER_VERSION, **extra) -> dict:
    """The header: the server writes it at start; the engine writes one from the plan when the server did not."""
    return {"kind": "header", "schema": SCHEMA, "task": task, "clarifications_sha256": clarifications_sha256,
            "matcher_version": matcher_version, **extra}


class LogWriter:
    """Appends rows; each row is written and closed (so flushed) before the call returns."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self.path = Path(path)
        self._clock = clock
        self._start = clock()
        self._lock = threading.Lock()
        self._seq = 0

    def _append(self, row: dict) -> dict:
        with open(self.path, "a", encoding="ascii", newline="\n") as f:
            f.write(_line(row))
        return row

    def _write(self, row: dict) -> dict:
        with self._lock:
            return self._append(row)

    def header(self, cset, log_source: str) -> dict:
        return self._write(header_row(cset.task, cset.sha256, log_source=log_source))

    def refused(self, code: str, message: str) -> dict:
        """The server refused to start (design section 6: fail closed at load); the tool is then never listed."""
        return self._write({"kind": "refused", "code": code, "message": message})

    def initialize(self, client, protocol_version: str, requested) -> dict:
        return self._write({"kind": "initialize", "client": client, "protocol_version": protocol_version,
                            "requested_protocol_version": requested})

    def tools_listed(self) -> dict:
        return self._write({"kind": "tools_listed"})

    def call(self, question, result: MatchResult, reply: str, cset) -> dict:
        with self._lock:
            self._seq += 1
            row = {"kind": "call", "seq": self._seq, "t": round(self._clock() - self._start, 3), "question": question,
                   "question_sha256": matcher.question_sha256(question), "clarifications_sha256": cset.sha256,
                   "matcher_version": MATCHER_VERSION, "decision": result.decision(), "reply": reply}
            if result.invalid is not None:
                row["invalid"] = result.invalid
            return self._append(row)


def read_rows(text: str) -> tuple[list[dict], bool]:
    """The complete rows, and whether a torn last line was dropped. A row is a line ending in a newline; the server
    writes each row in one write, so a last line without one is torn (the server was killed mid-write, before the
    reply was sent) and is not a row."""
    *complete, tail = text.split("\n")
    rows = []
    for n, line in enumerate(complete, 1):
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if not isinstance(row, dict):
            raise BenchError("HB-USR-002", f"scripted-user log line {n} is not a JSON object")
        rows.append(row)
    return rows, tail != ""


def end_row(rows: list[dict], torn_tail: bool) -> dict:
    """The `end` row. With zero calls: "no question asked" when the tool was listed, else "tool not reached"."""
    kinds = [r.get("kind") for r in rows]
    calls = kinds.count("call")
    row = {"kind": "end", "calls": calls, "client_initialized": "initialize" in kinds,
           "tool_listed": "tools_listed" in kinds}
    if calls == 0:
        row["note"] = "no question asked" if row["tool_listed"] else "tool not reached"
    if torn_tail:
        row["torn_tail"] = True
    return row


def close_log(path: Path, header: dict) -> dict:
    """Write the `end` row after the turn (the engine's step; the server is gone by then). A missing file or header
    gets `header` first, and a torn tail is dropped, so the log is never absent or empty. Returns the end row."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rows, torn = read_rows(text)
    end = end_row(rows, torn)
    has_header = any(r.get("kind") == "header" for r in rows)
    if torn or not has_header:
        complete = text[: text.rfind("\n") + 1]
        path.write_bytes(((_line(header) if not has_header else "") + complete + _line(end)).encode("utf-8"))
    else:
        with open(path, "a", encoding="ascii", newline="\n") as f:
            f.write(_line(end))
    return end


def stored_decisions(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    """The match store: key -> the stored decision. The same key always yields the same decision (design section 3)."""
    store: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        if r.get("kind") != "call":
            continue
        key = (r["question_sha256"], r["clarifications_sha256"], r["matcher_version"])
        if key in store and store[key] != r["decision"]:
            raise BenchError("HB-USR-002", f"call seq {r['seq']}: a second decision for one match key")
        store[key] = r["decision"]
    return store


def decide(question, cset, store: dict[tuple[str, str, str], dict]) -> dict:
    """A re-grade's decision: the stored one for this key; only a key the store lacks (another matcher version, R-52
    c4) gets a new match, under its own key."""
    key = matcher.cache_key(question, cset.sha256)
    if key in store:
        return store[key]
    return matcher.match(question, cset.clarifications).decision()
