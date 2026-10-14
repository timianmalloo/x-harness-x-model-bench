"""Drift: scope_creep, scope_creep_files and convention_drift from the cell's change set (design phase3-graders, Drift).

- The change set is `_changes`' (GR-CODE c1): the cell's working tree against the pre-turn tree under the tamper rule,
  by content with CRLF normalised, build output excluded. A pack-on cell's base is the pack commit, so the pack is not
  a change; a commit the agent made after it is (the Codex cell 3ff0 of row15-d1-1). An added file that the pre-turn
  tree's own ignore rules name is not a change either (the pack hook's marker; see `_ignored`).
- Lines are counted with `difflib` over the CRLF-normalised bytes, split at LF only (a line keeps its end, so a lost
  final newline is a changed line, as in `git diff`). A symlink's one line is its target's text (as `_changes`).
- Catalog 0.8 (ADR-0026 s5) splits the lines added plus deleted in files outside the task's `blast_radius` three ways,
  by grader rule: drift_machine_lines (a path `_changes.machine_written` names: a tool cache, or a file the pack's
  audit script or hooks write), drift_task_implied_lines (a test path, `_changes.is_test_path`; stated limit: an
  unrequested new test file counts here) and scope_creep, redefined as the discretionary rest; scope_creep_files is
  the files scope_creep counts. An outside line of drift.log gains a last field naming its class (`machine:cache`,
  `machine:pack-log`, `task-implied`, `discretionary`), so the pack's own lines show on their own row; an inside
  line keeps its 0.7 shape.
- attention_drift is the share of read and search targets outside the task's neighbourhood (see `_neighbourhood`);
  calls with no extractable path are excluded and counted in attention.log.
- convention_drift is violations of the task's hardcoded rule set in added or changed lines of the rules' file types,
  per 100 such lines (a Decimal; the design's scale is 2). NA `no lines changed` when there are none.
- spec_coverage, constraint_violations and instruction_reread_rate are NA by design, with the design's reasons
  (R-67 DR-G2, R-68: nothing changes in 0.4).
- Every measured score's evidence is `drift.log` under the grader's out_dir: one line per changed file.
"""

from __future__ import annotations

import ast
import codecs
import difflib
import inspect
import io
import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import archive, gitsafe, profiles
from harness_bench.grade import CellInput, Score, _changes

NO_WORKING_COPY = "no working copy in the archive"
NO_LINES = "no lines changed"
NO_RULES = "no convention rules for this task"
NA_BY_DESIGN = {  # design phase3-graders, Drift: the reasons verbatim
    "spec_coverage": "hidden-test coverage is partial_credit (not counted twice); no rubric for this task",
    "constraint_violations": "no constraint checklist in this task version",
    "instruction_reread_rate": "read targets not in the tool record (no arguments extracted)",
}
SCOPE = ("scope_creep", "scope_creep_files", "drift_machine_lines", "drift_task_implied_lines")
NO_SESSION = "no native session for the cell"
NO_RECORD = "no native record for the session"
NO_TARGETS = "no read or search call with a path"

# The rule table, keyed by task id: (rule, file suffix, a line pattern that breaks the rule), measured on D1 (G14).
# R1 holds in 228/228 files: a namespace is file-scoped (`namespace X;`), so a declaration with no `;` breaks it.
# R2 (namespace equals the path) holds in 214/228 = 93.9 %, below 95 %, and is dropped.
# simplify: rules in code, keyed by task id; ceiling D1; upgrade trigger: a second task with convention rules.
BLOCK_NAMESPACE = re.compile(rb"\s*namespace\s+[\w.]+\s*(?:\{.*)?\s*")
RULES: dict[str, tuple[tuple[str, str, re.Pattern[bytes]], ...]] = {"D1": (("R1 file-scoped namespace", ".cs", BLOCK_NAMESPACE),)}

__all__ = ["NA_BY_DESIGN", "NO_LINES", "NO_RECORD", "NO_RULES", "NO_SESSION", "NO_TARGETS", "RULES", "grade_cell"]


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


_in_radius = _changes.in_radius


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
    scratch.mkdir(parents=True, exist_ok=True)
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


INSIDE, TASK_IMPLIED, DISCRETIONARY = "inside", "task-implied", "discretionary"


