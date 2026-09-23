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

FAKE = Path(__file__).parent / "fake_acp_agent.py"


def _spawn(tmp_path, fake="ok", **cfg):
    env = dict(os.environ, FAKE_ACP=json.dumps({"mode": fake, **cfg}))
    return procs.spawn([sys.executable, str(FAKE)], cwd=str(tmp_path), env=env)


def _turn(tmp_path, prompt="Do the task.", before_send=None, acp_mode=None, handshake=10, fake="ok", **cfg):
    cell = _spawn(tmp_path, fake=fake, **cfg)
    try:
        return driver.run_turn(cell, cwd=tmp_path, prompt=prompt, mode=acp_mode, handshake_timeout=handshake,
                               before_send=before_send or (lambda: None))
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()


# the line reader: bounded, never crashes (D2) ------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(st.binary(max_size=4096))
def test_line_reader_never_crashes_and_stays_bounded(data):
    reader = driver.LineParser(max_line=256, max_junk=20)
    try:
        for msg in reader.feed(data):
            assert isinstance(msg, dict)
    except driver.ProtocolError:
        pass
    assert len(reader._buf) <= 256 + 4096


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
    def refuse():
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
    result = driver.run_turn(cell, cwd=tmp_path, prompt="p", mode=None, handshake_timeout=10, before_send=lambda: None)
    timer.join()
    cell.close()
    assert result.prompt_sent and result.stop_reason is None and result.eof


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
