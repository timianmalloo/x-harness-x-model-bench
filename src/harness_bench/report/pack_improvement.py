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
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

import yaml

from harness_bench import profiles
from harness_bench.board import LEGACY_PAIR, Board, _cell_task_rep, view_comparisons
from harness_bench.errors import BenchError
from harness_bench.grade.cost import ACP_MISSES_CALLS, SESSION_TOTALS
from harness_bench.plan import cell_arm
from harness_bench.stats import fisher_exact_two_sided, holm
from harness_bench.telemetry import ProcessTrace, ToolInput, claude_code, codex, copilot
from harness_bench.views import CellView, Measure, RunView, rows, sum_tokens

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
    """One pair (design section 3: pair grain) -- a (task, combo, rep) whose treatment-arm cell (`on`)
    and reference-arm cell (`off`) are BOTH `validity == "valid"`; the field names are the legacy
    pack-on and pack-off ones. A cell whose partner is invalid, ungraded, or missing forms no pair;
    it never appears half-paired."""

    task: str
    combo: str
    rep: int
    on: CellView
    off: CellView


def pairs(cells: Sequence[CellView], plan_by_id: Mapping[str, dict],
          arms: tuple[str, str] = LEGACY_PAIR) -> list[Pair]:
    """Every complete pair among `cells` for the comparison `arms` = (reference, treatment) (design
    section 3; the default is the legacy off/on pair). `plan_by_id` is `plan.json`'s
    `cells[]` keyed by cell id, the same map `board._cell_task_rep` (reused here, not copied --
    design section 3.1) reads task and rep from. Deterministic order: (task, combo, rep)."""
    by_key: dict[tuple[str, str, int], dict[str, CellView]] = {}
    for c in cells:
        if c.validity != "valid":
            continue
        task, rep, _ = _cell_task_rep(c.cell_id, plan_by_id)
        by_key.setdefault((task, c.combo, rep), {})[c.arm] = c
    result = []
    ref, treat = arms
    for (task, combo, rep), by_arm in sorted(by_key.items()):
        if treat in by_arm and ref in by_arm:
            result.append(Pair(task=task, combo=combo, rep=rep, on=by_arm[treat], off=by_arm[ref]))
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


def _relative_to_root(raw: str, root: Path | None) -> str:
    """POSIX-normalised `raw`, relative to `root` when it falls under it (design section 4.3): a
    native record's own paths are absolute -- Windows backslash or POSIX forward-slash, depending
    on harness and OS -- while blast_radius globs (`src/**`, a bare file name) are repo-relative,
    so an `fnmatch` comparison needs both sides in the same shape. Found as a real bug (not
    guessed): grid-1 native records carry absolute paths, so `src/**` never matched them and only
    a bare `**` pattern ever fired `product_write` (4 of PK-02's false positives traced to this).

    A path outside `root` (or when `root` is unknown, e.g. no attempt archive) keeps only its last
    three segments -- never a full absolute path past this module (section 8's own privacy rule);
    a path with 3 or fewer segments already (the common case for an already-relative fixture path)
    is unchanged."""
    posix = raw.replace("\\", "/")
    if root is not None:
        root_posix = root.as_posix().rstrip("/") + "/"
        if posix.startswith(root_posix):
            return posix[len(root_posix):]
    segments = [s for s in posix.split("/") if s]
    return "/".join(segments[-3:])


def _normalize_calls(calls: Sequence[ToolInput], ws: Path | None) -> tuple[ToolInput, ...]:
    """Every call's `paths`, run through `_relative_to_root(..., ws)` -- the ONE place raw native
    paths (Claude Code, Codex and Copilot's readers all leave `ToolInput.paths` exactly as their
    own native record states them, `telemetry/__init__.py::ToolInput`'s own docstring) are
    normalised before any glob match. Called once per cell (`_cell_indicators`), before
    `ceremony_share`/`test_first`/`stopped_without_product` -- every caller of `classify()` in
    production sees already-relative paths; only direct unit tests of `classify()` pass raw ones."""
    return tuple(replace(c, paths=tuple(_relative_to_root(p, ws) for p in c.paths)) for c in calls)


def _matches_blast_radius(paths: Sequence[str], blast_radius: Sequence[str]) -> bool:
    """One definition of "a relative path matches a blast-radius glob" (design section 4.4's own
    comment: `product_write` and `diverted_delivery` must use "the same matcher... for the
    identical glob syntax, one definition, not two"). `fnmatch`'s `*` matches `/` too, so `src/**`
    and `src/*` match the same set -- intentional (design section 4.4)."""
    return any(fnmatch.fnmatch(p, pat) for p in paths for pat in blast_radius)


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
    elif call.is_write and blast_radius is not None and _matches_blast_radius(call.paths, blast_radius):
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
    the blast radius could not be read (R-85 item 1).

    Matches every file under the sibling (`rglob("*")`) against `blast_radius` by `fnmatch` on its
    path relative to the sibling, POSIX-normalised -- the same matcher `classify()`'s own
    `product_write` rule uses for the identical glob syntax (`src/**`, `tests/**`, a bare file name),
    so a `**` pattern means one thing in this module, not two. `Path.glob(pattern)` per pattern (the
    S3 original) silently misses every leaf file under a `**` segment -- pathlib's `**` matches
    directories at each depth but not the files inside them without a trailing `/*` -- discovered
    against the real grid-1-cc archive (a `src/**` blast radius, S5 hand-off) where it made PK-01
    silently 0 for cells the design's own PI-T15 pins as evidence."""
    if blast_radius is None:
        return Measure(None, NA_BLAST_RADIUS)
    for sibling in sibling_worktrees(attempt_dir):
        for candidate in sibling.rglob("*"):
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(sibling).as_posix()
            if not _matches_blast_radius((rel,), blast_radius):
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


