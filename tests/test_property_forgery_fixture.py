"""W1-F spike SP-F2, committed (RV-SEC W1-F finding 1; RV-TA W1-F finding 5): the module-body forgery fixture and its pair.

The grader side here is the spike's: a kill-on-close job, the check started suspended and DETACHED with the base
interpreter and `-S`, a first-byte job query, the one-byte acknowledgement, stdin closed on every path, the exit time
from GetProcessTimes, and W0 rev 2 section 3's outcome rows 2 and 4-7 (no suspend and no `check/` copy here, so rows 1
and 3 are not exercised). X-F's `tests/test_property_grader.py` re-runs the same fixture through the real grader.

- The control proves the fixture forges: imported into the check, its forged `blocked` line is the accepted result.
- The refusal proves the shipped shape (a probe-host child with pipes the check owns) never yields that line.
- The probe-host control proves the refusal is not vacuous: the same host shape answers a probe with the raw response.
Each runs three trials in one node, the spike's count.
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from harness_bench import procs

pytestmark = pytest.mark.native

FIX = Path(__file__).parent / "fixtures" / "property"
OUTER_S = 20.0
MAX_RESULT_BYTES = 64 * 1024  # W0 rev 2 section 3 framing
TRIALS = 3


def _filetime_now() -> int:
    t = ctypes.c_ulonglong()
    ctypes.windll.kernel32.GetSystemTimePreciseAsFileTime(ctypes.byref(t))
    return t.value


def _exit_filetime(proc) -> int:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    c, e, k, u = (ctypes.c_ulonglong() for _ in range(4))
    assert k32.GetProcessTimes(int(proc._handle), ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
    return e.value


def _valid(doc) -> bool:
    if not isinstance(doc, dict) or set(doc) != {"schema", "deliverable", "cases", "measures"}:
        return False
    if doc["schema"] != "bench-check-result/1" or doc["measures"] != {}:
        return False
    if doc["deliverable"] in ("did not build", "did not start"):
        return doc["cases"] == []
    return (doc["deliverable"] == "ran" and len(doc["cases"]) == 1 and doc["cases"][0].get("id") == "inj-1"
            and doc["cases"][0].get("outcome") in ("blocked", "exploited", "timeout"))


def _grade(mode: str, app: str, evid: Path) -> dict:
    """One check run, classified by W0 rev 2 section 3 (first matching row decides)."""
    evid.mkdir(parents=True)
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP") if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    job = procs.Job()
    proc = subprocess.Popen(
        [sys._base_executable, "-S", str(FIX / "spike_check.py"), mode, str(evid / "check"), str(FIX), app],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(evid / "check.stderr", "wb"), close_fds=True,
        creationflags=0x4 | 0x8, env=env)  # CREATE_SUSPENDED | DETACHED_PROCESS (spike E1-S3)
    try:
        handle = procs._open_process(proc.pid)
        assert procs._assign(job.handle, handle)
        procs._ntdll.NtResumeProcess(handle)
        procs._k32.CloseHandle(handle)
        t0 = time.monotonic()
        st = {"buf": b"", "arrival": None, "view": None}
        line_ready = threading.Event()

        def reader():
            while chunk := proc.stdout.read1(65536):
                if st["arrival"] is None:
                    st["arrival"], st["view"] = _filetime_now(), job.pids()
                st["buf"] += chunk
                if b"\n" in st["buf"]:
                    line_ready.set()
            line_ready.set()

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        bound = not line_ready.wait(OUTER_S)
        line = st["buf"].partition(b"\n")[0]
        try:
            doc = json.loads(line) if line and len(line) <= MAX_RESULT_BYTES else None
        except ValueError:
            doc = None
        alone = st["view"] == {proc.pid}
        acked = not bound and alone and _valid(doc)
        if acked:
            proc.stdin.write(b"\x06")
        proc.stdin.close()  # on every path
        try:
            code = proc.wait(timeout=max(0.1, OUTER_S - (time.monotonic() - t0)))
        except subprocess.TimeoutExpired:
            bound, code = True, None
        t.join(5)
        documents = st["buf"].count(b"\n") + (0 if st["buf"].endswith(b"\n") or not st["buf"] else 1)
        exit_after = code is not None and st["arrival"] is not None and _exit_filetime(proc) > st["arrival"]
        if bound:
            row = 2
        elif (not alone or documents != 1 or not exit_after or not line
              or code != (0 if acked else 3)):
            row = 4
        elif not _valid(doc):
            row = 5
        elif doc["deliverable"] != "ran":
            row = 6
        else:
            row = 7
        return {"row": row, "doc": doc if row in (6, 7) else None, "exit_code": code, "documents": documents}
    finally:
        job.terminate()
        job.close()


def test_module_body_forgery_is_accepted_when_imported_in_check(tmp_path):
    """Positive control: the fixture bites. The honest check would answer `exploited`; the forged line says `blocked`."""
    for n in range(TRIALS):
        r = _grade("in-check-import", "forge_module:handle", tmp_path / f"t{n}")
        assert r["row"] == 7, r
        assert r["doc"]["cases"][0]["outcome"] == "blocked", r


def test_module_body_forgery_in_probe_host_is_refused(tmp_path):
    """The shipped shape: the forged line is the probe host's first line, not its ready line, so `did not start`."""
    for n in range(TRIALS):
        r = _grade("probe-host", "forge_module:handle", tmp_path / f"t{n}")
        assert r["row"] == 6, r  # a measured 0 (EV-1), never a forged score
        assert r["doc"]["deliverable"] == "did not start", r
        assert all(c["outcome"] != "blocked" for c in r["doc"]["cases"]), r


def test_probe_host_control_answers_with_the_raw_response(tmp_path):
    """The same host shape serves a probe: an unescaped echo is `exploited`, decided in the check."""
    for n in range(TRIALS):
        r = _grade("probe-host", "vulnerable_app:handle", tmp_path / f"t{n}")
        assert r["row"] == 7, r
        assert r["doc"]["deliverable"] == "ran" and r["doc"]["cases"][0]["outcome"] == "exploited", r
