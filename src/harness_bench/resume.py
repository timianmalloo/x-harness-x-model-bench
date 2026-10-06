"""Run resume entry points (W1-K).

K5 supplies the ordered read-only refusals; K6 the continuation: the resume's own segments, the reconciliation of
each crashed cell, the pid check and the engine loop. The stop predicate, classifier and remaining-work predicate read
ledger rows only. Nothing here imports a grade module: `cfg.verify` is injected by the composition root.
"""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from harness_bench import archive, atomic, engine, host, ledger, lifecycle, oslock
from harness_bench import plan as plan_module
from harness_bench.errors import BenchError, Cause

log = engine.log  # the run-log handler owns both engine and resume events
DEFAULT_PID_WAIT_S = 30  # D-K2: the bounded wait for a recorded pid that is still alive
PHASES = {"C2": "mid-turn", "C3": "between-turns", "C4": "between-turns", "C5": "turn-complete", "C6": "mid-turn"}
CAUSES = {"HB-CELL-117": Cause.archive, "HB-CELL-118": Cause.coordinator_crash,
          "HB-CELL-119": Cause.coordinator_crash_between_turns}


def resume_run(run_dir: Path, root: Path, plan: dict, cfg):
    """W1-K 3.1 steps 1–3; refusal order precedes all writes and first-run checks."""
    started = time.perf_counter()
    confirmed = plan_module.load_confirmed(run_dir)
    passed_hash, confirmed_hash = plan_module.plan_hash(plan), plan_module.plan_hash(confirmed)
    if passed_hash != confirmed_hash:  # the confirmed plan is the one authority; a caller's edit is never silently dropped
        raise ValueError(f"the plan passed to resume_run differs from {run_dir / 'plan.json'}: "
                         f"passed {passed_hash}, confirmed {confirmed_hash}")
    plan = confirmed
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
        stopped = stop_recorded(rows)
        if not has_work(plan, rows):  # step 4: no segment and no row
            actions = classify(plan, rows, stopped)
            log.info("resume.started", extra={"run_id": plan["run_id"], "segment_id": None, "dead_segments": None,
                                               "cells_total": len(plan["cells"]), "has_work": False})
            _log_classified(actions)
            return _report(engine.RunSummary(3 if stopped else 0), [], stopped, [], started=started,
                           skipped=sum(a.rule == "C0" for a in actions))
        usage = _fact_rows(run_dir, "turn_usage")
        state = _Resume(run_dir, plan, cfg, lock, {"events": rows, "archive_files": files, "turn_usage": usage}, stopped)
        summary = state.eng.resume(lock, engine.next_ordinal(run_dir), state.boot)
        mine = _fact_rows(run_dir, "events")
        mine = mine[max(i for i, r in enumerate(mine) if r["kind"] == "run.resumed"):]  # this invocation's own rows
        return _report(summary, mine, stopped or bool(state.eng.run_stopped), state.eng.deferred, started=started,
                       skipped=state.skipped)


def _report(summary: engine.RunSummary, rows: list[dict], stopped: bool, deferred: list[str], *, started: float,
            skipped: int) -> engine.RunSummary:
    """The one closing line of a resume: three exits, three different lines (D-K13, R-101). `rows` are the rows
    this invocation wrote, so an idempotent re-run reports 0."""
    if deferred:
        print(f"run is not finished: cell {deferred[0]} process still alive, run again")
    elif stopped:
        n = sum(r["kind"] == "cell.outcome" and r["outcome"] == "stopped" for r in rows)
        m = sum(r["kind"] == "cell.archived" for r in rows)
        print(f"run is stopped: {n} cells recorded stopped, {m} archived, graded, 0 launched")
    elif summary.exit_code == 0:
        print("run is complete")
    log.info("resume.done", extra={"skipped": skipped,
                                  "launched": sum(r["kind"] == "cell.launch_intent" for r in rows),
                                  "reconciled": sum(r["kind"] == "cell.outcome" and "resume" in r for r in rows),
                                  "duration_ms": max(0, round((time.perf_counter() - started) * 1000))})
    return summary


def _log_classified(actions: list["Action"]) -> None:
    log.info("resume.classified", extra={"counts": {f"C{i}": sum(a.rule == f"C{i}" for a in actions) for i in range(8)}})


