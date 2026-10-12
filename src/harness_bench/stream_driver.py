"""The Antigravity stream-json protocol module (ADR-0025 s1, s3): one agy process, several turns, under procs control.

`engine.protocol_module` picks this module for a profile with `transport: agy-stream`. It exposes exactly
`driver.open_session` and `driver.send_turn`'s parameters and return types, so `engine._attempt` passes the same
arguments to either. The architecture rule (tests/test_architecture.py) makes this the only module holding the
stream's input event and its outcome grammar, as `driver.py` is the only one holding ACP's method names.

- The process is the CellProcess the engine spawned through `procs` (containment, peak memory and CPU as for every
  cell); this module never starts one.
- No handshake: agy reads its first `user` line, then writes `init` (the conversation id) and its steps. A turn is one
  `{"event": "user", "message": {"role": "user", "content": <prompt>}}` line; it ends at the turn's `result`
  (measured on agy 1.3.3: one `init` per process, one `result` per turn; tests/fixtures/agy/stream).
- Every stdout byte is teed, unchanged, to `<cell home>/agy-stream.ndjson`, the native record. The sidecar
  `agy-stream.times.jsonl` gives each line's `time.monotonic_ns()` at read (read time, not emit time), joined by line
  index; `read_times` gives `not recorded` when the counts differ. Both are best-effort: a write failure stops that
  file (the stream file is then removed, so a reader finds no record rather than a cut one) and never the cell.
- Line bound: the driver's 8 MiB (`driver.MAX_LINE`; BND-A, one kind of content has one bound). A longer line, bad
  JSON, a non-object line or an event type this table does not name is `failed (protocol)`.
- Outcomes (ADR-0025 s3), checked the way the oracle checks them (coord_transport.py `_Session.agy`, tests/
  test_agy_oracle.py):

  | stream shows | here |
  | --- | --- |
  | `result.status == "SUCCESS"`, empty `denied_actions` | a TurnRecord, stop reason `end_turn` |
  | `result.status != "SUCCESS"` | a TurnRecord whose stop reason is the status (the engine classifies it) |
  | non-empty `denied_actions`, or a tool ERROR starting `permission check failed for ` | `Cause.blocked_denied` |
  | five consecutive native tool errors | `STREAK_CAUSE` (`NATIVE_ERROR_STREAK_CAP`) |
  | unknown event type, or bad JSON | `Cause.protocol` |
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from time import monotonic_ns as _read_ns

from harness_bench.driver import MAX_LINE, Session, TurnRecord, TurnResult, cell_home
from harness_bench.errors import Cause
from harness_bench.procs import CellProcess

STREAM_RECORD = "agy-stream.ndjson"
TIMES_RECORD = "agy-stream.times.jsonl"
DENIAL_PREFIX = "permission check failed for "
# coord_transport.NATIVE_ERROR_STREAK_CAP, pinned equal by tests/test_stream_driver.py: this many ERROR steps with no
# DONE step between them end the cell.
NATIVE_ERROR_STREAK_CAP = 5
# assume: an agy tool-error loop is a harness-side failure until the taxonomy names it. Confirm: the decision request
# R-TRANSPORT handed back (no HB-CELL code names the streak). Breaks: a streak is scored against the harness.
STREAK_CAUSE = Cause.adapter_crash
_ID = re.compile(r"[A-Za-z0-9._:/+-]{1,256}")  # coord_transport._identifier: the conversation and action id shape
log = logging.getLogger("harness_bench.stream_driver")



def read_times(stream: Path) -> tuple[list[int] | None, str | None]:
    """Each stream line's read time (`time.monotonic_ns()`), by line index; (None, reason) when the sidecar is absent,
    unreadable or holds another count than the stream has lines (ADR-0025 s3): never a guessed join."""
    sidecar = stream.with_name(TIMES_RECORD)
    try:
        lines = stream.read_bytes().count(b"\n")
        rows = [json.loads(row) for row in sidecar.read_bytes().splitlines()]
        times = [row["mono_ns"] for row in rows if isinstance(row, dict) and isinstance(row.get("mono_ns"), int)]
    except (OSError, ValueError, KeyError) as exc:
        return None, f"not recorded: line-time sidecar unreadable ({type(exc).__name__})"
    if len(times) != len(rows) or len(times) != lines:
        return None, f"not recorded: the sidecar has {len(rows)} times for {lines} stream lines"
    return times, None


class _Tee:
    """The raw stream and its line times, written as read. Best-effort: a failure stops the file and is logged."""

    def __init__(self, home: Path) -> None:
        self.stream_path = home / STREAM_RECORD
        self.stream = self.times = None
        self.line = 0
        try:
            self.stream = self.stream_path.open("wb")
            self.times = (home / TIMES_RECORD).open("w", encoding="utf-8", newline="\n")
        except OSError as exc:
            self._stop("open", exc)

    def _stop(self, what: str, exc: OSError) -> None:
        log.warning("agy stream record not kept", extra={"step": what, "detail": str(exc)})
        for f in (self.stream, self.times):
            try:
                if f is not None:
                    f.close()
            except OSError:
                pass
        self.stream = self.times = None
        try:
            self.stream_path.unlink(missing_ok=True)  # no record, rather than a cut one read as complete
        except OSError:
            pass

    def chunk(self, data: bytes, line_times: list[int]) -> None:
        if self.stream is None:
            return
        try:
            self.stream.write(data)
            self.stream.flush()
            for ns in line_times:
                self.times.write(json.dumps({"line": self.line, "mono_ns": ns}) + "\n")
                self.line += 1
            self.times.flush()
        except OSError as exc:
            self._stop("write", exc)

    def close(self) -> None:
        for f in (self.stream, self.times):
            try:
                if f is not None:
                    f.close()
            except OSError:
                pass
        self.stream = self.times = None


class _Channel:
    """agy's stdio: a reader thread tees stdout and turns its lines into events on a queue."""

    def __init__(self, cell: CellProcess, result: TurnResult, home: Path, cancel: threading.Event | None) -> None:
        self.cell, self.result, self.cancel = cell, result, cancel
        self.cancel_handled = False
        self.inbox: queue.Queue = queue.Queue()
        self.tee = _Tee(home)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        stream, buf = self.cell.proc.stdout, b""
        try:
            while True:
                data = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
                if not data:
                    break
                buf += data
                lines = buf.split(b"\n")
                buf = lines.pop()
                self.tee.chunk(data, [_read_ns()] * len(lines))
                if max(map(len, lines), default=0) > MAX_LINE or len(buf) > MAX_LINE:  # complete or still partial
                    self.inbox.put(("protocol", "a line over 8 MiB from agy"))
                    return
                for line in lines:
                    self.inbox.put(("line", line))
        except (OSError, ValueError):
            pass
        finally:
            self.tee.close()
        self.inbox.put(("protocol", "a partial line at the end of the stream") if buf else ("eof", None))

    def observe_cancel(self) -> bool:
        """A set cancel closes agy's input once (it exits at stdin EOF); the engine's kill still owns termination."""
        if self.cancel is None or not self.cancel.is_set():
            return False
        if not self.cancel_handled:
            self.cancel_handled = True
            try:
                self.cell.proc.stdin.close()
            except (OSError, ValueError):
                pass
        return True

    def pending(self) -> bool:
        return not self.inbox.empty()


