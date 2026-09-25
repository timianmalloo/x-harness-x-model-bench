"""Offline self-test of the S-04 probe: no harness, no model, no network. Stdlib only.

  python tests/fixtures/acp/scripted-user/probe_selftest.py

1. The probe server over real pipes: initialize, tools/list, tools/call ask_user, an unknown tool, an unknown
   method, a notification, junk; the log path from the env var, then from --log alone.
2. `probe_turn.analyse` on a synthetic recording and server log: every fact the summary reports.
3. `probe_turn.session_mcp_servers` rewrites only `session/new`, and restores the driver's channel afterwards.
Exit 0 when every check holds; each failure is printed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_turn

FAILURES: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILURES.append(what)


def talk(messages: list, env_log: str | None, arg_log: str | None) -> list[dict]:
    env = {k: v for k, v in os.environ.items() if k != probe_turn.LOG_ENV}
    if env_log:
        env[probe_turn.LOG_ENV] = env_log
    argv = [sys.executable, str(probe_turn.SERVER), "--reply", "R-TEXT"] + (["--log", arg_log] if arg_log else [])
    lines = b"".join((m if isinstance(m, bytes) else json.dumps(m).encode()) + b"\n" for m in messages)
    out = subprocess.run(argv, input=lines, capture_output=True, env=env, timeout=30, check=True).stdout
    return [json.loads(line) for line in out.decode("utf-8").splitlines() if line.strip()]


def test_server(tmp: Path) -> None:
    log = tmp / "server.jsonl"
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                       "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ask_user", "arguments": {"question": "Max or any?"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "other", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
        b"not json",
    ]
    replies = {r["id"]: r for r in talk(msgs, str(log), None)}
    check(set(replies) == {1, 2, 3, 4, 5}, "server answers every request and no notification")
    check(replies[1]["result"]["protocolVersion"] == "2025-06-18", "initialize echoes the client's protocol version")
    check(replies[1]["result"]["capabilities"] == {"tools": {"listChanged": False}}, "initialize declares tools only")
    tools = replies[2]["result"]["tools"]
    check([t["name"] for t in tools] == ["ask_user"], "tools/list lists exactly ask_user")
    check(tools[0]["inputSchema"]["required"] == ["question"], "ask_user requires question")
    check(replies[3]["result"] == {"content": [{"type": "text", "text": "R-TEXT"}], "isError": False},
          "tools/call ask_user returns the fixed reply as text")
    check(replies[4]["error"]["code"] == -32602, "an unknown tool is -32602")
    check(replies[5]["error"]["code"] == -32601, "an unknown method is -32601")
    records = probe_turn._load_jsonl(log)
    check(records[0]["kind"] == "start" and records[0]["log_source"] == "env", "the env var names the log")
    check(sum(r["kind"] == "in" for r in records) == 6 and sum(r["kind"] == "out" for r in records) == 5,
          "every message in and out is logged")
    check(any(r["kind"] == "junk" for r in records) and records[-1]["kind"] == "eof", "junk and eof are logged")
    arg_log = tmp / "arg.jsonl"
    talk([msgs[0]], None, str(arg_log))
    check(probe_turn._load_jsonl(arg_log)[0]["log_source"] == "arg", "--log names the log when the env var is absent")


def line(seq: int, direction: str, msg: dict) -> dict:
    return {"kind": "line", "seq": seq, "t": seq / 10, "dir": direction, "text": json.dumps(msg), "nl": True}


def update(session_update: str, **fields) -> dict:
    return {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "s1", "update": {"sessionUpdate": session_update, **fields}}}


def test_analyse(tmp: Path) -> None:
    servers = probe_turn.mcp_servers("C:/py.exe", tmp / "s.jsonl", probe_turn.PROBE_REPLY)
    rec = [
        {"kind": "header", "format": "acp-recording/1"},
        line(1, "to_agent", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        line(2, "to_client", {"jsonrpc": "2.0", "id": 1, "result": {"agentCapabilities": {"mcpCapabilities": {"http": True}}}}),
        line(3, "to_agent", {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": "C:/ws", "mcpServers": servers}}),
        line(4, "to_client", {"jsonrpc": "2.0", "id": 2, "result": {"sessionId": "s1"}}),
        line(5, "to_client", update("tool_call", toolCallId="t1", title="scripted_user: ask_user", kind="other", status="pending")),
        line(6, "to_client", {"jsonrpc": "2.0", "id": 9, "method": "session/request_permission",
                              "params": {"toolCall": {"title": "mcp__scripted_user__ask_user"}}}),
        line(7, "to_client", {"jsonrpc": "2.0", "id": 10, "method": "session/request_permission", "params": {"toolCall": {"title": "Bash"}}}),
        line(8, "to_client", update("agent_message_chunk", content={"type": "text", "text": "The probe token is S04-"})),
        line(9, "to_client", update("agent_message_chunk", content={"type": "text", "text": "TOKEN-4417."})),
        line(10, "to_client", update("plan", entries=[{"content": "call ask_user"}])),
    ]
    rec_path = tmp / "rec.jsonl"
    rec_path.write_text("".join(json.dumps(r) + "\n" for r in rec) + '{"kind": "line", "dir": "to_client", "text": "{trunc', encoding="utf-8")
    log_path = tmp / "s.jsonl"
    log = [
        {"kind": "start", "log_source": "env"},
        {"kind": "in", "msg": {"id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "c"}}}},
        {"kind": "in", "msg": {"id": 1, "method": "tools/list"}},
        {"kind": "in", "msg": {"id": 2, "method": "tools/call", "params": {"name": "ask_user", "arguments": {"question": "Token?"}}}},
        {"kind": "out", "msg": {"id": 2, "result": {"content": [{"type": "text", "text": probe_turn.PROBE_REPLY}]}}},
    ]
    log_path.write_text("".join(json.dumps(r) + "\n" for r in log), encoding="utf-8")
    native = tmp / "native.jsonl"
    native.write_text('{"tools": ["Bash", "mcp__scripted_user__ask_user"]}\n{"other": 1}\n', encoding="utf-8")
    f = probe_turn.analyse(rec_path, log_path, [native], probe_turn.PROBE_TOKEN)
    check(f["agent_mcp_capabilities"] == {"http": True}, "analyse: the agent's mcpCapabilities")
    check(f["mcp_servers_sent"] == servers and "type" not in servers[0], "analyse: the stdio shape sent, with no type field")
    check(f["session_new"] == {"status": "accepted", "session_id": "s1"}, "analyse: session/new accepted")
    check(f["tool_in_acp_stream"] and f["acp_tool_call_updates"][0]["toolCallId"] == "t1", "analyse: the tool call in the ACP stream")
    check(f["permission_requests"] == 2 and len(f["permission_requests_naming_tool"]) == 1, "analyse: permission requests naming the tool")
    check(f["permission_request_titles"] == ["mcp__scripted_user__ask_user", "Bash"], "analyse: every permission request's title")
    check(f["reply_token_in_agent_text"] is True, "analyse: the reply token across streamed chunks")
    check(len(f["acp_other_mentions"]) == 1, "analyse: another update naming the tool is kept")
    check(f["server_started"] and f["server_log_source"] == "env" and f["tool_listed"], "analyse: started, env, listed")
    check(f["calls"] == [{"tool": "ask_user", "question": "Token?", "reply": probe_turn.PROBE_REPLY, "error": None}],
          "analyse: each call's question and reply")
    check(f["log_record"] == {"calls": f["calls"]}, "analyse: the log record carries the calls")
    check(f["tool_in_native_record"] is True and f["native_record_lines_naming_tool"] == 1, "analyse: the native record names the tool")
    # the negative: an error from session/new, a server that never started, no native record
    rec_err = tmp / "rec-err.jsonl"
    rec_err.write_text("".join(json.dumps(r) + "\n" for r in [
        rec[3], line(4, "to_client", {"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "bad mcpServers"}})]), encoding="utf-8")
    g = probe_turn.analyse(rec_err, tmp / "absent.jsonl", [], None)
    check(g["session_new"]["status"] == "error" and g["session_new"]["error"]["code"] == -32602, "analyse: a session/new error is kept")
    check(not g["server_started"] and not g["tool_listed"] and not g["model_called_tool"], "analyse: no server log is no start")
    check(g["log_record"] == {"calls": [], "note": "no question asked"}, "analyse: zero calls record 'no question asked'")
    check(g["tool_in_native_record"] is None and g["reply_token_in_agent_text"] is None, "analyse: absent evidence is null, not false")


def test_channel_swap() -> None:
    class FakeDriver:
        class _Channel:
            def rpc(self, method, params, deadline):
                return (method, params)

    original = FakeDriver._Channel
    with probe_turn.session_mcp_servers(FakeDriver, [{"name": "x"}]):
        ch = FakeDriver._Channel()
        check(ch.rpc("session/new", {"cwd": "c", "mcpServers": []}, None) == ("session/new", {"cwd": "c", "mcpServers": [{"name": "x"}]}),
              "channel swap: session/new carries the servers")
        check(ch.rpc("initialize", {"a": 1}, None) == ("initialize", {"a": 1}), "channel swap: other requests are unchanged")
    check(FakeDriver._Channel is original, "channel swap: the driver's channel is restored")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        test_server(Path(d))
        test_analyse(Path(d))
    test_channel_swap()
    print(f"{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
