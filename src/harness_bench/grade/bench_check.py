"""The helper a hidden property check imports, and the probe host it spawns (design 5.4, 5.5; ADR-0018).

Stdlib only. Copied into every check copy and run with the base interpreter, `-S`, DETACHED_PROCESS, in the grader's
job. The check process never imports deliverable code: an in-process probe is a one-host-per-case child
(`bench_check.py --probe-host`) whose first line must be the ready line. Two jobs here:

- check side: `load`, `probe_host`, `run_case`, `sweep`, `write_result`, `main`. `write_result` sweeps the job, waits
  until the check is alone, writes one line, then blocks for the grader's one-byte acknowledgement
  (exit 0 on 0x06, 3 on EOF, 4 when never alone, 5 from `main` on an uncaught error).
- host side: the start sequence of design 5.5 (private protocol duplicates, fds 0-2 moved, then agent code), and a
  `callable` or `wsgi` (PEP 3333) request loop.
"""

import base64
import contextlib
import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import queue
import random
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import unquote_to_bytes

READY = {"ready": "bench-probe-host/1"}
PROBE_LINE_MAX = 1 << 20
DETACHED_PROCESS = 0x00000008
ACK = b"\x06"
_REPARSE = 0x400
_KILL = 0x0001 | 0x00100000  # PROCESS_TERMINATE | SYNCHRONIZE
_QUERY = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_GONE = 87  # ERROR_INVALID_PARAMETER: OpenProcess on a pid that has exited

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.GetCurrentProcess.restype = wt.HANDLE
_k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4


class DidNotStart(Exception):
    """The probe host sent no ready line: `deliverable: did not start` (W0 outcome row 6)."""


class ListenerError(Exception):
    """HB-CHK-005: a check listener is not bound to 127.0.0.1."""


_BIND = ("127.0.0.1", 0)  # the literal loopback address, port 0 so parallel cases never collide (F15)