def _fact_rows(run_dir: Path, fact: str) -> list[dict]:
    """Read engine facts without crossing the run -> grade dependency boundary."""
    return [row for path in sorted((run_dir / fact).glob("engine-*.jsonl"), key=lambda p: p.stem) for row in ledger.read_segment(path)]


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


def sweep_archives(run_dir: Path, lock: oslock.RunLock) -> None:
    """W0 4: the resume pins its own lock to both levels of archive temps."""
    if lock.path.resolve() != (run_dir / ".lock").resolve():
        raise ValueError("resume archive sweep needs this run's lock")
    root = run_dir / "archive"
    atomic.sweep_temps(root, lock)
    if root.is_dir():
        for folder in sorted(root.iterdir()):
            if folder.is_dir() and not folder.is_symlink() and not folder.is_junction():
                atomic.sweep_temps(folder, lock)


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


def _live_pid(cell_rows: list[dict]) -> tuple[int, int] | None:
    """The recorded (pid, created_at) of a cell whose process was started and never recorded ended."""
    started = [r for r in cell_rows if r["kind"] == "attempt.process_started"]
    if not started or any(r["kind"] == "attempt.process_ended" for r in cell_rows) or not started[-1].get("pid"):
        return None
    return started[-1]["pid"], started[-1].get("created_at") or 0


def _folder_rows(folder: Path) -> list[dict]:
    """The rows a published snapshot folder holds (simplify: files only; ceiling a snapshot with links, which `copy.fill`
    never publishes; upgrade trigger: a snapshot row of kind link that must survive a redo)."""
    return [{"path": p.relative_to(folder).as_posix(), "kind": "file", "size": p.stat().st_size,
             "sha256": archive._sha(p), "link_target": ""} for p in sorted(folder.rglob("*")) if p.is_file()]


