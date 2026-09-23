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
  the prompt (US-10).
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    ModelCall,
    ProviderError,
    ToolCall,
    as_dict,
    as_int,
    rows,
)

CALL_TYPES = ("custom_tool_call", "function_call", "local_shell_call")
OUTPUT_TYPES = ("custom_tool_call_output", "function_call_output", "local_shell_call_output")
SHELL_NAMES = ("exec", "shell", "exec_command", "local_shell", "container.exec")
EDIT_NAMES = ("apply_patch", "write_file", "edit")


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
    status = body.get("status")
    etype = as_dict(body.get("error")).get("type") or body.get("type") or "unknown"
    return (status if isinstance(status, int) else None), str(etype)


def read(path: Path) -> Extraction:
    ex = Extraction()
    model = None
    last_total = None
    open_tools: dict[str, dict] = {}
    for n, row in rows(path, ex):
        kind = row.get("type")
        payload = as_dict(row.get("payload"))
        ptype = payload.get("type")
        if kind == "session_meta" and ex.session_id is None:
            ex.session_id = payload.get("id") or payload.get("session_id")
        elif kind == "turn_context" and isinstance(payload.get("model"), str):
            model = payload["model"]
        elif kind == "event_msg" and ptype == "token_count":
            info = as_dict(payload.get("info"))
            total, last = info.get("total_token_usage"), as_dict(info.get("last_token_usage"))
            if not last or total == last_total:
                continue
            last_total = total
            cached = as_int(last.get("cached_input_tokens"))
            ex.model_calls.append(ModelCall(n, model or "NOT_RECORDED", max(as_int(last.get("input_tokens")) - cached, 0), cached,
                                            as_int(last.get("cache_write_input_tokens")), as_int(last.get("output_tokens")),
                                            as_int(last.get("reasoning_output_tokens")), row.get("timestamp"), row.get("timestamp")))
        elif kind == "event_msg" and ptype == "task_complete":
            err = as_dict(payload.get("error"))
            if err:
                status, etype = _parse_error(str(err.get("message") or ""))
                ex.errors.append(ProviderError(n, status, etype, str(err.get("message") or "")[:300]))
        elif kind == "response_item" and ptype == "message" and payload.get("role") == "user" and ex.first_user_text is None:
            texts = [c.get("text") for c in payload.get("content") or [] if isinstance(c, dict) and isinstance(c.get("text"), str)]
            if texts and not all(t.lstrip().startswith("<") for t in texts):
                ex.first_user_text = "".join(t for t in texts if not t.lstrip().startswith("<"))
        elif kind == "response_item" and ptype in CALL_TYPES and isinstance(payload.get("call_id"), str):
            name = str(payload.get("name") or ptype)
            open_tools[payload["call_id"]] = {"n": n, "name": name, "start": row.get("timestamp")}
        elif kind == "response_item" and ptype in OUTPUT_TYPES and payload.get("call_id") in open_tools:
            tool = open_tools.pop(payload["call_id"])
            ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], row.get("timestamp"), None))
    for tool in open_tools.values():
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    return ex
