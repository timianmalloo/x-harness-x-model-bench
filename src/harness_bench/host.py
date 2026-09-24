"""Host facts and controls the engine needs, from kernel32 (Windows only, NG9).

- Process identity: a pid is reused by Windows, so a process is (pid, creation time).
- Sleep detection: QueryUnbiasedInterruptTime excludes time the host was suspended; a gap between it
  and the wall clock over the plan's `suspend_gap` means the host slept during a cell (HB-CELL-106).
  A failed query is not recorded, and a missing reading is not sleep.
- The power request (SetThreadExecutionState) keeps the host awake for the run; it is per thread, so
  the engine thread sets and clears it.
- Available physical memory for each outcome (GlobalMemoryStatusEx). A failed query is not recorded.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

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


def keep_awake(on: bool) -> None:
    _k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED if on else ES_CONTINUOUS)


def available_memory() -> int | None:
    """Available physical bytes, or None when the query fails (not recorded)."""
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not _k32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)
