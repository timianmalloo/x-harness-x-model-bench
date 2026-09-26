"""Mutation score of agent-written tests: Stryker.NET for C#, mutmut for Python (design phase3-graders, Mutation).

- Metrics: mutation_score (scale 4, non-additive).
- Runs Stryker.NET in a disposable grading copy (_changes.grading_copy; never in the archive).
- Mutates non-test .cs files added or changed relative to pre-turn tree.
- Tests with test projects added or changed relative to pre-turn tree.
- NA reasons: "no tests written", "no non-test source changed", "no mutants generated",
  "mutation tool not available", "mutation run failed: <exit code>".
- Records initial_failing_tests from Stryker's "<n> tests are failing" line (R-75).
  An absent line is "not recorded", never 0. A non-zero exit stays "mutation run failed: <exit code>".
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path

from harness_bench.grade import CellInput, Score, _changes, correctness
from harness_bench.profiles import CELL_ENV

METRIC = "mutation_score"
SCALE = Decimal("0.0001")
NO_WORKING_COPY = "no working copy in the archive"
NO_TESTS_WRITTEN = "no tests written"
NO_SOURCE_CHANGED = "no non-test source changed"
NO_MUTANTS_GENERATED = "no mutants generated"
TOOL_NOT_AVAILABLE = "mutation tool not available"

HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")
DOTNET_HOST_ENV = (
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
    "ProgramData", "ProgramFiles", "NUGET_PACKAGES", "PROCESSOR_ARCHITECTURE",
)
TEST_PROJECT_MARKER = re.compile(
    r"<PackageReference\s+Include=\"Microsoft\.NET\.Test\.Sdk\"|<IsTestProject>\s*true\s*</IsTestProject>",
    re.IGNORECASE,
)
# Stryker 4.16.0: "{FailingTestsCount} tests are failing. Stryker will continue..."
_INITIAL_FAILING = re.compile(r"(\d+) tests are failing")

__all__ = [
    "DOTNET_HOST_ENV",
    "HOST_ENV",
    "METRIC",
    "NO_MUTANTS_GENERATED",
    "NO_SOURCE_CHANGED",
    "NO_TESTS_WRITTEN",
    "NO_WORKING_COPY",
    "SCALE",
    "TEST_PROJECT_MARKER",
    "TOOL_NOT_AVAILABLE",
    "find_stryker_dll",
    "grade_cell",
]


def find_stryker_dll() -> Path | None:
    """Find pinned Stryker.CLI.dll 4.16.0 in the NuGet global packages cache."""
    candidates: list[Path] = []
    if "NUGET_PACKAGES" in os.environ:
        candidates.append(Path(os.environ["NUGET_PACKAGES"]))
    if "USERPROFILE" in os.environ:
        candidates.append(Path(os.environ["USERPROFILE"]) / ".nuget" / "packages")
    try:
        candidates.append(Path.home() / ".nuget" / "packages")
    except RuntimeError:
        pass
    for base in candidates:
        dll = base / "dotnet-stryker" / "4.16.0" / "tools" / "net8.0" / "any" / "Stryker.CLI.dll"
        if dll.is_file():
            return dll
    return None


def _initial_failing_tests(stdout: str, stderr: str = "") -> str:
    """The count in Stryker's warning, or "not recorded" when that line was not printed."""
    match = _INITIAL_FAILING.search(stdout) or _INITIAL_FAILING.search(stderr)
    if match is None:
        return "not recorded"
    return match.group(1)


def _is_test_project(csproj: Path) -> bool:
    try:
        content = csproj.read_text(encoding="utf-8")
        return bool(TEST_PROJECT_MARKER.search(content))
    except (OSError, UnicodeDecodeError):
        return False


