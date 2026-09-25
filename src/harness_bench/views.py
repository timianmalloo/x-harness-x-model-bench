"""Projections over the verified facts (ADR-0006; design: Data model, Rules).

Pattern: On-demand Projection. Every view reads rows through `rows()`, which verifies each segment's hash
chain (HB-LED-002 on a break) and admits only:
- the engine process's segments (`engine-*`), and
- the segments of **completed** grading passes: a `grade-*` pass whose events segment is sealed and holds
  `grading.completed`. Any other grading segment belongs to an abandoned pass and is skipped (HB-LED-004).

Rules, each defined once here:
- Duplicates are refused (HB-LED-003): a second `cell.outcome` for a cell, or a repeated key in any fact.
- The current pass for a catalog version is the latest completed one (greatest `grading.completed`
  `recorded_at`, then `grading_id`). The current extraction is the one its scores name. With no version asked
  for, a probe pass (a `.dev` catalog version, R-59 DR-4) is never current; it is counted in `header["probe_passes"]`.
- Validity, tokens, the time split, leaderboard rows and exports are derived, never stored. A value that
  was not measured is a `Measure(None, reason)`, never 0 (US-27).
- Validity, in order: an invalidating cause; `invalid (build mismatch)` (HB-VAL-007, R-47); not graded;
  `invalid (tools denied by hook)` (HB-VAL-004, R-27); `invalid (out-of-profile tool called)` (HB-VAL-008, R-45 item
  2, R-54) for a class-`other` tool call that executed; `invalid (model mismatch)` (HB-VAL-002) for a served model
  that is not the pin, a declared auxiliary model, or one the task's `model_map` names (US-11), even in a partial
  record; `not recorded` for an unreadable usage record (HB-VAL-003, R-15), distinct from `invalid (no model call)`
  (HB-VAL-001, a readable record with no call); else valid.
- Warnings flag a cell without changing its validity: HB-VAL-005 (Σ model_calls vs the ACP turn total, R-24/R-26
  c5), HB-VAL-006 (the executed-build check skipped, R-22 c1, R-47) and HB-VAL-009 (an out-of-profile attempt the
  driver or a native hook refused, R-54). One code has one level and one emitter; a `Cause` code is never a view
  finding (R-47).
- `meta_calls` counts class-`meta` tool calls per cell (Claude Code's `ToolSearch`): a cost axis, never scored (R-54 c3).
- A class-`delegate` call (R-74) is in profile only in a cell whose frozen task scenario is 6, else HB-VAL-008 when
  executed and HB-VAL-009 when refused; `delegate_calls` counts them per cell, a cost axis, never scored (R-74 c2).

"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from harness_bench import archive, ledger, profiles
from harness_bench.errors import BenchError, Cause
from harness_bench.plan import load_confirmed, resolved_model_map
from harness_bench.telemetry import (
    Extraction,
    ModelCall,
    as_dict,
    copilot,
    is_count,
    normalize,
)

ENGINE_PREFIX = "engine-"
GRADE_PREFIX = "grade-"
FACTS = ("events", "model_calls", "tool_calls", "turn_usage", "archive_files", "scores", "verdict_uses")
KEYS = {  # ADR-0006 as amended: the key of one row of each fact
    "model_calls": ("run_id", "extraction_id", "principal", "native_session_id", "native_ordinal", "model"),
    "tool_calls": ("run_id", "extraction_id", "cell_id", "native_session_id", "native_ordinal"),
    "turn_usage": ("run_id", "cell_id", "attempt", "model"),
    "archive_files": ("run_id", "cell_id", "archive_attempt", "path"),
    "scores": ("run_id", "grading_id", "cell_id", "metric_id"),
    "verdict_uses": ("run_id", "grading_id", "cell_id", "item_id", "judge_or_matcher"),  # Amendment 3
}


def segment_paths(run_dir: Path, fact: str) -> list[Path]:
    folder = run_dir / fact
    return sorted(folder.glob("*.jsonl")) if folder.is_dir() else []


def _completions(run_dir: Path) -> dict[str, dict]:
    """grading_id -> its `grading.completed` row, for each completed pass (a sealed events segment holding one)."""
    done = {}
    for path in segment_paths(run_dir, "events"):
        if not path.stem.startswith(GRADE_PREFIX):
            continue
        report = ledger.verify_segment(path)
        if report.sealed and not report.error:
            row = next((r for r in ledger.read_segment(path) if r["kind"] == "grading.completed"), None)
            if row is not None:
                done[path.stem] = row
    return done


def completed_passes(run_dir: Path) -> set[str]:
    return set(_completions(run_dir))


def rows(run_dir: Path, fact: str) -> list[dict]:
    """Verified rows of the engine's segments and of completed grading passes, in segment order."""
    done = completed_passes(run_dir)
    out: list[dict] = []
    for path in segment_paths(run_dir, fact):
        sid = path.stem
        if sid.startswith(GRADE_PREFIX) and sid not in done:
            continue
        if not sid.startswith((ENGINE_PREFIX, GRADE_PREFIX)):
            raise BenchError("HB-LED-002", f"{fact}/{path.name}: no known writer for this segment")
        out.extend(ledger.read_segment(path))
    return out


