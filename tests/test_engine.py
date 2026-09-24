"""The run engine (ADR-0007, ADR-0013; design: Error & concurrency model) against the fake ACP agent.

Each test runs the real engine: real ledger, real Job Objects, real archive; only the harness is the
fake agent and the working-copy builder is a stub (the real one is covered in test_workspace.py).
Every run's events are replayed against the model's phase-1 guards (lifecycle.replay, US-44 AC3).
"""

import errno
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from harness_bench import engine, host, ledger, lifecycle, plan
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code

pytestmark = pytest.mark.native
FAKE = Path(__file__).parent / "fake_acp_agent.py"
ROOT = Path(__file__).resolve().parents[1]
RUN_LIMIT = 120  # seconds: the bound on any one engine run in these tests
SECRET = "sk-ant-FAKE-login-5f1c0de"  # the copied login the fake launcher seeds (T-CELL-credclean, T-LOG-nosecret)
USAGE = [{"model": "fake-model", "token_count": {"inputTokens": 3, "cachedInputTokens": 30, "cachedWriteTokens": 7,
                                                 "outputTokens": 5, "reasoningOutputTokens": 0}}]


class FakeLauncher:
    """A Launcher (engine protocol) that runs the fake ACP agent; behaviour per cell label."""

    harness = "fake"
    credential_names = frozenset({".credentials.json"})
    usage_source = "acp_turn"
    mode = None

    def __init__(self, behaviours: dict[str, dict], build_changed: bool = False, missing_exe: bool = False,
                 build_changed_for: set[str] | None = None):
        self.behaviours = behaviours
        self.build_changed = build_changed
        self.missing_exe = missing_exe
        self.build_changed_for = build_changed_for or set()  # cell ids (the engine names each worker thread cell-<id>)

    def check_build(self) -> dict:
        import threading
        if self.build_changed or threading.current_thread().name.removeprefix("cell-") in self.build_changed_for:
            from harness_bench.tools import BuildChanged
            raise BuildChanged("fake", "binary replaced after planning")
        return {"version": "0", "sha256": "f" * 64, "adapter_version": "0", "adapter_sha256": "e" * 64}

    def seed(self, home: Path, model: str) -> None:
        home.mkdir(parents=True, exist_ok=True)
        (home / ".credentials.json").write_text(json.dumps({"token": SECRET}), encoding="utf-8")

    def clean(self, home: Path) -> None:
        (home / ".credentials.json").unlink(missing_ok=True)

    def argv_env(self, cell: dict, home: Path, traceparent: str):
        cfg = {"mode": "ok", "record_dir": str(home), "usage": USAGE, **self.behaviours.get(cell["label"], {})}
        exe = str(home / "missing.exe") if self.missing_exe else sys.executable
        return [exe, str(FAKE)], dict(os.environ, FAKE_ACP=json.dumps(cfg), TRACEPARENT=traceparent)

    def records(self, home: Path, session_id: str) -> list[Path]:
        return sorted(home.glob(f"projects/**/{session_id}.jsonl"))

    def read(self, path: Path):
        return claude_code.read(path)


def _plan(n_cells=2, budget=60, parallelism=2, labels=None):
    cells = []
    for i in range(n_cells):
        c = plan.Cell("X1", "v1", 5, f"combo{i}", "fake", "fake-model", "on" if i % 2 == 0 else "off", 1, budget)
        cells.append({"cell_id": c.id, "label": labels[i] if labels else c.label, **c.__dict__})
    return {"run_id": "r-" + uuid.uuid4().hex[:6], "plan_hash": "p" * 64, "trace_id": "a" * 32,
            "parameters": {**plan.DEFAULT_PARAMETERS, "parallelism": parallelism, "disk_floor_bytes": 1024},
            "tasks": {"X1": {"prompt": "Implement slugify.\n"}}, "cells": cells, "builds": {"fake": {}}}


def _build_workspace(cell: dict, cell_dir: Path) -> dict:
    ws = cell_dir / "ws"
    ws.mkdir(parents=True)
    (ws / "slug.py").write_text("def slugify(t): raise NotImplementedError\n", encoding="utf-8")
    return {"pack_manifest": 0}


