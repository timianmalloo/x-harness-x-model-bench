"""The ACP cell driver (ADR-0002): one prompt turn with one harness adapter over stdio.

- Bounded line reader: a line over 8 MiB, or more than 20 lines that are not JSON (update banners,
  warnings), is `failed (protocol)`; the reader never grows past one line. 8 MiB (raised from 1 MiB,
  HB-CELL-107 fix, 2026-10-02) is measured, not guessed: grid-3's own archived evidence has a Claude
  Code image tool_result (base64 PNG) at 1.0-1.3 MiB and a Codex CommandExecution's full
  `--verbosity detailed` stdout at 2.3 MiB, both legitimate single tool-result lines, not malformed
  input -- the old 1 MiB bound failed the whole turn on them. 8 MiB keeps a >3x margin over the
  largest measured line while staying a hard ceiling (`PHASE1_MAX_PARALLELISM` caps concurrent cells
  at 4, so worst case is 32 MiB of buffered line data, trivial against host memory).
- Strict parse: only JSON objects are messages; responses are matched by id.
- Deny-all permissions: every `session/request_permission` is answered `cancelled` and counted
  (the static profile should make it zero, US-14); any other client request gets -32601.
- Verbatim prompt: the task text is sent exactly as given (US-10).
- Optional model pin: `session/set_model` right after `session/new`, only when the caller passes `model=`; a
  refusal is `failed (model unavailable)` and the prompt is never sent (ADR-0003, R-13, R-18). An answer that carries
  `_meta.model` must be `{"Ok": <pin>}` (Grok 1.0.41's report; SERVE-A), else the same failure (ADR-0025 s2).
- Optional `session_meta`: the profile's mapping, sent as `session/new` `_meta` (ADR-0025 s2); none sends none.
- Update timeline (ADR-0026 s3): `acp-timeline.jsonl` in the cell home, arrival times and kinds, never content;
  consecutive messages of one kind collapse into one line, so its size follows kind changes, not streamed chunks.
  A `usage_update` line also carries the numbers `used` (its last) and `size`; a new size starts a new line, so
  the timeline is the served context size's source over ACP (telemetry/claude_code.py; J1A-FIX item 22).
  Buffered and best-effort: a write failure stops the timeline and is logged, never a cell failure.
- Ack barrier: `before_send()` runs after the handshake and before `session/prompt` is written; the
  engine persists `prompt_sent` in it, so a failed append means the prompt is never sent (model
  QueuePromptSent -> PersistPromptSent -> SendPrompt). The driver never retries `session/prompt`.
- The handshake has its own deadline; the engine cancels a turn at its budget, then terminates the
  cell's job after the profile's bounded grace if the adapter has not exited.

Only this module speaks ACP (design D3 import lint).
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic_ns as _arrival_ns

from harness_bench.errors import Cause
from harness_bench.procs import CellProcess
from harness_bench.telemetry import ProviderError, normalize

MAX_LINE = 8 << 20
MAX_JUNK = 20
PROTOCOL_VERSION = 1
CLIENT_INFO = {"name": "harness-bench", "version": "1"}
TIMELINE = "acp-timeline.jsonl"
TIMELINE_FLUSH = 64  # completed lines held before one append (the buffer bound)
# The timeline's labels a reader matches (`views.acp_intervals`): the prompt request's method, the two kinds this
# driver stamps on a request line, and the two tool-call update kinds the agent sends. Exported so no other module
# spells an ACP name (test_only_driver_speaks_acp; Leader ruling on R-DERIV seam 3).
TIMELINE_PROMPT = "session/prompt"
TIMELINE_SENT, TIMELINE_RESPONSE = "sent", "response"
TIMELINE_TOOL_CALL, TIMELINE_TOOL_CALL_UPDATE = "tool_call", "tool_call_update"
log = logging.getLogger("harness_bench.driver")


def cell_home(cwd: Path) -> Path:
    """The cell home beside the worktree: engine.py lays a cell out as `home, ws = cell_dir / "home", cell_dir / "ws"`
    and passes ws as cwd (pinned by tests/test_stream_driver.py). Shared with stream_driver."""
    return Path(cwd).parent / "home"


def _label(value) -> str | None:
    """A protocol kind or id as the timeline keeps it; anything else (content) is not kept."""
    return value if isinstance(value, str) and len(value) <= 128 else None


def _number(value) -> int | None:
    """A usage_update count as the timeline keeps it: a non-negative int, else None (never content)."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class _Timeline:
    """ADR-0026 s3: one line per run of same-kind messages, `{first_mono_ns, last_mono_ns, count, method,
    update_kind, tool_call_id}`; fed by the reader thread and the prompt send, flushed at turn end and close."""

    def __init__(self, path: Path | None) -> None:
        self.path, self.lock = path, threading.Lock()
        self.run: dict | None = None
        self.pending: list[dict] = []
        self.stopped = path is None

    def add(self, method: str | None, update_kind: str | None, tool_call_id: str | None,
            usage: tuple[int | None, int | None] | None = None) -> None:
        """`usage` is a usage_update's (used, size), numbers only: the size is in the run's key, `used` its last."""
        ns = _arrival_ns()
        with self.lock:
            if self.stopped:
                return
            key = (method, update_kind, tool_call_id, None if usage is None else usage[1])
            if self.run is not None and self.run["key"] == key:
                self.run["last_mono_ns"], self.run["count"] = ns, self.run["count"] + 1
                if usage is not None:
                    self.run["used"] = usage[0]
                return
            if self.run is not None:
                self.pending.append(self.run)
            self.run = {"key": key, "first_mono_ns": ns, "last_mono_ns": ns, "count": 1}
            if usage is not None:
                self.run["used"] = usage[0]
            if len(self.pending) >= TIMELINE_FLUSH:
                self._write()

    def flush(self, final: bool = False) -> None:
        with self.lock:
            if final and self.run is not None:
                self.pending.append(self.run)
                self.run = None
            self._write()
            if final:
                self.stopped = True

    def _write(self) -> None:
        if self.stopped or not self.pending:
            self.pending.clear()
            return
        rows = [{"first_mono_ns": r["first_mono_ns"], "last_mono_ns": r["last_mono_ns"], "count": r["count"],
                 "method": r["key"][0], "update_kind": r["key"][1], "tool_call_id": r["key"][2],
                 **({"used": r["used"], "size": r["key"][3]} if "used" in r else {})} for r in self.pending]
        self.pending.clear()
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write("".join(json.dumps(row) + "\n" for row in rows))
        except OSError as exc:  # the stderr-tail pattern (engine.py): the timeline stops, the cell goes on
            self.stopped = True
            log.warning("acp timeline stopped", extra={"detail": str(exc)})


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
class TurnRecord:
    turn: int
    stop_reason: str | None
    turn_seconds: float
    usage: dict | None
    last_update_seconds: float | None


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
    turns: list[TurnRecord] = field(default_factory=list)