@contextlib.contextmanager
def listen():
    """A case's fake: a listening socket on 127.0.0.1, port 0, exclusive on its port, closed when the case ends.

    The whole lifecycle is here: bind, assert the bound address is the literal `127.0.0.1` (HB-CHK-005 otherwise), yield
    the socket, close it. It is the only socket the check opens, it is never inherited (the probe host starts with
    close_fds), and it holds no state beyond the socket (ADR-0018 s3; W0 R6-17)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # R6-17: no other process can share the port
        sock.bind(_BIND)
        if sock.getsockname()[0] != "127.0.0.1":
            raise ListenerError(f"HB-CHK-005: listener bound to {sock.getsockname()[0]}, not 127.0.0.1")
        sock.listen()
        yield sock
    finally:
        sock.close()


class _PidList(ctypes.Structure):
    _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD), ("Ids", ctypes.c_size_t * 1024)]


def job_pids() -> set:
    """Every process id in the job this process belongs to (BasicProcessIdList on the calling process's job)."""
    buf = _PidList()
    if not _k32.QueryInformationJobObject(None, 3, ctypes.byref(buf), ctypes.sizeof(buf), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {int(buf.Ids[i]) for i in range(buf.InList)}


def _created(handle) -> int | None:
    """The process's creation time in FILETIME ticks, or None when it cannot be read."""
    times = [wt.FILETIME() for _ in range(4)]
    if not _k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
        return None
    return times[0].dwHighDateTime << 32 | times[0].dwLowDateTime


def _kill_younger(pids, mine) -> bool:
    """Terminate `pids` only when none started before this process (JOB-A). The grader made the job for the check, so
    the check is its first member; an older member means an inherited job, such as the logon session's job that holds
    the terminal and every agent. Each handle is held from the age check to the kill, so a reused pid is never hit.
    False, with nothing terminated, when any member is older or cannot be inspected."""
    handles = []
    try:
        for pid in pids:
            h = _k32.OpenProcess(_KILL | _QUERY, False, pid)
            if not h:
                if ctypes.get_last_error() == _GONE:
                    continue
                return False
            handles.append(h)
            born = _created(h)
            if born is None or born < mine:
                return False
        for h in handles:
            _k32.TerminateProcess(h, 1)
        return True
    finally:
        for h in handles:
            _k32.CloseHandle(h)


def sweep(bound_s=5.0) -> bool:
    """Terminate every job member except this process; True once alone, False at the bound, when the query fails, or
    when the job holds a process older than this one (then nothing is terminated: JOB-A)."""
    me, t0 = os.getpid(), time.monotonic()
    mine = _created(_k32.GetCurrentProcess())
    if mine is None:
        return False  # fail closed: without its own start time the check cannot tell its job from an inherited one
    while time.monotonic() - t0 < bound_s:
        try:
            others = job_pids() - {me}
        except OSError:
            return False  # fail closed: a job that cannot be read is not "alone"
        if not others:
            return True
        if not _kill_younger(others, mine):
            return False
        time.sleep(0.01)
    return False


# ---- check side -------------------------------------------------------------------------------------------------


class Context:
    def __init__(self, deliverable, cases_path, seed, evidence):
        with open(cases_path, encoding="utf-8") as f:
            doc = json.load(f)
        self.doc, self.deliverable, self.evidence, self.seed = doc, deliverable, evidence, seed
        self.rng = random.Random(seed)
        self.cases, self.app = doc["cases"], doc["app"]
        self.interface, self.bounds_ms = doc["interface"], doc["bounds_ms"]

    def bound_ms(self, case):
        interface = self.bounds_ms[self.interface]
        return min(case.get("bound_ms", interface), interface)


_CTX = None
_STARTS = []
_SPANS = []
_TIMED_OUT = []


def load():
    global _CTX
    args = dict(zip(sys.argv[1::2], sys.argv[2::2], strict=False))
    _CTX = Context(args["--deliverable"], args["--cases"], int(args["--seed"]), args["--evidence"])
    os.makedirs(_CTX.evidence, exist_ok=True)
    return _CTX


def _resolve(value, state_dir, fake_url=None):
    """`str.replace` of the literal `{state_dir}` (and, when given, `{fake_url}`) in every string value at any depth;
    keys are never rewritten. `state_dir` None leaves `{state_dir}` alone (a request frame has no state dir)."""
    if isinstance(value, str):
        if state_dir is not None:
            value = value.replace("{state_dir}", state_dir)
        return value if fake_url is None else value.replace("{fake_url}", fake_url)
    if isinstance(value, list):
        return [_resolve(v, state_dir, fake_url) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, state_dir, fake_url) for k, v in value.items()}
    return value


def _rmtree(path):
    """Remove a tree without following a junction or symlink (a reparse point is unlinked, never walked)."""
    st = os.lstat(path)
    if os.path.islink(path) or getattr(st, "st_file_attributes", 0) & _REPARSE:
        try:
            os.unlink(path)
        except OSError:
            os.rmdir(path)
        return
    if not os.path.isdir(path):
        os.unlink(path)
        return
    for entry in os.listdir(path):
        _rmtree(os.path.join(path, entry))
    os.rmdir(path)


class ProbeHost:
    def __init__(self, ctx, case, bound_s, fake=None):
        self.ctx, self.case, self.bound_s, self.timed_out = ctx, case, bound_s, False
        self.fake_url = None if fake is None else f"http://127.0.0.1:{fake.getsockname()[1]}"
        self.state_dir = os.path.join(os.path.dirname(os.path.abspath(ctx.deliverable)), "state", case["id"])
        if os.path.lexists(self.state_dir):
            _rmtree(self.state_dir)
        os.makedirs(self.state_dir)
        host_dir = os.path.join(ctx.evidence, "host")
        os.makedirs(host_dir, exist_ok=True)
        self.log_path = os.path.join(host_dir, case["id"] + ".log")
        app = dict(ctx.app)
        app["args"] = _resolve(app.get("args", {}), self.state_dir)
        argv = [sys._base_executable, "-S", "-u", os.path.abspath(__file__), "--probe-host", "--root",
                os.path.abspath(ctx.deliverable), "--app", json.dumps(app, sort_keys=True, separators=(",", ":"))]
        self.lines = queue.Queue()
        with open(self.log_path, "wb") as log:
            self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, close_fds=True,
                                         creationflags=DETACHED_PROCESS, env=dict(os.environ))
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        t0 = time.monotonic()
        first = self._next(ctx.bounds_ms[ctx.interface] / 1000)
        self.start_ms = round((time.monotonic() - t0) * 1000)
        end = "ready" if first == READY else {"bound": "start bound", "eof": "exit"}.get(first, "not ready line")
        self._record(end)
        if end != "ready":
            self.close()
            raise DidNotStart(end)
        self._n = 0
        self.deadline = time.monotonic() + bound_s  # the case span starts at the ready line

    def _record(self, end):
        line = json.dumps({"case": self.case["id"], "start_ms": self.start_ms, "end": end}, sort_keys=True)
        with open(os.path.join(self.ctx.evidence, "hosts.jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _read(self):
        while True:
            raw = self.proc.stdout.readline(PROBE_LINE_MAX + 1)
            self.lines.put(raw if raw else None)
            if not raw or len(raw) > PROBE_LINE_MAX:
                return

    def _next(self, wait_s):
        """A parsed line, "bound" (nothing in time), "eof" (host gone), or "bad" (oversize or not JSON)."""
        try:
            raw = self.lines.get(timeout=max(0.0, wait_s))
        except queue.Empty:
            return "bound"
        if raw is None:
            return "eof"
        if len(raw) > PROBE_LINE_MAX:
            return "bad"
        try:
            return json.loads(raw)
        except ValueError:
            return "bad"

    def request(self, frame):
        """One frame out, one response line in, within what is left of the case bound. None is a broken exchange."""
        self._n += 1
        frame = {"id": self._n} | dict(frame)
        if self.fake_url is not None:  # `{fake_url}` in a request's string args, as `{state_dir}` is in the app's
            frame = {k: _resolve(v, None, self.fake_url) if k in ("args", "kwargs") else v for k, v in frame.items()}
        t0 = time.monotonic()
        try:
            self.proc.stdin.write((json.dumps(frame) + "\n").encode())
            self.proc.stdin.flush()
        except OSError:
            return None
        resp = self._next(self.deadline - time.monotonic())
        _SPANS.append(round((time.monotonic() - t0) * 1000))  # frame written to response read: host start is outside it
        if resp == "bound":
            self.timed_out = True
            _TIMED_OUT.append(self.case["id"])
        return resp if isinstance(resp, dict) and resp.get("id") == frame["id"] else None

    def close(self):
        """Stdin EOF, a short wait, a kill, then the job sweep (it also ends any grandchild and the reader's read)."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=0.2 if self.timed_out else 1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        sweep()
        self.reader.join(1)

    def output_contains(self, *needles):
        """Whether the case's app-output file holds any needle: 64 KiB chunks, overlapped by the longest needle - 1."""
        keep = max(len(n) for n in needles) - 1
        tail = b""
        with open(self.log_path, "rb") as f:
            while chunk := f.read(65536):
                data = tail + chunk
                if any(n in data for n in needles):
                    return True
                tail = data[len(data) - keep:] if keep else b""
        return False


def probe_host(case, fake=None):
    """The case's host. `fake` is the case's `listen()` socket (shape (b)): `{fake_url}` then names its port."""
    host = ProbeHost(_CTX, case, _CTX.bound_ms(case) / 1000, fake)
    _STARTS.append(host.start_ms)
    return host


def run_case(case, fn):
    """Time one case from the host's ready line (the start is bounded apart), and turn an overrun into `timeout`.

    A `kind: fault` case is timed by the probe-host calls alone (frame written to response read), so the fake's setup
    and the host start are outside it (W0 section 3, shape (b))."""
    t0 = time.monotonic()
    del _STARTS[:], _SPANS[:], _TIMED_OUT[:]
    outcome = fn()
    elapsed_ms = sum(_SPANS) if case.get("kind") == "fault" else round((time.monotonic() - t0) * 1000) - sum(_STARTS)
    if _TIMED_OUT or elapsed_ms > _CTX.bound_ms(case):
        outcome = "timeout"
    return {"id": case["id"], "outcome": outcome, "duration_ms": max(0, elapsed_ms)}


def write_result(cases, measures=None, deliverable="ran"):
    """Sweep, wait until alone, write one canonical line last, then block on the acknowledgement. Never returns."""
    if not sweep():
        os._exit(4)  # never write while not alone
    doc = {"schema": "bench-check-result/1", "deliverable": deliverable, "cases": cases, "measures": measures or {}}
    sys.stdout.buffer.write((json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode())
    sys.stdout.buffer.flush()
    os._exit(0 if sys.stdin.buffer.read(1) == ACK else 3)


def main(check_fn):
    """Run the task's check. A failed host start is `did not start`; any other uncaught error exits 5 (no line)."""
    try:
        load()
        check_fn(_CTX)
        raise RuntimeError("check function returned without calling write_result")
    except DidNotStart:
        write_result([], deliverable="did not start")
    except Exception:  # noqa: BLE001 - a check bug: traceback to stderr, exit 5
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(5)


# ---- the probe host ---------------------------------------------------------------------------------------------


def _environ(frame):
    body = base64.b64decode(frame.get("body_b64", ""))
    content_type = ""
    environ = {
        "REQUEST_METHOD": frame["method"], "SCRIPT_NAME": "",
        "PATH_INFO": unquote_to_bytes(frame["path"]).decode("latin-1"), "QUERY_STRING": frame.get("query", ""),
        "CONTENT_LENGTH": str(len(body)), "SERVER_NAME": "localhost", "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1", "REMOTE_ADDR": "127.0.0.1", "REMOTE_PORT": "50000",
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(body), "wsgi.errors": sys.stderr,
        "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False,
    }
    for name, value in frame.get("headers", []):
        if name.lower() == "content-type":
            content_type = value
        elif name.lower() != "content-length":
            environ["HTTP_" + name.upper().replace("-", "_")] = value
    environ["CONTENT_TYPE"] = content_type
    return environ


def _serve_wsgi(app, frame):
    seen, written = {}, []

    def start_response(status, headers, exc_info=None):
        seen["status"], seen["headers"] = int(status.split()[0]), [[k, v] for k, v in headers]
        return written.append

    result = app(_environ(frame), start_response)
    try:
        chunks = list(written) + list(result)
    finally:
        if hasattr(result, "close"):
            result.close()
    return {"id": frame["id"], "ok": True, "status": seen["status"], "headers": seen["headers"],
            "body_b64": base64.b64encode(b"".join(chunks)).decode()}


def _serve_callable(fn, frame):
    return {"id": frame["id"], "ok": True, "value": fn(*frame.get("args", []), **frame.get("kwargs", {}))}


def _host(argv):
    args = dict(zip(argv[::2], argv[1::2], strict=True))
    # 1-3: the protocol on private duplicates, then fds 0-2 moved, before any agent code runs (design 5.5)
    proto_in, proto_out = os.fdopen(os.dup(0), "rb"), os.fdopen(os.dup(1), "wb")
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(2, 1)
    spec, root = json.loads(args["--app"]), args["--root"]
    sys.path[0:0] = [root, *(os.path.join(root, p) for p in spec.get("paths", []))]
    try:
        import importlib
        attr = getattr(importlib.import_module(spec["module"]), spec["attr"])
        app = attr(**spec.get("args", {})) if spec.get("factory") else attr
    except BaseException:  # noqa: BLE001 - any failure to import or build is "did not start"
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(10)
    serve = _serve_wsgi if spec.get("kind") == "wsgi" else _serve_callable
    try:
        proto_out.write((json.dumps(READY) + "\n").encode())
        proto_out.flush()
        for raw in proto_in:
            frame = json.loads(raw)
            try:
                resp = serve(app, frame)
                line = json.dumps(resp)
            except Exception as exc:  # noqa: BLE001 - the exception type is the deliverable's answer
                line = json.dumps({"id": frame["id"], "ok": False, "error": type(exc).__name__})
            proto_out.write((line + "\n").encode())
            proto_out.flush()
    except OSError:
        pass  # the check closed the pipe


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--probe-host":
    _host(sys.argv[2:])