def _engine_run(p, config, limit=RUN_LIMIT):
    """Run the engine on its own thread with a bounded wait, so a missing guard fails the test fast, never hangs it."""
    box = {}

    def target():
        try:
            box["summary"] = engine.Engine(p, config).run()
        except BenchError as exc:  # handed back to the test thread below; anything else fails the test on "summary"
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True, name="engine-under-test")
    t.start()
    t.join(limit)
    assert not t.is_alive(), f"the engine did not finish within {limit} s"
    if "error" in box:
        raise box["error"]
    return box["summary"]


def _run(base, p, launcher, limit=RUN_LIMIT, **cfg):
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": launcher}, build_workspace=cfg.pop("build_workspace", _build_workspace),
                                 grade=cfg.pop("grade", None), end_grace=cfg.pop("end_grace", 5), **cfg)
    summary = _engine_run(p, config, limit)
    events = _events(config.run_dir)
    lifecycle.replay(events, parallelism=p["parameters"]["parallelism"])  # conformance (US-44 AC3)
    return summary, events, config


def _events(run_dir: Path) -> list[dict]:
    return [row for seg in sorted((run_dir / "events").glob("*.jsonl")) for row in ledger.read_segment(seg)]


def _outcomes(events):
    return {e["cell_id"]: e for e in events if e["kind"] == "cell.outcome"}


def test_the_engine_keeps_no_dead_helpers_or_literals(base):  # T1-17 (Simplifier minors)
    assert not hasattr(engine, "process_alive") and not hasattr(engine, "read_events")  # host / the ledger own these
    _, _, config = _run(base, _plan(n_cells=1), FakeLauncher({}))
    rows = ledger.read_segment(next((config.run_dir / "archive_files").glob("*.jsonl")))
    assert rows and not any("kind" in r for r in rows)  # a fact's rows are typed by the fact, not a literal


def test_happy_run_completes_archives_and_deletes_every_cell(base):
    p = _plan()
    summary, events, config = _run(base, p, FakeLauncher({}))
    outs = _outcomes(events)
    assert {o["outcome"] for o in outs.values()} == {"completed"} and len(outs) == 2
    for cell in p["cells"]:
        kinds = [e["kind"] for e in events if e.get("cell_id") == cell["cell_id"]]
        assert kinds == ["cell.launch_intent", "cell.workspace_built", "attempt.process_started", "attempt.session_opened",
                         "cell.prompt_sent", "attempt.process_ended", "cell.outcome", "cell.archived", "cell.workspace_deleted"]
        assert not (config.cells_root / p["run_id"] / cell["cell_id"]).exists()
    assert events[-1]["kind"] == "run.completed" and summary.exit_code == 0
    assert [e["exit_status"] for e in events if e["kind"] == "attempt.process_ended"] == [0, 0]  # the real status
    for e in events:
        if e["kind"] == "attempt.process_started":  # every cell process is gone, not just recorded as ended
            assert not host.process_alive(e["pid"], e["created_at"])
    for fact in ("events", "turn_usage", "archive_files"):
        for seg in (config.run_dir / fact).glob("*.jsonl"):
            assert ledger.verify_segment(seg).sealed


def test_the_engine_grades_once_after_every_cell_is_archived_and_records_the_pass(base):
    p = _plan()
    calls = []

    def grade(run_dir):
        archived = [e["cell_id"] for e in _events(run_dir) if e["kind"] == "cell.archived"]
        calls.append(sorted(archived))
        return {"grading_id": "grade-x", "heads": {"scores": "h" * 64}, "cells_graded": len(archived)}

    summary, events, _ = _run(base, p, FakeLauncher({}), grade=grade)
    assert calls == [sorted(c["cell_id"] for c in p["cells"])]
    assert events[-1]["grading"] == {"grading_id": "grade-x", "heads": {"scores": "h" * 64}, "cells_graded": 2}
    assert summary.exit_code == 0


