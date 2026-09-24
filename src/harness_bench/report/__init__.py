"""Reports over the views (design: UI & interaction design): the CLI table and the static HTML page.

The formatters here are the one definition of how a value reads on every surface. A value that was not
measured reads `NA (<reason>)`, never 0, 0% or $0 (US-27). Numbers carry their unit.
"""

from __future__ import annotations

from decimal import Decimal

from harness_bench.views import Measure


def na(m: Measure) -> str:
    return f"NA ({m.reason})"


def rate(m: Measure) -> str:
    return na(m) if m.value is None else f"{Decimal(m.value):.2f}"


def tokens(m: Measure) -> str:
    return na(m) if m.value is None else f"{round(Decimal(m.value)):,} tok"


def seconds(m: Measure) -> str:
    return na(m) if m.value is None else f"{Decimal(m.value) / 1000:.1f} s"


def millis(m: Measure) -> str:
    return na(m) if m.value is None else f"{round(Decimal(m.value)):,} ms"


def usd(m: Measure) -> str:
    return na(m) if m.value is None else f"${Decimal(m.value):.6f}"


def cell_tokens(totals: dict[str, dict[str, int]] | None, reason: str | None) -> str:
    if not totals:
        return f"NA ({reason})"
    return f"{sum(sum(b.values()) for b in totals.values()):,} tok"
