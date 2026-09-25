"""S-04 probe: a minimal MCP server (stdio, or Streamable HTTP) with one tool, `ask_user(question) -> reply` (R-37).

Not the scripted user. It has no matcher: every `ask_user` call gets the one fixed `--reply`. Its only job is to
show, per harness, whether a server passed in ACP `session/new` `mcpServers` is started, listed and called.

Transport: MCP stdio, one JSON-RPC message per line, UTF-8. Stdlib only.

Log: every message received and every message sent, one JSON object per line, appended to the file named by the
environment variable `SCRIPTED_USER_PROBE_LOG`, else by `--log`. The first record says which one it used
(`log_source`), because whether an adapter forwards the ACP `env` list is itself a measurement. With neither, the
server still answers, and nothing is logged.

Usage (the adapter starts it; by hand only for the self-test):
  python probe_server.py [--log PATH] [--reply TEXT]              stdio (the harness starts it)
  python probe_server.py --http PORT [--log PATH] [--reply TEXT]  Streamable HTTP on 127.0.0.1 (the probe starts it)
"""

from __future__ import annotations

import json
import os
import sys
import time

LOG_ENV = "SCRIPTED_USER_PROBE_LOG"
TOOL = "ask_user"
SERVER_INFO = {"name": "scripted_user", "version": "s04-probe-1"}
DEFAULT_REPLY = "Decide and state your assumption."
TOOL_DEF = {
    "name": TOOL,
    "description": "Ask the user one question about the task. Returns the user's reply as text.",
    "inputSchema": {
        "type": "object",
        "properties": {"question": {"type": "string", "description": "The question for the user."}},
        "required": ["question"],
    },
}


def parse_args(argv: list[str]) -> tuple[str | None, str]:
    log, reply = None, DEFAULT_REPLY
    i = 0
    while i < len(argv):
        if argv[i] == "--log" and i + 1 < len(argv):
            log, i = argv[i + 1], i + 2
        elif argv[i] == "--reply" and i + 1 < len(argv):
            reply, i = argv[i + 1], i + 2
        elif argv[i] == "--http" and i + 1 < len(argv):
            i += 2  # read in main
        else:
            i += 1  # unknown arguments are ignored and logged in the start record
    return log, reply


class Log:
    def __init__(self, path: str | None) -> None:
        self.path = path
        self.start = time.monotonic()

    def write(self, record: dict) -> None:
        if not self.path:
            return
        record = {"t": round(time.monotonic() - self.start, 6), **record}
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def handle(msg: dict, reply_text: str) -> dict | None:
    """The response to one message, or None for a notification or a response."""
    if "method" not in msg or "id" not in msg:
        return None
    method, rid, params = msg["method"], msg["id"], msg.get("params") or {}
    if method == "initialize":
        # simplify: echoes the client's protocol version (a probe accepts whatever the harness speaks, and the log
        # records it). Ceiling: the probe only. Upgrade trigger: the real server (W2-USER-M) pins the versions it supports.
        version = params.get("protocolVersion") if isinstance(params.get("protocolVersion"), str) else "2025-06-18"
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO}
    elif method == "tools/list":
        result = {"tools": [TOOL_DEF]}
    elif method == "tools/call":
        if params.get("name") != TOOL:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"unknown tool {params.get('name')!r}"}}
        result = {"content": [{"type": "text", "text": reply_text}], "isError": False}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def serve_http(port: int, log: Log, reply_text: str) -> int:
    """MCP Streamable HTTP, the JSON-response subset: POST one message (or a batch) to /mcp; a request gets
    200 with a JSON body, a notification or response 202. No SSE stream (GET is 405), no session id.
    Binds 127.0.0.1 only. Prints {"port": N} as its first stdout line, so a caller can pass port 0."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # the JSONL log is the record; stderr stays quiet
            pass

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                log.write({"kind": "junk", "text": body.decode("utf-8", "replace")[:2000]})
                self.send_response(400)
                self.end_headers()
                return
            messages = payload if isinstance(payload, list) else [payload]
            outs = []
            for msg in messages:
                if isinstance(msg, dict):
                    log.write({"kind": "in", "msg": msg, "path": self.path})
                    out = handle(msg, reply_text)
                    if out is not None:
                        log.write({"kind": "out", "msg": out})
                        outs.append(out)
            if not outs:
                self.send_response(202)
                self.end_headers()
                return
            data = json.dumps(outs if isinstance(payload, list) else outs[0], ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            log.write({"kind": "http", "method": "GET", "path": self.path})
            self.send_response(405)
            self.end_headers()

        def do_DELETE(self) -> None:
            log.write({"kind": "http", "method": "DELETE", "path": self.path})
            self.send_response(405)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    bound = server.server_address[1]
    log.write({"kind": "listening", "port": bound})
    sys.stdout.write(json.dumps({"port": bound}) + "\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    finally:
        log.write({"kind": "eof"})
    return 0


def main(argv: list[str]) -> int:
    arg_log, reply_text = parse_args(argv)
    env_log = os.environ.get(LOG_ENV)
    log = Log(env_log or arg_log)
    http_port = int(argv[argv.index("--http") + 1]) if "--http" in argv[:-1] else None
    log.write({"kind": "start", "pid": os.getpid(), "log_source": "env" if env_log else ("arg" if arg_log else "none"),
               "transport": "http" if http_port is not None else "stdio", "argv": argv, "reply": reply_text,
               "server": SERVER_INFO})
    if http_port is not None:
        return serve_http(http_port, log, reply_text)
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    for raw in iter(stdin.readline, b""):
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            log.write({"kind": "junk", "text": line.decode("utf-8", "replace")[:2000]})
            continue
        if not isinstance(msg, dict):
            log.write({"kind": "junk", "text": line.decode("utf-8", "replace")[:2000]})
            continue
        log.write({"kind": "in", "msg": msg})
        out = handle(msg, reply_text)
        if out is not None:
            stdout.write(json.dumps(out, ensure_ascii=False).encode("utf-8") + b"\n")
            stdout.flush()
            log.write({"kind": "out", "msg": out})
    log.write({"kind": "eof"})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
