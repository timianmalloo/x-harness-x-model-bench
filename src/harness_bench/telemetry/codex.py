"""Codex native record: `sessions/YYYY/MM/DD/rollout-*-<session id>.jsonl` (spike 1.2, W3; golden fixture 2026-09-23).

- The model comes from the latest `turn_context`.
- Each API call is an `event_msg`/`token_count` with `info.last_token_usage`; a repeated event with an
  unchanged `total_token_usage` is not a new call. OpenAI-style `input_tokens` includes cached tokens,
  so uncached = input - cached (ADR-0006 disjoint buckets). Reasoning is a component of output.
- The record is complete for this harness (profile usage_source native_record); the adapter's prompt
  response reports only the last call.
- Tool calls are `response_item` `custom_tool_call` / `function_call` / `local_shell_call`, closed by
  their `*_output` row with the same `call_id`; a `web_search_call` is a standalone out-of-profile row.
- Code-mode MCP calls also appear as `event_msg` `item_completed` / `McpToolCall` items. Their
  server and tool fields form one server-qualified, out-of-profile tool row.
- An error is `event_msg`/`task_complete` with `error.message`, which embeds a JSON body with `status`
  and `error.type` (probe W3). When that body has no status field, `unexpected status NNN` in the text
  is the status. The message stored on the row is the CLI text, unchanged.
- The first user message that is not tagged system context (`<environment_context>` and the like) is
  the prompt (US-10). A pack-on cell's first user message also carries a harness-injected AGENTS.md
  block shaped `# AGENTS.md instructions for <cwd>\n\n<INSTRUCTIONS>\n...\n</INSTRUCTIONS>`; that block
  is context too, and is skipped the same way (real E2E, US-10, T8 defect 1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    MissingField,
    ModelCall,
    ProcessTrace,
    ProviderError,
    ToolCall,
    ToolInput,
    as_dict,
    as_list,
    as_status,
    as_str,
    patch_header_paths,
    rows,
    unexpected_status,
)

CALL_TYPES = ("custom_tool_call", "function_call", "local_shell_call")
OUTPUT_TYPES = ("custom_tool_call_output", "function_call_output", "local_shell_call_output")
SHELL_NAMES = ("exec", "shell", "exec_command", "local_shell", "container.exec")
EDIT_NAMES = ("apply_patch", "write_file", "edit")
# R-74 item 5: the collaboration ids the pinned 0.156.0 system message names (ok.jsonl:4). qual-r74-codex-1 issued
# spawn_agent and wait_agent. Static here, as the Claude and Copilot readers; in profile only in a scenario-6 cell (views).
DELEGATE_NAMES = ("spawn_agent", "send_message", "followup_task", "wait_agent", "interrupt_agent", "list_agents")
MCP_CLASSES = {"scripted_user.ask_user": "scripted user"}  # R-37 c2: the task's own MCP tool; every other MCP call is other

# Quoted `key: value` pairs inside a call's own input text (design section 4.3). Verified 2026-09-24
# capture: a `custom_tool_call`'s `input` is not JSON -- it is a JS-source snippet, e.g.
# `tools.exec_command({cmd:'...', workdir:'...'})` or `tools.apply_patch("*** Begin Patch\n...")` -- so
# this reads key/value pairs by regex rather than by parsing JSON, tolerant of either quote character.
_KV = re.compile(r"""(?P<key>cmd|command|path|file_path)\s*:\s*(?P<q>['"])(?P<val>(?:\\.|(?!(?P=q)).)*)(?P=q)""")


def _is_injected_context(text: str) -> bool:
    """A harness-injected context part, not something the user (or the prompt) wrote: a `<tagged>`
    block, or the AGENTS.md instructions block Codex prepends for a pack-on cell (US-10)."""
    stripped = text.lstrip()
    return stripped.startswith(("<", "# AGENTS.md instructions for "))


def _open_call(kind: str, ptype, call_id: str | None) -> bool:
    """A `response_item` row that opens a tracked tool call: `function_call`, `custom_tool_call` or
    `local_shell_call` (R-85 conditions 1-2). The one predicate `read()`'s `ToolCall`s and
    `tool_inputs()`'s `ToolInput`s both key off for this call family -- out-of-band calls
    (`web_search_call`, an MCP `item_completed`) are each their own row kind and are not part of
    this walk (design section 4.3 names only the three `CALL_TYPES`; PI-T6 compares counts on a
    fixture with no out-of-band call)."""
    return kind == "response_item" and ptype in CALL_TYPES and call_id is not None


def _tool_class(name: str) -> str:
    if name in SHELL_NAMES:
        return "shell"
    if name in EDIT_NAMES:
        return "edit"
    if name in DELEGATE_NAMES:
        return "delegate"
    return "other"


def _parse_error(message: str) -> tuple[int | None, str]:
    """Status from a JSON body. With no status field, `unexpected status NNN` in the text is the status."""
    status, etype = None, "unknown"
    try:
        body = json.loads(message)
    except (ValueError, RecursionError):
        body = None
    if isinstance(body, dict):
        etype = as_str(as_dict(body.get("error")).get("type")) or as_str(body.get("type")) or "unknown"
        status = as_status(body.get("status"))
    if status is None:
        status = unexpected_status(message)
    return status, etype


def read(path: Path) -> Extraction:
    ex = Extraction()
    model = None
    last_total = None
    open_tools: dict[str, dict] = {}
    for n, row in rows(path, ex):
        kind = row.get("type")
        payload = as_dict(row.get("payload"))
        item = as_dict(payload.get("item"))
        ptype = payload.get("type")
        stamp = as_str(row.get("timestamp"))
        call_id = as_str(payload.get("call_id"))
        if kind == "session_meta" and ex.session_id is None:
            ex.session_id = as_str(payload.get("id")) or as_str(payload.get("session_id"))
        elif kind == "turn_context" and isinstance(payload.get("model"), str):
            model = payload["model"]
        elif kind == "event_msg" and ptype == "token_count":
            info = as_dict(payload.get("info"))
            total, last = info.get("total_token_usage"), as_dict(info.get("last_token_usage"))
            if not last or total == last_total:
                continue
            last_total = total
            if model is None:
                ex.missing.append(MissingField(n, "model"))
            cached = ex.count(n, last, "cached_input_tokens")
            ex.model_calls.append(ModelCall(n, model or "NOT_RECORDED", max(ex.count(n, last, "input_tokens") - cached, 0), cached,
                                            ex.count(n, last, "cache_write_input_tokens"), ex.count(n, last, "output_tokens"),
                                            ex.count(n, last, "reasoning_output_tokens"), stamp, stamp))
        elif kind == "event_msg" and ptype == "task_complete":
            err = as_dict(payload.get("error"))
            if err:
                message = as_str(err.get("message")) or ""
                status, etype = _parse_error(message)
                ex.errors.append(ProviderError(n, status, etype, message[:300]))
        elif kind == "response_item" and ptype == "message" and payload.get("role") == "user" and ex.first_user_text is None:
            texts = [c.get("text") for c in as_list(payload.get("content")) if isinstance(c, dict) and isinstance(c.get("text"), str)]
            if texts and not all(_is_injected_context(t) for t in texts):
                ex.first_user_text = "".join(t for t in texts if not _is_injected_context(t))
        elif kind == "response_item" and ptype == "web_search_call":
            ex.tool_calls.append(ToolCall(n, "web_search", "other", stamp,
                                          stamp if payload.get("status") == "completed" else None, None))
        elif kind == "event_msg" and ptype == "item_completed" and item.get("type") == "McpToolCall":
            server, tool = as_str(item.get("server")), as_str(item.get("tool"))
            if server and tool:
                ok = {"completed": True, "failed": False}.get(as_str(item.get("status")))
                name = f"{server}.{tool}"
                ex.tool_calls.append(ToolCall(n, name, MCP_CLASSES.get(name, "other"), None, stamp, ok))
        elif _open_call(kind, ptype, call_id):
            open_tools[call_id] = {"n": n, "name": as_str(payload.get("name")) or ptype, "start": stamp}
        elif kind == "response_item" and ptype in OUTPUT_TYPES and call_id in open_tools:
            tool = open_tools.pop(call_id)
            ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], stamp, None))
    for tool in open_tools.values():
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    return ex


