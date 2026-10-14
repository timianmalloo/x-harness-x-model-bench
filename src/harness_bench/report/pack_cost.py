"""`bench report --pack-cost` (ADR-0029): where the AI-Forward pack's tokens go, for the pack owner.

`build(views) -> PackCost` defines no derivation of its own: the per-request input series and compactions come from
`context_growth.request_series`, the carry until compaction from `tool_phases.carry_until_compaction` (ADR-0026 s4,
one definition each), the pairing from `verdicts.collect` (the lean pairing) and the outcome from `lean.build`. Pack-on
and pack-off cells pair by (harness, task, batch); every figure is per harness, a per-pair median with its range, never
pooled. Each pair's terms sum exactly to its delta: the residual is the delta minus the recorded terms, shown, never
spread. Each harness row carries its `transport` (Ruling 120). Tokens only: no price (Ruling 115).

The decomposition of one pair (ADR-0029 s3), with `tpc` the pack-on cell's own tokens per character (its first
request's input tokens over its prefix characters, the prefix being every `inlined` or `listed` prompt part):

- fixed prefix: per prompt part, (on chars - off chars) x the pack-on cell's requests x tpc. Inferred. A part with no
  character count leaves the prefix not recorded, with one exception: the same kind with an identical fingerprint in
  both cells of the pair is an exact zero delta (`_identical`; the page says so).
- extra requests: (on requests - off requests) x the pack-off cell's median per-request input. Verified counts.
- pack reads: each pack-on tool call (not a write, not a skill load) naming a pack file: its bytes returned x tpc,
  entering at the next request and carried until a compaction. Inferred.
- skill loads: each skill tool call, the same way. Inferred.
- hooks: counts and time from `harness_events`; their tokens are not recorded (no hook output size in the record).
- reasoning and output: the delta of the output buckets (reasoning is a component of output). Verified.

The pack's files are the pack-on base tree minus the pack-off base tree (`CellFacts.base_tree`); each is classed by its
path and its frontmatter, read through `gitsafe` from the pack source and commit the plan's `arms` block records.
"""

from __future__ import annotations

import argparse
import bisect
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from harness_bench import archive, gitsafe, lean, stats, verdicts, views
from harness_bench import plan as plan_mod
from harness_bench.errors import BenchError
from harness_bench.report import context_growth, model, tool_phases
from harness_bench.report.html_builder import Html, el
from harness_bench.telemetry import HarnessEvent, PromptPart, ToolInput
from harness_bench.views import CellView, Measure, RunView

# ADR-0029 s3: the decomposition of the pack-on minus pack-off token delta per pair; `residual` is shown, never spread.
TERMS = ("fixed_prefix", "extra_requests", "pack_reads", "skill_loads", "hooks", "reasoning_output", "residual")
# ADR-0029 s4: the class of a pack file, by its path and frontmatter; `unclassified` when the pack source is not read.
COMPONENTS = ("always_applied_instruction", "scoped_instruction", "agents_md", "skill", "persona", "hook",
              "knowledge_doc", "other", "unclassified")

# ADR-0029 s5: the tuning rules' thresholds, shown on the page. A rule fires at its threshold or above.
ALWAYS_APPLIED_SHARE = Decimal("0.10")  # an inlined always-applied file's tokens per cell, of pack-on tokens per cell
ON_DEMAND_CELL_SHARE = Decimal("0.50")  # the share of pack-on cells that read one knowledge doc on demand
HOOK_WALL_SHARE = Decimal("0.20")  # hook time per cell, of the pack-on cell's wall clock
SKILL_CATALOGUE_SHARE = Decimal("0.05")  # the skill catalogue's tokens per cell, of pack-on tokens per cell
TOP_FILES = 15  # files per harness in the top-files table
THRESHOLDS = {
    "ALWAYS_APPLIED_SHARE": (ALWAYS_APPLIED_SHARE, ("an always-applied instruction file inlined on every request: its "
                             "attributed tokens per cell, as a share of pack-on tokens per cell")),
    "ON_DEMAND_CELL_SHARE": (ON_DEMAND_CELL_SHARE, ("a knowledge doc read on demand: the share of pack-on cells that "
                             "read it")),
    "HOOK_WALL_SHARE": (HOOK_WALL_SHARE, "hook time per pack-on cell, as a share of that cell's wall clock"),
    "SKILL_CATALOGUE_SHARE": (SKILL_CATALOGUE_SHARE, ("the skill catalogue sent on every request: its tokens per cell, "
                              "as a share of pack-on tokens per cell")),
    "TOP_FILES": (TOP_FILES, "files per harness in the top-files table"),
}

TPC = "Inferred (tokens per character)"
LABELS = {
    "fixed_prefix": f"{TPC}: the change in prefix characters x the pack-on cell's requests x its first-request "
                    "tokens per character",
    "extra_requests": "Verified counts; Inferred per-request base (the pack-off cell's median request input)",
    "pack_reads": f"{TPC}: bytes returned by tool calls naming a pack file, carried until a compaction",
    "skill_loads": f"{TPC}: bytes returned by skill tool calls, carried until a compaction",
    "hooks": "Verified counts and time; tokens not recorded",
    "reasoning_output": "Verified: the change in output tokens (reasoning is a component of output)",
    "residual": "Verified: the delta minus the recorded terms; shown, never spread",
}
HOOK_TOKENS = "not recorded: hook output size is not in the record"
IDENTICAL_FINGERPRINT = "tool catalogue identical in both arms (fingerprint equal): delta 0"
NO_RUN_DIR = "not recorded: the run directory is not known to pack_cost"
UNREADABLE = "not recorded: pack source not readable"
NO_PACK = "not recorded: the plan binds no pack"
SKILL_TOOLS = frozenset({"skill"})  # lower-cased tool names that load a skill (Claude Code's `Skill`)
DEFAULT_OUT = Path("docs") / "coordination" / "ai-forward-pack-cost.html"
TITLE = "Where the AI-Forward pack's tokens go"
GIT_TIMEOUT = 60