def test_the_heartbeat_runs_during_the_grading_hook(base):  # T1-10: a long pass never looks like a stalled engine
    seen = []

    def grade(run_dir):
        lock = run_dir / ".lock"
        start = lock.stat().st_mtime_ns
        time.sleep(1.5)
        seen.append(lock.stat().st_mtime_ns - start)
        return {"grading_id": "grade-x"}

    _run(base, _plan(n_cells=1), FakeLauncher({}), grade=grade)
    assert seen and seen[0] > 0, "the lock's mtime (the heartbeat) did not move while grading"


def test_a_failed_grading_pass_never_costs_the_run(base):  # re-gradable from the archive (US-26)
    def grade(run_dir):
        raise BenchError("HB-GRD-001", "held by bench grade")

    summary, events, config = _run(base, _plan(n_cells=1), FakeLauncher({}), grade=grade)
    assert events[-1]["kind"] == "run.completed" and summary.exit_code == 0
    assert events[-1]["grading"] == {"error_code": "HB-GRD-001"}
    assert ledger.verify_segment(next((config.run_dir / "events").glob("*.jsonl"))).sealed


def test_verbatim_prompt_reaches_the_agent_and_turn_usage_is_recorded(base):
    p = _plan(n_cells=1)
    p["tasks"]["X1"]["prompt"] = "Implement slugify.\r\nKeep the signature.\n"  # the plan's frozen task prompt (US-10)
    _, _, config = _run(base, p, FakeLauncher({}))
    archive = config.run_dir / "archive" / p["cells"][0]["cell_id"] / "attempt-1" / "ws" / ".fake-prompt.txt"
    assert archive.read_bytes().decode("utf-8") == p["tasks"]["X1"]["prompt"]
    usage = ledger.read_segment(next((config.run_dir / "turn_usage").glob("*.jsonl")))
    assert [(u["model"], u["uncached_input"], u["cache_read"], u["cache_write"], u["output"]) for u in usage] == [("fake-model", 3, 30, 7, 5)]


def test_turn_usage_is_summed_per_model_before_it_is_recorded(base):  # T1-6: one row per (cell, attempt, model)
    tc = {"inputTokens": 1, "cachedInputTokens": 2, "cachedWriteTokens": 3, "outputTokens": 4, "reasoningOutputTokens": 5}
    usage = [{"model": "m-a", "token_count": tc}, {"model": "m-b", "token_count": tc}, {"model": "m-a", "token_count": tc}]
    p = _plan(n_cells=1)
    _, _, config = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"usage": usage}}))
    rows = ledger.read_segment(next((config.run_dir / "turn_usage").glob("*.jsonl")))
    assert sorted((u["model"], u["uncached_input"], u["cache_read"], u["cache_write"], u["output"], u["reasoning"]) for u in rows) == [
        ("m-a", 2, 4, 6, 8, 10), ("m-b", 1, 2, 3, 4, 5)]


def test_the_outcome_records_updates_and_last_update_ms(base, monkeypatch):  # T1-11
    from harness_bench import driver
    real = driver.run_turn

    def with_last_update(*args, **kwargs):  # the driver half is seam request req-01M38KX8503601BEP857749VVF (T3)
        result = real(*args, **kwargs)
        result.last_update_seconds = 0.25
        return result

    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    first = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert first["updates"] == 1 and "last_update_ms" in first  # null (not recorded) until the driver reports it
    monkeypatch.setattr(driver, "run_turn", with_last_update)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["last_update_ms"] == 250


def test_budget_kill_is_timed_out_and_recorded_only_after_the_tree_is_gone(base):  # T-ENG-budget
    p = _plan(n_cells=1, budget=2)
    started = time.monotonic()
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "hang_prompt"}}), limit=45)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert out["outcome"] == "timed_out" and out["code"] == "HB-CELL-301"
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["confirmed"] == 1 and ended["seq"] < out["seq"]
    assert time.monotonic() - started < 45


def test_a_budget_expiring_after_the_turn_ended_is_not_a_timeout(base):  # T1-1: ended before the graceful end
    p = _plan(n_cells=1, budget=2)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"linger": 8}}), end_grace=6)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["stop_reason"], out["cause"]) == ("completed", "end_turn", None)


