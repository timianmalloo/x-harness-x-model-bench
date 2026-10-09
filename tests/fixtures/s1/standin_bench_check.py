"""Stand-in for `grade/bench_check.py` (W1-F rev 3 section 5.4, 5.5) until X-F's real helper exists. Stdlib only.

It is the check-side API S1's `check.py` calls (`load`, `probe_host`, `run_case`, `write_result`, `main`) and, run as a
script with `--probe-host`, the wsgi probe host. It follows W1-F's text where the text is exact (frames, environ, the
private protocol duplicate, one host per case, fds 1 and 2 captured in one file, the start bound). Where W1-F leaves a
name open, this file fixes it and S1's check.py depends on it. Each such name is an `assume:` in the task's
evidence.md and is confirmed or corrected by `test_s1_real_host_reproduces_the_expected_values`.

  assume: Context.cases / .app / .evidence / .deliverable, ProbeHost.close() and .state_dir exist on the real helper.
  confirm: the real-host test (X-F landed). breaks if false: check.py raises AttributeError, exit 5, and the test fails.

Not modelled: the Job Object, DETACHED_PROCESS, the acknowledgement byte and the sweep. The real-wiring test covers them.
"""

import base64
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import unquote_to_bytes

READY = {"ready": "bench-probe-host/1"}
PROBE_LINE_MAX = 1 << 20


class DidNotStart(Exception):
    """The probe host did not send its ready line: `deliverable: did not start` (W0 outcome row 6)."""


class Context:
    def __init__(self, deliverable, cases_path, seed, evidence):
        with open(cases_path, encoding="utf-8") as f:
            doc = json.load(f)
        self.doc = doc
        self.deliverable = deliverable
        self.evidence = evidence
        self.seed = seed
        self.cases = doc["cases"]
        self.app = doc["app"]
        self.interface = doc["interface"]
        self.bounds_ms = doc["bounds_ms"]

    def bound_ms(self, case):
        interface = self.bounds_ms[self.interface]
        return min(case.get("bound_ms", interface), interface)


_CTX = None


def load():
    global _CTX
    args = dict(zip(sys.argv[1::2], sys.argv[2::2], strict=False))
    _CTX = Context(args["--deliverable"], args["--cases"], int(args["--seed"]), args["--evidence"])
    os.makedirs(_CTX.evidence, exist_ok=True)
    return _CTX


def _resolve(value, state_dir):
    if isinstance(value, str):
        return value.replace("{state_dir}", state_dir)
    if isinstance(value, list):
        return [_resolve(v, state_dir) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, state_dir) for k, v in value.items()}
    return value


class ProbeHost:
    def __init__(self, ctx, case, bound_s):
        self.ctx, self.case, self.bound_s = ctx, case, bound_s
        self.state_dir = os.path.join(os.path.dirname(os.path.abspath(ctx.deliverable)), "state", case["id"])
        if os.path.lexists(self.state_dir):
            shutil.rmtree(self.state_dir)
        os.makedirs(self.state_dir)
        host_dir = os.path.join(ctx.evidence, "host")
        os.makedirs(host_dir, exist_ok=True)
        self.log_path = os.path.join(host_dir, case["id"] + ".log")
        app = dict(ctx.app)
        app["args"] = _resolve(app.get("args", {}), self.state_dir)
        argv = [sys.executable, "-S", "-u", os.path.abspath(__file__), "--probe-host", "--root", ctx.deliverable,
                "--app", json.dumps(app, sort_keys=True, separators=(",", ":"))]
        self._log = open(self.log_path, "wb")  # noqa: SIM115 - held open for the host process's life, closed in close()
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                                     close_fds=True, env={k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
                                                          if k in os.environ} | {"PYTHONDONTWRITEBYTECODE": "1"},
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.lines = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.start_ms = None
        t0 = time.monotonic()
        first = self._next(ctx.bounds_ms[ctx.interface] / 1000)
        self.start_ms = round((time.monotonic() - t0) * 1000)
        if first != READY:
            self.close()
            raise DidNotStart(str(first))
        self._n = 0
        self.deadline = time.monotonic() + bound_s

    def _read(self):
        while True:
            raw = self.proc.stdout.readline(PROBE_LINE_MAX + 1)
            self.lines.put(raw if raw else None)
            if not raw or len(raw) > PROBE_LINE_MAX:
                return

    def _next(self, wait_s):
        try:
            raw = self.lines.get(timeout=max(0.0, wait_s))
        except queue.Empty:
            return "bound"
        if raw is None or len(raw) > PROBE_LINE_MAX:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def request(self, frame):
        self._n += 1
        frame = {"id": self._n} | dict(frame)
        try:
            self.proc.stdin.write((json.dumps(frame) + "\n").encode())
            self.proc.stdin.flush()
        except OSError:
            return None
        resp = self._next(self.deadline - time.monotonic())
        return resp if isinstance(resp, dict) and resp.get("id") == frame["id"] else None

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._log.close()

    def output_contains(self, *needles):
        with open(self.log_path, "rb") as f:
            data = f.read()
        return any(n in data for n in needles)


