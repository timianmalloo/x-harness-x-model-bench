"""S-04 probe driver: one ACP turn with the probe `ask_user` MCP server in `session/new` `mcpServers` (R-37 c1, c2).

The turn is built exactly as `tools/acp_record.py turn` builds one (the bench's own profile, pinned build, working
copy, the `record` tee and `driver.run_turn`), with three differences, all stated:
  1. `session/new` carries `mcpServers: [<the probe server>]` instead of `[]` (`driver.py:236`). `src/**` is not
     changed: the probe swaps `driver._Channel` for a subclass that rewrites that one request's params, for the
     duration of the turn only.
  2. The allowlist names the probe tool, as R-37 c2 says the real profile will: Claude Code gets
     `mcp__scripted_user__ask_user` in `permissions.allow`; Copilot gets `--allow-tool scripted_user`. Codex runs
     `agent-full-access` and gets nothing. `--no-allow` turns this off (then a permission request is the expected
     observation, and the driver refuses it as it always does).
  3. `--prompt probe` (the default) sends a short instruction to call `ask_user` once and repeat the reply;
     `--prompt a1` sends `tasks/A1/prompt.md` verbatim (R-37 c1: "whether one A1 turn calls it").
Copilot only: `--copilot-disable-builtin-mcps` appends the ADR-0004:58 flag, which the profile does not carry today.

`--handshake-only` stops at the ack barrier: `initialize`, `session/new` (+ `set_model`), then it waits up to
`--server-wait` seconds for the server to be listed, and never sends a prompt, so no model turn is spent. A server
listed in that window is proof the adapter started it; a server not listed is not proof of the contrary (a harness
may start MCP servers lazily, at the first prompt).

Usage (from the repository root; the models are stipulated, R-33, never defaulted):
  uv run python tests/fixtures/acp/scripted-user/probe_turn.py run --harness H --model M
      [--prompt probe|a1] [--handshake-only] [--server-wait S] [--copilot-disable-builtin-mcps] [--no-allow]
      [--tools-dir D] [--cells-root D] [--out-dir D] [--budget S] [--handshake S] [--dry-run]
  python tests/fixtures/acp/scripted-user/probe_turn.py analyse --summary SUMMARY.json
      Re-derive a summary offline from the files it names (the recording, the server log, the native records).

Outputs, per run, in --out-dir (default <cells-root>/s04-probe), named <label> = <harness>-<variant>-<UTC stamp>:
  <label>.jsonl          the full ACP recording (acp-recording/1; raw, never committed unscrubbed)
  <label>.stderr.log     the adapter's stderr (never committed)
  <label>.server.jsonl   the probe server's log: every MCP message it received and sent
  <label>.summary.json   the measured facts (below); printed to stdout too
The cell folder (<cells-root>/s04-probe-<label>/) keeps the harness home with its native records; the credential
copy is deleted after the turn, as in `acp_record.py`.

Summary facts (R-37 c1): the `mcpServers` shape sent; whether `session/new` accepted it (or its error); whether the
server was started (a `start` record) and how its log path arrived (`env` or `arg`); whether it was listed
(`tools/list`); whether the tool appears in the ACP stream and in the native record; whether the model called it
(`tools/call` received) with each question and the reply sent; whether the reply reached the model (the probe
reply's token in the agent's text, `--prompt probe` only); permission requests, and those that name the tool.
Exit status: 0 when the server received at least one `tools/call` (or, with --handshake-only, a `tools/list`); else 1.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SERVER = HERE / "probe_server.py"
RECORDER = ROOT / "tools" / "acp_record.py"
SERVER_NAME = "scripted_user"  # an underscore, not a hyphen: it becomes part of each harness's tool id
TOOL = "ask_user"
LOG_ENV = "SCRIPTED_USER_PROBE_LOG"
MODELS = {"claude-code": "claude-opus-5-5", "codex": "gpt-6-sol", "copilot": "gpt-6-sol"}  # R-33, for the check only
PROBE_TOKEN = "S04-TOKEN-4417"
PROBE_REPLY = f"The probe token is {PROBE_TOKEN}."
A1_REPLY = "Decide and state your assumption."  # the US-10 default reply, verbatim
PROBE_PROMPT = (
    "This is a connectivity check, not a coding task.\n\n"
    "Call the `ask_user` tool exactly once, with the question \"What is the probe token?\". "
    "Then reply with the tool's answer, verbatim, and stop. Do not edit any file and do not run any command.\n"
)
CLAUDE_TOOL_ID = f"mcp__{SERVER_NAME}__{TOOL}"
# assume: Claude Code names an MCP tool mcp__<server>__<tool>. Confirm: the account connectors in this repo's own
# native records are named mcp__claude_ai_<Name>__<tool> (R-36), and the probe's native record lists this id.
# Breaks: the id differs, the allowlist misses it, and the model's call becomes a permission request, which the
# summary records by title (`permission_requests_naming_tool`), so a wrong id is visible, never silent.
COPILOT_ALLOW = SERVER_NAME
# assume: `--allow-tool <server>` allows every tool of that MCP server. Confirm: copilot 1.0.89-1 `--help`:
# "Allow all but one specific tool from MCP server with name "MyMCP": --deny-tool='MyMCP(denied_tool)'
# --allow-tool='MyMCP'" (read 2026-09-25). Breaks: as above, a permission request naming the tool.


class HandshakeOnly(Exception):
    """Raised at the ack barrier so the prompt is never sent (driver.run_turn propagates it unsent)."""


def mcp_servers(python: str, server_log: Path, reply: str) -> list[dict]:
    """The ACP `McpServerStdio` shape (ACP schema: name, command, args, env[{name, value}], no `type`).
    claude-agent-acp 0.81.2 maps an entry without `type` to stdio (acp-agent.js:6227); codex-acp 1.12.0 parses it
    with `zMcpServerStdio` and silently skips an entry that fails the schema (index.js:19535, `vecSkipError`)."""
    return [{"name": SERVER_NAME, "command": python,
             "args": [str(SERVER), "--log", str(server_log), "--reply", reply],
             "env": [{"name": LOG_ENV, "value": str(server_log)}]}]


@contextlib.contextmanager
def session_mcp_servers(driver_module, servers: list[dict]):
    """Swap driver._Channel for the duration of one turn so `session/new` carries `servers`."""
    base = driver_module._Channel

    class ProbeChannel(base):
        def rpc(self, method, params, deadline):
            if method == "session/new":
                params = {**params, "mcpServers": servers}
            return super().rpc(method, params, deadline)

    driver_module._Channel = ProbeChannel
    try:
        yield
    finally:
        driver_module._Channel = base


def allow_probe_tool(profile, harness: str, extra_argv: list[str]):
    """R-37 c2 for the probe: the profile's allowlist plus the probe tool id."""
    if harness == "claude-code":
        settings = json.loads(profile.files["settings.json"])
        settings["permissions"]["allow"] = [*settings["permissions"]["allow"], CLAUDE_TOOL_ID]
        return dataclasses.replace(profile, files={**profile.files, "settings.json": json.dumps(settings)})
    if harness == "copilot":
        extra_argv += ["--allow-tool", COPILOT_ALLOW]
    return profile


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _messages(recording: list[dict]) -> list[tuple[str, dict]]:
    """(direction, JSON-RPC message) for every complete recorded line that parses as a JSON object."""
    out = []
    for r in recording:
        if r.get("kind") == "line" and r.get("nl") and "text" in r:
            try:
                msg = json.loads(r["text"])
            except ValueError:
                continue
            if isinstance(msg, dict):
                out.append((r["dir"], msg))
    return out


