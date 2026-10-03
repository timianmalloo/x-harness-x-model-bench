#!/usr/bin/env python3
"""git-identity-guard.py -- PK-07's mechanical control: never invent a git identity.

AL0.2 states the rule in prose: neither a pack script nor the agent running it may run
`git config user.*` (or an inline `git -c user.*=...`) to force a blocked commit through;
a failed commit is left uncommitted and the gap is reported. A sweep test
(`tests/docs_explorer/test_no_git_identity.py`) already pins this against the PACK'S OWN
source. This hook is the second half: it runs at the PreToolUse seam in a CONSUMING repo
and refuses the shell command itself, so the rule holds even when the agent forgets it.

It does not filter by tool name (Bash, run_terminal_cmd, ... differ per host and are not
all verified in this pack) -- it inspects whatever command-like string the tool call
carries (`command`/`cmd`/`script`/`shellCommand`/`commandLine`, the shapes already used
elsewhere in this hook family) and matches only the narrow git-identity-SET pattern:
`git config [--global|--local|--system] [--add] user.name/email <value>`, or an inline
`-c user.name=...` / `-c user.email=...`. A bare `git config user.name` (reading, not
setting) never matches, so a legitimate check-before-you-commit is never refused.

Per-host block form (grounded from the hosts' own contracts the rest of this hook family
already relies on, `pack/adapters/hooks/README.md`):
  Claude Code   PreToolUse: exit 2, reason on stderr -- blocks the call.
  Grok Build    Claude-format PreToolUse: exit 2, reason on stderr -- blocks the call.
  Copilot CLI   preToolUse: exit 2 denies the call (reread-guard.py's own documented
                "never exit 2 on preToolUse: that denies"); reason on stderr.
  Antigravity   has a PreToolUse event (reread-guard's own `view_file` matcher proves
                it fires), but this pack has never observed agy's PreToolUse DENY
                contract (only `{"decision":"allow"}` is verified, by reread-guard).
                Rather than guess a deny shape that might silently fail open OR block
                everything it touches, agy is left unwired here; PK-07 stays prose-only
                for agy (AL0.2, `audit-and-change-log.md`).

Usage: git-identity-guard.py --host claude|grok|copilot
"""
import argparse
import json
import re
import sys

# The host pipes a JSON payload in and reads a line out. Same console-encoding guard as
# every other hook in this family (DC-211/PLAT-A): every arm is fail-open.
for _stream, _kw in ((sys.stdin, {"encoding": "utf-8", "errors": "replace"}),
                     (sys.stdout, {"encoding": "utf-8", "errors": "replace"}),
                     (sys.stderr, {"encoding": "utf-8", "errors": "replace"})):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(**_kw)
        except (ValueError, OSError, UnicodeError):
            pass

COMMAND_KEYS = ("command", "cmd", "script", "shellCommand", "commandLine")

# `git config [...] user.name/email <value>` (a value follows -- reading alone never
# matches, nor does a read followed by a shell operator or redirect: `&&`, `||`, `|`, `;`,
# `>`, `<`, `2>`) or the inline per-invocation override `-c user.name=...`/`-c user.email=...`.
GIT_IDENTITY_SET_RX = re.compile(
    r"git\s+config\s+(?:--global\s+|--local\s+|--system\s+)?(?:--add\s+)?"
    r"user\.(?:name|email)\s*(?:=|\s+(?![|&;<>]|\d+>)\S)"
    r"|-c\s+user\.(?:name|email)\s*=",
    re.IGNORECASE,
)

REASON = ("git-identity guard (PK-07): this command sets a git identity (user.name/user.email) "
          "to force a commit through. Leave the change uncommitted and report the gap instead "
          "of inventing an author -- AL0.2.")


def _command_text(host, payload):
    """The command-like string from whatever shape this host's tool-call args take. Not
    filtered by tool name (that varies per host and is unverified for several of them);
    any tool call carrying one of COMMAND_KEYS is inspected."""
    if host in ("claude", "grok"):
        event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
        if event and event != "PreToolUse":
            return None
        args = payload.get("tool_input") or payload.get("toolInput") or {}
    elif host == "copilot":
        args = payload.get("toolArgs") or {}
    else:
        args = {}
    for key in COMMAND_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def evaluate(host, payload):
    """Pure decision: returns a reason string to block on, or None to allow. Exercised
    directly by the tests."""
    command = _command_text(host, payload)
    if not command:
        return None
    if GIT_IDENTITY_SET_RX.search(command):
        return REASON
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", choices=["claude", "copilot", "grok"], required=True)
    args = ap.parse_args(argv)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0  # fail open: an unreadable payload must never block a real tool call
    if not isinstance(payload, dict):
        return 0
    reason = evaluate(args.host, payload)
    if not reason:
        return 0
    print(reason, file=sys.stderr)
    return 2  # claude, grok (Claude-format) and copilot all deny preToolUse on exit 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a guard must never break the host's tool call
        sys.exit(0)
