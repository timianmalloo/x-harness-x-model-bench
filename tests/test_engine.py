"""The run engine (ADR-0007, ADR-0013; design: Error & concurrency model) against the fake ACP agent.

Each test runs the real engine: real ledger, real Job Objects, real archive; only the harness is the
fake agent and the working-copy builder is a stub (the real one is covered in test_workspace.py).
Every run's events are replayed against the model's phase-1 guards (lifecycle.replay, US-44 AC3).
"""

import ctypes
import errno
import itertools
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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


CONTROL_UID = "0123456789abcdef0123456789abcdef"
CONTROL_EFFECTS = {"applied", "rejected (already resolved)", "rejected (invalid)", "no-op (already stopped)",
                   "no-op (run ending)"}  # design 3: the closed effect set of control.applied


def _control(uid: str, **over) -> dict:
    return {"schema": "bench-control/1", "uuid": uid, "control": "stop", "decision_id": None, "option": None,
            "requested_at": "2026-09-25T00:00:00Z", **over}


def _stop_file(run_dir: Path, uid: str | None = None, body: str | None = None, name: str | None = None) -> Path:
    """A control file written as `bench stop` writes it: a temp file, then os.replace (design 4.1)."""
    uid = uid or uuid.uuid4().hex
    folder = run_dir / "control"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{name or uid}.json"
    temp = folder / f"{name or uid}.json.tmp"
    temp.write_text(json.dumps(_control(uid)) if body is None else body, encoding="utf-8")
    os.replace(temp, target)
    return target


def _wait(predicate, limit: float = 20.0) -> None:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline and not predicate():
        time.sleep(0.02)
    assert predicate(), f"not reached within {limit} s"


def _stop_and_wait(run_dir: Path) -> None:
    """Called from a cell's worker thread: drop a stop file, return once the engine thread has consumed it."""
    control = _stop_file(run_dir)
    _wait(lambda: not control.exists())


def _running_engine(base, p, launcher, on_ready, *, grace=1.0, grade=None):
    """Start the engine on its own thread and return once on_ready(engine) holds (the point to stop at)."""
    launcher.shutdown_grace = grace
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": launcher}, build_workspace=_build_workspace, grade=grade)
    eng = engine.Engine(p, config)
    box = {}

    def target():
        try:
            box["summary"] = eng.run()
        except BenchError as exc:
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True, name="engine-under-test")
    thread.start()
    _wait(lambda: on_ready(eng))
    return eng, config, thread, box


def _confirm(p: dict, base: Path) -> dict:
    """Freeze the plan under runs/<id>/ so `bench status` can read the run while and after it runs."""
    p["profiles"] = {"fake": {"profile_hash": "", "usage_source": "acp_turn", "auxiliary_models": [],
                              "record_glob": "projects/**/*.jsonl"}}
    p["plan_hash"] = plan.plan_hash(p)
    plan.confirm(base / "runs" / p["run_id"], p)
    return p


def _markers(base: Path, p: dict, name: str) -> list[Path]:
    return [m for m in (base / "cells" / p["run_id"]).glob(f"*/ws/{name}") if m.stat().st_size]


def test_stop_ends_stubborn_trees_within_30s(base):  # R10-1 and R10-3: real Job Objects, two children that ignore it
    from harness_bench import status
    p = _confirm(_plan(n_cells=2, parallelism=2), base)
    launcher = FakeLauncher({c["label"]: {"mode": "stubborn"} for c in p["cells"]})
    _, cfg, thread, box = _running_engine(base, p, launcher, lambda _: len(_markers(base, p, ".fake-stubborn-child.pid")) == 2,
                                          grace=10.0)
    children = [(pid, host.creation_time(pid)) for pid in
                (int(m.read_text(encoding="utf-8")) for m in _markers(base, p, ".fake-stubborn-child.pid"))]
    _stop_file(cfg.run_dir)
    started = time.monotonic()
    phase = None
    while phase != "stopped" and time.monotonic() - started <= 30:  # R10-3: what `bench status` shows (UXA-10)
        phase = status.build(cfg.run_dir).phase
        time.sleep(0.1)
    shown = time.monotonic() - started
    thread.join(30)
    assert not thread.is_alive(), "the engine did not stop the stubborn process trees within 30 s"
    events = _events(cfg.run_dir)
    applied = next(e for e in events if e["kind"] == "control.applied")
    outs = [e for e in events if e["kind"] == "cell.outcome"]
    stop_s = (max(e["mono_ns"] for e in outs) - applied["mono_ns"]) / 1e9  # the engine's clock: the ledger's mono_ns
    print(f"\nR10-1 measured: last cell.outcome{{stopped}} {stop_s:.2f} s after control.applied; "
          f"bench status showed stopped {shown:.2f} s after the control file was written")
    assert applied["effect"] == "applied"
    assert phase == "stopped" and shown <= 30
    assert [e["outcome"] for e in outs] == ["stopped", "stopped"] and stop_s <= 30
    assert [e["ended_by"] for e in events if e["kind"] == "attempt.process_ended"] == ["terminate", "terminate"]
    assert all(not host.process_alive(pid, created) for pid, created in children)
    assert len([e for e in events if e["kind"] == "cell.archived"]) == 2  # US-45: every started cell is archived
    assert box["summary"].exit_code == 3  # design 5, step 4: a stopped run exits 3
    lifecycle.replay(events, parallelism=2)


