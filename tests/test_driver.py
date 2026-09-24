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
    live = dict(meta["result"])
    if recording.name in RECLASSIFIED:  # a cause a ruling changed since the capture: the capture's own value first
        captured, live["cause"] = RECLASSIFIED[recording.name]
        assert meta["result"]["cause"] == captured
    assert (result.stop_reason, result.cause.code if result.cause else None, result.session_id, result.updates,
            result.permission_requests, result.prompt_sent, result.usage is not None) == (
        live["stop_reason"], live["cause"], live["session_id"], live["updates"], live["permission_requests"],
        live["prompt_sent"], live["usage_reported"])


UNSUPPORTED = ACP_FIX / "recordings" / "claude-code-x1-model-unsupported.jsonl"
RECLASSIFIED = {UNSUPPORTED.name: ("HB-CELL-105", "HB-CELL-116")}  # R-18/R-23: capture-time cause -> today's


@pytestmark_native
def test_a_model_the_harness_refuses_at_the_prompt_is_model_unavailable(tmp_path):  # R-18, R-23: the measured w1 record
    result, _, _ = _replay(tmp_path, UNSUPPORTED)
    assert result.cause is Cause.model_unavailable and result.prompt_sent
    assert "2.1.280 or newer is required" in result.detail  # the adapter's text stays in the detail


@pytestmark_native
@pytest.mark.parametrize(("message", "data", "cause"), [
    ("Internal error: API Error: 529 overloaded", {"errorKind": "overloaded_error"}, Cause.provider),
    ("Internal error: API Error: 429 rate limited", None, Cause.provider),
    ("Internal error: API Error: 401 Invalid credentials. Please run /login", {"errorKind": "authentication_error"},
     Cause.blocked_auth),
    ("Internal error: something broke", None, Cause.adapter_crash),  # no status, no type: never 116 by guess
    # Codex cross-vendor review F2: a status decides before the broad `api_error` type
    ("Internal error: API Error: 400 bad model", {"errorKind": "api_error"}, Cause.model_unavailable),
    ("Internal error: overloaded", {"errorKind": "overloaded_error"}, Cause.provider),  # no status: the type decides
], ids=["overloaded", "rate-limit", "auth", "no-status-no-type", "4xx-with-api_error-type", "overload-type-no-status"])
def test_a_prompt_error_is_classified_by_its_status_and_type(tmp_path, message, data, cause):  # R-23
    error = {"code": -32603, "message": message, **({"data": data} if data else {})}
    derived = _derive(UNSUPPORTED, tmp_path, lambda m: {**m, "error": error} if "error" in m else m)
    result, _, _ = _replay(tmp_path, derived)
    assert result.cause is cause and message in result.detail


@pytestmark_native
def test_the_prompt_error_path_calls_the_native_record_classifier(tmp_path, monkeypatch):  # R-23 condition 1
    from harness_bench.telemetry import ProviderError
    real, seen = normalize.classify, []

    def spy(errors):
        seen.append(errors)
        return real(errors)

    monkeypatch.setattr(normalize, "classify", spy)
    result, _, _ = _replay(tmp_path, UNSUPPORTED)
    assert seen and result.cause is real(seen[-1]) is Cause.model_unavailable
    # the same refusal as a native record row (status 400, an invalid-request type) reads the same cause
    assert real([ProviderError(0, 400, "invalid_request", "does not support this model")]) is result.cause


def test_every_recorded_acp_fixture_states_its_provenance():  # D5: adapter version, capture date, scrub
    provenance = json.loads((ACP_FIX / "provenance.json").read_text(encoding="utf-8"))["fixtures"]
    assert RECORDED and RECORDINGS
    assert {p.name for p in RECORDED} | {f"recordings/{p.name}" for p in RECORDINGS} == set(provenance)
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