_STARTS = []


def probe_host(case):
    host = ProbeHost(_CTX, case, _CTX.bound_ms(case) / 1000)
    _STARTS.append(host.start_ms)
    return host


def run_case(case, fn):
    """The case span starts at the host's ready line: the start is bounded apart from the case (W1-F 5.5)."""
    t0 = time.monotonic()
    del _STARTS[:]
    outcome = fn()
    elapsed_ms = round((time.monotonic() - t0) * 1000) - sum(_STARTS)
    if elapsed_ms > _CTX.bound_ms(case):
        outcome = "timeout"
    return {"id": case["id"], "outcome": outcome, "duration_ms": elapsed_ms}


def write_result(cases, measures=None, deliverable="ran"):
    doc = {"schema": "bench-check-result/1", "deliverable": deliverable, "cases": cases, "measures": measures or {}}
    sys.stdout.write(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    sys.exit(0)


def main(check_fn):
    load()
    try:
        check_fn(_CTX)
    except DidNotStart:
        write_result([], deliverable="did not start")


# ---- the wsgi probe host ----------------------------------------------------------------------------------------

def _environ(frame):
    body = base64.b64decode(frame.get("body_b64", ""))
    headers = frame.get("headers", [])
    content_type = ""
    environ = {
        "REQUEST_METHOD": frame["method"], "SCRIPT_NAME": "",
        "PATH_INFO": unquote_to_bytes(frame["path"]).decode("latin-1"), "QUERY_STRING": frame.get("query", ""),
        "CONTENT_LENGTH": str(len(body)), "SERVER_NAME": "localhost", "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1", "REMOTE_ADDR": "127.0.0.1", "REMOTE_PORT": "50000",
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(body), "wsgi.errors": sys.stderr,
        "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False,
    }
    for name, value in headers:
        if name.lower() == "content-type":
            content_type = value
        elif name.lower() != "content-length":
            environ["HTTP_" + name.upper().replace("-", "_")] = value
    environ["CONTENT_TYPE"] = content_type
    return environ


def _serve(app, frame):
    seen = {}
    written = []

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


def _host(argv):
    args = dict(zip(argv[::2], argv[1::2], strict=True))
    proto_in = os.fdopen(os.dup(0), "rb")
    proto_out = os.fdopen(os.dup(1), "wb")
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(2, 1)
    spec = json.loads(args["--app"])
    root = args["--root"]
    sys.path[0:0] = [root, *(os.path.join(root, p) for p in spec.get("paths", []))]
    try:
        import importlib
        attr = getattr(importlib.import_module(spec["module"]), spec["attr"])
        app = attr(**spec.get("args", {})) if spec.get("factory") else attr
    except BaseException:  # noqa: BLE001 - any failure to import or build is "did not start"
        import traceback
        traceback.print_exc()
        os._exit(10)
    proto_out.write((json.dumps(READY) + "\n").encode())
    proto_out.flush()
    for raw in proto_in:
        frame = json.loads(raw)
        try:
            resp = _serve(app, frame)
        except Exception as exc:  # noqa: BLE001 - the exception type is the deliverable's answer
            resp = {"id": frame["id"], "ok": False, "error": type(exc).__name__}
        proto_out.write((json.dumps(resp) + "\n").encode())
        proto_out.flush()


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--probe-host":
    _host(sys.argv[2:])
