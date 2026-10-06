"""Run resume entry points (W1-K K1 refusal skeleton).

K1a preserves the existing refusal. K1b-K1d supply reconciliation and the
remaining-work predicate after their assertion reds have been observed.
"""

from pathlib import Path

from harness_bench.errors import BenchError


def resume_run(run_dir: Path, root: Path, plan: dict, cfg):
    """Preserve today's already-started refusal until the resume path lands."""
    raise BenchError("HB-USR-002", f"run {plan['run_id']} has already started; phase 1 re-runs under a new run id")


def has_work(plan: dict, rows: list[dict]) -> bool:
    """Neutral K1 skeleton; K1b replaces this after the remaining-work reds."""
    return False
