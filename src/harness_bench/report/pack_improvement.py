"""Pack-improvement report section: pure computations over `view`, board rows and harness traces
(design docs/design/pack-improvement-section.md sections 3-6, slices S3-S4; R-85 DR-PI-1..4).

Report-only (ADR-0006 derive, don't store) -- the `context_growth` pattern (`report/context_growth.py`):
this module reads only what the report already holds through the existing readers and stores nothing.
Nothing here writes the ledger, the catalog or the board export (DR-PI-1, DR-PI-4).

NA is never 0 (R-85 item 1): a computation that cannot read what it needs returns a `views.Measure(None,
reason)` carrying one of this module's own NA-reason constants, never a silently zeroed count. In
particular, an unreadable `blast_radius` makes `product_write` NA, which cascades to every indicator
built on it (`test_first`, `stopped_without_product`, `diverted_delivery`) -- they read
`NA_BLAST_RADIUS`, never "zero product writes".

This slice (S3, S4) implements the pairing, cost, classification and indicator primitives the red-first
plan names (PI-T3, T4, T7, T8, T9, T13) and the rule-layer primitives for value/waste, the R-85-renamed
inconclusive predicates, per-intention verdicts and findings ranking (PI-T10, T11, T12). Rendering
(`html.py`, S5) and the golden slow-ring test (S6) are a later slice; see the module's own docstring
notes below for what each function still needs wired to it.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

from harness_bench.board import _cell_task_rep
from harness_bench.grade.cost import ACP_MISSES_CALLS, SESSION_TOTALS
from harness_bench.telemetry import ToolInput
from harness_bench.views import CellView, Measure, sum_tokens

# A threshold change bumps this and the Method line prints it (design section 10 DR-PI-2, R-85 c4).
PACK_RULES_VERSION = "1"

# Decimal arithmetic under a fixed context (design section 4). stats.py builds an equal context for the
# same reason but keeps it module-private (T-B9's import-graph contract), so this module builds its own
# rather than reaching into stats' internals.
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)

# Thresholds (design section 10 DR-PI-2; each versioned by PACK_RULES_VERSION, each basis-commented).
WASTE_RATIO = Decimal("1.25")  # grid-1 F-7: pack-on token share 0.32 on vs 0.01 off at this ratio
CEREMONY_SHARE_THRESHOLD = Decimal("0.20")  # PK-05; grid-1 F-2's ceremony-heavy cells cluster above this
FIXED_CONTEXT_TOKENS = 5000  # PK-04 absolute floor; grid-1 F-2 delta +18.4k on / +9.2k off
FIXED_CONTEXT_SHARE = Decimal("0.25")  # PK-04 relative floor, the same F-2 deltas as a share of off
PROCESS_ONLY_ON = Decimal("0.8")  # section 5 rule 3
PROCESS_ONLY_OFF = Decimal("0.2")  # section 5 rule 3

# NA reasons -- module constants (design section 9; R-85 item 1, condition 2: "every NA above carries
# its reason string as a module constant").
NA_BLAST_RADIUS = "blast radius not readable"
NA_NO_EXTRA_TOKENS = "no extra tokens"
NA_ARCHIVE_ABSENT = "archive not present"
NA_RECORD_UNREADABLE = "native record unreadable"
NA_NO_TOOL_CALLS = "no tool calls"
NA_NO_TEST_PATH = "task has no test path in its blast radius"
NA_NO_DRIFT_GRADER = "no drift grader for this task"

# design section 4.3's table.
PACK_PATHS = (
    ".claude/knowledge/", ".claude/skills/", ".claude/agents/",
    ".github/instructions/", ".github/knowledge/", ".github/agents/", ".github/prompts/",
    ".agents/skills/", ".grok/", "docs/ai-forward-pack/", "AGENTS.md",
)
PACK_SCRIPTS = ("audit-log.py", "prompt-log.py", "docs-graph.py", "coord-core.py", "pack-doctor.py")
PACK_WRITE_PATHS = ("docs/audit/", "docs/docs-index.js", ".agents/", "docs/coordination/", "docs/lessons/")

TEST_PATH = re.compile(r"(^|/)tests?/|Tests?\.cs$|(^|/)test_[^/]*\.py$|_test\.py$")
_WORKTREE_CREATE = re.compile(r"\bgit\s+worktree\s+add\b|\bworktree\s+new\b")
_GIT_IDENTITY = re.compile(r"\bgit\s+config\s+(--global\s+)?user\.(name|email)\b")
_GOAL = re.compile(r"\bGoal\b\s*[:*]", re.IGNORECASE)
_DONE_WHEN = re.compile(r"Done when", re.IGNORECASE)
_GITDIR_MARKER = "/ws/.git/worktrees/"

CEREMONY_CLASSES = frozenset({"pack_read", "skill_load", "pack_script", "worktree_create"})

# drift.log's own two line shapes (`grade/drift.py:125,139`, pinned by reading the grader's writer, not
# guessed from a sample -- R-85 hand-off): a changed-file line is 5 tab-separated fields ending in the
# +added/-deleted counts, a skipped-file line is `ignored\t<path>\n` (2 fields; never counted).
_DRIFT_LINE = re.compile(
    r"^(?P<status>[^\t]+)\t(?P<path>[^\t]+)\t(?P<zone>inside|outside)\t\+(?P<added>\d+) -(?P<deleted>\d+)(?:\t.*)?$"
)

# oracle.log's two observed failing-test-name shapes (design section 4.6 "same failure both arms";
# pinned against the real grid-1/grid-1-cc corpus, `tests/fixtures/pack_improvement/oracle-*.log`):
# unittest's verbose per-test line (`correctness.py`'s own oracle, stderr) and xUnit's `[FAIL]` line
# (the dotnet oracle, `correctness.py:120-260`). No pytest-shaped failure line was observed in either
# grid (pytest failures there come from a JUnit XML report, not oracle.log's own text) -- a task graded
# by pytest with a failure this reader cannot parse simply yields no names, and the caller skips the
# reason rather than guessing (design 4.6's own rule).
_UNITTEST_FAIL_NAME = re.compile(r"^\S+ \(([\w.]+)\) \.\.\. FAIL$", re.MULTILINE)
_XUNIT_FAIL_NAME = re.compile(r"^\[xUnit\.net[^\]]*\]\s+(\S+) \[FAIL\]$", re.MULTILINE)


# --------------------------------------------------------------------------------------------------
# Section 3: pairing (PI-T3)
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    """One pair (design section 3: pair grain) -- a (task, combo, rep) whose pack-on and pack-off
    cells are BOTH `validity == "valid"`. A cell whose partner is invalid, ungraded, or missing forms
    no pair; it never appears half-paired."""

    task: str
    combo: str
    rep: int
    on: CellView
    off: CellView


def pairs(cells: Sequence[CellView], plan_by_id: Mapping[str, dict]) -> list[Pair]:
    """Every complete pair among `cells` (design section 3). `plan_by_id` is `plan.json`'s
    `cells[]` keyed by cell id, the same map `board._cell_task_rep` (reused here, not copied --
    design section 3.1) reads task and rep from. Deterministic order: (task, combo, rep)."""
    by_key: dict[tuple[str, str, int], dict[str, CellView]] = {}
    for c in cells:
        if c.validity != "valid":
            continue
        task, rep, _ = _cell_task_rep(c.cell_id, plan_by_id)
        by_key.setdefault((task, c.combo, rep), {})[c.pack] = c
    result = []
    for (task, combo, rep), by_pack in sorted(by_key.items()):
        if "on" in by_pack and "off" in by_pack:
            result.append(Pair(task=task, combo=combo, rep=rep, on=by_pack["on"], off=by_pack["off"]))
    return result


# --------------------------------------------------------------------------------------------------
# Section 4.2: cost (PI-T4, PI-T13)
# --------------------------------------------------------------------------------------------------


def tokens_ratio(pair: Pair) -> Measure:
    """`tokens_on / tokens_off` (design section 4.2). NA when either side is NA, carrying that side's
    own `tokens_reason` -- never 0 (PI-T4). NA "off arm used 0 tokens" when the off side is a real,
    readable zero (a division the design does not define)."""
    on_t = sum_tokens(pair.on.tokens)
    if on_t is None:
        return Measure(None, pair.on.tokens_reason or "not recorded")
    off_t = sum_tokens(pair.off.tokens)
    if off_t is None:
        return Measure(None, pair.off.tokens_reason or "not recorded")
    if off_t == 0:
        return Measure(None, "off arm used 0 tokens")
    with localcontext(_CONTEXT):
        return Measure(Decimal(on_t) / Decimal(off_t))


def median_ratio(ratios: Sequence[Measure]) -> tuple[Measure, int, int]:
    """(median Measure, k pairs whose ratio > 1, n pairs with a recorded ratio) -- design section 4.2's
    "median pair ratio, and k of n pairs > 1". NA ratios are dropped from both the median and the two
    counts, never coerced to 0 or 1 (PI-T4: "the median uses the other pairs")."""
    valid = sorted(r.value for r in ratios if r.value is not None)
    if not valid:
        return Measure(None, "no pair has a recorded ratio"), 0, 0
    mid = len(valid) // 2
    if len(valid) % 2:
        median = valid[mid]
    else:
        with localcontext(_CONTEXT):
            median = (valid[mid - 1] + valid[mid]) / 2
    above = sum(1 for v in valid if v > 1)
    return Measure(median), above, len(valid)


def modeled_share(delta: Decimal, calls_on_sum: int, tokens_on_sum: int, tokens_off_sum: int) -> Measure:
    """The fixed-context modeled share (design section 4.2): `delta * calls_on / (tokens_on -
    tokens_off)`, capped at 1.00, always labelled Inferred by its caller. NA `NA_NO_EXTRA_TOKENS`
    when the denominator is <= 0 (R-85 item 1) -- pack-on did not use more tokens overall, so no
    share of "extra" tokens is defined; never capped to a number in that case."""
    denom = tokens_on_sum - tokens_off_sum
    if denom <= 0:
        return Measure(None, NA_NO_EXTRA_TOKENS)
    with localcontext(_CONTEXT):
        share = (delta * Decimal(calls_on_sum)) / Decimal(denom)
    return Measure(min(share, Decimal(1)))


def first_call_input(
    *, usage_source: str, harness: str, auxiliary_models: Sequence[str], model_call_rows: Sequence[Mapping]
) -> Measure:
    """The earliest model call (by `start`, then `native_ordinal`) whose `model` is not one of the
    profile's `auxiliary_models` (design section 3.1). NA reasons are `grade/cost.py`'s own constants,
    reused rather than redefined (DM7, PI-T13): an `acp_turn` profile's native record misses calls
    entirely (`ACP_MISSES_CALLS`); Copilot's record is a per-model session total, never per call
    (`SESSION_TOTALS`), regardless of usage_source."""
    if usage_source == "acp_turn":
        return Measure(None, ACP_MISSES_CALLS)
    if harness == "copilot":
        return Measure(None, SESSION_TOTALS)
    candidates = [
        r for r in model_call_rows if not any(str(r.get("model", "")).startswith(a) for a in auxiliary_models)
    ]
    if not candidates:
        return Measure(None, "no model call recorded")
    first = min(candidates, key=lambda r: (r.get("start") or "", r["native_ordinal"]))
    return Measure(Decimal(first["uncached_input"] + first["cache_read"] + first["cache_write"]))


# --------------------------------------------------------------------------------------------------
# Section 4.3: classification and ceremony indicators (PI-T7)
# --------------------------------------------------------------------------------------------------


def classify(call: ToolInput, blast_radius: Sequence[str] | None) -> frozenset[str]:
    """One tool call's classes (design section 4.3's table). `blast_radius=None` means the task's
    own blast radius could not be read: `product_write` then never fires here (it would otherwise
    guess a match against an unknown set) -- a caller that needs the NA propagated checks
    `blast_radius is None` itself before calling (the indicator functions below do this).

    Only `call.paths` and `call.command` are examined (PI-T7): a source write whose file *content*
    happens to mention `tests/` is invisible to `ToolInput`, which carries no content field, so it
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
    elif (
        call.is_write
        and blast_radius is not None
        and any(fnmatch.fnmatch(p, pat) for p in call.paths for pat in blast_radius)
    ):
        classes.add("product_write")
    return frozenset(classes)


