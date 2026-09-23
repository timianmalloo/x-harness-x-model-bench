"""Cost and efficiency from normalised telemetry and bench/prices.yaml.

Metrics: cost_usd, cost_of_pass, tokens_per_solved, cache_hit_ratio, cache_write_amplification, context_growth, wall_clock_split, compactions, coordinator_overhead.
Build first (proposal: Codex reader and cost are the first two graders). Cost is NA without a dated list price; never estimated from memory.
Spec: S-08a (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("cost", "S-08a")
