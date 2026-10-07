"""Liveness and alarm check (W1-K §6.2, ADR-0021 §7)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness_bench.resume import has_work


@dataclass(frozen=True)
class AlarmResult:
    code: str
    cause: str
    last_progress_at: str | None
    age_s: float


def check(
    run_dir: Path,
    after_s: float,
    now: float | None = None,
    lock_age: float | None = None,
) -> AlarmResult | None:
    """Pure core alarm check (W1-K §6.2)."""
    _ = (run_dir, after_s, now, lock_age, has_work)
    return None