def test_a_second_stop_is_recorded_as_a_no_op(base):  # R10-8; a re-read of the ledger rebuilds the engine's control state
    p = _plan(n_cells=1)
    launcher = FakeLauncher({p["cells"][0]["label"]: {"mode": "stubborn"}})
    eng, cfg, thread, _ = _running_engine(base, p, launcher, lambda _: bool(_markers(base, p, ".fake-stubborn-child.pid")))
    _stop_file(cfg.run_dir)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    rows = _events(cfg.run_dir)
    controls = [e for e in rows if e["kind"] == "control.applied"]
    assert [e["code"] for e in rows if e["kind"] == "run.stopped"] == ["HB-RUN-006"]
    assert sorted(e["effect"] for e in controls) == ["applied", "no-op (already stopped)"]
    assert {e["uuid"] for e in controls} == eng.applied_controls  # the dedup set, rebuilt from control.applied (design 4.1)
    assert next(e["code"] for e in rows if e["kind"] == "run.stopped") == eng.run_stopped
    lifecycle.replay(rows, parallelism=1)


@pytest.fixture
def reader(base):
    """An engine with only its events writer: the control reader driven on this thread, with no loop."""
    p = _plan(n_cells=1)
    run_dir = base / "runs" / p["run_id"]
    run_dir.mkdir(parents=True)
    eng = engine.Engine(p, engine.EngineConfig(run_dir, base / "cells", {"fake": FakeLauncher({})}, _build_workspace, None))
    eng.writers["events"] = ledger.SegmentWriter.create(run_dir / "events", "engine-1")
    yield eng
    eng.writers["events"].close()


MALFORMED = {  # name -> (file stem or None for the uuid, body): R10-9's Postel cases
    "an extra key": (None, json.dumps({**_control(CONTROL_UID), "extra": 1})),
    "a missing key": (None, json.dumps({k: v for k, v in _control(CONTROL_UID).items() if k != "option"})),
    "over 4 KiB": (None, json.dumps(_control(CONTROL_UID)) + " " * 5000),  # valid JSON: only the size refuses it
    "not JSON": (None, "{not json"),
    "a stem that is not the uuid": ("f" * 32, json.dumps(_control(CONTROL_UID))),
    "a uuid outside the grammar": ("XYZ", json.dumps(_control("XYZ"))),
    "a stop carrying an option": (None, json.dumps(_control(CONTROL_UID, option="continue"))),
    "a time that is not UTC ISO": (None, json.dumps(_control(CONTROL_UID, requested_at="yesterday"))),
}


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a_malformed_control_file_is_quarantined(reader, case, caplog):  # R10-9
    name, body = MALFORMED[case]
    path = _stop_file(reader.cfg.run_dir, uid=CONTROL_UID, body=body, name=name)
    with caplog.at_level(logging.WARNING, logger="harness_bench.engine"):
        reader._read_controls()
    assert not path.exists() and path.with_suffix(".rejected").exists()
    assert _events(reader.cfg.run_dir) == [] and reader.run_stopped is None and reader.stopped is None
    assert [(r.message, r.error_code, r.detail) for r in caplog.records] == [("control rejected", "HB-USR-002", path.name)]


def test_a_control_file_that_cannot_be_read_is_retried_next_tick(reader, monkeypatch):  # R10-9b (PE-9)
    path = _stop_file(reader.cfg.run_dir)
    real = Path.read_bytes

    def held(self):
        if self == path:
            raise PermissionError(13, "held by the indexer")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", held)
    reader._read_controls()
    assert path.exists() and not path.with_suffix(".rejected").exists() and _events(reader.cfg.run_dir) == []
    monkeypatch.undo()
    reader._read_controls()
    assert not path.exists()
    assert [(e["kind"], e.get("effect")) for e in _events(reader.cfg.run_dir)] == [
        ("control.applied", "applied"), ("run.launch_stopped", None), ("run.stopped", None)]  # design 5, steps 1-3


def test_control_file_is_applied_once_even_if_delete_fails(reader, monkeypatch):  # design 4.1: the dedup set
    path = _stop_file(reader.cfg.run_dir)
    real = Path.unlink

    def held(self, missing_ok=False):
        if self == path:
            raise PermissionError(13, "held by antivirus")
        return real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", held)
    reader._read_controls()
    reader._read_controls()
    assert path.exists()
    assert [e["kind"] for e in _events(reader.cfg.run_dir)] == ["control.applied", "run.launch_stopped", "run.stopped"]
    monkeypatch.undo()
    reader._read_controls()
    assert not path.exists() and len(_events(reader.cfg.run_dir)) == 3  # deleted with no second row