@dataclass(frozen=True)
class Measure:
    """A measured value, or NOT_RECORDED (`value` None) with the reason."""

    value: int | str | Decimal | None
    reason: str | None = None


@dataclass
class CellView:
    cell_id: str
    label: str
    combo: str
    pack: str
    harness: str
    model: str
    outcome: str  # completed | timed_out | failed | not started | no outcome (launched; the run is incomplete)
    cause: str | None  # the cause's report label
    code: str | None
    validity: str  # valid | invalid (<attribution>) | invalid (...) as status.VALIDITY names them | not recorded | not graded | not started | no outcome
    validity_code: str | None
    wall_ms: Measure
    model_ms: Measure
    tool_ms: Measure
    idle_ms: Measure
    tokens: dict[str, dict[str, int]] | None  # per model, disjoint buckets; None = not recorded
    tokens_reason: str | None
    calls_per_cell: Measure = field(default_factory=lambda: Measure(None, "not recorded"))
    scores: dict[str, Measure] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)
    extraction_id: str | None = None
    warnings: list[Finding] = field(default_factory=list)  # view checks that flag a cell without changing its validity
    meta_calls: Measure = field(default_factory=lambda: Measure(None, "not graded"))  # R-54 c3: a cost axis, never scored
    delegate_calls: Measure = field(default_factory=lambda: Measure(None, "not graded"))  # R-74 c2: a cost axis, never scored


@dataclass
class RunView:
    run_id: str
    plan: dict
    completed: bool  # run.completed was recorded
    grading_id: str | None  # the current pass
    catalog_version: str | None
    cells: list[CellView]
    header: dict[str, str | int | None] = field(default_factory=dict)  # credential kind, network mode, executed builds, probe passes


@dataclass
class Row:
    combo: str
    pack: str
    harness: str
    model: str
    n_cells: int
    n_valid: int
    pass_at_1: Measure
    rank: str  # "1", "2=", or "" when unranked
    interval: str
    tokens: Measure  # mean total tokens per valid cell
    wall_ms: Measure  # mean per valid cell
    cost_usd: Measure  # mean per valid cell


def _refuse_duplicates(facts: dict[str, list[dict]]) -> None:
    seen: set[str] = set()
    for e in facts["events"]:
        if e["kind"] == "cell.outcome":
            if e["cell_id"] in seen:
                raise BenchError("HB-LED-003", f"a second cell.outcome for cell {e['cell_id']}")
            seen.add(e["cell_id"])
    for fact, key in KEYS.items():
        keys: set[tuple] = set()
        for r in facts[fact]:
            k = tuple(r.get(f) for f in key)
            if k in keys:
                raise BenchError("HB-LED-003", f"duplicate {fact} key {dict(zip(key, k, strict=True))}")
            keys.add(k)


def _is_probe(catalog_version) -> bool:
    """R-59 DR-4: a catalog version ending in `.dev` is a probe; its passes are never current scores."""
    return str(catalog_version or "").endswith(".dev")


def _probe_passes(events: list[dict]) -> int:
    """The completed passes a default view skips as probes (reported as `probe pass: <n>`)."""
    catalog = {e["grading_id"]: e.get("catalog_version") for e in events if e["kind"] == "grading.started"}
    return sum(1 for e in events if e["kind"] == "grading.completed" and _is_probe(catalog.get(e["grading_id"])))


def _current_pass(events: list[dict], catalog_version: str | None) -> tuple[str | None, str | None]:
    """The latest completed pass of `catalog_version`; with None, the latest that is not a probe (V-1)."""
    catalog = {e["grading_id"]: e.get("catalog_version") for e in events if e["kind"] == "grading.started"}
    done = [(e["recorded_at"], e["grading_id"]) for e in events if e["kind"] == "grading.completed"]
    if catalog_version is not None:
        done = [d for d in done if catalog.get(d[1]) == catalog_version]
    else:
        done = [d for d in done if not _is_probe(catalog.get(d[1]))]
    if not done:
        return None, catalog_version
    gid = max(done)[1]
    return gid, catalog.get(gid)