@pytestmark_native
def test_d5_fails_when_one_byte_of_a_recorded_session_new_result_changes(tmp_path):  # D5 negative control (W1-ACP d)
    import shutil
    recording = ACP_FIX / "recordings" / "codex-x1.jsonl"
    lines = recording.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next(i for i, line in enumerate(lines) if '\\"id\\":2,\\"result\\":{\\"sessionId\\":\\"' in line)
    at = lines[i].index('sessionId\\":\\"') + len('sessionId\\":\\"')
    lines[i] = lines[i][:at] + ("f" if lines[i][at] != "f" else "e") + lines[i][at + 1:]
    mutated = tmp_path / "mutated" / recording.name
    mutated.parent.mkdir()
    mutated.write_text("".join(lines), encoding="utf-8", newline="")
    shutil.copyfile(recording.with_suffix(".meta.json"), mutated.with_suffix(".meta.json"))
    original, changed = recording.read_bytes(), mutated.read_bytes()
    assert len(original) == len(changed) and sum(a != b for a, b in zip(original, changed, strict=True)) == 1
    for cwd in ("control", "mutant"):
        (tmp_path / cwd).mkdir()
    _assert_replays(tmp_path / "control", recording)  # the unmutated recording passes, so the failure below is the byte
    with pytest.raises(AssertionError):
        _assert_replays(tmp_path / "mutant", mutated)


@pytestmark_native
def test_last_update_is_the_turn_time_of_the_last_session_update(tmp_path):  # W1-ACP (f), seam req-01M38KX8
    recording = ACP_FIX / "recordings" / "claude-code-x1.jsonl"
    result, _, _ = _replay(tmp_path, recording, None)
    assert result.updates == _meta(recording)["result"]["updates"] > 0
    assert result.last_update_seconds is not None and 0 <= result.last_update_seconds <= result.turn_seconds


@pytestmark_native
def test_last_update_is_null_never_zero_with_no_session_update(tmp_path):  # W1-ACP (f)
    def no_updates(msg):
        return None if msg.get("method") == "session/update" else msg

    result, _, _ = _replay(tmp_path, _derive(ACP_FIX / "recordings" / "claude-code-x1.jsonl", tmp_path, no_updates), None)
    assert result.stop_reason == "end_turn" and result.updates == 0
    assert result.last_update_seconds is None  # not recorded, never a zeroed guess


def test_every_recording_states_its_provenance_from_its_capture():  # W1-ACP (e)
    provenance = json.loads((ACP_FIX / "provenance.json").read_text(encoding="utf-8"))
    assert "No full ACP transcript" not in provenance["note"]
    for recording in RECORDINGS:
        record, build = provenance["fixtures"].get(f"recordings/{recording.name}"), _meta(recording)["build"]
        assert record and all(isinstance(record.get(k), str) and record[k].strip() for k in PROVENANCE_KEYS), recording.name
        assert record["adapter_version"] == build["adapter_version"] and build["version"] in record["harness_version"]
        header = _records(recording)[0]
        assert header["kind"] == "header" and header["scrub"]["placeholders"] and "acp_record.py scrub" in record["scrub"]


# D7: every message type the fake emits is paired with a real transcript or the ACP schema ------

