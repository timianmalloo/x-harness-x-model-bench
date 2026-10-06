"""STUB check for the F3a runner tests (stdlib only; base interpreter, -S, DETACHED_PROCESS, in the grader's job).

Not `bench_check` (F3b writes that). It keeps spike_check.py's write_result: wait until alone in the job, write one
line, flush, block on stdin for the ack byte, exit 0 on 0x06 and 3 otherwise; exit 4 when never alone. The behaviour is
chosen by `mode.txt` beside this file. argv: --deliverable D --cases C --seed S --evidence E
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
HERE = os.path.dirname(os.path.abspath(__file__))


class PidList(ctypes.Structure):
    _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD), ("Ids", ctypes.c_size_t * 1024)]


def job_pids():
    buf = PidList()
    if not k32.QueryInformationJobObject(None, 3, ctypes.byref(buf), ctypes.sizeof(buf), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {int(buf.Ids[i]) for i in range(buf.InList)}


def write_result(raw: bytes) -> None:
    t0 = time.monotonic()
    while job_pids() != {os.getpid()}:
        if time.monotonic() - t0 > 5.0:
            os._exit(4)
        time.sleep(0.01)
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    os._exit(0 if sys.stdin.buffer.read(1) == b"\x06" else 3)


def doc(deliverable, cases):
    return (json.dumps({"schema": "bench-check-result/1", "deliverable": deliverable, "cases": cases, "measures": {}},
                       sort_keys=True) + "\n").encode()


def main():
    args = dict(zip(sys.argv[1::2], sys.argv[2::2], strict=True))
    with open(os.path.join(HERE, "mode.txt"), encoding="utf-8") as f:
        mode = f.read().strip()
    with open(args["--cases"], encoding="utf-8") as f:
        ids = [c["id"] for c in json.load(f)["cases"]]
    os.makedirs(args["--evidence"], exist_ok=True)
    with open(os.path.join(args["--evidence"], "stub.args.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": args["--seed"], "deliverable": args["--deliverable"], "cwd": os.getcwd(),
                   "env": sorted(os.environ)}, f)
    outcome = {"exploited": "exploited", "passed": "passed"}.get(mode, "blocked")
    cases = [{"duration_ms": 1, "id": i, "outcome": outcome} for i in ids]
    if mode == "hang":
        time.sleep(600)
    if mode == "exit5":
        os._exit(5)
    if mode == "malformed":
        write_result(b'{"x": 1}\n')
    if mode == "oversize":
        write_result(b"x" * (70 * 1024) + b"\n")
    if mode == "did_not_build":
        write_result(doc("did not build", []))
    if mode == "tamper":
        open(os.path.join(HERE, "dropped.txt"), "w").close()
    if mode == "two_docs":
        write_result(doc("ran", cases) + doc("ran", cases))
    write_result(doc("ran", cases))


main()
