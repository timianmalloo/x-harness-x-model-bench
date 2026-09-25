"""Correctness from hidden tests (US-28): pass@1, partial credit and build_and_suite_clean for one archived cell.

- The hidden tests run in a grading copy (the archived working copy, then the task's `tests/`), never in
  the archive, in their own Job Object under the grading-step deadline (HB-GRD-002). The copy is removed
  afterwards; the oracle's output is kept as the evidence.
- `unittest` summaries and the named TRX file from a `dotnet` oracle are parsed strictly; a missing or
  invalid summary is NA, never 0. A pass needs exit status 0 and every test passed.
- DR-G4, decided by cause (R-67 c1; measured in docs/notes/spike-gr-code-trx.md): a dotnet step that wrote no TRX
  is classified from MSBuild's canonical error lines. A restore error (`NUxxxx`) is NA
  `infrastructure failure before build: restore`; a failing `dotnet --version` is NA `... sdk`. A compiler error
  (`CSxxxx`) scores 0 only when the same oracle on the pre-turn tree (`_changes`) compiles and runs its tests under the
  same toolchain; otherwise NA `pre-turn tree does not build` (or the control's own infrastructure reason).
- build_and_suite_clean: 1 iff the working copy builds on its own, in a grading copy without build output: every
  `*.csproj` builds offline (`dotnet build`, sorted, the first failure decides), or `python -m compileall -q` exits 0.
- regression_count (GR-CODE c2): the task's public tests, keyed `className.name` from the per-test TRX, that pass on the
  pre-turn tree and fail, are skipped or are missing on the cell's tree. The cell's tree runs first; the pre-turn
  commit and tree are found once per cell and shared with DR-G4's control. The TRX's host fields and the
  `Results File:` line are never read or stored (docs/notes/spike-gr-code-trx.md).
- behavioural_equivalence is NA on every task version (R-68 1); `not a D-task` off scenario 4 is the recorded deviation N4.
- pass@k and pass^k are derived (row 19).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from pathlib import Path

from harness_bench import archive, procs
from harness_bench.grade import CellInput, Score, _changes
from harness_bench.profiles import CELL_ENV

RAN = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
RESULT = re.compile(r"^(?:OK|FAILED)(?: \(([^)]*)\))?\s*$", re.MULTILINE)
NOT_PASSED = ("failures", "errors", "skipped", "expected failures", "unexpected successes")
HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")
DOTNET_HOST_ENV = ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "ProgramData", "ProgramFiles",
                   "NUGET_PACKAGES")
# MSBuild's canonical error line, `<origin>: error <code>: <text>` (spike: `…Broken.cs(5,31): error CS1002: ; expected`,
# `…AiDe.Core.csproj : error NU1101: Unable to find package …`). simplify: C# and NuGet codes only; ceiling D1, the one
# dotnet task; upgrade trigger: an F# or VB task.
BUILD_ERROR = re.compile(r": error (NU|CS)\d{4}: ")
RESTORE = "infrastructure failure before build: restore"
SDK = "infrastructure failure before build: sdk"
PRE_TURN_BROKEN = "pre-turn tree does not build"
OFFLINE = ("-p:RestoreSources=.", "-p:NuGetAudit=false", "-v:q", "-nologo")  # the host cache only, as the D1 oracle
NO_PUBLIC_TESTS = "task has no public tests"
NOT_BUILDING = "workspace does not build"
NOT_D_TASK = "not a D-task"
NO_DIFFERENTIAL = "no differential oracle in this task version"
TEST_SDK = re.compile(r"<PackageReference\s+Include=\"Microsoft\.NET\.Test\.Sdk\"", re.IGNORECASE)  # VSTest's marker
TRX = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"


@dataclass(frozen=True)
class Result:
    passed: int | None  # pass@1 for this cell: 1 or 0
    partial_credit: Decimal | None  # fraction of hidden tests passing
    reason: str | None
    evidence: str  # relative to the run directory
    compile_error: bool = False  # no TRX, and the step's output carries a compiler error and no restore error


def build_failure(output: str) -> str | None:
    """'restore', 'compile' or None, from the error codes in a dotnet step's output; a restore error comes first."""
    codes = set(BUILD_ERROR.findall(output))
    return "restore" if "NU" in codes else "compile" if "CS" in codes else None


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
        return Result(None, None, SDK, evidence)
    if kind == "dotnet" and spec is None:
        return Result(None, None, "oracle command has no named TRX result", evidence)
    cause = build_failure(done.stdout) if kind == "dotnet" and not trx_files else None
    if cause == "restore":
        return Result(None, None, RESTORE, evidence)
    if kind == "dotnet" and not trx_files:
        return Result(None, None, "named TRX result file missing", evidence, compile_error=cause == "compile")
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


