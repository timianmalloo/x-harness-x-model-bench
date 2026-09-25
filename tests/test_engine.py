"""The run engine (ADR-0007, ADR-0013; design: Error & concurrency model) against the fake ACP agent.

Each test runs the real engine: real ledger, real Job Objects, real archive; only the harness is the
fake agent and the working-copy builder is a stub (the real one is covered in test_workspace.py).
Every run's events are replayed against the model's phase-1 guards (lifecycle.replay, US-44 AC3).
"""

import ctypes
import errno
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import Future
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
    credential_kind = "subscription login (copied)"
    usage_source = "acp_turn"
    mode = None
    set_model = False
    shutdown_grace = 1.0

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
    launcher.shutdown_grace = cfg.pop("shutdown_grace", launcher.shutdown_grace)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": launcher}, build_workspace=cfg.pop("build_workspace", _build_workspace),
                                 grade=cfg.pop("grade", None), **cfg)
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
    assert '"archive_file"' not in Path(engine.__file__).read_text(encoding="utf-8")  # always overwritten by the row's kind
    _, _, config = _run(base, _plan(n_cells=1), FakeLauncher({}))
    rows = ledger.read_segment(next((config.run_dir / "archive_files").glob("*.jsonl")))
    assert rows and {r["kind"] for r in rows} <= {"file", "link"}  # the archive row's own kind, as before


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
    assert {e["attempt"] for e in events if e["kind"] == "attempt.process_started"} == {1}
    opened = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
    assert opened == {cid: o["session_id"] for cid, o in outs.items()} and all(opened.values())
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


def test_context_window_tag_is_recorded_on_process_ended_from_a_tagged_served_model(base):  # R-32
    tc = {"inputTokens": 1, "cachedInputTokens": 0, "cachedWriteTokens": 0, "outputTokens": 1, "reasoningOutputTokens": 0}
    usage = [{"model": "claude-haiku-4-5-20251001", "token_count": tc}, {"model": "claude-opus-5-5[1m]", "token_count": tc}]
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"usage": usage}}))
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["context_window_tag"] == "1m"


def test_context_window_tag_is_null_when_no_served_model_carries_one(base):  # R-32 negative control
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))  # the default USAGE names "fake-model", no bracket
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["context_window_tag"] is None


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
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"linger": 8}}), shutdown_grace=6)
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


@pytest.mark.parametrize("reason", ["timeout", "host_suspended", "stop"])
def test_engine_kill_deadline_uses_one_injected_clock(base, reason):  # R21-5, PE-8
    from types import SimpleNamespace

    now = [100.0]
    calls = []
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={"fake": FakeLauncher({})},
                                 build_workspace=_build_workspace, grade=None, clock=lambda: now[0])
    eng = engine.Engine(_plan(n_cells=1), config)
    a = engine._Active(eng.plan["cells"][0], threading.current_thread())
    a.proc = SimpleNamespace(job=SimpleNamespace(active=lambda: 0 if calls else 1,
                                                  terminate=lambda: calls.append(now[0])))
    eng.active[a.cell["cell_id"]] = a
    eng._kill(a, reason)
    assert a.kill_deadline == 101.0 and a.cancel.is_set()
    now[0] = 100.9
    eng._check_kills(now[0])
    assert not a.terminated and calls == []
    now[0] = 101.0
    eng._check_kills(now[0])
    assert a.terminated and calls == [101.0]
    eng._check_kills(now[0])
    assert calls == [101.0]


def test_hard_kill_retries_until_the_job_is_empty(base):  # R21-5, an unsuccessful first termination
    from types import SimpleNamespace

    now = [100.0]
    attempts = []
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={"fake": FakeLauncher({})},
                                 build_workspace=_build_workspace, grade=None, clock=lambda: now[0])
    eng = engine.Engine(_plan(n_cells=1), config)
    a = engine._Active(eng.plan["cells"][0], threading.current_thread())
    a.proc = SimpleNamespace(job=SimpleNamespace(active=lambda: 0 if len(attempts) >= 2 else 1,
                                                  terminate=lambda: attempts.append(now[0])))
    eng.active[a.cell["cell_id"]] = a
    eng._kill(a, "timeout")
    now[0] = 101.0
    eng._check_kills(now[0])
    now[0] = 101.2
    eng._check_kills(now[0])
    assert a.terminated and attempts == [101.0, 101.2]


def test_a_budget_kill_lets_the_agent_write_its_shutdown_record(base):  # R21-1
    p = _plan(n_cells=1, budget=1)
    label = p["cells"][0]["label"]
    _, events, config = _run(base, p, FakeLauncher({label: {"mode": "on_cancel", "shutdown_file": "shutdown.txt"}}))
    assert next((config.run_dir / "archive").rglob("shutdown.txt")).read_text(encoding="utf-8") == "shutdown\n"
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "timed_out"


