"""A scriptable fake ACP agent for driver and engine tests (design T8 / D7).

Behaviour comes from the FAKE_ACP environment variable (JSON):
  {"mode": "ok" | "permission" | "hang_prompt" | "hang_handshake" | "eof_mid_turn" | "junk_lines" | "huge_line"
          | "exit_before_prompt" | "provider_error" | "no_model_call" | "no_memory" | "stubborn" | "on_cancel",
   "record_dir": "<folder for a Claude-shaped native record>", "write_file": "<name written into cwd>",
   "sleep": <seconds to run the turn>, "model": "<served model>",
   "usage": [<model_usage entries for the prompt result, as claude-agent-acp reports them>],
   "hang": <hang after writing the record, any mode>, "flush_on_eof": <append a record row after stdin closes>,
   "linger": <seconds to stay alive after stdin closes, like a CLI that is slow to exit>,
   "stderr": "<text written to stderr at start>", "mkdir": "<a folder created relative to cwd at start>",
   "handshake_delay": <seconds before answering initialize>,
   "echo_credential": <at the prompt, echo record_dir/.credentials.json to stderr, a message chunk, echo.txt in cwd,
                       and the prompt's error reply>,
   "daemon": <at the prompt, start a detached grandchild that outlives the turn (a build server), trying breakaway
              first; it writes its own "pid creation_time" to daemon.pid in cwd>}

Messages it emits (each paired with a recorded real transcript or the ACP schema in
tests/test_driver.py::test_fake_agent_message_types_are_paired): the initialize result, the session/new
result, the set_mode result, the set_model result (a driver call passing `model=`, D7 W1-ACP open item 6),
session/update notifications (agent_message_chunk), session/request_permission, and the session/prompt
result with a stopReason.
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


DAEMON = """
import os, sys, time
from harness_bench import host  # the venv's package: the same (pid, creation time) identity the engine uses
pid = os.getpid()
open(sys.argv[1] + ".tmp", "w").write(f"{pid} {host.creation_time(pid)}")
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
time.sleep(120)
"""


def start_daemon() -> None:
    """The daemon writes its own identity: sys.executable may be a venv launcher whose child is the real process."""
    import subprocess

    marker = Path(os.getcwd(), "daemon.pid")
    detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    argv = [sys.executable, "-c", DAEMON, str(marker)]
    try:  # breakaway is never allowed by the cell's job, so this must fail
        subprocess.Popen(argv, creationflags=detached | subprocess.CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
    except OSError:
        subprocess.Popen(argv, creationflags=detached, close_fds=True)
    deadline = time.monotonic() + 20
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)


def main() -> int:
    if CFG.get("stderr"):
        sys.stderr.write(CFG["stderr"])
        sys.stderr.flush()
    if CFG.get("mkdir"):
        Path(os.getcwd(), CFG["mkdir"]).mkdir(parents=True, exist_ok=True)
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
            time.sleep(CFG.get("handshake_delay", 0))
            if MODE == "hang_handshake":
                time.sleep(600)
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1, "agentCapabilities": {},
                                                           "agentInfo": {"name": "fake", "version": "0"}}})
        elif method == "session/new":
            Path(os.getcwd(), ".fake-session-new.json").write_text(json.dumps(msg["params"]), encoding="utf-8")
            if CFG.get("scripted_user_log"):
                with Path(CFG["scripted_user_log"]).open("a", encoding="utf-8") as log:
                    log.write(json.dumps({"kind": "tools_listed"}) + "\n")
            send({"jsonrpc": "2.0", "id": mid, "result": {"sessionId": session_id,
                                                           "modes": {"currentModeId": "agent", "availableModes": [{"id": "agent"}, {"id": "agent-full-access"}]}}})
        elif method == "session/set_mode":
            Path(os.getcwd(), ".fake-set_mode").write_text(json.dumps(msg["params"]), encoding="utf-8")
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "session/set_model":
            Path(os.getcwd(), ".fake-set_model").write_text(json.dumps(msg["params"]), encoding="utf-8")
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "session/prompt":
            text = msg["params"]["prompt"][0]["text"]
            Path(os.getcwd(), ".fake-prompt.txt").write_text(text, encoding="utf-8", newline="")
            record(session_id, os.getcwd(), text)
            if MODE in {"stubborn", "on_cancel"}:
                if MODE == "stubborn":
                    import subprocess

                    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=OUT)
                    Path(os.getcwd(), ".fake-stubborn-child.pid").write_text(str(child.pid), encoding="utf-8")
                cancel = json.loads(sys.stdin.buffer.readline())
                Path(os.getcwd(), ".fake-cancel.json").write_text(json.dumps(cancel), encoding="utf-8")
                if MODE == "stubborn":
                    time.sleep(60)
                if CFG.get("late_permission"):
                    send({"jsonrpc": "2.0", "id": 901, "method": "session/request_permission",
                          "params": {"sessionId": session_id, "toolCall": {"toolCallId": "t2", "title": "late"},
                                     "options": [{"optionId": "allow", "kind": "allow_once", "name": "Allow"}]}})
                if not sys.stdin.buffer.readline() and CFG.get("shutdown_file"):
                    Path(os.getcwd(), CFG["shutdown_file"]).write_text("shutdown\n", encoding="utf-8")
                result = {"stopReason": "cancelled"}
                if CFG.get("usage"):
                    result.update({"usage": {"inputTokens": 1}, "_meta": {"quota": {"model_usage": CFG["usage"]}}})
                send({"jsonrpc": "2.0", "id": mid, "result": result})
                continue
            if CFG.get("echo_credential"):  # T-LOG-nosecret: an agent that prints its login everywhere it can
                secret = (Path(CFG["record_dir"]) / ".credentials.json").read_text(encoding="utf-8")
                sys.stderr.write(secret + "\n")
                sys.stderr.flush()
                Path(os.getcwd(), "echo.txt").write_text(secret, encoding="utf-8")
                send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session_id,
                      "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": secret}}}})
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": secret}})
                continue
            if CFG.get("daemon"):  # T-JOB-daemon: like `dotnet build` leaving its build server behind
                start_daemon()
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
