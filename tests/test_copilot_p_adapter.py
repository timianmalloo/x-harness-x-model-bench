"""ADR-0028 s1-s4: the copilot -p ACP adapter, driven by the bench's own driver against a fake `copilot` exe.

The engine's process is the adapter: one process per attempt, one `copilot -p` child per prompt (`--session-id`, then
`--resume` with the same id), so `lifecycle.replay` holds for a multi-turn cell (gate veto A).
"""

import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from test_engine import FakeLauncher, _plan, _run

from harness_bench import driver, engine, procs

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "bench" / "adapters" / "copilot_p_acp.py"
PIN = ROOT / "bench" / "adapters" / "copilot_p_acp.pin.json"
FIX = Path(__file__).parent / "fixtures" / "copilot-p"
FAKE = FIX / "fake_copilot.py"
PASS = ["--output-format", "json", "--model", "gpt-6.1-sol", "--available-tools", "view", "glob"]


def _spawn(tmp_path: Path, **cfg) -> tuple[procs.CellProcess, Path, Path, Path]:
    home, ws = tmp_path / "home", tmp_path / "ws"
    home.mkdir()
    ws.mkdir()
    log = tmp_path / "children.jsonl"
    env = dict(os.environ, COPILOT_HOME=str(home), FAKE_COPILOT=json.dumps({"log": str(log), **cfg}))
    cp = procs.spawn([sys.executable, str(ADAPTER), "--exe", sys.executable, str(FAKE), "--", *PASS], ws, env)
    return cp, home, ws, log


def _children(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def _turns(cp, ws, prompts, cancel=None):
    session = driver.open_session(cp, ws, None, 30, cancel=cancel)
    assert session is not None, f"handshake failed: {session}"
    alive = []
    recs = []
    for n, text in enumerate(prompts, 1):
        recs.append(driver.send_turn(session, text, lambda sid: None, n))
        alive.append(cp.proc.poll() is None)
    return session, recs, alive


def test_two_prompts_are_two_children_on_one_session_in_one_adapter_process(tmp_path):
    cp, _, ws, log = _spawn(tmp_path)
    try:
        session, (r1, r2), alive = _turns(cp, ws, ["turn one", "turn two"])
    finally:
        cp.terminate_and_confirm(10)
        cp.close()
    sid = session.result.session_id
    kids = _children(log)
    assert len(kids) == 2, kids
    assert kids[0]["argv"] == ["-p", "turn one", "--session-id", sid, *PASS]
    assert kids[1]["argv"] == ["-p", "turn two", "--resume", sid, *PASS]
    assert str(uuid.UUID(sid)) == sid
    assert alive == [True, True], "one engine-side process, the adapter, outlives both children"
    assert (r1.stop_reason, r2.stop_reason) == ("end_turn", "end_turn")
    assert session.result.agent_version == "1.0.89-1", "agentInfo.version is the Copilot build's own self-report"


def test_session_cancel_kills_the_child_and_answers_cancelled(tmp_path):
    cancel = threading.Event()
    cp, _, ws, log = _spawn(tmp_path, mode="hang")

    def cancel_once_the_child_runs():
        deadline = time.monotonic() + 30
        while not _children(log) and time.monotonic() < deadline:
            time.sleep(0.05)
        cancel.set()

    threading.Thread(target=cancel_once_the_child_runs, daemon=True).start()
    try:
        _, (rec,), _ = _turns(cp, ws, ["hang"], cancel=cancel)
        assert rec is not None and rec.stop_reason == "cancelled"
        assert rec.turn_seconds < 30, "the child was killed, not waited out"
        child = _children(log)[0]["pid"]
        assert child not in cp.job.pids(), "the cancelled child is gone"
    finally:
        cp.terminate_and_confirm(10)
        cp.close()


@pytest.mark.parametrize("mode", ["fail", "noresult"])
def test_a_child_that_fails_or_ends_without_a_result_is_not_end_turn(tmp_path, mode):
    cp, _, ws, _ = _spawn(tmp_path, mode=mode)
    try:
        _, (rec,), _ = _turns(cp, ws, ["x"])
    finally:
        cp.terminate_and_confirm(10)
        cp.close()
    assert rec is not None and rec.stop_reason != "end_turn"
    assert rec.stop_reason not in engine.COMPLETED_STOP_REASONS, "the engine classifies it, never as completed"


@pytest.mark.parametrize(("mode", "usage"), [
    ("replay", None),  # 1.0.89-1's final object: premiumRequests and durations, no tokens (spike q1, q3)
    ("tokens", {"inputTokens": 11, "outputTokens": 2, "cachedReadTokens": 5, "cachedWriteTokens": 0}),
])
def test_usage_comes_from_the_final_object_only_when_it_carries_tokens(tmp_path, mode, usage):
    cp, _, ws, _ = _spawn(tmp_path, mode=mode)
    try:
        _, (rec,), _ = _turns(cp, ws, ["x"])
    finally:
        cp.terminate_and_confirm(10)
        cp.close()
    assert rec.stop_reason == "end_turn"
    got = (rec.usage or {}).get("usage")
    assert (got and {k: got[k] for k in usage}) == usage if usage else got is None, rec.usage


class _Raw:
    """The adapter's stdio without the driver, so the test sees the exact bytes it writes."""

    def __init__(self, cp):
        self.cp, self.seen, self.n = cp, b"", 0

    def call(self, method, params):
        self.n += 1
        self.cp.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
                                 .encode("utf-8") + b"\n")
        self.cp.proc.stdin.flush()
        while True:
            line = self.cp.proc.stdout.readline()
            assert line, "the adapter closed its stdout"
            self.seen += line
            msg = json.loads(line.decode("utf-8"))
            if msg.get("id") == self.n:
                return msg["result"]


