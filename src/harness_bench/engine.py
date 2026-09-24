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
A budget or a detected host sleep terminates the cell's job; the outcome is recorded only after the job
reports no active process (kill -> confirm -> record). The parallelism slot is held from the launch
intent until the process is confirmed gone. The lock file's mtime is the heartbeat.
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
from collections.abc import Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from harness_bench import archive, driver, host, ledger, oslock, procs
from harness_bench.errors import BenchError, Cause
from harness_bench.gitsafe import GitError
from harness_bench.telemetry import normalize
from harness_bench.tools import BuildChanged

ENGINE_TRANSITIONS = frozenset({
    "run.started", "cell.launch_intent", "cell.workspace_built", "attempt.process_started", "attempt.session_opened",
    "cell.prompt_sent", "attempt.process_ended", "cell.outcome", "cell.archived", "cell.archive_failed", "cell.workspace_deleted",
    "cell.workspace_kept", "run.launch_stopped", "run.completed",
})
FACTS = ("events", "turn_usage", "archive_files")
USAGE_BUCKETS = ("uncached_input", "cache_read", "cache_write", "output", "reasoning")
STOP = "stop"  # the inbox item a worker sends to ask the engine thread to stop launching (not a ledger fact)
NO_MEMORY_STATUSES = {0xC0000017, 0xC000012D}
OOM_SIGNATURE = re.compile(rb"heap out of memory|out of memory|OutOfMemory", re.IGNORECASE)
COMPLETED_STOP_REASONS = {"end_turn", "max_tokens", "max_turn_requests", "refusal"}
CIRCUIT_BREAKER = 3
LOG_EXTRAS = ("detail", "pids", "fact", "win32_error")  # the only extras engine.log keeps (never argv, env or cell text)
DISK_FULL_WINERRORS = (39, 112)  # ERROR_HANDLE_DISK_FULL, ERROR_DISK_FULL
KILL_RETRY_CAP = 60.0  # seconds: the longest wait between retries of an unconfirmed kill (HB-RUN-002)
RECORD_POLL = 0.5  # seconds: how often a waiting worker re-checks that the engine can still record
log = logging.getLogger("harness_bench.engine")


class Launcher(Protocol):
    """How the engine starts one harness (profiles.ProfileLauncher for real ones; a fake in tests)."""

    harness: str
    credential_names: set[str]
    usage_source: str
    mode: str | None

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
    end_grace: float = 10.0
    loop_interval: float = 0.2


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
    ended: bool = False  # the turn is over: the worker ends the process itself; the engine never kills it now
    lock: threading.Lock = field(default_factory=threading.Lock)  # guards kill_reason/ended and terminate vs close


def read_events(run_dir: Path) -> list[dict]:
    rows = []
    for seg in sorted((run_dir / "events").glob("*.jsonl")):
        rows.extend(ledger.read_segment(seg))
    return rows


def process_alive(pid: int, created: int) -> bool:
    return host.process_alive(pid, created)


def span_id(trace_id: str, entity: str, phase: str) -> str:
    """Deterministic, so a log line written before its span is derived still joins it (design: Telemetry)."""
    return hashlib.sha256(f"{trace_id}|{entity}|{phase}".encode()).hexdigest()[:16]