class PreTurn:
    """The cell's pre-turn commit and materialised tree, each found at most once per cell and shared by DR-G4's control
    and regression_count (the c1 residual). The tree is removed when the cell's grading ends (`stack`)."""

    def __init__(self, inp: CellInput, timeout: float, stack: ExitStack) -> None:
        self._inp, self._timeout, self._stack = inp, timeout, stack

    @cached_property
    def commit(self) -> str | None:
        return _changes.pre_turn_commit(self._inp.archive / "ws", self._inp.cell, self._timeout)

    @cached_property
    def tree(self) -> Path:
        ws, dest = self._inp.archive / "ws", self._inp.out_dir / "pre-turn"
        return self._stack.enter_context(_changes.pre_turn_tree(ws, self.commit, dest, self._timeout))


def _by_cause(inp: CellInput, oracle: dict, cell: Result, timeout: float, pre: PreTurn) -> Result:
    """The cell's tree did not compile: 0 only when the pre-turn tree does under the same toolchain (DR-G4, R-67 c1).

    simplify: the control's own oracle run is one per compile-failing cell (the commit and tree are shared); ceiling:
    compile failures are rare (none in the gate runs, G16); upgrade trigger: a pass where they are not.
    """
    if pre.commit is None:
        return Result(None, None, _changes.NOT_FOUND, cell.evidence)
    control = inp.out_dir / "pre-turn-oracle"
    control.mkdir()
    base = grade(pre.tree, inp.task_dir, oracle, control, inp.run_dir, timeout)  # a copy; the shared tree is untouched
    if base.reason is None:  # the hidden tests compiled and ran on the pre-turn tree: the cell broke the build
        return Result(0, Decimal(0), None, cell.evidence)
    if base.reason in (RESTORE, SDK) or base.reason.startswith("HB-GRD-002"):  # the control could not tell
        return Result(None, None, base.reason, cell.evidence)
    return Result(None, None, PRE_TURN_BROKEN, cell.evidence)


def build_and_suite_clean(inp: CellInput, oracle: dict, timeout: float) -> Score:
    """1 iff the working copy builds on its own (analysis rung); NA only for a failure before the build."""
    kind, ws = oracle.get("runner"), inp.archive / "ws"
    if kind not in ("unittest", "dotnet") or not oracle.get("command"):
        return Score(None, f"oracle runner {kind!r} not built (phase 1 runs unittest)")
    if not ws.is_dir():
        return Score(None, "no working copy in the archive")
    out = inp.out_dir / "build"
    out.mkdir()
    env = _env()
    if kind == "dotnet":
        env.update({k: os.environ[k] for k in DOTNET_HOST_ENV if k in os.environ})  # ADR-0013, as the oracle step
    steps, lines, last = [], [], None
    started = time.monotonic()
    with _changes.grading_copy(ws, out / "work") as work:
        if kind == "unittest":
            steps = [[sys.executable, "-m", "compileall", "-q", "."]]
        else:
            projects = sorted(p.relative_to(work).as_posix() for p in work.rglob("*.csproj") if p.is_file())
            steps = [["dotnet", "--version"], *(["dotnet", "build", p, *OFFLINE] for p in projects)]
        for argv in steps:
            remaining = timeout - (time.monotonic() - started)
            last = procs.run(argv, cwd=work, env=env, timeout=remaining) if remaining > 0 else None
            lines.append(f"$ {' '.join(argv)}\nexit {last.returncode if last else 'not run'}\n"
                         f"--- stdout\n{last.stdout if last else ''}\n--- stderr\n{last.stderr if last else ''}\n")
            if last is None or last.timed_out or last.returncode != 0:
                break
    log = out / "build.log"
    log.write_text("".join(lines), encoding="utf-8")
    evidence = log.relative_to(inp.run_dir).as_posix()
    if last is None or last.timed_out:
        return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s", evidence)
    if last.returncode != 0 and steps[len(lines) - 1] == ["dotnet", "--version"]:
        return Score(None, SDK, evidence)
    if last.returncode != 0 and kind == "dotnet" and build_failure(last.stdout) == "restore":
        return Score(None, RESTORE, evidence)
    # assume: a dotnet working copy with no project builds nothing, so it is not a clean build (0, never a vacuous 1).
    # Confirm: D1's workspace always holds six projects; if false, only a cell that deleted them all reads 0.
    return Score(int(last.returncode == 0 and len(steps) > 1 if kind == "dotnet" else last.returncode == 0), None, evidence)