class _StreamSession(Session):
    def close(self) -> None:
        if self.closed:
            return
        super().close()  # closes stdin: agy ends at EOF
        self.channel.reader.join(timeout=2.0)  # the last lines reach the tee before the engine reads the record


class _Turn:
    """One turn's reading of the stream: returns "result" at the turn's end, else None; raises _Stop to end the cell."""

    def __init__(self, session: Session, turn_start: float, on_first_update: Callable[[], None] | None) -> None:
        self.result = session.result
        self.session = session
        self.turn_start = turn_start
        self.on_first_update = on_first_update

    def step(self, event: dict) -> dict | None:
        kind, result = event.get("event"), self.result
        if kind == "init":
            cid = event.get("conversation_id")
            if not isinstance(cid, str) or not _ID.fullmatch(cid) or result.session_id not in (None, cid):
                raise _Stop(Cause.protocol, "init without a valid, stable conversation_id")
            result.session_id = cid
            init = event.get("init") if isinstance(event.get("init"), dict) else {}
            mode = init.get("permission_mode")
            result.permission_mode_effective = mode if isinstance(mode, str) else None  # R-34: what agy reports
            return None
        if kind == "step_update":
            return self._step(event.get("step_update"))
        if kind == "result":
            return self._result(event.get("result"))
        raise _Stop(Cause.protocol, f"unknown agy event {str(kind)[:60]!r}")

    def _step(self, step) -> None:
        result = self.result
        if not isinstance(step, dict) or ("conversation_id" in step and (
                not result.session_id or step["conversation_id"] != result.session_id)):
            raise _Stop(Cause.protocol, "step_update outside the session")
        result.updates += 1
        first, self.on_first_update = self.on_first_update, None
        if first is not None:
            first()
        result.last_update_seconds = time.monotonic() - self.turn_start
        if step.get("state") == "ERROR":
            info = step.get("tool_info", {})
            if (not result.session_id or step.get("conversation_id") != result.session_id or not isinstance(info, dict)
                    or not isinstance(info.get("error", {}), dict)):
                raise _Stop(Cause.protocol, "an ERROR step without its session or error object")
            error = info.get("error", {})
            message = error.get("message", "")
            if (step.get("step_type") == "tool" and error.get("type") == "TOOL_ERROR" and isinstance(message, str)
                    and message.startswith(DENIAL_PREFIX)):
                raise _Stop(Cause.blocked_denied, message[:200])
            self.session.error_streak += 1
            if self.session.error_streak >= NATIVE_ERROR_STREAK_CAP:
                raise _Stop(STREAK_CAUSE, f"{NATIVE_ERROR_STREAK_CAP} consecutive native tool errors "
                                          "(NATIVE_ERROR_STREAK_CAP)")
        elif step.get("state") == "DONE":
            self.session.error_streak = 0

    def _result(self, body) -> dict:
        result = self.result
        if not isinstance(body, dict) or not result.session_id or body.get("conversation_id") != result.session_id:
            raise _Stop(Cause.protocol, "a result outside the session")
        denied = body.get("denied_actions", [])
        if not isinstance(denied, list) or any(not isinstance(item, dict) or not isinstance(item.get("action"), str)
                                               or not _ID.fullmatch(item["action"]) for item in denied):
            raise _Stop(Cause.protocol, "denied_actions is not a list of actions")
        if denied:
            raise _Stop(Cause.blocked_denied, "denied_actions: " + ", ".join(item["action"] for item in denied)[:200])
        self.session.error_streak = 0
        return body


