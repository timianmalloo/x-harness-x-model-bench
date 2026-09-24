"""The run engine (ADR-0007, ADR-0013; design: Error & concurrency model) against the fake ACP agent.

Each test runs the real engine: real ledger, real Job Objects, real archive; only the harness is the
fake agent and the working-copy builder is a stub (the real one is covered in test_workspace.py).
Every run's events are replayed against the model's phase-1 guards (lifecycle.replay, US-44 AC3).
"""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from harness_bench import engine, ledger, lifecycle, plan
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code

pytestmark = pytest.mark.native
FAKE = Path(__file__).parent / "fake_acp_agent.py"
ROOT = Path(__file__).resolve().parents[1]
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
        (home / ".credentials.json").write_text('{"token":"secret"}', encoding="utf-8")

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


@pytest.fixture
def base():
    root = Path("C:/Projects/bench-test") / uuid.uuid4().hex[:8]
    root.mkdir(parents=True)
    yield root
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    if root.parent.exists() and not any(root.parent.iterdir()):
        root.parent.rmdir()


def _plan(n_cells=2, budget=60, parallelism=2, labels=None):
    cells = []
    for i in range(n_cells):
        c = plan.Cell("X1", "v1", 5, f"combo{i}", "fake", "fake-model", "on" if i % 2 == 0 else "off", 1, budget)
        cells.append({"cell_id": c.id, "label": labels[i] if labels else c.label, **c.__dict__})
    return {"run_id": "r-" + uuid.uuid4().hex[:6], "plan_hash": "p" * 64, "trace_id": "a" * 32,
            "parameters": {**plan.DEFAULT_PARAMETERS, "parallelism": parallelism, "disk_floor_bytes": 1024},
            "cells": cells, "builds": {"fake": {}}}


def _build_workspace(cell: dict, cell_dir: Path) -> dict:
    ws = cell_dir / "ws"
    ws.mkdir(parents=True)
    (ws / "slug.py").write_text("def slugify(t): raise NotImplementedError\n", encoding="utf-8")
    return {"pack_manifest": 0}


def _run(base, p, launcher, **cfg):
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": launcher}, build_workspace=cfg.pop("build_workspace", _build_workspace),
                                 grade=cfg.pop("grade", None), end_grace=cfg.pop("end_grace", 5), **cfg)
    summary = engine.Engine(p, config).run()
    events = engine.read_events(config.run_dir)
    lifecycle.replay(events, parallelism=p["parameters"]["parallelism"])  # conformance (US-44 AC3)
    return summary, events, config


def _outcomes(events):
    return {e["cell_id"]: e for e in events if e["kind"] == "cell.outcome"}


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
            assert not engine.process_alive(e["pid"], e["created_at"])
    for fact in ("events", "turn_usage", "archive_files"):
        for seg in (config.run_dir / fact).glob("*.jsonl"):
            assert ledger.verify_segment(seg).sealed


def test_the_engine_grades_once_after_every_cell_is_archived_and_records_the_pass(base):
    p = _plan()
    calls = []

    def grade(run_dir):
        archived = [e["cell_id"] for e in engine.read_events(run_dir) if e["kind"] == "cell.archived"]
        calls.append(sorted(archived))
        return {"grading_id": "grade-x", "heads": {"scores": "h" * 64}, "cells_graded": len(archived)}

    summary, events, _ = _run(base, p, FakeLauncher({}), grade=grade)
    assert calls == [sorted(c["cell_id"] for c in p["cells"])]
    assert events[-1]["grading"] == {"grading_id": "grade-x", "heads": {"scores": "h" * 64}, "cells_graded": 2}
    assert summary.exit_code == 0


def test_a_failed_grading_pass_never_costs_the_run(base):  # re-gradable from the archive (US-26)
    def grade(run_dir):
        raise BenchError("HB-GRD-001", "held by bench grade")

    summary, events, config = _run(base, _plan(n_cells=1), FakeLauncher({}), grade=grade)
    assert events[-1]["kind"] == "run.completed" and summary.exit_code == 0
    assert events[-1]["grading"] == {"error_code": "HB-GRD-001"}
    assert ledger.verify_segment(next((config.run_dir / "events").glob("*.jsonl"))).sealed


def test_verbatim_prompt_reaches_the_agent_and_turn_usage_is_recorded(base):
    p = _plan(n_cells=1)
    p["cells"][0]["prompt"] = "Implement slugify.\r\nKeep the signature.\n"
    _, _, config = _run(base, p, FakeLauncher({}))
    archive = config.run_dir / "archive" / p["cells"][0]["cell_id"] / "attempt-1" / "ws" / ".fake-prompt.txt"
    assert archive.read_bytes().decode("utf-8") == p["cells"][0]["prompt"]
    usage = ledger.read_segment(next((config.run_dir / "turn_usage").glob("*.jsonl")))
    assert [(u["model"], u["uncached_input"], u["cache_read"], u["cache_write"], u["output"]) for u in usage] == [("fake-model", 3, 30, 7, 5)]


def test_budget_kill_is_timed_out_and_recorded_only_after_the_tree_is_gone(base):  # T-ENG-budget
    p = _plan(n_cells=1, budget=2)
    started = time.monotonic()
    _, events, _ = _run(base, p, FakeLauncher({p["cells"][0]["label"]: {"mode": "hang_prompt"}}))
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert out["outcome"] == "timed_out" and out["code"] == "HB-CELL-301"
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    assert ended["confirmed"] == 1 and ended["seq"] < out["seq"]
    assert time.monotonic() - started < 45


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
    summary = engine.Engine(p, config).run()
    assert summary.exit_code == 3
    assert not list((base / "cells").rglob(".fake-prompt.txt")) and not list((config.run_dir / "archive").rglob(".fake-prompt.txt"))


def test_a_started_run_is_refused(base):
    p = _plan(n_cells=1)
    _run(base, p, FakeLauncher({}))
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({})}, build_workspace=_build_workspace, grade=None)
    with pytest.raises(BenchError) as e:
        engine.Engine(p, config).run()
    assert e.value.code == "HB-USR-002"


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
        events = engine.read_events(base / "runs" / run_id) if (base / "runs" / run_id / "events").exists() else []
        pids = [(e["pid"], e["created_at"]) for e in events if e["kind"] == "attempt.process_started"]
    assert len(pids) == 2, "cells never started"
    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    proc.wait(timeout=30)
    time.sleep(2)
    for pid, created in pids:
        assert not engine.process_alive(pid, created), f"cell process {pid} survived the engine"