_JSON = st.none() | st.booleans() | st.integers() | st.text(max_size=12) | st.lists(st.integers(), max_size=2) | st.sampled_from(
    ["stop", "answer", "bench-control/1", "D1", "D0", "continue", "2026-09-25T00:00:00Z", "2026-99-99T00:00:00Z",
     CONTROL_UID])


@settings(max_examples=60, deadline=None)
@given(over=st.dictionaries(st.sampled_from([*_control(CONTROL_UID), "extra"]), _JSON, max_size=4),
       drop=st.sets(st.sampled_from(list(_control(CONTROL_UID))), max_size=2), stem_is_uuid=st.booleans())
def test_any_control_object_never_raises_and_keeps_the_closed_effects(over, drop, stem_is_uuid):  # design 16.3 D2
    with tempfile.TemporaryDirectory() as tmp:
        p = _plan(n_cells=1)
        run_dir = Path(tmp) / "run"
        run_dir.mkdir()
        eng = engine.Engine(p, engine.EngineConfig(run_dir, Path(tmp) / "cells", {"fake": FakeLauncher({})},
                                                   _build_workspace, None))
        eng.writers["events"] = ledger.SegmentWriter.create(run_dir / "events", "engine-1")
        try:
            data = {k: v for k, v in {**_control(CONTROL_UID), **over}.items() if k not in drop}
            _stop_file(run_dir, body=json.dumps(data), name=CONTROL_UID if stem_is_uuid else "e" * 32)
            eng._read_controls()
            rows = _events(run_dir)
        finally:
            eng.writers["events"].close()
        controls = [e for e in rows if e["kind"] == "control.applied"]
        assert {e["effect"] for e in controls} <= CONTROL_EFFECTS and {e["control"] for e in controls} <= {"stop", "answer"}
        assert len(controls) <= 1 and not list((run_dir / "control").glob("*.json"))  # consumed or quarantined
        assert ([e["kind"] for e in rows if e["kind"] == "run.stopped"] == ["run.stopped"]) == (
            [e["effect"] for e in controls] == ["applied"])


def test_a_failed_append_of_a_control_row_ends_the_run_incomplete_not_raised(base, monkeypatch):  # design 11
    real = ledger.SegmentWriter.append

    def failing(self, record):
        if record.get("kind") == "control.applied":
            raise OSError("disk full")
        return real(self, record)

    p = _plan(n_cells=1)
    launcher = FakeLauncher({p["cells"][0]["label"]: {"hang": True}})
    eng, cfg, thread, box = _running_engine(base, p, launcher, lambda e: any(a.prompt_mono for a in list(e.active.values())))
    started = next(e for e in _events(cfg.run_dir) if e["kind"] == "attempt.process_started")
    monkeypatch.setattr(ledger.SegmentWriter, "append", failing)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    assert "error" not in box, box.get("error")  # the ledger broke: the loop aborts and drains, never raises
    assert box["summary"].exit_code == 3 and eng.broken
    assert not host.process_alive(started["pid"], started["created_at"])  # the live cell was killed on the way out


def test_a_stop_during_the_build_never_spawns(base):  # R10-5
    p = _plan(n_cells=1)
    launcher = FakeLauncher({})
    seeded = []
    real_seed = launcher.seed
    launcher.seed = lambda home, model: (seeded.append(home), real_seed(home, model))
    run_dir = base / "runs" / p["run_id"]

    def build_then_stop(cell, cell_dir):
        info = _build_workspace(cell, cell_dir)
        _stop_and_wait(run_dir)
        return info

    summary, events, _ = _run(base, p, launcher, build_workspace=build_then_stop)
    kinds = [e["kind"] for e in events if e.get("cell_id")]
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert "attempt.process_started" not in kinds and seeded == []  # no spawn, and no login copied for one
    assert (out["outcome"], out["cause"], out["code"]) == ("stopped", None, None)
    assert "cell.archived" in kinds and summary.exit_code == 3


def test_a_stop_after_the_build_check_is_caught_at_the_spawn(base):  # design 11: the spawn linearization point
    p = _plan(n_cells=1)
    launcher = FakeLauncher({})
    real_seed = launcher.seed
    run_dir = base / "runs" / p["run_id"]
    launcher.seed = lambda home, model: (real_seed(home, model), _stop_and_wait(run_dir))
    summary, events, _ = _run(base, p, launcher)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert not [e for e in events if e["kind"] == "attempt.process_started"]
    assert (out["outcome"], out["cause"]) == ("stopped", None) and summary.exit_code == 3


def test_a_stop_during_the_spawn_terminates_at_once(base, monkeypatch):  # R10-10 (TA m3)
    from harness_bench import procs
    p = _plan(n_cells=1)
    run_dir = base / "runs" / p["run_id"]
    real_spawn = procs.spawn

    def spawn_then_stop(*args, **kwargs):
        cp = real_spawn(*args, **kwargs)
        _stop_and_wait(run_dir)
        return cp

    monkeypatch.setattr(procs, "spawn", spawn_then_stop)
    summary, events, _ = _run(base, p, FakeLauncher({}), shutdown_grace=6.0)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert out["outcome"] == "stopped" and not [e for e in events if e["kind"] == "cell.prompt_sent"]
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["ended_by"] == "terminate"  # no grace: no prompt
    assert summary.exit_code == 3


