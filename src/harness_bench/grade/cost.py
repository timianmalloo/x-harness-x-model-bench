"""cost_usd for one cell (US-23): tokens by type x the price-list entry in force on the run date, or NA.

- Prices are per million tokens. The entry in force is the latest one for the exact model id whose
  `effective` date is on or before the run date.
- A served model with no entry, or a used token type with no price, is NA with the reason. No usage at
  all is NA, never $0 (US-27).
- The price list must be the one the plan froze; the caller checks its hash first.
- The other cost metrics (cost of pass, tokens per solved, cache ratios, time split) are derived in
  views or built in later phases (Spec S-08a).
"""

from __future__ import annotations

from decimal import Decimal

PRICE_KEYS = {"uncached_input": "input", "cache_read": "cache_read", "cache_write": "cache_write", "output": "output"}


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