def _ts(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


NO_MODEL_START = "the native record gives no model-call start time"


def busy_ms(calls: list[dict], *, positive: bool = False, missing: str = "an interval has no start or end") -> Measure:
    """Milliseconds covered by the union of the calls' [start, end] spans (overlaps counted once).

    The one span rule: both ends recorded and the end not before the start; with `positive`, strictly after it
    (a model call with no length means its start was not recorded). One call that breaks it makes the whole
    measure NOT_RECORDED with `missing` as the reason, never a partial sum."""
    spans = [(_ts(c.get("start")), _ts(c.get("end"))) for c in calls]
    if any(start is None or end is None or end < start or (positive and end == start) for start, end in spans):
        return Measure(None, missing)
    total, cur_start, cur_end = 0.0, None, None
    for start, end in sorted(spans):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                total += (cur_end - cur_start).total_seconds()
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        total += (cur_end - cur_start).total_seconds()
    return Measure(round(total * 1000))


def _wall(events: dict[str, dict]) -> Measure:
    if "cell.launch_intent" not in events:
        return Measure(None, "cell never started")
    start, end = events.get("attempt.process_started", {}), events.get("attempt.process_ended", {})
    if "mono_ns" not in start or "mono_ns" not in end:
        return Measure(None, "no process start or end recorded")
    return Measure((end["mono_ns"] - start["mono_ns"]) // 1_000_000)


def _model_time(source: str, calls: list[dict] | None) -> Measure:
    if source == "acp_turn":
        return Measure(None, "the native record misses calls (token source acp_turn)")
    if calls is None:
        return Measure(None, "not graded")
    if not calls:
        return Measure(None, NO_MODEL_START)
    return busy_ms(calls, positive=True, missing=NO_MODEL_START)


def turn_usage(row: dict) -> normalize.TurnUsage:
    """The one mapping of a `turn_usage` row to its value object (views and the grading pass both read it)."""
    return normalize.TurnUsage(**{f.name: row[f.name] for f in fields(normalize.TurnUsage)})


_MODEL_CALL_MIGRATED_FIELDS = ("requests", "total_nano_aiu")  # optional: absent in a pre-amendment ledger row


def model_call(row: dict) -> ModelCall:
    """Map one ledger row; a field a migration made optional (`requests`, absent before Amendment 1;
    `total_nano_aiu`, absent before Amendment 2) uses only the ModelCall field default when the row
    does not carry it. Any other field's absence is a real defect and still raises KeyError."""
    values = {f.name: row[f.name] for f in fields(ModelCall) if f.name not in _MODEL_CALL_MIGRATED_FIELDS}
    for name in _MODEL_CALL_MIGRATED_FIELDS:
        if name in row:
            values[name] = row[name]
    return ModelCall(**values)


def calls_per_cell(calls: list[ModelCall] | None) -> Measure:
    """Requests in a recorded extraction; the caller passes None when it has no rows."""
    if calls is None or any(call.requests == 0 for call in calls):
        return Measure(None, "not recorded")
    return Measure(sum(call.requests for call in calls))


def judge_calls(uses: list[dict]) -> dict[tuple[str, str | None], int]:
    """Judge calls per (outcome, code), over `verdict_uses` rows (ADR-0006 Amendment 3). A row is one rubric item,
    not one call: one call yields a row per item. So a call is one distinct (grading_id, cell_id, metric_id,
    judge_or_matcher), with `metric_id` read from `item_id` (`<metric_id>#<n>`). The one compute reader that counts
    calls; no view counts rows as calls (tests/test_grade_judge.py guards it)."""
    calls: dict[tuple[str, str | None], set[tuple]] = {}
    for r in uses:
        call = (r["grading_id"], r["cell_id"], r["item_id"].rsplit("#", 1)[0], r["judge_or_matcher"])
        calls.setdefault((r["outcome"], r["code"]), set()).add(call)
    return {k: len(v) for k, v in sorted(calls.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))}


def _idle(wall: Measure, model: Measure, tool: Measure) -> Measure:
    for name, m in (("wall", wall), ("model", model), ("tool", tool)):
        if m.value is None:
            return Measure(None, f"needs {name} time")
    idle = wall.value - model.value - tool.value
    return Measure(idle) if idle >= 0 else Measure(None, "model and tool time exceed wall time")


NO_ACP_USAGE = "the adapter reported no usage"

# R-24, R-26 c5: the ACP turn total cross-checks Σ of the current extraction's model_calls buckets.
# simplify: a harness list in code. Ceiling: harnesses whose adapter `usage` is the turn total over every model.
# Upgrade trigger: any change to this list -> a profile datum instead (D&P). Verified: Copilot's ACP usage equals Σ modelMetrics in all
# three captured samples (tests/fixtures/native/copilot/provenance.json). Codex's adapter reports the last call only and
# Claude Code's the main model only (normalize docstring; tests/fixtures/acp/*-prompt-response.json), so a check there
# would fire on every cell.
ACP_TOTAL_HARNESSES = ("copilot",)
ACP_TOTAL_KEYS = (("inputTokens", ("uncached_input", "cache_read", "cache_write")), ("outputTokens", ("output",)),
                  ("cachedReadTokens", ("cache_read",)), ("cachedWriteTokens", ("cache_write",)))


def _build_check(plan: dict, harness: str, opened: dict) -> Finding | None:
    """R-47 (R-28 c2 re-pointed): `attempt.session_opened.agent_version`, verbatim from ACP `initialize.agentInfo`, must
    equal the pinned build's *recorded self-report*, `plan.builds[<harness>].agent_version` (observed at qualification
    for the same sha256). A proven mismatch is HB-VAL-007 at level error, which `_validity` turns into
    `invalid (build mismatch)`. `version` / `adapter_version` are package.json labels, never the comparand (Copilot
    self-reports 1.0.89-3 against a 1.0.89-1 manifest, R-45 c2). A null on either side skips the check with the
    HB-VAL-006 warning, never a pass (R-22 c1). HB-CELL-115 stays the engine's pre-launch cause (one code, one emitter)."""
    recorded = as_dict(as_dict(plan.get("builds")).get(harness)).get("agent_version")
    agent = opened.get("agent_version")
    if agent is None:
        return Finding("HB-VAL-006", "warning", "executed-build check skipped: no agent_version recorded")
    if recorded is None:
        return Finding("HB-VAL-006", "warning", f"executed-build check skipped: no recorded agent_version for {harness}")
    if agent != recorded:
        return Finding("HB-VAL-007", "error", f"agent_version {agent} differs from the pinned build's recorded {recorded}")
    return None


def _token_cross_check(ended: dict, calls: list[ModelCall]) -> Finding | None:
    """HB-VAL-005, a warning, never a validity change: the ACP turn total and Σ model_calls disagree, or no ACP usage
    was recorded (the check did not run, which is never read as a pass). Copilot's `inputTokens` includes cache read
    and write (R-20 c2)."""
    usage = as_dict(ended.get("acp_usage")).get("usage")
    if not isinstance(usage, dict):
        return Finding("HB-VAL-005", "warning", "token cross-check not run: no ACP usage recorded")
    diffs = []
    for key, buckets in ACP_TOTAL_KEYS:
        total = sum(getattr(c, b) for c in calls for b in buckets)
        if not (is_count(usage.get(key)) and usage[key] == total):
            diffs.append(f"{key} ACP {usage.get(key)}, model_calls {total}")
    if not diffs:
        return None
    return Finding("HB-VAL-005", "warning", "model_calls tokens differ from the ACP turn total: " + "; ".join(diffs))


OTHER = "other"  # the readers' class for a tool outside ADR-0004's profile (claude_code, codex, copilot TOOL_CLASS)
META = "meta"  # R-54 (a): loads a deferred tool's schema and invokes nothing (Claude Code's ToolSearch)
DELEGATE = "delegate"  # R-74 item 1: starts, addresses or reads a sub-agent (Claude Code Agent; Copilot task, ...)


def _scenario(plan: dict, cell: dict):
    """The cell's frozen task scenario (`plan.tasks[<id>].scenario`, R-74 item 2); None when the plan froze none."""
    return as_dict(as_dict(plan.get("tasks")).get(cell.get("task"))).get("scenario")


def _outside(tool_class, scenario) -> bool:
    """R-74 item 2, the one scenario rule: a class-`other` call is always outside the profile; a class-`delegate` call is
    outside it in every cell whose frozen task scenario is not 6. The readers' classes are static; only this reads the plan."""
    return tool_class == OTHER or (tool_class == DELEGATE and scenario != 6)


def _advertised_out_of_class(harness: str, advertised, scenario=None) -> list[str]:
    """R-45 item 2: for Copilot, the ids the pass recorded as advertised (`grading.completed.tools_advertised[cell]`,
    the reader's list) that the reader's own class map puts outside the profile (`_outside`, so a `delegate` id outside a
    scenario-6 cell, R-74). A list that was not read (null or absent) gives no finding: not recorded, never a pass and
    never an empty list."""
    if harness != "copilot" or not isinstance(advertised, list):
        return []
    return [name for name in advertised if isinstance(name, str) and _outside(copilot.TOOL_CLASS.get(name, OTHER), scenario)]


def _out_of_profile(tools: list[dict], permission_requests, advertised: list[str] = (),
                    scenario=None) -> tuple[Finding | None, Finding | None]:
    """R-45 item 2 as refined by R-54 (b): (HB-VAL-008 error for the calls outside the profile that executed, HB-VAL-009
    warning for the ones that were refused), each None when there is none. Outside the profile is `_outside`: class
    `other`, and class `delegate` in a cell whose frozen task scenario is not 6 (R-74 item 2).

    Refused: a native hook denied it (Copilot's denial envelope, `outcome_code` "denied"), or it failed (`ok` 0) and the
    driver counted a permission request for it (Claude Code: the driver cancels every request, `driver.py`). One counted
    request refuses one failed row. The refusal signal is the driver's count or the native envelope, never the model's
    prose. Anything else executed: `ok` 1; `ok` null, which is never refused (every Codex `exec` row); or a failure no
    counted request accounts for (the Codex Q1 `McpToolCall` failed at the connector, so it left the cell, R-55).
    assume: a counted request belongs to a failed class-`other` row before any other row. Confirm: allowlisted in-class ids
    never prompt (R-34's static test keeps each in the allowlist). Breaks: a request for an in-class id would refuse one
    executed `other` row; that row is still named in the HB-VAL-009 warning, never hidden."""
    requests = permission_requests if is_count(permission_requests) else 0
    executed: list[str] = []
    refused: list[str] = []
    for r in tools:
        if not _outside(r.get("tool_class"), scenario):
            continue
        if r.get("outcome_code") == normalize.HOOK_DENIED:
            refused.append(r["name"])
        elif r.get("ok") == 0 and requests > 0:
            requests -= 1
            refused.append(r["name"])
        else:
            executed.append(r["name"])
    parts = ([f"out-of-profile tool called: {', '.join(executed)}"] if executed else []) + (
        [f"out-of-profile tool advertised: {', '.join(advertised)}"] if advertised else [])
    error = Finding("HB-VAL-008", "error", "; ".join(parts)) if parts else None
    warning = Finding("HB-VAL-009", "warning", "out-of-profile attempt refused: " + ", ".join(refused)) if refused else None
    return error, warning


def _unrecorded(source: str, record_reason: str | None, ended: dict, usage: list) -> str | None:
    """Why the cell's authoritative usage record is not recorded (R-15, R-21 c2), or None when it was read.

    - `native_record`: `record_reason`, the current pass's `grading.completed.unreadable_records` entry (no record,
      more than one, or unreadable as a whole). A pass from before R-15 names none, so its cells read as before.
    - `acp_turn`: `attempt.process_ended.acp_usage` is recorded as null (R-24 c2: the adapter reported nothing) and
      there is no `turn_usage` row. A ledger from before R-24 has no `acp_usage` key and reads as before."""
    if source == "acp_turn":
        return NO_ACP_USAGE if not usage and "acp_usage" in ended and ended["acp_usage"] is None else None
    return record_reason


def _validity(cell: dict, prof: dict, outcome: dict | None, state: str, served: set[str] | None,
              unrecorded: str | None = None, denials: int = 0, mapped: frozenset[str] = frozenset(),
              build: Finding | None = None, out_of_profile: Finding | None = None) -> tuple[str, str | None]:
    if outcome is None:
        return state, None  # not started | no outcome
    cause = Cause[outcome["cause"]] if outcome.get("cause") else None
    if cause is not None and cause.invalidates:
        return f"invalid ({cause.attribution})", cause.code
    if build is not None and build.level == "error":  # R-47 c2: needs only attempt.session_opened, so before grading
        return "invalid (build mismatch)", build.code
    if served is None:
        return "not graded", None
    if denials:  # R-27: measured, so it outranks a record that is otherwise unreadable
        return "invalid (tools denied by hook)", "HB-VAL-004"
    # R-45 item 2, R-54: the slot is this track's choice (the rulings leave it open). After HB-VAL-004: both are the tool
    # treatment (US-14), and a hook denial is the narrower, pack-specific finding, so R-27's negative control keeps its
    # code. Before the model mismatch and "not recorded": an executed call is measured even in a partial record (D&P).
    if out_of_profile is not None:
        return "invalid (out-of-profile tool called)", out_of_profile.code
    # A served model that is neither the pin, a declared auxiliary model, nor one the task's model_map names. Seen in a
    # partial record it is still measured, so it outranks "not recorded" (D&P); an empty served set cannot mismatch.
    if any(not profiles.model_allowed(m, cell["model"], prof["auxiliary_models"]) and m not in mapped for m in served):
        return "invalid (model mismatch)", "HB-VAL-002"
    if unrecorded is not None:  # R-15 c1: distinct from a readable record with no call (HB-VAL-001)
        return "not recorded", "HB-VAL-003"
    if not served:
        return "invalid (no model call)", "HB-VAL-001"
    return "valid", None


def _mapped(plan: dict, cell: dict) -> frozenset[str]:
    """US-11: the models the cell's task routes roles to for the cell's own vendor (R-73 item 2: the one resolver,
    `plan.resolved_model_map`), by base id (R-32). A plan from before the map, or the vendor, was frozen has none."""
    return frozenset(normalize.base_model_id(m) for m in resolved_model_map(plan, cell).values())


def _cell_view(plan: dict, cell: dict, facts: dict[str, list[dict]], grading_id: str | None) -> CellView:
    cid = cell["cell_id"]
    events = {e["kind"]: e for e in facts["events"] if e.get("cell_id") == cid}
    outcome = events.get("cell.outcome")
    prof = plan["profiles"][cell["harness"]]
    source = prof["usage_source"]
    now = {s["metric_id"]: s for s in facts["scores"] if s["grading_id"] == grading_id and s["cell_id"] == cid}
    extraction = next((s["extraction_id"] for s in now.values()), None)
    calls = tools = None
    if extraction is not None:
        calls = [r for r in facts["model_calls"] if r["cell_id"] == cid and r["extraction_id"] == extraction]
        tools = [r for r in facts["tool_calls"] if r["cell_id"] == cid and r["extraction_id"] == extraction]
    usage = [turn_usage(r) for r in facts["turn_usage"] if r["cell_id"] == cid]
    ex = Extraction(model_calls=[model_call(r) for r in calls or []])
    recorded = source == "acp_turn" or calls is not None
    served = normalize.served_models(source, ex, usage) if recorded else None
    completed = next((e for e in facts["events"] if e["kind"] == "grading.completed" and e["grading_id"] == grading_id), {})
    ended = events.get("attempt.process_ended", {})
    record_reason = as_dict(completed.get("unreadable_records")).get(cid)  # the native record, whatever the token source
    unrecorded = _unrecorded(source, record_reason, ended, usage)
    build = _build_check(plan, cell["harness"], events["attempt.session_opened"]) if "attempt.session_opened" in events else None
    warnings = [build] if build is not None and build.level == "warning" else []
    scenario = _scenario(plan, cell)
    advertised = _advertised_out_of_class(cell["harness"], as_dict(completed.get("tools_advertised")).get(cid), scenario)
    executed, refused = _out_of_profile(tools or [], (outcome or {}).get("permission_requests"), advertised, scenario)
    warnings.append(refused)
    if cell["harness"] in ACP_TOTAL_HARNESSES and source == "native_record" and calls is not None and unrecorded is None:
        warnings.append(_token_cross_check(ended, ex.model_calls))
    totals = normalize.totals(source, ex, usage) if recorded and unrecorded is None else {}
    if unrecorded is not None:
        tokens_reason = f"not recorded ({unrecorded})"  # R-21 c2: never a partial sum or a zero
    else:
        tokens_reason = None if totals else ("not graded" if not recorded else "no usage recorded")
    wall = _wall(events)  # lifecycle-derived: never gated on the native record
    if record_reason is not None:  # Codex F1: every native-record measure is NA with the reason, never a partial one
        model = tool = idle = per_cell = meta = delegate = Measure(None, record_reason)
    else:
        model = _model_time(source, calls)
        tool = Measure(None, "not graded") if tools is None else busy_ms(tools)
        idle = _idle(wall, model, tool)
        per_cell = calls_per_cell(ex.model_calls if calls else None)
        meta = Measure(None, "not graded") if tools is None else Measure(sum(1 for r in tools if r.get("tool_class") == META))
        delegate = Measure(None, "not graded") if tools is None else Measure(sum(1 for r in tools if r.get("tool_class") == DELEGATE))
    state = outcome["outcome"] if outcome else ("no outcome" if "cell.launch_intent" in events else "not started")
    # R-54 (b): a row outside the profile that a hook denied is a refused attempt (HB-VAL-009), not an R-27 treatment denial.
    denials = normalize.hook_denials([r for r in tools or [] if not _outside(r.get("tool_class"), scenario)])
    validity, validity_code = _validity(cell, prof, outcome, state, served, unrecorded, denials, _mapped(plan, cell), build,
                                        executed)
    cause = Cause[outcome["cause"]] if outcome and outcome.get("cause") else None
    return CellView(
        cell_id=cid, label=cell.get("label", cid), combo=cell["combo"], pack=cell["pack"], harness=cell["harness"], model=cell["model"],
        outcome=state, cause=cause.label if cause else None,
        code=cause.code if cause else None, validity=validity, validity_code=validity_code,
        wall_ms=wall, model_ms=model, tool_ms=tool, idle_ms=idle,
        tokens=totals or None, tokens_reason=tokens_reason, calls_per_cell=per_cell,
        scores={m: Measure(s["value"], s["reason"]) for m, s in now.items()},
        evidence={m: s["evidence"] for m, s in now.items() if s.get("evidence")}, extraction_id=extraction,
        warnings=[w for w in warnings if w is not None], meta_calls=meta, delegate_calls=delegate)


def load(run_dir: Path, catalog_version: str | None = None) -> RunView:
    plan = load_confirmed(run_dir)
    facts = {f: rows(run_dir, f) for f in FACTS}
    _refuse_duplicates(facts)
    grading_id, catalog = _current_pass(facts["events"], catalog_version)
    cells = [_cell_view(plan, c, facts, grading_id) for c in plan["cells"]]
    completed = any(e["kind"] == "run.completed" for e in facts["events"])
    return RunView(plan["run_id"], plan, completed, grading_id, catalog, cells, _header(facts["events"]))


def build_label(harness: str, version: str) -> str:
    label = f"{harness} {version}".strip()
    return f"{label} (prerelease)" if harness == "copilot" and "-" in version else label


def _header(events: list[dict]) -> dict[str, str | int | None]:
    """Report-header facts as recorded at process start; None = not recorded. `probe_passes` counts the `.dev`
    passes a default view skips (R-59 DR-4, V-1); it is a header key, so `export` never carries it."""
    started = [e for e in events if e["kind"] == "attempt.process_started"]

    def one(field_name: str) -> str | None:
        values = sorted({str(e[field_name]) for e in started if e.get(field_name)})
        return ", ".join(values) or None

    builds = sorted({build_label(e["harness"], str(e["build_version"])) for e in started
                     if e.get("harness") and e.get("build_version")})
    return {"credential_kind": one("credential_kind"), "network_mode": one("network_mode"), "executed_builds": ", ".join(builds) or None,
            "probe_passes": _probe_passes(events)}


def _mean(values: list) -> Decimal:
    return sum((Decimal(v) for v in values), Decimal(0)) / len(values)


def _row(view: RunView, cells: list[CellView]) -> Row:
    valid = [c for c in cells if c.validity == "valid"]
    passes = [c.scores["pass_at_1"].value for c in valid if c.scores.get("pass_at_1", Measure(None)).value is not None]
    if passes:
        pass_at_1 = Measure(_mean(passes))
    else:
        pass_at_1 = Measure(None, "not graded" if view.grading_id is None else "no valid graded cell")
    used = [sum(sum(b.values()) for b in c.tokens.values()) for c in valid if c.tokens]
    walls = [c.wall_ms.value for c in valid if c.wall_ms.value is not None]
    no_cost = [c for c in valid if c.scores.get("cost_usd", Measure(None, "not graded")).value is None]
    if not valid:
        cost = Measure(None, "no valid cell")
    elif no_cost:
        reason = no_cost[0].scores.get("cost_usd", Measure(None, "not graded")).reason
        cost = Measure(None, f"{len(no_cost)} of {len(valid)} valid cells have no cost: {reason}")
    else:
        cost = Measure(_mean([c.scores["cost_usd"].value for c in valid]))
    first = cells[0]
    return Row(first.combo, first.pack, first.harness, first.model, len(cells), len(valid), pass_at_1, "",
               "interval not computed (n < 2)" if len(valid) < 2 else "interval not computed (statistics are phase 4)",
               Measure(_mean(used)) if used else Measure(None, "no valid cell with usage"),
               Measure(_mean(walls)) if walls else Measure(None, "no valid cell with wall time"), cost)


def leaderboard(view: RunView) -> list[Row]:
    """One row per combo x pack, correctness first: a cheaper failure never outranks a pass; equal pass rates tie."""
    groups: dict[tuple[str, str], list[CellView]] = {}
    for c in view.cells:
        groups.setdefault((c.combo, c.pack), []).append(c)
    out = [_row(view, cells) for cells in groups.values()]
    ranked = [r.pass_at_1.value for r in out if r.pass_at_1.value is not None]
    for r in out:
        v = r.pass_at_1.value
        if v is not None:
            r.rank = str(1 + sum(1 for o in ranked if o > v)) + ("=" if ranked.count(v) > 1 else "")
    return sorted(out, key=lambda r: (r.pass_at_1.value is None, -(r.pass_at_1.value or 0), r.combo, r.pack))


def _enc(value):
    if isinstance(value, Measure):
        return {"value": _enc(value.value), "reason": value.reason}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _enc(v) for k, v in value.items()}
    return value