def ceiling_off(passes_off: int, n_pairs: int = 0, *, n_recorded: int | None = None) -> bool:
    """4.5's group-level relabel: the off arm passed every pair, so no gain was possible."""
    n = n_recorded if n_recorded is not None else n_pairs
    return n > 0 and passes_off == n


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
    n_recorded: int | None = None

    def __post_init__(self):
        if self.n_recorded is None:
            object.__setattr__(self, "n_recorded", self.n_pairs)


def classify_group(g: GroupClassInput) -> tuple[str, bool]:
    """(class, ceiling_off) -- design section 4.5's rule table, first match wins (PI-T10, including
    rule order). `ceiling_off` is reported alongside the class so a `waste` class can be rendered as
    "waste (saturated task: no gain was possible)" per the design's own text, renamed per R-85."""
    n_rec = g.n_recorded if g.n_recorded is not None else g.n_pairs
    is_ceiling_off = ceiling_off(g.passes_off, n_rec)
    if n_rec == 0 or g.n_pairs < 2 or g.n_ratio_valid == 0:
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
    detail: str = ""  # the human-readable waste measure (design section 6); ranking still reads only
    # failed_pairs/extra_tokens -- a finding whose natural unit is neither (PK-03's files/lines,
    # PK-05's token delta already folded into extra_tokens) carries it here for display only.


def rank_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Deterministic ranking (design section 6): failed pairs attributed (descending), then extra
    tokens (descending), then code (ascending) -- stable under input shuffles because the full key is
    a total order (PI-T12). A finding with `count == 0` is dropped, never rendered."""
    live = [f for f in findings if f.count > 0]
    return sorted(live, key=lambda f: (-f.failed_pairs, -f.extra_tokens, f.code))


# ======================================================================================================
# S5: assembly -- wires every primitive above (S3, S4) and the two readers this slice adds (4.4's
# `pack_files_written`, 4.6's `same_failure_both_arms`/`judge_not_recorded`) into one
# `PackImprovementResult` the renderer (`report/html.py::_pack_improvement`) turns into markup
# (design section 7, section 2's states table, section 11's PI-T1/T2/T14).
#
# Known, named simplification (smallest-correct ladder, not a guess): design section 5's per-intention
# `metric_lo_positive`/`metric_hi_negative` need a per-(combo, metric) bootstrap interval for every
# mapped quality metric. `board.py` computes that interval for `pass_at_1` alone (`pack_effect.rows`)
# and an area-level composite (`AreaRow`); it computes no per-metric interval for the other mapped
# metrics (honest_completion_claims, scope_creep, ...), and adding one is a `board.py` change this
# hand-off's scope excludes ("Not in scope: catalog changes; engine changes"). So `quality_lo_positive`
# is always False and every intention verdict this slice renders is decided by its own indicators alone
# (rule 3 "process only") or reads "inconclusive: not recorded: <mapped metric ids>" -- never a
# fabricated hit/miss. Findings PK-01..PK-08, which are the "Done when" bar for this slice, do not
# depend on this gap: none of them reads a quality-metric interval. ceiling: the mapped-metric verdict
# rows stay honest but never fire; upgrade trigger: `board.py` grows a per-metric interval (a `board.py`
# change, a different slice).
# ======================================================================================================

STATE_ONE_PACK = "one_pack"
STATE_NOT_GRADED = "not_graded"
STATE_NO_PAIRS = "no_pairs"
STATE_PARTIAL = "partial"
STATE_FULL = "full"

_ONE_PACK_LINE = "Not applicable: this run has one pack setting."
_NOT_GRADED_LINE = "Not graded yet: the section needs a grading pass."

PAIR_DEFINITION = (
    'One pair is exactly one (task, combo, rep) with a pack-on and a pack-off cell that are both '
    'validity == "valid" (design section 3).'
)
INFERRED_SHARE_GAP = (
    "the Inferred fixed-context share (PK-04) is modeled, not measured: no per-call record names "
    "which tokens in a call are fixed context versus task content, so the share is delta x calls "
    "divided by the run's own extra tokens, capped at 1.00 (R-85 c3)."
)
_THRESHOLD_BASIS = (
    ("WASTE_RATIO", WASTE_RATIO, "grid-1 F-7: pack-on token share 0.32 on vs 0.01 off at this ratio"),
    ("CEREMONY_SHARE_THRESHOLD", CEREMONY_SHARE_THRESHOLD, "PK-05; grid-1 F-2's ceremony-heavy cells cluster above this"),
    ("FIXED_CONTEXT_TOKENS", FIXED_CONTEXT_TOKENS, "PK-04 absolute floor; grid-1 F-2 delta +18.4k on / +9.2k off"),
    ("FIXED_CONTEXT_SHARE", FIXED_CONTEXT_SHARE, "PK-04 relative floor, the same F-2 deltas as a share of off"),
    ("PROCESS_ONLY_ON", PROCESS_ONLY_ON, "section 5 rule 3"),
    ("PROCESS_ONLY_OFF", PROCESS_ONLY_OFF, "section 5 rule 3"),
)

_TRACE_READERS = {"claude-code": claude_code, "codex": codex, "copilot": copilot}


@dataclass(frozen=True)
class GroupRow:
    """One (task, combo) row of section 7.3's value-vs-waste table."""

    task: str
    combo: str
    passes_on: int
    passes_off: int
    n_pairs: int
    median_token_ratio: Measure
    n_token_above: int
    n_token_valid: int
    median_wall_ratio: Measure
    cls: str
    is_ceiling_off: bool