class Engine:
    def __init__(self, plan: dict, config: EngineConfig) -> None:
        self.plan = plan
        self.cfg = config
        self.params = plan["parameters"]
        self.trace_id = plan["trace_id"]
        self.inbox: queue.Queue = queue.Queue(maxsize=64)
        self.writers: dict[str, ledger.SegmentWriter] = {}
        self.active: dict[str, _Active] = {}
        self.outcomes: dict[str, dict] = {}
        self.stopped: str | None = None
        self.broken = False
        self.closed = False
        self.archive_failed: set[str] = set()  # cells whose outcome stands but whose archive failed: the run is incomplete
        self.infra_streak = 0

    # the single writer ----------------------------------------------------------------------------

    def _append_now(self, fact: str, record: dict) -> dict:
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
                a.prompt_mono = time.monotonic()
        elif kind == "cell.outcome":
            self.outcomes[row["cell_id"]] = row
            cause = Cause[row["cause"]] if row["cause"] else None
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
        lock = oslock.RunLock.acquire(run_dir / ".lock", code="HB-RUN-003")
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
                else:
                    self._check_budgets()
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
        complete = not self.broken and not self.archive_failed and len(self.outcomes) == len(self.plan["cells"])
        return RunSummary(0 if complete else 3, dict(self.outcomes))

    def _stop_launching(self, code: str, reason: str) -> None:
        if self.stopped:
            return
        self.stopped = code
        try:
            self._append_now("events", {"kind": "run.launch_stopped", "code": code, "reason": reason})
        except BenchError:  # the ledger broke: the loop now aborts and drains
            pass

    def _launch(self, cell: dict) -> None:
        try:
            self._append_now("events", {"kind": "cell.launch_intent", "cell_id": cell["cell_id"], "label": cell["label"]})
        except BenchError:  # the ledger broke: this cell is never launched; the loop aborts and drains
            return
        a = _Active(cell, threading.Thread(target=self._cell_worker, args=(cell,), daemon=True, name=f"cell-{cell['cell_id']}"))
        self.active[cell["cell_id"]] = a
        a.thread.start()

    @staticmethod
    def _kill(a: _Active, reason: str | None) -> None:
        """EngineKill: terminate a live turn's job; the worker's turn ends at EOF, then it confirms and records.
        A turn that has already ended is never killed (nor classified by the kill): its worker is ending it."""
        with a.lock:
            if a.proc is None or a.ended or a.kill_reason:
                return
            a.kill_reason = reason
            a.proc.job.terminate()

    def _check_budgets(self) -> None:
        now = time.monotonic()
        for a in self.active.values():
            if a.prompt_mono and now - a.prompt_mono > a.cell["budget_seconds"]:
                self._kill(a, "timeout")

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
        try:
            info = self.cfg.build_workspace(cell, cell_dir)
        except (BenchError, GitError, OSError) as exc:
            self._outcome(cell, "failed", Cause.disk if _disk_full(exc) else Cause.workspace, detail=f"{type(exc).__name__}: {exc}")
            self._archive(cell, cell_dir, launcher)
            return
        self.record("events", {"kind": "cell.workspace_built", "cell_id": cid, **{k: v for k, v in info.items() if isinstance(v, (int, str))}})
        try:
            build = launcher.check_build()
        except BuildChanged as exc:
            self._outcome(cell, "failed", Cause.build_changed, detail=str(exc))
            self.request_stop(Cause.build_changed.code, str(exc))
            self._archive(cell, cell_dir, launcher)
            return
        traceparent = f"00-{self.trace_id}-{span_id(self.trace_id, cid, 'cell')}-01"
        argv, env = launcher.argv_env(cell, home, traceparent)  # before seed: a failure here leaves no credential copy
        try:
            launcher.seed(home, cell["model"])
            ended = self._attempt(self.active[cid], cell, launcher, build, argv, env, ws, home)
        finally:
            launcher.clean(home)  # every end: a spawn failure, a kill, a ledger failure, a bug (T-CELL-credclean)
        if isinstance(ended, procs.SpawnError):
            self._outcome(cell, "failed", Cause.spawn, detail=str(ended), win32_error=ended.win32_error or 0)
            self._archive(cell, cell_dir, launcher)
            return
        result, exit_status, tail = ended
        cause = self._classify(result, launcher, home, exit_status, tail, self.active[cid].kill_reason)
        for model, buckets in _usage_per_model(normalize.turn_usage({"_meta": (result.usage or {}).get("meta")})).items():
            self.record("turn_usage", {"kind": "turn_usage", "run_id": self.plan["run_id"], "cell_id": cid, "attempt": 1,
                                       "model": model, **buckets})
        outcome = "completed" if cause is None else ("timed_out" if cause is Cause.timed_out else "failed")
        # assume: the driver reports `last_update_seconds` (seam request req-01M38KX8503601BEP857749VVF to T3); until it
        # does, last_update_ms is null (not recorded), never a guessed number.
        last_update = getattr(result, "last_update_seconds", None)
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
        self._archive(cell, cell_dir, launcher)

    def _attempt(self, a: _Active, cell: dict, launcher: Launcher, build: dict, argv: list[str], env: dict, ws: Path,
                 home: Path) -> procs.SpawnError | tuple[driver.TurnResult, int | None, bytes]:
        """Spawn, the turn, then always: end the process, close the job, clean the credential copy, and only then
        record `attempt.process_ended` (a record can fail or wait; nothing live or secret is left behind it)."""
        cid = cell["cell_id"]
        try:
            cp = procs.spawn(argv, cwd=str(ws), env=env, stderr=subprocess.PIPE)
        except procs.SpawnError as exc:
            return exc
        with a.lock:
            a.proc = cp
        tail = bytearray()
        drain = threading.Thread(target=_keep_tail, args=(cp.proc.stderr, tail, self.params["stderr_tail_bytes"]), daemon=True)
        drain.start()

        def barrier(session_id: str | None) -> None:
            self.record("events", {"kind": "attempt.session_opened", "cell_id": cid, "session_id": session_id or ""})
            self.record("events", {"kind": "cell.prompt_sent", "cell_id": cid})

        exit_status: int | None = None
        started = False
        try:
            self.record("events", {"kind": "attempt.process_started", "cell_id": cid, "attempt": 1, "pid": cp.pid,
                                   "created_at": host.creation_time(cp.pid), "harness": launcher.harness,
                                   "build_version": build.get("version"), "build_sha256": build.get("sha256"),
                                   "credential_kind": "subscription login (copied)", "network_mode": "unrestricted"})
            started = True
            result = driver.run_turn(cp, cwd=ws, prompt=self.plan["tasks"][cell["task"]]["prompt"], mode=launcher.mode,
                                     handshake_timeout=self.params["handshake_timeout"], before_send=barrier)
        finally:
            with a.lock:
                a.ended = True
            try:
                exit_status, confirmed = self._end_process(cp)
                drain.join(timeout=5)
                ended = {"kind": "attempt.process_ended", "cell_id": cid, "exit_status": -1 if exit_status is None else exit_status,
                         "confirmed": int(confirmed), "peak_memory": cp.job.peak_memory(), "cpu_ms": cp.job.cpu_time_ms()}
            finally:
                with a.lock:
                    cp.close()
                launcher.clean(home)
            if started:  # an unrecorded start has no recorded end
                self.record("events", ended)
        return result, exit_status, bytes(tail)

    def _end_process(self, cp: procs.CellProcess) -> tuple[int | None, bool]:
        """Graceful first (stdin closed, the adapter flushes and exits), then terminate and confirm."""
        try:
            cp.proc.stdin.close()
        except OSError:
            pass
        deadline = time.monotonic() + self.cfg.end_grace
        while cp.job.active() and time.monotonic() < deadline:
            time.sleep(0.1)
        confirmed = cp.terminate_and_confirm(timeout=self.params["kill_escalation"])
        if not confirmed:  # a kill that never takes effect: logged once, retried with capped backoff, the slot held
            log.error("kill unconfirmed; retrying", extra={"error_code": "HB-RUN-002", "pids": sorted(cp.job.pids())})
        wait = 1.0
        while not confirmed:
            confirmed = cp.terminate_and_confirm(timeout=wait)
            wait = min(wait * 2, KILL_RETRY_CAP)
        try:
            return cp.wait(timeout=10), confirmed
        except subprocess.TimeoutExpired:
            return None, confirmed

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
            self.record("archive_files", {"kind": "archive_file", "run_id": self.plan["run_id"], "cell_id": cid, **row})
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


def configure_logging(run_dir: Path, trace_id: str) -> None:
    """engine.log: JSON lines with trace context and error codes; no cell text, no credentials, no argv."""

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

    handler = logging.FileHandler(run_dir / "engine.log", encoding="utf-8")
    handler.setFormatter(_Json())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
