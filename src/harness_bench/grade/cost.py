"""cost_usd and the cell-grain cost/efficiency metrics (US-23; design docs/design/phase3-cost.md; seam C-1).

- cost_usd: tokens by type x the price-list entry in force on the run date, or NA. Prices are per
  million tokens. The entry in force is the latest one for the exact model id whose `effective` date
  is on or before the run date. A served model with no entry, or a used token type with no price, is
  NA with the reason. No usage at all is NA, never $0 (US-27). The price list must be the one the plan
  froze; the caller checks its hash first. `_cost_usd` is `grade/runner.py`'s former `_cost`, moved
  here verbatim (seam C-1): same branches, same reasons, same order.
- The other five: `tokens_per_minute`, `output_tokens_per_turn`, `cache_hit_ratio`,
  `cache_write_amplification` and `context_growth` (peak). Each is built only from `normalize.totals`
  and the existing view measures `views.busy_ms`, `views.calls_per_cell` and `views.model_call` (DM7:
  one definition per quantity) -- never a second, competing definition of a token total, a busy span or
  a request count. `compactions` has no recorded signal on any harness today (checked, not assumed: no
  event, tool-call or model-call field anywhere in the ledger names a compaction), so it is
  unconditionally NA, never 0 (US-27).
- `cost_of_pass`, `tokens_per_solved`, `tokens_by_type`, `wall_clock_split`, `turns_and_tool_calls` and
  `coordinator_overhead` are `kind: derived` (DM7): they stay view-only and are never built here.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from harness_bench import views
from harness_bench.grade import CellInput, Score
from harness_bench.telemetry import Extraction
from harness_bench.telemetry.normalize import totals as token_totals

PRICE_KEYS = {"uncached_input": "input", "cache_read": "cache_read", "cache_write": "cache_write", "output": "output"}

# The closed NA-reason vocabulary this module writes (US-27: never 0).
NO_USAGE = "no usage recorded"  # matches views.py's own tokens_reason wording for the same fact
ACP_MISSES_CALLS = "the native record misses calls (token source acp_turn)"  # matches views._model_time's reason
NO_MODEL_CALL_TIME = "no model call time recorded"
NO_INPUT_TOKENS = "no input tokens recorded"
NO_CACHE_ACTIVITY = "no cache activity recorded"
NO_CACHE_READS = "no cache reads recorded"
NO_COMPACTION_SIGNAL = "no compaction signal recorded by any harness"


def _entry(prices: dict, model: str, run_date: str) -> dict | None:
    live = [e for e in prices.get("entries") or [] if e.get("model") == model and str(e.get("effective")) <= run_date]
    return max(live, key=lambda e: str(e["effective"])) if live else None


def cost_usd(totals: dict[str, dict[str, int]], prices: dict, run_date: str) -> tuple[Decimal | None, str | None, str]:
    """(value, NA reason, evidence) from per-model token totals."""
    if not totals:
        return None, "no usage recorded", ""
    total, used = Decimal(0), []
    for model in sorted(totals):
        entry = _entry(prices, model, run_date)
        if entry is None:
            return None, f"no price list entry for {model}", ""
        for bucket, key in PRICE_KEYS.items():
            tokens = totals[model][bucket]
            if not tokens:
                continue
            if entry.get(key) is None:
                return None, f"no {key} price for {model}", ""
            total += Decimal(tokens) * Decimal(str(entry[key]))
        used.append(f"{model}@{entry['effective']}")
    return total / 1_000_000, None, "bench/prices.yaml#" + ",".join(used)


def _cost_usd(inp: CellInput, source: str) -> Score:
    """cost_usd (US-23): `runner.py`'s former `_cost`, moved verbatim (seam C-1). Same branches, same order."""
    ex, unreadable = inp.extraction, inp.record_reason
    if inp.prices is None:
        return Score(None, "price list changed since the plan (hash mismatch)", "")
    if source == "native_record" and ex is None:
        return Score(None, unreadable, "")
    if source == "native_record" and ex.missing:  # a usage field the record lacks is NOT_RECORDED, never 0 (US-27)
        fields = ", ".join(sorted({m.field for m in ex.missing}))
        return Score(None, f"HB-TEL-001 native-record fields missing: {fields}", "")
    if source == "native_record" and unreadable is not None:  # e.g. truncated: never a price on a partial sum (R-15)
        return Score(None, unreadable, "")
    totals = token_totals(source, ex or Extraction(), list(inp.turn_usage))
    return Score(*cost_usd(totals, inp.prices, inp.plan["created_at"][:10]))