@dataclass(frozen=True)
class Term:
    """One decomposition term for one harness: the per-pair median with its range, and its label (Verified, Inferred,
    or a `not recorded` reason; ADR-0029 s3's label column)."""
    name: str  # one of TERMS
    median: Measure
    low: Measure
    high: Measure
    label: str


@dataclass(frozen=True)
class HarnessDecomposition:
    harness: str
    transport: str  # a plan fact (tool_phases.TRANSPORTS)
    pairs: int
    delta_total: Measure
    terms: tuple[Term, ...]  # in TERMS order


@dataclass(frozen=True)
class PackFile:
    """One file of the pack: the pack-on base tree minus the pack-off base tree, for the bound pack revision."""
    path: str
    component: str  # one of COMPONENTS


@dataclass(frozen=True)
class ComponentCost:
    component: str
    harness: str
    tokens_per_cell: Measure


@dataclass(frozen=True)
class TopFile:
    path: str
    component: str
    harness: str
    tokens_per_cell: Measure
    requests_carried: Measure
    delivery: str  # telemetry.DELIVERIES


@dataclass(frozen=True)
class Candidate:
    """A rule-based tuning candidate with its figure; it never claims an effect it did not measure (ADR-0029 s5)."""
    rule: str
    harness: str
    figure: str
    threshold: str  # the module constant it crossed, shown on the page
    lever: str


@dataclass(frozen=True)
class PairRow:
    """One pair's exact decomposition: `terms` in TERMS order, summing with the residual to `delta_total`."""
    harness: str
    run_id: str
    task: str
    rep: int
    delta_total: Measure
    terms: tuple[Measure, ...]


@dataclass(frozen=True)
class Outcome:
    """The lean summary's pack effect on `property_check_pass` for one combo (ADR-0029 s6), repeated, never recomputed."""
    harness: str
    combo: str
    statement: str
    effect: Decimal | None
    lo: Decimal | None
    hi: Decimal | None
    mde: Decimal
    pairs: int


@dataclass(frozen=True)
class PackCost:
    runs: tuple[str, ...]
    pack_source: str  # e.g. `C:/Projects/ai-forward@<sha>`, from the plan's `arms` block
    pack_source_reason: str | None  # `not recorded: pack source not readable`, or None
    harnesses: tuple[HarnessDecomposition, ...]
    components: tuple[PackFile, ...]
    component_costs: tuple[ComponentCost, ...]
    top_files: tuple[TopFile, ...]
    candidates: tuple[Candidate, ...]
    thresholds: Mapping[str, str]
    pairs: tuple[PairRow, ...] = ()
    outcomes: tuple[Outcome, ...] = ()
    outcome_reason: str | None = None
    transports: Mapping[str, str] = field(default_factory=dict)  # harness -> transport, for every harness row


# --- the seams: the per-cell facts and the pack source ---------------------------------------------------------------

@dataclass(frozen=True)
class CellFacts:
    """One cell's reader facts (ADR-0026 s1), each a tuple or its `not recorded` reason."""
    model_ordinals: tuple[int, ...] | str  # the native ordinals of the cell's own requests, native order
    prompt_parts: tuple[PromptPart, ...] | str
    tool_inputs: tuple[ToolInput, ...] | str
    harness_events: tuple[HarnessEvent, ...] | str
    base_tree: frozenset[str] | str  # the paths of the cell's pre-turn tree


@dataclass(frozen=True)
class PackSource:
    label: str  # `<source>@<commit>`, or `not recorded`
    reason: str | None
    read: Callable[[str], str | None]  # a pack file's text at the commit; None when the source has no such path


def load_views(args) -> list[RunView]:
    """The views of `args.pack_cost`, from `--runs` (default `<root>/runs`), in the order named. Each view carries
    its own run directory and rows (`RunView.run_dir`, `RunView.facts`), so nothing is registered here."""
    runs = Path(args.runs) if getattr(args, "runs", None) else Path(args.root) / "runs"
    return [views.load(runs / run_id) for run_id in args.pack_cost]


def _base_tree(run_dir: Path, view: RunView, cell: CellView) -> frozenset[str] | str:
    # grade imports report: imported when a real cell is read
    from harness_bench.grade import _changes

    attempts = archive.attempt_dirs(run_dir, cell.cell_id)
    ws = attempts[-1] / "ws" if attempts else None
    plan_cell = next((c for c in view.plan.get("cells", []) if c.get("cell_id") == cell.cell_id), None)
    if ws is None or plan_cell is None:
        return "not recorded: no archived working copy"
    commit = _changes.pre_turn_commit(ws, plan_cell, GIT_TIMEOUT)
    if commit is None:
        return f"not recorded: {_changes.NOT_FOUND}"
    done = gitsafe.git(["ls-tree", "-r", "--name-only", commit], cwd=ws, timeout=GIT_TIMEOUT, check=False)
    if done.timed_out or done.returncode != 0:
        return "not recorded: the pre-turn tree is not readable"
    return frozenset(done.stdout.splitlines())


