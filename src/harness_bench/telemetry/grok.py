"""Grok native record reader (ADR-0025 s5, ADR-0026 s1-s2; R-READ-GROK).

A Grok session is a directory, `.grok/sessions/<cwd>/<session id>/`. `read` takes that directory or any file in it.
Sources, each Verified on the frozen 1.0.41 spike sessions (tests/fixtures/grok/rerun-provenance.json):
- `chat_history.jsonl`: `assistant` rows carry `model_id`, `reasoning_effort` and `tool_calls`; `reasoning` rows carry
  `summary` (a list of `summary_text` parts, empty on some turns) and `encrypted_content`. Text is stored as the
  harness stored it; an encrypted payload is hashed, never decoded.
- `usage.json` `turns[]`: per-turn, per-model usage (`modelUsage`). There is no per-request usage, so each row is one
  turn of one model with `requests` = `modelCalls` (ADR-0026 s2), and the per-request grain is PER_REQUEST.
- `signals.json` `contextWindowTokens`; `system_prompt.txt`, `tool_definitions.json`, `prompt_context.json`
  `agents_md_files` (the instruction files, inlined into the first user message's `<rules>` block), and the skill
  catalogue: a `system_reminder` user row before the prompt (`_skill_catalogues`, A7). Not parts: the rest of the
  `<user_info>` row and the other pre-prompt reminders (the MCP server notice, pack-off's workflow list).
- `events.jsonl`: `tool_started` / `tool_completed` (`tool_call_id`, `outcome`) give a call's times and outcome.
- `updates.jsonl` (C4, Verified on the lean run lean-20261013T222527, build 1.0.41, every archived cell): each
  `params.update` with `sessionUpdate` `hook_execution` is one hook event (`event_name`: session_start,
  user_prompt_submit, pre_tool_use, post_tool_use, stop; `tool_name` on the tool events) and its `runs[]` are the hook
  invocations, each `name` (the config path) and `status.status` / `status.elapsed_ms`. `harness_events` has one `hook`
  row per run. The runs of one row ran one after another and `_meta.agentTimestampMs` is the last one's end: in cell
  55f8737f9f071f28, `tool_started` to the first pre_tool_use row is 5993 ms against a runs' sum of 5990 (their max was
  1627), and the pre_tool_use rows match the tool calls one for one (57/57). So run k ends at the stamp minus the later
  runs' elapsed_ms and starts elapsed_ms before that. Only `success` was seen (10,591 runs): any other status is `ok`
  None with the status in `detail`. The hook time sits inside the tool call's own interval (the hooks run after
  `tool_started`). Compaction is not recorded: no record shows its shape (ADR-0026 s1).
- `tool_inputs` (the report's and attention drift's trace) reads `chat_history.jsonl` alone: the assistant rows' calls,
  and the `tool_result` rows by `tool_call_id`.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path

from harness_bench.telemetry import (
    MAX_FILE,
    Extraction,
    HarnessEvent,
    MissingField,
    ModelCall,
    ProcessTrace,
    PromptPart,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    ToolInput,
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
NO_UPDATES = not_recorded("updates.jsonl absent (hook runs are recorded there)")[1]
UPDATES = "updates.jsonl"
NO_PROMPT_CONTEXT = not_recorded("prompt_context.json absent or unreadable")[1]
CHAT = "chat_history.jsonl"
SKILLS_HEAD = "<system-reminder>\nThe following skills are available for use:"
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


def _skill_catalogues(d: Path) -> list[int]:
    """The chars of each skill catalogue Grok sent before the prompt: a `user` row with `synthetic_reason`
    `system_reminder` whose text opens with SKILLS_HEAD, before the first row with `prompt_index` (A7, Verified on
    lean-20261013T222527: one per pack-on cell, after `<user_info>`; a reload after the prompt is not the prefix)."""
    out: list[int] = []
    if (d / CHAT).is_file():
        for _, row in rows(d / CHAT, Extraction()):
            if "prompt_index" in row or row.get("type") in ("assistant", "reasoning"):
                break
            text = "".join(as_str(p.get("text")) or "" for p in as_list(row.get("content")) if isinstance(p, dict))
            if row.get("synthetic_reason") == "system_reminder" and text.startswith(SKILLS_HEAD):
                out.append(len(text))
    return out


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
    parts += [PromptPart(len(parts) + k, "skills", None, chars, "listed", f"{CHAT}:user.system_reminder (skills)")
              for k, chars in enumerate(_skill_catalogues(d))]
    return parts


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hook_events(d: Path) -> list[HarnessEvent] | str:
    """One `hook` event per run of each `hook_execution` update (module docstring), in record order. A run's times
    are derived back from the row's stamp through the later runs' elapsed_ms, so a run with no count leaves its own
    and every earlier run's times None (the stream's sum is then not recorded, never a partial one)."""
    if not (d / UPDATES).is_file():
        return NO_UPDATES
    events: list[HarnessEvent] = []
    for _, row in rows(d / UPDATES, Extraction()):
        params = as_dict(row.get("params"))
        update = as_dict(params.get("update"))
        if update.get("sessionUpdate") != "hook_execution":
            continue
        at = as_dict(params.get("_meta")).get("agentTimestampMs")
        end = at if is_count(at) else None
        tool = as_str(update.get("tool_name"))
        label = (as_str(update.get("event_name")) or "unknown") + (f" tool={tool}" if tool else "")
        timed = []
        for run in reversed([as_dict(r) for r in as_list(update.get("runs"))]):
            status = as_dict(run.get("status"))
            elapsed, state = status.get("elapsed_ms"), as_str(status.get("status"))
            start = end - elapsed if end is not None and is_count(elapsed) and elapsed <= end else None
            detail = f"{label} elapsed_ms={elapsed}" + ("" if state == "success" else f" status={state}")
            timed.append((as_str(run.get("name")), start, end if start is not None else None,
                          True if state == "success" else None, detail))
            end = start
        for name, start, stop, ok, detail in reversed(timed):
            events.append(HarnessEvent(len(events) + 1, "hook", name, None if start is None else _iso(start),
                                       None if stop is None else _iso(stop), ok, detail))
    return events


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


# The parameters that name a file or directory, from the build's own tool_definitions.json (Verified, 1.0.41): read_file
# `target_file`, list_dir `target_directory`, grep `path` (optional: absent means the workspace), search_replace and write
# `file_path`. No other advertised tool takes one.
_PATH_ARGS = ("target_file", "target_directory", "file_path", "path")


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from the assistant rows' `tool_calls`, in native order, one per call id: the calls `read` counts, so
    the two counts are equal (R-85 condition 1). `native_ordinal` is the call's 1-based position, as `read` gives it.
    `bytes_returned` is the UTF-8 size of the call's `tool_result` content; None when the record has no result for it.
    Reply text is the assistant rows' `content` (reasoning is its own row type, so none is counted); a blank row is no
    message. A session with no `chat_history.jsonl` or a cut-short read gives no calls and no text counts (None)."""
    ex = Extraction()
    if not (d := path if path.is_dir() else path.parent).joinpath(CHAT).is_file():
        return ProcessTrace(None)
    pending: dict[str, tuple[str, dict]] = {}
    sizes: dict[str, int] = {}
    messages: list[str] = []
    for _, row in rows(d / CHAT, ex):
        if row.get("type") == "tool_result" and (call_id := as_str(row.get("tool_call_id"))) and isinstance(row.get("content"), str):
            sizes.setdefault(call_id, len(row["content"].encode("utf-8")))
        elif row.get("type") == "assistant":
            if (text := as_str(row.get("content"))) and text.strip():
                messages.append(text)
            for call in as_list(row.get("tool_calls")):
                call = as_dict(call)
                call_id, arguments = as_str(call.get("id")), call.get("arguments")
                if call_id is None or call_id in pending:
                    continue
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except (ValueError, RecursionError):
                        arguments = None
                pending[call_id] = (as_str(call.get("name")) or "unknown", as_dict(arguments))
    calls = []
    for position, (call_id, (name, args)) in enumerate(pending.items(), 1):
        paths = tuple(dict.fromkeys(v for k in _PATH_ARGS if isinstance(v := args.get(k), str) and v))
        calls.append(ToolInput(position, name, paths, as_str(args.get("command")), tool_class(name) == "edit", sizes.get(call_id)))
    counted = not ex.truncated
    return ProcessTrace(messages[0] if messages else None, tuple(calls), sum(map(len, messages)) if counted else None,
                        len(messages) if counted else None)


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
    ex.harness_events = _hook_events(d)
    return ex