@dataclass(frozen=True)
class TaskInconclusive:
    task: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Pk08Watch:
    """PK-08's own watch line (R-85 item 6: never a ranked `Finding`)."""

    mean_on: Decimal | None
    mean_off: Decimal | None
    n_on: int
    n_off: int


@dataclass(frozen=True)
class PackImprovementResult:
    state: str
    state_line: str | None
    headline: str | None
    groups: tuple[GroupRow, ...]
    findings: tuple[Finding, ...]
    pk08: Pk08Watch | None
    inconclusive: tuple[TaskInconclusive, ...]
    method_lines: tuple[str, ...]
    population_caveats: tuple[str, ...] = ()


def population_caveats(view: RunView) -> tuple[str, ...]:
    """An NA-style honesty line -- never a new metric -- for every (combo, pack) whose planned cell
    count (`plan.json`'s own `cells[]`, never re-derived) has fewer than half its cells land
    `validity == "valid"`. Verified on grid-1: `cc-opus` planned 18/18 for each arm, landed 5 valid
    off and 6 valid on -- both under half, both reported. A plan cell missing `combo`/`pack` (a
    synthetic `RunView` built directly by a test, not through `views.load`) is skipped, never
    guessed into a bucket."""
    planned: dict[tuple[str, str], int] = {}
    for c in view.plan.get("cells") or []:
        if isinstance(c, dict) and isinstance(c.get("combo"), str):
            try:
                key = (c["combo"], cell_arm(c))
            except BenchError:
                continue
            planned[key] = planned.get(key, 0) + 1
    valid: dict[tuple[str, str], int] = {}
    for c in view.cells:
        if c.validity == "valid":
            key = (c.combo, c.arm)
            valid[key] = valid.get(key, 0) + 1
    lines = []
    for key in sorted(planned):
        n_planned = planned[key]
        n_valid = valid.get(key, 0)
        if n_planned > 0 and n_valid < n_planned / 2:
            combo, pack = key
            lines.append(
                f"Population caveat: {combo} ({pack}) has {n_valid} of {n_planned} planned cells "
                f"valid -- fewer than half; its findings rest on a smaller population than planned."
            )
    return tuple(lines)


def method_lines(board_obj: Board | None) -> tuple[str, ...]:
    """Design section 7 item 6: `PACK_RULES_VERSION`, every threshold with its basis, the pair
    definition, the board's own `exclusion_line` (R-85 item 3: the same excluded-task set named
    once), and the gap that forces the fixed-context share to be Inferred (R-85 c3)."""
    lines = [f"PACK_RULES_VERSION: {PACK_RULES_VERSION}.", PAIR_DEFINITION]
    lines += [f"{name} = {value} ({basis})." for name, value, basis in _THRESHOLD_BASIS]
    lines.append(
        board_obj.pack_effect.exclusion_line if board_obj is not None
        else "Excluded as contamination-prone: not computed (no board)."
    )
    lines.append(INFERRED_SHARE_GAP)
    lines.append('p-values are exploratory at n < 10 per arm.')
    return tuple(lines)


def _attempt_dirs(run_dir: Path, cell_id: str) -> list[Path]:
    base = run_dir / "archive" / cell_id
    if not base.is_dir():
        return []
    return sorted((p for p in base.glob("attempt-*") if p.name.rsplit("-", 1)[-1].isdigit()),
                  key=lambda p: int(p.name.rsplit("-", 1)[1]))


def _cell_trace(run_dir: Path, view: RunView, cell: CellView, session_id: str | None) -> ProcessTrace | None:
    """This cell's `ProcessTrace`: the main session's `tool_inputs` composed with every sub-agent
    record's own calls, in native order (design section 4.3's own comment). The record globs come
    from the run's OWN frozen `plan.json` profile entry (`plan.py:240-245`), never a live
    `bench/profiles/*.yaml` re-read -- a profile that drifted after this run was planned must never
    change what this run's own trace reads. `None` (never a guessed empty trace) when the harness has
    no reader, the archive has no attempt, or no session id was recorded."""
    reader = _TRACE_READERS.get(cell.harness)
    profile = (view.plan.get("profiles") or {}).get(cell.harness) or {}
    if reader is None or not session_id or not profile.get("record_glob"):
        return None
    attempts = _attempt_dirs(run_dir, cell.cell_id)
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


