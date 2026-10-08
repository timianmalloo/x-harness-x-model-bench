"""Windows check tool (R6.15a, C-W0).

Lists each visible top-level window (EnumWindows, IsWindowVisible, through
stdlib ctypes) whose process is --root-pid or a descendant and was created at
or after --since, one line per window with pid, image name and window class.
Prints no window title.

Exit codes:
  0: none (or host is not Windows: 'not recorded: not Windows')
  1: some listed
  2: check failed (which never reads as none)
"""

import argparse
import os
import sys
from collections import defaultdict, deque
from datetime import UTC, datetime

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes


def _get_process_creation_time(pid: int) -> datetime | None:
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        c = wintypes.FILETIME()
        e = wintypes.FILETIME()
        k = wintypes.FILETIME()
        u = wintypes.FILETIME()
        if kernel32.GetProcessTimes(
            h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)
        ):
            val = (c.dwHighDateTime << 32) + c.dwLowDateTime
            if val == 0:
                return None
            epoch = 116444736000000000
            ts = (val - epoch) / 10000000.0
            return datetime.fromtimestamp(ts, tz=UTC)
        return None
    finally:
        kernel32.CloseHandle(h)


def _get_process_image_name(pid: int, fallback: str = "unknown") -> str:
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return fallback
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return fallback
    finally:
        kernel32.CloseHandle(h)


def _collect_descendants(root_pid: int) -> dict[int, str]:
    kernel32 = ctypes.windll.kernel32

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    h_snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if h_snap == -1:
        raise RuntimeError("CreateToolhelp32Snapshot failed")

    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
    children: dict[int, list[int]] = defaultdict(list)
    names: dict[int, str] = {}
    try:
        if kernel32.Process32FirstW(h_snap, ctypes.byref(pe)):
            while True:
                children[pe.th32ParentProcessID].append(pe.th32ProcessID)
                names[pe.th32ProcessID] = pe.szExeFile
                if not kernel32.Process32NextW(h_snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(h_snap)

    all_pids: dict[int, str] = {root_pid: names.get(root_pid, "unknown")}

    queue: deque[int] = deque([root_pid])
    while queue:
        curr = queue.popleft()
        for child in children.get(curr, []):
            if child not in all_pids:
                all_pids[child] = names.get(child, "unknown")
                queue.append(child)

    return all_pids


def _scan_visible_windows(
    valid_pids: dict[int, str],
) -> list[tuple[int, str, str]]:
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    matches: list[tuple[int, str, str]] = []

    def enum_cb(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in valid_pids:
                buf = ctypes.create_unicode_buffer(512)
                user32.GetClassNameW(hwnd, buf, 512)
                matches.append((pid.value, valid_pids[pid.value], buf.value))
        return True

    cb = WNDENUMPROC(enum_cb)
    user32.EnumWindows(cb, 0)
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List visible top-level windows of session processes."
    )
    parser.add_argument(
        "--since",
        required=True,
        help="ISO-8601 UTC instant (e.g. 2026-10-08T18:45:19Z)",
    )
    parser.add_argument(
        "--root-pid",
        required=True,
        type=int,
        help="Root process ID to inspect",
    )

    args = parser.parse_args()

    if sys.platform != "win32":
        print("not recorded: not Windows")
        sys.exit(0)

    try:
        since_dt = datetime.fromisoformat(args.since)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=UTC)
        else:
            since_dt = since_dt.astimezone(UTC)
    except (ValueError, TypeError) as exc:
        sys.stderr.write(f"window_check: invalid --since: {exc}\n")
        sys.exit(2)

    if args.root_pid <= 0:
        sys.stderr.write(
            f"window_check: invalid --root-pid: {args.root_pid} (must be > 0)\n"
        )
        sys.exit(2)

    try:
        candidates = _collect_descendants(args.root_pid)
        valid_pids: dict[int, str] = {}
        for pid, fallback_name in candidates.items():
            creation_time = _get_process_creation_time(pid)
            if creation_time is not None and creation_time >= since_dt:
                valid_pids[pid] = _get_process_image_name(pid, fallback_name)

        matches = _scan_visible_windows(valid_pids)
    except (OSError, RuntimeError) as exc:
        sys.stderr.write(f"window_check failed: {exc}\n")
        sys.exit(2)

    if matches:
        for pid, img, cls_name in sorted(matches):
            print(f"{pid} {img} {cls_name}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