def ceremony_share(calls: Sequence[ToolInput], blast_radius: Sequence[str] | None) -> Measure:
    """`ceremony_calls / len(calls)` (design section 4.3). NA `NA_NO_TOOL_CALLS` when the trace has
    no calls at all -- never 0/0 read as 0."""
    if not calls:
        return Measure(None, NA_NO_TOOL_CALLS)
    ceremony = sum(1 for c in calls if classify(c, blast_radius) & CEREMONY_CLASSES)
    with localcontext(_CONTEXT):
        return Measure(Decimal(ceremony) / Decimal(len(calls)))


def goal_state_present(first_assistant_text: str | None) -> bool:
    """`first_assistant_text` matches `\\bGoal\\b\\s*[:*]` and `Done when`, case-insensitive
    (design section 4.3)."""
    text = first_assistant_text or ""
    return bool(_GOAL.search(text) and _DONE_WHEN.search(text))


def test_first(calls: Sequence[ToolInput], blast_radius: Sequence[str] | None) -> Measure:
    """The first `test_write` ordinal precedes the first `product_write` ordinal, or a `test_write`
    exists and no `product_write` does (design section 4.3). NA `NA_BLAST_RADIUS` when the blast
    radius could not be read (R-85 item 1's cascade from `product_write`) -- never a guessed False.
    NA `NA_NO_TEST_PATH` when the task's own blast radius has no test-shaped entry in it at all."""
    if blast_radius is None:
        return Measure(None, NA_BLAST_RADIUS)
    if not any(TEST_PATH.search(p) for p in blast_radius):
        return Measure(None, NA_NO_TEST_PATH)
    first_test = next((i for i, c in enumerate(calls) if "test_write" in classify(c, blast_radius)), None)
    if first_test is None:
        return Measure(False)
    first_product = next((i for i, c in enumerate(calls) if "product_write" in classify(c, blast_radius)), None)
    return Measure(first_product is None or first_test < first_product)