def export(view: RunView) -> bytes:
    """The canonical result (sorted keys and rows). A pass's identity and evidence paths are not part of it,
    so a re-grade of the same archive gives the same bytes (US-26)."""
    cells = [{"cell_id": c.cell_id, "label": c.label, "outcome": c.outcome, "cause": c.cause, "code": c.code,
              "validity": c.validity, "validity_code": c.validity_code, "wall_ms": _enc(c.wall_ms), "model_ms": _enc(c.model_ms),
              "tool_ms": _enc(c.tool_ms), "idle_ms": _enc(c.idle_ms), "tokens": c.tokens, "tokens_reason": c.tokens_reason,
              "scores": _enc(c.scores), "extraction_id": c.extraction_id, "meta_calls": _enc(c.meta_calls),
              "delegate_calls": _enc(c.delegate_calls),
              "warnings": [{"code": w.code, "level": w.level, "message": w.message} for w in c.warnings]}
             for c in sorted(view.cells, key=lambda c: c.cell_id)]
    board = [{"combo": r.combo, "pack": r.pack, "n_cells": r.n_cells, "n_valid": r.n_valid, "pass_at_1": _enc(r.pass_at_1),
              "rank": r.rank, "interval": r.interval, "tokens": _enc(r.tokens), "wall_ms": _enc(r.wall_ms), "cost_usd": _enc(r.cost_usd)}
             for r in leaderboard(view)]
    return ledger.canonical({"run_id": view.run_id, "catalog_version": view.catalog_version, "cells": cells, "leaderboard": board})


