"""Claude Code native record: `projects/<slug>/<session id>.jsonl` (spikes 1.2, W3; golden fixture 2026-09-23).

- One API message is written as several `assistant` rows (thinking, text, tool_use) that share
  `message.id` and repeat the same `usage`: they are one model call, keyed by the first row's line.
- A failed call is an `assistant` row with `isApiErrorMessage: true`, `apiErrorStatus`, `error`, model
  `<synthetic>` and zero usage (probe W3): it is a provider error, never a model call.
- Anthropic-style usage already excludes cached tokens from `input_tokens`.
- Verified 2026-09-23: with Claude Code 2.1.274 under the ACP adapter, the record omits the turn's
  final API call and auxiliary calls; the adapter's turn usage is authoritative for this harness
  (normalize.totals, profile usage_source acp_turn).
"""

from __future__ import annotations

import re
from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    ModelCall,
    ProviderError,
    ToolCall,
    as_dict,
    as_list,
    as_status,
    as_str,
    rows,
)

__all__ = ["ProviderError", "read"]

TOOL_CLASSES = {"Bash": "shell", "PowerShell": "shell", "Edit": "edit", "Write": "edit", "MultiEdit": "edit",
                "NotebookEdit": "edit", "Read": "read", "Glob": "read", "Grep": "read"}
# Account connectors as the pinned 2.1.282 record advertises them: prompt_snapshot tools and deferred_tools_delta.
_ACCOUNT_CONNECTOR = re.compile(r"mcp__claude_ai_[A-Za-z0-9_]+")


def _text(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "".join(texts) if texts else None
    return None


def _note_advertised(names: list[str], row: dict) -> None:
    """Keep the tool names still advertised after this row (loaded tools, then a deferred-tool delta)."""
    att = as_dict(row.get("attachment"))
    kind = att.get("type")
    if kind == "prompt_snapshot":
        for tool in as_list(att.get("tools")):
            name = as_str(tool.get("name")) if isinstance(tool, dict) else None
            if name is not None:
                names.append(name)
    elif kind == "deferred_tools_delta":
        for name in as_list(att.get("addedNames")):
            if isinstance(name, str):
                names.append(name)
        for name in as_list(att.get("removedNames")):
            if isinstance(name, str):
                while name in names:
                    names.remove(name)


def read(path: Path) -> Extraction:
    ex = Extraction()
    seen_messages: set[str] = set()
    open_tools: dict[str, dict] = {}
    advertised: list[str] = []
    try:
        for n, row in rows(path, ex):
            _note_advertised(advertised, row)
            kind = row.get("type")
            message = as_dict(row.get("message"))
            stamp = as_str(row.get("timestamp"))
            if ex.session_id is None:
                ex.session_id = as_str(row.get("sessionId"))
            if kind == "user":
                content = message.get("content")
                if ex.first_user_text is None:
                    text = _text(content)
                    if text is not None and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in as_list(content)):
                        ex.first_user_text = text
                for block in as_list(content):
                    tool_id = as_str(block.get("tool_use_id")) if isinstance(block, dict) and block.get("type") == "tool_result" else None
                    if tool_id in open_tools:
                        tool = open_tools.pop(tool_id)
                        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], TOOL_CLASSES.get(tool["name"], "other"),
                                                      tool["start"], stamp, not bool(block.get("is_error"))))
                continue
            if kind != "assistant":
                continue
            if row.get("isApiErrorMessage"):
                ex.errors.append(ProviderError(n, as_status(row.get("apiErrorStatus")), as_str(row.get("error")) or "unknown",
                                               (_text(message.get("content")) or "")[:300]))
                continue
            model = message.get("model")
            if not isinstance(model, str) or model == "<synthetic>":
                continue
            mid = message.get("id")
            if isinstance(mid, str) and mid not in seen_messages:
                seen_messages.add(mid)
                usage = as_dict(message.get("usage"))
                ex.model_calls.append(ModelCall(n, model, ex.count(n, usage, "input_tokens"), ex.count(n, usage, "cache_read_input_tokens"),
                                                ex.count(n, usage, "cache_creation_input_tokens"), ex.count(n, usage, "output_tokens"),
                                                None, stamp, stamp))
            for block in as_list(message.get("content")):
                if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                    open_tools[block["id"]] = {"n": n, "name": as_str(block.get("name")) or "unknown", "start": stamp}
    except OSError:
        return ex
    for tool in open_tools.values():  # a call with no result (killed turn)
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], TOOL_CLASSES.get(tool["name"], "other"), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    ex.account_connector_tools = len({name for name in advertised if _ACCOUNT_CONNECTOR.fullmatch(name)})
    return ex