def _totals_or_na(inp: CellInput, source: str) -> tuple[dict[str, dict[str, int]] | None, str | None]:
    """(totals, NA reason): the same record-reliability gate as `_cost_usd`, minus its price-list check (that
    check is cost_usd's alone). One trustworthy per-model token-total reader for every metric below."""
    ex, unreadable = inp.extraction, inp.record_reason
    if source == "native_record" and ex is None:
        return None, unreadable
    if source == "native_record" and ex.missing:
        fields = ", ".join(sorted({m.field for m in ex.missing}))
        return None, f"HB-TEL-001 native-record fields missing: {fields}"
    if source == "native_record" and unreadable is not None:
        return None, unreadable
    totals = token_totals(source, ex or Extraction(), list(inp.turn_usage))
    return (totals or None), (None if totals else NO_USAGE)


def _sum_bucket(totals: dict[str, dict[str, int]], bucket: str) -> int:
    return sum(model[bucket] for model in totals.values())


def _round(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / Decimal(denominator)).to_integral_value(rounding=ROUND_HALF_UP))


def _tokens_per_minute(totals: dict[str, dict[str, int]], source: str, model_calls: tuple) -> Score:
    """Total tokens / model-busy-minutes. Busy time is `views.busy_ms` on the extraction's model-call spans, the
    same reader `views.py` uses for `model_ms` -- including its acp_turn gate (that record misses calls, G1), so
    this never redefines "model busy time" a second way (DM7). Called only once totals are known trustworthy
    (`grade_cell`'s shared na-gate)."""
    if source == "acp_turn":
        return Score(None, ACP_MISSES_CALLS)
    busy = views.busy_ms(list(model_calls), positive=True, missing=NO_MODEL_CALL_TIME)
    if busy.value is None:
        return Score(None, busy.reason)
    tokens = sum(_sum_bucket(totals, b) for b in ("uncached_input", "cache_read", "cache_write", "output"))
    return Score(_round(tokens * 60_000, busy.value), None)


def _output_tokens_per_turn(totals: dict[str, dict[str, int]], model_calls: tuple) -> Score:
    """Output tokens / turns, where turns is `views.calls_per_cell` (Sigma `requests`) -- the one definition of a
    turn count this catalog already has, unconditional on the token source, exactly as `views.py` uses it."""
    calls = [views.model_call(r) for r in model_calls] or None
    turns = views.calls_per_cell(calls)
    if turns.value is None:
        return Score(None, turns.reason)
    return Score(_round(_sum_bucket(totals, "output"), turns.value), None)


def _cache_hit_ratio(totals: dict[str, dict[str, int]]) -> Score:
    """Cache-read tokens as a percentage of would-be-cached input (uncached_input + cache_read); cache_write is
    not a hit or a miss, so it is not in the denominator."""
    uncached, read = _sum_bucket(totals, "uncached_input"), _sum_bucket(totals, "cache_read")
    if uncached + read == 0:
        return Score(None, NO_INPUT_TOKENS)
    return Score(_round(read * 100, uncached + read), None)


def _cache_write_amplification(totals: dict[str, dict[str, int]]) -> Score:
    """Cache-write tokens as a percentage of cache-read tokens: tokens (re)written per 100 tokens later read back.
    Above 100, the cell wrote more than it ever read (poor reuse); undefined with no reads at all."""
    read, write = _sum_bucket(totals, "cache_read"), _sum_bucket(totals, "cache_write")
    if read == 0 and write == 0:
        return Score(None, NO_CACHE_ACTIVITY)
    if read == 0:
        return Score(None, NO_CACHE_READS)
    return Score(_round(write * 100, read), None)


def _context_growth(totals: dict[str, dict[str, int]], source: str, model_calls: tuple) -> Score:
    """Peak per-call context size (uncached_input + cache_read + cache_write of one call), the largest single
    prompt this cell sent. NA for acp_turn: a peak (max) is not resilient to the calls that record misses (G1) --
    unlike a sum, one missing call silently understates it, so it is never reported as measured."""
    if source == "acp_turn":
        return Score(None, ACP_MISSES_CALLS)
    peak = max(c["uncached_input"] + c["cache_read"] + c["cache_write"] for c in model_calls)
    return Score(peak, None)


def grade_cell(inp: CellInput) -> dict[str, Score]:
    """cost_usd (seam C-1) and the five cell-grain efficiency metrics (design docs/design/phase3-cost.md). The
    five share one na-gate (`totals`/`na` from `_totals_or_na`): NA propagates before any of them computes."""
    source = inp.plan["profiles"][inp.cell["harness"]]["usage_source"]
    totals, na = _totals_or_na(inp, source)

    def scored(fn, *args) -> Score:
        return Score(None, na) if na is not None else fn(*args)

    return {
        "cost_usd": _cost_usd(inp, source),
        "tokens_per_minute": scored(_tokens_per_minute, totals, source, inp.model_calls),
        "output_tokens_per_turn": scored(_output_tokens_per_turn, totals, inp.model_calls),
        "cache_hit_ratio": scored(_cache_hit_ratio, totals),
        "cache_write_amplification": scored(_cache_write_amplification, totals),
        "context_growth": scored(_context_growth, totals, source, inp.model_calls),
        "compactions": Score(None, NO_COMPACTION_SIGNAL),
    }
