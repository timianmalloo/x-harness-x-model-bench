"""Calibration and kappa (design phase3-gateway-judges sections 4.4 and 11, row s5; R-58 c5, R-62 a3, R-72).

- **Unit:** one calibration item is one (artifact, rubric item) pair (spec `:208`). The artifact is two files, as the
  W3-CAL manifest's layout names them: `path` is rendered as docs/architecture.md and `code` as priority_queue.py,
  the catalog entry's `artifact:` list (design section 7.1). The request is the production template with the full
  rubric (`gateway.request`), so a verdict set scores every rubric item; only the verdict on the item's own
  `rubric_item` is compared (T-GW-17b).
- **Labels are file-conditional (R-72 item 4):** with no `labels.yaml` the pass runs and `calibration.started` records
  `labels_sha256: null`; a present file must match the manifest all or none (a duplicate, a missing id, an unknown id,
  a score outside {0, 1, 2}, or no rows at all) or the pass is refused with HB-CAL-001 before any spawn. A label is
  human (R-72): nothing in this module reads a label from the manifest.
- **The ledger:** `runs/calibration-<task>-<rubric sha256[:8]>/`, the run layout (`events/`, `model_calls/`,
  `calibration_uses/`, `grading/<calibration_id>/gateway/<call>/record.jsonl`), so the store's provenance check reads
  it as it reads a run (`store._vouches`). It has no plan.json, so no run scan takes it for a run (T-GW-19c).
  `calibration_uses`: one row per lookup of one judge's verdict set for one item, with its key and entry hash.
- **kappa:** Cohen's, unweighted, over {0, 1, 2}, exact in rationals, rounded half-even to a decimal string at scale
  3; `p_e = 1` is NOT_RECORDED `kappa undefined: one category`; always reported with n and exact agreement, never
  gated (spec `:1173`). Derived at report time from the recorded rows, the entries they name and the labels file whose
  sha256 `calibration.started` names; never stored (DM7).
- **The header line (R-72 item 6):** `n = <items> · inter-judge κ: <kappa> | not recorded: second judge not qualified
  · vs human labels: <per judge> | not recorded: <reason>`, with the stale and relabelled states of design section 11
  and the R-72 condition 4 disclosures. The R-62 a3 sentence is `DISCLOSURE`.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import yaml

from harness_bench import config, ledger
from harness_bench.errors import BenchError
from harness_bench.gateway import pipeline, request, schema, scrub
from harness_bench.gateway.backend import judge_pass, run_roots
from harness_bench.grade import judge

SCORES = (0, 1, 2)
NO_LABELS = "no human labels (operator declined 2026-09-25)"  # R-72 condition 1: terminal, never "pending"
ONE_CATEGORY = "kappa undefined: one category"
NO_PAIRS = "no recorded pairs"
SECOND_NOT_QUALIFIED = "second judge not qualified"
STALE = "calibration stale"
CHANGED = "labels changed since calibration"
NO_PASS = "no calibration pass"
POST_DATED = "labels post-date the calibration verdicts"
UNBLINDED = "labeller blinding: not recorded"
DISCLOSURE = "Calibration items were written by claude-opus-5-5; the Anthropic judge is a Claude model."  # R-62 a3
LAYOUT = (("path", "docs/architecture.md"), ("code", "priority_queue.py"))  # manifest field -> judged artifact path
FACTS = ("events", "model_calls", "calibration_uses")
BOUND = ("template_version", "scrub_version", "schema_sha256", "rubric_sha256", "invocations")  # design 11, A6


# ------------------------------------------------------------------------------------------------------ kappa
@dataclass(frozen=True)
class Kappa:
    n: int
    exact: int
    value: str | None  # a decimal string at scale 3, or None with a reason
    reason: str | None

    def text(self) -> str:
        shown = self.value if self.value is not None else f"not recorded: {self.reason}"
        return f"{shown} (n = {self.n}, exact {self.exact})"


def kappa(pairs: Sequence[tuple[int, int]]) -> Kappa:
    """Cohen's kappa over {0, 1, 2}: (p_o - p_e) / (1 - p_e), p_e = sum over k of p1(k) * p2(k); exact, then half-even
    at scale 3 (`round` of a Fraction rounds half to even)."""
    n = len(pairs)
    exact = sum(1 for a, b in pairs if a == b)
    if n == 0:
        return Kappa(0, 0, None, NO_PAIRS)
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    p_o = Fraction(exact, n)
    p_e = sum((Fraction(first[k], n) * Fraction(second[k], n) for k in SCORES), Fraction(0))
    if p_e == 1:
        return Kappa(n, exact, None, ONE_CATEGORY)
    value = (p_o - p_e) / (1 - p_e)
    return Kappa(n, exact, str(Decimal(round(value * 1000)).scaleb(-3)), None)


# ----------------------------------------------------------------------------------------- manifest and labels
@dataclass(frozen=True)
class Item:
    id: str
    rubric_item: int
    artifacts: tuple[tuple[str, bytes], ...]  # (judged path, raw bytes), in LAYOUT order


@dataclass(frozen=True)
class Labels:
    sha256: str
    scores: dict[str, int]
    blind: bool | None  # the labeller's file-level attestation (R-72 condition 4); None when absent
    earliest_utc: str | None  # the earliest `labelled_utc`; None when any row lacks one


def _where(task: str) -> str:
    return f"bench/calibration/{task}/labels.yaml"


def items(root: Path, task: str) -> tuple[bytes, list[Item]]:
    """The manifest's bytes and its items, each with its two artifact files read."""
    folder = root / "bench" / "calibration" / task
    raw = (folder / "manifest.yaml").read_bytes()
    rows = (yaml.safe_load(raw) or {}).get("items") or []
    return raw, [Item(str(r["id"]), int(r["rubric_item"]),
                      tuple((path, (folder / r[field]).read_bytes()) for field, path in LAYOUT)) for r in rows]