def _drift_class(path: str, radius: list[str], base_paths: frozenset[str]) -> str:
    """One changed file's class (ADR-0026 s5): inside the radius, else machine-written, task-implied or discretionary."""
    if _changes.in_radius(path, radius):
        return INSIDE
    machine = _changes.machine_written(path)
    if machine is not None:
        return f"machine:{machine}"
    return TASK_IMPLIED if _changes.is_test_path(path, base_paths) else DISCRETIONARY


@dataclass(frozen=True)
class _Hood:
    """The task's neighbourhood (ADR-0026 s5): the radius, the modules the radius files import (a static scan of the
    pre-turn tree), test paths, and the paths the task prompt names; `members` are its pre-turn files, so a directory
    target holding one is inside."""

    radius: list[str]
    base_paths: frozenset[str]
    imports: frozenset[str]
    named: tuple[str, ...]
    members: frozenset[str]

    def holds(self, target: str) -> bool:
        if target in ("", "."):  # the working copy's own root
            return True
        if _ABSOLUTE.match(target):  # outside the working copy
            return False
        if (_changes.in_radius(target, self.radius) or _changes.is_test_path(target, self.base_paths)
                or target in self.imports or any(_names(n, target) for n in self.named)):
            return True
        prefix = target.rstrip("/") + "/"
        return any(m.startswith(prefix) for m in self.members)


_ABSOLUTE = re.compile(r"(?:[A-Za-z]:)?/")
_BACKTICKED = re.compile(r"`([^`\s]+)`")
_EXTENSION = re.compile(r"\.[A-Za-z]\w{0,4}$")


def _names(named: str, target: str) -> bool:
    """`target` is the named path, under it, or ends with it (a prompt names `limiter.py` or `vendor/quotakit`)."""
    return target == named or target.startswith(named + "/") or target.endswith("/" + named)


def _prompt_paths(task_dir: Path) -> tuple[str, ...]:
    """The backticked tokens of prompt.md that look like paths: one holding a `/`, or ending in a file extension.

    simplify: backticked tokens only; ceiling: the ten lean prompts, which backtick every path they name (NG1:
    `src/cachetools/limiter.py`, `vendor/quotakit`, `tests/test_limiter.py`); upgrade trigger: a prompt naming a
    path in plain text.
    """
    try:
        text = (task_dir / "prompt.md").read_text(encoding="utf-8")
    except OSError:
        return ()
    tokens = {t.removeprefix("./").rstrip("/") for t in _BACKTICKED.findall(text)}
    return tuple(sorted(t for t in tokens if t and ("/" in t or _EXTENSION.search(t))))


def _module_files(dotted: str, base_paths: frozenset[str], anchor: str | None) -> set[str]:
    """The pre-turn files a module name can be: `<m>.py` or `<m>/__init__.py`, exactly under `anchor` (a relative
    import's package) or at any depth (an absolute import in a `src/` layout)."""
    rel = dotted.replace(".", "/")
    if anchor is not None:
        stem = "/".join(x for x in (anchor, rel) if x)
        return {f"{stem}.py", f"{stem}/__init__.py"} & base_paths
    ends = (f"/{rel}.py", f"/{rel}/__init__.py")
    return {p for p in base_paths if p in (f"{rel}.py", f"{rel}/__init__.py") or p.endswith(ends)}


def _imports(base: Path, base_paths: frozenset[str], radius: list[str]) -> frozenset[str]:
    """The pre-turn files the radius's Python files import, by a static scan (ast; no code runs).

    simplify: Python only; ceiling: the ten lean tasks (all Python); upgrade trigger: a C# task with a radius, whose
    `using` names a namespace, not a file.
    """
    out: set[str] = set()
    for rel in sorted(p for p in base_paths if p.endswith(".py") and _changes.in_radius(p, radius)):
        try:
            tree = ast.parse((base / rel).read_bytes())
        except (SyntaxError, ValueError, OSError):
            continue
        package = rel.rsplit("/", 1)[0] if "/" in rel else ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    out |= _module_files(alias.name, base_paths, None)
            elif isinstance(node, ast.ImportFrom):
                anchor = None
                if node.level:
                    parts = package.split("/") if package else []
                    anchor = "/".join(parts[:len(parts) - (node.level - 1)])
                module = node.module or ""
                out |= _module_files(module, base_paths, anchor) if module else set()
                for alias in node.names:  # `from pkg import mod` names a submodule as often as a member
                    out |= _module_files(f"{module}.{alias.name}" if module else alias.name, base_paths, anchor)
    return frozenset(out)


