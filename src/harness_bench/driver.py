"""The ACP cell driver (ADR-0002): one prompt turn with one harness adapter over stdio.

- Bounded line reader: a line over 1 MiB, or more than 20 lines that are not JSON (update banners,
  warnings), is `failed (protocol)`; the reader never grows past one line.
- Strict parse: only JSON objects are messages; responses are matched by id.
- Deny-all permissions: every `session/request_permission` is answered `cancelled` and counted
  (the static profile should make it zero, US-14); any other client request gets -32601.
- Verbatim prompt: the task text is sent exactly as given (US-10).
- Ack barrier: `before_send()` runs after the handshake and before `session/prompt` is written; the
  engine persists `prompt_sent` in it, so a failed append means the prompt is never sent (model
  QueuePromptSent -> PersistPromptSent -> SendPrompt). The driver never retries `session/prompt`.
- The handshake has its own deadline; the turn itself is bounded by the engine, which terminates the
  cell's job at the budget, so the reader sees EOF.

Only this module speaks ACP (design D3 import lint).
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from harness_bench.errors import Cause
from harness_bench.procs import CellProcess

MAX_LINE = 1 << 20
MAX_JUNK = 20
PROTOCOL_VERSION = 1
CLIENT_INFO = {"name": "harness-bench", "version": "1"}


class ProtocolError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class LineParser:
    """Splits a byte stream into JSON-object messages, bounded in line length and junk count."""

    def __init__(self, max_line: int = MAX_LINE, max_junk: int = MAX_JUNK) -> None:
        self.max_line = max_line
        self.max_junk = max_junk
        self.junk = 0
        self._buf = b""

    def _too_long(self) -> ProtocolError:
        self._buf = b""  # the parser is finished; it keeps nothing
        return ProtocolError(f"a line over {self.max_line // (1 << 20) or self.max_line} "
                             f"{'MiB' if self.max_line >= 1 << 20 else 'bytes'} from the adapter")

    def feed(self, data: bytes) -> Iterator[dict]:
        self._buf += data
        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                if len(self._buf) > self.max_line:
                    raise self._too_long()
                return
            line, self._buf = self._buf[:nl], self._buf[nl + 1:]
            if len(line) > self.max_line:
                raise self._too_long()
            try:
                msg = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):  # nesting too deep to parse is junk, not a crash
                msg = None
            if isinstance(msg, dict):
                yield msg
            elif line.strip():
                self.junk += 1
                if self.junk > self.max_junk:
                    raise ProtocolError(f"more than {self.max_junk} non-JSON lines from the adapter")


@dataclass
class TurnResult:
    session_id: str | None = None
    stop_reason: str | None = None
    permission_requests: int = 0
    updates: int = 0
    prompt_sent: bool = False
    eof: bool = False
    cause: Cause | None = None
    detail: str = ""
    handshake_seconds: float = 0.0
    turn_seconds: float = 0.0
    usage: dict | None = None  # the adapter's per-turn usage from the prompt response, if it reports one


class _Eof(Exception):
    pass


class _AcpError(Exception):
    pass


class _Timeout(Exception):
    pass


class _Channel:
    """The adapter's stdio: a reader thread turns stdout into messages on a queue."""

    def __init__(self, cell: CellProcess, result: TurnResult) -> None:
        self.cell = cell
        self.result = result
        self.inbox: queue.Queue = queue.Queue()
        self.seq = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        parser = LineParser()
        stream = self.cell.proc.stdout
        try:
            while True:
                chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
                if not chunk:
                    break
                for msg in parser.feed(chunk):
                    self.inbox.put(("msg", msg))
        except ProtocolError as exc:
            self.inbox.put(("protocol", exc.detail))
            return
        except (OSError, ValueError):
            pass
        self.inbox.put(("eof", None))

    def send(self, obj: dict) -> None:
        try:
            self.cell.proc.stdin.write(json.dumps(obj).encode("utf-8") + b"\n")
            self.cell.proc.stdin.flush()
        except (OSError, ValueError):
            raise _Eof from None

    def rpc(self, method: str, params: dict, deadline: float | None) -> dict:
        self.seq += 1
        rid = self.seq
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            wait = None if deadline is None else deadline - time.monotonic()
            if wait is not None and wait <= 0:
                raise _Timeout(method)
            try:
                kind, payload = self.inbox.get(timeout=wait)
            except queue.Empty:
                raise _Timeout(method) from None
            if kind == "eof":
                raise _Eof
            if kind == "protocol":
                raise ProtocolError(payload)
            msg = payload
            if "method" in msg and "id" in msg:  # a request from the agent
                if msg["method"] == "session/request_permission":
                    self.result.permission_requests += 1
                    self.send({"jsonrpc": "2.0", "id": msg["id"], "result": {"outcome": {"outcome": "cancelled"}}})
                else:
                    self.send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "not supported by harness-bench"}})
            elif "method" in msg:  # a notification
                if msg["method"] == "session/update":
                    self.result.updates += 1
            elif msg.get("id") == rid:
                if "error" in msg:
                    raise _AcpError(json.dumps(msg["error"])[:500])
                return msg.get("result") or {}


