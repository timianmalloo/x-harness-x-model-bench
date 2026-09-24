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

from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    ModelCall,
    ProviderError,
    ToolCall,
    as_dict,
    as_int,
    as_list,
    as_status,
    as_str,
    rows,
)

__all__ = ["ProviderError", "read"]

TOOL_CLASSES = {"Bash": "shell", "PowerShell": "shell", "Edit": "edit", "Write": "edit", "MultiEdit": "edit",
                "NotebookEdit": "edit", "Read": "read", "Glob": "read", "Grep": "read"}


def _text(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "".join(texts) if texts else None
    return None


def read(path: Path) -> Extraction:
    ex = Extraction()
    seen_messages: set[str] = set()
    open_tools: dict[str, dict] = {}
    for n, row in rows(path, ex):
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
            ex.model_calls.append(ModelCall(n, model, as_int(usage.get("input_tokens")), as_int(usage.get("cache_read_input_tokens")),
                                            as_int(usage.get("cache_creation_input_tokens")), as_int(usage.get("output_tokens")),
                                            None, stamp, stamp))
        for block in as_list(message.get("content")):
            if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                open_tools[block["id"]] = {"n": n, "name": as_str(block.get("name")) or "unknown", "start": stamp}
    for tool in open_tools.values():  # a call with no result (killed turn)
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], TOOL_CLASSES.get(tool["name"], "other"), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    return ex