def git_identity_set(calls: Sequence[ToolInput]) -> bool:
    """Any call matches `git config (--global) user.(name|email)` (design section 4.3). Independent
    of `blast_radius` (the class does not read it)."""
    return any("git_identity" in classify(c, None) for c in calls)


# --------------------------------------------------------------------------------------------------
# Section 4.4: drift indicators (PI-T8, PI-T9)
# --------------------------------------------------------------------------------------------------


def sibling_worktrees(attempt_dir: Path) -> list[Path]:
    """Directories under one cell's attempt dir, other than `home`/`ws`, whose `.git` is a FILE
    starting `gitdir:` and naming `/ws/.git/worktrees/` (design section 3.1) -- a linked git
    worktree of the cell's own `ws`. A directory with no `.git` file (e.g. `home`, or any plain
    directory) is never mistaken for one (PI-T8)."""
    if not attempt_dir.is_dir():
        return []
    siblings = []
    for child in sorted(attempt_dir.iterdir()):
        if not child.is_dir() or child.name in ("home", "ws"):
            continue
        marker = child / ".git"
        if not marker.is_file():
            continue
        try:
            head = marker.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            continue
        if head.startswith("gitdir:") and _GITDIR_MARKER in head:
            siblings.append(child)
    return siblings


def worktree_left(attempt_dir: Path) -> bool:
    return bool(sibling_worktrees(attempt_dir))