def analyse(recording_path: Path, server_log_path: Path, native_paths: list[Path], token: str | None) -> dict:
    """The measured facts of one probe turn, from its files only (offline; the self-test runs it)."""
    msgs = _messages(_load_jsonl(recording_path))
    facts: dict = {}
    # initialize: what the agent says it supports for MCP
    init_id = next((m.get("id") for d, m in msgs if d == "to_agent" and m.get("method") == "initialize"), None)
    init = next((m for d, m in msgs if d == "to_client" and "method" not in m and m.get("id") == init_id), {})
    caps = ((init.get("result") or {}).get("agentCapabilities") or {})
    facts["agent_mcp_capabilities"] = caps.get("mcpCapabilities")
    # session/new: the shape sent, and the answer
    new_req = next((m for d, m in msgs if d == "to_agent" and m.get("method") == "session/new"), None)
    facts["mcp_servers_sent"] = ((new_req or {}).get("params") or {}).get("mcpServers")
    new_resp = next((m for d, m in msgs if d == "to_client" and "method" not in m and new_req is not None
                     and m.get("id") == new_req.get("id")), None)
    if new_resp is None:
        facts["session_new"] = {"status": "no answer recorded"}
    elif "error" in new_resp:
        facts["session_new"] = {"status": "error", "error": new_resp["error"]}
    else:
        facts["session_new"] = {"status": "accepted", "session_id": (new_resp.get("result") or {}).get("sessionId")}
    # the ACP stream: tool calls, permission requests and any other update that names the server or the tool
    tool_updates, other_mentions, agent_text, perms = [], [], [], []
    for d, m in msgs:
        if d != "to_client":
            continue
        text = json.dumps(m, ensure_ascii=False)
        if m.get("method") == "session/request_permission":
            call = (m.get("params") or {}).get("toolCall") or {}
            perms.append({"title": call.get("title"), "names_tool": TOOL in text or SERVER_NAME in text})
            continue
        if m.get("method") != "session/update":
            continue
        update = (m.get("params") or {}).get("update") or {}
        kind = update.get("sessionUpdate")
        if kind == "agent_message_chunk" and isinstance((update.get("content") or {}).get("text"), str):
            agent_text.append(update["content"]["text"])
        elif kind in ("tool_call", "tool_call_update") and (TOOL in text or SERVER_NAME in text):
            tool_updates.append({k: update.get(k) for k in ("sessionUpdate", "toolCallId", "title", "kind", "status", "name")})
        elif TOOL in text or SERVER_NAME in text:
            other_mentions.append({"sessionUpdate": kind, "text": text[:600]})
    joined = "".join(agent_text)
    facts["acp_tool_call_updates"] = tool_updates
    facts["tool_in_acp_stream"] = bool(tool_updates)
    facts["acp_other_mentions"] = other_mentions[:10]
    facts["permission_requests"] = len(perms)
    facts["permission_request_titles"] = [p["title"] for p in perms]  # e.g. a ToolSearch gate before a deferred tool
    facts["permission_requests_naming_tool"] = [p for p in perms if p["names_tool"]]
    facts["agent_text_tail"] = joined[-1500:]
    facts["reply_token_in_agent_text"] = (token in joined) if token else None
    # the probe server's own log: the ground truth for started, listed and called
    log = _load_jsonl(server_log_path)
    starts = [r for r in log if r.get("kind") == "start"]
    ins = [r["msg"] for r in log if r.get("kind") == "in" and isinstance(r.get("msg"), dict)]
    outs = {r["msg"].get("id"): r["msg"] for r in log if r.get("kind") == "out" and isinstance(r.get("msg"), dict)}
    init_in = next((m for m in ins if m.get("method") == "initialize"), None)
    calls = []
    for m in ins:
        if m.get("method") == "tools/call":
            params = m.get("params") or {}
            answer = outs.get(m.get("id")) or {}
            content = ((answer.get("result") or {}).get("content") or [{}])
            calls.append({"tool": params.get("name"), "question": (params.get("arguments") or {}).get("question"),
                          "reply": content[0].get("text") if content else None, "error": answer.get("error")})
    facts["server_started"] = bool(starts)
    facts["server_starts"] = len(starts)
    facts["server_log_source"] = starts[0].get("log_source") if starts else None
    facts["server_initialize"] = ({"protocolVersion": (init_in.get("params") or {}).get("protocolVersion"),
                                   "clientInfo": (init_in.get("params") or {}).get("clientInfo")} if init_in else None)
    facts["tool_listed"] = any(m.get("method") == "tools/list" for m in ins)
    facts["server_methods"] = sorted({m.get("method") for m in ins if isinstance(m.get("method"), str)})
    facts["model_called_tool"] = bool(calls)
    facts["calls"] = calls
    facts["log_record"] = ({"calls": calls} if calls else {"calls": [], "note": "no question asked"})
    # the native record: every line that names the tool (R-37 c1: "whether the tool appears in the native record")
    hits, snippets = 0, []
    for path in native_paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if TOOL in line:
                hits += 1
                if len(snippets) < 3:
                    at = line.find(TOOL)
                    snippets.append(line[max(0, at - 200):at + 200])
    facts["native_records"] = [p.name for p in native_paths]
    facts["tool_in_native_record"] = hits > 0 if native_paths else None  # null: no native record found, not "no"
    facts["native_record_lines_naming_tool"] = hits
    facts["native_record_snippets"] = snippets
    return facts