def test_a_cancelled_turn_is_classified_by_its_kill_reason(base):  # R21-4, budget branch
    p = _plan(n_cells=1, budget=1)
    label = p["cells"][0]["label"]
    _, events, _ = _run(base, p, FakeLauncher({label: {"mode": "on_cancel"}}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert (out["outcome"], out["cause"], out["stop_reason"]) == ("timed_out", "timed_out", "cancelled")
    assert ended["ended_by"] == "grace"


def test_a_cancelled_turn_requested_by_stop_stays_stopped(base):  # R21-4, stop branch before slice-4 controls
    p = _plan(n_cells=1, budget=60)
    label = p["cells"][0]["label"]
    launcher = FakeLauncher({label: {"mode": "on_cancel"}})
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": launcher}, build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    real_tick = eng.on_tick

    def stop_tick():
        real_tick()
        for a in eng.active.values():
            if a.prompt_mono is not None and a.kill_reason is None:
                eng._kill(a, "stop")

    eng.on_tick = stop_tick
    box = {}
    run = threading.Thread(target=lambda: box.setdefault("summary", eng.run()), daemon=True)
    run.start()
    run.join(20)
    assert not run.is_alive()
    events = _events(config.run_dir)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["cause"], out["stop_reason"]) == ("stopped", None, "cancelled")
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["ended_by"] == "grace"


def test_ended_by_records_who_ended_the_job(base):  # R21-6
    p = _plan(n_cells=1, budget=1)
    label = p["cells"][0]["label"]
    _, events, _ = _run(base, p, FakeLauncher({label: {"mode": "stubborn"}}))
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["ended_by"] == "terminate"


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
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"linger": 60}}), shutdown_grace=1)
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["confirmed"] == 1
    assert [r for r in caplog.records if getattr(r, "error_code", None) == "HB-RUN-002"].__len__() == 1
    assert timeouts[:3] == [1, 1, 2]  # kill_escalation, then a backoff from 1 s
    assert timeouts[1:] == sorted(timeouts[1:]) and max(timeouts) <= engine.KILL_RETRY_CAP


def test_a_failing_job_query_is_an_unconfirmed_kill_not_a_crash(base, monkeypatch, caplog):  # T1-8b (T3-5 seam notice)
    from harness_bench import procs
    real_confirm = procs.CellProcess.terminate_and_confirm
    calls = []

    def failing(self, timeout, **kwargs):  # T3-5: a failed or closed-handle job query raises OSError
        calls.append(timeout)
        if len(calls) <= 2:
            raise OSError(6, "The handle is invalid")
        return real_confirm(self, timeout, **kwargs)

    monkeypatch.setattr(procs.CellProcess, "terminate_and_confirm", failing)
    p = _plan(n_cells=1)
    p["parameters"]["kill_escalation"] = 1
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"linger": 60}}), shutdown_grace=1)
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["confirmed"] == 1
    assert len([r for r in caplog.records if getattr(r, "error_code", None) == "HB-RUN-002"]) == 1
    assert calls[:3] == [1, 1, 2]  # kill_escalation, then the capped backoff: the slot stayed held


def test_job_queries_failing_through_the_procs_seam_hold_the_slot_until_confirmed(base, monkeypatch, caplog):  # T1-8b
    from harness_bench import procs
    real_query = procs._query
    first: list[float] = []

    def failing(job, info_class, buf):  # T3-5's fault seam: QueryInformationJobObject fails for 2.5 s
        first.append(first[0] if first else time.monotonic())
        return False if time.monotonic() - first[0] < 2.5 else real_query(job, info_class, buf)

    monkeypatch.setattr(procs, "_query", failing)
    p = _plan(n_cells=1)
    p["parameters"]["kill_escalation"] = 1
    _, events, _ = _run(base, p, FakeLauncher({}), shutdown_grace=1)
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["confirmed"] == 1
    assert len([r for r in caplog.records if getattr(r, "error_code", None) == "HB-RUN-002"]) == 1


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


def test_the_circuit_breaker_fires_at_its_threshold_not_before(base):  # CIRCUIT_BREAKER = 3 (a cosmic-ray survivor)
    p = _plan(n_cells=5, parallelism=1)
    summary, events, _ = _run(base, p, FakeLauncher({}, missing_exe=True))
    assert sum(1 for e in events if e["kind"] == "cell.launch_intent") == 3
    stop = next(i for i, e in enumerate(events) if e["kind"] == "run.launch_stopped")
    assert (events[stop]["code"], events[stop]["reason"]) == (
        "HB-CELL-114", "circuit breaker: 3 consecutive infrastructure failures")
    assert not any(e["kind"] == "cell.launch_intent" for e in events[stop + 1:])
    assert len(_outcomes(events)) == 3
    assert events[-1]["kind"] == "run.completed"
    assert summary.exit_code == 3


def test_harness_failures_do_not_trip_the_breaker(base):
    p = _plan(n_cells=4, parallelism=1)
    labels = {c["label"]: {"mode": "eof_mid_turn"} for c in p["cells"]}
    _, events, _ = _run(base, p, FakeLauncher(labels))
    assert [e["cause"] for e in events if e["kind"] == "cell.outcome"] == ["adapter_crash"] * 4
    assert sum(e["kind"] == "cell.launch_intent" for e in events) == 4
    assert not any(e["kind"] == "run.launch_stopped" for e in events)