def diverted_delivery(attempt_dir: Path, ws: Path, blast_radius: Sequence[str] | None) -> Measure:
    """True when a sibling worktree holds a blast-radius file missing from `ws`, or differing from
    it byte for byte (design section 4.4) -- file bytes only, never git. NA `NA_BLAST_RADIUS` when
    the blast radius could not be read (R-85 item 1)."""
    if blast_radius is None:
        return Measure(None, NA_BLAST_RADIUS)
    for sibling in sibling_worktrees(attempt_dir):
        for pattern in blast_radius:
            for candidate in sibling.glob(pattern):
                if not candidate.is_file():
                    continue
                counterpart = ws / candidate.relative_to(sibling)
                if not counterpart.is_file() or counterpart.read_bytes() != candidate.read_bytes():
                    return Measure(True)
    return Measure(False)


def diverted_and_failed(diverted: Measure, pass_at_1: int | None) -> Measure:
    if diverted.value is None:
        return Measure(None, diverted.reason)
    return Measure(bool(diverted.value) and pass_at_1 == 0)


def stopped_without_product(
    *, outcome: str, stop_reason: str | None, pass_at_1: int | None, calls: Sequence[ToolInput],
    blast_radius: Sequence[str] | None,
) -> Measure:
    """`outcome == "completed"`, `stop_reason == "end_turn"`, `pass_at_1 == 0`, and zero
    `product_write` calls in the trace, sub-agents included (design section 4.4). NA
    `NA_BLAST_RADIUS` when the blast radius could not be read (R-85 item 1's cascade). One
    `product_write` call anywhere turns this off (PI-T9)."""
    if blast_radius is None:
        return Measure(None, NA_BLAST_RADIUS)
    if not (outcome == "completed" and stop_reason == "end_turn" and pass_at_1 == 0):
        return Measure(False)
    return Measure(not any("product_write" in classify(c, blast_radius) for c in calls))


