"""Drift: scope_creep, scope_creep_files and convention_drift from the cell's change set (design phase3-graders, Drift).

- The change set is `_changes`' (GR-CODE c1): the cell's working tree against the pre-turn tree under the tamper rule,
  by content with CRLF normalised, build output excluded. A pack-on cell's base is the pack commit, so the pack is not
  a change; a commit the agent made after it is (the Codex cell 3ff0 of row15-d1-1). An added file that the pre-turn
  tree's own ignore rules name is not a change either (the pack hook's marker; see `_ignored`).
- Lines are counted with `difflib` over the CRLF-normalised bytes, split at LF only (a line keeps its end, so a lost
  final newline is a changed line, as in `git diff`). A symlink's one line is its target's text (as `_changes`).
- scope_creep is lines added plus deleted in files outside the task's `blast_radius`; scope_creep_files is those files.
- convention_drift is violations of the task's hardcoded rule set in added or changed lines of the rules' file types,
  per 100 such lines (a Decimal; the design's scale is 2). NA `no lines changed` when there are none.
- spec_coverage, constraint_violations and instruction_reread_rate are NA by design, with the design's reasons
  (R-67 DR-G2, R-68: nothing changes in 0.4).
- Every measured score's evidence is `drift.log` under the grader's out_dir: one line per changed file.
"""

from __future__ import annotations

import codecs
import difflib
import io
import os
import re
import shutil
from decimal import Decimal
from fnmatch import fnmatchcase
from pathlib import Path

from harness_bench import archive, gitsafe
from harness_bench.grade import CellInput, Score, _changes

NO_WORKING_COPY = "no working copy in the archive"
NO_LINES = "no lines changed"
NO_RULES = "no convention rules for this task"
NA_BY_DESIGN = {  # design phase3-graders, Drift: the reasons verbatim
    "spec_coverage": "hidden-test coverage is partial_credit (not counted twice); no rubric for this task",
    "constraint_violations": "no constraint checklist in this task version",
    "instruction_reread_rate": "read targets not in the tool record (no arguments extracted)",
}
SCOPE = ("scope_creep", "scope_creep_files")

# The rule table, keyed by task id: (rule, file suffix, a line pattern that breaks the rule), measured on D1 (G14).
# R1 holds in 228/228 files: a namespace is file-scoped (`namespace X;`), so a declaration with no `;` breaks it.
# R2 (namespace equals the path) holds in 214/228 = 93.9 %, below 95 %, and is dropped.
# simplify: rules in code, keyed by task id; ceiling D1; upgrade trigger: a second task with convention rules.
BLOCK_NAMESPACE = re.compile(rb"\s*namespace\s+[\w.]+\s*(?:\{.*)?\s*")
RULES: dict[str, tuple[tuple[str, str, re.Pattern[bytes]], ...]] = {"D1": (("R1 file-scoped namespace", ".cs", BLOCK_NAMESPACE),)}

__all__ = ["NA_BY_DESIGN", "NO_LINES", "NO_RULES", "RULES", "grade_cell"]


def _lines(path: Path) -> list[bytes]:
    """The file's lines, CRLF read as LF, split at LF only; a symlink is its target's text, never followed.

    simplify: a changed file is read whole and diffed by difflib; ceiling: D1's source files (tens of KB); upgrade
    trigger: a change set holding a file over 1 MiB, when lines move to a bounded line hash first.
    """
    if path.is_symlink():
        return [os.readlink(path).encode()]
    return io.BytesIO(path.read_bytes().replace(b"\r\n", b"\n")).readlines()


