#!/usr/bin/env python3
"""session-start.py - the audit marker, set by the HOST at the session seam (DC-190).

`audit-log.py start` is a skill's first action so its closing entry measures the run
(AL4a). Prose that says "mark first" is a memoir (CI6): measured in one programme, a node
grounded for minutes before it marked and reported a duration from the wrong instant, and
six resumed nodes' second runs set no marker at all. This hook runs on Claude Code's
`SessionStart` and `SubagentStart` events and records the instant the session actually
began, before any model action.

What it writes. `audit-log.py start`, keyed:
  - to `$AGENT_SESSION` when the harness environment carries one (the closing `append`
    names the same id, so this is the ordinary marker);
  - otherwise to a HARNESS slot (`__harness__:<session_id>[/<agent_id>]`). `append` uses
    that slot only when the entry's own session/skill marker is absent, records
    `duration_source: session-start-hook`, and consumes it - one marker measures one run.

Contract (from the hooks reference, read 2026-09-14): stdin carries `hook_event_name`,
`session_id`, `cwd`, and on `SubagentStart` `agent_id` + `agent_type`; a handler runs in
the session's current directory; SessionStart cannot block. This hook prints nothing to
stdout (stdout is added to the model's context) and exits 0 on every path, including its
own failures.

Usage:  python docs/ai-forward-pack/hooks/session-start.py --host claude|grok|agy|copilot
Grok Build sends camelCase keys (`sessionId`, `agentId`, `workspaceRoot`) with Claude
aliases (`session_id`, `agent_id`, `cwd`); Antigravity sends `conversationId`,
`workspacePaths`, and `invocationNum`; Copilot sessionStart uses camelCase session keys.
Documented Copilot subagentStart currently lacks a stable child id, so unattributed
subagentStart is ignored rather than consuming the parent's marker.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from coord_identity import copilot_child_identity_from_payload, parent_session

# The host pipes a JSON payload in and reads a JSON line out. On Windows both ends default
# to the console code page, so a non-ASCII path arrives mojibake or raises (DC-211/PLAT-A).
# Every arm is fail-open: a guard that cannot reconfigure still runs.
for _stream, _kw in ((sys.stdin, {"encoding": "utf-8", "errors": "replace"}),
                     (sys.stdout, {"encoding": "utf-8", "errors": "replace"}),
                     (sys.stderr, {"encoding": "utf-8", "errors": "replace"})):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(**_kw)
        except (ValueError, OSError, UnicodeError):
            pass


def _audit_script(here):
    """audit-log.py, resolved from the hook's own location: the deployed layout first
    (docs/ai-forward-pack/{hooks,scripts}), then the pack source (pack/adapters/hooks vs
    pack/scripts), then the cwd's deployed copy."""
    candidates = [
        os.path.join(here, "..", "scripts", "audit-log.py"),
        os.path.join(here, "..", "..", "scripts", "audit-log.py"),
        os.path.join(os.getcwd(), "docs", "ai-forward-pack", "scripts", "audit-log.py"),
    ]
    for c in candidates:
        c = os.path.abspath(c)
        if os.path.isfile(c):
            return c
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", choices=["claude", "grok", "agy", "copilot"], default="claude")
    args = parser.parse_args()
    try:
        if args.host == "claude" and os.environ.get("AGENT_HOST") == "copilot":
            return 0
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
        if args.host == "agy":
            inv_num = payload.get("invocationNum")
            if inv_num is not None and inv_num != 1:
                return 0
        session_id = str(payload.get("conversationId") or payload.get("session_id") or payload.get("sessionId") or "").strip()
        if not session_id:
            return 0
        agent_id = str(payload.get("agent_id") or payload.get("agentId") or "").strip()
        workspaces = payload.get("workspacePaths") or []
        cwd = workspaces[0] if workspaces else (payload.get("cwd") or payload.get("workspaceRoot") or os.getcwd())
        docs = os.path.join(cwd, "docs")
        if not os.path.isdir(docs):
            return 0
        script = _audit_script(os.path.dirname(os.path.abspath(__file__)))
        if not script:
            return 0
        session = parent_session(os.environ.get("AGENT_SESSION"))
        if os.environ.get("AGENT_SESSION") and not session:
            return 0
        child_session = copilot_child_identity_from_payload(payload) if args.host == "copilot" else None
        if args.host == "copilot" and event == "subagentStart" and child_session is None:
            return 0
        if args.host == "copilot" and (payload.get("agentId") or payload.get("agent_id")) and not child_session:
            return 0
        if child_session:
            session = child_session
        command = [sys.executable, script, "--root", docs, "start"]
        if session:
            command += ["--session", session]
        else:
            command += ["--harness", session_id + ("/" + agent_id if agent_id else "")]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=15)
    except Exception:  # noqa: BLE001 - fail-open: a hook must never fail the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