@dataclass(frozen=True)
class Finding:
    code: str
    level: str  # error | warning
    message: str


def _heads(run_dir: Path, segment_id: str, heads, owner: str) -> list[Finding]:
    """Each segment `heads` names (`<fact>/<segment_id>`) exists, is sealed, and ends at the recorded head."""
    if not isinstance(heads, dict):
        return [Finding("HB-LED-002", "error", f"{owner}: heads is not a fact -> head map")]
    out = []
    for fact, head in sorted(heads.items()):
        path = run_dir / fact / f"{segment_id}.jsonl"
        if not path.is_file():
            out.append(Finding("HB-LED-002", "error", f"{fact}/{segment_id}: missing, but {owner} records its head"))
            continue
        report = ledger.verify_segment(path)
        if not report.sealed:
            out.append(Finding("HB-LED-002", "error", f"{fact}/{segment_id}: not sealed, but {owner} records its head"))
        elif report.head_hash != head:
            out.append(Finding("HB-LED-002", "error", f"{fact}/{segment_id}: head does not match the one {owner} records"))
    return out


def _sealed_record(run_dir: Path) -> list[Finding]:
    """Every completed pass and every completed run against the heads it recorded (ruling R-2).

    - A completed pass: all its segments are sealed, and `grading.completed.heads` (never events) match. A pass
      recorded before `heads` existed verifies with a warning.
    - A completed run: `run.completed.segment_heads` match its engine segments; its events head is the row
      `run.completed` follows, and the in-run pass its `grading` summary names matches that summary's heads
      (events included), so the pass cannot be cut back into an abandoned one."""
    out: list[Finding] = []
    for gid, row in sorted(_completions(run_dir).items()):
        owner = f"grading.completed in events/{gid}"
        for fact in FACTS:
            path = run_dir / fact / f"{gid}.jsonl"
            if path.is_file() and not ledger.verify_segment(path).sealed:
                out.append(Finding("HB-LED-002", "error", f"{fact}/{gid}: not sealed, but {owner} marks the pass complete"))
        if "heads" in row:
            out += _heads(run_dir, gid, row["heads"], owner)
        else:
            out.append(Finding("HB-LED-006", "warning", f"events/{gid}: grading.completed records no heads "
                                                        "(written before ruling R-2); only its seals are checked"))
    for path in segment_paths(run_dir, "events"):
        if not path.stem.startswith(ENGINE_PREFIX):
            continue
        for row in ledger.read_segment(path):
            if row["kind"] != "run.completed":
                continue
            owner = f"run.completed in events/{path.stem}"
            heads = dict(row.get("segment_heads") or {})
            if heads.pop("events", None) != row["prev_hash"] or not ledger.verify_segment(path).sealed:
                out.append(Finding("HB-LED-002", "error", f"events/{path.stem}: {owner} does not follow the events head it records"))
            out += _heads(run_dir, path.stem, heads, owner)
            grading = row.get("grading")
            if isinstance(grading, dict) and "heads" in grading:
                out += _heads(run_dir, str(grading.get("grading_id")), grading["heads"], f"{owner} (grading)")
    return out