@dataclass(frozen=True)
class PackFilesWritten:
    """PK-03's own count (design section 4.4): distinct out-of-radius files under one of
    `PACK_WRITE_PATHS`, and the total lines those files' drift.log entries record (`+added` plus
    `-deleted`)."""

    files: int
    lines: int


def pack_files_written(drift_log: Path | None) -> Measure:
    """PK-03's reader (design section 4.4, deferred by S3/S4 -- "no committed drift.log fixture to
    verify against"; pinned this slice by reading `grade/drift.py`'s own writer, `_measure()`:
    `f"{status}\\t{path}\\t{'inside'/'outside'}\\t+{added} -{deleted}\\t{broken}\\n"` for a changed
    file, `f"ignored\\t{path}\\n"` for a skipped one -- confirmed byte for byte against real
    grid-1/grid-1-cc drift.log files, `tests/fixtures/pack_improvement/drift-pack-files.log`).

    `drift_log=None` is the design's own NA `NA_NO_DRIFT_GRADER` ("the evidence key is absent" --
    the caller passes None only when `CellView.evidence.get("scope_creep")` itself was absent, never
    for an I/O failure on a path the evidence dict did name). A drift.log that exists but names no
    `outside` pack-write line is a real, readable zero -- never NA."""
    if drift_log is None or not drift_log.is_file():
        return Measure(None, NA_NO_DRIFT_GRADER)
    files = lines = 0
    for raw in drift_log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _DRIFT_LINE.match(raw)
        if m is None or m.group("zone") != "outside":
            continue
        if not any(m.group("path").startswith(p) for p in PACK_WRITE_PATHS):
            continue
        files += 1
        lines += int(m.group("added")) + int(m.group("deleted"))
    return Measure(PackFilesWritten(files, lines))


# --------------------------------------------------------------------------------------------------
# Section 4.6: "same failure both arms" and "judge not recorded" (deferred by S3/S4; wired this slice,
# R-85 hand-off -- "needs oracle.log and the judge catalog's own formats").
# --------------------------------------------------------------------------------------------------


def failing_test_names(oracle_log: Path | None) -> frozenset[str] | None:
    """The failing hidden-test name set `oracle.log`'s own free text records (design section 4.6),
    read tolerantly across the two shapes the grid-1/grid-1-cc corpus actually contains (unittest's
    verbose per-test line, xUnit's `[FAIL]` line -- `tests/fixtures/pack_improvement/oracle-*.log`).
    `None` (never an empty set) when the file is absent/unreadable or the text names no failing test
    in either shape -- the caller then SKIPS the "same failure both arms" reason, never guessing
    (design 4.6: "when it cannot be read, this reason is skipped")."""
    if oracle_log is None or not oracle_log.is_file():
        return None
    try:
        text = oracle_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    names = frozenset(_UNITTEST_FAIL_NAME.findall(text)) | frozenset(_XUNIT_FAIL_NAME.findall(text))
    return names or None


