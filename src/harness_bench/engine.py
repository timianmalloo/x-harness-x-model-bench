"""The run engine (ADR-0007, ADR-0013; design: Error & concurrency model), built to models/run_lifecycle.tla.

Pattern: Producer-Consumer over a bounded buffer, with a Single Writer. One worker thread per running
cell does the long work (working copy, spawn, the ACP turn, archive); the engine thread is the only
appender to every ledger fact of this process. A worker hands each record to the engine thread through
a bounded queue and blocks on a Future until the record is durable (the write-ahead intent / ack
barrier: `cell.prompt_sent` is fsynced before the prompt is written, model QueuePromptSent ->
PersistPromptSent -> SendPrompt). A failed append (HB-RUN-001) propagates to the worker, which then
never sends the prompt.

Per cell, in order: launch intent -> working copy -> build check -> spawn into a Job Object -> handshake
-> session opened -> prompt sent -> the turn -> the job terminated and confirmed empty (process ended)
-> cause classified (provider-error scan first) -> outcome -> archive -> verify -> delete.
A budget or a detected host sleep requests cancel, then terminates the job at the bounded grace if needed;
the outcome is recorded only after the job reports no active process (kill -> confirm -> record). The
parallelism slot is held from launch intent until the process is confirmed gone. The lock file's mtime
is the heartbeat.
"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import queue
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from harness_bench import archive, driver, host, ledger, lifecycle, oslock, procs
from harness_bench.errors import BenchError, Cause
from harness_bench.gitsafe import GitError
from harness_bench.scripted_user import log as scripted_log
from harness_bench.scripted_user import server as scripted_server
from harness_bench.telemetry import normalize
from harness_bench.tools import BuildChanged

FACTS = ("events", "turn_usage", "archive_files")
USAGE_BUCKETS = ("uncached_input", "cache_read", "cache_write", "output", "reasoning")
STOP = "stop"  # the inbox item a worker sends to ask the engine thread to stop launching (not a ledger fact)
NO_MEMORY_STATUSES = {0xC0000017, 0xC000012D}
OOM_SIGNATURE = re.compile(rb"heap out of memory|out of memory|OutOfMemory", re.IGNORECASE)
COMPLETED_STOP_REASONS = {"end_turn", "max_tokens", "max_turn_requests", "refusal"}
CIRCUIT_BREAKER = 3
LOG_EXTRAS = ("detail", "pids", "fact", "win32_error")  # the only extras engine.log keeps (never argv, env or cell text)
DISK_FULL_WINERRORS = (39, 112)  # ERROR_HANDLE_DISK_FULL, ERROR_DISK_FULL
KILL_RETRY_CAP = 30.0  # seconds: the longest wait between retries of an unconfirmed kill (HB-RUN-002)
RECORD_POLL = 0.5  # seconds: how often a waiting worker re-checks that the engine can still record
log = logging.getLogger("harness_bench.engine")


class Launcher(Protocol):
    """How the engine starts one harness (profiles.ProfileLauncher for real ones; a fake in tests)."""

    harness: str
    credential_names: set[str]
    credential_kind: str  # what attempt.process_started records, as the launcher reports it (R-13)
    usage_source: str
    mode: str | None
    set_model: bool  # run_turn gets model= (the ACP session/set_model pin) only when true (R-13)
    shutdown_grace: float

    def check_build(self) -> dict: ...
    def seed(self, home: Path, model: str) -> None: ...
    def clean(self, home: Path) -> None: ...
    def argv_env(self, cell: dict, home: Path, traceparent: str) -> tuple[list[str], dict]: ...
    def records(self, home: Path, session_id: str) -> list[Path]: ...
    def read(self, path: Path): ...


@dataclass
class EngineConfig:
    run_dir: Path
    cells_root: Path
    launchers: dict[str, Launcher]
    build_workspace: object  # (cell, cell_dir) -> dict info; the working copy is cell_dir / "ws"
    grade: object | None  # (run_dir) -> pass summary dict; run once after every cell is terminal (grade/runner.py)
    loop_interval: float = 0.2
    clock: Callable[[], float] = time.monotonic


@dataclass
class RunSummary:
    exit_code: int
    outcomes: dict[str, dict] = field(default_factory=dict)


@dataclass
class _Active:
    cell: dict
    thread: threading.Thread
    proc: procs.CellProcess | None = None
    prompt_mono: float | None = None
    kill_reason: str | None = None
    kill_deadline: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    terminated: bool = False
    ended: bool = False  # the turn is over: the worker ends the process itself; the engine never kills it now
    lock: threading.Lock = field(default_factory=threading.Lock)  # guards kill_reason/ended and terminate vs close


def span_id(trace_id: str, entity: str, phase: str) -> str:
    """Deterministic, so a log line written before its span is derived still joins it (design: Telemetry)."""
    return hashlib.sha256(f"{trace_id}|{entity}|{phase}".encode()).hexdigest()[:16]


class Engine:
    def __init__(self, plan: dict, config: EngineConfig) -> None:
        self.plan = plan
        self.cfg = config
        self.clock = config.clock if config is not None else time.monotonic
        self.params = plan["parameters"]
        self.trace_id = plan["trace_id"]
        self.inbox: queue.Queue = queue.Queue(maxsize=64)
        self.writers: dict[str, ledger.SegmentWriter] = {}
        self.active: dict[str, _Active] = {}
        self.outcomes: dict[str, dict] = {}
        self.stopped: str | None = None
        self.run_stopped: str | None = None
        self.applied_controls: set[str] = set()
        self.broken = False
        self.closed = False
        self.archive_failed: set[str] = set()  # cells whose outcome stands but whose archive failed: the run is incomplete
        self.infra_streak = 0

    # the single writer ----------------------------------------------------------------------------

    def _append_now(self, fact: str, record: dict) -> dict:
        if fact == "events":  # the lifecycle table is the one source of the transitions the engine may write
            lifecycle.check_writer(record.get("kind"), "engine")
        stamped = ledger.stamp(record)
        try:
            return self.writers[fact].append(stamped)
        except OSError as exc:  # a write or fsync failed: the ledger cannot be written; stop launching, run incomplete
            self.broken = True
            log.error("ledger append failed", extra={"error_code": "HB-RUN-001", "detail": str(exc), "fact": fact})
            raise BenchError("HB-RUN-001", f"append to {fact} failed: {exc}") from exc

    def record(self, fact: str, record: dict) -> dict:
        """Called by a worker: hand the record to the engine thread and wait until it is durable. Once the ledger
        is broken or the engine has ended, it fails at once (HB-RUN-001): no worker ever waits on a dead drain."""
        ledger.canonical(ledger.stamp(record))  # a bad record fails its own worker (TypeError), never the run
        if fact == "events":
            lifecycle.check_writer(record.get("kind"), "engine")  # ConformanceError, also in the worker
        future: Future = Future()
        while not self.closed:
            if self.broken:
                break
            try:
                self.inbox.put((fact, record, future), timeout=RECORD_POLL)
                break
            except queue.Full:
                continue
        while not future.done() and not self.closed and not self.broken:
            try:
                return future.result(timeout=RECORD_POLL)
            except FutureTimeout:
                continue
        if future.done():
            return future.result()
        raise BenchError("HB-RUN-001", f"{record.get('kind')} not recorded: the ledger is broken or the engine has ended")

    def _drain(self, wait: float) -> None:
        deadline = time.monotonic() + wait
        while True:
            timeout = max(deadline - time.monotonic(), 0)
            try:
                fact, record, future = self.inbox.get(timeout=timeout)
            except queue.Empty:
                return
            if self.broken or self.closed:  # queued behind the failure or the end: failed, never written
                future.set_exception(BenchError("HB-RUN-001", f"{record.get('kind')} not recorded: the ledger is broken"))
                continue
            if fact == STOP:  # a worker's request: the one stop path runs here, on the engine thread
                self._stop_launching(record["code"], record["reason"])
                future.set_result(record)
                continue
            try:
                row = self._append_now(fact, record)
            except (BenchError, TypeError, ValueError) as exc:  # handed to the worker; only an OSError broke the run
                future.set_exception(exc)
                continue
            self._after_append(row)
            future.set_result(row)

    def _after_append(self, row: dict) -> None:
        """Engine-thread bookkeeping of a durable row, done before its worker is released."""
        kind = row.get("kind")
        if kind == "cell.prompt_sent":
            a = self.active.get(row["cell_id"])
            if a:
                a.prompt_mono = self.clock()
        elif kind == "cell.outcome":
            self.outcomes[row["cell_id"]] = row
            cause = Cause[row["cause"]] if row["cause"] else None
            if row["outcome"] == "stopped":
                return
            if row["outcome"] == "skipped (decision)":
                return
            if cause is Cause.model_unavailable:
                return
            if cause and cause.invalidates:
                self.infra_streak += 1
                if self.infra_streak >= CIRCUIT_BREAKER:
                    self._stop_launching(cause.code, f"circuit breaker: {CIRCUIT_BREAKER} consecutive infrastructure failures")
            else:
                self.infra_streak = 0

    def request_stop(self, code: str, reason: str) -> None:
        """Called by a worker: ask the engine thread to stop launching; returns once the stop is decided."""
        self.record(STOP, {"code": code, "reason": reason})

    # run ------------------------------------------------------------------------------------------

    def run(self) -> RunSummary:
        run_dir = self.cfg.run_dir
        if (run_dir / "events").exists():
            raise BenchError("HB-USR-002", f"run {self.plan['run_id']} has already started; phase 1 re-runs under a new run id")
        run_dir.mkdir(parents=True, exist_ok=True)
        lock = oslock.RunLock.acquire(run_dir / ".lock", code="HB-RUN-005")
        segment = f"engine-{int(time.time())}"
        for fact in FACTS:
            self.writers[fact] = ledger.SegmentWriter.create(run_dir / fact, segment)
        host.keep_awake(True)
        sleep = host.SleepDetector(self.params["suspend_gap"])
        pending = list(self.plan["cells"])
        try:
            self._append_now("events", {"kind": "run.started", "run_id": self.plan["run_id"], "plan_hash": self.plan["plan_hash"],
                                        "trace_id": self.trace_id})
            while (pending and not self.stopped and not self.broken) or self.active:
                lock.heartbeat()
                self._drain(self.cfg.loop_interval)
                if self.broken:  # nothing more is recorded: kill every live turn, keep draining until the workers exit
                    self._kill_all("aborted")
                    self._check_kills(self.clock())
                else:
                    self._read_controls()
                    self.on_tick()
                    if sleep.slept():
                        self._kill_all("host_suspended")
                    if not self.stopped and min(_free_bytes(self.cfg.cells_root), _free_bytes(run_dir)) < self.params["disk_floor_bytes"]:
                        self._stop_launching("HB-RUN-004", "free space below the floor")
                    while pending and not self.stopped and not self.broken and len(self.active) < self.params["parallelism"]:
                        self._launch(pending.pop(0))
                for cell_id, a in list(self.active.items()):
                    if not a.thread.is_alive():
                        self.active.pop(cell_id)
            self._drain(0)
            grading = None
            ended_whole = not self.broken and not self.archive_failed  # else no run.completed: the run needs recovery
            if ended_whole and self.cfg.grade is not None:
                try:
                    with _beating(lock, self.cfg.loop_interval):  # the loop's heartbeat stops here; a pass can be long
                        grading = self.cfg.grade(self.cfg.run_dir)
                except Exception as exc:  # grading is re-runnable from the archive (US-26): never costs the run
                    code = _code(exc)
                    log.exception("grading pass failed; run bench grade", extra={"error_code": code})
                    grading = {"error_code": code}
            if ended_whole:
                self._read_controls(ending=True)
                heads = {fact: w.seal() for fact, w in self.writers.items() if fact != "events"}
                self._append_now("events", {"kind": "run.completed", "run_id": self.plan["run_id"],
                                            "segment_heads": {**heads, "events": self.writers["events"].head_hash},
                                            "cells_ended": len(self.outcomes), "grading": grading})
                self.writers["events"].seal()
        finally:
            self.closed = True  # a record() from now on fails at once instead of waiting on a drain that never comes
            self._drain(0)
            host.keep_awake(False)
            for w in self.writers.values():
                w.close()
            lock.release()
        complete = (not self.broken and not self.archive_failed and not self.run_stopped  # a stopped run exits 3 (design 5)
                    and len(self.outcomes) == len(self.plan["cells"]))
        return RunSummary(0 if complete else 3, dict(self.outcomes))

    def _stop_launching(self, code: str, reason: str) -> None:
        if self.stopped:
            return
        self.stopped = code
        try:
            self._append_now("events", {"kind": "run.launch_stopped", "code": code, "reason": reason})
        except BenchError:  # the ledger broke: the loop now aborts and drains
            pass

    def _apply_stop(self) -> None:
        self._stop_launching("HB-RUN-006", "bench stop")
        self._append_now("events", {"kind": "run.stopped", "code": "HB-RUN-006", "decision_id": None})
        self.run_stopped = "HB-RUN-006"
        log.info("stop applied", extra={"error_code": "HB-RUN-006"})
        self._kill_all("stop")

    def _read_controls(self, *, ending: bool = False) -> None:
        """Consume atomic control files on the single writer thread; retain I/O failures for the next tick."""
        folder = self.cfg.run_dir / "control"
        try:
            paths = list(folder.glob("*.json"))
        except OSError as exc:
            log.warning("control retried", extra={"error_code": "HB-USR-002", "detail": type(exc).__name__})
            return
        parsed = []
        for path in paths:
            try:
                raw = path.read_bytes()
            except OSError as exc:
                log.warning("control retried", extra={"error_code": "HB-USR-002", "detail": type(exc).__name__})
                continue
            try:
                if len(raw) > 4096:
                    raise ValueError("oversized")
                data = json.loads(raw)
                if not isinstance(data, dict) or set(data) != {"schema", "uuid", "control", "decision_id", "option", "requested_at"}:
                    raise ValueError("fields")
                uid = data["uuid"]
                if (data["schema"] != "bench-control/1" or not isinstance(uid, str)
                        or not re.fullmatch(r"[0-9a-f]{32}", uid) or path.stem != uid
                        or data["control"] not in {"stop", "answer"}
                        or not isinstance(data["requested_at"], str)
                        or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["requested_at"])):
                    raise ValueError("schema")
                datetime.fromisoformat(data["requested_at"])
                if data["control"] == "stop" and (data["decision_id"] is not None or data["option"] is not None):
                    raise ValueError("stop fields")
                if data["control"] == "answer" and (not isinstance(data["decision_id"], str)
                        or not re.fullmatch(r"D[1-9][0-9]*", data["decision_id"])
                        or not isinstance(data["option"], str) or not re.fullmatch(r"[a-z_]+", data["option"])):
                    raise ValueError("answer fields")
            except (ValueError, TypeError, UnicodeDecodeError):
                try:
                    path.replace(path.with_suffix(".rejected"))
                except OSError as exc:
                    log.warning("control retried", extra={"error_code": "HB-USR-002", "detail": type(exc).__name__})
                    continue
                log.warning("control rejected", extra={"error_code": "HB-USR-002", "detail": path.name})
                continue
            parsed.append((path, data))
        parsed.sort(key=lambda item: (item[1]["control"] != "stop", item[1]["requested_at"], item[1]["uuid"]))
        for path, data in parsed:
            uid = data["uuid"]
            if uid in self.applied_controls:
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            effect = ("no-op (run ending)" if ending else "no-op (already stopped)" if self.run_stopped
                      else "applied" if data["control"] == "stop" else "rejected (invalid)")
            try:
                self._append_now("events", {"kind": "control.applied", "uuid": uid, "control": data["control"],
                                             "decision_id": data["decision_id"], "effect": effect})
                self.applied_controls.add(uid)
                if effect == "applied":
                    self._apply_stop()
            except BenchError:  # the ledger broke (self.broken): the loop now kills, aborts and drains; the file stays
                return
            try:
                path.unlink()
            except OSError as exc:
                log.warning("control retried", extra={"error_code": "HB-USR-002", "detail": type(exc).__name__})

    def _launch(self, cell: dict) -> None:
        try:
            self._append_now("events", {"kind": "cell.launch_intent", "cell_id": cell["cell_id"], "label": cell["label"]})
        except BenchError:  # the ledger broke: this cell is never launched; the loop aborts and drains
            return
        a = _Active(cell, threading.Thread(target=self._cell_worker, args=(cell,), daemon=True, name=f"cell-{cell['cell_id']}"))
        self.active[cell["cell_id"]] = a
        a.thread.start()

    def _kill(self, a: _Active, reason: str | None) -> None:
        """Request a cooperative end. The first reason owns the one hard deadline."""
        with a.lock:
            if a.ended or a.kill_reason:
                return
            a.kill_reason = reason
            a.kill_deadline = self.clock() + self.cfg.launchers[a.cell["harness"]].shutdown_grace
            a.cancel.set()

    def on_tick(self) -> None:
        """Read the engine clock once for budget and escalation decisions."""
        now = self.clock()
        self._check_budgets(now)
        self._check_kills(now)

    def _check_budgets(self, now: float) -> None:
        for a in self.active.values():
            if a.prompt_mono is not None and now - a.prompt_mono > a.cell["budget_seconds"]:
                self._kill(a, "timeout")

    def _check_kills(self, now: float) -> None:
        for a in self.active.values():
            with a.lock:
                if (a.kill_deadline is None or now < a.kill_deadline or a.ended
                        or a.proc is None or not _job_query(a.proc.job.active, 1)):
                    continue
                a.terminated = True
                _job_query(a.proc.job.terminate, None)  # retry on later ticks while the job remains active

    def _kill_all(self, reason: str) -> None:
        for a in self.active.values():
            self._kill(a, reason)

    # one cell (worker thread) ---------------------------------------------------------------------

    def _cell_worker(self, cell: dict) -> None:
        cid = cell["cell_id"]
        try:
            self._run_cell(cell)
        except Exception as exc:  # the unclassified bucket (target 0): logged with its stack, recorded
            code = _code(exc)
            if code == "HB-RUN-001":
                log.error("cell stopped: ledger unavailable", extra={"cell_id": cid, "error_code": code})
                return
            log.exception("cell failure", extra={"cell_id": cid, "error_code": code})
            detail = f"{type(exc).__name__}: {exc}"[:300]
            try:
                if cid not in self.outcomes:
                    self._outcome(cell, "failed", Cause.disk if _disk_full(exc) else Cause.unclassified, detail=detail)
                else:  # after the outcome: its archive failed; the workspace is the only copy, so it is kept
                    self.record("events", {"kind": "cell.archive_failed", "cell_id": cid, "code": code, "detail": detail})
                    self.archive_failed.add(cid)
            except BenchError:
                pass

    def _outcome(self, cell: dict, outcome: str, cause: Cause | None, **extra) -> dict:
        row = {"kind": "cell.outcome", "cell_id": cell["cell_id"], "outcome": outcome,
               "cause": cause.name if cause else None, "code": cause.code if cause else None,
               "host_mem_available": host.available_memory(), **extra}
        return self.record("events", row)  # the engine thread counts it (outcomes, circuit breaker) before returning

    def _run_cell(self, cell: dict) -> None:
        cid = cell["cell_id"]
        launcher = self.cfg.launchers[cell["harness"]]
        cell_dir = self.cfg.cells_root / self.plan["run_id"] / cid
        home, ws = cell_dir / "home", cell_dir / "ws"
        task = self.plan["tasks"][cell["task"]]

        def archive_after_outcome() -> None:
            if task.get("scripted_user"):
                cell_dir.mkdir(parents=True, exist_ok=True)
                scripted_log.close_log(cell_dir / "scripted-user.jsonl",
                                       scripted_log.header_row(cell["task"], task["clarifications_sha256"],
                                                               task["matcher_version"]))
            self._archive(cell, cell_dir, launcher)

        try:
            info = self.cfg.build_workspace(cell, cell_dir)
        except (BenchError, GitError, OSError) as exc:
            self._outcome(cell, "failed", Cause.disk if _disk_full(exc) else Cause.workspace, detail=f"{type(exc).__name__}: {exc}")
            archive_after_outcome()
            return
        self.record("events", {"kind": "cell.workspace_built", "cell_id": cid, **{k: v for k, v in info.items() if isinstance(v, (int, str))}})
        try:
            build = launcher.check_build()
        except BuildChanged as exc:
            self._outcome(cell, "failed", Cause.build_changed, detail=str(exc))
            self.request_stop(Cause.build_changed.code, str(exc))
            archive_after_outcome()
            return
        if self.active[cid].cancel.is_set():
            reason = self.active[cid].kill_reason
            cause = Cause.timed_out if reason == "timeout" else Cause.host_suspended if reason == "host_suspended" else None
            self._outcome(cell, "stopped" if reason == "stop" else "timed_out" if cause is Cause.timed_out else "failed", cause)
            archive_after_outcome()
            return
        traceparent = f"00-{self.trace_id}-{span_id(self.trace_id, cid, 'cell')}-01"
        argv_cell = cell
        if task.get("scripted_user") and cell["harness"] == "copilot":
            entry = scripted_server.entry(Path(task["clarifications_path"]), cell_dir / "scripted-user.jsonl")
            mcp_config = cell_dir / "mcp-config.json"
            mcp_config.write_text(json.dumps({"mcpServers": {entry["name"]: {
                "type": "local", "command": entry["command"], "args": entry["args"], "tools": ["*"],
                "env": {item["name"]: item["value"] for item in entry["env"]}}}}), encoding="utf-8")
            argv_cell = {**cell, "mcp_config": mcp_config}
        argv, env = launcher.argv_env(argv_cell, home, traceparent)  # before seed: no credential copy on failure
        try:
            launcher.seed(home, cell["model"])
            ended = self._attempt(self.active[cid], cell, launcher, build, argv, env, ws)
        finally:
            launcher.clean(home)  # every end: a spawn failure, a kill, a ledger failure, a bug (T-CELL-credclean)
        if isinstance(ended, procs.SpawnError):
            if self.active[cid].kill_reason == "stop":
                self._outcome(cell, "stopped", None)
            else:
                self._outcome(cell, "failed", Cause.spawn, detail=str(ended), win32_error=ended.win32_error or 0)
            archive_after_outcome()
            return
        result, exit_status, tail = ended
        kill_reason = self.active[cid].kill_reason
        cause = None if kill_reason == "stop" else self._classify(result, launcher, home, exit_status, tail, kill_reason)
        for model, buckets in _usage_per_model(normalize.turn_usage({"_meta": (result.usage or {}).get("meta")})).items():
            self.record("turn_usage", {"kind": "turn_usage", "run_id": self.plan["run_id"], "cell_id": cid, "attempt": 1,
                                       "model": model, **buckets})
        outcome = "stopped" if kill_reason == "stop" else "completed" if cause is None else (
            "timed_out" if cause is Cause.timed_out else "failed")
        last_update = result.last_update_seconds
        self._outcome(cell, outcome, cause, detail=result.detail[:300], stop_reason=result.stop_reason or "",
                      session_id=result.session_id or "", permission_requests=result.permission_requests,
                      exit_status=exit_status if exit_status is not None else -1,
                      handshake_ms=int(result.handshake_seconds * 1000), turn_ms=int(result.turn_seconds * 1000),
                      updates=result.updates, last_update_ms=None if last_update is None else int(last_update * 1000))
        if tail:  # best effort, after the outcome: a failed write loses only the tail, never the outcome
            try:
                (cell_dir / "adapter-stderr-tail.log").write_bytes(tail)
            except OSError as exc:
                log.warning("adapter stderr tail not kept", extra={"cell_id": cid, "error_code": _code(exc), "detail": str(exc)})
        archive_after_outcome()

    def _attempt(self, a: _Active, cell: dict, launcher: Launcher, build: dict, argv: list[str], env: dict,
                 ws: Path) -> procs.SpawnError | tuple[driver.TurnResult, int | None, bytes]:
        """Spawn, the turn, then always: end the process and close the job, and only then record
        `attempt.process_ended` (a record can fail; nothing live is left behind it). The caller cleans the home."""
        cid = cell["cell_id"]
        task = self.plan["tasks"][cell["task"]]
        mcp_servers = ([scripted_server.entry(Path(task["clarifications_path"]), ws.parent / "scripted-user.jsonl")]
                       if task.get("scripted_user") and cell["harness"] != "copilot" else [])
        with a.lock:
            if a.kill_reason is not None:  # the stop won before the spawn linearization point
                return procs.SpawnError("stopped before spawn", None)
        try:
            cp = procs.spawn(argv, cwd=str(ws), env=env, stderr=subprocess.PIPE)
        except procs.SpawnError as exc:
            return exc
        with a.lock:
            a.proc = cp
            if a.kill_reason is not None:  # the stop raced a spawn that had already passed its check
                a.terminated = True
                _job_query(cp.job.terminate, None)
        tail = bytearray()
        drain = threading.Thread(target=_keep_tail, args=(cp.proc.stderr, tail, self.params["stderr_tail_bytes"]), daemon=True)
        drain.start()

        result = driver.TurnResult()  # filled by run_turn; the barrier reads agent_version from it (R-28)

        def barrier(session_id: str | None) -> None:
            self.record("events", {"kind": "attempt.session_opened", "cell_id": cid, "session_id": session_id or "",
                                   "agent_version": result.agent_version,
                                   "permission_mode_effective": result.permission_mode_effective})  # R-34
            self.record("events", {"kind": "cell.prompt_sent", "cell_id": cid})

        exit_status: int | None = None
        started = False
        try:
            self.record("events", {"kind": "attempt.process_started", "cell_id": cid, "attempt": 1, "pid": cp.pid,
                                   "created_at": host.creation_time(cp.pid), "harness": launcher.harness,
                                   "build_version": build.get("version"), "build_sha256": build.get("sha256"),
                                   "credential_kind": launcher.credential_kind, "network_mode": "unrestricted"})
            started = True
            result = driver.run_turn(cp, cwd=ws, prompt=self.plan["tasks"][cell["task"]]["prompt"], mode=launcher.mode,
                                     handshake_timeout=self.params["handshake_timeout"], before_send=barrier,
                                     model=cell["model"] if launcher.set_model else None, result=result,
                                     mcp_servers=mcp_servers, cancel=a.cancel)
        finally:
            with a.lock:
                a.ended = True
            try:
                exit_status, confirmed, ended_by = self._end_process(a, cp, launcher.shutdown_grace)
                drain.join(timeout=5)
                turn_models = [u.model for u in normalize.turn_usage({"_meta": (result.usage or {}).get("meta")})]
                tag = next((t for m in turn_models if (t := normalize.context_window_tag(m)) is not None), None)
                ended = {"kind": "attempt.process_ended", "cell_id": cid, "exit_status": -1 if exit_status is None else exit_status,
                         "confirmed": int(confirmed), "ended_by": ended_by,
                         "peak_memory": _job_query(cp.job.peak_memory, None),
                         "cpu_ms": _job_query(cp.job.cpu_time_ms, None),  # null: not recorded, never a zeroed guess
                         "acp_usage": result.usage,  # R-24: the adapter's usage and _meta halves verbatim, or null
                         "context_window_tag": tag}  # R-32: e.g. "1m" from a served model id, disclosed; else None
            finally:
                with a.lock:
                    cp.close()
            if started:  # an unrecorded start has no recorded end
                self.record("events", ended)
        return result, exit_status, bytes(tail)

    def _end_process(self, a: _Active, cp: procs.CellProcess, grace: float) -> tuple[int | None, bool, str]:
        """Graceful first (stdin closed, the adapter flushes and exits), then terminate and confirm."""
        try:
            cp.proc.stdin.close()
        except (OSError, ValueError):
            pass
        with a.lock:
            remaining = grace if a.kill_deadline is None else max(0.0, a.kill_deadline - self.clock())
        deadline = time.monotonic() + min(grace, remaining)
        while _job_query(cp.job.active, 1) and time.monotonic() < deadline:
            time.sleep(0.05)
        with a.lock:
            active = _job_query(cp.job.active, 1)
            if active and not a.terminated:
                a.terminated = True
            terminated = a.terminated
        confirmed = not active or _confirm(cp, self.params["kill_escalation"])
        if not confirmed:  # a kill that never takes effect: logged once, retried with capped backoff, the slot held
            log.error("kill unconfirmed; retrying", extra={"error_code": "HB-RUN-002",
                                                           "pids": _job_query(lambda: sorted(cp.job.pids()), [])})
        wait = 1.0
        while not confirmed:
            confirmed = _confirm(cp, wait)
            wait = min(wait * 2, KILL_RETRY_CAP)
        try:
            return cp.wait(timeout=10), confirmed, ("terminate" if terminated else "grace" if a.kill_reason else "exit")
        except subprocess.TimeoutExpired:
            return None, confirmed, ("terminate" if terminated else "grace" if a.kill_reason else "exit")

    def _classify(self, result: driver.TurnResult, launcher: Launcher, home: Path, exit_status: int | None,
                  tail: bytes, kill_reason: str | None) -> Cause | None:
        """Precedence: provider/model error in the native record > budget kill > host sleep > memory > driver cause."""
        errors = []
        for path in launcher.records(home, result.session_id or ""):
            errors.extend(launcher.read(path).errors)
        scanned = normalize.classify(errors)
        if scanned:
            return scanned
        if kill_reason == "timeout":
            return Cause.timed_out
        if kill_reason == "host_suspended":
            return Cause.host_suspended
        if exit_status in NO_MEMORY_STATUSES or OOM_SIGNATURE.search(tail):
            return Cause.memory
        if result.cause:
            return result.cause
        if result.stop_reason in COMPLETED_STOP_REASONS:
            return None
        return Cause.adapter_crash

    def _archive(self, cell: dict, cell_dir: Path, launcher: Launcher) -> None:
        cid = cell["cell_id"]
        if not cell_dir.exists():
            cell_dir.mkdir(parents=True)
        result = archive.archive_cell(cell_dir, self.cfg.run_dir / "archive" / cid, attempt=1, exclude_names=launcher.credential_names)
        for row in result.rows:
            self.record("archive_files", {"run_id": self.plan["run_id"], "cell_id": cid, **row})
        self.record("events", {"kind": "cell.archived", "cell_id": cid, "archive_attempt": 1, "archive_hash": result.archive_hash,
                               "archive_bytes": result.total_bytes})
        if archive.delete_after_verify(cell_dir, result.folder, result.rows):
            self.record("events", {"kind": "cell.workspace_deleted", "cell_id": cid})
        else:
            self.record("events", {"kind": "cell.workspace_kept", "cell_id": cid, "reason": "sharing violation after retries"})


@contextmanager
def _beating(lock: oslock.RunLock, interval: float) -> Iterator[None]:
    """Keep the lock's mtime (the heartbeat) fresh while the engine thread is busy outside its loop."""
    stop = threading.Event()

    def beat() -> None:
        while not stop.wait(interval):
            try:
                lock.heartbeat()
            except OSError:  # a missed beat reads as stale in `bench status`; it never costs the run
                pass

    thread = threading.Thread(target=beat, daemon=True, name="heartbeat")
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def _job_query(query, failed):
    """A job query, or `failed` when it raises OSError (procs raises from the last Win32 error, T3-5)."""
    try:
        return query()
    except OSError:
        return failed


