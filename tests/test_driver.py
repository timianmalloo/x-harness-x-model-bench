"""The ACP cell driver (ADR-0002; design: driver.py): bounded reader, strict parse, deny-all permissions,
verbatim prompt, ack barrier, handshake deadline."""

import json
import os
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench import driver, procs
from harness_bench.errors import Cause
from harness_bench.telemetry import normalize

FAKE = Path(__file__).parent / "fake_acp_agent.py"


def _spawn(tmp_path, fake="ok", **cfg):
    env = dict(os.environ, FAKE_ACP=json.dumps({"mode": fake, **cfg}))
    return procs.spawn([sys.executable, str(FAKE)], cwd=str(tmp_path), env=env)


def _turn(tmp_path, prompt="Do the task.", before_send=None, acp_mode=None, handshake=10, fake="ok", **cfg):
    cell = _spawn(tmp_path, fake=fake, **cfg)
    try:
        return driver.run_turn(cell, cwd=tmp_path, prompt=prompt, mode=acp_mode, handshake_timeout=handshake,
                               before_send=before_send or (lambda sid: None))
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()


# the line reader: bounded, never crashes (D2) ------------------------------------------------

_NESTED = st.integers(min_value=1, max_value=120_000).flatmap(
    lambda n: st.sampled_from([b"[" * n, b'{"a":' * n, b"[" * n + b"]" * n])).map(lambda b: b + b"\n")
_CHUNK = st.one_of(st.binary(max_size=600), _NESTED, st.sampled_from([b"\n", b'{"a":1}\n', b"x" * 300, b"[1]\n"]))


@settings(max_examples=200, deadline=None)
@given(st.sampled_from([16, 256, 1 << 18]), st.lists(_CHUNK, max_size=12))
def test_line_reader_never_crashes_and_stays_bounded(max_line, chunks):  # D2
    """Any bytes in any chunking: only messages (dicts) or ProtocolError come out, and the buffer never
    holds more than one line, including after the error."""
    reader = driver.LineParser(max_line=max_line, max_junk=20)
    for chunk in chunks:
        try:
            for msg in reader.feed(chunk):
                assert isinstance(msg, dict)
        except driver.ProtocolError:
            assert len(reader._buf) <= max_line
            return
        assert len(reader._buf) <= max_line


@pytest.mark.parametrize("line", [b"[" * 100_000, b'{"a":' * 100_000], ids=["list", "object"])
def test_a_deeply_nested_line_is_junk_never_a_crash(line):  # D2: 100,000-deep nesting
    reader = driver.LineParser()
    assert list(reader.feed(line + b"\n" + b'{"ok":1}\n')) == [{"ok": 1}]
    assert reader.junk == 1


def test_line_reader_rejects_an_oversized_line():
    reader = driver.LineParser(max_line=16, max_junk=20)
    with pytest.raises(driver.ProtocolError):
        list(reader.feed(b"x" * 40))


def test_line_reader_tolerates_a_few_junk_lines_then_fails():
    reader = driver.LineParser(max_line=1024, max_junk=2)
    assert list(reader.feed(b"banner\n{\"a\":1}\nnoise\n")) == [{"a": 1}]
    with pytest.raises(driver.ProtocolError):
        list(reader.feed(b"more junk\n"))


# turns against the fake agent (native: real processes in jobs) --------------------------------

pytestmark_native = pytest.mark.native


@pytestmark_native
def test_happy_turn_delivers_the_prompt_verbatim_and_ends_the_turn(tmp_path):
    prompt = "Implement slugify.\r\nKeep the signature.  \n"
    result = _turn(tmp_path, prompt=prompt, write_file="out.txt")
    assert result.stop_reason == "end_turn" and result.cause is None
    assert result.session_id and result.permission_requests == 0 and result.updates >= 1
    assert (tmp_path / ".fake-prompt.txt").read_bytes().decode("utf-8") == prompt  # byte-exact, CRLF kept
    assert result.prompt_sent


@pytestmark_native
def test_ack_barrier_failure_means_the_prompt_is_never_sent(tmp_path):  # T-ENG-ack (driver half)
    def refuse(sid):
        raise OSError("HB-RUN-001: append failed")

    with pytest.raises(OSError):
        _turn(tmp_path, before_send=refuse)
    assert not (tmp_path / ".fake-prompt.txt").exists()


@pytestmark_native
def test_permission_requests_are_refused_and_counted(tmp_path):
    result = _turn(tmp_path, fake="permission")
    assert result.permission_requests == 1
    reply = json.loads((tmp_path / ".fake-permission-reply.json").read_text(encoding="utf-8"))
    assert reply["result"] == {"outcome": {"outcome": "cancelled"}}