@dataclass(frozen=True)
class _CellIndicators:
    trace: ProcessTrace | None
    ceremony_share: Measure
    goal_state_present: bool
    test_first: Measure
    git_identity_set: bool
    diverted_delivery: Measure
    diverted_and_failed: Measure
    stopped_without_product: Measure
    pack_files_written: Measure


def _cell_indicators(
    run_dir: Path, view: RunView, cell: CellView, blast_radius: Sequence[str] | None,
    outcome_event: Mapping, archive_present: bool,
) -> _CellIndicators:
    """Section 4.3/4.4's indicators for one cell (design section 9: "Missing archive: section
    4.3-4.4 indicators are NA archive not present")."""
    drift_path = (run_dir / cell.evidence["scope_creep"]) if cell.evidence.get("scope_creep") else None
    pfw = pack_files_written(drift_path)
    if not archive_present:
        na = Measure(None, NA_ARCHIVE_ABSENT)
        return _CellIndicators(None, na, False, na, False, na, na, na, pfw)
    attempts = _attempt_dirs(run_dir, cell.cell_id)
    attempt_dir = attempts[-1] if attempts else None
    ws = attempt_dir / "ws" if attempt_dir is not None else None
    session_id = outcome_event.get("session_id")
    trace = _cell_trace(run_dir, view, cell, session_id) if attempt_dir is not None else None
    record_na = Measure(None, NA_RECORD_UNREADABLE)
    if trace is None:
        ceremony, test_first_, goal_present, git_ident = record_na, record_na, False, False
        calls: tuple[ToolInput, ...] = ()
    else:
        # `_normalize_calls` is the ONE place raw native paths are relativized to `ws` before any
        # glob match; every indicator below that reads paths (through `classify()`) sees the
        # result, never the trace's own raw absolute paths.
        calls = _normalize_calls(trace.calls, ws)
        ceremony = ceremony_share(calls, blast_radius)
        test_first_ = test_first(calls, blast_radius)
        goal_present = goal_state_present(trace.first_assistant_text)
        git_ident = git_identity_set(calls)
    diverted = diverted_delivery(attempt_dir, ws, blast_radius) if attempt_dir is not None and ws is not None else Measure(None, NA_ARCHIVE_ABSENT)
    p1 = cell.scores.get("pass_at_1")
    p1_value = p1.value if p1 is not None else None
    diverted_failed = diverted_and_failed(diverted, p1_value)
    if trace is None:
        stopped = record_na if attempt_dir is not None else Measure(None, NA_ARCHIVE_ABSENT)
    else:
        stopped = stopped_without_product(
            outcome=cell.outcome, stop_reason=outcome_event.get("stop_reason"), pass_at_1=p1_value,
            calls=calls, blast_radius=blast_radius,
        )
    return _CellIndicators(trace, ceremony, goal_present, test_first_, git_ident, diverted, diverted_failed,
                            stopped, pfw)


def _blast_radius(root: Path | None, task: str) -> Sequence[str] | None:
    if root is None:
        return None
    path = root / "tasks" / task / "task.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    radius = (data or {}).get("blast_radius")
    return list(radius) if isinstance(radius, list) and radius else None


def _model_call_rows(run_dir: Path, cell: CellView) -> list[dict]:
    if cell.extraction_id is None:
        return []
    return [r for r in rows(run_dir, "model_calls")
            if r["cell_id"] == cell.cell_id and r["extraction_id"] == cell.extraction_id and r["principal"] == cell.cell_id]


def _evidence_ids(cell_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(cell_ids)[:5])


def _label(cell_ids: Sequence[str]) -> str:
    extra = len(cell_ids) - 5
    return f" and {extra} more" if extra > 0 else ""


