"""Autonomy and process metrics from the normalised trajectory.

p1 (docs/design/phase3-graders.md, Process): tool_error_rate and stuck_loops from inp.tool_calls
sorted by native_ordinal, excluding tool_class "meta". The other four metrics are NA "not built".
Not registered in runner.GRADERS (an unregistered grader is NA "not built" for every metric).
"""

from collections.abc import Mapping
from decimal import Decimal

from harness_bench.grade import CellInput, Score

NOT_BUILT = "not built"
RATE_SCALE = Decimal("0.0001")
STUCK_RUN = 3  # a maximal run of this many consecutive failures, same name
_UNBUILT = (
    "completion_without_intervention",
    "recovery_rate",
    "planning_ratio",
    "time_to_first_green",
)


def _counted(tool_calls: tuple[Mapping, ...]) -> list[Mapping]:
    """Non-meta calls in native_ordinal order. Meta rows are excluded everywhere."""
    rows = [row for row in tool_calls if row.get("tool_class") != "meta"]
    return sorted(rows, key=lambda row: row["native_ordinal"])


def _outcome_na(calls: list[Mapping]) -> str | None:
    """Shared NA for both metrics: no counted call, or any null ok (never a partial ratio)."""
    if not calls:
        return "no tool call"
    missing = sum(1 for row in calls if row.get("ok") is None)
    if missing:
        return f"per-call outcome missing on {missing} of {len(calls)} calls"
    return None


def _tool_error_rate(calls: list[Mapping]) -> Score:
    reason = _outcome_na(calls)
    if reason is not None:
        return Score(None, reason)
    failed = sum(1 for row in calls if row.get("ok") == 0)
    return Score((Decimal(failed) / Decimal(len(calls))).quantize(RATE_SCALE), None)


def _stuck_loops(calls: list[Mapping]) -> Score:
    """Maximal runs of >= STUCK_RUN consecutive calls with the same name and ok == 0."""
    reason = _outcome_na(calls)
    if reason is not None:
        return Score(None, reason)
    loops, index = 0, 0
    while index < len(calls):
        row = calls[index]
        if row.get("ok") != 0:
            index += 1
            continue
        name, end = row.get("name"), index + 1
        while end < len(calls) and calls[end].get("name") == name and calls[end].get("ok") == 0:
            end += 1
        length = end - index
        if length >= STUCK_RUN:
            loops += 1
        index = end
    return Score(loops, None)


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    calls = _counted(inp.tool_calls)
    scores: dict[str, Score] = {metric: Score(None, NOT_BUILT) for metric in _UNBUILT}
    scores["tool_error_rate"] = _tool_error_rate(calls)
    scores["stuck_loops"] = _stuck_loops(calls)
    return scores