def load_labels(root: Path, task: str, ids: set[str]) -> Labels | None:
    """None when the labels file is absent. A present file matches the manifest all or none (R-72 item 4), else
    HB-CAL-001 names every problem."""
    path = root / "bench" / "calibration" / task / "labels.yaml"
    if not path.is_file():
        return None
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    rows = data.get("labels") if isinstance(data, dict) else None
    problems: list[str] = []
    if not isinstance(rows, list) or not rows:
        problems.append("no label rows (an empty file is not an absent file)")
        rows = []
    rows = [r if isinstance(r, dict) else {} for r in rows]
    seen = [str(r.get("id")) for r in rows]
    counts = Counter(seen)
    problems += [f"duplicate id {i}" for i in sorted(i for i, c in counts.items() if c > 1)]
    problems += [f"missing id {i}" for i in sorted(ids - set(seen))] if rows else []
    problems += [f"unknown id {i}" for i in sorted(set(seen) - ids)]
    for r in rows:
        score = r.get("score")
        if isinstance(score, bool) or score not in SCORES:
            problems.append(f"{r.get('id')}: score {score} is not 0, 1 or 2")
    if problems:
        raise BenchError("HB-CAL-001", f"{_where(task)} does not match the manifest (R-72: all or none): "
                                       + "; ".join(problems))
    dates = [r.get("labelled_utc") for r in rows]
    blind = data.get("blind")
    return Labels(hashlib.sha256(raw).hexdigest(), {str(r["id"]): r["score"] for r in rows},
                  blind if isinstance(blind, bool) else None,
                  min(dates) if all(isinstance(d, str) for d in dates) else None)


# ------------------------------------------------------------------------------------------ the calibration pass
def _entry(root: Path, task: str) -> dict:
    """The judged catalog entry whose `rubrics:` names the task; its `artifact:` must be the calibration layout."""
    catalog = config.load_yaml(root / "bench" / "metrics.yaml")
    for area in (catalog.get("areas") or {}).values():
        for m in area.get("metrics") or []:
            if task in (m.get("rubrics") or {}):
                if list(m.get("artifact") or []) != [path for _, path in LAYOUT]:
                    raise BenchError("HB-USR-002", f"{m['id']}: artifact {m.get('artifact')} is not the calibration "
                                                   f"layout {[path for _, path in LAYOUT]}")
                return m
    raise BenchError("HB-USR-002", f"no catalog metric names a rubric for {task}")