def test_an_operator_stop_gives_the_grace_before_the_kill(base):  # R21-4 through bench stop's control file
    p = _plan(n_cells=1)
    launcher = FakeLauncher({p["cells"][0]["label"]: {"mode": "on_cancel"}})
    _, cfg, thread, box = _running_engine(base, p, launcher, lambda _: bool(_markers(base, p, ".fake-prompt.txt")), grace=6.0)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    events = _events(cfg.run_dir)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["cause"], out["stop_reason"]) == ("stopped", None, "cancelled")
    assert next(e for e in events if e["kind"] == "attempt.process_ended")["ended_by"] == "grace"
    assert box["summary"].exit_code == 3


def test_an_ended_turn_keeps_its_outcome_under_a_stop(base):  # R10-11, R21-2 (PE-2)
    p = _plan(n_cells=1)
    launcher = FakeLauncher({p["cells"][0]["label"]: {"linger": 2}})  # the turn ends, then the process lingers
    _, cfg, thread, box = _running_engine(base, p, launcher, lambda e: any(a.ended for a in list(e.active.values())),
                                          grace=6.0)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    events = _events(cfg.run_dir)
    applied = next(e for e in events if e["kind"] == "control.applied")
    ended = next(e for e in events if e["kind"] == "attempt.process_ended")
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert applied["effect"] == "applied" and [e["kind"] for e in events].count("run.stopped") == 1
    assert (out["outcome"], out["cause"]) == ("completed", None)
    assert ended["ended_by"] == "exit" and ended["mono_ns"] - applied["mono_ns"] <= 6_000_000_000  # within the grace
    assert box["summary"].exit_code == 3
    lifecycle.replay(events, parallelism=1)


def test_a_stop_after_the_breaker_is_still_a_run_stop(base):  # R10-12 (S-1, PE-1)
    from harness_bench import status
    p = _confirm(_plan(n_cells=5, parallelism=2), base)
    slow, *fast = p["cells"]
    launcher = FakeLauncher({slow["label"]: {"hang": True}, **{c["label"]: {"mode": "provider_error"} for c in fast}})
    _, cfg, thread, box = _running_engine(base, p, launcher, lambda e: e.stopped is not None)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    events = _events(cfg.run_dir)
    assert [e["code"] for e in events if e["kind"] == "run.launch_stopped"] == ["HB-CELL-108"]
    assert [e["code"] for e in events if e["kind"] == "run.stopped"] == ["HB-RUN-006"]
    assert _outcomes(events)[slow["cell_id"]]["outcome"] == "stopped"
    s = status.build(cfg.run_dir)
    assert (s.phase, s.stop_code) == ("stopped", "HB-CELL-108")  # R-3: stop_code stays the launch stop's code
    assert box["summary"].exit_code == 3
    lifecycle.replay(events, parallelism=2)


def test_a_late_control_is_recorded_not_lost(base):  # R10-13 (PE-10, Simplifier N-2)
    p = _plan(n_cells=1)
    run_dir = base / "runs" / p["run_id"]
    summary, events, _ = _run(base, p, FakeLauncher({}), grade=lambda d: (_stop_file(d), {"cells_graded": 1})[1])
    controls = [e for e in events if e["kind"] == "control.applied"]
    assert [e["effect"] for e in controls] == ["no-op (run ending)"]
    assert [e["kind"] for e in events[-2:]] == ["control.applied", "run.completed"]  # after grading, before the end
    assert not list((run_dir / "control").iterdir())
    assert "run.stopped" not in [e["kind"] for e in events] and summary.exit_code == 0


def test_stop_outranks_a_provider_error(base):  # R10-14 (TA M4)
    p = _plan(n_cells=1)
    launcher = FakeLauncher({p["cells"][0]["label"]: {"mode": "provider_error", "hang": True}})
    records = lambda _: [r for r in (base / "cells" / p["run_id"]).rglob("projects/**/*.jsonl") if r.stat().st_size]
    _, cfg, thread, box = _running_engine(base, p, launcher, records)
    _stop_file(cfg.run_dir)
    thread.join(30)
    assert not thread.is_alive()
    events = _events(cfg.run_dir)
    out = _outcomes(events)[p["cells"][0]["cell_id"]]
    assert (out["outcome"], out["cause"], out["code"]) == ("stopped", None, None)
    archived = [r.read_text(encoding="utf-8") for r in (cfg.run_dir / "archive").rglob("projects/**/*.jsonl")]
    assert any("isApiErrorMessage" in text for text in archived)  # the provider error was there to outrank
    assert box["summary"].exit_code == 3


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
    records = engine._read_records(launcher or _NativeRecords(), base, turn.session_id)
    return engine.Engine(_plan(n_cells=1), config)._classify(turn, records, exit_status, tail, kill_reason)


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


