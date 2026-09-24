"""Codex native record: `sessions/YYYY/MM/DD/rollout-*-<session id>.jsonl` (spike 1.2, W3; golden fixture 2026-09-23).

- The model comes from the latest `turn_context`.
- Each API call is an `event_msg`/`token_count` with `info.last_token_usage`; a repeated event with an
  unchanged `total_token_usage` is not a new call. OpenAI-style `input_tokens` includes cached tokens,
  so uncached = input - cached (ADR-0006 disjoint buckets). Reasoning is a component of output.
- The record is complete for this harness (profile usage_source native_record); the adapter's prompt
  response reports only the last call.
- Tool calls are `response_item` `custom_tool_call` / `function_call` / `local_shell_call`, closed by
  their `*_output` row with the same `call_id`.
- An error is `event_msg`/`task_complete` with `error.message`, which embeds a JSON body with `status`
  and `error.type` (probe W3).
- The first user message that is not tagged system context (`<environment_context>` and the like) is
  the prompt (US-10). A pack-on cell's first user message also carries a harness-injected AGENTS.md
  block shaped `# AGENTS.md instructions for <cwd>\n\n<INSTRUCTIONS>\n...\n</INSTRUCTIONS>`; that block
  is context too, and is skipped the same way (real E2E, US-10, T8 defect 1).
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    MissingField,
    ModelCall,
    ProviderError,
    ToolCall,
    as_dict,
    as_list,
    as_status,
    as_str,
    rows,
)

CALL_TYPES = ("custom_tool_call", "function_call", "local_shell_call")
OUTPUT_TYPES = ("custom_tool_call_output", "function_call_output", "local_shell_call_output")
SHELL_NAMES = ("exec", "shell", "exec_command", "local_shell", "container.exec")
EDIT_NAMES = ("apply_patch", "write_file", "edit")


def _is_injected_context(text: str) -> bool:
    """A harness-injected context part, not something the user (or the prompt) wrote: a `<tagged>`
    block, or the AGENTS.md instructions block Codex prepends for a pack-on cell (US-10)."""
    stripped = text.lstrip()
    return stripped.startswith(("<", "# AGENTS.md instructions for "))


def _tool_class(name: str) -> str:
    if name in SHELL_NAMES:
        return "shell"
    if name in EDIT_NAMES:
        return "edit"
    return "other"


def _parse_error(message: str) -> tuple[int | None, str]:
    try:
        body = json.loads(message)
    except (ValueError, RecursionError):
        return None, "unknown"
    body = as_dict(body)
    etype = as_str(as_dict(body.get("error")).get("type")) or as_str(body.get("type")) or "unknown"
    return as_status(body.get("status")), etype


def read(path: Path) -> Extraction:
    ex = Extraction()
    model = None
    last_total = None
    open_tools: dict[str, dict] = {}
    for n, row in rows(path, ex):
        kind = row.get("type")
        payload = as_dict(row.get("payload"))
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
        elif kind == "response_item" and ptype in CALL_TYPES and call_id is not None:
            open_tools[call_id] = {"n": n, "name": as_str(payload.get("name")) or ptype, "start": stamp}
        elif kind == "response_item" and ptype in OUTPUT_TYPES and call_id in open_tools:
            tool = open_tools.pop(call_id)
            ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], stamp, None))
    for tool in open_tools.values():
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    return ex
