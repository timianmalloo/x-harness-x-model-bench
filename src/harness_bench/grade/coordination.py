"""Coordination and pack-effect metrics.

Metrics: model_map_adherence, per_agent_attribution, intent_log_completeness, kg_use, coordination_overhead, parallel_efficiency,
protocol_conformance (the run's coordination ledger replayed as a trace against models/coordination_protocol.tla; spec S-14).
Reuse coord-core.py metrics, audit-log.py selfcheck and cfd-bench tools/grade-benchmarks.py axes.
Spec: S-08e (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.coordination is not built yet; spec S-08e in docs/specs/README.md")
