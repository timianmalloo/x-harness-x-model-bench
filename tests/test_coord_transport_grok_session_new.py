"""Grok's watcher acknowledgement can arrive before the session/new response (measured 2026-10-03, runs
w2-g1-e1e4 and w2-enva-e1e4, Grok 1.0.41). The compatibility stays narrow: named ids, shape, release floor."""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "docs" / "ai-forward-pack" / "scripts" / "coord_transport.py"
spec = importlib.util.spec_from_file_location("coord_transport", SCRIPT)
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)

WATCHER = {"id": "skills-reload", "jsonrpc": "2.0", "result": {"result": {"reloaded": 0}}}


class _Wire:
    def __init__(self, script):
        self.script, self.sent = list(script), []
        self.deadline = time.monotonic() + 60
        self.last_frame_bytes = 0

    def queue(self, message):
        self.sent.append(message)

    def receive(self):
        return self.script.pop(0)

    def check(self):
        pass


def _run(version, middle):
    init = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1, "agentInfo": {"name": "grok", "version": version},
                                                  "_meta": {"grokShell": True, "agentVersion": version}}}
    created = {"jsonrpc": "2.0", "id": 2, "result": {"sessionId": "s-1"}}
    result = {"session_id": None, "compatibility_responses": 0, "reported_version": None,
              "reported_version_source": None, "progress_updates": 0}
    session = ct._Session(_Wire([init, *middle, created]), result, lambda event: None, lambda left: True, [])
    try:
        session.acp("/tmp", [], [], None, False, None, None)
    except ct._Failure as failure:
        return result, failure, session
    return result, None, session


def test_watcher_ack_before_session_new_response_creates_the_session():
    result, failure, session = _run("1.0.41", [WATCHER])
    assert failure is None and session.phase == "session/new"
    assert result["session_id"] == "s-1" and result["compatibility_responses"] == 1


@pytest.mark.parametrize("version, message", [
    ("1.0.41", {"id": "surprise", "jsonrpc": "2.0", "result": {"result": {"reloaded": 0}}}),
    ("1.0.41", {"id": "skills-reload", "jsonrpc": "2.0", "result": {"result": {"reloaded": 0, "x": 1}}}),
    ("1.0.33", WATCHER),
])
def test_anything_else_unsolicited_during_session_new_is_still_a_protocol_error(version, message):
    result, failure, session = _run(version, [message])
    assert failure is not None and failure.code == "protocol_error" and session.phase == "session/new"
    assert result["session_id"] is None
