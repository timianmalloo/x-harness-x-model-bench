"""The shared tool-call classifier, the phase rule and the carry-until-compaction rule (ADR-0026 s4), one definition
each. Report-only: derived from a cell's `ToolInput` sequence, never stored.

`classify` is the classifier moved from `report.pack_improvement` (design pack-improvement-section.md section 4.3),
whose categories are computed here unchanged; it also names the three classes the phase rule reads (`edit_tool`,
`verify_command`, `read_tool`). The phase rule (ADR-0026 s4): `edit` for an edit-class tool or a write; `verify` for a
command matching VERIFY_COMMANDS; `explore` for read, search and list tools, and for other commands before the first
edit; `other` for the rest.

The read and edit classes are the readers' own (`TOOL_CLASS(ES)` of each harness reader; no name is in two classes)
plus Codex's shell read classifier (`codex.shell_read_kind`), applied to any call's command text.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from harness_bench import profiles
from harness_bench.grade import _changes
from harness_bench.telemetry import (
    ProcessTrace,
    ToolInput,
    agy,
    claude_code,
    codex,
    copilot,
    grok,
)
from harness_bench.views import CellView, Measure, RunView

PHASES = ("explore", "edit", "verify", "other")
VERIFY_COMMANDS = ("pytest", "tox", "ruff", "mypy", "pyright", "unittest")  # the declared test and lint patterns
_VERIFY = re.compile(r"\b(?:" + "|".join(VERIFY_COMMANDS) + r")\b")

# design section 4.3's table (moved from pack_improvement, unchanged).
PACK_PATHS = (
    ".claude/knowledge/", ".claude/skills/", ".claude/agents/",
    ".github/instructions/", ".github/knowledge/", ".github/agents/", ".github/prompts/",
    ".agents/skills/", ".grok/", "docs/ai-forward-pack/", "AGENTS.md",
)
PACK_SCRIPTS = ("audit-log.py", "prompt-log.py", "docs-graph.py", "coord-core.py", "pack-doctor.py")
TEST_PATH = re.compile(r"(^|/)tests?/|Tests?\.cs$|(^|/)test_[^/]*\.py$|_test\.py$")
_WORKTREE_CREATE = re.compile(r"\bgit\s+worktree\s+add\b|\bworktree\s+new\b")
_GIT_IDENTITY = re.compile(r"\bgit\s+config\s+(--global\s+)?user\.(name|email)\b")
CEREMONY_CLASSES = frozenset({"pack_read", "skill_load", "pack_script", "worktree_create"})

_CLASS_MAPS: tuple[Mapping[str, str], ...] = (claude_code.TOOL_CLASSES, copilot.TOOL_CLASS, grok.TOOL_CLASS,
                                              agy.TOOL_CLASS)
READ_TOOLS = frozenset(n for m in _CLASS_MAPS for n, c in m.items() if c == "read")
EDIT_TOOLS = frozenset(n for m in _CLASS_MAPS for n, c in m.items() if c == "edit")

NO_BYTES = "a tool result's size is not in the record"
NO_CALLS = "no tool calls recorded"
# The harnesses whose reader yields a `ToolInput` sequence (each module's `tool_inputs`).
TRACE_READERS = {"claude-code": claude_code, "codex": codex, "copilot": copilot}


def _matches_blast_radius(paths: Sequence[str], blast_radius: Sequence[str]) -> bool:
    """Any of `paths` inside `blast_radius`, by `_changes.in_radius`: the graders' one radius definition
    (ADR-0026 s4, RADIUS-TEST-A), case-sensitive on every host, so a path is inside on this report
    exactly when it is inside for drift and the property graders. Its `*` matches `/` too, so `src/**`
    and `src/*` match the same set (design section 4.4)."""
    return any(_changes.in_radius(p, list(blast_radius)) for p in paths)


def classify(call: ToolInput, blast_radius: Sequence[str] | None) -> frozenset[str]:
    """One tool call's classes (design section 4.3's table, plus the phase rule's three). `blast_radius=None`
    means the task's own blast radius could not be read: `product_write` then never fires here (it would
    otherwise guess a match against an unknown set) -- a caller that needs the NA propagated checks
    `blast_radius is None` itself before calling.

    Only `call.name`, `call.paths` and `call.command` are examined (PI-T7): a source write whose file
    *content* happens to mention `tests/` is invisible to `ToolInput`, which carries no content field, so it
    can never be mistaken for a `test_write`."""
    classes: set[str] = set()
    haystack = " ".join((*call.paths, call.command or ""))
    if not call.is_write and any(p in haystack for p in PACK_PATHS):
        classes.add("pack_read")
    if call.name in ("Skill", "skill"):
        classes.add("skill_load")
    if call.command and any(s in call.command for s in PACK_SCRIPTS):
        classes.add("pack_script")
    if (call.command and _WORKTREE_CREATE.search(call.command)) or call.name == "EnterWorktree":
        classes.add("worktree_create")
    if call.command and _GIT_IDENTITY.search(call.command):
        classes.add("git_identity")
    if call.is_write and any(TEST_PATH.search(p) for p in call.paths):
        classes.add("test_write")
    elif call.is_write and blast_radius is not None and _matches_blast_radius(call.paths, blast_radius):
        classes.add("product_write")
    if call.is_write or call.name in EDIT_TOOLS:
        classes.add("edit_tool")
    if call.command and _VERIFY.search(call.command):
        classes.add("verify_command")
    if call.name in READ_TOOLS or codex.shell_read_kind(call.command) is not None:
        classes.add("read_tool")
    return frozenset(classes)


def phases(calls: Sequence[ToolInput]) -> tuple[str, ...]:
    """One phase (PHASES) per call, in native order; the sequence decides `explore` (before the first edit).
    assume: a read, search or list tool is `explore` wherever it falls, and only "other commands" (a call with
    a command that is not a read and not a verify) need to precede the first edit -- the ADR's sentence read with
    "before the first edit" binding its last clause. Confirmed by: the ADR's author restating the rule. If false:
    reads after the first edit move from explore to other, so explore counts fall and other counts rise."""
    out: list[str] = []
    edited = False
    for call in calls:
        cls = classify(call, None)
        if "edit_tool" in cls:
            edited = True
            out.append("edit")
        elif "verify_command" in cls:
            out.append("verify")
        elif "read_tool" in cls or (call.command and not edited):
            out.append("explore")
        else:
            out.append("other")
    return tuple(out)


def phase_counts(calls: Sequence[ToolInput]) -> dict[str, int]:
    """Calls per phase, every phase present (a phase no call fell in is a real 0: the sequence was read)."""
    counts = dict.fromkeys(PHASES, 0)
    for p in phases(calls):
        counts[p] += 1
    return counts


def rereads(calls: Sequence[ToolInput]) -> int:
    """Reads of a path read before with no edit to that path in between (ADR-0026 s4), over the same sequence."""
    seen: set[str] = set()
    count = 0
    for call in calls:
        cls = classify(call, None)
        if "edit_tool" in cls:
            seen.difference_update(call.paths)
        elif "read_tool" in cls:
            count += sum(1 for p in call.paths if p in seen)
            seen.update(call.paths)
    return count


def bytes_returned(calls: Sequence[ToolInput]) -> Measure:
    """The bytes the tools returned: the sum, or NOT_RECORDED when any call's size is not in the record (never a
    partial sum) or there is no call."""
    if not calls:
        return Measure(None, NO_CALLS)
    if any(c.bytes_returned is None for c in calls):
        return Measure(None, NO_BYTES)
    return Measure(sum(c.bytes_returned for c in calls))


def carry_until_compaction(entered: Sequence[int], compacted_before: Collection[int]) -> tuple[int, ...]:
    """Per request index i, the amount still carried in the context: everything that `entered` at or before i,
    counted again on each later request until a compaction (`compacted_before` holds the request indices a
    compaction precedes), which drops what entered before it."""
    out: list[int] = []
    carried = 0
    for i, amount in enumerate(entered):
        if i in compacted_before:
            carried = 0
        carried += amount
        out.append(carried)
    return tuple(out)


def attempt_dirs(run_dir: Path, cell_id: str) -> list[Path]:
    """A cell's archived attempt folders, oldest first (`attempt-<n>`; a leaked temp sibling is not one)."""
    base = run_dir / "archive" / cell_id
    if not base.is_dir():
        return []
    return sorted((p for p in base.glob("attempt-*") if p.name.rsplit("-", 1)[-1].isdigit()),
                  key=lambda p: int(p.name.rsplit("-", 1)[1]))


