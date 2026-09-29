"""Host facts and controls the engine needs: from kernel32 on Windows, from POSIX/BSD tools (via
`procs.run`, the only sanctioned subprocess gateway, D3) and stdlib `time.CLOCK_UPTIME_RAW` on macOS
(ADR-0013 Amendment 1, section 5).

- Process identity: a pid is reused, so a process is (pid, creation time).
- Sleep detection: a gap between wall-clock time and a clock that excludes suspended time, over the
  plan's `suspend_gap`, means the host slept during a cell (HB-CELL-106). Windows:
  QueryUnbiasedInterruptTime; macOS: `time.CLOCK_UPTIME_RAW` (stdlib, Darwin-only). A failed query is
  not recorded, and a missing reading is not sleep.
- The power request keeps the host awake for the run (Windows: SetThreadExecutionState, per thread, so
  the engine thread sets and clears it; macOS: not yet built, a follow-up -- see `keep_awake`).
- Available physical memory for each outcome (Windows: GlobalMemoryStatusEx; macOS: not yet built, a
  follow-up). A failed or not-yet-built query is not recorded, never a zeroed guess.
"""

from __future__ import annotations

import sys
import time

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wt

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wt.HANDLE
    _k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    _k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
    _k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
    _k32.CloseHandle.argtypes = [wt.HANDLE]
    _k32.QueryUnbiasedInterruptTime.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
    _k32.QueryUnbiasedInterruptTime.restype = wt.BOOL
    _k32.SetThreadExecutionState.argtypes = [wt.DWORD]
    _k32.SetThreadExecutionState.restype = wt.DWORD

    _QUERY_LIMITED = 0x1000
    _STILL_ACTIVE = 259
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    _k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatus)]
    _k32.GlobalMemoryStatusEx.restype = wt.BOOL

    def creation_time(pid: int) -> int:
        """The process's creation time (FILETIME, 100 ns since 1601), or 0 if it cannot be opened."""
        handle = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
        if not handle:
            return 0
        try:
            created, exited, kernel, user = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            if not _k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
                return 0
            return (created.dwHighDateTime << 32) | created.dwLowDateTime
        finally:
            _k32.CloseHandle(handle)

    def process_alive(pid: int, created: int) -> bool:
        """True only if this exact process (pid and creation time) is still running."""
        handle = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
        if not handle:
            return False
        try:
            code = wt.DWORD()
            if not _k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != _STILL_ACTIVE:
                return False
        finally:
            _k32.CloseHandle(handle)
        return creation_time(pid) == created

    def unbiased_seconds() -> float | None:
        """Seconds since boot, excluding time the host was suspended. None when the query fails."""
        value = ctypes.c_ulonglong()
        if not _k32.QueryUnbiasedInterruptTime(ctypes.byref(value)):
            return None
        return value.value / 1e7

    def keep_awake(on: bool) -> None:
        _k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED if on else ES_CONTINUOUS)

    def available_memory() -> int | None:
        """Available physical bytes, or None when the query fails (not recorded)."""
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not _k32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPhys)

else:
    import os
    from datetime import datetime

    from harness_bench import procs

    def creation_time(pid: int) -> int:
        """The process's start time as a whole-second epoch timestamp (BSD `ps -o lstart=`, via
        `procs.run` -- the only sanctioned subprocess gateway, D3), or 0 if it cannot be read. Not a
        Windows FILETIME (a different unit and epoch, module doc): callers only ever compare two
        readings of this same function for equality (`process_alive`), never this one against the
        Windows one."""
        result = procs.run(["ps", "-o", "lstart=", "-p", str(pid)], cwd=None, env=None, timeout=5)
        line = result.stdout.strip()
        if result.returncode != 0 or not line:
            return 0
        try:
            # `ps` prints the host's local wall-clock time with no zone; naive-local is the right
            # reading (this value is only ever compared against another reading of itself).
            return int(datetime.strptime(line, "%a %b %d %H:%M:%S %Y").timestamp())  # noqa: DTZ007
        except ValueError:
            return 0

    def process_alive(pid: int, created: int) -> bool:
        """True only if this exact process (pid and creation time) is still running."""
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return creation_time(pid) == created

    def unbiased_seconds() -> float | None:
        """assume: `time.CLOCK_UPTIME_RAW` (Darwin-only; stdlib exposes it only where the platform
        defines it) excludes system-sleep time, the guarantee Windows' QueryUnbiasedInterruptTime
        gives (macOS's `clock_gettime(3)`: "does not increment while the system is asleep" -- recalled
        from documentation, not opened on this Windows host). Confirm: the macos-latest CI job's
        SleepDetector real-value test. Breaks if false: a host sleep during a cell misreads as active
        elapsed time, so `Cause.host_suspended` never fires on macOS the way it does on Windows -- a
        suspend-caused failure would then be misclassified (e.g. `timed_out`), never a silent pass."""
        clock = getattr(time, "CLOCK_UPTIME_RAW", None)
        if clock is None:
            return None
        try:
            return time.clock_gettime(clock)
        except OSError:
            return None

    def keep_awake(on: bool) -> None:
        """Not yet built for macOS (follow-up: `caffeinate -i` for the run's duration, via
        `procs.spawn`). A no-op here is a declared gap, not a silently wrong answer: `SleepDetector` +
        `Cause.host_suspended` (engine.py) still catch and correctly classify a host sleep during a
        cell either way; this only forgoes pre-empting it."""
        return

    def available_memory() -> int | None:
        """Not yet built for macOS (follow-up). Callers already read `None` as "not recorded", never a
        zeroed guess (module philosophy) -- the same contract as a failed Windows query."""
        return None


class SleepDetector:
    def __init__(self, gap_seconds: float) -> None:
        self.gap = gap_seconds
        self._wall = time.time()
        self._unbiased = unbiased_seconds()

    def slept(self) -> bool:
        """True if the host slept longer than the gap since the last call.

        A missing reading is not sleep: return False instead of raising, and keep the last good anchor.
        """
        wall, unbiased = time.time(), unbiased_seconds()
        if unbiased is None or self._unbiased is None:
            if unbiased is not None:  # the first good reading becomes the anchor; there is nothing to compare yet
                self._wall, self._unbiased = wall, unbiased
            return False
        gap = (wall - self._wall) - (unbiased - self._unbiased)
        self._wall, self._unbiased = wall, unbiased
        return gap > self.gap