def _variant(args: argparse.Namespace) -> str:
    parts = [args.prompt]
    if args.handshake_only:
        parts.append("handshake")
    if args.harness == "copilot":
        parts.append("dbm" if args.copilot_disable_builtin_mcps else "profile-flags")
    if args.no_allow:
        parts.append("noallow")
    return "-".join(parts)


def _wait_for_listing(server_log: Path, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if any(r.get("kind") == "in" and (r.get("msg") or {}).get("method") == "tools/list" for r in _load_jsonl(server_log)):
            return
        time.sleep(0.5)


def run(args: argparse.Namespace) -> int:
    from harness_bench import driver, procs, profiles, tools, workspace
    from harness_bench.plan import _prompt

    if args.harness in MODELS and args.model != MODELS[args.harness]:
        print(f"note: {args.harness} is stipulated as {MODELS[args.harness]} for S-04 (R-33); running {args.model} as asked",
              file=sys.stderr)
    task_dir, cells_root = ROOT / "tasks" / "A1", Path(args.cells_root)
    out_dir = Path(args.out_dir) if args.out_dir else cells_root / "s04-probe"
    label = f"{args.harness}-{_variant(args)}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    rec, server_log = (out_dir / f"{label}.jsonl").resolve(), (out_dir / f"{label}.server.jsonl").resolve()
    profile = profiles.load(ROOT, args.harness)
    extra: list[str] = []
    if not args.no_allow:
        profile = allow_probe_tool(profile, args.harness, extra)
    if args.harness == "copilot" and args.copilot_disable_builtin_mcps:
        extra.append("--disable-builtin-mcps")
    build = tools.resolve(Path(args.tools_dir))[args.harness]
    argv = [*profile.argv(build, args.model), *extra]
    token, reply = (PROBE_TOKEN, PROBE_REPLY) if args.prompt == "probe" else (None, A1_REPLY)
    prompt = PROBE_PROMPT if args.prompt == "probe" else _prompt(task_dir)["prompt"]
    servers = mcp_servers(sys.executable, server_log, reply)
    if args.dry_run:
        print(json.dumps({"label": label, "argv": argv, "mcpServers": servers, "set_model": profile.set_model,
                          "mode": profile.mode, "settings": profile.files.get("settings.json"),
                          "prompt": prompt, "recording": str(rec), "build": build.record()}, indent=1))
        return 0
    workspace.check_cells_root(cells_root)  # HB-PRE-002: no instruction file above the cell
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_dir = cells_root / f"s04-probe-{label}"
    home, ws = cell_dir / "home", cell_dir / "ws"
    workspace.cell_working_copy(workspace.task_source(task_dir, "capture", cell_dir / "source"), ws)
    env = profile.cell_env(dict(os.environ), home, build, args.model, "")
    profile.seed_home(home, args.model)
    result = driver.TurnResult()
    stopped_at_barrier = False

    def barrier(session_id):
        if args.handshake_only:
            _wait_for_listing(server_log, args.server_wait)
            raise HandshakeOnly(session_id)

    try:
        with rec.with_suffix(".stderr.log").open("wb") as err:
            cell = procs.spawn([sys.executable, str(RECORDER), "record", "--out", str(rec), "--", *argv],
                               cwd=str(ws), env=env, stderr=err)
            budget = threading.Timer(args.budget, lambda: cell.terminate_and_confirm(timeout=30))
            budget.start()
            try:
                with session_mcp_servers(driver, servers):
                    try:
                        result = driver.run_turn(cell, cwd=ws, prompt=prompt, mode=profile.mode,
                                                 handshake_timeout=args.handshake, before_send=barrier,
                                                 model=args.model if profile.set_model else None, result=result)
                    except HandshakeOnly:
                        stopped_at_barrier = True
                cell.proc.stdin.close()  # a clean end: the adapter sees EOF
                try:
                    cell.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                budget.cancel()
                cell.terminate_and_confirm(timeout=30)
                cell.close()
    finally:
        profile.clean_home(home)  # the credential copy never outlives the turn
    native = profile.native_records(home, result.session_id) if result.session_id else []
    summary = {"format": "s04-probe/1", "label": label, "harness": args.harness, "model": args.model,
               "prompt_kind": args.prompt, "handshake_only": args.handshake_only, "stopped_at_barrier": stopped_at_barrier,
               "copilot_disable_builtin_mcps": bool(args.copilot_disable_builtin_mcps), "allow_probe_tool": not args.no_allow,
               "extra_argv": extra, "build": build.record(), "captured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
               "files": {"recording": str(rec), "server_log": str(server_log), "cell_dir": str(cell_dir),
                         "native_records": [str(p) for p in native]},
               "turn": {"stop_reason": result.stop_reason, "cause": result.cause.code if result.cause else None,
                        "detail": result.detail[:500], "session_id": result.session_id, "prompt_sent": result.prompt_sent,
                        "permission_requests": result.permission_requests, "updates": result.updates,
                        "agent_version": result.agent_version, "turn_seconds": round(result.turn_seconds, 1)},
               "token": token,
               "facts": analyse(rec, server_log, native, token)}
    path = out_dir / f"{label}.summary.json"
    path.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    facts = summary["facts"]
    return 0 if (facts["tool_listed"] if args.handshake_only else facts["model_called_tool"]) else 1


def reanalyse(summary_path: Path) -> int:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    files = summary["files"]
    summary["facts"] = analyse(Path(files["recording"]), Path(files["server_log"]),
                               [Path(p) for p in files["native_records"]], summary.get("token"))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="probe_turn.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="one probe turn")
    r.add_argument("--harness", required=True, choices=sorted(MODELS))
    r.add_argument("--model", required=True, help="stipulated per R-33; never defaulted")
    r.add_argument("--prompt", choices=("probe", "a1"), default="probe")
    r.add_argument("--handshake-only", action="store_true")
    r.add_argument("--server-wait", type=float, default=30.0, help="seconds to wait for tools/list (handshake-only)")
    r.add_argument("--copilot-disable-builtin-mcps", action="store_true")
    r.add_argument("--no-allow", action="store_true", help="do not add the probe tool to the allowlist")
    r.add_argument("--tools-dir", default=str(ROOT / ".tools" / "harness"))
    r.add_argument("--cells-root", default=str(ROOT.parent / "bench-cells"))
    r.add_argument("--out-dir", default=None)
    r.add_argument("--budget", type=float, default=600.0, help="seconds before the cell is ended (default 600)")
    r.add_argument("--handshake", type=float, default=60.0, help="handshake deadline in seconds")
    r.add_argument("--dry-run", action="store_true", help="print the argv, mcpServers and prompt; spawn nothing")
    a = sub.add_parser("analyse", help="re-derive a summary from its files")
    a.add_argument("--summary", required=True)
    args = p.parse_args(argv)
    if args.command == "analyse":
        return reanalyse(Path(args.summary))
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