@pytest.mark.parametrize("outcome,cause", [
    ("stopped", None),
    ("skipped (decision)", None),
    ("failed (model unavailable)", "model_unavailable"),
])
def test_neutral_outcomes_neither_count_nor_reset(base, monkeypatch, outcome, cause):
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    stops = []
    monkeypatch.setattr(eng, "_stop_launching", lambda code, reason: stops.append((code, reason)))
    for i in range(2):
        eng._after_append({"kind": "cell.outcome", "cell_id": f"fail-{i}", "cause": "spawn", "outcome": "failed"})
    assert eng.infra_streak == 2
    eng._after_append({"kind": "cell.outcome", "cell_id": "neutral", "cause": cause, "outcome": outcome})
    assert eng.infra_streak == 2
    assert stops == []
    eng._after_append({"kind": "cell.outcome", "cell_id": "third", "cause": "spawn", "outcome": "failed"})
    assert stops == [("HB-CELL-114", "circuit breaker: 3 consecutive infrastructure failures")]


def test_model_unavailable_alone_does_not_count_toward_the_breaker(base, monkeypatch):
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    stops = []
    monkeypatch.setattr(eng, "_stop_launching", lambda code, reason: stops.append((code, reason)))
    for i in range(3):
        eng._after_append({"kind": "cell.outcome", "cell_id": f"unavailable-{i}",
                           "cause": "model_unavailable", "outcome": "failed (model unavailable)"})
    assert eng.infra_streak == 0
    assert stops == []


def test_the_breaker_leaves_running_cells_running(base):
    p = _plan(n_cells=5, parallelism=2)
    slow, *fast = p["cells"]
    launcher = FakeLauncher({slow["label"]: {"sleep": 3},
                             **{c["label"]: {"mode": "provider_error"} for c in fast}})
    summary, events, _ = _run(base, p, launcher)
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-CELL-108"]
    assert _outcomes(events)[slow["cell_id"]]["outcome"] == "completed"
    assert sum(e["kind"] == "cell.launch_intent" for e in events) == 4
    assert summary.exit_code == 3


def test_a_drain_with_nothing_queued_returns_at_its_deadline(base):  # the loop never stalls on an empty inbox
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={}, build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(_plan(n_cells=1), config)
    started = time.monotonic()
    eng._drain(0)
    eng._drain(0.2)
    assert time.monotonic() - started < 0.6


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
            raise RuntimeError("profile cannot build argv " + "x" * 1000)

    p = _plan(n_cells=1)
    _, events, config = _run(base, p, NoArgv({}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert out["cause"] == "unclassified" and len(out["detail"]) == 300  # the detail is capped, not dropped
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
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
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
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    summary = _engine_run(p, config)
    assert summary.exit_code == 3
    assert not list((base / "cells").rglob(".fake-prompt.txt")) and not list((config.run_dir / "archive").rglob(".fake-prompt.txt"))


def test_after_the_ledger_breaks_no_worker_blocks_forever(base, monkeypatch):  # T1-4
    p = _plan(n_cells=2, parallelism=2)
    first, second = p["cells"]
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "attempt.process_ended" and record.get("cell_id") == first["cell_id"]:  # second is mid-turn
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({first["label"]: {"sleep": 2}, second["label"]: {"mode": "hang_prompt"}})},
                                 build_workspace=_build_workspace, grade=None)
    assert _engine_run(p, config, limit=30).exit_code == 3
    alive = [t.name for t in threading.enumerate() if t.name.startswith("cell-")]
    assert alive == [], f"workers still alive after the run returned: {alive}"  # the hung turn was killed, not left running


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


def test_configure_logging_replaces_the_previous_handler(base):  # T9-2: cross-run contamination + Windows delete leak
    run_a, run_b = base / "a", base / "b"
    run_a.mkdir()
    run_b.mkdir()
    before = list(engine.log.handlers)
    try:
        handler_a = engine.configure_logging(run_a, "a" * 32)
        handler_b = engine.configure_logging(run_b, "b" * 32)
        assert handler_a not in engine.log.handlers and handler_b in engine.log.handlers  # replaced, not accumulated
        engine.log.info("after B")
        assert "after B" not in (run_a / "engine.log").read_text(encoding="utf-8")
        assert "after B" in (run_b / "engine.log").read_text(encoding="utf-8")
    finally:
        for h in [h for h in engine.log.handlers if h not in before]:
            engine.log.removeHandler(h)
            h.close()
    (run_a / "engine.log").unlink()  # only succeeds once handler_a was closed by configure_logging(B)
    assert not (run_a / "engine.log").exists()


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


