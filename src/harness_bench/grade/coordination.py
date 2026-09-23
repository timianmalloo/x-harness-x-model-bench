"""Coordination and pack-effect metrics.

Metrics: model_map_adherence, per_agent_attribution, intent_log_completeness, kg_use, coordination_overhead, parallel_efficiency.
Reuse coord-core.py metrics, audit-log.py selfcheck and cfd-bench tools/grade-benchmarks.py axes.
Spec: S-08e (docs/specs/README.md).
"""

from pathlib import Path

from harness_bench.grade import Result, not_built


def grade(run_dir: Path, task_dir: Path) -> Result:
    raise not_built("coordination", "S-08e")
