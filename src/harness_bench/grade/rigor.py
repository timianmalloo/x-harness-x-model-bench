"""Rigor grader: static_analysis_delta and NA-by-design metrics (design phase3-graders, section Rigor, GR-CODE c5).

- static_analysis_delta: distinct (file, line, code) warnings from `dotnet build` of the cell's tree, minus the
  same on the pre-turn tree (an int, may be negative). Reuses _changes and correctness's build helpers (one definition,
  no second build path). NA "workspace does not build" or "pre-turn tree does not build".
- verification_before_done, test_quality, maintainability and style_conformance: NA by design with the design's
  reasons verbatim (R-67 DR-G2, R-68).
- The evidence is `rigor.log` under the grader's out_dir.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

from harness_bench import procs
from harness_bench.grade import CellInput, Score, _changes, correctness

METRIC = "static_analysis_delta"
NO_WORKING_COPY = "no working copy in the archive"
WARNING_LINE = re.compile(r"^(.+?)\s*:\s*warning\s+([A-Za-z0-9_]+)\s*:", re.MULTILINE)
LINE_COL = re.compile(r"\((\d+)(?:,\d+)?\)$")
BUILD_FLAGS = (*correctness.OFFLINE, "-p:TreatWarningsAsErrors=false")

NA_BY_DESIGN = {
    "verification_before_done": "test runs not identifiable in the tool record (no command text extracted)",
    "test_quality": "mechanical rung is mutation_score (not counted twice); no rubric for this task",
    "maintainability": "no maintainability tool pinned in this catalog version",
    "style_conformance": (
        "no task-defined style rules (a root .editorconfig exists only in pack-on trees: a treatment); no rubric for"
        " this task"
    ),
}

__all__ = ["BUILD_FLAGS", "METRIC", "NA_BY_DESIGN", "NO_WORKING_COPY", "grade_cell", "parse_warnings"]


def parse_warnings(output: str, tree: Path) -> set[tuple[str, int, str]]:
    """Distinct (file, line, code) warnings parsed from MSBuild output, with file relative to tree."""
    warnings: set[tuple[str, int, str]] = set()
    for m in WARNING_LINE.finditer(output):
        loc = m.group(1).strip()
        code = m.group(2)
        lm = LINE_COL.search(loc)
        line_no = int(lm.group(1)) if lm else 0
        file_part = loc[: lm.start()].strip() if lm else loc
        try:
            rel = Path(file_part).resolve().relative_to(tree.resolve()).as_posix()
        except (ValueError, OSError):
            rel = Path(file_part).as_posix()
        warnings.add((rel, line_no, code))
    return warnings


def _build_tree(
    tree: Path,
    env: dict[str, str],
    timeout: float,
    started: float,
    log: list[str],
) -> tuple[set[tuple[str, int, str]], str | None]:
    """Build all projects in `tree` with dotnet, collecting distinct warnings or returning a failure reason."""
    projects = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*.csproj") if p.is_file())
    if not projects:
        return set(), correctness.NOT_BUILDING
    steps = [["dotnet", "--version"], *(["dotnet", "build", p, *BUILD_FLAGS] for p in projects)]
    warnings: set[tuple[str, int, str]] = set()
    last = None
    for argv in steps:
        remaining = timeout - (time.monotonic() - started)
        last = procs.run(argv, cwd=tree, env=env, timeout=remaining) if remaining > 0 else None
        log.append(
            f"{tree.name}: $ {' '.join(argv)}\nexit {last.returncode if last else 'not run'}\n"
            f"--- stdout\n{last.stdout if last else ''}\n--- stderr\n{last.stderr if last else ''}\n"
        )
        if last is None or last.timed_out:
            return set(), f"HB-GRD-002 grading step timeout after {timeout:g} s"
        if last.returncode != 0:
            if argv == ["dotnet", "--version"]:
                return set(), correctness.SDK
            if correctness.build_failure(last.stdout) == "restore":
                return set(), correctness.RESTORE
            return set(), correctness.NOT_BUILDING
        warnings |= parse_warnings(last.stdout, tree)
    return warnings, None


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """Grade rigor metrics: static_analysis_delta from dotnet build warnings delta, plus 4 NA-by-design metrics."""
    ws = inp.archive / "ws"
    if not ws.is_dir():
        scores = {METRIC: Score(None, NO_WORKING_COPY), **{m: Score(None, NA_BY_DESIGN[m]) for m in NA_BY_DESIGN}}
        return {m: scores[m] for m in inp.metrics if m in scores} if inp.metrics else scores

    timeout = inp.plan["parameters"]["grading_step_timeout"]
    started = time.monotonic()
    with ExitStack() as stack:
        pre = correctness.PreTurn(inp, timeout, stack)
        if pre.commit is None:
            scores = {METRIC: Score(None, _changes.NOT_FOUND), **{m: Score(None, NA_BY_DESIGN[m]) for m in NA_BY_DESIGN}}
            return {m: scores[m] for m in inp.metrics if m in scores} if inp.metrics else scores

        out = inp.out_dir
        out.mkdir(parents=True, exist_ok=True)
        log_file = out / "rigor.log"
        evidence = log_file.relative_to(inp.run_dir).as_posix()
        env = correctness._env() | {k: os.environ[k] for k in correctness.DOTNET_HOST_ENV if k in os.environ}
        log: list[str] = []

        def written(score: Score) -> dict[str, Score]:
            log_file.write_text("".join(log), encoding="utf-8")
            res = {METRIC: score, **{m: Score(None, NA_BY_DESIGN[m]) for m in NA_BY_DESIGN}}
            return {m: res[m] for m in inp.metrics if m in res} if inp.metrics else res

        with _changes.grading_copy(ws, out / "cell") as cell_tree:
            cell_warnings, cell_fail = _build_tree(cell_tree, env, timeout, started, log)

        if cell_fail:
            return written(Score(None, cell_fail, evidence))

        pre_warnings, pre_fail = _build_tree(pre.tree, env, timeout, started, log)
        if pre_fail:
            reason = (
                pre_fail
                if pre_fail in (correctness.RESTORE, correctness.SDK) or pre_fail.startswith("HB-GRD-002")
                else correctness.PRE_TURN_BROKEN
            )
            return written(Score(None, reason, evidence))

        delta = len(cell_warnings) - len(pre_warnings)
        log.append(
            f"cell distinct warnings: {len(cell_warnings)}\n"
            f"pre-turn distinct warnings: {len(pre_warnings)}\n"
            f"static_analysis_delta: {delta}\n"
        )
        return written(Score(delta, None, evidence))