def public_tests(task_dir: Path, kind: str) -> list[str]:
    """The task's public tests, relative to its workspace and sorted: for dotnet every `*.csproj` that references
    Microsoft.NET.Test.Sdk (D1: tests/AiDe.Core.Tests; its AcpProbe and TerminalHost are not test projects), for
    unittest every `test*.py`. Read from the task, never the cell, so a cell cannot unlist a suite it broke."""
    ws = task_dir / "workspace"
    if kind == "dotnet":
        return sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*.csproj") if TEST_SDK.search(p.read_text(encoding="utf-8")))
    return sorted(p.relative_to(ws).as_posix() for p in ws.rglob("test*.py"))


def public_outcomes(path: Path) -> dict[str, bool] | None:
    """{className.name: every case passed} from a TRX, joined through UnitTest@id = UnitTestResult@testId (the spike).
    Only those names, ids and `outcome` are read: never runUser, computerName, storage, codeBase or a time."""
    try:
        root = ET.parse(path).getroot()
        if root.tag != TRX + "TestRun":
            return None
        names = {}
        for unit in root.iter(TRX + "UnitTest"):
            method = unit.find(TRX + "TestMethod")
            names[unit.attrib["id"]] = f"{method.attrib['className']}.{method.attrib['name']}"
        out: dict[str, bool] = {}
        for result in root.iter(TRX + "UnitTestResult"):
            key = names[result.attrib["testId"]]
            out[key] = out.get(key, True) and result.attrib["outcome"] == "Passed"  # a theory passes only if every case does
    except (ET.ParseError, OSError, KeyError, AttributeError):
        return None
    return out


def _public_suite(tree: Path, projects: list[str], env: dict, timeout: float, log: list[str]) -> tuple[dict[str, bool], str | None]:
    """Every public project's outcomes on `tree` (in place), or the NA reason that stopped the run. A project the tree
    does not have contributes no test, so its tests are missing. The log keeps the command and exit only."""
    outcomes: dict[str, bool] = {}
    started = time.monotonic()
    for n, project in enumerate(projects):
        if not (tree / project).is_file():
            log.append(f"{tree.name}: {project} missing\n")
            continue
        trx = tree / "TestResults" / f"public-{n}.trx"
        argv = ["dotnet", "test", project, *OFFLINE[:2], "--logger", f"trx;LogFileName={trx.name}",
                "--results-directory", "TestResults", "-v:q"]
        remaining = timeout - (time.monotonic() - started)
        done = procs.run(argv, cwd=tree, env=env, timeout=remaining) if remaining > 0 else None
        log.append(f"{tree.name}: $ {' '.join(argv)}\nexit {done.returncode if done else 'not run'}\n")
        if done is None or done.timed_out:
            return outcomes, f"HB-GRD-002 grading step timeout after {timeout:g} s"
        if not trx.is_file():
            cause = build_failure(done.stdout)
            return outcomes, RESTORE if cause == "restore" else NOT_BUILDING if cause == "compile" else "named TRX result file missing"
        parsed = public_outcomes(trx)
        if parsed is None:
            return outcomes, "named TRX result is unparsable"
        for key, passed in parsed.items():
            outcomes[key] = outcomes.get(key, True) and passed
    return outcomes, None