def test_a_build_server_left_by_the_turn_is_gone_before_the_job_is_closed(base, monkeypatch):  # T-JOB-daemon (T1-15)
    from harness_bench import procs
    sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # another build, in no cell's job
    seen = []
    real_close = procs.CellProcess.close

    def spy(self):  # kill-on-close would hide a live daemon: the job must already be empty (terminated, confirmed)
        if self.job.handle:
            seen.append(sorted(self.job.pids()))
        real_close(self)

    monkeypatch.setattr(procs.CellProcess, "close", spy)
    try:
        p = _plan(n_cells=1)
        _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"daemon": True}}))
        assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
        assert seen == [[]]
        assert list((base / "runs" / p["run_id"] / "archive").rglob("daemon.pid")), "the turn started no daemon"
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


# --- tests that kill cosmic-ray survivors (docs/notes/mutation-record-t1.md) ------------------------------------------

def _bare_engine(base):
    """An engine that is not running: its inbox, drain and record are driven by the test."""
    config = engine.EngineConfig(run_dir=base / "runs" / "r", cells_root=base / "cells", launchers={},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(_plan(n_cells=1), config)
    eng.writers["events"] = ledger.SegmentWriter.create(base / "runs" / "r" / "events", "engine-1")
    return eng


def test_record_waits_through_a_full_inbox_and_a_slow_drain(base):  # backpressure: never drops, never gives up early
    eng = _bare_engine(base)
    try:
        for _ in range(eng.inbox.maxsize):
            eng.inbox.put(("events", {"kind": "run.started"}, Future()))
        box = {}
        t = threading.Thread(target=lambda: box.update(row=eng.record("events", {"kind": "run.started"})), daemon=True)
        t.start()
        time.sleep(1.2)  # the inbox stays full for more than two RECORD_POLL periods
        for _ in range(eng.inbox.maxsize):  # make room without draining: the worker's item goes in, unanswered
            eng.inbox.get()
        time.sleep(1.2)  # the worker now waits on its future for more than two periods
        assert t.is_alive()
        eng._drain(0.5)
        t.join(5)
        assert not t.is_alive() and box["row"]["seq"] == 1
    finally:
        eng.closed = True
        eng.writers["events"].close()


def test_a_drain_appends_what_arrives_before_its_deadline(base):
    eng = _bare_engine(base)
    try:
        future = Future()
        threading.Timer(0.2, lambda: eng.inbox.put(("events", {"kind": "run.started"}, future))).start()
        eng._drain(1.0)
        assert future.done() and future.result()["seq"] == 1
    finally:
        eng.writers["events"].close()


def test_once_the_engine_has_ended_a_queued_record_fails_unwritten(base):
    eng = _bare_engine(base)
    try:
        future = Future()
        eng.inbox.put(("events", {"kind": "run.started"}, future))
        eng.closed = True
        eng._drain(0)
        assert isinstance(future.exception(), BenchError) and future.exception().code == "HB-RUN-001"
        assert ledger.read_segment(base / "runs" / "r" / "events" / "engine-1.jsonl") == []
    finally:
        eng.writers["events"].close()


def test_an_archive_refused_with_a_bench_error_is_recorded_under_its_code(base, monkeypatch):  # not mistaken for HB-RUN-001
    from harness_bench import archive

    def exists(*args, **kwargs):
        raise BenchError("HB-USR-002", "an archive attempt is written once")

    monkeypatch.setattr(archive, "archive_cell", exists)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    assert [e["code"] for e in events if e["kind"] == "cell.archive_failed"] == ["HB-USR-002"]


def test_a_success_resets_the_infrastructure_streak(base):  # CIRCUIT_BREAKER counts consecutive failures only
    p = _plan(n_cells=6, parallelism=1)
    modes = ["provider_error", "ok", "provider_error", "provider_error", "provider_error", "ok"]
    _, events, _ = _run(base, p, FakeLauncher({c["label"]: {"mode": m} for c, m in zip(p["cells"], modes, strict=True)}))
    assert sum(1 for e in events if e["kind"] == "cell.launch_intent") == 5  # stopped after cells 3, 4, 5 failed


def test_the_budget_runs_from_the_prompt_not_from_the_working_copy(base):  # a slow handshake is not the agent's time
    p = _plan(n_cells=1, budget=2)
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"handshake_delay": 3}}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"


def test_a_failed_append_of_the_stop_ends_the_run_incomplete_not_raised(base, monkeypatch):
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "run.launch_stopped":
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    p = _plan(n_cells=1)
    p["parameters"]["disk_floor_bytes"] = 1 << 60
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    assert _engine_run(p, config).exit_code == 3


def test_a_stdin_that_fails_to_close_still_ends_the_turn(base, monkeypatch):
    from harness_bench import driver
    real = driver.run_turn

    class BrokenPipe:
        def close(self):
            raise OSError(32, "The pipe is being closed")

    def then_break_stdin(cell, *args, **kwargs):
        result = real(cell, *args, **kwargs)
        cell.proc.stdin.close()
        cell.proc.stdin = BrokenPipe()
        return result

    monkeypatch.setattr(driver, "run_turn", then_break_stdin)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"


