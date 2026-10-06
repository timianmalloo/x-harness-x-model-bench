"""Run resume entry points (W1-K).

`resume_run` is still the K1 refusal skeleton (K1c replaces it). K1b supplies the pure parts: the stop predicate,
the classifier (W1-K section 3.2) and the one remaining-work predicate (D-K12). All three read ledger rows only.
"""

from dataclasses import dataclass
from pathlib import Path

from harness_bench import views
from harness_bench.errors import BenchError


def resume_run(run_dir: Path, root: Path, plan: dict, cfg):
    """Preserve today's already-started refusal until the resume path lands."""
    raise BenchError("HB-USR-002", f"run {plan['run_id']} has already started; phase 1 re-runs under a new run id")


def stop_recorded(rows: list[dict]) -> bool:
    """D-K4: a stop is run.stopped, an applied stop control, or a stop decision. run.launch_stopped alone is not one."""
    for row in rows:
        kind = row.get("kind")
        if kind == "run.stopped":
            return True
        if kind == "control.applied" and row.get("control") == "stop" and row.get("effect") == "applied":
            return True
        if kind == "decision.resolved" and row.get("option") == "stop":
            return True
    return False


@dataclass(frozen=True)
class Action:
    """What the resume does for one plan cell: the rule matched, and the outcome row it records (None: no new outcome)."""

    cell_id: str
    rule: str
    outcome: str | None
    code: str | None


def _planned_turns(plan: dict, cell: dict) -> int:
    return 1 + len((plan.get("tasks") or {}).get(cell.get("task"), {}).get("turns", []))


def _classify_cell(cell_rows: list[dict], n_turns: int, stopped: bool) -> tuple[str, str | None, str | None]:
    kinds = {r["kind"] for r in cell_rows}
    if "cell.outcome" in kinds:
        return ("C0" if "cell.archived" in kinds else "C1"), None, None
    if "cell.launch_intent" not in kinds:
        return "C7", None, None
    sent = {r.get("turn", 1) for r in cell_rows if r["kind"] == "cell.prompt_sent"}
    if not sent:
        return "C6", ("stopped" if stopped else None), None
    ended = {r.get("turn", 1): r.get("next", "final") for r in cell_rows if r["kind"] == "cell.turn_ended"}
    snapped = {r.get("turn", 1) for r in cell_rows if r["kind"] == "cell.turn_snapshot_archived"}
    crashed = any(k not in ended for k in sent)  # C2 before C3: a crashed turn 2 also has turn_ended{1}
    last = max(sent)
    if crashed:
        rule, code = "C2", "HB-CELL-118"
    elif ended[last] == "snapshot" and last < n_turns:
        rule, code = ("C3", "HB-CELL-119") if last in snapped else ("C4", "HB-CELL-119")
    else:
        rule, code = "C5", "HB-CELL-118"
    return (rule, "stopped", None) if stopped else (rule, "failed", code)


def classify(plan: dict, rows: list[dict], stopped: bool) -> list[Action]:
    """One Action per plan cell, in plan order (W1-K section 3.2); `stopped` is stop_recorded(rows), computed once."""
    by_cell: dict[str, list[dict]] = {}
    for row in rows:
        if "cell_id" in row:
            by_cell.setdefault(row["cell_id"], []).append(row)
    return [Action(cell["cell_id"], *_classify_cell(by_cell.get(cell["cell_id"], []), _planned_turns(plan, cell), stopped))
            for cell in plan["cells"]]


def has_work(plan: dict, rows: list[dict]) -> bool:
    """D-K12: the one definition of remaining work (also read by the alarm)."""
    if not views.completed(rows):
        return True  # clause 4
    stopped = stop_recorded(rows)
    return any(a.rule in {"C1", "C2", "C3", "C4", "C5", "C6"} or (a.rule == "C7" and not stopped)
               for a in classify(plan, rows, stopped))