def test_stdout_is_utf8_with_lf_and_each_turn_is_teed_unchanged(tmp_path):
    cp, home, ws, _ = _spawn(tmp_path)
    raw = _Raw(cp)
    try:
        raw.call("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
        sid = raw.call("session/new", {"cwd": str(ws), "mcpServers": []})["sessionId"]
        for text in ("one", "two"):
            assert raw.call("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}) \
                ["stopReason"] == "end_turn"
    finally:
        cp.terminate_and_confirm(10)
        cp.close()
    assert b"\r" not in raw.seen and raw.seen.endswith(b"\n")
    for line in raw.seen.splitlines():
        json.loads(line.decode("utf-8"))  # strict UTF-8, one JSON object per line
    assert (home / "copilot-p-turn1.jsonl").read_bytes() == (FIX / "turn1-stdout.jsonl").read_bytes()
    assert (home / "copilot-p-turn2.jsonl").read_bytes() == (FIX / "turn2-resume-stdout.jsonl").read_bytes()


def test_the_pin_file_names_the_adapter_its_version_and_its_sha256():
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("copilot_p_acp", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert pin == {"path": "bench/adapters/copilot_p_acp.py", "version": module.VERSION,
                   "sha256": hashlib.sha256(ADAPTER.read_bytes()).hexdigest()}


class AdapterLauncher(FakeLauncher):
    """The engine's fake launcher, but the cell process is the copilot -p adapter over the fake copilot exe."""

    usage_source = "native_record"

    def __init__(self, log: Path):
        super().__init__({})
        self.log = log  # outside the cell dir, which the engine deletes after archiving

    def argv_env(self, cell, home, traceparent):
        cfg = {"log": str(self.log)}
        env = dict(os.environ, COPILOT_HOME=str(home), FAKE_COPILOT=json.dumps(cfg), TRACEPARENT=traceparent)
        return [sys.executable, str(ADAPTER), "--exe", sys.executable, str(FAKE), "--", *PASS], env

    def records(self, home, session_id):
        return []


def test_an_engine_two_turn_cell_through_the_adapter_passes_lifecycle_replay(base):  # gate veto A
    p = _plan(n_cells=1, parallelism=1)
    p["tasks"]["X1"]["turns"] = [{"n": 2, "prompt": "Repair it.\n",
                                  "sha256": hashlib.sha256(b"Repair it.\n").hexdigest()}]
    _, events, _ = _run(base, p, AdapterLauncher(base / "children.jsonl"))  # _run replays them (lifecycle.replay)
    kinds = [e["kind"] for e in events]
    assert kinds.count("attempt.process_started") == 1 and kinds.count("attempt.process_ended") == 1
    ended = [e for e in events if e["kind"] == "cell.turn_ended"]
    assert [(e["turn"], e["stop_reason"], e["next"]) for e in ended] == [(1, "end_turn", "snapshot"),
                                                                       (2, "end_turn", "final")]
    kids = _children(base / "children.jsonl")
    opened = next(e for e in events if e["kind"] == "attempt.session_opened")
    assert [k["argv"][2:4] for k in kids] == [["--session-id", opened["session_id"]], ["--resume", opened["session_id"]]]