@pytestmark_native
def test_eof_before_end_turn_is_an_adapter_crash(tmp_path):
    result = _turn(tmp_path, fake="eof_mid_turn")
    assert result.cause is Cause.adapter_crash and result.prompt_sent


@pytestmark_native
def test_exit_before_prompt_is_an_adapter_crash_with_no_prompt(tmp_path):
    result = _turn(tmp_path, fake="exit_before_prompt")
    assert result.cause is Cause.adapter_crash and not result.prompt_sent


@pytestmark_native
def test_junk_lines_are_a_protocol_failure(tmp_path):  # T-DRV-junk
    result = _turn(tmp_path, fake="junk_lines")
    assert result.cause is Cause.protocol and "non-JSON" in result.detail


@pytestmark_native
def test_a_huge_line_is_a_protocol_failure(tmp_path):
    result = _turn(tmp_path, fake="huge_line")
    assert result.cause is Cause.protocol and "1 MiB" in result.detail


@pytestmark_native
def test_a_hung_handshake_times_out(tmp_path):
    result = _turn(tmp_path, handshake=2, fake="hang_handshake")
    assert result.cause is Cause.handshake_timeout and not result.prompt_sent


@pytestmark_native
def test_the_profile_mode_is_set_before_the_prompt(tmp_path):
    result = _turn(tmp_path, acp_mode="agent-full-access")
    assert result.stop_reason == "end_turn"
    assert json.loads((tmp_path / ".fake-set_mode").read_text(encoding="utf-8"))["modeId"] == "agent-full-access"


@pytestmark_native
def test_a_killed_turn_returns_promptly_with_eof(tmp_path):
    import threading
    cell = _spawn(tmp_path, fake="hang_prompt")
    timer = threading.Timer(1.5, lambda: cell.terminate_and_confirm(timeout=10))
    timer.start()
    result = driver.run_turn(cell, cwd=tmp_path, prompt="p", mode=None, handshake_timeout=10, before_send=lambda sid: None)
    timer.join()
    cell.close()
    assert result.prompt_sent and result.stop_reason is None and result.eof


# D5: recorded adapter output replayed through the driver ------------------------------------------

ACP_FIX = Path(__file__).parent / "fixtures" / "acp"
REPLAY = ACP_FIX / "replay_agent.py"
RECORDED = sorted(p for p in ACP_FIX.glob("*.json") if p.name != "provenance.json")
RECORDINGS = sorted((ACP_FIX / "recordings").glob("*.jsonl"))  # full ACP transcripts (tools/acp_record.py)
PROVENANCE_KEYS = ("adapter", "adapter_version", "harness_version", "captured", "scrub", "source")
X1_PROMPT = (Path(__file__).parents[1] / "tasks" / "X1" / "prompt.md").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


def _records(recording: Path) -> list[dict]:
    return [json.loads(line) for line in recording.read_text(encoding="utf-8").splitlines()]


def _stream(records: list[dict], direction: str) -> bytes:
    """The bytes one direction carried (the acp-recording/1 line records, rebuilt)."""
    import base64
    return b"".join((r["text"].encode("utf-8") if "text" in r else base64.b64decode(r["b64"])) + (b"\n" if r["nl"] else b"")
                    for r in records if r["kind"] == "line" and r["dir"] == direction)


def _derive(recording: Path, tmp_path: Path, edit) -> Path:
    """A derived copy: `edit(msg)` returns the agent message to keep (changed or not), a list to insert, or None to drop."""
    out = []
    for r in _records(recording):
        if r["kind"] == "line" and r["dir"] == "to_client":
            kept = edit(json.loads(r["text"]))
            for msg in kept if isinstance(kept, list) else [] if kept is None else [kept]:
                out.append({**r, "text": json.dumps(msg, ensure_ascii=False, separators=(",", ":"))})
        else:
            out.append(r)
    path = tmp_path / f"derived-{recording.name}"
    path.write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    return path


def _replay(tmp_path, recording: Path, mode: str | None = None):
    """The driver against a verbatim replay of a recording, both pipes tapped: (TurnResult, read, written)."""
    env = dict(os.environ, REPLAY_ACP=json.dumps({"recording": str(recording)}))
    cell = procs.spawn([sys.executable, str(REPLAY)], cwd=str(tmp_path), env=env)
    cell.proc.stdout, cell.proc.stdin = _Tap(cell.proc.stdout), _Tap(cell.proc.stdin)
    try:
        result = driver.run_turn(cell, cwd=tmp_path, prompt=X1_PROMPT, mode=mode, handshake_timeout=10,
                                 before_send=lambda sid: None)
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    return result, bytes(cell.proc.stdout.data), bytes(cell.proc.stdin.data)


