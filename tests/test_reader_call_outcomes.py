"""W13: the Codex and agy readers set `ToolCall.ok` (ADR-0006: the native outcome, null when the record does not say).

`ok` is False when the call failed: a command that exited non-zero (a failing test run counts, as Claude Code's
`is_error` counts it), a tool error, a refused or cancelled step. The failing exit code rides on `outcome_code` as
`exit_<N>`, so a consumer can tell a command that ran and failed from a tool that did not run (Copilot's `ok` is the
second kind only). Shapes are copied from the lean runs of 2026-10-13 (Codex 0.160.0 rollouts, agy 1.3.3 stream and
conversation db); the agy db rows here are built with the same field numbers the reader decodes (140.2.1 = the result).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from harness_bench.telemetry import agy, codex

FIX = Path(__file__).resolve().parent / "fixtures"
TURN = "01a0d0a4-6ad7-7342-8ed5-cec663a0f128"
OTHER_TURN = "01a0d0a4-0000-7000-8000-000000000002"


# --- Codex ---------------------------------------------------------------------------------------------------------

def _call(call_id, name="exec", kind="custom_tool_call", turn=TURN):
    return {"type": "response_item", "payload": {
        "type": kind, "call_id": call_id, "name": name, "input": "text(await tools.exec_command({cmd:'x'}));",
        "internal_chat_message_metadata_passthrough": {"turn_id": turn}}}


def _output(call_id, head, kind="custom_tool_call_output"):
    return {"type": "response_item", "payload": {
        "type": kind, "call_id": call_id,
        "output": [{"type": "input_text", "text": head + "\nWall time 0.1 seconds\nOutput:\n"}]}}


def _command(status, exit_code, turn=TURN):
    return {"type": "event_msg", "payload": {"type": "item_completed", "turn_id": turn, "item": {
        "type": "CommandExecution", "status": status, "exit_code": exit_code, "command": ["pwsh", "-Command", "x"]}}}


def _patch(status, turn=TURN):
    return {"type": "event_msg", "payload": {"type": "item_completed", "turn_id": turn, "item": {
        "type": "FileChange", "status": status, "changes": {}}}}


def _read_codex(tmp_path, *events):
    record = tmp_path / "rollout.jsonl"
    record.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return [(c.ok, c.outcome_code) for c in codex.read(record).tool_calls]


@pytest.mark.parametrize("name, events, expected", [
    ("a command that exited 0", [_call("a"), _command("completed", 0), _output("a", "Script completed")], (True, None)),
    ("a command that exited 1 (a failing test run is a failed call)",
     [_call("a"), _command("failed", 1), _output("a", "Script completed")], (False, "exit_1")),
    ("one failed command among several in one script",
     [_call("a"), _command("completed", 0), _command("failed", 2), _command("completed", 0),
      _output("a", "Script completed")], (False, "exit_2")),
    ("a script that failed before or while running",
     [_call("a"), _output("a", "Script failed")], (False, "script_failed")),
    ("an apply_patch that did not complete", [_call("a"), _patch("failed"), _output("a", "Script completed")],
     (False, "patch_failed")),
    ("a patch that completed", [_call("a"), _patch("completed"), _output("a", "Script completed")], (True, None)),
    ("a poll that returned while the process still runs: the call itself did not fail",
     [_call("a"), _output("a", "Script running with cell ID 11")], (True, None)),
    ("a command of another thread's turn (a sub-agent's) is not this call's",
     [_call("a"), _command("failed", 1, turn=OTHER_TURN), _output("a", "Script completed")], (True, None)),
    ("a delegation tool whose output came back", [_call("a", "spawn_agent", "function_call"),
                                                  _output("a", '{"task_name":"/root/r"}', "function_call_output")],
     (True, None)),
    ("a call with no output row", [_call("a")], (None, None)),
    ("an exec whose output head says nothing known", [_call("a"), _output("a", "Something else")], (None, None)),
    ("two open calls of one turn: the items cannot be attributed",
     [_call("a"), _call("b"), _command("failed", 1), _output("a", "Script completed"), _output("b", "Script completed")],
     (None, None)),
])
def test_codex_call_outcome(tmp_path, name, events, expected):
    assert _read_codex(tmp_path, *events)[0] == expected, name


def test_codex_outcomes_on_the_committed_real_rollouts():
    ok = codex.read(FIX / "native/codex/ok.jsonl").tool_calls
    assert [(c.ok, c.outcome_code) for c in ok] == [(True, None), (True, None)]  # two commands, each exit_code 0
    pack_on = codex.read(FIX / "native/codex/pack-on.jsonl").tool_calls
    assert pack_on and all(c.ok is not None for c in pack_on)


# --- agy -----------------------------------------------------------------------------------------------------------

CID = "00000000-0000-4000-8000-000000000030"


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(number, payload: bytes) -> bytes:
    return _varint(number << 3 | 2) + _varint(len(payload)) + payload


def _result_payload(text: str) -> bytes:
    """A step payload whose field 140.2.1 holds the tool's result text (the run_command shape of a real db)."""
    return _field(140, _field(2, _field(1, text.encode("utf-8"))))


