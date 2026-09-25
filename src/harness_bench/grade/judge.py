"""Rubric judging by two blind judges, one per vendor, synthesized per item (design phase3-gateway-judges sections
4.1, 6, 10; graders design "Judged" and seam S-5; W3-GW-I slice 3). Spec: S-09 (docs/specs/README.md).

Metrics: honest_completion_claims, error_handling, goal_drift_slope, unrequested_behaviour, assumption_disclosure,
spec_quality, adr_quality, handoff_fidelity, mast_failure_codes.

- When judges run (section 6, R-58 DR-2): the in-run pass (`IN_RUN`) makes no lookup, no call and no row, and
  every judged metric is NA `judge calls not allowed in this pass`; `bench grade` reads the verdict store only (a miss
  is `not_allowed`, counted by `misses`); only `bench grade --allow-model-calls` (`calling`) may spawn a judge, inside
  the gateway's `judge_pass`, which refuses while any run is live (HB-GRD-005).
- The jury is `bench/gateway.yaml` (`config.load_gateway`), in order: the second entry is the second judge. With no
  stipulation every judged metric is NA `no qualified judge`.
- A metric whose catalog entry has no `rubrics` entry for the cell's task is NA `no rubric for this task` (R-59 c2,
  R-67, R-68), with no lookup.
- A metric with a rubric: one lookup per judge through `gateway.pipeline.run` (blinded, scanned, keyed, egress-checked;
  the store read first). Each lookup writes one `verdict_uses` row per rubric item (ADR-0006 Amendment 3), and a
  call's `model_calls` rows (principal gateway) go into the pass's `model_calls`. Both go through `CellInput.emit`
  into the pass's own segments, which the pass seals.
- Synthesis (section 10.1): both verdicts recorded and at most 1 step apart give their mean, a decimal at scale 1; 2
  steps apart is NA `judges disagree by 2 steps`; a judge not recorded is named with its outcome and code. While the
  second judge is not qualified, or not stipulated, every item is NA `second judge not qualified` (R-63 b): a single
  verdict is never a judged score. The metric (section 10.2) is the sum over the items only when every item is
  synthesized, else NA naming the items.
- There is no temperature: neither CLI has the flag (section 8.1). A re-grade is deterministic because it reads the
  verdict store and never calls on a hit (US-26; T-GW-12).
- Judges never see the harness or model name (the scrub and the scan, section 7.3).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from harness_bench import config, egress, profiles, tools, views
from harness_bench.gateway import pipeline, scrub
from harness_bench.gateway.backend import Launch, ReplayBackend, judge_pass, run_roots
from harness_bench.grade import CellInput, GraderFn, Score

NO_JUDGE = "no qualified judge"
NOT_ALLOWED = "judge calls not allowed in this pass"
NO_RUBRIC = "no rubric for this task"
SECOND_NOT_QUALIFIED = "second judge not qualified"
DISAGREE = "judges disagree by 2 steps"
RECORDED = ("hit", "stored", "race_lost")
_ITEM = re.compile(r"^(\d+)\. ", re.MULTILINE)  # a rubric item line: "1. **Heap family.** ..."
_SCALE = Decimal("0.1")  # scale 1


@dataclass(frozen=True)
class Calls:
    """What a pass that may call a judge supplies (slice 4's `bench grade --allow-model-calls`): where a call runs,
    the pinned CLI and profile per harness, and whom egress protects. Never read from a committed file (R-42)."""

    cells_root: Path
    builds: Mapping[str, tools.Build]  # harness -> the pinned CLI
    profiles: Mapping[str, profiles.Profile]  # harness -> its profile (the credential to copy)
    operator: egress.Operator
    secrets: tuple[str, ...] = ()
    canaries: tuple[str, ...] = ()
    prefix: tuple[str, ...] = ()  # argv before the executable: empty for the pinned exe


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """The registered grader (runner.GRADERS), `bench grade` without the flag: it reads the verdict store only."""
    return grade(inp, None)


def in_run(inp: CellInput) -> dict[str, Score]:
    """The in-run pass (`bench run`'s grading, section 6): no lookup, no call, no `verdict_uses` row."""
    return dict.fromkeys(inp.metrics, Score(None, NOT_ALLOWED))


IN_RUN: Mapping[str, GraderFn] = {"judge": in_run}  # runner.run_pass's `judging` for the in-run pass


def calling(calls: Calls) -> dict[str, GraderFn]:
    """runner.run_pass's `judging` for `bench grade --allow-model-calls`: the only pass that may spawn a judge."""
    return {"judge": lambda inp: grade(replace(inp, allow_model_calls=True), calls)}


def misses(run_dir: Path, grading_id: str) -> int:
    """The pass's judge calls that a cache-only pass could not make (`not_allowed`), counted as calls, never as rows
    (`views.judge_calls`; US-26 c2)."""
    rows = [r for r in views.rows(run_dir, "verdict_uses") if r["grading_id"] == grading_id]
    return views.judge_calls(rows).get(("not_allowed", None), 0)


def grade(inp: CellInput, calls: Calls | None) -> dict[str, Score]:
    """One Score per applicable judged metric of the cell; `calls` is required when the pass may call a judge."""
    stipulation = config.load_gateway(inp.root)
    if stipulation is None:  # bench/gateway.yaml is not in the tree (R-70)
        return dict.fromkeys(inp.metrics, Score(None, NO_JUDGE))
    if inp.emit is None or (inp.allow_model_calls and calls is None):
        raise ValueError("the judge grader needs the pass's emit, and a call environment when calls are allowed")
    task = inp.cell["task"]
    out = {m: Score(None, NO_RUBRIC) for m, entry in inp.metrics.items() if task not in (entry.get("rubrics") or {})}
    judged = sorted(m for m in inp.metrics if m not in out)
    if not judged:
        return out
    grading_id = inp.out_dir.parents[1].name  # out_dir is run_dir/grading/<grading_id>/<cell_id>/<grader>
    archive = inp.run_dir / "grading" / grading_id / "gateway"  # the call records (section 8.2; store._vouches)
    roots = run_roots(inp.root, inp.run_dir.parent)  # every worktree's runs/ plus --runs (section 6, R-65)
    ctx = pipeline.Context(
        store=inp.root / "cache" / "verdicts", known_roots=roots, own_run=inp.run_dir,
        stored_by={"ledger": "run", "ledger_id": inp.plan["run_id"], "grading_or_calibration_id": grading_id},
        denylist=scrub.denylist(inp.root, inp.plan), allow_model_calls=inp.allow_model_calls,
        operator=calls.operator if calls else None, secrets=calls.secrets if calls else (),
        canaries=calls.canaries if calls else ())
    jury = [(entry, _judge(inp.root, entry)) for entry in stipulation["judges"]]
    backends = [_backend(e, j, calls, grading_id, archive, stipulation["call_timeout_seconds"]) for e, j in jury]
    names = tuple(sorted({n for e, j in jury if j.qualified and (n := calls.profiles[e["harness"]].credential_name)})
                  ) if calls else ()
    with judge_pass(calls.cells_root, grading_id, names, roots) if calls else nullcontext():
        for metric in judged:
            inputs = _inputs(inp, inp.metrics[metric], task)
            results = [(j.model, pipeline.run(j, inputs, ctx, b)) for (_, j), b in zip(jury, backends, strict=True)]
            for model, result in results:
                _record(inp, grading_id, metric, inputs.items, model, result)
            second = results[1] if len(results) > 1 else None
            out[metric] = metric_score({n: item_score(results[0], second, n) for n in range(1, inputs.items + 1)})
    return out


def _judge(root: Path, entry: Mapping) -> pipeline.Judge:
    """The pipeline's judge for one stipulation entry: the pin plus the harness profile's declared auxiliaries."""
    aux = profiles.load(root, entry["harness"]).auxiliary_models
    return pipeline.Judge(model=entry["model"], invocation_sha256=entry["invocation_sha256"],
                          allowed_models=(entry["model"], *aux), qualified=entry["qualified"])


def _backend(entry: Mapping, j: pipeline.Judge, calls: Calls | None, grading_id: str, archive: Path,
             timeout: float) -> Launch | ReplayBackend:
    """Each qualified judge's Launch (plain data: the pipeline makes it a call only inside the egress release). A
    judge that is never called (unqualified, or a pass with no call environment) gets a backend that is down, so a
    call that reached it would close as HB-GW-001, never as a verdict."""
    if calls is None or not j.qualified:
        return ReplayBackend({}, archive, down=True)
    harness = entry["harness"]
    return Launch(profile=calls.profiles[harness], build=calls.builds[harness], model=entry["model"],
                  cells_root=calls.cells_root, grading_id=grading_id, archive=archive, timeout=timeout,
                  prefix=calls.prefix)


def _inputs(inp: CellInput, entry: Mapping, task: str) -> pipeline.Inputs:
    """The request's inputs (section 7.1): the catalog `note:` as the preamble (R-64), the rubric file, and each
    `artifact:` file from the cell's archived working copy, in catalog order.

    assume: the catalog fields are `rubrics: {<task>: <file under bench/rubrics/>}` (graders design, catalog 0.4) and
    `artifact: [<path>]` (design section 13); `bench/metrics.yaml` carries neither yet (slice 5 adds them). Confirm
    against CORE s2's `validate_metrics` at the join. Breaks: another field name reads as no rubric (NA `no rubric for
    this task`, fail-closed).
    assume: an artifact file the cell did not write is sent empty, so the judge scores it as missing (the rubric's 0).
    Confirm: the Owner, before the first C1 judge pass. Breaks: an empty file and a missing file score alike."""
    rubric = (inp.root / "bench" / "rubrics" / entry["rubrics"][task]).read_text(encoding="utf-8")
    numbers = [int(n) for n in _ITEM.findall(rubric)]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"the rubric for {entry['id']} does not number its items 1..n")
    ws = inp.archive / "ws"
    artifacts = tuple((path, (ws / path).read_bytes() if (ws / path).is_file() else b"") for path in entry["artifact"])
    return pipeline.Inputs(preamble=entry.get("note") or "", rubric=rubric, items=len(numbers), artifacts=artifacts)


def _record(inp: CellInput, grading_id: str, metric: str, items: int, model: str, result: pipeline.Result) -> None:
    """One `verdict_uses` row per rubric item of one judge's lookup, then the call's `model_calls` rows (section 4.2:
    a call that happened writes its rows whatever its outcome; a hit, a miss or a pre-spawn failure made none)."""
    for n in range(1, items + 1):
        inp.emit("verdict_uses", {"kind": "verdict_use", "run_id": inp.plan["run_id"], "grading_id": grading_id,
                                  "cell_id": inp.cell["cell_id"], "item_id": f"{metric}#{n}",
                                  "judge_or_matcher": model, "outcome": result.outcome, "code": result.code,
                                  "cache_key": result.cache_key, "entry_sha256": result.entry_sha256})
    for row in result.model_calls:
        inp.emit("model_calls", row)


def synthesize(a: int, b: int) -> Score:
    """Two recorded verdicts on one item (section 10.1): the mean at scale 1 within one step, else NA."""
    if abs(a - b) <= 1:
        return Score((Decimal(a + b) / 2).quantize(_SCALE), None)
    return Score(None, DISAGREE)


def _verdict(result: pipeline.Result, item: int) -> int:
    return next(v["score"] for v in result.verdicts if v["item"] == item)


def item_score(first: tuple[str, pipeline.Result], second: tuple[str, pipeline.Result] | None, item: int) -> Score:
    """One rubric item from the jury's lookups, each `(judge model, result)`; `second` is None when the stipulation
    names one judge."""
    if second is None or second[1].code == "HB-GW-007":  # R-63 (b): a single verdict is never a judged score
        return Score(None, SECOND_NOT_QUALIFIED)
    for model, result in (first, second):
        if result.outcome not in RECORDED:
            return Score(None, f"judge {model}: {result.outcome}" + (f" {result.code}" if result.code else ""))
    return synthesize(_verdict(first[1], item), _verdict(second[1], item))


def metric_score(items: Mapping[int, Score]) -> Score:
    """The metric (section 10.2): the sum of the items when every item is synthesized, else NA naming the items that
    are not, grouped by reason in item order."""
    if all(s.value is not None for s in items.values()):
        return Score(sum((s.value for s in items.values()), Decimal("0.0")), None)
    by_reason: dict[str, list[str]] = {}
    for n in sorted(items):
        if items[n].value is None:
            by_reason.setdefault(items[n].reason, []).append(str(n))
    return Score(None, "; ".join(f"items {', '.join(ns)}: {reason}" for reason, ns in by_reason.items()))
