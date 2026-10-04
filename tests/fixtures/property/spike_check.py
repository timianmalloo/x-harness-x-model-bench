"""Spike W1-F SP-F2 control check (stdlib only; base interpreter, -S, DETACHED_PROCESS, in the grader's job).

argv: in-check-import <evidence dir> <deliverable root> <module:attr>
It imports the deliverable module into this process (the revision 1 shape RV-SEC F1 broke) and declares one probe case,
`inj-1`. This is only the positive control: the shipped shape (the probe host) is tested through the real
`grade/bench_check.py` in tests/test_property_grader.py.
"""

import ctypes
import ctypes.wintypes as wt
import importlib
import json
import os
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
PAYLOAD = "<script>bench</script>"


class PidList(ctypes.Structure):
    _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD), ("Ids", ctypes.c_size_t * 1024)]


def job_pids():
    buf = PidList()
    if not k32.QueryInformationJobObject(None, 3, ctypes.byref(buf), ctypes.sizeof(buf), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {int(buf.Ids[i]) for i in range(buf.InList)}


def write_result(cases):
    t0 = time.monotonic()
    while job_pids() != {os.getpid()}:
        if time.monotonic() - t0 > 5.0:
            os._exit(4)  # never write while not alone
        time.sleep(0.01)
    doc = {"schema": "bench-check-result/1", "deliverable": "ran", "cases": cases, "measures": {}}
    sys.stdout.buffer.write((json.dumps(doc, sort_keys=True) + "\n").encode())
    sys.stdout.buffer.flush()
    os._exit(0 if sys.stdin.buffer.read(1) == b"\x06" else 3)


def main():
    _mode, evid, root, app = sys.argv[1:5]
    os.makedirs(evid, exist_ok=True)
    with open(os.path.join(evid, "check.env.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(os.environ), f)  # key names only: the test asserts no credential reached this process
    t0 = time.monotonic()
    sys.path.insert(0, root)
    fn = getattr(importlib.import_module(app.split(":")[0]), app.split(":")[1])
    outcome = "exploited" if PAYLOAD in str(fn(PAYLOAD)) else "blocked"
    write_result([{"duration_ms": round((time.monotonic() - t0) * 1000), "id": "inj-1", "outcome": outcome}])


main()