def _auth_failure(detail: str) -> bool:
    low = detail.lower()
    return "auth" in low or "login" in low or "credential" in low


def run_turn(cell: CellProcess, cwd: Path, prompt: str, mode: str | None, handshake_timeout: float,
             before_send: Callable[[str | None], None], model: str | None = None) -> TurnResult:
    """Handshake, ack barrier, one verbatim prompt. `before_send` exceptions propagate unsent."""
    result = TurnResult()
    ch = _Channel(cell, result)
    started = time.monotonic()
    deadline = started + handshake_timeout
    try:
        ch.rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "clientCapabilities": {}, "clientInfo": CLIENT_INFO}, deadline)
        created = ch.rpc("session/new", {"cwd": str(cwd), "mcpServers": []}, deadline)
        result.session_id = created.get("sessionId")
        if mode:
            ch.rpc("session/set_mode", {"sessionId": result.session_id, "modeId": mode}, deadline)
        if model:
            ch.rpc("session/set_model", {"sessionId": result.session_id, "modelId": model}, deadline)
    except _Timeout as exc:
        return _fail(result, Cause.handshake_timeout, f"no answer to {exc} within {handshake_timeout} s", started)
    except _Eof:
        result.eof = True
        return _fail(result, Cause.adapter_crash, "the adapter exited during the handshake", started)
    except ProtocolError as exc:
        return _fail(result, Cause.protocol, exc.detail, started)
    except _AcpError as exc:
        cause = Cause.blocked_auth if _auth_failure(str(exc)) else Cause.adapter_crash
        return _fail(result, cause, f"handshake error: {exc}", started)
    result.handshake_seconds = time.monotonic() - started

    before_send(result.session_id)  # the ack barrier: prompt_sent is durable before the prompt goes out
    turn_start = time.monotonic()
    result.prompt_sent = True
    try:
        done = ch.rpc("session/prompt", {"sessionId": result.session_id, "prompt": [{"type": "text", "text": prompt}]}, None)
        result.stop_reason = done.get("stopReason")
        usage, meta = (v if isinstance(v, dict) else None for v in (done.get("usage"), done.get("_meta")))
        if usage is not None or meta is not None:  # either half alone is still the adapter's report
            result.usage = {"usage": usage, "meta": meta}
    except _Eof:
        result.eof = True
        result.cause, result.detail = Cause.adapter_crash, "EOF before end_turn"
    except ProtocolError as exc:
        result.cause, result.detail = Cause.protocol, exc.detail
    except _AcpError as exc:
        result.cause, result.detail = Cause.adapter_crash, f"prompt error: {exc}"
    result.turn_seconds = time.monotonic() - turn_start
    return result


def _fail(result: TurnResult, cause: Cause, detail: str, started: float) -> TurnResult:
    result.cause, result.detail = cause, detail
    result.handshake_seconds = time.monotonic() - started
    return result