class Session:
    """Own the channel until close; close() is idempotent."""

    def __init__(self, channel, cwd, mode, handshake_timeout, model, mcp_servers, session_meta=None):
        self.channel = channel
        self.result = channel.result
        self.cwd, self.mode = cwd, mode
        self.handshake_timeout, self.model = handshake_timeout, model
        self.mcp_servers = mcp_servers
        self.session_meta = session_meta
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.channel.cell.proc.stdin.close()
        finally:
            timeline = getattr(self.channel, "timeline", None)
            if timeline is not None:
                timeline.flush(final=True)


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

    def __init__(self, cell: CellProcess, result: TurnResult, cancel: threading.Event | None = None,
                 timeline: _Timeline | None = None) -> None:
        self.cell = cell
        self.result = result
        self.cancel = cancel
        self.cancel_handled = False
        self.inbox: queue.Queue = queue.Queue()
        self.seq = 0
        self.turn_start: float | None = None  # set when the prompt is sent
        self.on_first_update: Callable[[], None] | None = None
        self.timeline = timeline if timeline is not None else _Timeline(None)
        self.methods: dict[int, str] = {}  # request id -> method, so a response's timeline line names its request
        threading.Thread(target=self._read, daemon=True).start()

    def _arrived(self, msg: dict) -> None:
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if "method" in msg:
            update = params.get("update") if isinstance(params.get("update"), dict) else {}
            call = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else update
            kind = "request" if "id" in msg else _label(update.get("sessionUpdate"))
            usage = (_number(update.get("used")), _number(update.get("size"))) if kind == "usage_update" else None
            self.timeline.add(_label(msg["method"]), kind, _label(call.get("toolCallId")), usage)
        else:
            rid = msg.get("id")
            self.timeline.add(self.methods.get(rid, TIMELINE_RESPONSE) if isinstance(rid, int) else TIMELINE_RESPONSE,
                              TIMELINE_RESPONSE, None)

    def _read(self) -> None:
        parser = LineParser()
        stream = self.cell.proc.stdout
        try:
            while True:
                chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
                if not chunk:
                    break
                for msg in parser.feed(chunk):
                    self._arrived(msg)
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
        self.methods[rid] = method
        if method == TIMELINE_PROMPT:
            self.timeline.add(method, TIMELINE_SENT, None)
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
                    first_update, self.on_first_update = self.on_first_update, None
                    if first_update is not None:
                        first_update()
                    if self.turn_start is not None:
                        self.result.last_update_seconds = time.monotonic() - self.turn_start
            elif msg.get("id") == rid:
                if "error" in msg:
                    raise _AcpError(msg["error"])
                return msg.get("result") or {}