def _diff(old: list[bytes], new: list[bytes]) -> tuple[list[tuple[int, bytes]], int]:
    """([(1-based line number, line)] added or changed on the new side, the number of deleted old lines)."""
    added, deleted = [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag != "equal":
            added += [(j + 1, new[j]) for j in range(j1, j2)]
            deleted += i2 - i1
    return added, deleted


def _in_radius(path: str, radius: list[str]) -> bool:
    # simplify: fnmatch, where `*` also crosses `/`, so `dir/**` is every file under dir; ceiling: the task globs are
    # `**`, `<dir>/**` or one file; upgrade trigger: a glob with a `*` inside a path segment.
    return any(fnmatchcase(path, glob) for glob in radius)


def _ignored(base: Path, added: list[str], scratch: Path, timeout: float) -> set[str]:
    """The added paths the pre-turn tree's own ignore rules name: `git check-ignore --no-index` over `base`.

    Git ignores no tracked file and every pre-turn path is tracked, so only an added path is asked. The rules are the
    pre-turn tree's (and no host config, via gitsafe), never the cell's: an agent cannot hide a change by ignoring it.
    assume: an untracked file under a pre-turn ignore rule is not an authored change; the measured case is the pack
    hook's `docs/audit/.run-starts.json` in the gate's pack-on Claude and Copilot cells, and the design's 0 was read
    with `git ls-files --others`. If false, a file force-added past a pre-turn rule goes uncounted.
    """
    if not added:
        return set()
    repo, out = scratch / "ignore-rules.git", set()
    try:
        gitsafe.git(["init", "-q", "--bare", str(repo)], cwd=scratch, timeout=timeout)
        for i in range(0, len(added), 100):  # a bounded command line (gitsafe has no stdin, so no `--stdin -z`)
            args = ["-c", "core.quotePath=false", "--git-dir", str(repo), "--work-tree", str(base),
                    "check-ignore", "--no-index", "--", *added[i:i + 100]]
            done = gitsafe.git(args, cwd=base, timeout=timeout, check=False)
            if done.timed_out or done.returncode not in (0, 1):  # 1: none of them is ignored
                raise gitsafe.GitError(args, done)
            # A path git still quotes (a `"`, `\` or control character) matches no added path, so it is counted: the
            # failure is toward counting a change, never toward hiding one.
            out.update(done.stdout.splitlines())
    finally:
        if repo.exists():
            shutil.rmtree(repo, onexc=archive.make_writable)
    return out


def _measure(inp: CellInput, rules: tuple | None) -> dict[str, Score]:
    ws, timeout = inp.archive / "ws", inp.plan["parameters"]["grading_step_timeout"]
    if not ws.is_dir():
        return dict.fromkeys((*SCOPE, "convention_drift"), Score(None, NO_WORKING_COPY))
    commit = _changes.pre_turn_commit(ws, inp.cell, timeout)
    if commit is None:
        return dict.fromkeys((*SCOPE, "convention_drift"), Score(None, _changes.NOT_FOUND))
    radius = inp.task.get("blast_radius") or []
    creep_lines = creep_files = changed = violations = 0
    log = []
    try:
        with (_changes.pre_turn_tree(ws, commit, inp.out_dir / "pre-turn", timeout) as base,
              _changes.grading_copy(ws, inp.out_dir / "work") as work):
            changes = _changes.change_set(base, work)
            ignored = _ignored(base, [p for p, s in changes.items() if s == "added"], inp.out_dir, timeout)
            for path, status in changes.items():
                if path in ignored:
                    log.append(f"ignored\t{path}\n")
                    continue
                old = _lines(base / path) if status != "added" else []
                added, deleted = _diff(old, _lines(work / path) if status != "deleted" else [])
                inside = _in_radius(path, radius)
                if not inside:
                    creep_lines += len(added) + deleted
                    creep_files += 1
                file_rules = [(name, pattern) for name, suffix, pattern in rules or () if Path(path).suffix == suffix]
                if file_rules:  # the denominator: added or changed lines of a file type the rules cover
                    changed += len(added)
                broken = [f"{name}:{n}" for n, line in added for name, pattern in file_rules
                          if pattern.fullmatch(line.removeprefix(codecs.BOM_UTF8))]
                violations += len(broken)
                log.append(f"{status}\t{path}\t{'inside' if inside else 'outside'}\t+{len(added)} -{deleted}\t{' '.join(broken)}\n")
    except gitsafe.GitError as exc:  # `git archive` of the pre-turn commit
        if not exc.result.timed_out:
            raise
        return dict.fromkeys((*SCOPE, "convention_drift"), Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s"))
    evidence = inp.out_dir / "drift.log"
    evidence.write_text("".join(log), encoding="utf-8")
    ev = evidence.relative_to(inp.run_dir).as_posix()
    out = {"scope_creep": Score(creep_lines, None, ev), "scope_creep_files": Score(creep_files, None, ev)}
    out["convention_drift"] = Score(Decimal(100 * violations) / Decimal(changed), None, ev) if changed else Score(None, NO_LINES, ev)
    return out


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """The design's drift metrics, each only when `inp.metrics` names it (the runner's applicable set)."""
    rules = RULES.get(inp.cell["task"])
    out = {m: Score(None, reason) for m, reason in NA_BY_DESIGN.items()} | _measure(inp, rules)
    if rules is None:  # a property of the task, so it reads before any property of the archive
        out["convention_drift"] = Score(None, NO_RULES)
    return {m: s for m, s in out.items() if m in inp.metrics}
