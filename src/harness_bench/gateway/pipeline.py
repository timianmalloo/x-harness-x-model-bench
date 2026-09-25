"""One judge lookup for one (artifact, rubric) request: the section 8 pipeline, offline half (slice 1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness_bench import egress
from harness_bench.gateway.backend import Backend, Reply

OUTCOMES = ("hit", "stored", "race_lost", "not_allowed", "failed")


@dataclass(frozen=True)
class Judge:
    model: str
    invocation_sha256: str
    allowed_models: tuple[str, ...]


@dataclass(frozen=True)
class Inputs:
    preamble: str
    rubric: str
    items: int
    artifacts: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class Context:
    store: Path
    known_roots: tuple[Path, ...]
    own_run: Path | None
    stored_by: dict
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
    escaped: tuple[str, ...] = ()


def _ask(backend: Backend, request: str) -> Reply:
    """The one call into a backend; every reference to it sits inside `egress.check(...).release(...)`."""
    return backend.judge(request)


def _send(request: str, judge: Judge, ctx: Context, backend: Backend) -> Reply | None:
    return egress.check(request, destination=judge.model, operator=ctx.operator, secrets=ctx.secrets,
                        canaries=ctx.canaries).release(lambda payload: _ask(backend, payload))


def run(judge: Judge, inputs: Inputs, ctx: Context, backend: Backend) -> Result:
    return Result("failed", "HB-GW-001")