def _meta(recording: Path) -> dict:
    return json.loads(recording.with_suffix(".meta.json").read_text(encoding="utf-8"))


def _prompt_reply(records: list[dict]) -> dict:
    return [m for m in map(json.loads, _stream(records, "to_client").splitlines()) if "id" in m and "method" not in m][-1]


def _assert_replays(tmp_path, recording: Path) -> None:
    """D5: the driver reads every recorded agent byte, writes what it wrote live, and returns the live TurnResult."""
    meta, records = _meta(recording), _records(recording)
    result, read, written = _replay(tmp_path, recording, meta["mode"])
    assert read == _stream(records, "to_client")  # every agent line, verbatim, nothing synthesised
    cwd = json.dumps(str(tmp_path))[1:-1].encode()
    assert written == _stream(records, "to_agent").replace(b"<CWD>", cwd)  # the driver still sends the live bytes
    live = meta["result"]
    assert (result.stop_reason, result.cause.code if result.cause else None, result.session_id, result.updates,
            result.permission_requests, result.prompt_sent, result.usage is not None) == (
        live["stop_reason"], live["cause"], live["session_id"], live["updates"], live["permission_requests"],
        live["prompt_sent"], live["usage_reported"])


def test_every_recorded_acp_fixture_states_its_provenance():  # D5: adapter version, capture date, scrub
    provenance = json.loads((ACP_FIX / "provenance.json").read_text(encoding="utf-8"))["fixtures"]
    assert RECORDED and {p.name for p in RECORDED} == set(provenance)
    for name, record in provenance.items():
        assert all(isinstance(record.get(k), str) and record[k].strip() for k in PROVENANCE_KEYS), name


@pytestmark_native
@pytest.mark.parametrize("recording", RECORDINGS, ids=[p.stem for p in RECORDINGS])
def test_a_recorded_transcript_replays_verbatim_through_the_driver(tmp_path, recording):  # D5
    _assert_replays(tmp_path, recording)


@pytestmark_native
@pytest.mark.parametrize("name", ["claude-code-x1.jsonl", "codex-x1.jsonl"])
def test_the_recorded_usage_reaches_the_engine_unchanged(tmp_path, name):  # D5, the usage half
    recording = ACP_FIX / "recordings" / name
    recorded = _prompt_reply(_records(recording))["result"]
    result, _, _ = _replay(tmp_path, recording, _meta(recording)["mode"])
    assert result.usage == {"usage": recorded["usage"], "meta": recorded["_meta"]}
    # the engine's reading of the driver's result is the reading of the recorded bytes
    assert normalize.turn_usage({"_meta": result.usage["meta"]}) == normalize.turn_usage(recorded) != []


@pytestmark_native
def test_meta_is_kept_when_the_adapter_reports_no_usage(tmp_path):  # derived variant: the codex result without `usage`
    recording = ACP_FIX / "recordings" / "codex-x1.jsonl"
    recorded = _prompt_reply(_records(recording))["result"]

    def drop_usage(msg):
        if msg.get("result", {}).get("stopReason"):
            msg["result"].pop("usage")
        return msg

    result, _, _ = _replay(tmp_path, _derive(recording, tmp_path, drop_usage), "agent-full-access")
    assert result.usage == {"usage": None, "meta": recorded["_meta"]}  # the TurnResult.usage shape is unchanged


# D7: every message type the fake emits is paired with a real transcript or the ACP schema ------

PAIRING = {
    # type: evidence (a recorded real transcript from the spikes, or the ACP schema)
    "initialize.result": "spike N4: real initialize results from claude-agent-acp, codex-acp, copilot --acp",
    "session/new.result": "spike N4: real session/new results (sessionId, modes.availableModes)",
    "session/set_mode.result": "spike N4: codex-acp set_mode agent-full-access returned {}",
    "session/update.agent_message_chunk": "spike R11 container_acp.py counted real session/update notifications",
    "session/prompt.result": "recorded: tests/fixtures/acp/*-prompt-response.json, replayed through the driver (D5)",
    "session/request_permission": "ACP schema (agentclientprotocol.com, RequestPermissionRequest); no real exemplar yet - "
                                  "flagged for the phase-2 permission probe",
}