def _confirm(cp: procs.CellProcess, timeout: float) -> bool:
    """terminate_and_confirm; a failed job query means the kill is not confirmed (the slot stays held)."""
    return _job_query(lambda: cp.terminate_and_confirm(timeout=timeout), False)


def _usage_per_model(entries: list[normalize.TurnUsage]) -> dict[str, dict[str, int]]:
    """One total per model: a turn_usage row's key is (run, cell, attempt, model), so entries are summed first."""
    totals: dict[str, dict[str, int]] = {}
    for u in entries:
        bucket = totals.setdefault(u.model, dict.fromkeys(USAGE_BUCKETS, 0))
        for name in USAGE_BUCKETS:
            bucket[name] += getattr(u, name)
    return totals


def _code(exc: BaseException) -> str:
    """The stable code a failure is recorded under: its own, or the unclassified bucket."""
    if isinstance(exc, BenchError):
        return exc.code
    return Cause.disk.code if _disk_full(exc) else Cause.unclassified.code


def _disk_full(exc: BaseException) -> bool:
    """ENOSPC, or Windows ERROR_HANDLE_DISK_FULL / ERROR_DISK_FULL."""
    return isinstance(exc, OSError) and (exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) in DISK_FULL_WINERRORS)


def _free_bytes(path: Path) -> int:
    """Free bytes on the volume that holds `path` (or its nearest existing ancestor: a mount point counts)."""
    while not path.exists() and path.parent != path:
        path = path.parent
    return shutil.disk_usage(path).free