def same_failure_both_arms(failing_name_sets: Sequence[frozenset[str] | None]) -> bool:
    """Design section 4.6: true only when EVERY failing cell (on and off, pooled for the task) has
    the SAME non-empty failing-test-name set. `failing_name_sets` is the caller's one entry per
    failing cell (`pass_at_1 == 0`); an empty sequence (no failing cell) or any entry that is `None`
    (unreadable) skips the reason -- never guessed true or false."""
    if not failing_name_sets or any(s is None for s in failing_name_sets):
        return False
    first = failing_name_sets[0]
    return bool(first) and all(s == first for s in failing_name_sets)


def judge_sourced_metric_ids(catalog: Mapping) -> frozenset[str]:
    """Metric ids in a loaded `bench/metrics.yaml` (`config.load_yaml`'s own shape) whose `source`
    list includes `"J"` (design section 4.6's "judge-sourced metric" -- the catalog's own oracle
    ladder, `bench/metrics.yaml:8`, never a second definition of which metrics are judged)."""
    return frozenset(
        m["id"]
        for area in (catalog.get("areas") or {}).values()
        for m in area.get("metrics") or []
        if "J" in (m.get("source") or ())
    )


def judge_not_recorded(task_graders: Sequence[str], catalog: Mapping, recorded_metric_ids: frozenset[str]) -> bool:
    """Design section 4.6: true when the task names at least one judge-sourced metric (through its
    own `graders:` list) and every one of them is absent from `recorded_metric_ids` (this task's
    recorded, non-NA score ids, pooled over its cells). A task whose graders name no judge-sourced
    metric at all never fires this -- that is a different task, not an inconclusive one."""
    judge_ids = judge_sourced_metric_ids(catalog)
    named = {
        m["id"]
        for area in (catalog.get("areas") or {}).values()
        for m in area.get("metrics") or []
        if m.get("grader") in task_graders and m["id"] in judge_ids
    }
    return bool(named) and named.isdisjoint(recorded_metric_ids)


def inconclusive_reasons(
    *, passes_on: int, passes_off: int, n_pairs: int, same_failure: bool, judge_not_recorded_: bool,
    no_mapped_metric: bool,
) -> tuple[str, ...]:
    """Design section 4.6: every reason that applies, in the design's own listed order -- a task can
    carry more than one."""
    reasons = []
    if saturated(passes_on, passes_off, n_pairs):
        reasons.append("saturated")
    if floor(passes_on, passes_off, n_pairs):
        reasons.append("floor")
    if same_failure:
        reasons.append("same failure both arms")
    if judge_not_recorded_:
        reasons.append("judge not recorded")
    if n_pairs < 3:
        reasons.append("few pairs")
    if no_mapped_metric:
        reasons.append("no mapped metric")
    return tuple(reasons)


# --------------------------------------------------------------------------------------------------
# Section 4.6 (R-85): the renamed task-level predicates. `saturated` (exclusively) and `floor` are the
# 4.6 inconclusive reasons; `ceiling_off` is 4.5's relabelled "off arm passes every pair" group flag.
# The 95%/5% band the design named is dropped (R-85): below 20 pairs per arm a percentage threshold
# cannot differ from exact equality, so these are exact comparisons, not percentages.
# --------------------------------------------------------------------------------------------------


def ceiling_off(passes_off: int, n_pairs: int) -> bool:
    """4.5's group-level relabel: the off arm passed every pair, so no gain was possible."""
    return n_pairs > 0 and passes_off == n_pairs


def saturated(passes_on: int, passes_off: int, n_pairs: int) -> bool:
    """4.6's task-level inconclusive reason: BOTH arms passed every pair."""
    return n_pairs > 0 and passes_on == n_pairs and passes_off == n_pairs


def floor(passes_on: int, passes_off: int, n_pairs: int) -> bool:
    """4.6's task-level inconclusive reason: BOTH arms passed no pair."""
    return n_pairs > 0 and passes_on == 0 and passes_off == 0


