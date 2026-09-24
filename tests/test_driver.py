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
PROVENANCE_KEYS = ("adapter", "adapter_version", "harness_version", "captured", "scrub", "source")


def _replay(tmp_path, **cfg):
    env = dict(os.environ, REPLAY_ACP=json.dumps(cfg))
    cell = procs.spawn([sys.executable, str(REPLAY)], cwd=str(tmp_path), env=env)
    try:
        return driver.run_turn(cell, cwd=tmp_path, prompt="p", mode=None, handshake_timeout=10, before_send=lambda sid: None)
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()


def test_every_recorded_acp_fixture_states_its_provenance():  # D5: adapter version, capture date, scrub
    provenance = json.loads((ACP_FIX / "provenance.json").read_text(encoding="utf-8"))["fixtures"]
    assert RECORDED and {p.name for p in RECORDED} == set(provenance)
    for name, record in provenance.items():
        assert all(isinstance(record.get(k), str) and record[k].strip() for k in PROVENANCE_KEYS), name


@pytestmark_native
@pytest.mark.parametrize("fixture", RECORDED, ids=[p.stem for p in RECORDED])
def test_a_recorded_prompt_result_replays_through_the_driver(tmp_path, fixture):  # D5
    recorded = json.loads(fixture.read_text(encoding="utf-8"))
    result = _replay(tmp_path, prompt_result=str(fixture))
    assert result.cause is None and result.stop_reason == recorded["stopReason"] and result.prompt_sent
    assert result.usage == {"usage": recorded["usage"], "meta": recorded["_meta"]}
    # the engine's reading of the driver's result is the reading of the recorded bytes
    assert normalize.turn_usage({"_meta": result.usage["meta"]}) == normalize.turn_usage(recorded) != []


# D7: every message type the fake emits is paired with a real transcript or the ACP schema ------

PAIRING = {
    # type: evidence (a recorded real transcript from the spikes, or the ACP schema)
    "initialize.result": "spike N4: real initialize results from claude-agent-acp, codex-acp, copilot --acp",
    "session/new.result": "spike N4: real session/new results (sessionId, modes.availableModes)",
    "session/set_mode.result": "spike N4: codex-acp set_mode agent-full-access returned {}",
    "session/set_model.result": "spike N4: copilot set_model returned {}",
    "session/update.agent_message_chunk": "spike R11 container_acp.py counted real session/update notifications",
    "session/prompt.result": "spike N4: stopReason end_turn from all three adapters",
    "session/request_permission": "ACP schema (agentclientprotocol.com, RequestPermissionRequest); no real exemplar yet - "
                                  "flagged for the phase-2 permission probe",
}


def test_fake_agent_message_types_are_paired():
    source = FAKE.read_text(encoding="utf-8")
    emitted = {"initialize.result", "session/new.result", "session/set_mode.result", "session/set_model.result",
               "session/update.agent_message_chunk", "session/prompt.result", "session/request_permission"}
    assert '"session/request_permission"' in source and "agent_message_chunk" in source
    unpaired = emitted - set(PAIRING)
    assert not unpaired, f"fake message types with no real transcript or schema: {sorted(unpaired)}"