def regression_count(inp: CellInput, oracle: dict, timeout: float, pre: PreTurn) -> Score:
    """Public tests that pass on the pre-turn tree and do not pass on the cell's (tests rung). The cell's tree runs
    first: when it does not build, the pre-turn run is not needed."""
    kind, ws = oracle.get("runner"), inp.archive / "ws"
    if kind not in ("unittest", "dotnet") or not oracle.get("command"):
        return Score(None, f"oracle runner {kind!r} not built (phase 1 runs unittest)")
    projects = public_tests(inp.task_dir, kind)
    if not projects:
        return Score(None, NO_PUBLIC_TESTS)
    if kind == "unittest":  # simplify: no python task ships public tests; upgrade trigger: the first that does
        return Score(None, "public tests of runner 'unittest' not built")
    if not ws.is_dir():
        return Score(None, "no working copy in the archive")
    if pre.commit is None:
        return Score(None, _changes.NOT_FOUND)
    out = inp.out_dir / "regressions"
    out.mkdir()
    log, evidence = [], (out / "regressions.log").relative_to(inp.run_dir).as_posix()
    env = _env() | {k: os.environ[k] for k in DOTNET_HOST_ENV if k in os.environ}  # ADR-0013, as the oracle step

    def written(value: int | None, reason: str | None) -> Score:
        (out / "regressions.log").write_text("".join(log), encoding="utf-8")
        return Score(value, reason, evidence)

    with _changes.grading_copy(ws, out / "cell") as tree:
        after, failure = _public_suite(tree, projects, env, timeout, log)
    if failure:
        return written(None, failure)
    before, failure = _public_suite(pre.tree, projects, env, timeout, log)
    if failure:
        return written(None, failure if failure == RESTORE or failure.startswith("HB-GRD-002") else PRE_TURN_BROKEN)
    regressed = sorted(k for k, passed in before.items() if passed and not after.get(k, False))
    log += [f"regressions {len(regressed)} of {sum(before.values())} passing before\n", *(f"regressed {k}\n" for k in regressed)]
    return written(len(regressed), None)


def behavioural_equivalence(task: Mapping) -> Score:
    """NA on every task version (R-68 1: kept, re-sourced by the first D-task version with a differential oracle).
    A D-task is scenario 4; elsewhere the row is the recorded deviation N4, `not a D-task`.

    simplify: no task version has a differential oracle; ceiling: every wave-3 task; upgrade trigger: the first that does.
    """
    return Score(None, NO_DIFFERENTIAL if task.get("scenario") == 4 else NOT_D_TASK)


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """pass@1 and partial credit from the hidden tests (US-28; seam C-2), decided by cause, build_and_suite_clean,
    regression_count and the behavioural_equivalence NA."""
    oracle, timeout = inp.task.get("oracle") or {}, inp.plan["parameters"]["grading_step_timeout"]
    with ExitStack() as stack:
        pre = PreTurn(inp, timeout, stack)
        c = grade(inp.archive / "ws", inp.task_dir, oracle, inp.out_dir, inp.run_dir, timeout)
        if c.compile_error:
            c = _by_cause(inp, oracle, c, timeout, pre)
        return {"pass_at_1": Score(c.passed, c.reason, c.evidence), "partial_credit": Score(c.partial_credit, c.reason, c.evidence),
                "build_and_suite_clean": build_and_suite_clean(inp, oracle, timeout),
                "regression_count": regression_count(inp, oracle, timeout, pre),
                "behavioural_equivalence": behavioural_equivalence(inp.task)}