class _Resume:
    """W1-K 3.1 steps 5-7 on the engine thread: `boot` runs inside `Engine.resume`, under the lock's heartbeat."""

    def __init__(self, run_dir: Path, plan: dict, cfg, lock: oslock.RunLock, rows: dict[str, list[dict]],
                 stopped: bool) -> None:
        self.run_dir, self.plan, self.cfg, self.lock, self.rows, self.stopped = run_dir, plan, cfg, lock, rows, stopped
        self.eng = engine.Engine(plan, cfg)
        self.pid_wait = plan["parameters"].get("pid_wait_s", DEFAULT_PID_WAIT_S)
        self.skipped = 0
        self.dead = [(fact, path.stem, report) for fact in engine.FACTS
                     for path in sorted((run_dir / fact).glob("engine-*.jsonl"), key=lambda p: p.stem)
                     if not (report := ledger.verify_segment(path)).sealed]

    def boot(self) -> list[dict]:
        eng, rows = self.eng, self.rows["events"]
        segment = eng.writers["events"].segment_id
        log.info("resume.started", extra={"run_id": self.plan["run_id"], "segment_id": segment,
                                           "dead_segments": len(self.dead), "cells_total": len(self.plan["cells"]),
                                           "has_work": True})
        if not any(r["kind"] == "run.started" for r in rows):  # D-K6: started by the resume
            eng.append_row({"kind": "run.started", "run_id": self.plan["run_id"], "plan_hash": self.plan["plan_hash"],
                            "trace_id": self.plan["trace_id"]})
        eng.append_row({"kind": "run.resumed", "run_id": self.plan["run_id"], "plan_hash": self.plan["plan_hash"],
                        "segment_id": segment, "trace_id": self.plan["trace_id"]})
        named = {(r["fact"], r["segment_id"]) for r in rows if r["kind"] == "segment.abandoned"}
        for fact, sid, report in self.dead:
            if (fact, sid) not in named:  # fenced, never appended to: the marker pins the head (D-K8)
                lifecycle.check_writer("segment.abandoned", "ledger")  # W0 R6.12b: no events append skips the table
                eng.writers["events"].append(ledger.stamp({
                    "kind": "segment.abandoned", "code": "HB-LED-004", "fact": fact, "segment_id": sid,
                    "line_count": report.lines, "head_hash": report.head_hash, "error": "engine died"}))
        sweep_archives(self.run_dir, self.lock)
        eng.restore(self.rows)
        actions = classify(self.plan, rows, self.stopped)
        _log_classified(actions)
        self.skipped = sum(a.rule == "C0" for a in actions)
        if self.stopped:
            self._finish_the_stop(rows)
        by_cell: dict[str, list[dict]] = {}
        for row in rows:
            if "cell_id" in row:
                by_cell.setdefault(row["cell_id"], []).append(row)
        pending = []
        for action, cell in zip(actions, self.plan["cells"], strict=True):
            started = time.perf_counter()
            cell_rows = by_cell.get(cell["cell_id"], [])
            launched = self._act(action, cell, cell_rows, segment)
            pending += launched
            turn = max((r.get("turn", 1) for r in cell_rows if r["kind"] == "cell.prompt_sent"), default=1)
            outcome = eng.outcomes.get(action.cell_id, {})
            reconciled = outcome.get("resume", {}).get("segment_id") == segment
            operation = ("deferred" if action.cell_id in eng.deferred else "launch" if launched
                         else outcome["outcome"] if reconciled else "archive" if action.rule == "C1" else "skip")
            log.info("resume.cell", extra={"cell_id": action.cell_id, "rule": action.rule, "action": operation,
                                            "code": outcome.get("code") if reconciled else action.code,
                                            "phase": PHASES.get(action.rule), "turn": turn,
                                            "duration_ms": max(0, round((time.perf_counter() - started) * 1000))})
        return pending

    def _finish_the_stop(self, rows: list[dict]) -> None:
        eng = self.eng
        code = next((r["code"] for r in rows if r["kind"] == "run.stopped"), None)
        if code is None:  # windows 1 and 2: a stop recorded without its run.stopped
            code, decision_id = "HB-RUN-006", None
            for row in rows:
                if row["kind"] == "decision.resolved" and row.get("option") == "stop":
                    kind = next(r["decision_kind"] for r in rows
                                if r["kind"] == "decision.opened" and r["decision_id"] == row["decision_id"])
                    code, decision_id = ("HB-RUN-007" if kind == "spend_cap" else "HB-RUN-006"), row["decision_id"]
            eng.append_row({"kind": "run.stopped", "code": code, "decision_id": decision_id})
        eng.stopped = eng.run_stopped = code
        for row in eng.decisions.supersede_all():
            eng.append_row(row)

    def _act(self, action: Action, cell: dict, cell_rows: list[dict], segment: str) -> list[dict]:
        rule, cid = action.rule, cell["cell_id"]
        if rule == "C0":
            return []
        if rule == "C7":
            return [] if self.stopped else [cell]
        if rule == "C1":
            self._archive(cell)
            return []
        if self._alive(cid, cell_rows):
            return []
        if rule == "C6" and not self.stopped:  # D-K3: the folder is discarded, the cell launches once
            folder = self.eng.cfg.cells_root / self.plan["run_id"] / cid
            if folder.exists():
                shutil.rmtree(folder, onexc=atomic.make_writable)
            return [cell]
        turn = max((r.get("turn", 1) for r in cell_rows if r["kind"] == "cell.prompt_sent"), default=1)
        outcome, code = action.outcome, action.code
        if rule == "C4" and not self._redo_snapshot(cell, turn):
            outcome, code = "failed", "HB-CELL-117"
        cause = CAUSES.get(code) if outcome == "failed" else None
        # simplify: a resume-written outcome goes through Engine.append_row, which skips Engine._after_append (no
        # infra_streak, no circuit breaker, no _raise_for); ceiling: resume writes one outcome per cell and never launches.
        # Upgrade trigger: a resume that launches cells, or a circuit breaker meant to count reconciled failures.
        self.eng.append_row({
            "kind": "cell.outcome", "cell_id": cid, "outcome": outcome, "cause": cause.name if cause else None,
            "code": cause.code if cause else None, "host_mem_available": host.available_memory(),
            "resume": {"segment_id": segment, "turn": turn, "phase": PHASES[rule], "rule": rule}})
        # simplify: the scripted-user log (scripted-user.jsonl) is not closed for a reconciled cell, unlike Engine's
        # archive_after_outcome; ceiling: the log is archived as it stands with the cell folder. Upgrade trigger: a
        # grader or view that requires a closed scripted-user log on a resumed cell.
        self._archive(cell)
        return []

    def _alive(self, cid: str, cell_rows: list[dict]) -> bool:
        """D-K2: gone means no process, or one with another creation time; a live one is waited for, then deferred."""
        live = _live_pid(cell_rows)
        if live is None:
            return False
        deadline = time.monotonic() + self.pid_wait
        while host.process_alive(*live):
            if time.monotonic() >= deadline:
                self.eng.deferred.append(cid)
                log.info("resume.cell_deferred", extra={"cell_id": cid, "pid": live[0]})
                return True
            time.sleep(0.2)
        return False

    def _redo_snapshot(self, cell: dict, turn: int) -> bool:
        """W1-K 3.4: publish (or adopt the published folder), append the missing rows, then the event. Three tries."""
        eng, cid = self.eng, cell["cell_id"]
        folder = archive.snapshot_folder(self.run_dir, cid, turn)
        cell_dir = eng.cfg.cells_root / self.plan["run_id"] / cid
        tag = f"turn-{turn}"
        present = [r for r in self.rows["archive_files"] if r.get("cell_id") == cid and r.get("archive_attempt") == 1
                   and archive.snapshot_of(r) == tag]
        for _ in range(3):
            try:
                # simplify: an already-published turn folder is adopted by file scan only (_folder_rows), not re-verified against
                # its recorded hash; ceiling: a folder published by this engine's own atomic publish. Upgrade trigger: a published
                # folder found with rows that disagree with its snapshot_hash in a real run.
                if folder.is_dir():
                    rows = [{**r, "archive_attempt": 1, "snapshot": tag} for r in _folder_rows(folder)]
                    digest, total, ms = archive.archive_hash(rows), sum(r["size"] for r in rows), None
                else:
                    copied = archive.snapshot_cell(cell_dir, self.run_dir / "archive" / cid, turn,
                                                   eng.cfg.launchers[cell["harness"]].credential_names, run_lock=self.lock)
                    rows, digest, total, ms = copied.rows, copied.archive_hash, copied.total_bytes, copied.duration_ms
                rows = [{"run_id": self.plan["run_id"], "cell_id": cid, **r} for r in rows]
                for r in archive.append_missing_rows(folder, rows, present, "HB-LED-008"):
                    eng._append_now("archive_files", r)
                eng.append_row({"kind": "cell.turn_snapshot_archived", "cell_id": cid, "turn": turn,
                                "snapshot_hash": digest, "files": len(rows), "bytes": total, "duration_ms": ms,
                                "job_active_processes": None, "job_active_after": None, "copy_retries": None})
                return True
            except OSError:
                atomic.sweep_temps(self.run_dir / "archive" / cid, self.lock)
            except BenchError as exc:
                if exc.code == "HB-RUN-001":
                    raise
                return False
        return False

    def _archive(self, cell: dict) -> None:
        """C1: recover or write the final archive of a cell whose outcome stands; never re-run the cell."""
        eng, cid = self.eng, cell["cell_id"]
        launcher = eng.cfg.launchers[cell["harness"]]
        cell_dir = eng.cfg.cells_root / self.plan["run_id"] / cid
        if (cell_dir / "home").exists():
            launcher.clean(cell_dir / "home")  # DS 11: seeded credentials never reach the archive
        recorded = [r for r in self.rows["archive_files"] if r.get("cell_id") == cid and r.get("archive_attempt") == 1
                    and archive.snapshot_of(r) == "final"]
        archived = any(r["kind"] == "cell.archived" and r["cell_id"] == cid for r in self.rows["events"])
        try:
            if not cell_dir.exists():
                cell_dir.mkdir(parents=True)
            rec = archive.recover_archive(cell_dir, self.run_dir / "archive" / cid, 1, launcher.credential_names, recorded,
                                          run_lock=self.lock, recorded_archived=archived)
            for row in rec.missing_rows:
                eng._append_now("archive_files", {"run_id": self.plan["run_id"], "cell_id": cid, **row})
            if not archived:
                eng.append_row({"kind": "cell.archived", "cell_id": cid, "archive_attempt": 1,
                                "archive_hash": rec.result.archive_hash, "archive_bytes": rec.result.total_bytes})
                if archive.delete_after_verify(cell_dir, rec.result.folder, rec.result.rows):
                    eng.append_row({"kind": "cell.workspace_deleted", "cell_id": cid})
                else:
                    eng.append_row({"kind": "cell.workspace_kept", "cell_id": cid, "reason": "sharing violation after retries"})
        except (OSError, BenchError) as exc:
            if isinstance(exc, BenchError) and exc.code == "HB-RUN-001":
                raise
            eng.append_row({"kind": "cell.archive_failed", "cell_id": cid, "code": getattr(exc, "code", "HB-CELL-117"),
                            "detail": f"{type(exc).__name__}: {exc}"[:300]})
            eng.archive_failed.add(cid)