def _neighbourhood(base: Path, base_paths: frozenset[str], radius: list[str], task_dir: Path) -> _Hood:
    imports, named = _imports(base, base_paths, radius), _prompt_paths(task_dir)
    literal = {g for g in radius if not any(c in g for c in "*?[")}  # a radius file the turn creates
    members = {p for p in base_paths if _changes.in_radius(p, radius) or _changes.is_test_path(p, base_paths)
               or p in imports or any(_names(n, p) for n in named)}
    return _Hood(radius, base_paths, imports, named, frozenset(members | literal | set(named)))


def _target(raw: str, cell_id: str) -> str:
    """A record's path relative to the cell's working copy (the live copy is `<cells_root>/<run>/<cell>/ws`, engine
    `_launch`); a path outside it stays absolute."""
    path = raw.replace("\\", "/")
    marker = f"/{cell_id}/ws"
    at = path.find(marker + "/")
    if at >= 0:
        return path[at + len(marker) + 1:]
    return "" if path.endswith(marker) else path.removeprefix("./")


def _shown(target: str) -> str:
    """A target as the evidence shows it: an absolute path outside the working copy keeps its last two segments only."""
    if not _ABSOLUTE.match(target):
        return target
    return ".../" + "/".join([s for s in target.split("/") if s][-2:])


def _attention(inp: CellInput, hood: _Hood) -> Score:
    """attention_drift: outside targets / read and search targets, over the cell's main and sub-agent records.

    A read or search call is one whose tool the reader classes `read` (the `tool_calls` rows' `tool_class`, one
    definition). A shell call is not one, except for a reader that classifies its shell commands per call
    (`shell_command_class`; Codex, which reads through its shell, B1 / I1): there each call contributes the targets
    of its read and list statements, whatever else it does, and a read that names no path is `no-path`.
    """
    session = next((e.get("session_id") for e in reversed(inp.events) if e.get("kind") == "attempt.session_opened"), "")
    session = session or (inp.extraction.session_id if inp.extraction is not None else None) or ""  # agy: the record names it
    if not session:
        return Score(None, NO_SESSION)
    harness = inp.cell.get("harness")
    reader = profiles.READERS.get(harness)
    tool_inputs = getattr(inspect.getmodule(reader), "tool_inputs", None) if reader is not None else None
    if tool_inputs is None:
        return Score(None, f"no tool-input reader for {harness}")
    profile, home = inp.plan["profiles"][harness], inp.archive / "home"
    mains = profiles.find_records(home, profile["record_glob"], session)
    if len(mains) != 1:  # the runner's own rule (`_extract`)
        return Score(None, NO_RECORD)
    records = [mains[0], *(p for p in profiles.find_records(home, profile.get("subagent_glob") or "", session) if p != mains[0])]
    module = inspect.getmodule(reader)
    shell_class, shell_names = getattr(module, "shell_command_class", None), getattr(module, "SHELL_NAMES", ())
    classes = {row["name"]: row["tool_class"] for row in inp.tool_calls}
    counts, log = {"inside": 0, "outside": 0, "no-path": 0}, []
    for record in records:
        for call in tool_inputs(record).calls:
            if shell_class is not None and call.name in shell_names:  # one name, many classes: decided per call
                kind, paths = shell_class(call.command)
                if kind != "read" and not paths:
                    continue
            elif call.is_write or classes.get(call.name) != "read":
                continue
            else:
                paths = call.paths
            for target in [_target(p, inp.cell["cell_id"]) for p in paths] or [None]:
                where = "no-path" if target is None else "inside" if hood.holds(target) else "outside"
                counts[where] += 1
                log.append(f"{record.name}\t{call.native_ordinal}\t{call.name}\t{'-' if target is None else _shown(target)}\t{where}\n")
    evidence = inp.out_dir / "attention.log"
    evidence.write_text("".join(log), encoding="utf-8")
    ev = evidence.relative_to(inp.run_dir).as_posix()
    targets = counts["inside"] + counts["outside"]
    return Score(Decimal(counts["outside"]) / Decimal(targets), None, ev) if targets else Score(None, NO_TARGETS, ev)


