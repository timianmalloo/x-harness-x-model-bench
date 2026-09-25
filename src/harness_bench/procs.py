"""Every subprocess runs in its own Windows Job Object (ADR-0013; spikes N2, N4).

Pattern: Gateway (PoEAA) for all process control, plus Bulkhead for per-cell lifetime. A job is not a
sandbox: it is how the engine enforces a budget or a stop and knows a process tree has ended.

- spawn: the process is created suspended, assigned to a new job, then resumed, so nothing it starts
  can run before it is inside the job. Only its own three standard handles are inherited (close_fds).
- The job is kill-on-close with breakaway never allowed, and its handle is not inheritable, so the
  engine's death kills every cell tree (N2.2) and no child leaves the job (N4).
- terminate_and_confirm: TerminateJobObject, then wait for the job's active-process count to reach 0.
- Accounting: peak memory and CPU time come from the job, with no polling.
- run: a bounded, deadline-limited command (git, graders) in its own job; the tree is always
  terminated when the main process ends or the deadline passes.

Windows only (NG9). Only this module calls `subprocess` (design D3 import lint).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import threading
import time
from dataclasses import dataclass

from harness_bench.errors import Cause

KILL_ON_JOB_CLOSE = 0x2000
BREAKAWAY_OK = 0x800
SILENT_BREAKAWAY_OK = 0x1000
DIE_ON_UNHANDLED_EXCEPTION = 0x400
_CREATE_SUSPENDED = 0x4
_CREATE_NO_WINDOW = 0x08000000
_PROCESS_ALL_ACCESS = 0x1F0FFF
_HANDLE_FLAG_INHERIT = 0x1
_BASIC_ACCOUNTING = 1
_BASIC_PID_LIST = 3
_EXTENDED_LIMIT = 9
_MAX_PIDS = 1024
_ERROR_INVALID_HANDLE = 6
_KILL_GRACE = 30.0  # seconds run() allows to confirm a kill, then to collect the exit status and the output

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ntdll = ctypes.WinDLL("ntdll")
_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
_k32.AssignProcessToJobObject.restype = wt.BOOL
_k32.TerminateJobObject.argtypes = [wt.HANDLE, wt.UINT]
_k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
_k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
_k32.GetHandleInformation.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
_ntdll.NtResumeProcess.argtypes = [wt.HANDLE]


class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]


class _BasicLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [("Basic", _BasicLimit), ("Io", _IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


class _BasicAccounting(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wt.DWORD), ("TotalProcesses", wt.DWORD),
                ("ActiveProcesses", wt.DWORD), ("TotalTerminatedProcesses", wt.DWORD)]


class _PidList(ctypes.Structure):
    _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD), ("Ids", ctypes.c_size_t * _MAX_PIDS)]


class SpawnError(Exception):
    """The process could not be started inside its job (HB-CELL-114)."""

    def __init__(self, message: str, win32_error: int | None) -> None:
        super().__init__(f"{Cause.spawn.code}: {message} (win32 error {win32_error})")
        self.cause = Cause.spawn
        self.win32_error = win32_error


# Fault seams for tests: the two calls whose failure must leave no process behind.
def _assign(job: int, handle: int) -> bool:
    return bool(_k32.AssignProcessToJobObject(job, handle))


def _open_process(pid: int) -> int:
    return _k32.OpenProcess(_PROCESS_ALL_ACCESS, False, pid)


# Fault seam: a failed query must raise, never leave a zeroed struct that reads as "no processes".
def _query(job: int | None, info_class: int, buf: ctypes.Structure) -> bool:
    return bool(_k32.QueryInformationJobObject(job, info_class, ctypes.byref(buf), ctypes.sizeof(buf), None))


class Job:
    """One kill-on-close Job Object with breakaway never allowed."""

    def __init__(self) -> None:
        handle = _k32.CreateJobObjectW(None, None)  # NULL security attributes: not inheritable
        if not handle:
            raise SpawnError("CreateJobObject failed", ctypes.get_last_error())
        info = _ExtendedLimit()
        info.Basic.LimitFlags = KILL_ON_JOB_CLOSE | DIE_ON_UNHANDLED_EXCEPTION
        if not _k32.SetInformationJobObject(handle, _EXTENDED_LIMIT, ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            _k32.CloseHandle(handle)
            raise SpawnError("SetInformationJobObject failed", err)
        self.handle = handle

    def _query[S: ctypes.Structure](self, info_class: int, buf: S) -> S:
        """Fill `buf` from the job, or raise OSError from the last error."""
        if not self.handle:  # a NULL handle would query the job of the calling process instead
            raise ctypes.WinError(_ERROR_INVALID_HANDLE)
        if not _query(self.handle, info_class, buf):
            raise ctypes.WinError(ctypes.get_last_error())
        return buf

    def _extended(self) -> _ExtendedLimit:
        return self._query(_EXTENDED_LIMIT, _ExtendedLimit())

    def _accounting(self) -> _BasicAccounting:
        return self._query(_BASIC_ACCOUNTING, _BasicAccounting())

    def limit_flags(self) -> int:
        return self._extended().Basic.LimitFlags

    def inheritable(self) -> bool:
        flags = wt.DWORD()
        if not self.handle or not _k32.GetHandleInformation(self.handle, ctypes.byref(flags)):  # same class: no zeroed answer
            raise ctypes.WinError(ctypes.get_last_error() or _ERROR_INVALID_HANDLE)
        return bool(flags.value & _HANDLE_FLAG_INHERIT)

    def active(self) -> int:
        return self._accounting().ActiveProcesses

    def pids(self) -> set[int]:
        buf = self._query(_BASIC_PID_LIST, _PidList())
        return {int(buf.Ids[i]) for i in range(buf.InList)}

    def peak_memory(self) -> int:
        return int(self._extended().PeakJobMemoryUsed)

    def cpu_time_ms(self) -> int:
        acc = self._accounting()
        return (acc.TotalUserTime + acc.TotalKernelTime) // 10_000

    def terminate(self, exit_code: int = 1) -> None:
        _k32.TerminateJobObject(self.handle, exit_code)

    def close(self) -> None:
        if self.handle:
            _k32.CloseHandle(self.handle)
            self.handle = None


@dataclass
class CellProcess:
    proc: subprocess.Popen
    job: Job

    @property
    def pid(self) -> int:
        return self.proc.pid

    def wait(self, timeout: float | None = None) -> int:
        """The main process's exit status, unsigned (e.g. 0xC0000017 for STATUS_NO_MEMORY)."""
        return self.proc.wait(timeout=timeout) & 0xFFFFFFFF

    def terminate_and_confirm(self, timeout: float) -> bool:
        """Kill the whole tree, re-sending the kill every second; True once the job reports no active process."""
        deadline = time.monotonic() + timeout
        next_kill = 0.0
        while time.monotonic() < deadline:
            if time.monotonic() >= next_kill:
                self.job.terminate()
                next_kill = time.monotonic() + 1.0
            if self.job.active() == 0:
                return True
            time.sleep(0.05)
        return self.job.active() == 0

    def close(self) -> None:
        """Close the job first (kill-on-close ends any remaining tree), then the pipes. In that order a
        close never blocks: closing a pipe that a reader thread is blocked on waits for the child to exit."""
        self.job.close()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass


