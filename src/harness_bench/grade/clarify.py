"""Scripted-user log vs the oracle's annotated clarifications.

Metrics: ask_vs_assume, key_question_recall, key_question_precision.
Spec: S-08d (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.clarify is not built yet; spec S-08d in docs/specs/README.md")