def test_keep_awake_is_held_through_an_operator_stop(base, monkeypatch):  # R10-7a, through bench stop's control file
    p = _plan(n_cells=2, parallelism=1)
    config = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                                 launchers={"fake": FakeLauncher({p["cells"][0]["label"]: {"hang": True}})},
                                 build_workspace=_build_workspace, grade=None)
    eng = engine.Engine(p, config)
    calls = []
    monkeypatch.setattr(host, "keep_awake", lambda flag: calls.append((flag, len(eng.active), eng.stopped)))
    real_tick = eng.on_tick

    def stop_while_running():
        real_tick()
        if any(a.prompt_mono for a in eng.active.values()) and not (config.run_dir / "control").exists():
            _stop_file(config.run_dir)  # once: the reader removes the file, not the folder

    eng.on_tick = stop_while_running
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("summary", eng.run()), daemon=True)
    thread.start()
    thread.join(30)
    assert not thread.is_alive()
    events = _events(config.run_dir)
    assert calls == [(True, 0, None), (False, 0, "HB-RUN-006")]  # released only after every stopped worker ended
    assert [e["outcome"] for e in events if e["kind"] == "cell.outcome"] == ["stopped"]
    assert box["summary"].exit_code == 3


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


# --- decision requests (US-15; design 6) -----------------------------------------------------------------------------

ORDERS = [order for n in (1, 2, 3) for order in itertools.permutations(("answer", "timeout", "stop"), n)]  # 3 + 6 + 6
FIRST_WINS = {"answer": ("answered", "continue"), "timeout": ("default applied (timeout)", "continue"),
              "stop": ("superseded (stop)", None)}


@pytest.mark.parametrize("order", ORDERS, ids="-".join)
def test_decision_resolves_exactly_once_in_every_order(order):  # R10-4, pure: every order on the functional core (S-7)
    core = getattr(engine, "_Decisions", None)
    assert core is not None, "design 6.2: the decision state machine is the functional core engine._Decisions"
    d = core(timeout=30)
    assert d.open("blocked_cell", "fake", "HB-CELL-202", now=0.0) == {
        "kind": "decision.opened", "decision_id": "D1", "decision_kind": "blocked_cell", "subject": "fake",
        "cause_code": "HB-CELL-202", "options": ["continue", "stop"], "default": "continue"}
    assert d.open("blocked_cell", "fake", "HB-CELL-202", now=1.0) is None  # at most once per (kind, subject, cause)
    assert d.answer("D9", "continue") == ("rejected (invalid)", None)
    assert d.answer("D1", "skip_combo") == ("rejected (invalid)", None)  # not an option this decision offers
    assert d.expire(now=29.9) == []
    rows, effects = [], []
    for step in order:
        if step == "answer":
            effect, row = d.answer("D1", "continue")
            effects.append(effect)
            rows += [row] if row else []
        elif step == "timeout":
            rows += d.expire(now=30.0)
        else:
            rows += d.supersede_all()
    state, option = FIRST_WINS[order[0]]
    assert rows == [{"kind": "decision.resolved", "decision_id": "D1", "state": state, "option": option}]
    assert effects == ([] if "answer" not in order else ["applied"] if order[0] == "answer" else ["rejected (already resolved)"])
    assert d.expire(now=1e6) == [] and d.supersede_all() == []
    assert d.answer("D1", "stop") == ("rejected (already resolved)", None)


AUTH = {"prompt_error": "Authentication required: run the login again"}  # driver: blocked (auth), HB-CELL-202
UNSERVED = {"prompt_error": "API Error: 400 the pinned model is not served"}  # normalize.classify: a 4xx, HB-CELL-116
CELL_TOKENS = 45  # the fake's USAGE over normalize.BUCKETS: 3 + 30 + 7 + 5 (reasoning is not a bucket)
JUMP = 31.0  # seconds added to the engine clock: past a 30 s decision_timeout, inside the 60 s cell budget


def _decision_plan(specs, parallelism, **parameters):
    """One cell per (harness, combo, fake behaviour), in launch order; decision_timeout is 30 s unless given."""
    p = _plan(n_cells=len(specs), parallelism=parallelism)
    p["parameters"].update({"decision_timeout": 30, **parameters})
    behaviours = {}
    for cell, (harness, combo, behaviour) in zip(p["cells"], specs, strict=True):
        cell["harness"], cell["combo"] = harness, combo
        behaviours[cell["label"]] = behaviour
    return p, FakeLauncher(behaviours)


def _answer_file(run_dir: Path, decision_id: str, option: str) -> Path:
    """An answer control file, written as `bench answer` writes it (design 4.2)."""
    uid = uuid.uuid4().hex
    return _stop_file(run_dir, uid=uid, body=json.dumps(_control(uid, control="answer", decision_id=decision_id, option=option)))


