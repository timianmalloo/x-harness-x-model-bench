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


def test_http_server(tmp: Path) -> None:
    """The Streamable HTTP subset: POST a request -> 200 JSON; a notification -> 202; GET -> 405."""
    import urllib.error
    import urllib.request

    log = tmp / "http.jsonl"
    proc = subprocess.Popen([sys.executable, str(probe_turn.SERVER), "--http", "0", "--log", str(log), "--reply", "H-TEXT"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        port = json.loads(proc.stdout.readline())["port"]
        url = f"http://127.0.0.1:{port}/mcp"

        def post(msg: dict) -> tuple[int, bytes]:
            req = urllib.request.Request(url, data=json.dumps(msg).encode(), method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Accept": "application/json, text/event-stream"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()

        status, body = post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "ask_user", "arguments": {"question": "q?"}}})
        check(status == 200 and json.loads(body)["result"]["content"][0]["text"] == "H-TEXT", "http: tools/call -> 200 with the reply")
        status, body = post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        check(status == 202 and body == b"", "http: a notification -> 202, no body")
        try:
            urllib.request.urlopen(url, timeout=10)
            got = 200
        except urllib.error.HTTPError as exc:
            got = exc.code
        check(got == 405, "http: GET (no SSE stream) -> 405")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    records = probe_turn._load_jsonl(log)
    check(records[0]["transport"] == "http" and any(r["kind"] == "listening" for r in records), "http: the log records transport and port")
    check(sum(r["kind"] == "in" for r in records) == 2, "http: every POSTed message is logged")


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
    check(f["native_record_tool_ids"] == ["mcp__scripted_user__ask_user"], "analyse: the harness's qualified tool id")
    prompt_only = tmp / "prompt-only.jsonl"  # Codex A1: the bare word only in the user message is not the tool
    prompt_only.write_text('{"type": "message", "text": "you can ask with the `ask_user` tool"}\n', encoding="utf-8")
    h = probe_turn.analyse(rec_path, log_path, [prompt_only], None)
    check(h["tool_in_native_record"] is False and h["native_record_lines_naming_tool"] == 1,
          "analyse: a prompt's mention of ask_user is not the tool in the native record")
    codex = tmp / "codex.jsonl"
    codex.write_text('{"title": "mcp.scripted_user.ask_user"}\n', encoding="utf-8")
    check(probe_turn.analyse(rec_path, log_path, [codex], None)["native_record_tool_ids"] == ["mcp.scripted_user.ask_user"],
          "analyse: Codex's dotted id counts")
    structured = tmp / "codex-http.jsonl"  # S-04b: Codex's rollout records {"type":"McpToolCall","server":..,"tool":..}
    structured.write_text('{"item":{"type":"McpToolCall","id":"x","server":"scripted_user","tool":"ask_user"}}\n', encoding="utf-8")
    check(probe_turn.analyse(rec_path, log_path, [structured], None)["native_record_tool_ids"] == ["McpToolCall scripted_user/ask_user"],
          "analyse: Codex's structured McpToolCall counts")
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


def test_emit_on_a_legacy_console() -> None:
    """OUT-A: printing the summary must not fail on a cp1252 console (a Windows pipe's default encoding)."""
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    code = "import probe_turn; probe_turn.emit({'agent_text_tail': '\\u2212 \\U0001f534'})"
    run = subprocess.run([sys.executable, "-c", code], cwd=str(HERE), env=env, capture_output=True, timeout=30, check=False)
    check(run.returncode == 0, "emit: a non-ASCII summary prints on a cp1252 console (exit 0)")
    check(b"\\u2212" in run.stdout, "emit: the text survives as a JSON escape")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        test_server(Path(d))
        test_analyse(Path(d))
        test_http_server(Path(d))
    test_channel_swap()
    test_emit_on_a_legacy_console()
    print(f"{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