class _Stop(Exception):
    def __init__(self, cause: Cause, detail: str) -> None:
        super().__init__(detail)
        self.cause, self.detail = cause, detail


def open_session(cell: CellProcess, cwd: Path, mode: str | None, handshake_timeout: float,
                 model: str | None = None, result: TurnResult | None = None,
                 mcp_servers: list[dict] | None = None, cancel: threading.Event | None = None,
                 session_meta: dict | None = None) -> Session | None:
    """Start reading agy's stream; None means the supplied result carries the cause. agy takes its model in argv and
    has no session mode, MCP-server or session `_meta` input on the stream, so each is refused rather than dropped."""
    result = result if result is not None else TurnResult()
    if mode or model or mcp_servers or session_meta:
        result.cause = Cause.adapter_crash
        result.detail = ("agy-stream takes no session mode, model pin, MCP servers or session _meta (the profile's "
                         "argv carries the model)")
        return None
    session = _StreamSession(_Channel(cell, result, cell_home(cwd), cancel), cwd, mode, handshake_timeout, model,
                             mcp_servers)
    session.error_streak = 0
    return session


def send_turn(session: Session, prompt: str, before_send: Callable[[str | None], None], turn: int,
              on_first_update: Callable[[], None] | None = None) -> TurnRecord | None:
    """Send one `user` line and read to the turn's `result`; None means result.cause is set (or the cell was
    cancelled before the prompt). The engine's snapshot runs between turns."""
    ch, result = session.channel, session.result
    if session.closed:
        result.cause, result.detail = Cause.adapter_crash, "send after session close"
        return None
    result.last_update_seconds = None
    if turn > 1 and ch.pending():  # coord_transport: output waiting at a turn boundary cannot answer an unsent prompt
        result.cause, result.detail = Cause.protocol, "agy output waiting before the next turn was sent"
        return None
    before_send(result.session_id)  # the ack barrier: prompt_sent is durable before the prompt goes out
    if ch.observe_cancel():
        return None
    turn_start = time.monotonic()
    line = {"event": "user", "message": {"role": "user", "content": prompt}}
    try:
        ch.cell.proc.stdin.write(json.dumps(line, ensure_ascii=False).encode("utf-8") + b"\n")
        ch.cell.proc.stdin.flush()
    except (OSError, ValueError):
        result.eof = True
        result.cause, result.detail = Cause.adapter_crash, "agy closed its input before the prompt"
        result.turn_seconds = time.monotonic() - turn_start
        return None
    result.prompt_sent = True
    reading = _Turn(session, turn_start, on_first_update)
    body = None
    try:
        while body is None:
            ch.observe_cancel()
            try:
                kind, payload = ch.inbox.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "eof":
                result.eof = True
                raise _Stop(Cause.adapter_crash, "EOF before the turn's result")
            if kind == "protocol":
                raise _Stop(Cause.protocol, payload)
            try:
                event = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):
                raise _Stop(Cause.protocol, "a line that is not JSON from agy") from None
            if not isinstance(event, dict):
                raise _Stop(Cause.protocol, "a line that is not a JSON object from agy")
            body = reading.step(event)
    except _Stop as stop:
        result.cause, result.detail = stop.cause, stop.detail
    result.turn_seconds = time.monotonic() - turn_start
    if result.cause is not None:
        return None
    status = body.get("status")
    result.stop_reason = "end_turn" if status == "SUCCESS" else str(status)
    usage = body.get("usage")
    result.usage = {"usage": usage, "meta": None} if isinstance(usage, dict) else None
    rec = TurnRecord(turn, result.stop_reason, result.turn_seconds, result.usage, result.last_update_seconds)
    result.turns.append(rec)
    return rec
