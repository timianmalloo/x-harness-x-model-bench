"""The scripted user's stdio MCP server (design section 6, R-37, R-51): one tool, `ask_user(question) -> reply`.

Launch: `<python> -m harness_bench.scripted_user.server <clarifications.yaml> <log.jsonl>`, with the log path also in
the environment variable SCRIPTED_USER_LOG (which wins; the argument is the fallback). `entry()` gives the ACP
`McpServerStdio` shape for `session/new` (Claude Code, Codex) and the same command, args and env serve Copilot's
`--additional-mcp-config` file (R-51). The protocol handling is the S-04 probe's
(tests/fixtures/acp/scripted-user/probe_server.py), with the real matcher and log, and pinned protocol versions.

The server loads the clarification set at start and refuses to start (exit 2, a `refused` log row, no reply ever
sent) on a malformed or ambiguous set, or when this Python's table and Unicode data do not give the committed
MATCHER_VERSION. A refused start then reads as "tool not reached" (design section 8).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from harness_bench.errors import BenchError
from harness_bench.scripted_user import matcher
from harness_bench.scripted_user.clarifications import ClarificationSet, load
from harness_bench.scripted_user.log import LOG_ENV, LogWriter
from harness_bench.scripted_user.matcher import MATCHER_VERSION

SERVER_NAME = "scripted_user"  # an underscore: the name becomes part of each harness's tool id (design section 4.1)
TOOL = "ask_user"
# The versions S-04 saw (Claude Code, Codex), newest first; any other request is answered with the newest.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18")
TOOL_DEF = {
    "name": TOOL,
    "description": "Ask the user one question about the task. Returns the user's reply as text.",
    "inputSchema": {
        "type": "object",
        "properties": {"question": {"type": "string", "description": "The question for the user."}},
        "required": ["question"],
    },
}
USAGE = "usage: python -m harness_bench.scripted_user.server CLARIFICATIONS_YAML LOG_JSONL"


class Server:
    def __init__(self, cset: ClarificationSet, log: LogWriter) -> None:
        self.cset, self.log = cset, log

    def handle(self, msg: dict) -> dict | None:
        """The response to one message, or None for a notification or a response. Every log row a request causes is
        written before this returns, so before its reply is sent."""
        if "method" not in msg or "id" not in msg:
            return None
        method, rid = msg["method"], msg["id"]
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            client = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else None
            self.log.initialize(client, version, requested)
            result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": SERVER_NAME, "version": MATCHER_VERSION}}
        elif method == "tools/list":
            self.log.tools_listed()
            result = {"tools": [TOOL_DEF]}
        elif method == "tools/call":
            if params.get("name") != TOOL:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"unknown tool {params.get('name')!r}"}}
            arguments = params.get("arguments")
            question = arguments.get("question") if isinstance(arguments, dict) else None
            decision = matcher.match(question, self.cset.clarifications)
            reply = self.cset.reply_for(decision)
            self.log.call(question, decision, reply, self.cset)
            result = {"content": [{"type": "text", "text": reply}], "isError": False}
        elif method == "ping":
            result = {}
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": rid, "result": result}


def serve(server: Server, stdin, stdout) -> None:
    """MCP stdio: one JSON-RPC message per line, UTF-8. A line that is not a JSON object gets no response."""
    for raw in iter(stdin.readline, b""):
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:  # UnicodeDecodeError is a ValueError
            continue
        if not isinstance(msg, dict):
            continue
        out = server.handle(msg)
        if out is not None:
            stdout.write(json.dumps(out, ensure_ascii=True).encode("ascii") + b"\n")
            stdout.flush()


def entry(clarifications: Path, log: Path, python: str = sys.executable) -> dict:
    """The ACP McpServerStdio entry: no `type` field (claude-agent-acp drops an entry with `type: "stdio"`)."""
    return {"name": SERVER_NAME, "command": python,
            "args": ["-m", "harness_bench.scripted_user.server", str(clarifications), str(log)],
            "env": [{"name": LOG_ENV, "value": str(log)}]}


def main(argv: list[str] | None = None, stdin=None, stdout=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.stderr.write(USAGE + "\n")
        return 2
    env_log = os.environ.get(LOG_ENV)
    log = LogWriter(Path(env_log or argv[1]))
    try:
        version = matcher.compute_matcher_version()
        if version != MATCHER_VERSION:
            raise BenchError("HB-USR-002", f"matcher_version mismatch: this Python gives {version}, "
                                           f"the committed constant is {MATCHER_VERSION}")
        cset = load(Path(argv[0]))
    except BenchError as e:
        log.refused(e.code, e.message)
        sys.stderr.write(f"{e}\n")
        return 2
    log.header(cset, "env" if env_log else "arg")
    serve(Server(cset, log), stdin or sys.stdin.buffer, stdout or sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