def _keep_tail(stream, tail: bytearray, limit: int) -> None:
    try:
        for chunk in iter(lambda: stream.read1(65536), b""):
            tail.extend(chunk)
            if len(tail) > limit:
                del tail[:-limit]
    except (OSError, ValueError):
        pass


def configure_logging(run_dir: Path, trace_id: str) -> logging.FileHandler:
    """engine.log: JSON lines with trace context and error codes; no cell text, no credentials, no argv.

    Closes and removes any FileHandler a previous call left on this logger before installing the new
    one (tracked as an attribute of this function, not a module global, so the change stays inside
    this function): otherwise two runs in one process cross-contaminate each other's engine.log, and
    a finished run's file is left open, which Windows then refuses to delete (T9-2). Returns the new
    handler so the caller (cli.cmd_run) can release it once its own run ends.
    """

    class _Json(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            entity = getattr(record, "cell_id", "run")
            body = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "severity_number": record.levelno,
                    "severity_text": record.levelname, "trace_id": trace_id, "span_id": span_id(trace_id, entity, "engine"),
                    "event": record.getMessage(), "error_code": getattr(record, "error_code", None), "cell_id": entity}
            body.update({k: getattr(record, k) for k in LOG_EXTRAS if hasattr(record, k)})
            if record.exc_info:
                body["exception.stacktrace"] = self.formatException(record.exc_info)
            return json.dumps(body)

    previous = getattr(configure_logging, "_installed", None)
    if previous is not None:
        log.removeHandler(previous)
        previous.close()

    handler = logging.FileHandler(run_dir / "engine.log", encoding="utf-8")
    handler.setFormatter(_Json())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    configure_logging._installed = handler
    return handler