def verify(run_dir: Path) -> list[Finding]:
    """`bench verify`: every segment's chain and seal, the heads each completed pass and run recorded, abandoned
    passes, duplicates, and each archive against its `archive_hash` and its `archive_files` rows. An error is an
    integrity failure; a warning is not."""
    out: list[Finding] = []
    done = completed_passes(run_dir)
    for fact in FACTS:
        for path in segment_paths(run_dir, fact):
            report = ledger.verify_segment(path)
            if report.error:
                out.append(Finding("HB-LED-002", "error", f"{fact}/{path.name}: {report.detail}"))
            elif path.stem.startswith(GRADE_PREFIX) and path.stem not in done:
                if fact == "events" and report.sealed:  # a pass seals its events only after grading.completed
                    out.append(Finding("HB-LED-002", "error", f"events/{path.stem}: sealed, but holds no grading.completed"))
                else:
                    out.append(Finding("HB-LED-004", "warning", f"{fact}/{path.stem}: abandoned grading segment, skipped by views"))
    if any(f.level == "error" for f in out):
        return out
    out += _sealed_record(run_dir)
    if any(f.level == "error" for f in out):
        return out
    try:
        load(run_dir)
    except BenchError as exc:
        return [*out, Finding(exc.code, "error", exc.message)]
    files = rows(run_dir, "archive_files")
    for e in rows(run_dir, "events"):
        if e["kind"] != "cell.archived":
            continue
        cid, attempt = e["cell_id"], e["archive_attempt"]
        cell_rows = [r for r in files if r["cell_id"] == cid and r["archive_attempt"] == attempt]
        if archive.archive_hash(cell_rows) != e["archive_hash"]:
            out.append(Finding("HB-LED-005", "error", f"{cid}: archive_hash does not match its archive_files rows"))
            continue
        folder = run_dir / "archive" / cid / f"attempt-{attempt}"
        try:
            archive.verify(folder, cell_rows)
        except BenchError as exc:
            out.append(Finding("HB-LED-005", "error", f"{cid}: {exc.message}"))
    return out