def _kv_fields(text: str) -> tuple[tuple[str, ...], str | None]:
    """`path`/`file_path`/`cmd`/`command` values from a call's own input text, plus any
    `apply_patch` header paths (design section 4.3). The first `cmd`/`command` match wins;
    every `path`/`file_path` match is kept."""
    paths: list[str] = []
    command: str | None = None
    for m in _KV.finditer(text):
        quote = m.group("q")
        value = m.group("val").replace(f"\\{quote}", quote)
        if m.group("key") in ("path", "file_path"):
            paths.append(value)
        elif command is None:
            command = value
    paths.extend(patch_header_paths(text))
    return tuple(paths), command


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from `function_call`/`custom_tool_call`/`local_shell_call` payloads (`_open_call`,
    the walker `read()`'s `ToolCall`s also key off -- R-85 condition 1), in native order, plus this
    record's own first assistant text block (design section 4.3, slice S2)."""
    ex = Extraction()
    first_text: str | None = None
    calls: list[ToolInput] = []
    for n, row in rows(path, ex):
        kind = row.get("type")
        if kind != "response_item":
            continue
        payload = as_dict(row.get("payload"))
        ptype = payload.get("type")
        call_id = as_str(payload.get("call_id"))
        if ptype == "message" and payload.get("role") == "assistant" and first_text is None:
            texts = [c.get("text") for c in as_list(payload.get("content")) if isinstance(c, dict) and isinstance(c.get("text"), str)]
            if texts:
                first_text = "".join(texts)
            continue
        if not _open_call(kind, ptype, call_id):
            continue
        name = as_str(payload.get("name")) or ptype
        arguments = payload.get("arguments")
        text = arguments if isinstance(arguments, str) else payload.get("input")
        text = text if isinstance(text, str) else ""
        paths, command = _kv_fields(text)
        calls.append(ToolInput(n, name, paths, command, bool(patch_header_paths(text))))
    return ProcessTrace(first_text, tuple(calls))