def test_provider_error_takes_precedence_and_invalidates(base):  # T-ENG-provider-timeout
    p = _plan(n_cells=1, budget=2)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "provider_error"}}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["cause"], out["code"]) == ("failed", "provider", "HB-CELL-108")


def test_a_provider_error_outranks_a_budget_kill(base):  # T-ENG-provider-timeout (precedence)
    p = _plan(n_cells=1, budget=2)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "provider_error", "hang": True}}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "provider"


def test_the_adapter_is_given_time_to_flush_its_record_before_the_kill(base):  # graceful end, then confirm
    p = _plan(n_cells=1)
    _, _, config = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"flush_on_eof": True}}))
    record = next((config.run_dir / "archive").rglob("projects/**/*.jsonl"))
    assert "flushed-on-exit" in record.read_text(encoding="utf-8")


def test_an_unconfirmed_kill_is_logged_once_and_retried_with_capped_backoff(base, monkeypatch, caplog):  # T-FI-unkillable
    from harness_bench import procs
    real_terminate, real_confirm = procs.Job.terminate, procs.CellProcess.terminate_and_confirm
    first: list[float] = []
    timeouts: list[float] = []

    def failing_terminate(self, exit_code=1):  # TerminateJobObject fails for the first 4.5 s (the procs seam)
        first.append(first[0] if first else time.monotonic())
        if time.monotonic() - first[0] > 4.5:
            real_terminate(self, exit_code)

    def spy(self, timeout, **kwargs):
        timeouts.append(timeout)
        return real_confirm(self, timeout, **kwargs)

    monkeypatch.setattr(procs.Job, "terminate", failing_terminate)
    monkeypatch.setattr(procs.CellProcess, "terminate_and_confirm", spy)
    p = _plan(n_cells=1)
    p["parameters"]["kill_escalation"] = 1
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"linger": 60}}), end_grace=1)
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["confirmed"] == 1
    assert [r for r in caplog.records if getattr(r, "error_code", None) == "HB-RUN-002"].__len__() == 1
    assert timeouts[:3] == [1, 1, 2]  # kill_escalation, then a backoff from 1 s
    assert timeouts[1:] == sorted(timeouts[1:]) and max(timeouts) <= engine.KILL_RETRY_CAP


def test_eof_mid_turn_is_an_adapter_crash(base):
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "eof_mid_turn"}}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "adapter_crash"


def test_out_of_memory_exit_is_a_memory_failure(base):  # T-FI-memory
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "no_memory"}}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["cause"], out["exit_status"]) == ("memory", 0xC0000017)


def test_spawn_failure_is_recorded_before_any_prompt(base):  # T-FI-spawn
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}, missing_exe=True))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["cause"], out["code"]) == ("spawn", "HB-CELL-114")
    assert not any(e["kind"] == "cell.prompt_sent" for e in events)


def test_workspace_failure_is_recorded(base):  # T-FI-workspace
    def broken(cell, cell_dir):
        raise OSError("disk says no")
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}), build_workspace=broken)
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "workspace"


def test_a_changed_build_fails_the_cell_and_stops_launching(base):  # T-CELL-build
    p = _plan(n_cells=2, parallelism=1)
    _, events, _ = _run(base, p, FakeLauncher({}, build_changed=True))
    outs = _outcomes(events)
    assert [o["cause"] for o in outs.values()] == ["build_changed"]
    assert any(e["kind"] == "run.launch_stopped" and e["code"] == "HB-CELL-115" for e in events)
    assert sum(1 for e in events if e["kind"] == "cell.launch_intent") == 1


def test_two_workers_asking_to_stop_give_one_launch_stopped(base):  # T1-7: one stop path, on the engine thread
    p = _plan(n_cells=3, parallelism=2)
    _, events, _ = _run(base, p, FakeLauncher({}, build_changed=True))
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-CELL-115"]