def _binding(rubric: str, stipulation: Mapping) -> dict:
    """What a calibration binds (design section 11, directive A6): a change of any value makes it stale."""
    return {"template_version": request.TEMPLATE_VERSION, "scrub_version": scrub.SCRUB_VERSION,
            "schema_sha256": schema.schema_sha256(), "rubric_sha256": hashlib.sha256(rubric.encode()).hexdigest(),
            "invocations": [j["invocation_sha256"] for j in stipulation["judges"]]}


def _denylist(root: Path) -> tuple[str, ...]:
    """The scrub's entries with every committed matrix's combos: a calibration has no plan of its own."""
    combos = []
    for path in sorted((root / "bench").glob("matrix*.yaml")):
        combos += (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("combos") or []
    return scrub.denylist(root, {"matrix": {"combos": combos}})


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run(root: Path, runs: Path, calls: judge.Calls, task: str = "C1") -> str:
    """One calibration pass; returns its calibration id. The labels check runs first: a refused file spawns nothing
    and writes no ledger. Each spawn goes through the gateway (`judge_pass`: the live-run refusal HB-GRD-005, the
    cells-root check, the pass lock, the credential sweep); a hit reads the store and calls nothing."""
    manifest, cal_items = items(root, task)
    labels = load_labels(root, task, {i.id for i in cal_items})
    stipulation = config.load_gateway(root)
    if stipulation is None:
        raise BenchError("HB-USR-002", "bench/gateway.yaml is not in the tree: there is no judge to calibrate")
    entry = _entry(root, task)
    rubric, n_items = judge.rubric_of(root, entry, task)
    binding = _binding(rubric, stipulation)
    folder = runs / f"calibration-{task}-{binding['rubric_sha256'][:8]}"
    cal_id = f"cal-{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}-{secrets.token_hex(3)}"
    archive = folder / "grading" / cal_id / "gateway"
    roots = run_roots(root, runs)
    ctx = pipeline.Context(
        store=root / "cache" / "verdicts", known_roots=roots, own_run=folder,
        stored_by={"ledger": "calibration", "ledger_id": folder.name, "grading_or_calibration_id": cal_id},
        denylist=_denylist(root), allow_model_calls=True, operator=calls.operator, secrets=calls.secrets,
        canaries=calls.canaries)
    jury = [(e, judge._judge(root, e)) for e in stipulation["judges"]]
    backends = [judge._backend(e, j, calls, cal_id, archive, stipulation["call_timeout_seconds"]) for e, j in jury]
    names = tuple(sorted({n for e, j in jury if j.qualified and (n := calls.profiles[e["harness"]].credential_name)}))
    with judge_pass(calls.cells_root, cal_id, names, roots):
        writers = {fact: ledger.SegmentWriter.create(folder / fact, cal_id) for fact in FACTS}
        try:
            writers["events"].append({
                "kind": "calibration.started", "calibration_id": cal_id, "task": task, "started_utc": _utc(),
                "started_ns": time.time_ns(), "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "labels_sha256": labels.sha256 if labels else None, **binding,
                "judges": [{"model": j["model"], "harness": j["harness"], "invocation_sha256": j["invocation_sha256"]}
                           for j in stipulation["judges"]]})
            for item in cal_items:
                inputs = pipeline.Inputs(preamble=entry.get("note") or "", rubric=rubric, items=n_items,
                                         artifacts=item.artifacts)
                for (_, j), b in zip(jury, backends, strict=True):
                    result = pipeline.run(j, inputs, ctx, b)
                    writers["calibration_uses"].append({
                        "kind": "calibration_use", "calibration_id": cal_id, "item_id": item.id,
                        "rubric_item": item.rubric_item, "judge_or_matcher": j.model, "outcome": result.outcome,
                        "code": result.code, "cache_key": result.cache_key, "entry_sha256": result.entry_sha256})
                    for row in result.model_calls:
                        writers["model_calls"].append(row)
            heads = {fact: writers[fact].seal() for fact in FACTS if fact != "events"}
            writers["events"].append({"kind": "calibration.completed", "calibration_id": cal_id,
                                      "completed_utc": _utc(), "heads": heads})
            writers["events"].seal()
        finally:
            for w in writers.values():
                w.close()
    return cal_id


# --------------------------------------------------------------------------------------------- the header line
def _latest(runs: Path, task: str) -> tuple[Path, dict] | None:
    """(ledger folder, calibration.started) of the task's latest completed calibration pass, or None."""
    done = []
    for folder in sorted(runs.glob(f"calibration-{task}-*")) if runs.is_dir() else []:
        for seg in sorted((folder / "events").glob("*.jsonl")):
            rows = ledger.read_segment(seg)
            first = next((r for r in rows if r.get("kind") == "calibration.started"), None)
            if first and any(r.get("kind") == "calibration.completed" for r in rows):
                done.append((first["started_ns"], folder, first))
    return max(done, key=lambda d: d[0])[1:] if done else None


def _verdicts(store: Path, row: Mapping) -> dict[int, int] | None:
    """A recorded row's verdict set, item -> score, from the entry it names; None when the entry is missing or its
    bytes are not the recorded entry_sha256."""
    if row.get("outcome") not in judge.RECORDED:
        return None
    path = store / f"{row['cache_key']}.json"
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["entry_sha256"]:
        return None
    return {v["item"]: v["score"] for v in json.loads(path.read_text(encoding="utf-8"))["verdicts"]}


def header_line(root: Path, runs: Path, task: str) -> str:
    """The header's calibration line for one task (design section 12; R-72 item 6)."""
    found = _latest(runs, task)
    if found is None:
        return f"not recorded: {NO_PASS}"
    folder, started = found
    stipulation = config.load_gateway(root)
    entry = _entry(root, task)
    rubric, _ = judge.rubric_of(root, entry, task)
    if stipulation is None or {k: started.get(k) for k in BOUND} != _binding(rubric, stipulation):
        return f"not recorded: {STALE}"
    _, cal_items = items(root, task)
    store = root / "cache" / "verdicts"
    verdict: dict[tuple[str, str], int] = {}
    for row in ledger.read_segment(folder / "calibration_uses" / f"{started['calibration_id']}.jsonl"):
        scores = _verdicts(store, row) if row.get("kind") == "calibration_use" else None
        if scores is not None and row["rubric_item"] in scores:
            verdict[(row["item_id"], row["judge_or_matcher"])] = scores[row["rubric_item"]]
    judges = [j for j in stipulation["judges"] if j["qualified"]]
    if len(stipulation["judges"]) < 2 or not stipulation["judges"][1]["qualified"]:
        inter = f"not recorded: {SECOND_NOT_QUALIFIED}"
    else:
        a, b = (j["model"] for j in stipulation["judges"])
        inter = kappa([(verdict[(i.id, a)], verdict[(i.id, b)]) for i in cal_items
                       if (i.id, a) in verdict and (i.id, b) in verdict]).text()
    return f"n = {len(cal_items)} · inter-judge κ: {inter} · vs human labels: " + \
        _human(root, task, started, cal_items, judges, verdict)


def _human(root: Path, task: str, started: Mapping, cal_items: list[Item], judges: list[Mapping],
           verdict: Mapping[tuple[str, str], int]) -> str:
    try:
        labels = load_labels(root, task, {i.id for i in cal_items})
    except BenchError:
        return f"not recorded: {CHANGED}"  # the recorded file matched the manifest, so this one is not it
    if (labels.sha256 if labels else None) != started.get("labels_sha256"):
        return f"not recorded: {CHANGED}"
    if labels is None:
        return f"not recorded: {NO_LABELS}"
    per_judge = "; ".join(
        f"{j['model']} κ " + kappa([(labels.scores[i.id], verdict[(i.id, j['model'])]) for i in cal_items
                                    if (i.id, j["model"]) in verdict]).text() for j in judges)
    notes = ([UNBLINDED] if labels.blind is not True else []) + \
        ([POST_DATED] if labels.earliest_utc is not None and labels.earliest_utc > started["started_utc"] else [])
    return " · ".join([per_judge, *notes])