def cell_facts(view: RunView, cell: CellView) -> CellFacts:
    """The real reader, through the view alone (J2-FIX item 2: the one accessor, `views.cell_rows` over
    `RunView.facts`, with `RunView.run_dir` for the archive): the cell's current-extraction main-session
    `model_calls`, its `prompt_parts` and `harness_events` rows, its tool inputs from its archived native record
    (`tool_phases.cell_trace`), and its pre-turn tree."""
    run_dir = view.run_dir
    if run_dir is None:
        return CellFacts(NO_RUN_DIR, NO_RUN_DIR, NO_RUN_DIR, NO_RUN_DIR, NO_RUN_DIR)
    if cell.extraction_id is None:
        return CellFacts(*(["not recorded: not graded"] * 5))
    session = tool_phases.main_session(view, cell)
    calls = sorted((r for r in views.cell_rows(view, "model_calls", cell) if r.get("principal") == cell.cell_id
                    and (session is None or r.get("native_session_id") == session)), key=lambda r: r["native_ordinal"])
    ordinals = tuple(r["native_ordinal"] for r in calls) or "not recorded: no model_calls rows"
    parts = tuple(PromptPart(r["native_ordinal"], r["part"], r.get("path"), r.get("chars"), r["delivery"], r["source"],
                       r.get("tokens"))
                  for r in sorted(views.cell_rows(view, "prompt_parts", cell), key=lambda r: r["native_ordinal"])) \
        or "not recorded: no prompt_parts rows"
    events = tuple(HarnessEvent(r["native_ordinal"], r["event"], r.get("name"), r.get("start"), r.get("end"),
                                r.get("ok"), r.get("detail"))
                   for r in views.cell_rows(view, "harness_events", cell)) or "not recorded: no harness_events rows"
    trace = tool_phases.cell_trace(run_dir, view, cell, session)
    tools = trace.calls if trace is not None else "not recorded: the native record is not readable"
    return CellFacts(ordinals, parts, tools, events, _base_tree(run_dir, view, cell))


def pack_source(plan: dict) -> PackSource:
    """The pack-on arm's source and commit (a plan fact), read through `gitsafe`; unreadable gives the reason.

    assume: each installed pack file sits at the same path in the pack source (the ai-forward repository carries its
    own consumer layout, e.g. `.github/instructions/*.instructions.md`, Verified by `git ls-tree` at 4a22f12). Confirm:
    a pack-on base-tree path that `git show` finds at the commit. Breaks if false: that file is classed by its path
    alone, and an instruction file with no readable frontmatter is `unclassified`."""
    pack = next((p for p in plan_mod.plan_packs(plan).values() if p), None)
    if pack is None:
        return PackSource("not recorded", NO_PACK, lambda _: None)
    source, commit = Path(str(pack["source"])), str(pack["commit"])
    label = f"{pack['source']}@{commit}"
    if not source.is_dir():  # git would not start in a missing folder
        return PackSource(label, UNREADABLE, lambda _: None)
    try:
        gitsafe.git(["cat-file", "-e", f"{commit}^{{commit}}"], cwd=source, timeout=GIT_TIMEOUT)
    except (gitsafe.GitError, OSError):
        return PackSource(label, UNREADABLE, lambda _: None)

    def read(path: str) -> str | None:
        done = gitsafe.git(["show", f"{commit}:{path}"], cwd=source, timeout=GIT_TIMEOUT, check=False)
        return done.stdout if not done.timed_out and done.returncode == 0 else None
    return PackSource(label, None, read)


def _apply_to(text: str) -> str | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        key, _, value = line.partition(":")
        if key.strip() == "applyTo":
            return value.strip().strip("'\"")
    return None


def classify(path: str, text: str | None) -> str:
    """One pack file's component (ADR-0029 s4), by its frontmatter first, then its path."""
    p = path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    if p.endswith(".instructions.md"):
        if text is None:
            return "unclassified"
        scope = _apply_to(text)
        if scope == "**":
            return "always_applied_instruction"
        return "scoped_instruction" if scope else "knowledge_doc"
    if name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "copilot-instructions.md"):
        return "agents_md"
    if "/skills/" in f"/{p}":
        return "skill"
    if "/agents/" in f"/{p}" and p.endswith(".md"):
        return "persona"
    if "/hooks/" in f"/{p}":
        return "hook"
    if "/knowledge/" in f"/{p}" and p.endswith(".md"):
        return "knowledge_doc"
    return "other"


def _pseudo(path: str) -> str:
    """The component of an attribution with no pack file behind it: a prompt part sent without a path (`(<part>
    part)`) or a skill tool call; the skill catalogue is a skill cost, everything else `other`."""
    return "skill" if path in ("(skills part)", "(skill tool call)") else "other"


# --- one pair ------------------------------------------------------------------------------------------------------

