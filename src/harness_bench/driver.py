"""The ACP cell driver (ADR-0002): one prompt turn with one harness adapter over stdio.

- Bounded line reader: a line over 1 MiB, or more than 20 lines that are not JSON (update banners,
  warnings), is `failed (protocol)`; the reader never grows past one line.
- Strict parse: only JSON objects are messages; responses are matched by id.
- Deny-all permissions: every `session/request_permission` is answered `cancelled` and counted
  (the static profile should make it zero, US-14); any other client request gets -32601.
- Verbatim prompt: the task text is sent exactly as given (US-10).
- Optional model pin: `session/set_model` right after `session/new`, only when the caller passes `model=`; a
  refusal is `failed (model unavailable)` and the prompt is never sent (ADR-0003, R-13, R-18).
- Ack barrier: `before_send()` runs after the handshake and before `session/prompt` is written; the
  engine persists `prompt_sent` in it, so a failed append means the prompt is never sent (model
  QueuePromptSent -> PersistPromptSent -> SendPrompt). The driver never retries `session/prompt`.
- The handshake has its own deadline; the engine cancels a turn at its budget, then terminates the
  cell's job after the profile's bounded grace if the adapter has not exited.

Only this module speaks ACP (design D3 import lint).
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from harness_bench.errors import Cause
from harness_bench.procs import CellProcess
from harness_bench.telemetry import ProviderError, normalize

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
    # assume: "last update" (seam req-01M38KX8503601BEP857749VVF) is on the turn clock of turn_seconds: seconds from
    # the prompt being sent to the last session/update read in the turn, so 0 <= it <= turn_seconds. Confirm: the
    # engine test pairs 2.0 with turn 2.5 (test_engine.py:1067). Breaks: a reader that expects the handshake clock.
    # Null (not recorded, never 0) when the turn read no session/update; handshake-time updates do not set it.
    last_update_seconds: float | None = None
    agent_version: str | None = None  # initialize.agentInfo.version, verbatim (R-28); null when not reported
    # R-34: the mode the session reports (session/new modes.currentModeId, after the adapter's own fallback), or the
    # mode a session/set_mode it accepted; null when not reported, never the profile's declared mode
    permission_mode_effective: str | None = None


class _Eof(Exception):
    pass


class _AcpError(Exception):
    def __init__(self, error) -> None:
        super().__init__(json.dumps(error)[:500])
        self.error = error if isinstance(error, dict) else {}


class _Timeout(Exception):
    pass


class _Channel:
    """The adapter's stdio: a reader thread turns stdout into messages on a queue."""

    def __init__(self, cell: CellProcess, result: TurnResult, cancel: threading.Event | None = None) -> None:
        self.cell = cell
        self.result = result
        self.cancel = cancel
        self.cancel_handled = False
        self.inbox: queue.Queue = queue.Queue()
        self.seq = 0
        self.turn_start: float | None = None  # set when the prompt is sent
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

    def _observe_cancel(self, prompt_in_flight: bool) -> bool:
        if self.cancel is None or not self.cancel.is_set():
            return False
        if not self.cancel_handled:
            self.cancel_handled = True
            if prompt_in_flight and self.result.session_id:
                try:
                    self.cell.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "session/cancel",
                                                           "params": {"sessionId": self.result.session_id}}).encode("utf-8") + b"\n")
                    self.cell.proc.stdin.flush()
                except (OSError, ValueError):
                    pass  # the hard deadline still owns termination
            try:
                self.cell.proc.stdin.close()
            except (OSError, ValueError):
                pass
        return True

    def send(self, obj: dict) -> bool:
        if self.cancel_handled or (self.cancel is not None and self.cancel.is_set()):
            return False  # late permission replies never turn a graceful cancel into _Eof
        try:
            self.cell.proc.stdin.write(json.dumps(obj).encode("utf-8") + b"\n")
            self.cell.proc.stdin.flush()
        except (OSError, ValueError):
            raise _Eof from None
        return True

    def rpc(self, method: str, params: dict, deadline: float | None) -> dict:
        self.seq += 1
        rid = self.seq
        if not self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}):
            self._observe_cancel(False)
            raise _Eof
        if method == "session/prompt":
            self.result.prompt_sent = True
        while True:
            if self._observe_cancel(method == "session/prompt") and method != "session/prompt":
                raise _Eof
            wait = None if deadline is None else deadline - time.monotonic()
            if wait is not None and wait <= 0:
                raise _Timeout(method)
            try:
                kind, payload = self.inbox.get(timeout=min(wait, 0.2) if wait is not None else 0.2)
            except queue.Empty:
                continue
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
                    if self.turn_start is not None:
                        self.result.last_update_seconds = time.monotonic() - self.turn_start
            elif msg.get("id") == rid:
                if "error" in msg:
                    raise _AcpError(msg["error"])
                return msg.get("result") or {}