def test_a_process_whose_status_never_arrives_is_recorded_as_minus_one(base, monkeypatch):
    from harness_bench import procs

    def no_status(self, timeout=None):
        raise subprocess.TimeoutExpired("fake", timeout)

    monkeypatch.setattr(procs.CellProcess, "wait", no_status)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["exit_status"] == -1
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["exit_status"] == -1


def test_the_heartbeat_keeps_beating_after_a_failed_beat():
    class Lock:
        calls = 0

        def heartbeat(self):
            Lock.calls += 1
            if Lock.calls == 1:
                raise OSError(5, "Access is denied")

    with engine._beating(Lock(), 0.05):
        time.sleep(0.4)
    assert Lock.calls >= 3


# --- _classify, the cause precedence table (T10: cosmic-ray survivors, docs/notes/mutation-record-t1.md) ---------------

class _NativeRecords:
    """A launcher stub for `_classify`: each native record found for the session carries these provider errors."""

    def __init__(self, *errors_per_record):
        self.errors_per_record = errors_per_record
        self.asked: list[str] = []

    def records(self, home: Path, session_id: str) -> list[Path]:
        self.asked.append(session_id)
        return [home / f"{i}.jsonl" for i in range(len(self.errors_per_record))]

    def read(self, path: Path):
        from types import SimpleNamespace
        return SimpleNamespace(errors=list(self.errors_per_record[int(path.stem)]))


def _provider_error(status, error_type="overloaded_error"):
    from harness_bench.telemetry import ProviderError
    return ProviderError(native_ordinal=1, status=status, error_type=error_type, message="")


def _classify(base, launcher=None, kill_reason=None, exit_status=0, tail=b"", **result):
    from harness_bench import driver
    turn = driver.TurnResult(**{"session_id": "s-1", "stop_reason": "end_turn", **result})
    config = engine.EngineConfig(run_dir=base / "runs" / "r", cells_root=base / "cells", launchers={},
                                 build_workspace=_build_workspace, grade=None)
    return engine.Engine(_plan(n_cells=1), config)._classify(turn, launcher or _NativeRecords(), base, exit_status, tail, kill_reason)


NO_MEMORY = 0xC0000017  # STATUS_NO_MEMORY
OOM_TAIL = b"<--- Last few GCs --->\nFATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory\n"


@pytest.mark.parametrize(("case", "expected"), [
    # each row differs from the next rule down in exactly the input that rule reads
    ({"launcher": _NativeRecords([_provider_error(529)]), "kill_reason": "timeout", "exit_status": NO_MEMORY}, "provider"),
    ({"launcher": _NativeRecords([_provider_error(400, "invalid_request_error")]), "kill_reason": "timeout"}, "model_unavailable"),
    ({"kill_reason": "timeout", "exit_status": NO_MEMORY, "cause": "protocol"}, "timed_out"),
    ({"kill_reason": "host_suspended", "exit_status": NO_MEMORY, "tail": OOM_TAIL}, "host_suspended"),  # host_suspended > memory
    ({"kill_reason": "host_suspended", "cause": "protocol"}, "host_suspended"),
    ({"exit_status": NO_MEMORY, "cause": "protocol"}, "memory"),
    ({"exit_status": 0xC000012D, "cause": "protocol"}, "memory"),  # STATUS_COMMITMENT_LIMIT
    ({"tail": OOM_TAIL, "cause": "protocol"}, "memory"),  # the OOM stderr signature, with a clean exit status
    ({"tail": b"System.OutOfMemoryException", "stop_reason": None}, "memory"),
    ({"tail": b"fatal: OUT OF MEMORY", "stop_reason": None}, "memory"),  # case-insensitive
    ({"exit_status": None, "tail": b"out of memory"}, "memory"),  # an exit status that never arrived
    ({"kill_reason": "aborted", "cause": "protocol"}, "protocol"),  # a kill with no rule of its own falls through
    ({"cause": "protocol", "stop_reason": "end_turn"}, "protocol"),  # the driver's cause outranks a completed stop reason
    ({"cause": "blocked_auth", "stop_reason": None}, "blocked_auth"),
    ({"stop_reason": "cancelled"}, "adapter_crash"),  # the adapter_crash fallback: a stop reason that is not completion
    ({"stop_reason": None}, "adapter_crash"),
    ({"stop_reason": "end_turn"}, None),
    ({"stop_reason": "max_tokens"}, None),
    ({"stop_reason": "max_turn_requests"}, None),
    ({"stop_reason": "refusal"}, None),
    ({"exit_status": 1, "tail": b"memory usage: 12 MB\n"}, None),  # neither a no-memory status nor the signature
    ({"kill_reason": "timeout-ish"}, None),  # only the exact kill reasons count
    ({"kill_reason": "TIMEOUT".lower()}, "timed_out"),  # a new str object: compared by value, not by identity
    ({"kill_reason": "HOST_SUSPENDED".lower()}, "host_suspended"),
])
def test_classify_applies_the_cause_precedence_in_order(base, case, expected):
    from harness_bench.errors import Cause
    case = dict(case)
    if "cause" in case:
        case["cause"] = Cause[case["cause"]]
    cause = _classify(base, **case)
    assert (cause.name if cause else None) == expected


