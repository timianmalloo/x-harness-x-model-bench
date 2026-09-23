#!/usr/bin/env python3
"""reread-guard.py — the re-read guard hook (defect class CTX-D), for Claude Code, Copilot CLI, Grok Build, and Antigravity (agy).

The shape it catches, measured on a profiled session: the same file viewed four times in three
minutes (140 KB re-entering the context), a 43 KB paged tool output viewed whole twice, and a
sub-agent reading one mockup six times. None of it errors; all of it is paid for on every later
request. A prose rule ("check whether you already have it") is a memoir (CI6). This is the
control: it runs at the pre-tool-use seam, counts identical reads per turn, and speaks up on the
third — a WARNING to the model, never a block, because a genuine third read exists.

Host adapters (one script, four payloads — established from the hosts' own contracts):
  Claude Code   stdin {"hook_event_name","session_id","tool_name","tool_input":{"file_path"}}
                warn: exit 0 + {"hookSpecificOutput":{"hookEventName":"PreToolUse","systemMessage":...}}
  Copilot CLI   stdin {"sessionId","toolName","toolArgs":{"path","view_range"}} (one call per invocation)
                warn: exit 0 + {"additionalContext": ...}   (never exit 2 on preToolUse: that denies)
  Grok Build    stdin camelCase with Claude aliases: {"hookEventName"/"hook_event_name",
                "sessionId"/"session_id","toolName"/"tool_name",
                "toolInput":{"target_file"|"file_path"|"path"}}
                warn: exit 0 + {"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":...}}
                (`Read` in a matcher aliases to `read_file`; the script accepts both tool names.)
  Antigravity   stdin {"toolCall":{"name":"view_file","args":{"AbsolutePath"}},"conversationId"}
                warn: exit 0 + {"decision":"allow","reason":...}
The turn boundary is the prompt-submit event (UserPromptSubmit / userPromptSubmitted), which
resets the counter. State lives in a per-session file under the OS temp dir. Every failure
path is fail-OPEN: a broken guard must never cost a tool call (a hook that blocks by accident
is worse than no hook).

Usage (from the host's hook config):  reread-guard.py --host claude|copilot|grok|agy [--threshold 3]
"""
import argparse
import json
import os
import re
import sys
import tempfile

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

PAGED_OUTPUT_RX = re.compile(r"copilot-tool-output-[0-9a-f-]+\.txt$", re.I)
READ_TOOLS = {"claude": {"Read"}, "copilot": {"view"}, "grok": {"read_file", "Read"}, "agy": {"view_file"}}


def state_path(session):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "unknown")[:80]
    return os.path.join(tempfile.gettempdir(), "ai-forward-reread-guard-{0}.json".format(safe))


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def normalize(p):
    return os.path.normcase(os.path.normpath(p)) if p else ""


def evaluate(host, payload, threshold=3, state=None):
    """Pure decision: returns (new_state, warning_or_None). Exercised directly by the tests."""
    state = dict(state or {})
    if host == "claude":
        event = payload.get("hook_event_name") or ""
        if event == "UserPromptSubmit":
            return {}, None
        tool = payload.get("tool_name") or ""
        args = payload.get("tool_input") or {}
        path = args.get("file_path") or args.get("path") or ""
        ranged = bool(args.get("offset") or args.get("limit"))
    elif host == "grok":
        event = payload.get("hook_event_name") or payload.get("hookEventName") or ""
        if event in ("UserPromptSubmit", "user_prompt_submit"):
            return {}, None
        tool = payload.get("tool_name") or payload.get("toolName") or ""
        args = payload.get("tool_input") or payload.get("toolInput") or {}
        path = args.get("target_file") or args.get("file_path") or args.get("path") or ""
        ranged = bool(args.get("offset") or args.get("limit"))
    elif host == "agy":
        event = payload.get("hook_event_name") or payload.get("hookEventName") or ""
        if event in ("UserPromptSubmit", "user_prompt_submit", "PreInvocation"):
            return {}, None
        tool_call = payload.get("toolCall") or {}
        tool = tool_call.get("name") or payload.get("tool_name") or ""
        args = tool_call.get("args") or payload.get("tool_input") or {}
        path = args.get("AbsolutePath") or args.get("path") or args.get("file_path") or ""
        ranged = bool(args.get("StartLine") or args.get("EndLine"))
    else:
        if "prompt" in payload and "toolName" not in payload:  # userPromptSubmitted
            return {}, None
        tool = payload.get("toolName") or ""
        args = payload.get("toolArgs") or {}
        path = args.get("path") or ""
        ranged = bool(args.get("view_range"))
    if tool not in READ_TOOLS.get(host, set()) or not path:
        return state, None
    key = normalize(path)
    counts = state.setdefault("reads", {})
    counts[key] = counts.get(key, 0) + 1
    n = counts[key]
    warning = None
    if PAGED_OUTPUT_RX.search(key) and not ranged:
        warning = ("re-read guard: '{0}' is a paged tool output being viewed whole ({1} time{2} this turn). "
                   "Its content was already produced by the tool that wrote it; read only the range you need."
                   .format(os.path.basename(path), n, "" if n == 1 else "s"))
    elif n >= threshold:
        warning = ("re-read guard: '{0}' has now been read {1} times in this turn. Its contents are already in "
                   "your context; re-use what you have (or read only the lines that changed). A third identical "
                   "read is defect class CTX-D."
                   .format(os.path.basename(path), n))
    return state, warning


def emit(host, warning):
    if host == "agy":
        payload = {"decision": "allow"}
        if warning:
            payload["reason"] = warning
        print(json.dumps(payload))
        return
    if not warning:
        return
    if host == "claude":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "systemMessage": warning}}))
    elif host == "grok":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": warning}}))
    else:
        print(json.dumps({"additionalContext": warning}))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", choices=["claude", "copilot", "grok", "agy"], required=True)
    ap.add_argument("--threshold", type=int, default=3)
    args = ap.parse_args(argv)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0  # fail open
    if not isinstance(payload, dict):
        return 0
    session = payload.get("conversationId") or payload.get("session_id") or payload.get("sessionId") or "unknown"
    path = state_path(session)
    state, warning = evaluate(args.host, payload, args.threshold, load(path))
    save(path, state)
    emit(args.host, warning)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a guard must never break the host's tool call
        sys.exit(0)
