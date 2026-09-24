"""Preflight before `bench run` (design: Run-level codes). Each check stops the run with its code.

- HB-PRE-002: an agent instruction file in the cells root or an ancestor (every cell would load it).
- HB-PRE-003: free disk under the cells root below 20 GB. (A projected need from measured peaks is a
  phase-2 upgrade; no estimate is guessed here.)
- HB-PRE-005: Windows long paths not enabled. Bench git always runs with `core.longpaths=true`
  (gitsafe), and cells get it through their environment (profiles.CELL_ENV).
- HB-PRE-007: a planned harness build missing from the tools folder, or its hash differs from the plan.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from harness_bench import tools, workspace
from harness_bench.errors import BenchError

MIN_FREE_BYTES = 20 * 1024**3


def long_paths_enabled() -> bool | None:
    """Windows `LongPathsEnabled`; None off Windows or when the value cannot be read."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return None


def check(plan: dict, cells_root: Path, tools_dir: Path, min_free: int = MIN_FREE_BYTES,
          long_paths: Callable[[], bool | None] = long_paths_enabled) -> dict:
    """Run every check; return the facts it measured."""
    workspace.check_cells_root(cells_root)
    cells_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(cells_root).free
    if free < min_free:
        raise BenchError("HB-PRE-003", f"{free // 1024**3} GB free under {cells_root}; at least {min_free // 1024**3} GB is needed")
    if long_paths() is False:
        raise BenchError("HB-PRE-005", "Windows long paths are off (HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem LongPathsEnabled)")
    installed = tools.resolve(tools_dir)
    for harness, planned in sorted(plan["builds"].items()):
        if harness not in installed:
            raise BenchError("HB-PRE-007", f"no installed build for {harness}")
        try:
            tools.check_build(installed[harness], planned)
        except tools.BuildChanged as exc:
            raise BenchError("HB-PRE-007", f"{exc}; re-plan, or reinstall the planned build") from exc
    return {"free_bytes": free}
