"""A scriptable fake ACP agent for driver and engine tests (design T8 / D7).

Behaviour comes from the FAKE_ACP environment variable (JSON):
  {"mode": "ok" | "permission" | "hang_prompt" | "hang_handshake" | "eof_mid_turn" | "junk_lines" | "huge_line"
          | "exit_before_prompt" | "provider_error" | "no_model_call" | "no_memory",
   "record_dir": "<folder for a Claude-shaped native record>", "write_file": "<name written into cwd>",
   "sleep": <seconds to run the turn>, "model": "<served model>",
   "usage": [<model_usage entries for the prompt result, as claude-agent-acp reports them>],
   "hang": <hang after writing the record, any mode>, "flush_on_eof": <append a record row after stdin closes>,
   "linger": <seconds to stay alive after stdin closes, like a CLI that is slow to exit>}

Messages it emits (each paired with a recorded real transcript or the ACP schema in
tests/test_driver.py::test_fake_agent_message_types_are_paired): the initialize result, the session/new
result, the set_mode / set_model results, session/update notifications (agent_message_chunk),
session/request_permission, and the session/prompt result with a stopReason.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

CFG = json.loads(os.environ.get("FAKE_ACP", "{}"))
MODE = CFG.get("mode", "ok")
OUT = sys.stdout.buffer


def send(obj) -> None:
    OUT.write(json.dumps(obj).encode() + b"\n")
    OUT.flush()


def record(session_id: str, cwd: str, prompt: str) -> None:
    folder = CFG.get("record_dir")
    if not folder:
        return
    path = Path(folder) / "projects" / "fake" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    now = "2026-09-23T00:00:00.000Z"
    rows = [{"type": "user", "sessionId": session_id, "timestamp": now, "message": {"role": "user", "content": prompt}}]
    if MODE == "provider_error":
        rows.append({"type": "assistant", "isApiErrorMessage": True, "apiErrorStatus": 529, "error": "overloaded_error",
                     "timestamp": now, "message": {"model": "<synthetic>", "usage": {"input_tokens": 0, "output_tokens": 0}}})
    elif MODE != "no_model_call":
        rows.append({"type": "assistant", "sessionId": session_id, "timestamp": now,
                     "message": {"id": "msg_1", "model": CFG.get("model", "claude-sonnet-5"), "role": "assistant",
                                 "content": [{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "python -c \"print(6*7)\""}}],
                                 "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100,
                                           "cache_creation_input_tokens": 20}}})
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main() -> int:
    if MODE == "exit_before_prompt":
        return 3
    if MODE == "no_memory":
        import ctypes
        ctypes.windll.kernel32.ExitProcess(0xC0000017)
    if MODE == "junk_lines":
        for _ in range(25):
            OUT.write(b"Update available! Run npm i -g something\n")
        OUT.flush()
    if MODE == "huge_line":
        OUT.write(b"x" * (2 * 1024 * 1024) + b"\n")
        OUT.flush()
    session_id = str(uuid.uuid4())
    for raw in sys.stdin.buffer:
        msg = json.loads(raw)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            if MODE == "hang_handshake":
                time.sleep(600)
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1, "agentCapabilities": {},
                                                           "agentInfo": {"name": "fake", "version": "0"}}})
        elif method == "session/new":
            send({"jsonrpc": "2.0", "id": mid, "result": {"sessionId": session_id,
                                                           "modes": {"currentModeId": "agent", "availableModes": [{"id": "agent"}, {"id": "agent-full-access"}]}}})
        elif method in ("session/set_mode", "session/set_model"):
            Path(os.getcwd(), f".fake-{method.split('/')[1]}").write_text(json.dumps(msg["params"]), encoding="utf-8")
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "session/prompt":
            text = msg["params"]["prompt"][0]["text"]
            Path(os.getcwd(), ".fake-prompt.txt").write_text(text, encoding="utf-8", newline="")
            record(session_id, os.getcwd(), text)
            if MODE == "hang_prompt" or CFG.get("hang"):
                time.sleep(600)
            if MODE == "eof_mid_turn":
                send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session_id,
                      "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "wor"}}}})
                return 1
            if MODE == "permission":
                send({"jsonrpc": "2.0", "id": 900, "method": "session/request_permission",
                      "params": {"sessionId": session_id, "toolCall": {"toolCallId": "t1", "title": "run"},
                                 "options": [{"optionId": "allow", "kind": "allow_once", "name": "Allow"}]}})
                reply = json.loads(sys.stdin.buffer.readline())
                Path(os.getcwd(), ".fake-permission-reply.json").write_text(json.dumps(reply), encoding="utf-8")
            if CFG.get("write_file"):
                Path(os.getcwd(), CFG["write_file"]).write_text("done\n", encoding="utf-8")
            time.sleep(CFG.get("sleep", 0))
            send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session_id,
                  "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "DONE"}}}})
            result = {"stopReason": "end_turn"}
            if CFG.get("usage"):  # shaped like claude-agent-acp's prompt response (tests/fixtures/acp)
                result.update({"usage": {"inputTokens": 1}, "_meta": {"quota": {"model_usage": CFG["usage"]}}})
            send({"jsonrpc": "2.0", "id": mid, "result": result})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}})
    if CFG.get("flush_on_eof") and CFG.get("record_dir"):  # like a CLI that writes its last rows on exit
        time.sleep(0.5)
        for rec in Path(CFG["record_dir"]).glob("projects/**/*.jsonl"):
            with rec.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"type": "flushed-on-exit"}) + "\n")
    time.sleep(CFG.get("linger", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
