"""copilot -p behind a minimal ACP server on stdio (ADR-0028 s1). Stdlib only; the engine launches it as the cell
process, so one process runs the whole attempt and the engine, driver and lifecycle stay unchanged.

    python copilot_p_acp.py --exe <copilot argv prefix...> -- <copilot pass-through argv...>

Served: `initialize` (agentInfo.version is the build's own `--version` self-report, null when unparsed),
`session/new` (a fresh UUID), `session/set_model` (accepted; the model is in the pass-through argv), `session/prompt`,
and the `session/cancel` notification. Each prompt runs one child, `<exe> -p <text> --session-id <uuid>` for the first
and `--resume <uuid>` after, then the pass-through argv, which keeps `--available-tools` last (the scenario-6 and
scripted-user appends extend that list, profiles.py). The child's stdout is teed unchanged to
`$COPILOT_HOME/copilot-p-turn<k>.jsonl`; each line is also announced as a `session/update`, so the driver's update
count and first-update hook measure the turn. The stop reason: `end_turn` for exit 0 with a final `result` object;
`cancelled` after `session/cancel` (the child is killed); `incomplete` for anything else, which the engine classifies
(native record first, then adapter_crash, engine._classify) and never reads as completed. The final object's `usage` is
returned as ACP usage only when it carries a token count: Copilot 1.0.89-1's carries none (spike, 2026-10-12), and a
token-free usage would make HB-VAL-005 report a difference rather than "not recorded" (ADR-0028 s4).
"""

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

VERSION = "0.1.0"
TOKEN_KEYS = ("inputTokens", "outputTokens", "cachedReadTokens", "cachedWriteTokens")
_SEMVER = re.compile(r"\b(\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?)")


class Adapter:
    def __init__(self, exe: list[str], passthrough: list[str], out) -> None:
        self.exe, self.passthrough, self.out = exe, passthrough, out
        self.lock = threading.Lock()
        self.session_id: str | None = None
        self.turns = 0
        self.child: subprocess.Popen | None = None
        self.cancelled = False
        self.worker: threading.Thread | None = None

    def send(self, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"
        with self.lock:
            try:
                self.out.write(line)
                self.out.flush()
            except (OSError, ValueError):
                pass  # the client is gone; the engine's job owns what happens next

    def reply(self, rid, result=None, error=None) -> None:
        self.send({"jsonrpc": "2.0", "id": rid, **({"error": error} if error else {"result": result or {}})})

    def version(self) -> str | None:
        try:
            done = subprocess.run([*self.exe, "--version"], capture_output=True, timeout=60, check=False, stdin=subprocess.DEVNULL,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            return None
        found = _SEMVER.search(done.stdout.decode("utf-8", "replace"))
        return found.group(1) if found and done.returncode == 0 else None

    def handle(self, msg: dict) -> None:
        method, rid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "session/cancel":
            self.cancel()
        elif rid is None:
            return  # an unknown notification
        elif method == "initialize":
            self.reply(rid, {"protocolVersion": 1, "agentCapabilities": {},
                             "agentInfo": {"name": "copilot-p-acp", "title": f"Copilot -p (adapter {VERSION})",
                                           "version": self.version()}})
        elif method == "session/new":
            self.session_id = str(uuid.uuid4())
            self.reply(rid, {"sessionId": self.session_id})
        elif method == "session/set_model":
            self.reply(rid, {})
        elif method == "session/prompt":
            if params.get("sessionId") != self.session_id or self.session_id is None:
                self.reply(rid, error={"code": -32602, "message": "unknown sessionId"})
            elif self.worker is not None and self.worker.is_alive():
                self.reply(rid, error={"code": -32600, "message": "a prompt is already running"})
            else:
                text = "\n".join(b.get("text", "") for b in params.get("prompt") or [] if b.get("type") == "text")
                self.cancelled = False  # here, not in the worker: a cancel read right after this prompt must stand
                self.worker = threading.Thread(target=self.prompt, args=(rid, text), daemon=True)
                self.worker.start()
        else:
            self.reply(rid, error={"code": -32601, "message": f"{method} is not served by copilot-p-acp"})

    def cancel(self) -> None:
        self.cancelled = True
        child = self.child
        if child is not None and child.poll() is None:
            # simplify: kills copilot itself; a grandchild it started (a shell) lives until the engine ends the cell's
            # job, which follows a cancel. Upgrade trigger: a cancelled turn whose grandchild still writes the workspace.
            child.kill()

    def prompt(self, rid, text: str) -> None:
        self.turns += 1
        resume = ["--resume", self.session_id] if self.turns > 1 else ["--session-id", self.session_id]
        argv = [*self.exe, "-p", text, *resume, *self.passthrough]
        env = dict(os.environ, COPILOT_AUTO_UPDATE="false")  # ADR-0028 s2: the pinned exe never updates itself
        if "COPILOT_HOME" not in env:
            self.reply(rid, error={"code": -32603, "message": "copilot-p-acp: COPILOT_HOME is not set"})
            return
        try:
            with open(Path(env["COPILOT_HOME"]) / f"copilot-p-turn{self.turns}.jsonl", "wb") as tee:
                code, last = self.run_child(argv, env, tee)
        except OSError as exc:  # no turn record, or no child: e.g. a command line over 32,767 characters (WinError 206)
            self.reply(rid, error={"code": -32603, "message": f"copilot-p-acp: the turn did not start: {exc}"})
            return
        result: dict = {"stopReason": stop_reason(code, last, self.cancelled)}
        usage = last.get("usage") if isinstance(last, dict) and last.get("type") == "result" else None
        if isinstance(usage, dict) and any(isinstance(usage.get(k), int) for k in TOKEN_KEYS):
            result["usage"] = usage
        self.reply(rid, result)

    def run_child(self, argv: list[str], env: dict, tee) -> tuple[int, dict | None]:
        """One copilot -p child: its stdout teed unchanged and announced line by line; its exit code and last object."""
        self.child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, env=env,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if self.cancelled:  # the cancel came while the child was starting
            self.child.kill()
        last = None
        for line in self.child.stdout:
            tee.write(line)
            try:
                obj = json.loads(line)
            except ValueError:
                obj = None
            last = obj if isinstance(obj, dict) else last
            self.send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": self.session_id, "update": {
                "sessionUpdate": "copilot_p_event", "type": obj.get("type") if isinstance(obj, dict) else None}}})
        return self.child.wait(), last


def stop_reason(code: int, last: dict | None, cancelled: bool) -> str:
    if cancelled:
        return "cancelled"
    if code == 0 and isinstance(last, dict) and last.get("type") == "result":
        return "end_turn"
    return "incomplete"


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "--exe" or "--" not in argv[2:]:
        print("usage: copilot_p_acp.py --exe <copilot argv prefix...> -- <copilot argv...>", file=sys.stderr)
        return 2
    split = argv.index("--", 1)
    adapter = Adapter(argv[1:split], argv[split + 1:], sys.stdout.buffer)
    for raw in sys.stdin.buffer:
        try:
            msg = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(msg, dict):
            adapter.handle(msg)
    if adapter.worker is not None:  # stdin closed: let a running prompt answer (a cancel already killed its child)
        adapter.worker.join()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
