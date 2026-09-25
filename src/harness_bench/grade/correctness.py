"""Correctness from hidden tests (US-28): pass@1 and partial credit for one archived cell.

- The hidden tests run in a grading copy (the archived working copy, then the task's `tests/`), never in
  the archive, in their own Job Object under the grading-step deadline (HB-GRD-002). The copy is removed
  afterwards; the oracle's output is kept as the evidence.
- `unittest` summaries and the named TRX file from a `dotnet` oracle are parsed strictly; a missing or
  invalid summary is NA, never 0. A pass needs exit status 0 and every test passed.
- pass@k, pass^k, regressions and build checks are later phases (Spec S-08b).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import archive, procs
from harness_bench.grade import CellInput, Score
from harness_bench.profiles import CELL_ENV

RAN = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
RESULT = re.compile(r"^(?:OK|FAILED)(?: \(([^)]*)\))?\s*$", re.MULTILINE)
NOT_PASSED = ("failures", "errors", "skipped", "expected failures", "unexpected successes")
HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")
DOTNET_HOST_ENV = ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "ProgramData", "ProgramFiles",
                   "NUGET_PACKAGES")


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


def _trx_spec(command: list[str]) -> tuple[str, str] | None:
    """The oracle's exact TRX filename and result-directory name."""
    logger = None
    results_dir = "TestResults"
    for index, arg in enumerate(command):
        if arg in ("--logger", "-l") and index + 1 < len(command):
            logger = command[index + 1]
        elif arg.startswith(("--logger:", "--logger=")):
            logger = arg[9:]
        elif arg == "--results-directory" and index + 1 < len(command):
            results_dir = command[index + 1]
        elif arg.startswith("--results-directory="):
            results_dir = arg.partition("=")[2]
    if not logger or not re.match(r"^trx(?:\s*;|\s*$)", logger.strip(), re.IGNORECASE):
        return None
    match = re.search(r"(?:^|;)\s*LogFileName\s*=\s*([^;]+)", logger, re.IGNORECASE)
    if not match:
        return None
    name = match.group(1).strip().strip('"')
    if not name or Path(name).name != name or Path(name).suffix.lower() != ".trx":
        return None
    return name, Path(results_dir).name


def _trx_matches(work: Path, spec: tuple[str, str]) -> list[Path]:
    """Find only the named TRX under a result directory, including nested test projects."""
    name, directory = spec
    return sorted(p for p in work.rglob(name) if p.is_file() and p.parent.name.casefold() == directory.casefold())


def parse_trx(path: Path) -> tuple[int, int] | None:
    """(total, passed) from the named TRX ResultSummary/Counters, or None if invalid."""
    try:
        root = ET.parse(path).getroot()
        if root.tag.rpartition("}")[2] != "TestRun":
            return None
        summaries = [e for e in root if e.tag.rpartition("}")[2] == "ResultSummary"]
        if len(summaries) != 1:
            return None
        counters = [e for e in summaries[0] if e.tag.rpartition("}")[2] == "Counters"]
        if len(counters) != 1:
            return None
        total = int(counters[0].attrib["total"])
        passed = int(counters[0].attrib["passed"])
    except (ET.ParseError, OSError, KeyError, ValueError):
        return None
    return (total, passed) if total >= 0 and 0 <= passed <= total else None


def grade(ws: Path, task_dir: Path, oracle: dict, out_dir: Path, run_dir: Path, timeout: float) -> Result:
    kind = oracle.get("runner")
    if kind not in ("unittest", "dotnet") or not oracle.get("command"):
        return Result(None, None, f"oracle runner {kind!r} not built (phase 1 runs unittest)", "")
    if not ws.is_dir():
        return Result(None, None, "no working copy in the archive", "")
    work = out_dir / "work"
    shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".git"))
    shutil.copytree(task_dir / "tests", work, dirs_exist_ok=True)
    argv = [sys.executable if a == "{python}" else a for a in oracle["command"]]
    env = _env()
    if kind == "dotnet":
        # ADR-0013: grading runs natively on the host, so dotnet uses the host profile and NuGet cache.
        env.update({k: os.environ[k] for k in DOTNET_HOST_ENV if k in os.environ})
    version = ""
    version_done = None
    spec = _trx_spec(oracle["command"]) if kind == "dotnet" else None
    if spec:
        for old in _trx_matches(work, spec):
            old.unlink()  # discard archived results in this disposable copy before the new step
    started = time.monotonic()
    try:
        if kind == "dotnet":
            version_done = procs.run(["dotnet", "--version"], cwd=work, env=env, timeout=timeout)
            version = version_done.stdout.strip()
        remaining = timeout - (time.monotonic() - started)
        done = procs.run(argv, cwd=work, env=env, timeout=max(remaining, 0)) if remaining > 0 and not (version_done and version_done.timed_out) else None
        trx_files = _trx_matches(work, spec) if spec else []
        parsed = parse_trx(trx_files[0]) if len(trx_files) == 1 else None
    finally:
        shutil.rmtree(work, onexc=archive.make_writable)
    log = out_dir / "oracle.log"
    version_log = f"$ dotnet --version\nexit {version_done.returncode}\n{version or version_done.stderr}\n" if version_done else ""
    log.write_text(f"{version_log}$ {' '.join(oracle['command'])}\nexit {done.returncode if done else 'not run'}\n"
                   f"--- stdout\n{done.stdout if done else ''}\n--- stderr\n{done.stderr if done else ''}",
                   encoding="utf-8")
    evidence = log.relative_to(run_dir).as_posix()
    if (version_done and version_done.timed_out) or (done and done.timed_out) or done is None:
        return Result(None, None, f"HB-GRD-002 grading step timeout after {timeout:g} s", evidence)
    if kind == "dotnet" and version_done and version_done.returncode != 0:
        return Result(None, None, "dotnet --version failed", evidence)
    if kind == "dotnet" and spec is None:
        return Result(None, None, "oracle command has no named TRX result", evidence)
    if kind == "dotnet" and not trx_files:
        return Result(None, None, "named TRX result file missing", evidence)
    if kind == "dotnet" and len(trx_files) != 1:
        return Result(None, None, "multiple named TRX result files", evidence)
    if kind == "unittest":
        parsed = parse_unittest(done.stderr)
    if parsed is None:
        return Result(None, None, "named TRX result is unparsable" if kind == "dotnet" else "oracle output has no unittest summary", evidence)
    total, passed = parsed
    if total == 0:
        return Result(None, None, "no hidden test ran", evidence)
    return Result(int(done.returncode == 0 and passed == total), Decimal(passed) / Decimal(total), None, evidence)


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """pass@1 and partial credit from the hidden tests (US-28); moved verbatim from the runner (seam C-2)."""
    c = grade(inp.archive / "ws", inp.task_dir, inp.task.get("oracle") or {}, inp.out_dir, inp.run_dir,
              inp.plan["parameters"]["grading_step_timeout"])
    return {"pass_at_1": Score(c.passed, c.reason, c.evidence), "partial_credit": Score(c.partial_credit, c.reason, c.evidence)}
