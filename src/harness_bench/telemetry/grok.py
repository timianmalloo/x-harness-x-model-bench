"""Grok native record reader (ADR-0025 s5, ADR-0026 s1-s2; R-READ-GROK).

A Grok session is a directory, `.grok/sessions/<cwd>/<session id>/`. `read` takes that directory or any file in it.
Sources, each Verified on the frozen 1.0.41 spike sessions (tests/fixtures/grok/rerun-provenance.json):
- `chat_history.jsonl`: `assistant` rows carry `model_id`, `reasoning_effort` and `tool_calls`; `reasoning` rows carry
  `summary` (a list of `summary_text` parts, empty on some turns) and `encrypted_content`. Text is stored as the
  harness stored it; an encrypted payload is hashed, never decoded.
- `usage.json` `turns[]`: per-turn, per-model usage (`modelUsage`). There is no per-request usage, so each row is one
  turn of one model with `requests` = `modelCalls` (ADR-0026 s2), and the per-request grain is PER_REQUEST.
- `signals.json` `contextWindowTokens`; `system_prompt.txt`, `tool_definitions.json`, `prompt_context.json`
  `agents_md_files` (the instruction files, inlined into the first user message's `<rules>` block).
- `events.jsonl`: `tool_started` / `tool_completed` (`tool_call_id`, `outcome`) give a call's times and outcome.
Hooks and compaction are Flagged (ADR-0026 s1): no record shows their shape, so `harness_events` is not recorded.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

from harness_bench.telemetry import (
    MAX_FILE,
    Extraction,
    MissingField,
    ModelCall,
    PromptPart,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    as_dict,
    as_list,
    as_str,
    is_count,
    not_recorded,
    rows,
)

# ADR-0004 classes for the 26 tools the 1.0.41 build advertises (spike G6, `tool_definitions.json`). Out of profile
# (`other`, HB-VAL-008 when executed): web, image and video generation, sub-agents, the scheduler, workflows, the MCP
# call `use_tool`, and every other tool outside file read/edit and shell ("any other tool the harness offers").
# `spawn_subagent` is not `delegate`: no Grok qualification turn has measured it (Codex's precedent, ADR-0004 R-74).
# The background-task controls run or read shell commands, so they are shell (Copilot's read/stop_powershell).
TOOL_CLASS = {"run_terminal_command": "shell", "get_command_or_subagent_output": "shell",
              "kill_command_or_subagent": "shell", "monitor": "shell",
              "read_file": "read", "list_dir": "read", "grep": "read",
              "search_replace": "edit", "write": "edit",
              "search_tool": "meta",  # R-54 (a)'s ToolSearch: returns an MCP tool's schema, invokes nothing
              # Workspace-inert (Leader ruling on R-READ-GROK's DR): counted, never scored, as ToolSearch is (claude_code.py,
              # R-54 (a)); grok agent --agent-profile's tools: allowlist is probed at S3.
              "todo_write": "meta", "enter_plan_mode": "meta", "exit_plan_mode": "meta",
              "ask_user_question": "meta", "send_feedback": "meta",
              "spawn_subagent": "other", "scheduler_create": "other", "scheduler_delete": "other",
              "scheduler_list": "other", "workflow": "other", "use_tool": "other", "web_fetch": "other",
              "image_gen": "other", "image_edit": "other", "image_to_video": "other", "reference_to_video": "other"}

PER_REQUEST = not_recorded("per-turn totals only")[1]
NO_EVENTS = not_recorded("grok hook and compaction events are Flagged (no record shows their shape)")[1]
NO_PROMPT_CONTEXT = not_recorded("prompt_context.json absent or unreadable")[1]
CHAT = "chat_history.jsonl"
USAGE_KEYS = ("inputTokens", "cachedReadTokens", "cacheCreationTokens", "outputTokens")


def tool_class(name: str) -> str:
    return TOOL_CLASS.get(name, "other")


def _json(path: Path):
    """A whole-file JSON document, or None when it is absent, over the size bound, or does not parse."""
    try:
        if path.stat().st_size > MAX_FILE:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8") if path.stat().st_size <= MAX_FILE else None
    except (OSError, UnicodeDecodeError):
        return None


def _model_calls(d: Path, ex: Extraction) -> None:
    """One ModelCall per turn and model from `usage.json` `turns[]`. `inputTokens` is the full prompt (Verified:
    `totalTokens` = `inputTokens` + `outputTokens` on the spike sessions), so the uncached bucket is it minus both
    cache buckets. assume: `cacheCreationTokens` is inside `inputTokens` like `cachedReadTokens`; confirm: a record
    with a non-zero cache write; breaks: uncached input would be undercounted by the cache write."""
    turns = as_dict(_json(d / "usage.json")).get("turns")
    if not isinstance(turns, list):
        ex.missing.append(MissingField(0, "usage.json:turns"))
        return
    for turn in turns:
        turn = as_dict(turn)
        n = turn.get("turnNumber")
        if not is_count(n):
            continue
        for model, usage in as_dict(turn.get("modelUsage")).items():
            usage = as_dict(usage)
            full, read, write, out = (ex.count(n, usage, k) for k in USAGE_KEYS)
            if full < read + write:  # the full prompt is less than its cached part: no uncached count is defensible
                ex.missing.append(MissingField(n, "inputTokens"))
            reasoning = usage.get("reasoningTokens")
            calls = usage.get("modelCalls")
            ex.model_calls.append(ModelCall(n, model, max(full - read - write, 0), read, write, out,
                                            reasoning if is_count(reasoning) else None, None,
                                            as_str(turn.get("endedAt")), calls if is_count(calls) else 1))


def _reasoning_items(row: dict) -> list[tuple[str, str | None, str | None]]:
    """(source_kind, text, opaque_sha256) for one `reasoning` row: one item per summary part, else one encrypted-only."""
    payload = as_str(row.get("encrypted_content"))
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else None
    texts = [as_str(p.get("text")) for p in as_list(row.get("summary")) if isinstance(p, dict)]
    texts = [t for t in texts if t]
    if texts:
        return [("summary", t, sha) for t in texts]
    return [("encrypted-only", None, sha)] if sha else [("omitted", None, None)]


def _chat(d: Path, ex: Extraction, served: list[str], effort: list[str]) -> dict[str, str]:
    """Reasoning items and the calls each assistant row made, in native order; the requested calls by id."""
    ex.reasoning = []
    calls: dict[str, str] = {}
    request = None  # the line that opened the current model response (its first reasoning or assistant row)
    items = 0
    for n, row in rows(d / CHAT, ex):
        kind = row.get("type")
        if kind not in ("reasoning", "assistant"):
            request = None
            if kind == "user" and ex.first_user_text is None and "prompt_index" in row:
                parts = [as_str(p.get("text")) for p in as_list(row.get("content")) if isinstance(p, dict)]
                ex.first_user_text = "".join(p for p in parts if p) or None
            continue
        if request is None:
            request, items = n, 0
        if kind == "reasoning":
            for source_kind, text, sha in _reasoning_items(row):
                ex.reasoning.append(ReasoningItem(request, items, source_kind, text, None if text is None else len(text),
                                                  None, sha))
                items += 1
            continue
        for value, seen in ((as_str(row.get("model_id")), served), (as_str(row.get("reasoning_effort")), effort)):
            if value and value not in seen:
                seen.append(value)
        for call in as_list(row.get("tool_calls")):
            call = as_dict(call)
            if (call_id := as_str(call.get("id"))) is not None:
                calls[call_id] = as_str(call.get("name")) or "unknown"
    return calls


def _tool_calls(d: Path, ex: Extraction, calls: dict[str, str]) -> None:
    """A requested call's times and outcome from `events.jsonl`: `tool_completed` names its call id; its start is the
    earliest open `tool_started` of the same tool (events carry no id on start). A call with no completion has
    neither (a killed turn). `native_ordinal` is the call's position among the record's requested calls, 1-based, in
    native order (line, then its index in that row's `tool_calls`): one assistant row holds several parallel calls
    (devprobe-rerun-1), so its line is no key (HB-LED-003; Claude Code's DR1 rule for events)."""
    started: dict[str, deque] = defaultdict(deque)
    done: dict[str, tuple[str | None, str | None, str | None]] = {}
    if (d / "events.jsonl").is_file():
        for _, event in rows(d / "events.jsonl", Extraction()):
            name, stamp = as_str(event.get("tool_name")), as_str(event.get("ts"))
            if event.get("type") == "tool_started" and name:
                started[name].append(stamp)
            elif event.get("type") == "tool_completed" and (call_id := as_str(event.get("tool_call_id"))):
                start = started[name].popleft() if name and started[name] else None
                done[call_id] = (start, stamp, as_str(event.get("outcome")))
    for position, (call_id, name) in enumerate(calls.items(), 1):
        start, end, outcome = done.get(call_id, (None, None, None))
        ok = None if outcome is None else outcome == "success"
        ex.tool_calls.append(ToolCall(position, name, tool_class(name), start, end, ok, None if ok in (None, True) else outcome))


def _prompt_parts(d: Path) -> list[PromptPart] | str:
    context = _json(d / "prompt_context.json")
    files = as_dict(context).get("agents_md_files")
    if not isinstance(files, list):
        return NO_PROMPT_CONTEXT
    parts = []
    for name, part in (("system_prompt.txt", "system"), ("tool_definitions.json", "tools")):
        if (text := _text(d / name)) is not None:
            parts.append(PromptPart(len(parts), part, name, len(text), "inlined", name))
    for f in files:
        f = as_dict(f)
        content = as_str(f.get("content"))
        parts.append(PromptPart(len(parts), "instruction_file", as_str(f.get("file_path")), None if content is None else len(content),
                                "inlined", "prompt_context.json:agents_md_files"))
    return parts


def _served(d: Path, served: list[str], effort: list[str]) -> tuple[ServedSettings, ...]:
    """One ServedSettings per distinct served id (ADR-0026 DR2: two values under one source are both written)."""
    window = as_dict(_json(d / "signals.json")).get("contextWindowTokens")
    common = {
        "effort": effort[0] if len(effort) == 1 else not_recorded(
            "no reasoning_effort in chat_history.jsonl" if not effort else f"reasoning_effort varies: {', '.join(effort)}"),
        "context_tokens": window if is_count(window) else not_recorded("no contextWindowTokens in signals.json"),
        "model_api": not_recorded("grok's record shows no API model id beyond model_id"),
        "context_tier": not_recorded("grok has no context tier"),
        "reasoning_summary": not_recorded("grok's record shows no reasoning-summary setting"),
    }
    sources = {"model_served": f"{CHAT}:assistant.model_id", "effort": f"{CHAT}:assistant.reasoning_effort",
               "context_tokens": "signals.json:contextWindowTokens"}
    ids = served or [None]
    return tuple(ServedSettings(model_served=s if s else not_recorded("no model_id in chat_history.jsonl"),
                                sources=sources, **common) for s in ids)


def read(path: Path) -> Extraction:
    d = path if path.is_dir() else path.parent
    ex = Extraction(session_id=d.name)
    served: list[str] = []
    effort: list[str] = []
    if (d / CHAT).is_file():
        _tool_calls(d, ex, _chat(d, ex, served, effort))
    else:
        ex.missing.append(MissingField(0, CHAT))
        ex.reasoning = not_recorded(f"{CHAT} absent")[1]
    _model_calls(d, ex)
    ex.served = _served(d, served, effort)
    ex.prompt_parts = _prompt_parts(d)
    ex.harness_events = NO_EVENTS
    return ex