def _measure(inp: CellInput, rules: tuple | None) -> dict[str, Score]:
    ws, timeout = inp.archive / "ws", inp.plan["parameters"]["grading_step_timeout"]
    measured = (*SCOPE, "convention_drift", "attention_drift")
    if not ws.is_dir():
        return dict.fromkeys(measured, Score(None, NO_WORKING_COPY))
    commit = _changes.pre_turn_commit(ws, inp.cell, timeout)
    if commit is None:
        return dict.fromkeys(measured, Score(None, _changes.NOT_FOUND))
    radius = inp.task.get("blast_radius") or []
    lines: Counter[str] = Counter()
    files: Counter[str] = Counter()
    changed = violations = 0
    log, hood = [], None
    work_root = inp.work_root or inp.out_dir  # ADR-0013: outside the repository in a real pass; out_dir in a test
    try:
        with (_changes.pre_turn_tree(ws, commit, work_root / "pre-turn", timeout) as base,
              _changes.grading_copy(ws, work_root / "work") as work):
            changes = _changes.change_set(base, work)
            ignored = _ignored(base, [p for p, s in changes.items() if s == "added"], work_root, timeout)
            base_paths = frozenset(_changes._files(base))
            for path, status in changes.items():
                if path in ignored:
                    log.append(f"ignored\t{path}\n")
                    continue
                old = _lines(base / path) if status != "added" else []
                added, deleted = _diff(old, _lines(work / path) if status != "deleted" else [])
                cls = _drift_class(path, radius, base_paths)
                if cls != INSIDE:
                    lines[cls] += len(added) + deleted
                    files[cls] += 1
                file_rules = [(name, pattern) for name, suffix, pattern in rules or () if Path(path).suffix == suffix]
                if file_rules:  # the denominator: added or changed lines of a file type the rules cover
                    changed += len(added)
                broken = [f"{name}:{n}" for n, line in added for name, pattern in file_rules
                          if pattern.fullmatch(line.removeprefix(codecs.BOM_UTF8))]
                violations += len(broken)
                line = f"{status}\t{path}\t{'inside' if cls == INSIDE else 'outside'}\t+{len(added)} -{deleted}\t{' '.join(broken)}"
                log.append(line + ("\n" if cls == INSIDE else f"\t{cls}\n"))  # an inside line keeps its 0.7 bytes
            if "attention_drift" in inp.metrics:
                hood = _neighbourhood(base, base_paths, radius, inp.task_dir)
    except gitsafe.GitError as exc:  # `git archive` of the pre-turn commit, or `git check-ignore` over its tree
        if not exc.result.timed_out:
            raise
        return dict.fromkeys(measured, Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s"))
    evidence = inp.out_dir / "drift.log"
    evidence.write_text("".join(log), encoding="utf-8")
    ev = evidence.relative_to(inp.run_dir).as_posix()
    machine = sum(n for cls, n in lines.items() if cls.startswith("machine:"))
    out = {"scope_creep": Score(lines[DISCRETIONARY], None, ev), "scope_creep_files": Score(files[DISCRETIONARY], None, ev),
           "drift_machine_lines": Score(machine, None, ev), "drift_task_implied_lines": Score(lines[TASK_IMPLIED], None, ev)}
    out["convention_drift"] = Score(Decimal(100 * violations) / Decimal(changed), None, ev) if changed else Score(None, NO_LINES, ev)
    if hood is not None:
        out["attention_drift"] = _attention(inp, hood)
    return out


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """The design's drift metrics, each only when `inp.metrics` names it (the runner's applicable set)."""
    rules = RULES.get(inp.cell["task"])
    out = {m: Score(None, reason) for m, reason in NA_BY_DESIGN.items()} | _measure(inp, rules)
    if rules is None:  # a property of the task, so it reads before any property of the archive
        out["convention_drift"] = Score(None, NO_RULES)
    return {m: s for m, s in out.items() if m in inp.metrics}