def spawn(argv: list[str], cwd, env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) -> CellProcess:
    """Start argv suspended, assign it to a new job, resume it. Raises SpawnError, leaving no process."""
    job = Job()
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=stdout, stderr=stderr,
                                creationflags=_CREATE_SUSPENDED | _CREATE_NO_WINDOW, close_fds=True)
    except OSError as exc:
        job.close()
        raise SpawnError(f"cannot start {argv[0]}", getattr(exc, "winerror", None) or exc.errno) from exc
    handle = _open_process(proc.pid)
    if not handle or not _assign(job.handle, handle):
        err = ctypes.get_last_error()
        try:
            if handle:
                _k32.TerminateProcess(handle, 1)
                _k32.CloseHandle(handle)
            else:
                proc.kill()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                # Already terminated above (TerminateProcess, or kill when OpenProcess failed).
                # Swallow the timeout so the finally closes the job and the caller gets SpawnError.
                pass
        finally:
            job.close()
        raise SpawnError(f"cannot assign pid {proc.pid} to its job", err)
    _ntdll.NtResumeProcess(handle)
    _k32.CloseHandle(handle)
    return CellProcess(proc, job)


@dataclass
class Completed:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    seconds: float


def _drain(stream, limit: int, sink: list, flags: list) -> None:
    kept = 0
    for chunk in iter(lambda: stream.read(65536), b""):
        room = limit - kept
        if room > 0:
            sink.append(chunk[:room])
            kept += min(len(chunk), room)
        if len(chunk) > room:
            flags.append(True)


def _feed(stream, data: bytes) -> None:
    """Write `data` to the child's stdin, then close it (EOF). A child that exits or closes stdin early ends it."""
    try:
        stream.write(data)
    except OSError:
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def run(argv: list[str], cwd, env, timeout: float, max_output: int = 1 << 20, input: str | None = None) -> Completed:
    """Run a bounded command in its own job; the whole tree is terminated when it ends or times out.

    `input`, when given, is written to the child's stdin as UTF-8 from a thread (so a large text cannot deadlock
    against the output pipes), then stdin is closed; otherwise stdin is the null device."""
    started = time.monotonic()
    cell = spawn(argv, cwd, env, stdin=subprocess.DEVNULL if input is None else subprocess.PIPE,
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err, trunc = [], [], []
    readers = [threading.Thread(target=_drain, args=(cell.proc.stdout, max_output, out, trunc), daemon=True),
               threading.Thread(target=_drain, args=(cell.proc.stderr, max_output, err, trunc), daemon=True)]
    if input is not None:
        readers.append(threading.Thread(target=_feed, args=(cell.proc.stdin, input.encode("utf-8")), daemon=True))
    for t in readers:
        t.start()
    timed_out = False
    code: int | None = None
    try:
        try:
            code = cell.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        cell.terminate_and_confirm(timeout=_KILL_GRACE)
        if code is None:
            try:
                code = cell.wait(timeout=_KILL_GRACE)
            except subprocess.TimeoutExpired:
                pass  # an unconfirmed kill: no exit status is reported; closing the job below ends the tree
        deadline = time.monotonic() + _KILL_GRACE
        for t in readers:
            t.join(timeout=max(0.0, deadline - time.monotonic()))
    finally:
        cell.close()  # the job (kill-on-close) and the pipes, on every path

    def decode(parts: list) -> str:
        return b"".join(parts).decode("utf-8", errors="replace")

    return Completed(code, decode(out), decode(err), timed_out, bool(trunc), time.monotonic() - started)