# --------------------------------------------------------------------------------------------------
# Section 4.5: value vs waste (PI-T10)
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupClassInput:
    """One (task, combo) group's decided inputs to the 4.5 rule table -- already-computed booleans
    and counts, never raw cells (the caller assembles these from `pairs()`, `median_ratio()` and the
    task's Holm-adjusted p and mapped-quality interval)."""

    passes_on: int
    passes_off: int
    n_pairs: int
    n_ratio_valid: int  # pairs with a recorded token ratio (design 4.5: "NA in every pair")
    median_token_ratio: Decimal | None
    holm_p: Decimal | None
    harm_indicator: bool  # >=1 on-cell is diverted_and_failed or stopped_without_product
    quality_lo_positive: bool  # a mapped quality metric's board interval has lo > 0 for this combo


def classify_group(g: GroupClassInput) -> tuple[str, bool]:
    """(class, ceiling_off) -- design section 4.5's rule table, first match wins (PI-T10, including
    rule order). `ceiling_off` is reported alongside the class so a `waste` class can be rendered as
    "waste (saturated task: no gain was possible)" per the design's own text, renamed per R-85."""
    is_ceiling_off = ceiling_off(g.passes_off, g.n_pairs)
    if g.n_pairs < 2 or g.n_ratio_valid == 0:
        return "inconclusive", is_ceiling_off
    if g.passes_on < g.passes_off and ((g.holm_p is not None and g.holm_p < Decimal("0.05")) or g.harm_indicator):
        return "harm", is_ceiling_off
    if (g.passes_on > g.passes_off and g.holm_p is not None and g.holm_p < Decimal("0.05")) or g.quality_lo_positive:
        return "value", is_ceiling_off
    if g.median_token_ratio is not None and g.median_token_ratio >= WASTE_RATIO:
        return "waste", is_ceiling_off
    return "neutral", is_ceiling_off


# --------------------------------------------------------------------------------------------------
# Section 5: per-intention verdicts (PI-T11)
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class VerdictInput:
    """One intention's decided evidence (design section 5) -- the caller resolves which mapped
    metrics and which behaviour indicators apply to this intention before building this."""

    metric_hi_negative: bool = False  # a mapped metric's interval has hi < 0 in the good direction
    metric_lo_positive: bool = False  # a mapped metric's interval has lo > 0 in the good direction
    harm_fired: bool = False  # a harm-type indicator fired (section 5 rule 1's list)
    on_share: Decimal | None = None  # the behaviour indicator's on-cell share (rule 3)
    off_share: Decimal | None = None
    inconclusive_reason: str = "not recorded"  # rule 4's reason, when nothing else decides


def verdict(v: VerdictInput) -> tuple[str, str | None]:
    """(verdict, reason) in section 5's rule order: miss beats hit (PI-T11: a miss indicator beats a
    hit metric), then hit, then "process only" only when BOTH the on >= 0.8 and off <= 0.2 thresholds
    hold, else inconclusive with its reason."""
    if v.metric_hi_negative or v.harm_fired:
        return "miss", None
    if v.metric_lo_positive:
        return "hit", None
    if v.on_share is not None and v.off_share is not None and v.on_share >= PROCESS_ONLY_ON and v.off_share <= PROCESS_ONLY_OFF:
        return "process only", None
    return "inconclusive", v.inconclusive_reason


# --------------------------------------------------------------------------------------------------
# Section 6: findings and ranking (PI-T12)
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One "where to improve the pack" row (design section 6). PK-08 (R-85 item 6: a watch line
    under Inconclusive, never ranked) is never constructed as a `Finding` by this module's callers --
    it renders on its own line, not through `rank_findings`."""

    code: str
    title: str
    count: int
    failed_pairs: int
    extra_tokens: int
    evidence_cell_ids: tuple[str, ...]
    pack_area: str
    confidence: str


def rank_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Deterministic ranking (design section 6): failed pairs attributed (descending), then extra
    tokens (descending), then code (ascending) -- stable under input shuffles because the full key is
    a total order (PI-T12). A finding with `count == 0` is dropped, never rendered."""
    live = [f for f in findings if f.count > 0]
    return sorted(live, key=lambda f: (-f.failed_pairs, -f.extra_tokens, f.code))