def _decision_run(base, plan_and_launcher, script=None, limit=45):
    """The engine on its own thread, its clock `time.monotonic() + offset[0]`, and `script(eng, offset, run_dir)` called
    in every tick after the controls and the expiry (design 6.2): each ordering is forced by the tick, never by a sleep."""
    p, launcher = plan_and_launcher
    offset = [0.0]
    run_dir = base / "runs" / p["run_id"]
    config = engine.EngineConfig(run_dir=run_dir, cells_root=base / "cells", launchers={"fake": launcher, "other": launcher},
                                 build_workspace=_build_workspace, grade=None, clock=lambda: time.monotonic() + offset[0])
    eng = engine.Engine(p, config)
    real_tick = eng.on_tick

    def tick():
        if script is not None:
            script(eng, offset, run_dir)
        real_tick()

    eng.on_tick = tick
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("summary", eng.run()), daemon=True, name="engine-under-test")
    thread.start()
    thread.join(limit)
    assert not thread.is_alive(), f"the engine did not finish within {limit} s"
    events = _events(run_dir)
    lifecycle.replay(events, parallelism=p["parameters"]["parallelism"])
    return eng, events, box["summary"]


def _kind(events: list[dict], kind: str) -> list[dict]:
    return [e for e in events if e["kind"] == kind]


def _resolutions(events: list[dict]) -> list[tuple]:
    return [(e["decision_id"], e["state"], e["option"]) for e in _kind(events, "decision.resolved")]


LOOP_ORDERS = {  # case -> step groups, one group per tick, from the tick in which the blocked cell's outcome lands
    "answer then timeout": (("answer",), ("timeout",)), "timeout then answer": (("timeout",), ("answer",)),
    "answer and timeout in one tick": (("answer", "timeout"),),
    "stop then timeout": (("stop",), ("timeout",)), "timeout then stop": (("timeout",), ("stop",))}
LOOP_EXPECTED = {  # case -> (decision.resolved rows, control.applied effects, cells launched)
    "answer then timeout": ([("D1", "answered", "continue")], ["applied"], 2),
    "timeout then answer": ([("D1", "default applied (timeout)", "continue")], ["rejected (already resolved)"], 2),
    "answer and timeout in one tick": ([("D1", "answered", "continue")], ["applied"], 2),  # controls run before the expiry
    "stop then timeout": ([("D1", "superseded (stop)", None)], ["applied"], 1),
    "timeout then stop": ([("D1", "default applied (timeout)", "continue")], ["applied"], 2)}


@pytest.mark.parametrize("case", sorted(LOOP_ORDERS))
def test_resolution_order_through_the_loop(base, case):  # R10-4, engine: the tick order of design 6.2 (TA M3)
    p, launcher = _decision_plan([("fake", "A", AUTH), ("fake", "A", {})], parallelism=1)
    blocked = p["cells"][0]["cell_id"]
    steps = list(LOOP_ORDERS[case])

    def script(eng, offset, run_dir):
        if blocked in eng.outcomes and steps:
            for step in steps.pop(0):
                if step == "timeout":
                    offset[0] += JUMP
                elif step == "stop":
                    _stop_file(run_dir)
                else:
                    _answer_file(run_dir, "D1", "continue")

    _, events, summary = _decision_run(base, (p, launcher), script)
    resolved, effects, launched = LOOP_EXPECTED[case]
    assert _resolutions(events) == resolved  # exactly one terminal state per decision
    assert [e["effect"] for e in _kind(events, "control.applied")] == effects
    assert len(_kind(events, "cell.launch_intent")) == launched
    assert summary.exit_code == (3 if "stop" in case else 0)


def test_a_stop_supersedes_every_open_decision(base):  # R10-2
    p, launcher = _decision_plan([("fake", "A", AUTH), ("other", "B", UNSERVED), ("fake", "A", {}), ("other", "B", {})],
                                 parallelism=2)
    first = {c["cell_id"] for c in p["cells"][:2]}
    fired = []

    def script(eng, offset, run_dir):
        if first <= set(eng.outcomes) and not fired:
            fired.append(True)
            _stop_file(run_dir)
            offset[0] += JUMP  # past the timeout in the same tick: the stop is applied first, then nothing expires

    _, events, summary = _decision_run(base, (p, launcher), script)
    assert sorted((e["decision_kind"], e["subject"]) for e in _kind(events, "decision.opened")) == [
        ("blocked_cell", "fake"), ("qualification_gap", "B")]
    assert sorted(_resolutions(events)) == [("D1", "superseded (stop)", None), ("D2", "superseded (stop)", None)]
    assert [(e["code"], e["decision_id"]) for e in _kind(events, "run.stopped")] == [("HB-RUN-006", None)]
    assert len(_kind(events, "cell.launch_intent")) == 2 and summary.exit_code == 3