# assume: an adapter reports a provider's HTTP status as "API Error: <status>" in the JSON-RPC error message and its
# type as data.errorKind. Confirm: the one measured form, claude-agent-acp 0.79.0 refusing claude-opus-5-5
# (tests/fixtures/acp/recordings/claude-code-x1-model-unsupported.jsonl). Breaks: another adapter's form is not
# parsed, so its error stays adapter_crash with the text in detail (R-18 condition 2), never a guessed cause.
_API_STATUS = re.compile(r"\bAPI Error: (\d{3})\b")


def _prompt_error_cause(exc: _AcpError) -> Cause:
    """R-23: a prompt-time error with a status or a provider type goes through the native-record classifier
    (`normalize.classify`, one classifier for both paths); an auth failure keeps its precedence; an error with
    neither status nor type is adapter_crash."""
    if normalize.is_auth_failure(str(exc)):  # CAUSE-A: one auth-failure text rule, shared with normalize.classify
        return Cause.blocked_auth
    message = exc.error.get("message") if isinstance(exc.error.get("message"), str) else ""
    data = exc.error.get("data") if isinstance(exc.error.get("data"), dict) else {}
    found = _API_STATUS.search(message)
    status = int(found.group(1)) if found else None
    error_type = data.get("errorKind") if isinstance(data.get("errorKind"), str) else ""
    if status is None and not error_type:
        return Cause.adapter_crash
    return normalize.classify([ProviderError(0, status, error_type, message[:300])]) or Cause.adapter_crash


