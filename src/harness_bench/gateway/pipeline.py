"""One judge lookup for one (artifact, rubric) request: the section 8 pipeline, offline half (slice 1).

The steps run in a fixed order, and the first failing step is the one recorded (design section 4.1):
1. bound (HB-GW-008); 2. render in the section 7.2 order; 3. the independent scan of the whole request (HB-GW-004);
4. key and lookup: a hit is accepted only through `store.lookup`'s section 9.3 check (HB-GW-005), a miss without
   `--allow-model-calls` is `not_allowed`, and an orphan is moved aside before a fresh call;
5. `egress.check(...).release(...)`: a withheld request never reaches the backend (HB-GW-009); a backend that is
   down is HB-GW-001, never a 0;
6. read and validate the answer against the schema file (HB-GW-002); a served model other than the pin is HB-GW-003;
7. write-once: `stored`, `race_lost`, or a store write error (HB-GW-001).

Every result is `(outcome, code)` from the closed sets below. A NOT_RECORDED result (`failed`, `not_allowed`)
carries no verdicts, no key and no entry hash. Writing the `verdict_uses` rows is grade/judge.py's (slice 3).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from harness_bench import egress
from harness_bench.gateway import request, schema, scrub, store
from harness_bench.gateway.backend import (
    Backend,
    BackendDown,
    Headless,
    Launch,
    Reply,
    read_reply,
)

OUTCOMES = ("hit", "stored", "race_lost", "not_allowed", "failed")
CODES = {  # design section 17; slice 1 reaches 001, 002, 003, 004, 005, 008, 009
    "HB-GW-001": "judge unavailable: CLI error, timeout, provider error, breaker open, or a store write error "
                 "other than a lost race",
    "HB-GW-002": "invalid output",
    "HB-GW-003": "served model not the pin",
    "HB-GW-004": "blinding scan hit",
    "HB-GW-005": "store entry invalid, or not matched by its storing row",
    "HB-GW-006": "tool event in a judge call",
    "HB-GW-007": "judge not qualified",
    "HB-GW-008": "artifact over the bound or not UTF-8",
    "HB-GW-009": "withheld: sensitive content",
    "HB-GW-010": "leftover credential copy (a verify error)",
    "HB-GW-011": "judge build changed",
}


@dataclass(frozen=True)
class Judge:
    model: str  # the stipulated model id; also the egress destination
    invocation_sha256: str  # section 9.1; built from the argv template in slice 2
    allowed_models: tuple[str, ...]  # the pin plus declared auxiliaries (US-11)
    qualified: bool  # gateway.yaml `qualified`, set by the Leader from a probe of the exact invocation (section 8.4)


@dataclass(frozen=True)
class Inputs:
    preamble: str  # the catalog entry's note (R-64)
    rubric: str
    items: int  # rubric items, numbered 1..items
    artifacts: tuple[tuple[str, bytes], ...]  # (catalog path, raw archived bytes), in catalog order


@dataclass(frozen=True)
class Context:
    store: Path  # cache/verdicts
    known_roots: tuple[Path, ...]  # the runs/ of every worktree (section 6)
    own_run: Path | None  # this run's folder, for an orphaned entry (section 9.3)
    stored_by: dict  # {ledger, ledger_id, grading_or_calibration_id} of this pass
    denylist: tuple[str, ...]
    allow_model_calls: bool
    operator: egress.Operator
    secrets: tuple[str, ...] = ()
    canaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class Result:
    outcome: str
    code: str | None = None
    cache_key: str | None = None
    entry_sha256: str | None = None
    verdicts: tuple[dict, ...] | None = None
    escaped: tuple[str, ...] = ()  # files whose closing fence was escaped (flagged, US-46)
    model_calls: tuple[dict, ...] = ()  # the call's `model_calls` rows, principal `gateway` (section 4.2)
    fenced: bool = False  # the answer came fenced and was unwrapped once (T-GW-35)

    def __post_init__(self) -> None:
        recorded = self.outcome in ("hit", "stored", "race_lost")
        if self.outcome not in OUTCOMES or (self.code is not None) != (self.outcome == "failed") or \
                (self.code is not None and self.code not in CODES) or \
                (self.verdicts is not None, self.cache_key is not None, self.entry_sha256 is not None) != (recorded,) * 3:
            raise ValueError(f"not a result of the closed set: {self.outcome!r}, {self.code!r}")


def _ask(backend: Backend, request_text: str, call_id: str) -> Reply:
    """The one call into a backend; every reference to it sits inside `egress.check(...).release(...)`."""
    return backend.judge(request_text, call_id)


def _send(request_text: str, judge: Judge, ctx: Context, backend: Backend | Launch, call_id: str) -> Reply | None:
    """The reply, or None when egress withheld the request (the backend was never called). A `Launch` becomes a
    `Headless` call only here, inside the release."""
    return egress.check(request_text, destination=judge.model, operator=ctx.operator, secrets=ctx.secrets,
                        canaries=ctx.canaries).release(
        lambda payload: _ask(Headless(backend) if isinstance(backend, Launch) else backend, payload, call_id))


def _recorded(outcome: str, cache_key: str, found: store.Found, items: int, escaped: tuple[str, ...]) -> Result:
    """A hit or a lost race carries the stored verdicts only when they still have the answer's shape."""
    verdicts = found.entry["verdicts"]
    if schema.validate({"items": verdicts}, items):
        return Result("failed", "HB-GW-005", escaped=escaped)
    return Result(outcome, None, cache_key, found.entry_sha256, tuple(verdicts), escaped)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(judge: Judge, inputs: Inputs, ctx: Context, backend: Backend | Launch) -> Result:
    if not judge.qualified:  # never spawned, and no verdict is read for it (sections 5, 8.4, 10.1; T-GW-32)
        return Result("failed", "HB-GW-007")
    if request.bound_problem(inputs.artifacts) is not None:
        return Result("failed", "HB-GW-008")
    rendered = request.render(inputs.preamble, inputs.rubric, inputs.items, inputs.artifacts, ctx.denylist)
    escaped = rendered.escaped
    if scrub.scan(rendered.text, ctx.denylist):
        return Result("failed", "HB-GW-004", escaped=escaped)
    key_inputs = {"request_sha256": hashlib.sha256(rendered.text.encode("utf-8")).hexdigest(),
                  "schema_sha256": schema.schema_sha256(), "model": judge.model,
                  "invocation_sha256": judge.invocation_sha256}
    cache_key = store.key(key_inputs)
    found = store.lookup(ctx.store, cache_key, ctx.known_roots, judge.allowed_models, ctx.own_run)
    if found.state == "hit":
        return _recorded("hit", cache_key, found, inputs.items, escaped)
    if found.state == "failed":
        return Result("failed", found.code, escaped=escaped)
    if not ctx.allow_model_calls:
        return Result("not_allowed", escaped=escaped)
    if found.state == "orphaned":
        store.move_orphan(ctx.store, cache_key, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    try:
        reply = _send(rendered.text, judge, ctx, backend, cache_key[:16])
    except BackendDown:
        return Result("failed", "HB-GW-001", escaped=escaped)
    if reply is None:
        return Result("failed", "HB-GW-009", escaped=escaped)
    read = read_reply(reply.stdout)
    try:
        answer = json.loads(read[0]) if read else None
    except ValueError:
        answer = None
    if read is None or schema.validate(answer, inputs.items):
        return Result("failed", "HB-GW-002", escaped=escaped)
    _, served, session = read
    # the pin must be among the served models, and every served model allowed (design 4.3; review F1)
    if judge.model not in served or not all(m in judge.allowed_models for m in served):
        return Result("failed", "HB-GW-003", escaped=escaped)
    entry = {"format": store.FORMAT, "key_inputs": key_inputs,
             "components": {"artifact_sha256": rendered.artifact_sha256,
                            "rubric_sha256": _sha256(inputs.rubric),
                            "template_version": request.TEMPLATE_VERSION, "scrub_version": scrub.SCRUB_VERSION,
                            "schema_sha256": key_inputs["schema_sha256"]},
             "served_models": list(served), "stored_by": dict(ctx.stored_by), "native_session_id": session,
             "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verdicts": answer["items"]}
    written = store.write_once(ctx.store, cache_key, entry, judge.allowed_models)
    if written.state == "failed":
        return Result("failed", written.code, escaped=escaped)
    return _recorded(written.state, cache_key, written, inputs.items, escaped)
