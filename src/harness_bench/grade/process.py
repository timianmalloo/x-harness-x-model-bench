"""Autonomy and process metrics from the normalised trajectory.

p1 (docs/design/phase3-graders.md, Process): tool_error_rate and stuck_loops from inp.tool_calls
sorted by native_ordinal, excluding tool_class "meta".
p2: recovery_rate over those same calls, and planning_ratio from model-call requests.
completion_without_intervention and time_to_first_green are NA "not built".
Not registered in runner.GRADERS (an unregistered grader is NA "not built" for every metric).
"""

from collections.abc import Mapping
from decimal import Decimal

from harness_bench.grade import CellInput, Score

NOT_BUILT = "not built"
RATE_SCALE = Decimal("0.0001")
STUCK_RUN = 3  # a maximal run of this many consecutive failures, same name
NO_FAILED = "no failed tool call"
NO_EDIT = "no edit-class tool call (edits through the shell are not classed)"
SUMMARY_ROWS = "model calls not itemised in time (summary rows)"
_UNBUILT = (
    "completion_without_intervention",
    "time_to_first_green",
)


def _counted(tool_calls: tuple[Mapping, ...]) -> list[Mapping]:
    """Non-meta calls in native_ordinal order. Meta rows are excluded everywhere."""
    rows = [row for row in tool_calls if row.get("tool_class") != "meta"]
    return sorted(rows, key=lambda row: row["native_ordinal"])


def _missing_outcome(calls: list[Mapping]) -> str | None:
    """The p1 missing-outcome reason, or None. An empty list is not this reason."""
    missing = sum(1 for row in calls if row.get("ok") is None)
    if missing:
        return f"per-call outcome missing on {missing} of {len(calls)} calls"
    return None


def _outcome_na(calls: list[Mapping]) -> str | None:
    """Shared NA for tool_error_rate and stuck_loops: no counted call, or any null ok."""
    if not calls:
        return "no tool call"
    return _missing_outcome(calls)


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


def _followed_by_success(calls: list[Mapping], index: int) -> bool:
    """A later ok == 1 call of the same name. An earlier success, or another name, does not count."""
    name = calls[index].get("name")
    return any(later.get("name") == name and later.get("ok") == 1 for later in calls[index + 1:])


def _recovery_rate(calls: list[Mapping]) -> Score:
    """Failed calls later followed by an ok == 1 of the same name, divided by failed calls."""
    reason = _missing_outcome(calls)
    if reason is not None:
        return Score(None, reason)
    failed = [index for index, row in enumerate(calls) if row.get("ok") == 0]
    if not failed:
        return Score(None, NO_FAILED)
    recovered = sum(1 for index in failed if _followed_by_success(calls, index))
    return Score((Decimal(recovered) / Decimal(len(failed))).quantize(RATE_SCALE), None)


def _planning_ratio(calls: list[Mapping], model_calls: tuple[Mapping, ...]) -> Score:
    """Requests that start before the first edit-class call, divided by all requests."""
    edits = [row for row in calls if row.get("tool_class") == "edit"]
    if not edits:
        return Score(None, NO_EDIT)
    if not model_calls or any(row.get("start") is None for row in model_calls):
        return Score(None, SUMMARY_ROWS)
    first = edits[0]["start"]
    before = sum(row["requests"] for row in model_calls if row["start"] is not None and row["start"] < first)
    total = sum(row["requests"] for row in model_calls)
    return Score((Decimal(before) / Decimal(total)).quantize(RATE_SCALE), None)


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    calls = _counted(inp.tool_calls)
    scores: dict[str, Score] = {metric: Score(None, NOT_BUILT) for metric in _UNBUILT}
    scores["tool_error_rate"] = _tool_error_rate(calls)
    scores["stuck_loops"] = _stuck_loops(calls)
    scores["recovery_rate"] = _recovery_rate(calls)
    scores["planning_ratio"] = _planning_ratio(calls, inp.model_calls)
    return scores