def assemble(
    view: RunView, board_obj: Board | None, run_dir: Path | None, root: Path | None,
    archive_present: bool = False,
) -> PackImprovementResult:
    """Design section 7's whole section, assembled once per report render (design section 2's states
    table; PI-T1, T2, T14)."""
    packs = {c.arm for c in view.cells}
    if len(packs) < 2:
        return PackImprovementResult(STATE_ONE_PACK, _ONE_PACK_LINE, None, (), (), None, (), method_lines(board_obj))
    if view.grading_id is None:
        return PackImprovementResult(STATE_NOT_GRADED, _NOT_GRADED_LINE, None, (), (), None, (), method_lines(board_obj))

    plan_by_id = {c["cell_id"]: c for c in (view.plan.get("cells") or []) if isinstance(c, dict) and "cell_id" in c}
    comparisons = view_comparisons(view, sorted(packs))
    ref, treat = comparisons[0] if comparisons else LEGACY_PAIR
    all_pairs = pairs(view.cells, plan_by_id, (ref, treat))
    if not all_pairs:
        n_valid = sum(1 for c in view.cells if c.validity == "valid")
        line = f"No complete pairs: every pair has an invalid or ungraded arm ({n_valid} of {len(view.cells)} cells valid)."
        return PackImprovementResult(STATE_NO_PAIRS, line, None, (), (), None, (), method_lines(board_obj))

    combo_packs: dict[str, set[str]] = {}
    for c in view.cells:
        combo_packs.setdefault(c.combo, set()).add(c.arm)
    partial = any(len(p) < 2 for p in combo_packs.values())
    state = STATE_PARTIAL if partial else STATE_FULL

    if run_dir is None:
        archive_present = False

    excluded_tasks = set(board_obj.pack_effect.excluded_tasks) if board_obj is not None else set()
    outcome_by_cell: dict[str, dict] = {}
    if run_dir is not None:
        for e in rows(run_dir, "events"):
            if e.get("kind") == "cell.outcome":
                outcome_by_cell[e.get("cell_id")] = e

    # Indicators are computed over every VALID cell, never only cells that landed in a complete pair
    # (design section 4.4's indicators are per-cell facts; section 3's stricter pair grain governs
    # 4.1/4.2/4.5 alone). A cell whose partner turned out invalid is still a real diverted/stopped
    # fact -- excluding it would silently drop PK-01/02/03/07 evidence the design's own PI-T15 pins
    # (real grid-1-cc regression, S5 hand-off: F1's cc-opus r1/r3 on-cells are diverted_and_failed
    # with an invalid off partner).
    valid_cells = {c.cell_id: c for c in view.cells if c.validity == "valid"}
    task_of = {cid: plan_by_id.get(cid, {}).get("task") for cid in valid_cells}
    blast_by_task = {t: _blast_radius(root, t) for t in {t for t in task_of.values() if t}}

    indicators: dict[str, _CellIndicators] = {}
    if run_dir is not None:
        for cid, cell in valid_cells.items():
            indicators[cid] = _cell_indicators(
                run_dir, view, cell, blast_by_task.get(task_of.get(cid)), outcome_by_cell.get(cid, {}), archive_present,
            )

    # ---- 4.1 quality: per-task Fisher, Holm, pooled (one population, R-85 item 3) ----
    by_task: dict[str, list] = {}
    for p in all_pairs:
        if p.task not in excluded_tasks:
            by_task.setdefault(p.task, []).append(p)
    task_ps: dict[str, Decimal] = {}
    task_counts: dict[str, tuple[int, int, int]] = {}
    tasks_with_no_recorded: dict[str, str] = {}
    for task, task_pairs in by_task.items():
        recorded = [p for p in task_pairs if _pass(p.on) is not None and _pass(p.off) is not None]
        if not recorded:
            na_reasons = [
                c.scores["pass_at_1"].reason
                for p in task_pairs
                for c in (p.on, p.off)
                if c.scores.get("pass_at_1") is not None and c.scores["pass_at_1"].reason
            ]
            tasks_with_no_recorded[task] = na_reasons[0] if na_reasons else "not recorded"
            continue
        passes_on = sum(1 for p in recorded if _pass(p.on) is True)
        passes_off = sum(1 for p in recorded if _pass(p.off) is True)
        n = len(recorded)
        task_counts[task] = (passes_on, passes_off, n)
        task_ps[task] = fisher_exact_two_sided(passes_on, n - passes_on, passes_off, n - passes_off)
    holm_ps = holm(task_ps) if task_ps else {}

    # ---- groups: one (task, combo) row each ----
    by_group: dict[tuple[str, str], list] = {}
    for p in all_pairs:
        by_group.setdefault((p.task, p.combo), []).append(p)

    # ---- indicator-driven findings scan every VALID on/off cell directly (never only paired ones --
    # see the `indicators` comment above: a cell's partner turning out invalid must not hide a real
    # diverted/stopped/git-identity/pack-file fact). `by_trc` finds an on-cell's own off PARTNER by
    # (task, combo, rep) regardless of the partner's validity, for PK-03's escalation clause, which
    # names "its pair's off-cell" -- a relationship pairing() itself does not keep once a partner is
    # invalid.
    by_trc: dict[tuple[str, str, int], dict[str, CellView]] = {}
    for c in view.cells:
        rec = plan_by_id.get(c.cell_id, {})
        t = rec.get("task")
        if t is None or "rep" not in rec:
            continue
        by_trc.setdefault((t, c.combo, rec["rep"]), {})[c.arm] = c

    on_diverted_failed: list[str] = []
    on_stopped: list[str] = []
    on_git_ids, off_git_ids = [], []
    on_pack_files, off_pack_files = [], []
    escalated_pack_files = False
    for cid, ind in indicators.items():
        cell = valid_cells[cid]
        if cell.arm != treat:
            if cell.arm != ref:
                continue
            if ind.git_identity_set:
                off_git_ids.append(cid)
            off_files = ind.pack_files_written.value
            if isinstance(off_files, PackFilesWritten) and off_files.files > 0:
                off_pack_files.append((cid, off_files))
            continue
        if ind.diverted_and_failed.value is True:
            on_diverted_failed.append(cid)
        if ind.stopped_without_product.value is True:
            on_stopped.append(cid)
        if ind.git_identity_set:
            on_git_ids.append(cid)
        on_files = ind.pack_files_written.value
        if isinstance(on_files, PackFilesWritten) and on_files.files > 0:
            on_pack_files.append((cid, on_files))
            rec = plan_by_id.get(cid, {})
            partner = by_trc.get((rec.get("task"), cell.combo, rec.get("rep")), {}).get(ref)
            reg_on = cell.scores.get("regression_count")
            reg_off = partner.scores.get("regression_count") if partner is not None else None
            if (reg_on is not None and reg_on.value and reg_on.value > 0
                    and reg_off is not None and reg_off.value == 0):
                escalated_pack_files = True

    groups: list[GroupRow] = []
    findings: list[Finding] = []
    harm_groups_without_cause = 0
    harm_groups_failed_pairs = 0

    for (task, combo), group_pairs in sorted(by_group.items()):
        recorded = [p for p in group_pairs if _pass(p.on) is not None and _pass(p.off) is not None]
        n_recorded = len(recorded)
        passes_on = sum(1 for p in recorded if _pass(p.on) is True)
        passes_off = sum(1 for p in recorded if _pass(p.off) is True)
        n_pairs = len(group_pairs)
        token_ratios = [tokens_ratio(p) for p in group_pairs]
        median_tok, above_tok, n_tok = median_ratio(token_ratios)
        wall_ratios = [_measure_ratio(p.on.wall_ms, p.off.wall_ms) for p in group_pairs]
        median_wall, _, _ = median_ratio(wall_ratios)

        harm_indicator = any(
            (ind := indicators.get(p.on.cell_id)) is not None
            and (ind.diverted_and_failed.value is True or ind.stopped_without_product.value is True)
            for p in group_pairs
        )
        gi = GroupClassInput(
            passes_on=passes_on, passes_off=passes_off, n_pairs=n_pairs, n_ratio_valid=n_tok,
            median_token_ratio=median_tok.value, holm_p=holm_ps.get(task), harm_indicator=harm_indicator,
            quality_lo_positive=False,  # named simplification, module docstring above
            n_recorded=n_recorded,
        )
        cls, is_ceiling_off = classify_group(gi)
        groups.append(GroupRow(task, combo, passes_on, passes_off, n_pairs, median_tok, above_tok, n_tok,
                                median_wall, cls, is_ceiling_off))

        if cls == "harm":
            has_named_cause = any(
                p.on.cell_id in on_diverted_failed or p.on.cell_id in on_stopped for p in group_pairs
            )
            if not has_named_cause:
                harm_groups_without_cause += 1
                harm_groups_failed_pairs += max(0, n_recorded - passes_on)

    # ---- PK-01 / PK-02 ----
    if on_diverted_failed:
        findings.append(Finding("PK-01", "Diverted delivery", len(on_diverted_failed), len(on_diverted_failed), 0,
                                 _evidence_ids(on_diverted_failed), "session-worktree discipline (WT1)", "Verified",
                                 detail=f"{len(on_diverted_failed)} failed pairs{_label(on_diverted_failed)}"))
    if on_stopped:
        findings.append(Finding("PK-02", "Turn ended before product", len(on_stopped), len(on_stopped), 0,
                                 _evidence_ids(on_stopped), "turn close (CT), coordination preconditions", "Verified",
                                 detail=f"{len(on_stopped)} failed pairs{_label(on_stopped)}"))

    # ---- PK-03 ----
    pk03_count = max(0, len(on_pack_files) - len(off_pack_files))
    if pk03_count > 0:
        files = sum(f.files for _, f in on_pack_files)
        lines_ = sum(f.lines for _, f in on_pack_files)
        title = "Pack files in the product tree" + (" (escalated: a regression with a clean off arm)" if escalated_pack_files else "")
        findings.append(Finding("PK-03", title, pk03_count, 0, 0,
                                 _evidence_ids([cid for cid, _ in on_pack_files]),
                                 "audit & change log mandate", "Verified",
                                 detail=f"{files} files, {lines_} lines"))

    # ---- PK-04: fixed context overhead, per harness ----
    by_harness: dict[str, list] = {}
    for p in all_pairs:
        by_harness.setdefault(p.on.harness, []).append(p)
    pk04_cells: list[str] = []
    pk04_tokens = 0
    for harness, hp in by_harness.items():
        profile = (view.plan.get("profiles") or {}).get(harness) or {}
        aux = tuple(profile.get("auxiliary_models") or ())
        usage_source = profile.get("usage_source", "native_record")
        on_firsts = [first_call_input(usage_source=usage_source, harness=harness, auxiliary_models=aux,
                                       model_call_rows=_model_call_rows(run_dir, p.on)) for p in hp] if run_dir else []
        off_firsts = [first_call_input(usage_source=usage_source, harness=harness, auxiliary_models=aux,
                                        model_call_rows=_model_call_rows(run_dir, p.off)) for p in hp] if run_dir else []
        on_vals = sorted(m.value for m in on_firsts if m.value is not None)
        off_vals = sorted(m.value for m in off_firsts if m.value is not None)
        if not on_vals or not off_vals:
            continue
        med_on_v = on_vals[len(on_vals) // 2]
        med_off_v = off_vals[len(off_vals) // 2]
        delta = med_on_v - med_off_v
        if delta >= FIXED_CONTEXT_TOKENS or (med_off_v > 0 and delta / med_off_v >= FIXED_CONTEXT_SHARE):
            calls_on_sum = sum(len(_model_call_rows(run_dir, p.on)) for p in hp) if run_dir else 0
            pk04_tokens += int(delta * calls_on_sum)
            pk04_cells.extend(p.on.cell_id for p in hp)
    if pk04_cells:
        findings.append(Finding("PK-04", "Fixed context overhead", len(by_harness), 0, pk04_tokens,
                                 _evidence_ids(pk04_cells), 'always-loaded files (AGENTS.md, applyTo: "**")',
                                 "Verified delta, Inferred share", detail=f"{pk04_tokens} tokens (modeled)"))

    # ---- PK-05: ceremony on ceiling_off tasks ----
    pk05_cells, pk05_tokens = [], 0
    for g, group_pairs in zip(groups, (by_group[(g.task, g.combo)] for g in groups), strict=True):
        if not g.is_ceiling_off or g.median_token_ratio.value is None or g.median_token_ratio.value < Decimal("1.5"):
            continue
        shares = [indicators[p.on.cell_id].ceremony_share for p in group_pairs if p.on.cell_id in indicators]
        on_shares = [s.value for s in shares if s.value is not None]
        if not on_shares or (sum(on_shares) / len(on_shares)) < CEREMONY_SHARE_THRESHOLD:
            continue
        pk05_cells.extend(p.on.cell_id for p in group_pairs)
        for p in group_pairs:
            on_t, off_t = sum_tokens(p.on.tokens), sum_tokens(p.off.tokens)
            if on_t is not None and off_t is not None:
                pk05_tokens += max(0, on_t - off_t)
    if pk05_cells:
        findings.append(Finding("PK-05", "Ceremony on tasks with no room to improve (ceiling_off)", len(pk05_cells),
                                 0, pk05_tokens, _evidence_ids(pk05_cells), "tiering (T0 means no pack reads)",
                                 "Verified", detail=f"{pk05_tokens} extra tokens"))

    # ---- PK-06: harm without a named cause ----
    if harm_groups_without_cause:
        harm_cells = [p.on.cell_id for g in groups if g.cls == "harm" for p in by_group[(g.task, g.combo)]
                      if p.on.cell_id not in on_diverted_failed and p.on.cell_id not in on_stopped]
        findings.append(Finding("PK-06", "Quality harm without a named cause", harm_groups_without_cause,
                                 harm_groups_failed_pairs, 0, _evidence_ids(harm_cells), "investigate (transcripts)",
                                 "Verified count", detail=f"{harm_groups_failed_pairs} failed pairs"))

    # ---- PK-07: git identity set ----
    pk07_count = max(0, len(on_git_ids) - len(off_git_ids))
    if pk07_count > 0:
        findings.append(Finding("PK-07", "Git identity set by the agent", pk07_count, 0, 0,
                                 _evidence_ids(on_git_ids), "commit discipline", "Verified",
                                 detail=f"{len(on_git_ids)} cells"))

    ranked = tuple(rank_findings(findings))

    # ---- PK-08: watch line (R-85 item 6: never ranked) ----
    pk08 = _pk08_watch(all_pairs, plan_by_id)

    # ---- inconclusive reasons per task ----
    catalog = _load_catalog(root)
    inconclusive: list[TaskInconclusive] = []
    for task, reason in sorted(tasks_with_no_recorded.items()):
        inconclusive.append(TaskInconclusive(task, (f"pass_at_1 not recorded: {reason}",)))
    for task, (passes_on, passes_off, n) in sorted(task_counts.items()):
        task_pairs = by_task[task]
        failing_sets = [
            failing_test_names(run_dir / p.on.evidence["pass_at_1"]) if run_dir and p.on.evidence.get("pass_at_1") else None
            for p in task_pairs if _pass(p.on) is False
        ] + [
            failing_test_names(run_dir / p.off.evidence["pass_at_1"]) if run_dir and p.off.evidence.get("pass_at_1") else None
            for p in task_pairs if _pass(p.off) is False
        ]
        same_fail = same_failure_both_arms(failing_sets)
        graders = _task_graders(root, task)
        recorded = frozenset(
            mid for p in task_pairs for c in (p.on, p.off) for mid, m in c.scores.items() if m.value is not None
        )
        judge_na = judge_not_recorded(graders, catalog, recorded) if catalog else False
        reasons = inconclusive_reasons(passes_on=passes_on, passes_off=passes_off, n_pairs=n, same_failure=same_fail,
                                        judge_not_recorded_=judge_na, no_mapped_metric=False)
        if reasons:
            inconclusive.append(TaskInconclusive(task, reasons))

    headline = _headline(all_pairs, (ref, treat), task_counts, valid_cells, on_diverted_failed, on_stopped)
    return PackImprovementResult(state, None, headline, tuple(groups), ranked, pk08, tuple(inconclusive),
                                  method_lines(board_obj), population_caveats(view))


def _pass(c: CellView) -> bool | None:
    s = c.scores.get("pass_at_1")
    if s is None or s.value is None:
        return None
    if s.value == 1:
        return True
    if s.value == 0:
        return False
    return None


def _passed(c: CellView) -> bool:
    return _pass(c) is True


def _measure_ratio(on: Measure, off: Measure) -> Measure:
    if on.value is None:
        return Measure(None, on.reason or "not recorded")
    if off.value is None:
        return Measure(None, off.reason or "not recorded")
    if off.value == 0:
        return Measure(None, "off arm value is 0")
    with localcontext(_CONTEXT):
        return Measure(Decimal(on.value) / Decimal(off.value))


def _pk08_watch(all_pairs: Sequence, plan_by_id: Mapping[str, dict]) -> Pk08Watch | None:
    on_vals, off_vals = [], []
    for p in all_pairs:
        scenario = p.on.scenario
        if scenario != 1:
            continue
        on_m = p.on.scores.get("ask_vs_assume")
        off_m = p.off.scores.get("ask_vs_assume")
        if on_m is not None and on_m.value is not None:
            on_vals.append(Decimal(str(on_m.value)))
        if off_m is not None and off_m.value is not None:
            off_vals.append(Decimal(str(off_m.value)))
    if not on_vals and not off_vals:
        return None
    with localcontext(_CONTEXT):
        mean_on = sum(on_vals, Decimal(0)) / Decimal(len(on_vals)) if on_vals else None
        mean_off = sum(off_vals, Decimal(0)) / Decimal(len(off_vals)) if off_vals else None
    return Pk08Watch(mean_on, mean_off, len(on_vals), len(off_vals))


def _load_catalog(root: Path | None) -> Mapping | None:
    if root is None:
        return None
    path = root / "bench" / "metrics.yaml"
    if not path.is_file():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _task_graders(root: Path | None, task: str) -> list[str]:
    if root is None:
        return []
    path = root / "tasks" / task / "task.yaml"
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    return list((data or {}).get("graders") or [])


def _headline(all_pairs: Sequence, arms: tuple[str, str], task_counts: Mapping[str, tuple[int, int, int]],
              valid_cells: Mapping[str, CellView], on_diverted_failed: Sequence[str],
              on_stopped: Sequence[str]) -> str:
    ref, treat = arms
    tok_on = sum(v for p in all_pairs if (v := sum_tokens(p.on.tokens)) is not None)
    tok_off = sum(v for p in all_pairs if (v := sum_tokens(p.off.tokens)) is not None)
    wall_on = sum(v.value for p in all_pairs if (v := p.on.wall_ms).value is not None)
    wall_off = sum(v.value for p in all_pairs if (v := p.off.wall_ms).value is not None)
    passes_on = sum(c[0] for c in task_counts.values())
    passes_off = sum(c[1] for c in task_counts.values())
    n = sum(c[2] for c in task_counts.values())
    a, b = passes_on, n - passes_on
    c_, d = passes_off, n - passes_off
    pooled_p = fisher_exact_two_sided(a, b, c_, d) if n else None
    tok_text = f"{Decimal(tok_on) / Decimal(tok_off):.1f}x the tokens" if tok_off else "an unmeasured share of the tokens"
    wall_text = f"{Decimal(wall_on) / Decimal(wall_off):.1f}x the wall clock" if wall_off else "an unmeasured share of the wall clock"
    # Population parity (a real defect caught while wiring this slice): `attributed` is scanned over
    # EVERY valid on-cell (indicators are per-cell, not per-pair -- the `indicators` comment above),
    # so `on_failures` must be the same population, never only the on-cells that happened to land in
    # a complete pair -- an "N of M" with M < N is nonsense, not a rounding quirk.
    attributed = len(set(on_diverted_failed) | set(on_stopped))
    on_failures = 0
    k_on = 0
    k_off = 0
    for c in valid_cells.values():
        p = _pass(c)
        if c.arm == treat:
            if p is False:
                on_failures += 1
            elif p is None:
                k_on += 1
        elif c.arm == ref and p is None:
            k_off += 1
    not_recorded_text = f", {k_on} pack-{treat} and {k_off} pack-{ref} cells not recorded" if (k_on > 0 or k_off > 0) else ""
    p_text = f"pooled p = {pooled_p:.2f}" if pooled_p is not None else "pooled p not computed"
    return (f"Pack {treat} used {tok_text} and {wall_text}; pass {passes_on}/{n} vs {passes_off}/{n} ({p_text}); "
            f"{attributed} of {on_failures} pack-{treat} failures have a pack-attributed cause{not_recorded_text}.")