def test_the_circuit_breaker_stops_launching_once(base):  # T1-7: CIRCUIT_BREAKER consecutive infrastructure failures
    p = _plan(n_cells=4, parallelism=2)
    _, events, _ = _run(base, p, FakeLauncher({}, missing_exe=True))
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-CELL-114"]


def test_no_launch_after_a_stop_while_another_cell_still_runs(base):  # NoLaunchAfterStop, a slot freeing up
    p = _plan(n_cells=3, parallelism=2, budget=60)
    a, b, c = (cell["cell_id"] for cell in p["cells"])
    launcher = FakeLauncher({p["cells"][1]["label"]: {"sleep": 3}}, build_changed_for={a})
    _, events, _ = _run(base, p, launcher)
    launched = [e["cell_id"] for e in events if e["kind"] == "cell.launch_intent"]
    assert launched == [a, b] and c not in launched
    assert _outcomes(events)[b]["outcome"] == "completed"


def test_parallelism_is_never_exceeded(base):
    p = _plan(n_cells=3, parallelism=1)
    _, events, _ = _run(base, p, FakeLauncher({c["label"]: {"sleep": 1} for c in p["cells"]}))
    running = peak = 0
    for e in events:
        running += {"attempt.process_started": 1, "attempt.process_ended": -1}.get(e["kind"], 0)
        peak = max(peak, running)
    assert peak == 1 and len(_outcomes(events)) == 3


def test_credentials_are_gone_after_every_cell_even_when_the_workspace_is_kept(base, monkeypatch):  # T-CELL-credclean
    from harness_bench import archive
    monkeypatch.setattr(archive, "delete_after_verify", lambda *a, **k: False)  # the workspace cannot be deleted
    p = _plan(n_cells=2, budget=2)
    labels = [c["label"] for c in p["cells"]]
    _, events, config = _run(base, p, FakeLauncher({labels[0]: {"mode": "hang_prompt"}}))
    assert sum(1 for e in events if e["kind"] == "cell.workspace_kept") == 2
    assert list(config.cells_root.rglob("home")) and not list(config.cells_root.rglob(".credentials.json"))
    assert not list((config.run_dir / "archive").rglob(".credentials.json"))


def test_credentials_are_gone_after_a_spawn_failure(base):  # T-CELL-credclean, the spawn-failure variant
    p = _plan(n_cells=1)
    _, events, config = _run(base, p, FakeLauncher({}, missing_exe=True))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "spawn"
    assert not list(config.cells_root.rglob(".credentials.json"))


def test_a_failing_argv_env_leaves_no_credential_copy(base):  # T1-2: argv_env runs before seed
    class NoArgv(FakeLauncher):
        def argv_env(self, cell, home, traceparent):
            raise RuntimeError("profile cannot build argv")

    p = _plan(n_cells=1)
    _, events, config = _run(base, p, NoArgv({}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "unclassified"
    assert not list(config.cells_root.rglob(".credentials.json"))


def test_a_failure_after_spawn_ends_the_process_and_cleans_the_credentials(base, monkeypatch):  # T1-2
    from harness_bench import driver

    def boom(*args, **kwargs):
        raise RuntimeError("driver bug")

    monkeypatch.setattr(driver, "run_turn", boom)
    p = _plan(n_cells=1)
    _, events, config = _run(base, p, FakeLauncher({}))  # the replay: process_ended (confirmed) before the outcome
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert out["cause"] == "unclassified"
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["confirmed"] == 1 and ended["seq"] < out["seq"]
    started = next(e for e in events if e["kind"] == "attempt.process_started")
    assert not host.process_alive(started["pid"], started["created_at"])
    assert not list(config.cells_root.rglob(".credentials.json"))


def test_a_ledger_failure_after_spawn_still_cleans_the_credentials(base, monkeypatch):  # T1-2
    p = _plan(n_cells=1)
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "cell.prompt_sent":
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None, end_grace=3)
    assert _engine_run(p, config).exit_code == 3
    started = next(e for e in ledger.read_segment(next((config.run_dir / "events").glob("*.jsonl")))
                   if e["kind"] == "attempt.process_started")
    assert not host.process_alive(started["pid"], started["created_at"])
    assert not list(config.cells_root.rglob(".credentials.json"))


def test_an_archive_failure_is_recorded_and_the_run_is_incomplete(base, monkeypatch):  # T1-3
    from harness_bench import archive

    def boom(*args, **kwargs):
        raise OSError("archive volume unavailable")

    monkeypatch.setattr(archive, "archive_cell", boom)
    p = _plan(n_cells=1)
    cid = p["cells"][0]["cell_id"]
    summary, events, config = _run(base, p, FakeLauncher({}))
    assert [(e["cell_id"], e["code"]) for e in events if e["kind"] == "cell.archive_failed"] == [(cid, "HB-CELL-199")]
    assert _outcomes(events)[cid]["outcome"] == "completed"  # the outcome stands; its archive is what failed
    assert summary.exit_code == 3 and not any(e["kind"] == "run.completed" for e in events)
    assert (config.cells_root / p["run_id"] / cid / "ws").is_dir()  # the only copy of the work is kept


def test_a_full_disk_while_building_the_workspace_is_a_disk_failure(base):  # T1-12: ENOSPC -> Cause.disk
    def full(cell, cell_dir):
        raise OSError(errno.ENOSPC, "No space left on device")

    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}), build_workspace=full)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["cause"], out["code"]) == ("disk", "HB-CELL-112")