def test_classify_reads_every_native_record_of_the_session(base):
    launcher = _NativeRecords([], [_provider_error(429, "rate_limit_error")])  # the error is in the second record only
    assert _classify(base, launcher, session_id="s-7").name == "provider"
    assert launcher.asked == ["s-7"]
    missing = _NativeRecords()
    assert _classify(base, missing, session_id=None, stop_reason="end_turn") is None
    assert missing.asked == [""]  # a session that never opened is looked up as "", never as None


# --- run, _run_cell, _keep_tail (T10: cosmic-ray survivors) ------------------------------------------------------------

def test_the_inbox_is_the_designs_bounded_queue(base):  # design: Error & concurrency model, queue.Queue(maxsize=64)
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={}, build_workspace=_build_workspace, grade=None)
    assert engine.Engine(_plan(n_cells=1), config).inbox.maxsize == 64


def test_the_host_is_kept_awake_for_the_run_and_released_at_its_end(base, monkeypatch):
    calls = []
    monkeypatch.setattr(host, "keep_awake", calls.append)
    p = _plan(n_cells=1)
    _run(base, p, FakeLauncher({}))
    assert calls == [True, False]


def test_keep_awake_is_held_through_a_stop(base, monkeypatch):
    p = _plan(n_cells=2, parallelism=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({p["cells"][0]["label"]: {"sleep": 1}})},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    calls = []
    monkeypatch.setattr(host, "keep_awake", lambda flag: calls.append((flag, len(eng.active), eng.stopped)))

    def stop_when_running(_now):
        if eng.active and eng.stopped is None:
            eng._stop_launching("HB-RUN-006", "operator stop")

    monkeypatch.setattr(eng, "_check_budgets", stop_when_running)
    summary = eng.run()
    events = _events(config.run_dir)
    assert calls == [(True, 0, None), (False, 0, "HB-RUN-006")]
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-RUN-006"]
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["outcome"] == "completed"
    assert summary.exit_code == 3


def test_keep_awake_is_released_when_the_run_raises(base, monkeypatch):
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    calls = []
    monkeypatch.setattr(host, "keep_awake", calls.append)
    monkeypatch.setattr(eng, "_check_budgets", lambda _now: (_ for _ in ()).throw(RuntimeError("budget check failed")))
    with pytest.raises(RuntimeError, match="budget check failed"):
        eng.run()
    assert calls == [True, False]


def test_a_failed_memory_query_still_records_the_outcome_with_null(base, monkeypatch):
    # GlobalMemoryStatusEx failing is "not recorded": the cell.outcome row is still written.
    def fail(out):
        ctypes.set_last_error(6)
        return 0

    monkeypatch.setattr(host._k32, "GlobalMemoryStatusEx", fail)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    out = _outcomes(events).get(p["cells"][0]["cell_id"])
    assert out is not None and out["host_mem_available"] is None


def test_a_run_with_nothing_left_to_launch_ends_without_an_idle_wait(base):  # the end drains without waiting
    p = _plan(n_cells=1)
    p["cells"] = []
    started = time.monotonic()
    summary, events, _ = _run(base, p, FakeLauncher({}))
    assert time.monotonic() - started < 0.8
    assert [e["kind"] for e in events] == ["run.started", "run.completed"] and summary.exit_code == 0


def test_the_engine_loop_passes_every_fifth_of_a_second_and_never_spins(base, monkeypatch):  # loop_interval = 0.2 s
    import itertools
    import statistics

    from harness_bench import oslock
    beats = []
    real = oslock.RunLock.heartbeat

    def timed(self):  # one beat per pass of the loop
        beats.append(time.monotonic())
        return real(self)

    monkeypatch.setattr(oslock.RunLock, "heartbeat", timed)
    p = _plan(n_cells=1)
    _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"sleep": 1}}))
    gaps = [b - a for a, b in itertools.pairwise(beats)]
    assert len(gaps) >= 3 and 0.15 <= statistics.median(gaps) <= 0.6


def test_free_space_exactly_at_the_floor_is_not_below_it(base, monkeypatch):  # HB-RUN-004: "below the floor"
    real = shutil.disk_usage
    p = _plan(n_cells=1)
    monkeypatch.setattr(shutil, "disk_usage", lambda path: real(path)._replace(free=p["parameters"]["disk_floor_bytes"]))
    summary, events, _ = _run(base, p, FakeLauncher({}))
    assert not any(e["kind"] == "run.launch_stopped" for e in events) and summary.exit_code == 0


def test_a_plan_of_more_than_256_cells_can_end_complete(base):  # cell counts are compared by value, not identity
    class NoArgv(FakeLauncher):  # every cell fails fast and unclassified: no process, no circuit breaker
        def argv_env(self, cell, home, traceparent):
            raise RuntimeError("profile cannot build argv")

    p = _plan(n_cells=257, parallelism=64)
    summary, events, _ = _run(base, p, NoArgv({}))
    assert len(_outcomes(events)) == 257 and events[-1]["kind"] == "run.completed" and summary.exit_code == 0