def test_blocked_cell_default_continues_after_the_timeout(base):  # US15-1 (US-15, UXA-9)
    p, launcher = _decision_plan([("fake", "A", AUTH), ("other", "B", {"sleep": 2}), ("fake", "A", {})], parallelism=2)
    blocked, running, waiting = (c["cell_id"] for c in p["cells"])

    def script(eng, offset, run_dir):
        if {blocked, running} <= set(eng.outcomes) and not offset[0]:
            offset[0] += JUMP

    _, events, summary = _decision_run(base, (p, launcher), script)
    opened = _kind(events, "decision.opened")
    assert [{k: e[k] for k in ("decision_id", "decision_kind", "subject", "cause_code", "options", "default")} for e in opened] == [
        {"decision_id": "D1", "decision_kind": "blocked_cell", "subject": "fake", "cause_code": "HB-CELL-202",
         "options": ["continue", "stop"], "default": "continue"}]
    assert _resolutions(events) == [("D1", "default applied (timeout)", "continue")]
    start, end = events.index(opened[0]), events.index(_kind(events, "decision.resolved")[0])
    assert [e for e in events[start:end] if e["kind"] == "cell.launch_intent"] == []  # launching pauses while it is open
    assert running in [e["cell_id"] for e in events[start:end] if e["kind"] == "cell.outcome"]  # running cells continue
    assert [e["cell_id"] for e in events[end:] if e["kind"] == "cell.launch_intent"] == [waiting]  # launching resumes
    outs = _outcomes(events)
    assert (outs[blocked]["outcome"], outs[blocked]["cause"]) == ("failed", "blocked_auth")  # its outcome is unchanged
    assert outs[waiting]["outcome"] == "completed" and summary.exit_code == 0


def test_qualification_gap_default_skips_the_combos_pending_cells(base):  # US15-2
    p, launcher = _decision_plan([("fake", "A", UNSERVED), ("fake", "A", UNSERVED), ("fake", "A", {}), ("fake", "B", {})],
                                 parallelism=2)
    first, second, skipped, other = (c["cell_id"] for c in p["cells"])

    def script(eng, offset, run_dir):
        if {first, second} <= set(eng.outcomes) and not offset[0]:
            offset[0] += JUMP

    _, events, summary = _decision_run(base, (p, launcher), script)
    assert [(e["decision_kind"], e["subject"], e["cause_code"], e["options"], e["default"])
            for e in _kind(events, "decision.opened")] == [
        ("qualification_gap", "A", "HB-CELL-116", ["skip_combo", "stop"], "skip_combo")]  # the second gap opens none
    assert _resolutions(events) == [("D1", "default applied (timeout)", "skip_combo")]
    outs = _outcomes(events)
    assert {k: outs[skipped][k] for k in ("outcome", "cause", "code", "decision_id")} == {
        "outcome": "skipped (decision)", "cause": None, "code": None, "decision_id": "D1"}
    assert [e["kind"] for e in events if e.get("cell_id") == skipped] == ["cell.outcome"]  # never launched: its only row
    assert outs[other]["outcome"] == "completed" and summary.exit_code == 0


def test_spend_cap_default_stops_the_run(base):  # US15-3
    p, launcher = _decision_plan([("fake", "A", {}), ("fake", "A", {"mode": "on_cancel"}), ("fake", "A", {})], parallelism=2,
                                 spend_cap_tokens=CELL_TOKENS - 5)
    ended, running, waiting = (c["cell_id"] for c in p["cells"])

    def script(eng, offset, run_dir):
        if ended in eng.outcomes and not offset[0]:
            offset[0] += JUMP

    _, events, summary = _decision_run(base, (p, launcher), script)
    assert [{k: e[k] for k in ("decision_kind", "subject", "cause_code", "options", "default", "spend_tokens", "cells_unmeasured")}
            for e in _kind(events, "decision.opened")] == [
        {"decision_kind": "spend_cap", "subject": p["run_id"], "cause_code": "HB-RUN-007", "options": ["stop", "continue"],
         "default": "stop", "spend_tokens": 45, "cells_unmeasured": 0}]  # a literal from the fake's buckets (TA m2)
    assert _resolutions(events) == [("D1", "default applied (timeout)", "stop")]
    assert [(e["code"], e["decision_id"]) for e in _kind(events, "run.stopped")] == [("HB-RUN-007", "D1")]
    outs = _outcomes(events)
    assert outs[running]["outcome"] == "stopped" and waiting not in outs and summary.exit_code == 3


def test_a_cell_with_no_usage_is_unmeasured_never_zero(base):  # US15-3b (design 6.3)
    p, launcher = _decision_plan([("fake", "A", {"usage": None}), ("fake", "A", {}), ("fake", "A", {})], parallelism=1,
                                 spend_cap_tokens=CELL_TOKENS - 5, decision_timeout=0)
    _, events, summary = _decision_run(base, (p, launcher))
    assert [(e["spend_tokens"], e["cells_unmeasured"]) for e in _kind(events, "decision.opened")] == [(45, 1)]
    assert _resolutions(events) == [("D1", "default applied (timeout)", "stop")]
    assert len(_kind(events, "cell.launch_intent")) == 2 and summary.exit_code == 3