def test_the_disk_floor_also_checks_the_run_dirs_volume(base, monkeypatch):  # T1-12
    real = shutil.disk_usage
    monkeypatch.setattr(shutil, "disk_usage", lambda path: real(path)._replace(free=0) if "runs" in str(path) else real(path))
    p = _plan(n_cells=1)
    summary, events, _ = _run(base, p, FakeLauncher({}))
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-RUN-004"]
    assert summary.exit_code == 3


def test_the_outcome_is_recorded_before_the_best_effort_files(base):  # T1-12: the stderr tail cannot cost the outcome
    p = _plan(n_cells=1)
    blocked = {"stderr": "adapter noise\n", "mkdir": "../adapter-stderr-tail.log"}  # a folder where the tail file goes
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: blocked}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
    assert any(e["kind"] == "cell.archived" for e in events)


def test_disk_floor_stops_launching_before_any_cell(base):
    p = _plan(n_cells=2)
    p["parameters"]["disk_floor_bytes"] = 1 << 60
    summary, events, _ = _run(base, p, FakeLauncher({}))
    assert any(e["kind"] == "run.launch_stopped" and e["code"] == "HB-RUN-004" for e in events)
    assert not any(e["kind"] == "cell.launch_intent" for e in events)
    assert summary.exit_code == 3  # run incomplete


def test_an_append_failure_means_the_prompt_is_never_sent(base, monkeypatch):  # T-ENG-ack
    p = _plan(n_cells=1)
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "cell.prompt_sent":
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None, end_grace=3)
    summary = _engine_run(p, config)
    assert summary.exit_code == 3
    assert not list((base / "cells").rglob(".fake-prompt.txt")) and not list((config.run_dir / "archive").rglob(".fake-prompt.txt"))


def test_after_the_ledger_breaks_no_worker_blocks_forever(base, monkeypatch):  # T1-4
    p = _plan(n_cells=2, parallelism=2)
    first, second = p["cells"]
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "cell.prompt_sent" and record.get("cell_id") == first["cell_id"]:
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({second["label"]: {"sleep": 2}})},
                                 build_workspace=_build_workspace, grade=None, end_grace=3)
    assert _engine_run(p, config, limit=30).exit_code == 3
    alive = [t.name for t in threading.enumerate() if t.name.startswith("cell-")]
    assert alive == [], f"workers still blocked after the run returned: {alive}"


