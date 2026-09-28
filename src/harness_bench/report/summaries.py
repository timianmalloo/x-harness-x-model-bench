"""The AI summaries, offline (design phase4-report.md section 8, slice R7; ruling R-81 DR-R-4..6).

The seven-step call path (section 8): manifest -> `summary-request/1` -> `egress.check` -> `.release(backend)`
through the gateway's `ReplayBackend` (R8 alone wires the live `Headless` backend) -> `claim_check` (pure,
offline, deterministic) -> an append-only `summary_records` row -> the report reads it.

`summary_records` is the one new stored fact (design section 4): one row per summary generation attempt,
written only through `ledger.SegmentWriter` (never rewritten -- a tampered row fails to verify, same as
every other ledger-backed fact) and never carrying a `published` outcome with a failing claim (`Row.__post_init__`,
the second invariant: a published row with a failing claim cannot be constructed).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from harness_bench import board as board_mod
from harness_bench import egress, ledger, oslock, views
from harness_bench.errors import BenchError
from harness_bench.gateway import backend as gw_backend
from harness_bench.gateway import request as gw_request
from harness_bench.gateway import schema as gw_schema
from harness_bench.stats import no_detectable_effect

KIND_RANKING = "ranking"
KIND_PACK = "pack"
KINDS = (KIND_RANKING, KIND_PACK)
OUTCOMES = ("published", "not_published", "refused", "withheld", "backend_unavailable")
EXCERPT_BOUND = 8_000  # DR-R-4: up to 8,000 characters each
SAMPLE_CAP = 2  # DR-R-4: at most 2 per combo
FACT = "summary_records"
SEGMENT_ID = "summary"
# simplify: no gateway.yaml entry for a summarizer model exists yet (that is R8's Headless wiring); a fixed
# egress destination id stands in until then. Upgrade trigger: R8 reads the pinned judge-like config instead.
MODEL = "report-summaries"
SAMPLING_RULE = ("DR-R-4: per combo, the pack=on cells discordant with their paired pack=off cell on pass@1, "
                 "at most 2 per combo, chosen by cell id")

RANKING_INSTRUCTIONS = ("Write claims about the ranking: who is ahead, and how sure the data is. Cite every "
                        "number to a board: reference, a run id or a cell id.")
PACK_INSTRUCTIONS = ("Write claims about the pack's effect. Cite every number to a pack: reference and print "
                     "its [lo, hi] interval in the same sentence. State no_effect, never effect or suggestion, "
                     "for an interval that crosses zero.")

STATE_COPY = {
    "S-NONE": "Summary not generated: no summary was requested for this results pass. Generate with "
              "bench report {run_id} --summaries.",
    "S-WAIT": "Summary not generated: the summarizer backend is not available (backend_unavailable).",
    "S-STALE": "Summary not generated: the results changed since the summary was written. Regenerate with "
               "bench report {run_id} --summaries.",
    "S-NOTPUB": "Not published: {n} claims did not resolve. Regenerate the summaries with bench report.",
    "S-WITHHELD": "Summary not generated: withheld: sensitive content.",
    "S-REFUSED": "Summary not generated: the model's answer did not match the claims schema.",
}
PUB_LABEL = "Written by {model} from the results store. Every claim links to its runs."
_OUTCOME_STATE = {"backend_unavailable": "S-WAIT", "withheld": "S-WITHHELD", "refused": "S-REFUSED",
                  "not_published": "S-NOTPUB", "published": "S-PUB"}


# --------------------------------------------------------------------------------------- the stored fact (grain)
@dataclass(frozen=True)
class Row:
    """design section 4's grain: one row is exactly one summary generation attempt, for (run_id, pass_id,
    kind, manifest_sha256, model). The second invariant is structural: a `published` outcome may never
    carry a failing claim -- attempting to construct one raises (never a state a caller could render)."""

    run_id: str
    pass_id: str
    kind: str
    model: str
    manifest: tuple[dict, ...]
    manifest_sha256: str
    request_sha256: str
    template_version: str
    schema_sha256: str
    outcome: str
    claims: tuple[dict, ...] = ()
    failing_claims: tuple[dict, ...] = ()
    egress: tuple[dict, ...] = ()
    sampling: dict | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"not a known summary kind: {self.kind!r}")
        if self.outcome not in OUTCOMES:
            raise ValueError(f"not a known summary outcome: {self.outcome!r}")
        if self.outcome == "published" and self.failing_claims:
            raise ValueError("a published summary_records row may not carry a failing claim (design section 4)")
        if self.outcome not in ("published", "not_published") and self.claims:
            raise ValueError(f"a {self.outcome!r} row may not carry claims")

    def to_record(self) -> dict:
        return {"kind": "summary_record", "run_id": self.run_id, "pass_id": self.pass_id, "summary_kind": self.kind,
                "model": self.model, "manifest": list(self.manifest), "manifest_sha256": self.manifest_sha256,
                "request_sha256": self.request_sha256, "template_version": self.template_version,
                "schema_sha256": self.schema_sha256, "outcome": self.outcome, "claims": list(self.claims),
                "failing_claims": list(self.failing_claims), "egress": list(self.egress), "sampling": self.sampling}

    @classmethod
    def from_record(cls, row: dict) -> Row:
        return cls(run_id=row["run_id"], pass_id=row["pass_id"], kind=row["summary_kind"], model=row["model"],
                  manifest=tuple(row["manifest"]), manifest_sha256=row["manifest_sha256"],
                  request_sha256=row["request_sha256"], template_version=row["template_version"],
                  schema_sha256=row["schema_sha256"], outcome=row["outcome"], claims=tuple(row["claims"]),
                  failing_claims=tuple(row["failing_claims"]), egress=tuple(row.get("egress") or ()),
                  sampling=row.get("sampling"))


def _segment_path(run_dir: Path) -> Path:
    return run_dir / FACT / f"{SEGMENT_ID}.jsonl"


def append(run_dir: Path, row: Row) -> dict:
    """Append one `summary_records` row through `ledger` (append-only; never rewritten). The segment is
    never sealed: a regenerate reopens it and appends a new row (design section 4's history rule).

    `SegmentWriter`'s single-writer guard is in-process only (`ledger._open_writers`, a Python `set`),
    and this is the one call site that reopens a fact segment across separate `bench report --summaries`
    processes rather than opening a fresh segment once per run (Data & Persistence Architect review,
    R7 final review, Major finding): two racing processes would both `_scan` the same head, then both
    append with the same `seq`, breaking the hash chain for the *whole* segment on the next read, not
    only the new row. `HB-SUM-002` takes an OS file lock (`oslock`, the same primitive the run and grade
    locks use) around reopen+append+close, so a race fails closed and loud instead of poisoning history.
    """
    lock = oslock.RunLock.acquire(run_dir / FACT / ".lock", "HB-SUM-002")
    try:
        path = _segment_path(run_dir)
        writer = ledger.SegmentWriter.reopen(path) if path.is_file() else ledger.SegmentWriter.create(run_dir / FACT, SEGMENT_ID)
        try:
            return writer.append(ledger.stamp(row.to_record()))
        finally:
            writer.close()
    finally:
        lock.release()


def read_records(run_dir: Path) -> list[dict]:
    """Every verified `summary_records` row; [] when none exist. A tampered file raises HB-LED-002, the
    same tamper-evidence every other ledger-backed fact carries (the first invariant: a rewrite fails)."""
    path = _segment_path(run_dir)
    return ledger.read_segment(path) if path.is_file() else []


def latest_row(run_dir: Path, run_id: str, kind: str) -> Row | None:
    """The newest row for (run_id, kind); append order is chronological (ledger `seq`)."""
    rows = [Row.from_record(r) for r in read_records(run_dir) if r.get("summary_kind") == kind and r.get("run_id") == run_id]
    return rows[-1] if rows else None


def manifest_digest(manifest: tuple[dict, ...]) -> str:
    return hashlib.sha256(ledger.canonical({"manifest": list(manifest)})).hexdigest()


def state_for(row: Row | None, current_manifest_sha256: str | None) -> str:
    """design section 8's state table, S-NONE excepted by no row and S-STALE by a manifest mismatch (when
    `current_manifest_sha256` is given); otherwise the outcome names the state directly."""
    if row is None:
        return "S-NONE"
    if current_manifest_sha256 is not None and row.manifest_sha256 != current_manifest_sha256:
        return "S-STALE"
    return _OUTCOME_STATE[row.outcome]


# ------------------------------------------------------------------------------------------------ the manifest
def _entry(id_: str, data: bytes) -> dict:
    return {"id": id_, "sha256": hashlib.sha256(data).hexdigest()}


def _header_facts(view: views.RunView) -> bytes:
    """The header facts section 8 allows into the ranking manifest: run id, catalog version, pack revision --
    nothing else (never transcripts or agent text)."""
    pack_rev = (view.plan.get("pack") or {}).get("revision")
    return ledger.canonical({"run_id": view.run_id, "catalog_version": view.catalog_version, "pack_revision": pack_rev})


def _validity_counts(view: views.RunView) -> bytes:
    counts: dict[str, int] = {}
    for c in view.cells:
        counts[c.validity] = counts.get(c.validity, 0) + 1
    return ledger.canonical({"validity_counts": counts})


def _pack_effect_export(board_obj: board_mod.Board) -> bytes:
    """The pack-effect part of `board.export` (section 8's kind-2 manifest), not the whole export."""
    data = json.loads(board_mod.export(board_obj))
    return ledger.canonical({"pack_effect": data["pack_effect"], "method": data["method"],
                             "export_version": data["export_version"]})


def _cell_key(c: views.CellView) -> tuple[str, str]:
    """The pairing key across pack=on/off (label's own shape, `plan.py` `f"{task}.{combo}.pack-{pack}.r{rep}"`,
    read directly rather than re-derived): the task and repetition, within one combo."""
    parts = c.label.split(".")
    return (parts[0] if parts else "", parts[-1] if len(parts) > 1 else "")


def sample_pack_on_cells(view: views.RunView) -> tuple[str, ...]:
    """DR-R-4: per combo, the pack=on cells whose pass@1 differs from their paired pack=off cell, at most
    `SAMPLE_CAP` per combo, chosen by cell id. Deterministic: no randomness, ordered by combo then cell id."""
    off_by_key: dict[tuple[str, str, str], views.CellView] = {}
    for c in view.cells:
        if c.pack == "off":
            off_by_key[(c.combo, *_cell_key(c))] = c
    chosen: dict[str, list[str]] = {}
    for c in sorted(view.cells, key=lambda c: c.cell_id):
        if c.pack != "on":
            continue
        off = off_by_key.get((c.combo, *_cell_key(c)))
        if off is None:
            continue
        p1_on, p1_off = c.scores.get("pass_at_1"), off.scores.get("pass_at_1")
        if p1_on is None or p1_off is None or p1_on.value is None or p1_off.value is None or p1_on.value == p1_off.value:
            continue
        bucket = chosen.setdefault(c.combo, [])
        if len(bucket) < SAMPLE_CAP:
            bucket.append(c.cell_id)
    return tuple(cid for combo in sorted(chosen) for cid in chosen[combo])


def _excerpt_text(run_dir: Path | None, cell: views.CellView) -> str:
    """DR-R-4: the final assistant turn and the test output for one sampled cell, bounded. Read from the
    cell's archived working copy when present; "" otherwise (never fabricated).

    simplify: reads the archived attempt's log/text files directly rather than a per-cell "final answer"
    accessor (telemetry.normalize has none today). Upgrade trigger: a normalize.final_text-style accessor
    lands and this reads it instead, one definition of "the agent's final turn" (DM7).
    """
    if run_dir is None:
        return ""
    home = run_dir / "archive" / cell.cell_id / "attempt-1"
    if not home.is_dir():
        return ""
    texts = []
    for pattern in ("*.log", "*.txt"):
        for path in sorted(home.rglob(pattern)):
            try:
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(texts)[:EXCERPT_BOUND]


@dataclass(frozen=True)
class BuiltRequest:
    rendered: gw_request.Rendered
    manifest: tuple[dict, ...]
    sampling: dict | None
    withheld_excerpts: tuple[dict, ...]  # US-42 c2: [{"cell_id":.., "classes": [...]}], each dropped, not sent


def build_ranking_request(view: views.RunView, board_obj: board_mod.Board) -> BuiltRequest:
    segments = (("board-export", board_mod.export(board_obj)), ("header-facts", _header_facts(view)),
               ("validity-counts", _validity_counts(view)))
    manifest = tuple(_entry(i, d) for i, d in segments)
    rendered = gw_request.render_summary(RANKING_INSTRUCTIONS, segments)
    return BuiltRequest(rendered, manifest, None, ())


def build_pack_request(view: views.RunView, board_obj: board_mod.Board, run_dir: Path | None,
                       operator: egress.Operator, secrets: tuple[str, ...] = (),
                       canaries: tuple[str, ...] = ()) -> BuiltRequest:
    chosen = sample_pack_on_cells(view)
    by_id = {c.cell_id: c for c in view.cells}
    segments: list[tuple[str, bytes]] = [("pack-effect-export", _pack_effect_export(board_obj))]
    manifest_entries: list[dict] = [_entry(*segments[0])]
    withheld: list[dict] = []
    excerpt_lengths: dict[str, int] = {}
    for cid in chosen:
        text = _excerpt_text(run_dir, by_id[cid])[:EXCERPT_BOUND]
        verdict = egress.check(text, destination=MODEL, operator=operator, secrets=secrets, canaries=canaries)
        if verdict.withheld:
            withheld.append({"cell_id": cid, "classes": list(verdict.classes)})
            manifest_entries.append({"id": f"excerpt-{cid}", "withheld": egress.WITHHELD})
            continue
        segments.append((f"excerpt-{cid}", text.encode("utf-8")))
        manifest_entries.append(_entry(f"excerpt-{cid}", text.encode("utf-8")))
        excerpt_lengths[cid] = len(text)
    rendered = gw_request.render_summary(PACK_INSTRUCTIONS, tuple(segments))
    sampling = {"rule": SAMPLING_RULE, "cells": list(chosen), "excerpt_lengths": excerpt_lengths}
    return BuiltRequest(rendered, tuple(manifest_entries), sampling, tuple(withheld))


# ------------------------------------------------------------------------------- US-42 c1: the manifest check
_FENCE_RE = re.compile(r"<<<DATA [0-9a-f]{12} (?P<id>\S+)>>>\n(?P<body>.*?)<<<END DATA [0-9a-f]{12}>>>", re.DOTALL)


def extract_segments(request_text: str) -> dict[str, bytes]:
    """Every nonce-fenced data segment in a captured request payload, id -> raw bytes. Independent of
    `build_ranking_request`/`build_pack_request`: it reads only the bytes a backend actually received
    (US-42 c1's own requirement)."""
    return {m.group("id"): m.group("body").removesuffix("\n").encode("utf-8") for m in _FENCE_RE.finditer(request_text)}


def recompute_manifest(request_text: str) -> dict[str, str]:
    return {i: hashlib.sha256(b).hexdigest() for i, b in extract_segments(request_text).items()}


def manifest_matches(manifest: tuple[dict, ...], request_text: str) -> bool:
    """US-42 c1: recomputes sha256 over each captured segment and compares with the recorded manifest.
    False (refuses) on any mismatch: a tampered export byte changes a hash; a payload segment absent from
    the manifest, or a manifest entry the payload never carried, changes the key set."""
    recomputed = recompute_manifest(request_text)
    recorded = {e["id"]: e["sha256"] for e in manifest if e.get("sha256") is not None}
    return recomputed == recorded


# --------------------------------------------------------------------------------------------- the claim check
@dataclass(frozen=True)
class _PointLike:
    """A `stats.Measure` (cost_of_pass, tokens, wall...) normalised to the same `.point/.lo/.hi` shape a
    `stats.Interval` already has, so the number check reads one shape regardless of which board column a
    `board:` ref names (DM7: one comparison, not two)."""

    point: Decimal | None
    lo: Decimal | None = None
    hi: Decimal | None = None


@dataclass(frozen=True)
class Resolved:
    interval: object | None  # a stats.Interval, a _PointLike, or None (a cell/run id ref)
    decimals: int
    is_delta: bool  # pack:/cmp: refs: the zero rule and the printed-[lo,hi] rule apply
    kind: str  # "combo" (a metric ref) | "cell" | "run"


@dataclass(frozen=True)
class Failing:
    index: int
    rule: str


@dataclass(frozen=True)
class CheckResult:
    claims: tuple[dict, ...]
    failing: tuple[Failing, ...]

    @property
    def ok(self) -> bool:
        return not self.failing


def _decimals_for(measure: str) -> int:
    """The report's own displayed precision (phase4-statistics `:375`, design section 8): rates 2 decimals,
    composites/area deltas 1 decimal, tokens integer, USD 2 decimals."""
    if measure == "pass_at_1":
        return 2
    if "cost" in measure:
        return 2
    if "token" in measure:
        return 0
    return 1  # gated, area, composite deltas


def resolve_ref(ref: str, board_obj: board_mod.Board, view: views.RunView, comparison_obj=None) -> Resolved | None:
    """One claim ref resolved against the current pass's results (section 8's shape rule). None when it
    does not resolve: an unknown combo/pack/measure, or an id naming no cell and no run."""
    if ref.startswith("board:"):
        parts = ref.removeprefix("board:").split("|")
        if len(parts) != 3:
            return None
        combo, pack, measure = parts
        row = next((r for r in board_obj.rows if r.combo == combo and r.pack == pack), None)
        value = getattr(row, measure, None) if row is not None else None
        if value is None:
            return None
        if hasattr(value, "lo"):  # a stats.Interval (pass_at_1, gated)
            interval = value
        elif hasattr(value, "value"):  # a stats.Measure (cost_of_pass, tokens, wall_ms, ...)
            interval = _PointLike(value.value)
        else:
            return None
        return Resolved(interval, _decimals_for(measure), False, "combo")
    if ref.startswith("pack:"):
        parts = ref.removeprefix("pack:").split("|")
        if len(parts) != 2:
            return None
        combo, measure = parts
        row = next((r for r in board_obj.pack_effect.rows if r.combo == combo and r.measure == measure), None)
        if row is None:
            return None
        return Resolved(row.delta, _decimals_for(measure), True, "combo")
    if ref.startswith("cmp:"):
        if comparison_obj is None or isinstance(comparison_obj, str):
            return None
        parts = ref.removeprefix("cmp:").split("|")
        if len(parts) != 3:
            return None
        combo, pack, measure = parts
        row = next((r for r in comparison_obj.rows if r.combo == combo and r.pack == pack and r.measure == measure), None)
        if row is None:
            return None
        return Resolved(row.delta, _decimals_for(measure), True, "combo")
    if ref == view.run_id:
        return Resolved(None, 0, False, "run")
    if any(c.cell_id == ref for c in view.cells):
        return Resolved(None, 0, False, "cell")
    return None


_NUMBER_RE = re.compile(r"[-+−]?\d+(?:[.,]\d+)*%?")
_MINUS = str.maketrans({"−": "-"})
_COUNT_RE = re.compile(r"(\d+)\s+(combos?|cells?|runs?)\b", re.IGNORECASE)


def _round(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _candidate_value(tok: str) -> Decimal | None:
    body = tok.translate(_MINUS)
    pct = body.endswith("%")
    body = (body[:-1] if pct else body).replace(",", "")
    try:
        value = Decimal(body)
    except InvalidOperation:
        return None
    return value / 100 if pct else value


def _numbers_ok(text: str, resolved: list[Resolved]) -> bool:
    """US-42 c3's number check: every numeral in `text` (excluding the fixed 95% confidence level) must
    equal, after rounding to a cited ref's own displayed precision, that ref's point, lo or hi."""
    for m in _NUMBER_RE.finditer(text):
        tok = m.group(0)
        if tok == "95" and text[m.end():m.end() + 1] == "%":
            continue  # the fixed 95% bootstrap interval, not a data value (design section 8)
        value = _candidate_value(tok)
        if value is None:
            continue
        matched = False
        for r in resolved:
            if r.interval is None:
                continue
            for candidate in (r.interval.point, r.interval.lo, r.interval.hi):
                if candidate is not None and _round(Decimal(str(candidate)), r.decimals) == _round(value, r.decimals):
                    matched = True
                    break
            if matched:
                break
        if not matched:
            return False
    return True


def _counts_ok(text: str, refs: list[str], view: views.RunView) -> bool:
    """"A count ('2 combos', '36 cells') must equal a count in the cited result set" (section 8): the
    number of distinct combos, cells or the run named among the claim's own refs."""
    for m in _COUNT_RE.finditer(text):
        n, noun = int(m.group(1)), m.group(2).lower().rstrip("s")
        if noun == "combo":
            actual = len({r.split(":", 1)[1].split("|")[0] for r in refs if r.startswith(("board:", "pack:", "cmp:"))})
        elif noun == "cell":
            actual = sum(1 for r in refs if any(c.cell_id == r for c in view.cells))
        else:  # "run"
            actual = sum(1 for r in refs if r == view.run_id)
        if n != actual:
            return False
    return True


def _zero_rule_ok(claim: dict, resolved: dict[str, Resolved]) -> bool:
    """section 8's zero rule and its mirror, plus the observation/suggestion print-the-interval rule."""
    delta_refs = [resolved[r] for r in claim["refs"] if r in resolved and resolved[r].is_delta]
    nde = [no_detectable_effect(r.interval) for r in delta_refs]
    if claim["kind"] in ("effect", "suggestion") and any(nde):
        return False
    if claim["kind"] == "no_effect" and delta_refs and not any(nde):
        return False
    text = claim["text"].translate(_MINUS)
    for r in delta_refs:
        if r.interval.lo is None or r.interval.hi is None:
            continue
        lo_s, hi_s = f"{_round(r.interval.lo, r.decimals)}", f"{_round(r.interval.hi, r.decimals)}"
        if lo_s not in text or hi_s not in text:
            return False
    return True


def _suggestion_ok(claim: dict, resolved: dict[str, Resolved]) -> bool:
    if claim["kind"] != "suggestion":
        return True
    has_metric = any(resolved[r].kind == "combo" for r in claim["refs"] if r in resolved)
    has_id = any(resolved[r].kind in ("cell", "run") for r in claim["refs"] if r in resolved)
    return has_metric and has_id


def claim_check(answer: dict, board_obj: board_mod.Board, view: views.RunView, comparison_obj=None) -> CheckResult:
    """section 8's claim check: pure, offline, deterministic. Every failing claim names the one rule it
    failed first (resolution, then the zero rule, then numbers, then counts, then the suggestion shape)."""
    claims = tuple(answer.get("claims") or ())
    failing: list[Failing] = []
    for i, claim in enumerate(claims):
        refs = list(claim.get("refs") or [])
        resolved = {r: resolve_ref(r, board_obj, view, comparison_obj) for r in refs}
        if not refs or any(v is None for v in resolved.values()):
            failing.append(Failing(i, "unresolved ref"))
            continue
        if not _zero_rule_ok(claim, resolved):
            failing.append(Failing(i, "zero rule"))
            continue
        metric_resolved = [v for v in resolved.values() if v.kind == "combo"]
        if not _numbers_ok(claim["text"], metric_resolved):
            failing.append(Failing(i, "number check"))
            continue
        if not _counts_ok(claim["text"], refs, view):
            failing.append(Failing(i, "count check"))
            continue
        if not _suggestion_ok(claim, resolved):
            failing.append(Failing(i, "suggestion shape"))
            continue
    return CheckResult(claims, tuple(failing))


# ---------------------------------------------------------------------------------------- the seven-step path
def refuse_if_live(roots: tuple[Path, ...]) -> None:
    """DR-R-5: `bench report --summaries` refuses while any run is live -- its own call site, its own code
    (HB-SUM-001, ruling R-81 condition 3), reusing the one liveness scan (`gateway.backend.scan_runs`)
    HB-GRD-005 also reads from (DM7)."""
    _found, live = gw_backend.scan_runs(roots)
    if live:
        raise BenchError("HB-SUM-001", f"bench report --summaries refused while a run is live; scanned "
                                       f"{', '.join(map(str, roots))}; {'; '.join(live)}")


def generate(kind: str, run_dir: Path, view: views.RunView, board_obj: board_mod.Board, backend,
            operator: egress.Operator, model: str = MODEL, secrets: tuple[str, ...] = (),
            canaries: tuple[str, ...] = ()) -> Row:
    """One summary generation attempt (section 8's seven-step call path). `backend` is the `ReplayBackend`
    only in R7 (R8 wires the live `Headless` gateway); every outcome appends exactly one row."""
    built = (build_ranking_request(view, board_obj) if kind == KIND_RANKING
            else build_pack_request(view, board_obj, run_dir, operator, secrets, canaries))
    manifest_sha = manifest_digest(built.manifest)
    request_sha = hashlib.sha256(built.rendered.text.encode("utf-8")).hexdigest()
    schema_sha = gw_schema.schema_sha256(gw_schema.CLAIMS_SCHEMA_PATH)
    egress_records: list[dict] = [{"cell_id": w["cell_id"], "classes": w["classes"]} for w in built.withheld_excerpts]

    def row(outcome: str, **kw) -> Row:
        r = Row(run_id=view.run_id, pass_id=view.grading_id or "", kind=kind, model=model, manifest=built.manifest,
               manifest_sha256=manifest_sha, request_sha256=request_sha,
               template_version=gw_request.SUMMARY_TEMPLATE_VERSION, schema_sha256=schema_sha, outcome=outcome,
               egress=tuple(egress_records), sampling=built.sampling, **kw)
        append(run_dir, r)
        return r

    verdict = egress.check(built.rendered.text, destination=model, operator=operator, secrets=secrets, canaries=canaries)
    v_record = verdict.record()
    egress_records.append({"request": 1, "destination": v_record["destination"],  # no bool in canonical (ADR-0006:49)
                           "payload_sha256": v_record["payload_sha256"], "classes": list(v_record["classes"]),
                           "scanned": list(v_record["scanned"])})
    if verdict.withheld:
        return row("withheld")
    try:
        reply = verdict.release(lambda payload: backend.judge(payload, f"summary-{kind}"))
    except gw_backend.BackendDown:
        reply = None
    if reply is None:
        return row("backend_unavailable")
    text = gw_backend.final_text(reply)
    try:
        answer = json.loads(text) if text is not None else None
    except ValueError:
        answer = None
    if answer is None or gw_schema.check_shape(answer, gw_schema.CLAIMS_SCHEMA_PATH):
        return row("refused")
    check = claim_check(answer, board_obj, view)
    claim_dicts = tuple(dict(c) for c in check.claims)
    if check.ok:
        return row("published", claims=claim_dicts)
    return row("not_published", claims=claim_dicts,
              failing_claims=tuple({"id": f.index, "rule": f.rule} for f in check.failing))
