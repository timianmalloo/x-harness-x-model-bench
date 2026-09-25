"""Architecture: architecture_conformance from the cell's change set (design phase3-graders, Architecture).

- Dependency direction: the component depends only on the platform and its own layer. The rule table below is keyed
  by task id; it sits in this module, so `runner.grader_build` hashes it with the grader.
- The change set is `_changes`' (GR-CODE c1, one definition): the cell's working tree against the pre-turn tree under
  the tamper rule, by content with CRLF normalised, build output excluded. A rule reads every file the cell added or
  changed that lies in its scope (folder prefix and suffix), whole, in the cell's tree.
- The value is rules passed / rules, a Decimal at scale 4. A rule passes when every file in its scope conforms.
  NA `no architecture rules for this task` for a task with no row; NA `no source file changed` when no rule has a file
  in scope. The shared reasons (no working copy, pre-turn commit not found, HB-GRD-002) are as the other graders'.
- Not re-checked here, because they are measured elsewhere: C1's section checks (hidden tests) and D1's layer
  boundary (`scope_creep`).
- The evidence is `architecture.log` under the grader's out_dir: one line per file read, `pass` or `fail`, its rule,
  its path and the names that broke the rule.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from harness_bench import gitsafe
from harness_bench.grade import CellInput, Score, _changes

METRIC = "architecture_conformance"
NO_WORKING_COPY = "no working copy in the archive"  # the design's shared reason, as drift and correctness write it
NO_RULES = "no architecture rules for this task"
NO_SOURCE = "no source file changed"
SCALE = Decimal("0.0001")

__all__ = ["METRIC", "NO_RULES", "NO_SOURCE", "RULES", "grade_cell"]


def _py_breaks(work: Path, path: str) -> list[str]:
    """C1: the top-level names the file imports that are neither `sys.stdlib_module_names` nor in the working copy.

    A relative import is in the working copy. "In the working copy" is a `<name>.py` or a `<name>/` folder at the root
    of the cell's tree or beside the importing file (the two folders `sys.path` starts with for a script and for the
    project). assume: that is what "modules in the working copy" means; if false, an import of a module that sits
    deeper in the tree is counted as a break. A file that does not parse cannot show its imports, so it is one break,
    `<unparsed>`; assume: an unparsed file is not conformant (the design has no reason for it; correctness scores it).
    """
    try:
        tree = ast.parse((work / path).read_bytes(), filename=path)
    except (SyntaxError, ValueError):
        return ["<unparsed>"]
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.append(node.module.split(".")[0])
    local = set()
    for folder in {work, (work / path).parent}:
        local |= {p.stem if p.suffix == ".py" else p.name for p in folder.iterdir() if p.suffix == ".py" or p.is_dir()}
    return sorted({n for n in names if n not in sys.stdlib_module_names and n not in local})


# A using directive: at the file's start or after `;`, `{` or `}` (a namespace block), optionally `global` and
# `static`, optionally `Alias =`, then the name (`global::` dropped) and `;`, a generic alias's `<...>` allowed. A
# `using (...)` statement or a `using var x = ...;` declaration never matches (its name is not followed by `;`).
USING = re.compile(r"(?:^|(?<=[;{}]))\s*(?:global\s+)?using\s+(?:static\s+)?(?:@?\w+\s*=\s*)?(?:global::)?"
                   r"(@?[A-Za-z_][\w.]*)\s*(?:<[^;]*>)?\s*;", re.MULTILINE)
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
D1_LAYERS = ("System", "AiDe.Core")


def _cs_breaks(work: Path, path: str) -> list[str]:
    """D1: the `using` names in the file that are not System, System.*, AiDe.Core or AiDe.Core.*.

    simplify: comments are removed by a regex that does not know string literals; ceiling: D1's Projections files,
    where no string holds `//` or `/*` before a using; upgrade trigger: a task whose rules read C# beyond usings, when
    this moves to a real C# tokenizer.
    """
    text = COMMENT.sub("", (work / path).read_text(encoding="utf-8-sig", errors="replace"))
    names = [m.group(1).removeprefix("@") for m in USING.finditer(text)]
    return sorted({n for n in names if not any(n == layer or n.startswith(layer + ".") for layer in D1_LAYERS)})


# The rule table, keyed by task id: (rule, folder prefix, file suffix, the names in a file that break the rule).
# simplify: rules in code, keyed by task id; ceiling: C1 and D1; upgrade trigger: a third task or a new task version,
# when the rules move to tasks/<id>/oracle/architecture.yaml.
Rule = tuple[str, str, str, Callable[[Path, str], list[str]]]
RULES: dict[str, tuple[Rule, ...]] = {
    "C1": (("C1 imports: stdlib or the working copy", "", ".py", _py_breaks),),
    "D1": (("D1 Projections usings: System or AiDe.Core", "src/AiDe.Core/Projections/", ".cs", _cs_breaks),),
}


def _measure(inp: CellInput, rules: tuple[Rule, ...]) -> Score:
    ws, timeout = inp.archive / "ws", inp.plan["parameters"]["grading_step_timeout"]
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    commit = _changes.pre_turn_commit(ws, inp.cell, timeout)
    if commit is None:
        return Score(None, _changes.NOT_FOUND)
    applied = passed = 0
    log = []
    try:
        with (_changes.pre_turn_tree(ws, commit, inp.out_dir / "pre-turn", timeout) as base,
              _changes.grading_copy(ws, inp.out_dir / "work") as work):
            written = [p for p, status in _changes.change_set(base, work).items() if status != "deleted"]
            for name, prefix, suffix, breaks in rules:
                scope = [p for p in written if p.startswith(prefix) and p.endswith(suffix)]
                if not scope:  # a rule with no file to read is not a rule of this cell
                    continue
                applied += 1
                broken = {p: breaks(work, p) for p in scope}
                passed += not any(broken.values())
                log += [f"{'fail' if b else 'pass'}\t{name}\t{p}\t{' '.join(b)}\n" for p, b in broken.items()]
    except gitsafe.GitError as exc:  # `git archive` of the pre-turn commit
        if not exc.result.timed_out:
            raise
        return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s")
    evidence = inp.out_dir / "architecture.log"
    evidence.write_text("".join(log), encoding="utf-8")
    ev = evidence.relative_to(inp.run_dir).as_posix()
    if not applied:
        return Score(None, NO_SOURCE, ev)
    return Score((Decimal(passed) / Decimal(applied)).quantize(SCALE), None, ev)


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """architecture_conformance, only when `inp.metrics` names it (the runner's applicable set)."""
    if METRIC not in inp.metrics:
        return {}
    rules = RULES.get(inp.cell["task"])
    if rules is None:  # a property of the task, so it reads before any property of the archive
        return {METRIC: Score(None, NO_RULES)}
    return {METRIC: _measure(inp, rules)}