def test_record_rejects_a_non_canonical_value_on_the_worker_side(base):  # T1-5
    config = engine.EngineConfig(run_dir=base / "runs" / "r", cells_root=base / "cells", launchers={},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(_plan(n_cells=1), config)
    box = {}

    def call():
        try:
            eng.record("events", {"kind": "cell.outcome", "cell_id": "x", "ratio": 0.5})
        except TypeError as exc:
            box["error"] = exc

    t = threading.Thread(target=call, daemon=True)
    t.start()
    t.join(5)
    assert not t.is_alive() and isinstance(box.get("error"), TypeError)
    assert eng.inbox.empty() and not eng.broken


def test_a_bad_record_fails_its_cell_not_the_run(base):  # T1-5: only a write or fsync OSError breaks the run
    class FloatVersion(FakeLauncher):
        def check_build(self):
            return {**super().check_build(), "version": 1.5}  # not in the canonical form

    p = _plan(n_cells=1)
    summary, events, _ = _run(base, p, FloatVersion({}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "unclassified"
    assert events[-1]["kind"] == "run.completed" and summary.exit_code == 0


def _engine_log(run_dir: Path, emit) -> list[dict]:
    """Lines engine.log gets while `emit` runs; the handler is removed afterwards."""
    before = list(engine.log.handlers)
    engine.configure_logging(run_dir, "a" * 32)
    try:
        emit()
    finally:
        for h in [h for h in engine.log.handlers if h not in before]:
            engine.log.removeHandler(h)
            h.close()
    return [json.loads(line) for line in (run_dir / "engine.log").read_text(encoding="utf-8").splitlines()]


def test_engine_log_keeps_the_whitelisted_extras_only(base):  # T1-9
    extra = {"error_code": "HB-RUN-002", "pids": [4, 8], "detail": "why", "fact": "events", "win32_error": 5, "argv": ["x"]}
    [line] = _engine_log(base, lambda: engine.log.error("kill unconfirmed", extra=extra))
    assert {k: line.get(k) for k in ("error_code", "pids", "detail", "fact", "win32_error")} == {
        "error_code": "HB-RUN-002", "pids": [4, 8], "detail": "why", "fact": "events", "win32_error": 5}
    assert "argv" not in line  # not whitelisted: argv may carry a credential


def test_an_echoed_credential_reaches_the_archive_but_never_engine_log_or_status(base):  # T-LOG-nosecret (T1-14)
    from harness_bench import status
    p = _plan(n_cells=1)
    p["profiles"] = {"fake": {"profile_hash": "", "usage_source": "acp_turn", "auxiliary_models": [],
                              "record_glob": "projects/**/*.jsonl"}}  # what `bench status` reads from a confirmed plan
    p["plan_hash"] = plan.plan_hash(p)
    run_dir = base / "runs" / p["run_id"]
    plan.confirm(run_dir, p)
    echo = {"echo_credential": True, "mkdir": "../adapter-stderr-tail.log"}  # the blocked tail file logs a warning
    lines = _engine_log(run_dir, lambda: _run(base, p, FakeLauncher({p["cells"][0]["label"]: echo})))
    assert lines, "engine.log got no line; the probe proves nothing"
    assert SECRET not in json.dumps(lines)
    s = status.build(run_dir)
    assert SECRET not in status.to_json(s) and SECRET not in status.text(s)
    archived = [f.read_bytes() for f in (run_dir / "archive").rglob("*") if f.is_file()]
    assert any(SECRET.encode() in b for b in archived)  # allowed there: the archive is the cell's record


def test_a_host_sleep_mid_turn_kills_the_cell_as_host_suspended(base, monkeypatch):  # T-ENG-suspend (T1-15)
    real = host.unbiased_seconds
    cells = base / "cells"
    slept = []

    def clock():  # the injected clock: once the prompt is on disk, suspended time stops counting (a 120 s sleep)
        if not slept and any(cells.rglob(".fake-prompt.txt")):
            slept.append(True)
        return real() - (120 if slept else 0)

    monkeypatch.setattr(host, "unbiased_seconds", clock)
    p = _plan(n_cells=1, budget=60)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "hang_prompt"}}), limit=45)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["cause"], out["code"]) == ("failed", "host_suspended", "HB-CELL-106")
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["confirmed"] == 1 and ended["seq"] < out["seq"]