class _Tap:
    """One side of the adapter's stdio, passed through unchanged and recorded."""

    def __init__(self, stream) -> None:
        self.stream, self.data = stream, bytearray()

    def read1(self, n: int) -> bytes:
        chunk = self.stream.read1(n)
        self.data += chunk
        return chunk

    def write(self, data: bytes) -> int:
        self.data += data
        return self.stream.write(data)

    def flush(self) -> None:
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


def _objects(data: bytes) -> list[dict]:
    out = []
    for line in data.split(b"\n"):
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _message_types(agent: bytes, client: bytes) -> set[str]:
    """Each agent message as `method[.sessionUpdate]` or `<the client request's method>.result|error`."""
    asked = {m["id"]: m["method"] for m in _objects(client) if "method" in m and "id" in m}
    types = set()
    for m in _objects(agent):
        if "method" in m:
            update = (m.get("params") or {}).get("update") or {}
            types.add(m["method"] + (f".{update['sessionUpdate']}" if "sessionUpdate" in update else ""))
        elif "id" in m:
            types.add(f"{asked.get(m['id'], '?')}.{'error' if 'error' in m else 'result'}")
    return types


def _tapped_turn(tmp_path, argv, env, acp_mode=None) -> set[str]:
    import threading
    cell = procs.spawn(argv, cwd=str(tmp_path), env=env)
    cell.proc.stdout, cell.proc.stdin = _Tap(cell.proc.stdout), _Tap(cell.proc.stdin)
    stop = threading.Timer(4, lambda: cell.terminate_and_confirm(timeout=10))  # ends the hang modes
    stop.start()
    try:
        driver.run_turn(cell, cwd=tmp_path, prompt="p", mode=acp_mode, handshake_timeout=3, before_send=lambda sid: None)
    finally:
        stop.cancel()
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    return _message_types(bytes(cell.proc.stdout.data), bytes(cell.proc.stdin.data))


def _fake_modes() -> list[str]:
    """Every mode the fake agent declares in its docstring, so a new mode is exercised without editing this test."""
    import re
    doc = FAKE.read_text(encoding="utf-8").split('"mode":', 1)[1].split('"record_dir"', 1)[0]
    return re.findall(r'"(\w+)"', doc)


def _assert_paired(emitted: set[str]) -> None:
    unpaired = emitted - set(PAIRING)
    assert not unpaired, f"message types with no real transcript or schema: {sorted(unpaired)}"


@pytestmark_native
def test_every_message_type_the_fake_emits_is_paired_and_every_pairing_is_emitted(tmp_path):  # D7
    from concurrent.futures import ThreadPoolExecutor
    modes = _fake_modes()
    assert {"ok", "permission", "eof_mid_turn"} <= set(modes)
    env = {m: dict(os.environ, FAKE_ACP=json.dumps({"mode": m, "usage": [{"model": "m", "token_count": {}}]})) for m in modes}
    for m in modes:
        (tmp_path / m).mkdir()
    with ThreadPoolExecutor(max_workers=len(modes)) as pool:
        runs = [pool.submit(_tapped_turn, tmp_path / m, [sys.executable, str(FAKE)], env[m], "agent-full-access") for m in modes]
        emitted = set().union(*(r.result() for r in runs))
    _assert_paired(emitted)
    stale = set(PAIRING) - emitted
    assert not stale, f"pairings no real run of the fake emits: {sorted(stale)}"


@pytestmark_native
def test_the_fidelity_check_fails_on_a_seeded_unpaired_type(tmp_path):  # D7 negative control, through a real run
    seed = {"jsonrpc": "2.0", "method": "session/update",
            "params": {"sessionId": "replay-session", "update": {"sessionUpdate": "plan", "entries": []}}}

    def seed_before_result(msg):
        return [seed, msg] if msg.get("result", {}).get("stopReason") else msg

    recording = _derive(ACP_FIX / "recordings" / "claude-code-x1.jsonl", tmp_path, seed_before_result)
    env = dict(os.environ, REPLAY_ACP=json.dumps({"recording": str(recording)}))
    emitted = _tapped_turn(tmp_path, [sys.executable, str(REPLAY)], env)
    assert "session/update.plan" in emitted
    with pytest.raises(AssertionError, match=r"session/update\.plan"):
        _assert_paired(emitted)


def test_run_turn_has_no_model_switch():  # Simplifier minor: no caller passes model=, so no session/set_model path
    import inspect
    assert "model" not in inspect.signature(driver.run_turn).parameters
    assert "session/set_model" not in Path(driver.__file__).read_text(encoding="utf-8")