def cell_trace(run_dir: Path, view: RunView, cell: CellView, session_id: str | None) -> ProcessTrace | None:
    """This cell's `ProcessTrace`: the main session's `tool_inputs` composed with every sub-agent
    record's own calls, in native order (design section 4.3's own comment). The record globs come
    from the run's OWN frozen `plan.json` profile entry (`plan.py:240-245`), never a live
    `bench/profiles/*.yaml` re-read -- a profile that drifted after this run was planned must never
    change what this run's own trace reads. `None` (never a guessed empty trace) when the harness has
    no reader, the archive has no attempt, or no session id was recorded."""
    reader = TRACE_READERS.get(cell.harness)
    profile = (view.plan.get("profiles") or {}).get(cell.harness) or {}
    if reader is None or not session_id or not profile.get("record_glob"):
        return None
    attempts = attempt_dirs(run_dir, cell.cell_id)
    if not attempts:
        return None
    home = attempts[-1] / "home"
    mains = profiles.find_records(home, profile["record_glob"], session_id)
    if not mains:
        return None
    main = reader.tool_inputs(mains[0])
    extra: list[ToolInput] = []
    for sub_path in profiles.find_records(home, profile.get("subagent_glob") or "", session_id):
        extra.extend(reader.tool_inputs(sub_path).calls)
    return ProcessTrace(main.first_assistant_text, main.calls + tuple(extra))