def test_a_build_server_left_by_the_turn_is_gone_when_the_end_is_recorded(base, monkeypatch):  # T-JOB-daemon (T1-15)
    sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # another build, in no cell's job
    seen = {}
    real = engine.Engine.record

    def spy(self, fact, record):
        if record.get("kind") == "attempt.process_ended":  # the daemon must already be gone: the job reports 0 processes
            daemon = next(self.cfg.cells_root.rglob("daemon.pid")).read_text(encoding="utf-8").split()
            seen["daemon_alive"] = host.process_alive(int(daemon[0]), int(daemon[1]))
        return real(self, fact, record)

    monkeypatch.setattr(engine.Engine, "record", spy)
    try:
        p = _plan(n_cells=1)
        _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"daemon": True}}))
        assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
        assert seen == {"daemon_alive": False}
        assert next(e for e in events if e["kind"] == "attempt.process_ended")["confirmed"] == 1
        assert sibling.poll() is None, "a process outside the cell's job was killed"
    finally:
        sibling.kill()
        sibling.wait(timeout=30)


def test_a_full_disk_during_the_archive_records_archive_failed_as_disk(base, monkeypatch):  # T-ARC-full (T1-15)
    from harness_bench import archive

    def full(src, dst, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(archive.shutil, "copyfile", full)
    p = _plan(n_cells=1)
    cid = p["cells"][0]["cell_id"]
    summary, events, config = _run(base, p, FakeLauncher({}))
    assert [(e["cell_id"], e["code"]) for e in events if e["kind"] == "cell.archive_failed"] == [(cid, "HB-CELL-112")]
    assert not any(e["kind"] in ("cell.archived", "cell.workspace_deleted") for e in events)
    assert (config.cells_root / p["run_id"] / cid / "ws" / "slug.py").is_file()  # the work is kept
    assert summary.exit_code == 3


def test_a_started_run_is_refused(base):
    p = _plan(n_cells=1)
    _run(base, p, FakeLauncher({}))
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    with pytest.raises(BenchError) as e:
        engine.Engine(p, config).run()
    assert e.value.code == "HB-USR-002"


def test_a_second_engine_on_a_held_run_is_refused_with_run_lock_held(base):  # T1-13: HB-RUN-005, not teardown's code
    from harness_bench import oslock
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    with oslock.RunLock.acquire(config.run_dir / ".lock", "HB-RUN-005"), pytest.raises(BenchError) as e:
        engine.Engine(p, config).run()
    assert e.value.code == "HB-RUN-005"


CRASHER = """
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, {tests!r}); sys.path.insert(0, {src!r})
import test_engine as t
from harness_bench import engine
p = t._plan(n_cells=2)
p["run_id"] = {run_id!r}
launcher = t.FakeLauncher({{c["label"]: {{"mode": "hang_prompt"}} for c in p["cells"]}})
config = engine.EngineConfig(run_dir=Path({run_dir!r}), cells_root=Path({cells!r}), launchers={{"fake": launcher}},
                             build_workspace=t._build_workspace, grade=None)
engine.Engine(p, config).run()
"""


def test_engine_crash_leaves_no_cell_running(base):  # T-ENG-crash-no-orphan
    run_id = "crash-" + uuid.uuid4().hex[:4]
    script = base / "crasher.py"
    script.write_text(CRASHER.format(tests=str(Path(__file__).parent), src=str(ROOT / "src"), run_id=run_id,
                                     run_dir=str(base / "runs" / run_id), cells=str(base / "cells")), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    deadline = time.monotonic() + 60
    pids = []
    while time.monotonic() < deadline and len(pids) < 2:
        time.sleep(0.5)
        events = _events(base / "runs" / run_id) if (base / "runs" / run_id / "events").exists() else []
        pids = [(e["pid"], e["created_at"]) for e in events if e["kind"] == "attempt.process_started"]
    assert len(pids) == 2, "cells never started"
    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    proc.wait(timeout=30)
    time.sleep(2)
    for pid, created in pids:
        assert not host.process_alive(pid, created), f"cell process {pid} survived the engine"