def test_grading_never_runs_on_a_run_that_needs_recovery(base, monkeypatch):  # no run.completed, so no pass
    from harness_bench import archive

    def boom(*args, **kwargs):
        raise OSError("archive volume unavailable")

    graded = []
    monkeypatch.setattr(archive, "archive_cell", boom)
    summary, _, _ = _run(base, _plan(n_cells=1), FakeLauncher({}), grade=graded.append)
    assert graded == [] and summary.exit_code == 3


def test_a_spawn_failure_with_no_win32_error_records_zero(base, monkeypatch):
    from harness_bench import procs

    def refused(*args, **kwargs):
        raise procs.SpawnError("refused", None)

    monkeypatch.setattr(procs, "spawn", refused)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["cause"], out["win32_error"]) == ("spawn", 0)


def test_the_outcome_records_times_in_milliseconds_and_a_capped_detail(base, monkeypatch):
    from harness_bench import driver
    real = driver.run_turn

    def timed(*args, **kwargs):
        result = real(*args, **kwargs)
        result.handshake_seconds, result.turn_seconds, result.last_update_seconds = 1.25, 2.5, 2.0
        result.detail = "d" * 1000
        return result

    monkeypatch.setattr(driver, "run_turn", timed)
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["handshake_ms"], out["turn_ms"], out["last_update_ms"]) == (1250, 2500, 2000)
    assert out["detail"] == "d" * 300  # the driver's detail is capped at 300 characters


def test_span_ids_are_w3c_parent_ids():  # 16 lowercase hex characters (W3C Trace Context), deterministic
    sid = engine.span_id("a" * 32, "cell-1", "cell")
    assert len(sid) == 16 and int(sid, 16) >= 0 and sid == sid.lower()
    assert sid == engine.span_id("a" * 32, "cell-1", "cell") != engine.span_id("a" * 32, "cell-2", "cell")


def test_a_failed_append_of_the_launch_intent_ends_the_run_incomplete_not_raised(base, monkeypatch):
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "cell.launch_intent":
            raise OSError("disk full")
        return real(self, record)

    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    assert _engine_run(p, config).exit_code == 3
    assert not (base / "cells").exists()  # the cell was never launched


def test_a_workspace_that_fails_before_any_folder_exists_is_still_archived(base):
    def broken(cell, cell_dir):
        raise OSError("disk says no")

    p = _plan(n_cells=1)
    summary, events, _ = _run(base, p, FakeLauncher({}), build_workspace=broken)
    assert not any(e["kind"] == "cell.archive_failed" for e in events)
    assert [e["kind"] for e in events if e.get("cell_id")][-2:] == ["cell.archived", "cell.workspace_deleted"]
    assert summary.exit_code == 0


def test_a_worker_still_running_when_the_run_fails_is_refused_at_once_not_left_waiting(base, monkeypatch):
    calls = []

    def slept(self):  # the engine thread fails on its second pass, while the only cell is mid-turn
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("engine thread bug")
        return False

    monkeypatch.setattr(host.SleepDetector, "slept", slept)
    p = _plan(n_cells=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({p["cells"][0]["label"]: {"sleep": 2}})},
                                 build_workspace=_build_workspace, grade=None)
    with pytest.raises(RuntimeError):
        engine.Engine(p, config).run()
    worker = next(t for t in threading.enumerate() if t.name == f"cell-{p['cells'][0]['cell_id']}")
    worker.join(30)
    assert not worker.is_alive(), "the worker waits forever on a record the ended engine will never drain"


def test_turn_usage_is_recorded_under_attempt_one(base):  # the row key is (run, cell, attempt, model)
    p = _plan(n_cells=1)
    _, _, config = _run(base, p, FakeLauncher({}))
    rows = ledger.read_segment(next((config.run_dir / "turn_usage").glob("*.jsonl")))
    assert [(r["cell_id"], r["attempt"]) for r in rows] == [(p["cells"][0]["cell_id"], 1)]


def test_the_archive_is_recorded_as_attempt_one(base):
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, FakeLauncher({}))
    assert [(e["cell_id"], e["archive_attempt"]) for e in events if e["kind"] == "cell.archived"] == [(p["cells"][0]["cell_id"], 1)]


def _unlink_segments(run_dir: Path) -> None:
    segments = [seg for fact in engine.FACTS for seg in (run_dir / fact).glob("*.jsonl")]
    assert len(segments) == len(engine.FACTS)
    for seg in segments:
        seg.unlink()  # PermissionError while the engine still holds the file open (Windows)