def _handshake(session: Session) -> bool:
    ch, result = session.channel, session.result
    cwd, mode = session.cwd, session.mode
    handshake_timeout, model = session.handshake_timeout, session.model
    mcp_servers = session.mcp_servers
    started = time.monotonic()
    deadline = started + handshake_timeout
    try:
        init = ch.rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "clientCapabilities": {}, "clientInfo": CLIENT_INFO}, deadline)
        info = init.get("agentInfo")
        version = info.get("version") if isinstance(info, dict) else None
        result.agent_version = version if isinstance(version, str) else None  # verbatim; null when not reported
        params = {"cwd": str(cwd), "mcpServers": mcp_servers or []}
        if session.session_meta:  # ADR-0025 s2: the profile's mapping, verbatim
            params["_meta"] = dict(session.session_meta)
        created = ch.rpc("session/new", params, deadline)
        result.session_id = created.get("sessionId")
        modes = created.get("modes") if isinstance(created.get("modes"), dict) else {}
        current = modes.get("currentModeId")
        result.permission_mode_effective = current if isinstance(current, str) else None
        if model:
            try:
                answer = ch.rpc("session/set_model", {"sessionId": result.session_id, "modelId": model}, deadline)
            except _AcpError as exc:  # tagged by step: the plan's model is not served here
                _fail(result, Cause.model_unavailable, f"set_model refused: {exc}", started)
                return False
            meta = answer.get("_meta")
            # ADR-0025 s2 (SERVE-A): an answer that reports the session's model must report the pin, else the cell
            # fails before the prompt; an answer without the report (Copilot's {}) is judged from native evidence.
            if isinstance(meta, dict) and "model" in meta and meta["model"] != {"Ok": model}:
                _fail(result, Cause.model_unavailable,
                      f"set_model answered _meta.model {json.dumps(meta['model'])[:200]}, not {{'Ok': {model!r}}}", started)
                return False
        if mode:
            ch.rpc("session/set_mode", {"sessionId": result.session_id, "modeId": mode}, deadline)
            result.permission_mode_effective = mode  # accepted: a refusal raised _AcpError above
    except _Timeout as exc:
        _fail(result, Cause.handshake_timeout, f"no answer to {exc} within {handshake_timeout} s", started)
        return False
    except _Eof:
        result.eof = True
        _fail(result, Cause.adapter_crash, "the adapter exited during the handshake", started)
        return False
    except ProtocolError as exc:
        _fail(result, Cause.protocol, exc.detail, started)
        return False
    except _AcpError as exc:
        cause = Cause.blocked_auth if normalize.is_auth_failure(str(exc)) else Cause.adapter_crash
        _fail(result, cause, f"handshake error: {exc}", started)
        return False
    result.handshake_seconds = time.monotonic() - started
    return True


def open_session(cell: CellProcess, cwd: Path, mode: str | None, handshake_timeout: float,
                 model: str | None = None, result: TurnResult | None = None,
                 mcp_servers: list[dict] | None = None, cancel: threading.Event | None = None,
                 session_meta: dict | None = None) -> Session | None:
    """Open one channel; None means the supplied result carries the handshake cause. The timeline is kept only where
    the cell home exists (the engine's layout); a caller with no home beside its cwd gets none."""
    result = result if result is not None else TurnResult()
    home = cell_home(cwd)
    timeline = _Timeline(home / TIMELINE if home.is_dir() else None)
    session = Session(_Channel(cell, result, cancel, timeline), cwd, mode, handshake_timeout, model, mcp_servers,
                      session_meta)
    if _handshake(session):
        return session
    timeline.flush(final=True)
    return None


def send_turn(session: Session, prompt: str, before_send: Callable[[str | None], None], turn: int,
              on_first_update: Callable[[], None] | None = None) -> TurnRecord | None:
    """Send one prompt; None means result.cause is set. The handshake ran once, in open_session."""
    ch, result = session.channel, session.result
    if session.closed:
        result.cause, result.detail = Cause.adapter_crash, "send after session close"
        return None
    result.last_update_seconds = None

    before_send(result.session_id)  # the ack barrier: prompt_sent is durable before the prompt goes out
    if ch.cancel is not None and ch.cancel.is_set():
        ch._observe_cancel(False)
        return None
    turn_start = ch.turn_start = time.monotonic()
    ch.on_first_update = on_first_update
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
    finally:
        ch.on_first_update = None
        ch.timeline.flush()
    result.turn_seconds = time.monotonic() - turn_start
    if result.cause is not None:
        return None
    rec = TurnRecord(turn, result.stop_reason, result.turn_seconds, result.usage, result.last_update_seconds)
    result.turns.append(rec)
    return rec


def run_turn(cell: CellProcess, cwd: Path, prompt: str, mode: str | None, handshake_timeout: float,
             before_send: Callable[[str | None], None], model: str | None = None,
             result: TurnResult | None = None, mcp_servers: list[dict] | None = None,
             cancel: threading.Event | None = None) -> TurnResult:
    """Compatibility wrapper: handshake, ack barrier, one prompt, then close."""
    result = result if result is not None else TurnResult()
    session = open_session(cell, cwd, mode, handshake_timeout, model, result, mcp_servers, cancel)
    if session is not None:
        try:
            send_turn(session, prompt, before_send, 1)
        finally:
            session.close()
    return result


def _fail(result: TurnResult, cause: Cause, detail: str, started: float) -> TurnResult:
    result.cause, result.detail = cause, detail
    result.handshake_seconds = time.monotonic() - started
    return result
