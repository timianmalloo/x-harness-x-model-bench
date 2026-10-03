"""Spike W1-F SP-F2 fixture check (stdlib only; base interpreter, -S, DETACHED_PROCESS, in the grader's job).

argv: <mode> <evidence dir> <deliverable root> <module:attr>
  in-check-import  imports the deliverable module into this process (the revision 1 shape RV-SEC F1 broke)
  probe-host       spawns probe_host.py with pipes this process owns and decides the case from the raw response
Both declare one probe case, `inj-1`. The honest answer to the probe is decided here, never by the deliverable.
X-F replaces this with the real `grade/bench_check.py`; the forge fixture and the assertions stay.
"""

import ctypes
import ctypes.wintypes as wt
import importlib
import json
import os
import queue
import subprocess
import sys
import threading
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
k32.CloseHandle.argtypes = [wt.HANDLE]
DETACHED_PROCESS = 0x00000008
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys._base_executable
PAYLOAD = "<script>bench</script>"
READY = {"ready": "bench-probe-host/1"}
CASE_BOUND_S = 2.0
MAX_LINE = 1 << 20


class PidList(ctypes.Structure):
    _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD), ("Ids", ctypes.c_size_t * 1024)]


def job_pids():
    buf = PidList()
    if not k32.QueryInformationJobObject(None, 3, ctypes.byref(buf), ctypes.sizeof(buf), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {int(buf.Ids[i]) for i in range(buf.InList)}


def sweep(bound_s=5.0):
    me, t0 = os.getpid(), time.monotonic()
    while time.monotonic() - t0 < bound_s:
        others = job_pids() - {me}
        if not others:
            return
        for pid in others:
            h = k32.OpenProcess(0x0001 | 0x00100000, False, pid)  # PROCESS_TERMINATE | SYNCHRONIZE
            if h:
                k32.TerminateProcess(h, 1)
                k32.CloseHandle(h)
        time.sleep(0.01)


def write_result(deliverable, cases):
    t0 = time.monotonic()
    while job_pids() != {os.getpid()}:
        if time.monotonic() - t0 > 5.0:
            os._exit(4)  # never write while not alone
        time.sleep(0.01)
    doc = {"schema": "bench-check-result/1", "deliverable": deliverable, "cases": cases, "measures": {}}
    sys.stdout.buffer.write((json.dumps(doc, sort_keys=True) + "\n").encode())
    sys.stdout.buffer.flush()
    ack = sys.stdin.buffer.read(1)
    os._exit(0 if ack == b"\x06" else 3)


def probe_host_case(root, app, evid):
    """One host per case. The host's first line must be the ready line, within the case bound (W1-F s5.5)."""
    t0 = time.monotonic()
    host = subprocess.Popen([PY, "-S", os.path.join(HERE, "probe_host.py"), "--root", root, "--app", app],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=open(os.path.join(evid, "host.err"), "wb"), close_fds=True,
                            creationflags=DETACHED_PROCESS, env=dict(os.environ))
    lines = queue.Queue()

    def reader():
        while True:
            raw = host.stdout.readline(MAX_LINE + 1)
            lines.put(raw if raw else None)
            if not raw or len(raw) > MAX_LINE:
                return

    threading.Thread(target=reader, daemon=True).start()

    def next_line():
        try:
            raw = lines.get(timeout=max(0.0, CASE_BOUND_S - (time.monotonic() - t0)))
        except queue.Empty:
            return "bound"
        if raw is None or len(raw) > MAX_LINE:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def close():
        try:
            host.stdin.close()
        except OSError:
            pass
        sweep()

    first = next_line()
    if first == "bound":
        close()
        return "ran", "timeout"
    if first != READY:  # an exit, a failed import or a non-ready first line: the start ended without ready
        close()
        return "did not start", None
    host.stdin.write((json.dumps({"id": 1, "args": [PAYLOAD], "kwargs": {}}) + "\n").encode())
    host.stdin.flush()
    resp = next_line()
    close()
    if resp == "bound":
        return "ran", "timeout"
    ok = isinstance(resp, dict) and resp.get("id") == 1 and resp.get("ok") is True
    if ok and PAYLOAD not in str(resp.get("value")):
        return "ran", "blocked"
    return "ran", "exploited"  # an echoed payload, or a broken exchange (fail closed)


def main():
    mode, evid, root, app = sys.argv[1:5]
    os.makedirs(evid, exist_ok=True)
    t0 = time.monotonic()
    if mode == "in-check-import":
        sys.path.insert(0, root)
        fn = getattr(importlib.import_module(app.split(":")[0]), app.split(":")[1])
        outcome = "exploited" if PAYLOAD in str(fn(PAYLOAD)) else "blocked"
        deliverable = "ran"
    else:
        deliverable, outcome = probe_host_case(root, app, evid)
    cases = [] if deliverable != "ran" else [
        {"duration_ms": round((time.monotonic() - t0) * 1000), "id": "inj-1", "outcome": outcome}]
    write_result(deliverable, cases)


main()