def test_the_run_releases_every_ledger_segment_when_it_returns(base, monkeypatch):
    from harness_bench import archive

    def boom(*args, **kwargs):
        raise OSError("archive volume unavailable")

    monkeypatch.setattr(archive, "archive_cell", boom)  # a run that needs recovery: no segment is sealed
    _, _, config = _run(base, _plan(n_cells=1), FakeLauncher({}))
    _unlink_segments(config.run_dir)
    monkeypatch.undo()  # a whole run: every segment is sealed
    _, _, config = _run(base, _plan(n_cells=1), FakeLauncher({}))
    _unlink_segments(config.run_dir)


def test_a_windows_disk_full_error_is_a_full_disk():  # ERROR_HANDLE_DISK_FULL maps to EINVAL, not ENOSPC
    handle_disk_full = OSError(0, "The disk is full", None, 39)
    assert handle_disk_full.errno != errno.ENOSPC and engine._disk_full(handle_disk_full)
    assert engine._disk_full(OSError(0, "There is not enough space on the disk", None, 112))
    assert not engine._disk_full(OSError(0, "Access is denied", None, 5))


def test_the_stderr_tail_keeps_the_last_bytes_up_to_its_limit():
    import io
    tail = bytearray()
    engine._keep_tail(io.BytesIO(bytes(range(100))), tail, 10)
    assert tail == bytes(range(90, 100))


@pytest.mark.parametrize("error", [OSError(109, "The pipe has been ended"), ValueError("read of closed file")])
def test_a_stderr_pipe_that_fails_ends_the_tail_quietly(error):  # the tail is best effort; its reader thread never raises
    class Failing:
        calls = 0

        def read1(self, size):
            Failing.calls += 1
            if Failing.calls > 1:
                raise error
            return b"last words"

    tail = bytearray()
    engine._keep_tail(Failing(), tail, 64)
    assert tail == b"last words"


CRASHER = """
import json, sys, uuid
from concurrent.futures import Future
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


FAILER = """
import sys
from pathlib import Path
sys.path.insert(0, {tests!r}); sys.path.insert(0, {src!r})
import test_engine as t
from harness_bench import engine, host
cells = Path({cells!r})

def slept(self):  # the engine thread fails once the only cell is mid-turn (its prompt is on disk)
    if any(cells.rglob(".fake-prompt.txt")):
        raise RuntimeError("engine thread bug")
    return False

host.SleepDetector.slept = slept
p = t._plan(n_cells=1)
p["run_id"] = {run_id!r}
launcher = t.FakeLauncher({{c["label"]: {{"mode": "hang_prompt"}} for c in p["cells"]}})
config = engine.EngineConfig(run_dir=Path({run_dir!r}), cells_root=cells, launchers={{"fake": launcher}},
                             build_workspace=t._build_workspace, grade=None)
engine.Engine(p, config).run()
"""


def test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running(base):  # workers are daemon threads
    run_id = "fail-" + uuid.uuid4().hex[:4]
    script = base / "failer.py"
    script.write_text(FAILER.format(tests=str(Path(__file__).parent), src=str(ROOT / "src"), run_id=run_id,
                                    run_dir=str(base / "runs" / run_id), cells=str(base / "cells")), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert proc.wait(timeout=60) == 1, "the process did not exit: a worker thread holds it open"
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
            proc.wait(timeout=30)
    time.sleep(2)
    [started] = [e for e in _events(base / "runs" / run_id) if e["kind"] == "attempt.process_started"]
    assert not host.process_alive(started["pid"], started["created_at"])


# --- the kill-retry backoff cap (T10: the code had drifted to 60 s; the design says 30 s) -----------------------------

class _UnconfirmedKill:
    """A CellProcess stand-in whose kill is confirmed only on its n-th check; it records each check's timeout."""

    def __init__(self, confirmed_on: int):
        import io
        from types import SimpleNamespace
        self.proc = SimpleNamespace(stdin=io.BytesIO())
        self.job = SimpleNamespace(active=lambda: 0 if len(self.timeouts) >= self.confirmed_on else 1, pids=list)
        self.confirmed_on = confirmed_on
        self.timeouts: list[float] = []

    def terminate_and_confirm(self, timeout):
        self.timeouts.append(timeout)
        return len(self.timeouts) >= self.confirmed_on

    def wait(self, timeout=None):
        return 0


def test_an_unconfirmed_kill_backs_off_from_1_s_doubling_to_the_designs_30_s_cap(base):
    """design/phase1-walking-skeleton.md:189: "Retries use capped exponential backoff (1 s doubling to 30 s)".
    Red at 70531dc, while KILL_RETRY_CAP was 60.0 (3d14c73, T1-8): the waits after 16 s were 32 and 60."""
    config = engine.EngineConfig(run_dir=base / "r", cells_root=base / "c", launchers={}, build_workspace=_build_workspace,
                                 grade=None)
    eng = engine.Engine(_plan(n_cells=1), config)
    cp = _UnconfirmedKill(confirmed_on=9)
    a = engine._Active(eng.plan["cells"][0], threading.current_thread())
    assert eng._end_process(a, cp, 0) == (0, True, "terminate")
    assert cp.timeouts == [eng.params["kill_escalation"], 1, 2, 4, 8, 16, 30, 30, 30]