def _int(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _out(cell: CellView) -> int | None:
    if cell.tokens is None:
        return None
    return sum(b.get("output", 0) for b in cell.tokens.values())


def _rel(path: str, pack: frozenset[str]) -> str | None:
    """The pack file a recorded path names (a record may state it absolute, under the cell's working copy)."""
    p = path.replace("\\", "/")
    if p in pack:
        return p
    hits = [f for f in pack if p.endswith("/" + f)]
    return max(hits, key=len) if hits else None


def _uncounted(parts: tuple[PromptPart, ...] | str) -> set[tuple[str, str]]:
    """The (part, fingerprint) keys of the prefix parts with no character count that name a fingerprint (`path`)."""
    if isinstance(parts, str):
        return set()
    return {(p.part, p.path) for p in parts if p.delivery in ("inlined", "listed") and p.chars is None and p.path}


def _identical(on: tuple[PromptPart, ...] | str, off: tuple[PromptPart, ...] | str) -> set[tuple[str, str]]:
    """The prefix rule's one exception (Leader ruling, J2-FIX tools-part DR): a part with no character count whose
    kind and fingerprint are identical in the pair's pack-on and pack-off cells contributes a delta of exactly 0,
    whatever its size; it is left out of both prefixes (and so of the tokens-per-character base). Differing or
    missing fingerprints leave the prefix not recorded."""
    return _uncounted(on) & _uncounted(off)


def _prefix(parts: tuple[PromptPart, ...], identical: set[tuple[str, str]] = frozenset()
            ) -> dict[tuple[str, str | None], int] | str:
    out: dict[tuple[str, str | None], int] = {}
    for part in parts:
        if part.delivery not in ("inlined", "listed") or (part.part, part.path) in identical:
            continue
        if part.chars is None:
            return f"not recorded: prompt part {part.part} has no character count"
        out[(part.part, part.path)] = out.get((part.part, part.path), 0) + part.chars
    return out


def _ms(events: Sequence[HarnessEvent]) -> int | None:
    total = 0
    for e in events:
        try:
            total += int((datetime.fromisoformat(e.end) - datetime.fromisoformat(e.start)).total_seconds() * 1000)
        except (TypeError, ValueError):
            return None
    return total


@dataclass
class _Pair:
    harness: str
    run_id: str
    task: str
    rep: int
    on_cell: CellView
    delta: Measure
    terms: dict[str, Measure]
    files: dict[str, tuple[int, int, str]]  # path -> (tokens, requests carried, delivery)
    pack_files: frozenset[str]
    on_total: int | None
    hook_ms: int | None
    identical: bool = False  # a fixed-prefix part entered as an exact zero delta (`_identical`)


def _carried(entered: list[int], compacted: Sequence[int]) -> tuple[int, int]:
    carried = tool_phases.carry_until_compaction(tuple(entered), frozenset(compacted))
    return sum(carried), sum(1 for c in carried if c)


def _pair(view: RunView, on: CellView, off: CellView, facts: Callable[[RunView, CellView], CellFacts]) -> _Pair:
    f_on, f_off = facts(view, on), facts(view, off)
    s_on = context_growth.request_series(view, on.cell_id)
    s_off = context_growth.request_series(view, off.cell_id)
    terms: dict[str, Measure] = {}
    files: dict[str, tuple[int, int, str]] = {}
    trees = next((t for t in (f_on.base_tree, f_off.base_tree) if isinstance(t, str)), None)
    pack: frozenset[str] = frozenset() if trees else f_on.base_tree - f_off.base_tree
    n_on, n_off = len(s_on.inputs), len(s_off.inputs)
    per_request = s_on.reason or s_off.reason or (None if n_on and n_off else "not recorded: no requests in the series")
    identical = _identical(f_on.prompt_parts, f_off.prompt_parts)
    prefix_on = _prefix(f_on.prompt_parts, identical) if isinstance(f_on.prompt_parts, tuple) else f_on.prompt_parts
    prefix_off = _prefix(f_off.prompt_parts, identical) if isinstance(f_off.prompt_parts, tuple) else f_off.prompt_parts
    tpc: Decimal | str  # the pack-on cell's tokens per character, or why it is not recorded
    if per_request or isinstance(prefix_on, str):
        tpc = per_request or prefix_on
    elif not sum(prefix_on.values()):
        tpc = "not recorded: a prefix of 0 characters"
    else:
        tpc = Decimal(s_on.inputs[0]) / Decimal(sum(prefix_on.values()))
    # fixed prefix, by part and path
    if isinstance(tpc, str) or isinstance(prefix_off, str):
        terms["fixed_prefix"] = Measure(None, tpc if isinstance(tpc, str) else prefix_off)
    else:
        total = 0
        deliveries = {(p.part, p.path): p.delivery for p in f_on.prompt_parts}
        for key in sorted(set(prefix_on) | set(prefix_off), key=lambda k: (k[0], k[1] or "")):
            tokens = _int(Decimal(prefix_on.get(key, 0) - prefix_off.get(key, 0)) * n_on * tpc)
            total += tokens
            if tokens:
                part, path = key
                name = (_rel(path, pack) or path) if path else f"({part} part)"
                files[name] = (files.get(name, (0, 0, ""))[0] + tokens, n_on, deliveries.get(key, "inlined"))
        terms["fixed_prefix"] = Measure(total)
    # extra requests
    if per_request:
        terms["extra_requests"] = Measure(None, per_request)
    else:
        base = Decimal(str(statistics.median(s_off.inputs)))
        terms["extra_requests"] = Measure(_int((n_on - n_off) * base))
    # pack reads and skill loads, entering at the next request and carried until a compaction
    for name, is_skill in (("pack_reads", False), ("skill_loads", True)):
        if isinstance(tpc, str):
            terms[name] = Measure(None, tpc)
            continue
        absent = next((r for r in (f_on.tool_inputs, f_on.model_ordinals, None if is_skill else trees)
                       if isinstance(r, str)), None)  # a pack read needs the pack's files; a skill load does not
        if absent:
            terms[name] = Measure(None, absent)
            continue
        if len(f_on.model_ordinals) != n_on:
            terms[name] = Measure(None, "not recorded: the request ordinals and the request series differ in length")
            continue
        entered: dict[str, list[int]] = {}
        missing = None
        for call in f_on.tool_inputs:
            skill = call.name.lower() in SKILL_TOOLS
            if skill != is_skill or call.is_write:
                continue
            target = "(skill tool call)" if skill else next((r for p in call.paths if (r := _rel(p, pack))), None)
            if target is None:
                continue
            if call.bytes_returned is None:
                missing = "not recorded: bytes returned are not in the record"
                break
            index = bisect.bisect_right(f_on.model_ordinals, call.native_ordinal)
            if index >= n_on:
                continue  # no later request carried it
            row = entered.setdefault(target, [0] * n_on)
            row[index] += _int(Decimal(call.bytes_returned) * tpc)
        if missing:
            terms[name] = Measure(None, missing)
            continue
        total = 0
        for target, row in entered.items():
            tokens, carried = _carried(row, s_on.compacted_before)
            total += tokens
            files[target] = (files.get(target, (0, 0, ""))[0] + tokens, carried, "on-demand")
        terms[name] = Measure(total)
    # hooks: counts and time are kept for the candidates; their tokens are not recorded
    terms["hooks"] = Measure(None, HOOK_TOKENS)
    hook_ms = None
    if isinstance(f_on.harness_events, tuple):
        hook_ms = _ms([e for e in f_on.harness_events if e.event == "hook"])
    # reasoning and output
    out_on, out_off = _out(on), _out(off)
    terms["reasoning_output"] = Measure(out_on - out_off) if out_on is not None and out_off is not None else \
        Measure(None, on.tokens_reason or off.tokens_reason or "not recorded: tokens")
    t_on, t_off = views.sum_tokens(on.tokens), views.sum_tokens(off.tokens)
    if t_on is None or t_off is None:
        delta = Measure(None, on.tokens_reason or off.tokens_reason or "not recorded: tokens")
        terms["residual"] = delta
    else:
        delta = Measure(t_on - t_off)
        terms["residual"] = Measure(delta.value - sum(m.value for m in terms.values() if m.value is not None))
    return _Pair(on.harness, view.run_id, on.task, on.rep or 0, on, delta, terms, files, pack, t_on, hook_ms,
                 bool(identical) and terms["fixed_prefix"].value is not None)


def _pairs(view: RunView) -> list[tuple[CellView, CellView]]:
    """The lean pairing (`verdicts.collect`): one pair is exactly one (harness, task, rep) of one batch, a pack-off
    and a pack-on cell, both admitted by its rule."""
    named = plan_mod.plan_comparisons(view.plan)  # a plan with both packs and no comparisons block names off/on
    if not named:
        return []
    ref, treat = named[0]
    tasks = tuple(sorted({c.task for c in view.cells}))
    out = []
    for harness in dict.fromkeys(c.harness for c in view.cells):
        spec = verdicts.VerdictSpec(prop=verdicts.PRIMARY, harness=harness, comparison=(ref, treat), tasks=tasks,
                                    mde=Decimal(0), method=stats.METHOD, alpha_per_test=Decimal("0.05"),
                                    level_rule="not used", min_pairs=1, seed=0, resamples=stats.MIN_RESAMPLES,
                                    required_pairs=None)
        mine = [c for c in view.cells if c.harness == harness]
        by_key = {(c.task, c.rep, c.arm): c for c in mine}
        pairs, _, _ = verdicts.collect(mine, spec)
        out += [(by_key[(p.task, p.rep, treat)], by_key[(p.task, p.rep, ref)]) for p in pairs]
    return out


# --- per harness ---------------------------------------------------------------------------------------------------

def _median(values: Sequence[int]) -> int:
    return _int(Decimal(str(statistics.median(values))))


def _agg(ms: Sequence[Measure]) -> tuple[Measure, Measure, Measure]:
    got = [m.value for m in ms if m.value is not None]
    if not ms or not got:
        reason = next((m.reason for m in ms if m.reason), "not recorded: no pairs")
        na = Measure(None, reason)
        return na, na, na
    if len(got) < len(ms):
        na = Measure(None, f"not recorded in {len(ms) - len(got)} of {len(ms)} pairs")
        return na, na, na
    return Measure(_median(got)), Measure(min(got)), Measure(max(got))


def _share(part: int, whole: int | None) -> Decimal | None:
    """Exact: a rule compares the unrounded share with its threshold; `_show` rounds it for the page only."""
    return None if not whole else Decimal(part) / Decimal(whole)


def _show(share: Decimal) -> str:
    return str(share.quantize(Decimal("0.0001")))


def _candidates(harness: str, pairs: list[_Pair], tops: list[TopFile], classes: Mapping[str, str]) -> list[Candidate]:
    out: list[Candidate] = []
    totals = [p.on_total for p in pairs if p.on_total is not None]
    on_total = _median(totals) if totals else None
    for f in tops:
        share = _share(f.tokens_per_cell.value or 0, on_total)
        if share is None:
            continue
        if f.component == "always_applied_instruction" and f.delivery == "inlined" and share >= ALWAYS_APPLIED_SHARE:
            out.append(Candidate("always_applied_share", harness,
                                 f"{f.path}: {f.tokens_per_cell.value:,} tokens per cell, {_show(share)} of pack-on tokens "
                                 "per cell", f"ALWAYS_APPLIED_SHARE = {ALWAYS_APPLIED_SHARE}",
                                 "narrow its applyTo to the paths it governs, or move it to on-demand"))
        if f.path == "(skills part)" and share >= SKILL_CATALOGUE_SHARE:
            out.append(Candidate("skill_catalogue_share", harness,
                                 f"the skill catalogue: {f.tokens_per_cell.value:,} tokens per cell, {_show(share)} of pack-on "
                                 "tokens per cell", f"SKILL_CATALOGUE_SHARE = {SKILL_CATALOGUE_SHARE}",
                                 "shorten the skill descriptions"))
    docs = {path for p in pairs for path in p.files if path in p.pack_files and p.files[path][2] == "on-demand"}
    for path in sorted(docs):
        if classes.get(path) != "knowledge_doc":
            continue
        read = sum(1 for p in pairs if path in p.files)
        share = _share(read, len(pairs))
        if share is not None and share >= ON_DEMAND_CELL_SHARE:
            out.append(Candidate("on_demand_cell_share", harness,
                                 f"{path}: read on demand in {read} of {len(pairs)} pack-on cells ({_show(share)})",
                                 f"ON_DEMAND_CELL_SHARE = {ON_DEMAND_CELL_SHARE}",
                                 "shorten it, or put the part most cells read into an always-loaded file"))
    shares = [_share(p.hook_ms, p.on_cell.wall_ms.value) for p in pairs
              if p.hook_ms is not None and isinstance(p.on_cell.wall_ms.value, int)]
    shares = [s for s in shares if s is not None]
    if shares and len(shares) == len(pairs):
        hook = statistics.median(shares)
        ms = _median([p.hook_ms for p in pairs])
        if hook >= HOOK_WALL_SHARE:
            out.append(Candidate("hook_wall_share", harness,
                                 f"hooks: {ms:,} ms per pack-on cell, {_show(hook)} of its wall clock",
                                 f"HOOK_WALL_SHARE = {HOOK_WALL_SHARE}", "merge or drop a hook"))
    return out


def _outcomes(vs: Sequence[RunView]) -> tuple[tuple[Outcome, ...], str | None]:
    try:
        summary = lean.build([lean.BatchInput(v, None, None, None, None) for v in vs], None)
    except BenchError as exc:
        return (), f"not recorded: {exc}"
    return tuple(Outcome(r.harness, r.combo, r.statement, r.effect, r.lo, r.hi, r.mde, r.pairs)
                 for r in summary.rows), None


def build(views: Sequence[RunView]) -> PackCost:
    """The decomposition, the component map and the candidates, from the views and the ADR-0026 s4 derivations."""
    run_views = views
    plan = run_views[0].plan if run_views else {}
    src = pack_source(plan)
    transports = {c.harness: tool_phases.transport(v.plan, c.harness, c.combo) for v in run_views for c in v.cells}
    pairs = [_pair(v, on, off, cell_facts) for v in run_views for on, off in _pairs(v)]
    classes: dict[str, str] = {}
    pack_files = sorted(set().union(*(p.pack_files for p in pairs)) if pairs else set())
    for path in pack_files:
        classes[path] = "unclassified" if src.reason else classify(path, src.read(path))
    harnesses, costs, tops, candidates = [], [], [], []
    for harness in dict.fromkeys(p.harness for p in pairs):
        mine = [p for p in pairs if p.harness == harness]
        terms = []
        for name in TERMS:
            median, low, high = _agg([p.terms[name] for p in mine])
            label = median.reason if median.value is None else LABELS[name]
            if name == "fixed_prefix" and median.value is not None and any(p.identical for p in mine):
                label = f"{label}; {IDENTICAL_FINGERPRINT}"
            terms.append(Term(name, median, low, high, label))
        harnesses.append(HarnessDecomposition(harness, transports[harness], len(mine), _agg([p.delta for p in mine])[0],
                                              tuple(terms)))
        def comp_of(path: str) -> str:
            return classes.get(path, _pseudo(path))
        seen = {comp_of(path) for p in mine for path in p.files}
        for comp in (c for c in COMPONENTS if c in seen):  # per pair, the component's sum; then the median
            values = [sum(t for path, (t, _, _) in p.files.items() if comp_of(path) == comp) for p in mine]
            costs.append(ComponentCost(comp, harness, Measure(_median(values))))
        paths = sorted({path for p in mine for path in p.files})
        rows = []
        for path in paths:
            tokens = [p.files.get(path, (0, 0, ""))[0] for p in mine]
            carried = [p.files.get(path, (0, 0, ""))[1] for p in mine]
            delivery = next(p.files[path][2] for p in mine if path in p.files)
            comp = classes.get(path, _pseudo(path))
            rows.append(TopFile(path, comp, harness, Measure(_median(tokens)), Measure(_median(carried)), delivery))
        rows.sort(key=lambda f: (-(f.tokens_per_cell.value or 0), f.path))
        tops += rows[:TOP_FILES]
        candidates += _candidates(harness, mine, rows, classes)
    outcomes, reason = _outcomes(run_views)
    return PackCost(
        runs=tuple(v.run_id for v in run_views), pack_source=src.label, pack_source_reason=src.reason,
        harnesses=tuple(harnesses), components=tuple(PackFile(p, classes[p]) for p in pack_files),
        component_costs=tuple(costs), top_files=tuple(tops), candidates=tuple(candidates),
        thresholds={k: str(v) for k, (v, _) in THRESHOLDS.items()},
        pairs=tuple(PairRow(p.harness, p.run_id, p.task, p.rep, p.delta, tuple(p.terms[t] for t in TERMS))
                    for p in pairs),
        outcomes=outcomes, outcome_reason=reason, transports=transports)


# --- render --------------------------------------------------------------------------------------------------------

STYLE = """
.harness-head{min-width:12em}
.harness-head [data-part]{display:block}
.harness-head [data-part="transport"]{font-weight:400;font-size:var(--fs-small);color:var(--ink-2)}
.analysis{max-width:72ch}
"""
ATTRIBUTING = ("fixed_prefix", "pack_reads", "skill_loads")  # the terms whose tokens are attributed to files
TERM_HEADS = {"fixed_prefix": "Fixed prefix", "extra_requests": "Extra requests", "pack_reads": "On-demand pack reads",
              "skill_loads": "Skill loads", "hooks": "Hooks", "reasoning_output": "Reasoning and output",
              "residual": "Residual"}


def _fmt(m: Measure) -> str:
    if m.value is None:
        reason = m.reason or "not recorded"
        return reason if reason.startswith("not recorded") else f"not recorded ({reason})"
    return f"{m.value:,}" if isinstance(m.value, int) else str(m.value)


def _dec(value: Decimal | None) -> str:
    return "not recorded" if value is None else f"{value:+.2f}"


class _Tables:
    def __init__(self, pc: PackCost):
        self.transports = pc.transports

    def head(self, harness: str) -> Html:
        transport = self.transports.get(harness, "not recorded")
        return el("th", {"scope": "row", "class": "harness-head"}, el("span", {"data-part": "harness"}, harness),
                  el("span", {"data-part": "transport"}, f"transport: {transport}"))

    def table(self, cap_id: str, caption: str, headers: Sequence[str],
              rows: Sequence[tuple[str | None, Sequence[str | Html]]], first: str = "Harness") -> Html:
        head = el("tr", None, el("th", {"scope": "col"}, first), *(el("th", {"scope": "col"}, h) for h in headers))
        body = []
        for harness, cells in rows:
            tds = [el("td", None if isinstance(c, Html) else {"class": "num"}, c) for c in cells]
            if harness is None:
                body.append(el("tr", None, el("th", {"scope": "row"}, cells[0]), *tds[1:]))
            else:
                body.append(el("tr", {"data-harness": harness}, self.head(harness), *tds))
        table = el("table", None, el("caption", {"id": cap_id}, caption), el("thead", None, head),
                   el("tbody", None, *body))
        return el("div", {"class": "region", "role": "region", "tabindex": "0", "aria-labelledby": cap_id}, table)


def _section(sid: str, title: str, *children: str) -> model.Section:
    return model.Section(sid, title, el("section", {"id": sid}, el("h2", None, title), *children))


def _header(pc: PackCost, t: _Tables) -> model.Section:
    facts = [("Runs", ", ".join(pc.runs) or "not recorded"),
             ("Pack source", pc.pack_source + (f" ({pc.pack_source_reason})" if pc.pack_source_reason else "")),
             ("Transports", "; ".join(f"{h}: {v}" for h, v in pc.transports.items()) or "not recorded")]
    dl = el("dl", None, *(x for k, v in facts for x in (el("dt", None, k), el("dd", None, v))))
    if pc.outcomes:
        outcome = t.table("outcome-caption", "The pack's effect on property_check_pass, from the lean summary",
                          ["Combo", "Statement", "Effect, 95% interval and MDE", "Pairs"],
                          [(o.harness, [o.combo, o.statement,
                                        f"{_dec(o.effect)} [{_dec(o.lo)}, {_dec(o.hi)}], MDE {o.mde}",
                                        f"{o.pairs:,}"]) for o in pc.outcomes])
    else:
        outcome = el("p", None, f"Outcome: {pc.outcome_reason or 'not recorded'}")
    body = el("section", {"id": "header"}, el("h1", None, TITLE),
              el("p", {"class": "muted"}, "For the pack owner: the extra tokens pack-on spends over pack-off, per "
                 "harness and per pack component, and what to tune. Tokens are the only cost unit. Each figure is a "
                 "per-pair median with its range, never pooled across harnesses; each modelled step is labelled "
                 "Inferred, and the residual is shown, never spread."), dl,
              el("h2", None, "Outcome beside cost"), outcome)
    return model.Section("header", TITLE, body)


def _decomposition(pc: PackCost, t: _Tables) -> model.Section:
    def cell(term: Term) -> str:
        if term.median.value is None:
            return _fmt(term.median)
        return f"{_fmt(term.median)} (range {_fmt(term.low)} to {_fmt(term.high)})"

    rows = [(h.harness, [f"{h.pairs:,}", _fmt(h.delta_total), *(cell(term) for term in h.terms)]) for h in pc.harnesses]
    labels = [(h.harness, [term.label for term in h.terms]) for h in pc.harnesses]
    heads = [TERM_HEADS[n] for n in TERMS]
    return _section("decomposition", "Where the extra tokens go",
                    el("p", None, "Per pair, the terms and the residual sum exactly to the pair's delta (pack-on minus "
                       "pack-off tokens). Across several pairs, the medians need not sum to the median delta; the "
                       "per-pair table below shows each exact sum."),
                    t.table("decomposition-caption", "Delta tokens per cell and its terms (per-pair medians)",
                            ["Pairs", "Delta tokens", *heads], rows),
                    t.table("labels-caption", "How each term was computed, per harness", heads, labels))


def _pair_table(pc: PackCost, t: _Tables) -> model.Section:
    rows = [(p.harness, [p.run_id, p.task, f"{p.rep:,}", _fmt(p.delta_total), *(_fmt(m) for m in p.terms)])
            for p in pc.pairs]
    return _section("pairs", "Each pair",
                    t.table("pairs-caption", "Each pair's delta and its exact decomposition (tokens)",
                            ["Run", "Task", "Rep", "Delta tokens", *(TERM_HEADS[n] for n in TERMS)], rows))


def _components(pc: PackCost, t: _Tables) -> model.Section:
    present = [c for c in COMPONENTS if any(x.component == c for x in pc.component_costs)]
    rows = []
    for h in pc.harnesses:
        got = {x.component: x.tokens_per_cell for x in pc.component_costs if x.harness == h.harness}
        # An absent component is a measured 0 only when every attributing term was recorded for this harness.
        unrecorded = next((t.median for t in h.terms if t.name in ATTRIBUTING and t.median.value is None), None)
        rows.append((h.harness, [_fmt(got.get(c, unrecorded or Measure(0))) for c in present]))
    counts = [(None, [c, f"{sum(1 for f in pc.components if f.component == c):,}"]) for c in COMPONENTS]
    children = [el("p", None, f"{len(pc.components):,} pack files (the pack-on base tree minus the pack-off base tree), "
                   f"classed by path and frontmatter from {pc.pack_source}."
                   + (f" {pc.pack_source_reason}." if pc.pack_source_reason else ""))]
    children.append(t.table("component-files-caption", "Pack files per component", ["Files"], counts, first="Component"))
    if present:
        children.append(t.table("components-caption", f"Attributed tokens per cell by component, {TPC}", present, rows))
    else:
        children.append(el("p", None, "No tokens were attributed to a pack component in these pairs."))
    return _section("components", "Pack components", *children)


def _top(pc: PackCost, t: _Tables) -> model.Section:
    rows = [(f.harness, [el("code", None, f.path), f.component, _fmt(f.tokens_per_cell), _fmt(f.requests_carried),
                         f.delivery]) for f in pc.top_files]
    return _section("top-files", "Top files",
                    t.table("top-caption", f"The files that cost the most, per harness (at most {TOP_FILES} each)",
                            ["File", "Component", f"Tokens per cell, {TPC}", "Requests that carried it", "Delivery"],
                            rows))


def _tuning(pc: PackCost, t: _Tables) -> model.Section:
    children: list[str] = [el("p", None, "Rule-based: a candidate states the harness, the measured figure and the "
                              "lever. It claims no effect: none was measured.")]
    if pc.candidates:
        children.append(t.table("candidates-caption", "Tuning candidates",
                                ["Rule", "Figure", "Threshold", "Lever"],
                                [(c.harness, [c.rule, c.figure, c.threshold, c.lever]) for c in pc.candidates]))
    else:
        children.append(el("p", None, "No candidate crossed its threshold."))
    rows = [(None, [el("code", None, k), pc.thresholds.get(k, str(v)), meaning]) for k, (v, meaning) in THRESHOLDS.items()]
    children.append(t.table("thresholds-caption", "The rules' thresholds (module constants; a rule fires at or above)",
                            ["Value", "Meaning"], rows, first="Constant"))
    return _section("tuning", "What to tune", *children)


def render(pc: PackCost, analysis_html: Html | None = None) -> str:
    """The page's HTML; `analysis_html` is the analyst section `analysis.check_and_render` built (escaped by the
    builder), absent without `--analysis`."""
    # report.html and egress import each other; importing egress first is the order that resolves the cycle.
    from harness_bench import egress  # noqa: F401
    from harness_bench.report import html as report_html

    t = _Tables(pc)
    sections = [_header(pc, t), _decomposition(pc, t), _pair_table(pc, t), _components(pc, t), _top(pc, t),
                _tuning(pc, t)]
    if analysis_html is not None:
        sections.append(model.Section("analysis", "Analysis", analysis_html))
    return model.page(model.ReportModel(run_id=", ".join(pc.runs), sections=tuple(sections)),
                      style=report_html.STYLE + STYLE)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bench report --pack-cost")
    p.add_argument("pack_cost", nargs="+")
    p.add_argument("--out", default=None)
    p.add_argument("--analysis", default=None)
    p.add_argument("--open", action="store_true")
    p.add_argument("--root", default=".")
    p.add_argument("--runs", default=None)
    return p


def cli_main(argv: Sequence[str]) -> int:
    """`bench report --pack-cost RUN [RUN ...] --out PATH [--analysis MD] [--open]`, written through `publish`.
    `argv` is the CLI's parsed namespace (`cli.cmd_report`), or a list of strings for a direct call."""
    from harness_bench.report import analysis, publish

    args = argv if isinstance(argv, argparse.Namespace) else _parser().parse_args(list(argv))
    pc = build(load_views(args))
    section = None
    if args.analysis:
        md = Path(args.analysis).read_text(encoding="utf-8")
        section = analysis.check_and_render(md, analysis.table_numbers(render(pc)))
    out = Path(args.out) if args.out else Path(args.root) / DEFAULT_OUT
    publish.publish(render(pc, section), out, bool(args.open))
    return 0
