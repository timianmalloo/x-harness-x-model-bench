"""Every subprocess runs in its own Windows Job Object, or (ADR-0013 Amendment 1, section 5) its own
POSIX process group on macOS.

Pattern: Gateway (PoEAA) for all process control, plus Bulkhead for per-cell lifetime. A job is not a
sandbox: it is how the engine enforces a budget or a stop and knows a process tree has ended.

- spawn: on Windows, the process is created suspended, assigned to a new job, then resumed, so nothing
  it starts can run before it is inside the job (only its own three standard handles are inherited,
  close_fds). On POSIX, the process starts its own session (`start_new_session`, i.e. `setsid()`), so
  its pid is also its process group id, and a watchdog process is started to stand in for kill-on-close
  (below).
- The Windows job is kill-on-close with breakaway never allowed, and its handle is not inheritable, so
  the engine's death kills every cell tree (N2.2) and no child leaves the job (N4). POSIX has no kernel
  primitive that ties a child's life to a handle the way KILL_ON_JOB_CLOSE does (Linux's
  `PR_SET_PDEATHSIG` is Linux-only, not macOS), so a watchdog process supplies the same guarantee: it
  polls this engine's own pid and sends the process group SIGKILL the moment the engine is gone. The
  watchdog runs in its own session too, so killing the cell's group never kills the watchdog with it.
- terminate_and_confirm: terminate (Windows: TerminateJobObject; POSIX: SIGKILL to the process group --
  matching TerminateJobObject's own unconditional hard stop, with no graceful phase of its own), then
  wait for the job to report zero active processes (Windows: the job's active-process count; POSIX:
  `pgrep -g <pgid>` -- ships on macOS and Linux -- returning no pids).
- Accounting: peak memory and CPU time come from the Windows job, with no polling; POSIX accounting is
  not yet built (a follow-up), so `peak_memory`/`cpu_time_ms` raise OSError there, read as `None` by
  callers (module philosophy: never a zeroed guess).
- run: a bounded, deadline-limited command (git, graders) in its own job/group; the tree is always
  terminated when the main process ends or the deadline passes.

Windows or macOS only (NG9, ADR-0013 section 5). Only this module calls `subprocess` (design D3 import
lint).
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from harness_bench.errors import Cause

_KILL_GRACE = 30.0  # seconds run() allows to confirm a kill, then to collect the exit status and the output


class SpawnError(Exception):
    """The process could not be started inside its job/group (HB-CELL-114)."""

    def __init__(self, message: str, win32_error: int | None) -> None:
        label = "win32 error" if sys.platform == "win32" else "errno"  # read live: testable under a patched sys.platform
        super().__init__(f"{Cause.spawn.code}: {message} ({label} {win32_error})")
        self.cause = Cause.spawn
        self.win32_error = win32_error


@dataclass
class CellProcess:
    proc: subprocess.Popen
    job: Job

    @property
    def pid(self) -> int:
        return self.proc.pid

    def wait(self, timeout: float | None = None) -> int:
        """The main process's exit status: unsigned on Windows (e.g. 0xC0000017 for STATUS_NO_MEMORY);
        on POSIX, Python's own signed convention (a negative code -N means killed by signal N) is kept
        as-is -- masking it the Windows way would turn a signal death into a misleading large positive
        number that means nothing on POSIX."""
        code = self.proc.wait(timeout=timeout)
        return code & 0xFFFFFFFF if sys.platform == "win32" else code

    def _reap_posix_zombie(self, bounded: bool = False) -> None:
        """POSIX only, and only ever a no-op elsewhere (ADR-0013 Amendment 1, macOS port): a SIGKILLed
        direct child is a zombie -- its pid table entry persists, so `os.kill(pid, 0)` still reports it
        alive -- until this process reaps it, which `pgrep -g` (Job.active()) does not do. macos-latest CI
        observed a following `os.killpg` on that same, still-unreaped pgid fail with `PermissionError`
        instead of `ProcessLookupError` (tests/test_procs_posix.py). Kept strictly off `sys.platform ==
        "win32"`: windows-latest CI (run 36619679279,
        test_engine.py::test_a_cancelled_turn_is_classified_by_its_kill_reason) showed that even a
        harmless-seeming extra call here is not free on that path -- Job Objects tie engine.py's
        `_end_process` kill-reason classification to wall-clock timing, and Windows never had the zombie
        problem this exists for, so it never runs there rather than being proven safe there. `bounded`
        chooses a short, non-blocking-in-practice `wait()` (the kill was already unconditional) for a
        caller (close()) that may have skipped terminate_and_confirm's own poll()."""
        if sys.platform == "win32":
            return
        if bounded:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        else:
            self.proc.poll()

    def terminate_and_confirm(self, timeout: float) -> bool:
        """Kill the whole tree, re-sending the kill every second; True once the job reports no active
        process. See `_reap_posix_zombie` for why a POSIX pass here also reaps `self.proc`."""
        deadline = time.monotonic() + timeout
        next_kill = 0.0
        while time.monotonic() < deadline:
            if time.monotonic() >= next_kill:
                self.job.terminate()
                next_kill = time.monotonic() + 1.0
            if self.job.active() == 0:
                self._reap_posix_zombie()
                return True
            time.sleep(0.05)
        confirmed = self.job.active() == 0
        if confirmed:
            self._reap_posix_zombie()
        return confirmed

    def close(self) -> None:
        """Close the job first (kill-on-close, or its POSIX stand-in, ends any remaining tree), then the
        pipes. In that order a close never blocks: closing a pipe that a reader thread is blocked on
        waits for the child to exit.

        `close()` can run with no prior `terminate_and_confirm` (a caller may go straight to close()), so
        on POSIX it reaps `self.proc` itself; see `_reap_posix_zombie`."""
        self.job.close()
        self._reap_posix_zombie(bounded=True)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass


def spawn(argv: list[str], cwd, env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) -> CellProcess:
    """Start argv in its own job (Windows) or process group (POSIX). Raises SpawnError, leaving no process."""
    return _spawn_win32(argv, cwd, env, stdin, stdout, stderr) if sys.platform == "win32" else \
        _spawn_posix(argv, cwd, env, stdin, stdout, stderr)


def _parse_pgrep(stdout: str) -> set[int]:
    """Pure (platform-agnostic on purpose, so it is testable on any host): the pids `pgrep -g` printed,
    one per line. A wrong parse here would misread a group that still has members as empty -- a false
    confirmed kill (POSIX termination confirmation, ADR-0013 Amendment 1 section 5)."""
    return {int(p) for p in stdout.split()}


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wt

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

    def _spawn_win32(argv: list[str], cwd, env, stdin, stdout, stderr) -> CellProcess:
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

else:
    import os
    import shutil as _shutil
    import signal

    # The kill-on-close stand-in (module doc): polls the engine's own pid and kills the process group
    # the moment it disappears. A plain script, not a file on disk, so no extra install step; started
    # detached (its own session) so it outlives neither the cell's group nor gets killed with it.
    _WATCHDOG_SRC = (
        "import os,signal,sys,time\n"
        "engine_pid,pgid=int(sys.argv[1]),int(sys.argv[2])\n"
        "while True:\n"
        "    try:\n"
        "        os.kill(engine_pid, 0)\n"
        "    except ProcessLookupError:\n"
        "        break\n"
        "    except PermissionError:\n"
        "        pass\n"
        "    time.sleep(1)\n"
        "try:\n"
        "    os.killpg(pgid, signal.SIGKILL)\n"
        "except ProcessLookupError:\n"
        "    pass\n"
    )

    def _spawn_watchdog(pgid: int) -> subprocess.Popen:
        """assume: `sys.executable` stays resolvable and runnable for the life of the run on macOS (it
        is the same interpreter already running the engine, not a PATH lookup). Confirm: the
        macos-latest CI job's engine-crash test (mirrors test_procs.py::test_engine_crash_kills_every_descendant).
        Breaks if false: a crashed engine leaves its cell tree running, unobserved -- the one guarantee
        this watchdog exists to give."""
        return subprocess.Popen([sys.executable, "-c", _WATCHDOG_SRC, str(os.getpid()), str(pgid)],
                                start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, close_fds=True)

    def _pgrep_pids(pgid: int) -> set[int]:
        """The live pids of process group `pgid`, via `pgrep -g` (ships on macOS's base system and on
        Linux's procps; both are the CI-relevant hosts). Never a zeroed/empty read on failure: raises,
        so a caller reads "not recorded" rather than a false "no processes" (module philosophy).

        assume: `pgrep -g` on macOS (BSD `pgrep`) matches every process whose process group id is
        `pgid`, the same population Windows' Job Object accounting reports. Confirm: the macos-latest
        CI job's `test_spawned_tree_is_in_the_group_and_terminate_confirms_it_gone` (a child that
        starts a grandchild, both left in the group by `setsid`'s default inheritance). Breaks if
        false: `active()`/`pids()` under- or over-count, and `terminate_and_confirm` reports the wrong
        thing -- a wrong confirm, never a silent one, since the CI test asserts the exact pid set."""
        pgrep = _shutil.which("pgrep")
        if pgrep is None:
            raise OSError(f"{Cause.spawn.code}: pgrep not found; cannot confirm a POSIX process group")
        result = subprocess.run([pgrep, "-g", str(pgid)], capture_output=True, text=True, check=False)
        return _parse_pgrep(result.stdout)

    class Job:
        """A POSIX process group standing in for a Windows Job Object (ADR-0013 Amendment 1, section 5).

        No kernel primitive ties a child's life to a handle the way KILL_ON_JOB_CLOSE does, so
        `_spawn_watchdog` supplies that guarantee instead (module doc). Accounting (peak memory, CPU
        time) is not yet built: `peak_memory`/`cpu_time_ms` raise OSError, read as `None` by callers
        (`engine._job_query`), never a zeroed guess.
        """

        def __init__(self) -> None:
            self.pgid: int | None = None
            self._watchdog: subprocess.Popen | None = None

        def attach(self, pgid: int) -> None:
            self.pgid = pgid
            self._watchdog = _spawn_watchdog(pgid)

        def pids(self) -> set[int]:
            if self.pgid is None:
                raise OSError(f"{Cause.spawn.code}: job has no process group")
            return _pgrep_pids(self.pgid)

        def active(self) -> int:
            return len(self.pids())

        def peak_memory(self) -> int:
            raise OSError("peak memory accounting is not built for the POSIX process group (macOS follow-up)")

        def cpu_time_ms(self) -> int:
            raise OSError("CPU time accounting is not built for the POSIX process group (macOS follow-up)")

        def terminate(self, exit_code: int = 1) -> None:
            """SIGKILL, not SIGTERM: a Windows Job Object's TerminateJobObject is an unconditional hard
            stop with no graceful phase of its own (the graceful phase, closing stdin and waiting a
            grace period, is engine.py's, above this layer) -- SIGTERM here could leave a
            signal-ignoring process never confirmed gone, which TerminateJobObject cannot do.

            `PermissionError` is swallowed alongside `ProcessLookupError`: a repeat SIGKILL to a pgid
            whose sole member is already dead but not yet reaped (a zombie; CellProcess.terminate_and_confirm's
            own docstring) can read as EPERM rather than ESRCH on macOS/Darwin -- an already-dead target,
            never a real permission problem for a group this process itself just created."""
            if self.pgid is None:
                return
            try:
                os.killpg(self.pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

        def close(self) -> None:
            """Kill whatever remains of the group (the close-time insurance Windows gets from
            kill-on-close), then stop the watchdog -- it has nothing left to watch. `PermissionError` is
            swallowed for the same reason as `terminate()`: this can run against a pgid already fully
            terminated and reaped by terminate_and_confirm, and macOS can answer that with EPERM."""
            if self.pgid is not None:
                try:
                    os.killpg(self.pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                self.pgid = None
            if self._watchdog is not None:
                self._watchdog.terminate()
                try:
                    self._watchdog.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._watchdog.kill()
                    self._watchdog.wait(timeout=5)
                self._watchdog = None

    def _spawn_posix(argv: list[str], cwd, env, stdin, stdout, stderr) -> CellProcess:
        """Start argv as the leader of its own session (`setsid`: its pid is also its process group id),
        with a watchdog standing in for kill-on-close. Raises SpawnError, leaving no process."""
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=stdout, stderr=stderr,
                                    start_new_session=True, close_fds=True)
        except OSError as exc:
            raise SpawnError(f"cannot start {argv[0]}", getattr(exc, "winerror", None) or exc.errno) from exc
        job = Job()
        job.attach(proc.pid)  # setsid (start_new_session) makes pid == pgid == sid
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