PAIRING = {
    # type: evidence (the real recordings it is present in, checked by parsing them; or the ACP schema)
    "initialize.result": "recorded: recordings/claude-code-x1.jsonl, recordings/codex-x1.jsonl",
    "session/new.result": "recorded: recordings/claude-code-x1.jsonl, recordings/codex-x1.jsonl",
    "session/set_mode.result": "recorded: recordings/codex-x1.jsonl (agent-full-access returned {})",
    "session/update.agent_message_chunk": "recorded: recordings/claude-code-x1.jsonl, recordings/codex-x1.jsonl",
    "session/prompt.result": "recorded: recordings/claude-code-x1.jsonl, recordings/codex-x1.jsonl (replayed verbatim, D5)",
    "session/request_permission": "ACP schema (agentclientprotocol.com, RequestPermissionRequest); no real exemplar: every "
                                  "capture made 0 permission requests (the static profile, US-14)",
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


def test_every_pairing_but_permission_is_present_in_the_recordings_it_cites():  # D7, W1-ACP (c)
    for mtype, evidence in PAIRING.items():
        if mtype == "session/request_permission":  # no real exemplar: 0 permission requests in every capture (US-14)
            continue
        cited = [p for p in RECORDINGS if f"recordings/{p.name}" in evidence]
        assert cited, f"{mtype}: its evidence cites no recording"
        for p in cited:
            records = _records(p)
            assert mtype in _message_types(_stream(records, "to_client"), _stream(records, "to_agent")), f"{mtype} not in {p.name}"


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


# the engine's side of the driver change (R-13, R-24, R-28: W1-ACP's engine.py hunks), through a real engine run

@pytest.mark.parametrize("set_model", [False, True])
def test_the_engine_passes_the_plan_model_only_to_a_launcher_that_sets_it(base, monkeypatch, set_model):  # R-13
    from test_engine import FakeLauncher, _plan, _run
    real, seen = driver.run_turn, []

    def spy(*args, **kwargs):
        seen.append(kwargs.get("model"))
        return real(*args, **kwargs)

    monkeypatch.setattr(driver, "run_turn", spy)
    launcher = FakeLauncher({})
    launcher.set_model = set_model
    p = _plan(n_cells=1)
    _run(base, p, launcher)
    assert seen == [p["cells"][0]["model"] if set_model else None]


def test_the_credential_kind_is_the_one_the_launcher_reports(base):  # R-13 condition 2
    from test_engine import FakeLauncher, _plan, _run
    launcher = FakeLauncher({})
    launcher.credential_kind = "subscription login (credential store)"
    _, events, _ = _run(base, _plan(n_cells=1), launcher)
    assert [e["credential_kind"] for e in events if e["kind"] == "attempt.process_started"] == [launcher.credential_kind]


def test_the_session_opened_event_carries_the_agent_version(base):  # R-28: one verbatim field
    from test_engine import FakeLauncher, _plan, _run
    _, events, _ = _run(base, _plan(n_cells=1), FakeLauncher({}))
    opened = [e for e in events if e["kind"] == "attempt.session_opened"]
    assert [e["agent_version"] for e in opened] == ["0"]  # the fake agent's initialize.agentInfo.version


def test_the_attempt_end_records_the_acp_usage_verbatim_or_null(base):  # R-24
    from test_engine import USAGE, FakeLauncher, _plan, _run
    p = _plan(n_cells=2, labels=["with-usage", "no-usage"])
    _, events, _ = _run(base, p, FakeLauncher({"no-usage": {"usage": []}}))
    ended = {e["cell_id"]: e for e in events if e["kind"] == "attempt.process_ended"}
    with_usage, no_usage = (ended[c["cell_id"]]["acp_usage"] for c in p["cells"])
    assert with_usage == {"usage": {"inputTokens": 1}, "meta": {"quota": {"model_usage": USAGE}}}  # the fake's halves
    assert no_usage is None  # not recorded: never {} or zeros


def _with_set_model(tmp_path: Path, reply: dict) -> Path:
    """The codex recording with a session/set_model exchange right after session/new (ids after it shifted by one),
    answered by `reply` (a result or an error)."""
    out, shifted = [], False
    for r in _records(ACP_FIX / "recordings" / "codex-x1.jsonl"):
        if r["kind"] == "line" and r["dir"] == "to_client":
            msg = json.loads(r["text"])
            if shifted and "id" in msg and "method" not in msg:
                msg["id"] += 1
                r = {**r, "text": json.dumps(msg, separators=(",", ":"))}
            out.append(r)
            if msg.get("id") == 2 and "sessionId" in msg.get("result", {}):  # the session/new result
                out.append({**r, "text": '{"jsonrpc":"2.0","id":3,"method":"session/set_model"}'} | {"dir": "to_agent"})
                out.append({**r, "text": json.dumps({"jsonrpc": "2.0", "id": 3, **reply})})
                shifted = True
        else:
            out.append(r)
    path = tmp_path / "with-set-model.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    return path


def _methods(written: bytes) -> list[str]:
    return [m["method"] for m in map(json.loads, written.splitlines()) if "method" in m]


def _run_with_model(tmp_path, recording: Path, model: str):
    env = dict(os.environ, REPLAY_ACP=json.dumps({"recording": str(recording)}))
    cell = procs.spawn([sys.executable, str(REPLAY)], cwd=str(tmp_path), env=env)
    cell.proc.stdin = _Tap(cell.proc.stdin)
    try:
        result = driver.run_turn(cell, cwd=tmp_path, prompt=X1_PROMPT, mode="agent-full-access", handshake_timeout=10,
                                 before_send=lambda sid: None, model=model)
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    return result, bytes(cell.proc.stdin.data)


@pytestmark_native
def test_the_model_is_set_right_after_session_new_and_before_the_mode(tmp_path):  # R-13, ADR-0003 (Copilot pin)
    result, written = _run_with_model(tmp_path, _with_set_model(tmp_path, {"result": {}}), "gpt-6-sol")
    assert result.cause is None and result.stop_reason == "end_turn"
    assert _methods(written) == ["initialize", "session/new", "session/set_model", "session/set_mode", "session/prompt"]
    setter = next(m for m in map(json.loads, written.splitlines()) if m.get("method") == "session/set_model")
    assert setter["params"] == {"sessionId": result.session_id, "modelId": "gpt-6-sol"}


@pytestmark_native
@pytest.mark.parametrize("message", ["Invalid modelId 'x': not one of this session's models.",
                                     "model not available for this login"], ids=["copilot-32602", "auth-words"])
def test_a_refused_model_setter_is_model_unavailable_and_the_prompt_is_never_sent(tmp_path, message):  # R-18
    """By step, not by text: even an error whose text reads like an auth failure is HB-CELL-116 at the setter."""
    error = {"error": {"code": -32602, "message": message}}
    result, written = _run_with_model(tmp_path, _with_set_model(tmp_path, error), "no-such-model")
    assert result.cause is Cause.model_unavailable and message in result.detail
    assert not result.prompt_sent and _methods(written) == ["initialize", "session/new", "session/set_model"]


@pytestmark_native
def test_no_model_means_no_setter(tmp_path):  # Claude Code and Codex stay byte-identical (design section on driver)
    result, _, written = _replay(tmp_path, ACP_FIX / "recordings" / "codex-x1.jsonl", "agent-full-access")
    assert result.cause is None and "session/set_model" not in _methods(written)


@pytestmark_native
@pytest.mark.parametrize(("name", "version"), [("claude-code-x1.jsonl", "0.79.0"), ("codex-x1.jsonl", "1.12.0")])
def test_the_agent_version_is_initialize_agent_info_verbatim(tmp_path, name, version):  # R-22 as narrowed by R-28
    recording = ACP_FIX / "recordings" / name
    result, _, _ = _replay(tmp_path, recording, _meta(recording)["mode"])
    assert result.agent_version == version


@pytestmark_native
def test_the_agent_version_is_null_when_initialize_has_no_agent_info(tmp_path):  # R-28 condition 1
    def no_agent_info(msg):
        if msg.get("id") == 1 and "result" in msg:
            msg["result"].pop("agentInfo")
        return msg

    result, _, _ = _replay(tmp_path, _derive(ACP_FIX / "recordings" / "claude-code-x1.jsonl", tmp_path, no_agent_info))
    assert result.cause is None and result.agent_version is None


@pytestmark_native
def test_run_turn_fills_the_result_its_caller_supplies(tmp_path):  # so the ack barrier can read agent_version
    supplied, seen = driver.TurnResult(), []
    env = dict(os.environ, REPLAY_ACP=json.dumps({"recording": str(ACP_FIX / "recordings" / "claude-code-x1.jsonl")}))
    cell = procs.spawn([sys.executable, str(REPLAY)], cwd=str(tmp_path), env=env)
    try:
        result = driver.run_turn(cell, cwd=tmp_path, prompt=X1_PROMPT, mode=None, handshake_timeout=10,
                                 before_send=lambda sid: seen.append(supplied.agent_version), result=supplied)
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    assert result is supplied and seen == ["0.79.0"]  # known before the prompt goes out
