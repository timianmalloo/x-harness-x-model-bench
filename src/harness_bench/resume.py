"""Run resume entry points (W1-K).

K5 supplies ordered read-only refusals; the continuation remains the K1 skeleton
until K6. The stop predicate, classifier and remaining-work predicate read ledger rows only.
"""

from dataclasses import dataclass
from pathlib import Path

from harness_bench import archive, ledger, lifecycle, oslock
from harness_bench import plan as plan_module
from harness_bench.errors import BenchError


def resume_run(run_dir: Path, root: Path, plan: dict, cfg):
    """W1-K 3.1 steps 1–3; refusal order precedes all writes and first-run checks."""
    plan = plan_module.load_confirmed(run_dir)
    if cfg is None or cfg.verify is None:
        raise ValueError("resume_run requires EngineConfig.verify")
    lock_path = run_dir / ".lock"
    try:
        lock = oslock.RunLock.acquire(lock_path, code="HB-RUN-005")
    except BenchError as exc:
        age = f"{oslock.heartbeat_age(lock_path):.1f} s" if lock_path.is_file() else "not recorded"
        raise BenchError("HB-RUN-005", f"{lock_path}: heartbeat age {age}; {exc.message}") from exc
    with lock:
        if cfg.identity_check is not None:
            checked = cfg.identity_check()
            if checked.diff:
                raise BenchError("HB-IDN-001", "; ".join(checked.diff))
        errors = [f for f in cfg.verify(run_dir) if f.level == "error"]
        # A missing archive is D-K14's explicit third refusal, even when verify
        # also reports its incomplete archive hash. Segment errors still win.
        integrity_errors = [f for f in errors if f.code != "HB-LED-005"]
        if integrity_errors:
            raise BenchError("HB-RUN-009", integrity_errors[0].message)
        rows = _fact_rows(run_dir, "events")
        files = _fact_rows(run_dir, "archive_files")
        missing = _missing_archives(run_dir, rows, files)
        archive_errors = [f for f in errors if not any(f.message.startswith(f"{cid}:") or str(folder) in f.message
                                                     for cid, folder in missing)]
        if archive_errors:
            raise BenchError("HB-RUN-009", archive_errors[0].message)
        if missing:
            raise BenchError("HB-LED-005", f"archive folder {missing[0][1]} does not exist")
        raise BenchError("HB-USR-002", f"run {plan['run_id']} has already started; phase 1 re-runs under a new run id")


def _fact_rows(run_dir: Path, fact: str) -> list[dict]:
    """Read engine facts without crossing the run -> grade dependency boundary."""
    return [row for path in sorted((run_dir / fact).glob("engine-*.jsonl")) for row in ledger.read_segment(path)]


def _missing_archives(run_dir: Path, rows: list[dict], files: list[dict]) -> list[tuple[str, Path]]:
    folders = dict.fromkeys((row["cell_id"], row["archive_attempt"], "final")
                            for row in rows if row["kind"] == "cell.archived")
    folders.update(dict.fromkeys((row["cell_id"], row["archive_attempt"], archive.snapshot_of(row)) for row in files))
    missing = []
    for cid, attempt, snapshot in folders:
        folder = run_dir / "archive" / cid / (f"attempt-{attempt}" if snapshot == "final" else snapshot)
        if not folder.is_dir():
            missing.append((cid, folder))
    return missing


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
    if not lifecycle.completed(rows):
        return True  # clause 4
    stopped = stop_recorded(rows)
    return any(a.rule in {"C1", "C2", "C3", "C4", "C5", "C6"} or (a.rule == "C7" and not stopped)
               for a in classify(plan, rows, stopped))
