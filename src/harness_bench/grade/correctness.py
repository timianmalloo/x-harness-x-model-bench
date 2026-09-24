"""Correctness from hidden tests (US-28): pass@1 and partial credit for one archived cell.

- The hidden tests run in a grading copy (the archived working copy, then the task's `tests/`), never in
  the archive, in their own Job Object under the grading-step deadline (HB-GRD-002). The copy is removed
  afterwards; the oracle's output is kept as the evidence.
- Phase 1 knows one oracle runner, `unittest`. Its summary (`Ran N tests`, then `OK` or `FAILED (...)`)
  is parsed strictly; output without one is NA, never 0. A pass needs exit status 0 and every test passed.
- pass@k, pass^k, regressions and build checks are later phases (Spec S-08b).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import archive, procs
from harness_bench.profiles import CELL_ENV

RAN = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
RESULT = re.compile(r"^(?:OK|FAILED)(?: \(([^)]*)\))?\s*$", re.MULTILINE)
NOT_PASSED = ("failures", "errors", "skipped", "expected failures", "unexpected successes")
HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")


@dataclass(frozen=True)
class Result:
    passed: int | None  # pass@1 for this cell: 1 or 0
    partial_credit: Decimal | None  # fraction of hidden tests passing
    reason: str | None
    evidence: str  # relative to the run directory


def parse_unittest(output: str) -> tuple[int, int] | None:
    """(tests run, tests passed) from unittest's summary, or None when there is no well-formed summary."""
    ran, result = RAN.findall(output), RESULT.findall(output)
    if not ran or not result:
        return None
    total, failed = int(ran[-1]), 0
    for part in filter(None, (p.strip() for p in result[-1].split(","))):
        name, _, count = part.partition("=")
        if name not in NOT_PASSED or not count.isdigit():
            return None
        failed += int(count)
    return total, max(total - failed, 0)


def _env() -> dict[str, str]:
    env = {k: os.environ[k] for k in HOST_ENV if k in os.environ}
    return {**env, **CELL_ENV, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"}


def grade(ws: Path, task_dir: Path, oracle: dict, out_dir: Path, run_dir: Path, timeout: float) -> Result:
    if oracle.get("runner") != "unittest" or not oracle.get("command"):
        return Result(None, None, f"oracle runner {oracle.get('runner')!r} not built (phase 1 runs unittest)", "")
    if not ws.is_dir():
        return Result(None, None, "no working copy in the archive", "")
    work = out_dir / "work"
    shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".git"))
    shutil.copytree(task_dir / "tests", work, dirs_exist_ok=True)
    argv = [sys.executable if a == "{python}" else a for a in oracle["command"]]
    try:
        done = procs.run(argv, cwd=work, env=_env(), timeout=timeout)
    finally:
        shutil.rmtree(work, onexc=archive.make_writable)
    log = out_dir / "oracle.log"
    log.write_text(f"$ {' '.join(oracle['command'])}\nexit {done.returncode}\n--- stdout\n{done.stdout}\n--- stderr\n{done.stderr}",
                   encoding="utf-8")
    evidence = log.relative_to(run_dir).as_posix()
    if done.timed_out:
        return Result(None, None, f"HB-GRD-002 grading step timeout after {timeout:g} s", evidence)
    parsed = parse_unittest(done.stderr)
    if parsed is None:
        return Result(None, None, "oracle output has no unittest summary", evidence)
    total, passed = parsed
    if total == 0:
        return Result(None, None, "no hidden test ran", evidence)
    return Result(int(done.returncode == 0 and passed == total), Decimal(passed) / Decimal(total), None, evidence)