def _agy_cell(tmp_path, steps):
    """steps: (step_index, tool_name, stream state, stream error type | None, db status, db result text | None)."""
    home = tmp_path / "home"
    store = home / ".gemini" / "antigravity-cli" / "conversations"
    store.mkdir(parents=True)
    lines = [json.dumps({"event": "init", "conversation_id": CID, "init": {"model": "gemini-3.8-flash-high"}})]
    con = sqlite3.connect(store / (CID + ".db"))
    con.execute("create table steps (idx integer primary key, step_type integer, status integer, step_payload blob)")
    con.execute("create table gen_metadata (idx integer primary key, data blob, size integer)")
    for index, name, state, error, status, text in steps:
        for s in ("ACTIVE", state):
            update = {"conversation_id": CID, "step_index": index, "state": s, "step_type": "tool", "tool_name": name}
            if s == "ERROR":
                update["tool_info"] = {"name": name, "error": {"type": error}}
            lines.append(json.dumps({"event": "step_update", "step_update": update}))
        con.execute("insert into steps values (?, 132, ?, ?)", (
            index, status, _result_payload(text) if text is not None else _field(1, b"x")))
    con.commit()
    con.close()
    (home / "agy-stream.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return home / "agy-stream.ndjson"


@pytest.mark.parametrize("name, step, expected", [
    ("a command that exited 0", (2, "run_command", "DONE", None, 3, "\nThe command exited with code 0.\nOutput:\nhi"),
     (True, None)),
    ("a command that exited 1", (2, "run_command", "DONE", None, 3, "\nThe command exited with code 1.\nOutput:\nE"),
     (False, "exit_1")),
    ("a command whose result names no exit code", (2, "run_command", "DONE", None, 3, "no code here"), (None, None)),
    ("a command with no result field", (2, "run_command", "DONE", None, 3, None), (None, None)),
    ("a step the db marks cancelled (stream DONE, db status 6)", (2, "run_command", "DONE", None, 6, None),
     (False, "status_6")),
    ("a tool error (stream ERROR keeps its native type)", (2, "view_file", "ERROR", "TOOL_ERROR", 7, None),
     (False, "TOOL_ERROR")),
    ("a file read that completed", (2, "view_file", "DONE", None, 3, None), (True, None)),
    ("a status the reader does not know", (2, "view_file", "DONE", None, 9, None), (None, None)),
])
def test_agy_call_outcome(tmp_path, name, step, expected):
    calls = agy.read(_agy_cell(tmp_path, [step])).tool_calls
    assert [(c.ok, c.outcome_code) for c in calls] == [expected], name


def test_agy_outcome_on_the_committed_real_record():
    # pack-off (a real db row, scrubbed): one run_command whose result opens "The command exited with code 0."
    pack_off = agy.read(FIX / "agy/reader/pack-off/agy-stream.ndjson").tool_calls
    assert [(c.name, c.ok) for c in pack_off] == [("run_command", True)]


def test_agy_without_its_conversation_db_leaves_the_outcome_not_recorded(tmp_path):
    steps = [(2, "run_command", "DONE", None, 3, "\nThe command exited with code 1.\nOutput:\n")]
    stream = _agy_cell(tmp_path, steps)
    for db in stream.parent.rglob("*.db"):
        db.unlink()
    assert [(c.ok, c.outcome_code) for c in agy.read(stream).tool_calls] == [(None, None)]