def _auth_failure(detail: str) -> bool:
    low = detail.lower()
    return "auth" in low or "login" in low or "credential" in low


# assume: an adapter reports a provider's HTTP status as "API Error: <status>" in the JSON-RPC error message and its
# type as data.errorKind. Confirm: the one measured form, claude-agent-acp 0.79.0 refusing claude-opus-5-5
# (tests/fixtures/acp/recordings/claude-code-x1-model-unsupported.jsonl). Breaks: another adapter's form is not
# parsed, so its error stays adapter_crash with the text in detail (R-18 condition 2), never a guessed cause.
_API_STATUS = re.compile(r"\bAPI Error: (\d{3})\b")


def _prompt_error_cause(exc: _AcpError) -> Cause:
    """R-23: a prompt-time error with a status or a provider type goes through the native-record classifier
    (`normalize.classify`, one classifier for both paths); an auth failure keeps its precedence; an error with
    neither status nor type is adapter_crash."""
    if _auth_failure(str(exc)):
        return Cause.blocked_auth
    message = exc.error.get("message") if isinstance(exc.error.get("message"), str) else ""
    data = exc.error.get("data") if isinstance(exc.error.get("data"), dict) else {}
    found = _API_STATUS.search(message)
    status = int(found.group(1)) if found else None
    error_type = data.get("errorKind") if isinstance(data.get("errorKind"), str) else ""
    if status is None and not error_type:
        return Cause.adapter_crash
    return normalize.classify([ProviderError(0, status, error_type, message[:300])]) or Cause.adapter_crash


def run_turn(cell: CellProcess, cwd: Path, prompt: str, mode: str | None, handshake_timeout: float,
             before_send: Callable[[str | None], None], model: str | None = None,
             result: TurnResult | None = None, mcp_servers: list[dict] | None = None,
             cancel: threading.Event | None = None) -> TurnResult:
    """Handshake, ack barrier, one verbatim prompt. `before_send` exceptions propagate unsent.

    `model`: sent with `session/set_model` right after `session/new` (the ADR-0003 pin, for a profile that sets it);
    a refusal is `model_unavailable` by step, whatever its text, and the prompt is never sent (R-18).
    `result`: a TurnResult the caller supplies and can read in `before_send` (agent_version, R-28).
    `cancel`: an engine-owned event observed on this worker thread; it closes stdin and sends the ACP
    notification only while a prompt is in flight."""
    result = result if result is not None else TurnResult()
    ch = _Channel(cell, result, cancel)
    started = time.monotonic()
    deadline = started + handshake_timeout
    try:
        init = ch.rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "clientCapabilities": {}, "clientInfo": CLIENT_INFO}, deadline)
        info = init.get("agentInfo")
        version = info.get("version") if isinstance(info, dict) else None
        result.agent_version = version if isinstance(version, str) else None  # verbatim; null when not reported
        created = ch.rpc("session/new", {"cwd": str(cwd), "mcpServers": mcp_servers or []}, deadline)
        result.session_id = created.get("sessionId")
        modes = created.get("modes") if isinstance(created.get("modes"), dict) else {}
        current = modes.get("currentModeId")
        result.permission_mode_effective = current if isinstance(current, str) else None
        if model:
            try:
                ch.rpc("session/set_model", {"sessionId": result.session_id, "modelId": model}, deadline)
            except _AcpError as exc:  # tagged by step: the plan's model is not served here
                return _fail(result, Cause.model_unavailable, f"set_model refused: {exc}", started)
        if mode:
            ch.rpc("session/set_mode", {"sessionId": result.session_id, "modeId": mode}, deadline)
            result.permission_mode_effective = mode  # accepted: a refusal raised _AcpError above
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
    if cancel is not None and cancel.is_set():
        ch._observe_cancel(False)
        return result
    turn_start = ch.turn_start = time.monotonic()
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
        result.cause, result.detail = _prompt_error_cause(exc), f"prompt error: {exc}"
    result.turn_seconds = time.monotonic() - turn_start
    return result


def _fail(result: TurnResult, cause: Cause, detail: str, started: float) -> TurnResult:
    result.cause, result.detail = cause, detail
    result.handshake_seconds = time.monotonic() - started
    return result