def _enclosing_csproj(rel_path: str, work_tree: Path) -> Path | None:
    current = (work_tree / rel_path).parent
    while True:
        csprojs = list(current.glob("*.csproj"))
        if csprojs:
            return csprojs[0]
        if current.resolve() == work_tree.resolve() or current == current.parent:
            break
        current = current.parent
    return None


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """Grade mutation_score: run Stryker.NET on added/changed non-test .cs files using added/changed test projects."""
    ws = inp.archive / "ws"
    if not ws.is_dir():
        scores = {METRIC: Score(None, NO_WORKING_COPY)}
        return {m: scores[m] for m in inp.metrics if m in scores} if inp.metrics else scores

    timeout = inp.plan["parameters"]["grading_step_timeout"]
    commit = _changes.pre_turn_commit(ws, inp.cell, timeout)
    if commit is None:
        scores = {METRIC: Score(None, _changes.NOT_FOUND)}
        return {m: scores[m] for m in inp.metrics if m in scores} if inp.metrics else scores

    out = inp.out_dir
    out.mkdir(parents=True, exist_ok=True)
    log_file = out / "mutation.log"
    evidence = log_file.relative_to(inp.run_dir).as_posix()
    log: list[str] = []

    def written(score: Score) -> dict[str, Score]:
        log_file.write_text("".join(log), encoding="utf-8")
        res = {METRIC: Score(score.value, score.reason, evidence)}
        return {m: res[m] for m in inp.metrics if m in res} if inp.metrics else res

    started = time.monotonic()
    with ExitStack() as stack:
        pre_tree = stack.enter_context(_changes.pre_turn_tree(ws, commit, out / "pre-turn", timeout))
        work_tree = stack.enter_context(_changes.grading_copy(ws, out / "work"))
        changes = _changes.change_set(pre_tree, work_tree)

        added_or_changed = [p for p, status in changes.items() if status in ("added", "changed")]

        changed_test_projects: set[str] = set()
        changed_non_test_sources: list[str] = []
        source_projects: set[Path] = set()

        for p in added_or_changed:
            proj = _enclosing_csproj(p, work_tree)
            if proj is not None and _is_test_project(proj):
                changed_test_projects.add(proj.relative_to(work_tree).as_posix())
            elif p.endswith(".cs"):
                changed_non_test_sources.append(p)
                if proj is not None:
                    source_projects.add(proj)

        if not changed_test_projects:
            return written(Score(None, NO_TESTS_WRITTEN))

        if not changed_non_test_sources:
            return written(Score(None, NO_SOURCE_CHANGED))

        stryker_dll = find_stryker_dll()
        if stryker_dll is None or shutil.which("dotnet") is None:
            return written(Score(None, TOOL_NOT_AVAILABLE))

        target_project = min(source_projects).name if source_projects else "AiDe.Core.csproj"
        test_projects = sorted(changed_test_projects)
        mutate_patterns = sorted({f"**/{Path(p).name}" for p in changed_non_test_sources})

        config_data = {
            "stryker-config": {
                "additional-timeout": 5000,
                "concurrency": 4,
                "project": target_project,
                "test-projects": test_projects,
                "mutate": mutate_patterns,
                "reporters": ["Json", "ClearText"],
                "verbosity": "info",
                "thresholds": {"high": 80, "low": 60, "break": 0},
            }
        }
        (work_tree / "stryker-config.json").write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        cmd = [
            "dotnet",
            "exec",
            str(stryker_dll),
            "--skip-version-check",
            "--config-file",
            "stryker-config.json",
        ]
        env = {k: os.environ[k] for k in HOST_ENV if k in os.environ}
        env.update(CELL_ENV)
        env.update({k: os.environ[k] for k in DOTNET_HOST_ENV if k in os.environ})
        env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
        env["MSBUILDDISABLENODEREUSE"] = "1"
        env["UseSharedCompilation"] = "false"
        if "NUGET_PACKAGES" not in env:
            user_prof = os.environ.get("USERPROFILE")
            if user_prof:
                env["NUGET_PACKAGES"] = str(Path(user_prof) / ".nuget" / "packages")

        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            return written(Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s"))

        done = correctness.run_step(cmd, work_tree, env, remaining)  # the procs allowlist (R-60)
        log.append(
            f"$ {' '.join(cmd)}\nexit {done.returncode if done else 'not run'}\n"
            f"--- stdout\n{done.stdout if done else ''}\n--- stderr\n{done.stderr if done else ''}\n"
        )
        log.append(
            "initial_failing_tests: "
            f"{_initial_failing_tests(done.stdout if done else '', done.stderr if done else '')}\n"
        )
        if done.timed_out:
            return written(Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s"))
        if done.returncode != 0:
            return written(Score(None, f"mutation run failed: {done.returncode}"))

        reports = sorted(work_tree.rglob("mutation-report.json"))
        if not reports:
            return written(Score(None, NO_MUTANTS_GENERATED))
        # The grading copy is removed on exit. Keep the report where the score's evidence lives.
        shutil.copyfile(reports[0], out / "mutation-report.json")

        try:
            data = json.loads(reports[0].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return written(Score(None, NO_MUTANTS_GENERATED))

        counts: Counter[str] = Counter()
        for file_entry in data.get("files", {}).values():
            for mutant in file_entry.get("mutants", []):
                st = mutant.get("status")
                if st:
                    counts[st.lower()] += 1

        killed = counts.get("killed", 0)
        timeout_count = counts.get("timeout", 0)
        survived = counts.get("survived", 0)
        no_coverage = counts.get("nocoverage", 0)
        denom = killed + timeout_count + survived + no_coverage
        if denom == 0:
            return written(Score(None, NO_MUTANTS_GENERATED))

        score_val = (Decimal(killed + timeout_count) / Decimal(denom)).quantize(SCALE)
        log.append(
            f"killed: {killed}, timeout: {timeout_count}, survived: {survived}, no coverage: {no_coverage}\n"
            f"mutation_score: {score_val}\n"
        )
        return written(Score(score_val, None))
