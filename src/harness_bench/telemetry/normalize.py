"""One normaliser (ADR-0006, ADR-0008 as amended): extractions and turn usage into ledger rows and totals.

- extraction_id: the hash of this package's source, so a normaliser fix is a new extraction.
- turn_usage: the adapter's per-turn, per-model usage from the ACP prompt response
  (`_meta.quota.model_usage`; `cachedInputTokens` there is a separate bucket from `inputTokens`).
- totals: per model, from the profile's authoritative source. `acp_turn` for Claude Code (its record
  misses the final and auxiliary calls, Verified 2026-09-23); `native_record` for Codex (its adapter
  reports only the last call).
- classify: provider errors to a cause. 408, 429, 5xx and overload are `failed (provider)`
  (infrastructure); any other 4xx is `failed (model unavailable)` (benchmark: the plan pinned a model
  the account cannot serve) (probe W3).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from harness_bench.errors import Cause
from harness_bench.telemetry import Extraction, ProviderError, as_dict, as_int

BUCKETS = ("uncached_input", "cache_read", "cache_write", "output")
PROVIDER_TYPES = ("overloaded", "rate_limit", "timeout", "api_error", "server_error", "unavailable")


@dataclass(frozen=True)
class TurnUsage:
    model: str
    uncached_input: int
    cache_read: int
    cache_write: int
    output: int
    reasoning: int


def extraction_id() -> str:
    h = hashlib.sha256()
    for f in sorted(Path(__file__).parent.glob("*.py")):
        h.update(f.name.encode() + b"\0" + f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def turn_usage(prompt_response: dict | None) -> list[TurnUsage]:
    meta = as_dict(as_dict(as_dict(prompt_response).get("_meta")).get("quota"))
    out = []
    for entry in meta.get("model_usage") or []:
        entry = as_dict(entry)
        tc = as_dict(entry.get("token_count"))
        if isinstance(entry.get("model"), str):
            out.append(TurnUsage(entry["model"], as_int(tc.get("inputTokens")), as_int(tc.get("cachedInputTokens")),
                                 as_int(tc.get("cachedWriteTokens")), as_int(tc.get("outputTokens")),
                                 as_int(tc.get("reasoningOutputTokens"))))
    return out


def totals(source: str, ex: Extraction, usage: list[TurnUsage]) -> dict[str, dict[str, int]]:
    """Per-model token totals from the authoritative source (`acp_turn` or `native_record`)."""
    out: dict[str, dict[str, int]] = {}
    items = usage if source == "acp_turn" else ex.model_calls
    for item in items:
        bucket = out.setdefault(item.model, dict.fromkeys(BUCKETS, 0))
        for b in BUCKETS:
            bucket[b] += getattr(item, b)
    return out


def served_models(source: str, ex: Extraction, usage: list[TurnUsage]) -> set[str]:
    """Models with at least one successful call, from the authoritative source (US-11)."""
    if source == "acp_turn":
        return {u.model for u in usage if u.output or u.uncached_input or u.cache_read}
    return {c.model for c in ex.model_calls if c.output or c.uncached_input or c.cache_read}


def classify(errors: list[ProviderError]) -> Cause | None:
    """One classifier for the native record and the driver's prompt errors (R-23). A status is evidence and decides
    first: 408, 429 or 5xx is provider, any other status is model_unavailable; only without a status does the error
    type decide (a provider type is provider)."""
    if not errors:
        return None
    for e in errors:
        if e.status is not None:
            provider = e.status in (408, 429) or e.status >= 500
        else:
            provider = any(t in e.error_type.lower() for t in PROVIDER_TYPES)
        if provider:
            return Cause.provider
    return Cause.model_unavailable


def model_call_rows(run_id: str, cell_id: str, session_id: str, ex: Extraction, extraction: str) -> list[dict]:
    return [{"kind": "model_call", "run_id": run_id, "extraction_id": extraction, "principal": cell_id, "cell_id": cell_id,
             "native_session_id": session_id, "native_ordinal": c.native_ordinal, "model": c.model,
             "uncached_input": c.uncached_input, "cache_read": c.cache_read, "cache_write": c.cache_write, "output": c.output,
             "reasoning": c.reasoning, "start": c.start, "end": c.end, "requests": c.requests} for c in ex.model_calls]


def tool_call_rows(run_id: str, cell_id: str, session_id: str, ex: Extraction, extraction: str) -> list[dict]:
    return [{"kind": "tool_call", "run_id": run_id, "extraction_id": extraction, "cell_id": cell_id, "native_session_id": session_id,
             "native_ordinal": t.native_ordinal, "name": t.name, "tool_class": t.tool_class, "start": t.start, "end": t.end,
             "ok": None if t.ok is None else int(t.ok), "outcome_code": t.outcome_code} for t in ex.tool_calls]