def test_no_decision_after_a_launch_stop(base):  # US15-4 (S-4, PE-13, TA M8)
    _, events, _ = _decision_run(base, _decision_plan([("fake", "A", AUTH), ("fake", "A", {})], parallelism=1,
                                                      decision_timeout=0))
    assert [e["decision_kind"] for e in _kind(events, "decision.opened")] == ["blocked_cell"]  # the positive control
    _, events, _ = _decision_run(base, _decision_plan([("fake", "A", AUTH)], parallelism=1, decision_timeout=0))
    assert _kind(events, "decision.opened") == []  # nothing pending: nothing it could change
    p, launcher = _decision_plan([("fake", "A", {**UNSERVED, "sleep": 8}), *[("fake", "B", {"mode": "provider_error"})] * 3,
                                  ("fake", "A", {})], parallelism=2, decision_timeout=0)
    _, events, _ = _decision_run(base, (p, launcher))
    assert [e["code"] for e in _kind(events, "run.launch_stopped")] == ["HB-CELL-108"]  # the breaker, first
    assert _outcomes(events)[p["cells"][0]["cell_id"]]["cause"] == "model_unavailable"  # then the gap, combo A pending
    assert _kind(events, "decision.opened") == []


def test_the_run_waits_for_an_open_decision(base):  # US15-5 (UXA-9; the model's DecisionEventuallyResolved)
    p, launcher = _decision_plan([("fake", "A", {}), ("fake", "A", {"sleep": 2})], parallelism=2,
                                 spend_cap_tokens=CELL_TOKENS - 5)
    cells = {c["cell_id"] for c in p["cells"]}
    idle = []

    def script(eng, offset, run_dir):
        if cells <= set(eng.outcomes) and not eng.active:
            idle.append(True)
            if len(idle) == 3:  # three ticks with nothing pending or running: only the open decision holds the loop
                _answer_file(run_dir, "D1", "continue")

    _, events, summary = _decision_run(base, (p, launcher), script)
    assert len(idle) >= 3
    assert _resolutions(events) == [("D1", "answered", "continue")]
    last_outcome = max(events.index(e) for e in _kind(events, "cell.outcome"))
    assert last_outcome < events.index(_kind(events, "decision.resolved")[0]) < events.index(_kind(events, "run.completed")[0])
    assert summary.exit_code == 0


def test_one_blocked_harness_opens_one_decision(base):  # US15-6 (PE-4): one expired login costs one wait, not N
    p, launcher = _decision_plan([("fake", "A", AUTH)] * 3 + [("fake", "A", {})], parallelism=3, decision_timeout=0)
    _, events, summary = _decision_run(base, (p, launcher))
    assert [(e["decision_id"], e["subject"]) for e in _kind(events, "decision.opened")] == [("D1", "fake")]
    assert _resolutions(events) == [("D1", "default applied (timeout)", "continue")] and summary.exit_code == 0
    assert sorted(str(o["cause"]) for o in _outcomes(events).values()) == ["None"] + ["blocked_auth"] * 3


def test_an_answer_of_stop_is_an_operator_stop(base):  # US15-7 (design 6.1)
    p, launcher = _decision_plan([("fake", "A", AUTH), ("other", "B", {"mode": "on_cancel"}), ("fake", "A", {})],
                                 parallelism=2)
    blocked, running, waiting = (c["cell_id"] for c in p["cells"])
    sent = []

    def script(eng, offset, run_dir):
        if blocked in eng.outcomes and not sent:
            sent.append(_answer_file(run_dir, "D1", "stop"))

    _, events, summary = _decision_run(base, (p, launcher), script)
    assert [(e["control"], e["decision_id"], e["effect"]) for e in _kind(events, "control.applied")] == [
        ("answer", "D1", "applied")]
    assert _resolutions(events) == [("D1", "answered", "stop")]
    assert [(e["code"], e["decision_id"]) for e in _kind(events, "run.stopped")] == [("HB-RUN-006", "D1")]
    outs = _outcomes(events)
    assert outs[running]["outcome"] == "stopped" and waiting not in outs and summary.exit_code == 3


def test_continue_on_the_spend_cap_disables_the_cap(base):  # US15-7 (design 6.1)
    p, launcher = _decision_plan([("fake", "A", {})] * 3, parallelism=1, spend_cap_tokens=CELL_TOKENS - 5)
    first = p["cells"][0]["cell_id"]
    sent = []

    def script(eng, offset, run_dir):
        if first in eng.outcomes and not sent:
            sent.append(_answer_file(run_dir, "D1", "continue"))

    eng, events, summary = _decision_run(base, (p, launcher), script)
    assert _resolutions(events) == [("D1", "answered", "continue")]
    assert [o["outcome"] for o in _outcomes(events).values()] == ["completed"] * 3
    assert _kind(events, "run.stopped") == [] and summary.exit_code == 0
    assert eng.spend_cap is None  # disabled for the rest of the run: 135 tokens spent against a 40-token cap
