"""Claude Code native record: `projects/<slug>/<session id>.jsonl` (spikes 1.2, W3; golden fixture 2026-09-23).

- One API message is written as several `assistant` rows (thinking, text, tool_use) that share
  `message.id` and repeat the same `usage`: they are one model call, keyed by the first row's line.
- A failed call is an `assistant` row with `isApiErrorMessage: true`, `apiErrorStatus`, `error`, model
  `<synthetic>` and zero usage (probe W3): it is a provider error, never a model call.
- Anthropic-style usage already excludes cached tokens from `input_tokens`.
- Verified 2026-09-23: with Claude Code 2.1.274 under the ACP adapter, the record omits the turn's
  final API call and auxiliary calls; the adapter's turn usage is authoritative for this harness
  (normalize.totals, profile usage_source acp_turn). Observed 2026-10-12 on 2.1.282 (R-READ-CC, two turns): the
  record's per-`requestId` outputs sum exactly to the ACP turn's main-model `outputTokens`; the auxiliary title call
  (claude-haiku-4-5) is still absent from the record.

The lean re-run's reader facts (ADR-0026 s1; R-READ-CC spike, 2026-10-12, one pack-on X1 turn):
- served: `effort` on every assistant row; `attachment` type `model` -> `identity.modelId`; the context size is not in
  the transcript but in the ACP `usage_update.size`: the driver's `acp-timeline.jsonl` in the cell home (the parent
  of the record's `projects` folder). Only the adapter's authoritative size is served: the usage_update directly before
  a prompt response (`_authoritative`, PROBE-FIX-2 D); one served row per distinct such size, its source naming the
  timeline line (so two sizes are two keys and HB-VAL-010 judges them); in-turn sizes are the adapter's seed. A
  timeline with none is `not recorded`. `read(path, acp=...)` reads raw ACP messages instead (tests).
- model calls: `reasoning` is the request's `usage.output_tokens_details.thinking_tokens` (its first row).
- reasoning: each `thinking` block is a `summary` (display `summarized`), its text as stored; an empty one with only
  a signature is `encrypted-only`.
- prompt parts: `attachment` type `instructions` (`files[].path/content`), `prompt_snapshot` (`systemPrompt` list,
  `tools`), `skill_listing` (`content`).
- events: `system` rows of subtype `stop_hook_summary` (`hookInfos[].command/durationMs`, `hookErrors`); a `Skill`
  tool call is a skill load. Hooks of other events (SessionStart, PreToolUse, PostToolUse, UserPromptSubmit) that
  print nothing leave no row (the spike's SessionStart hook ran and wrote its file, with no transcript row), and no
  compaction row was seen: both are not recorded.
- Per-tool hook time (C4, lean run lean-20261013T222006, 30 pack-on cells, 712 tool calls) is not recorded by the
  harness: the pack wires 2-3 PreToolUse hooks and 1-2 PostToolUse hooks on every call, yet the transcript holds only 8
  `attachment` rows of type `hook_success` (`hookEvent`, `hookName`, `command`, `exitCode`, `durationMs`, `toolUseID`),
  all from the re-read guard when it printed a warning. Each is a hook event; its `timestamp` is the hook's end (the
  tool_use row's stamp plus `durationMs`, within 1-4 ms, on all 8). Every hook event keeps `start` None and its duration in
  `detail`, so the cell's hook time (a sum over events) stays not recorded rather than a sum that leaves out the
  silent invocations. The hook time is inside each tool call's interval (tool_use row to tool_result row). Inferred
  estimate, not emitted: the median Read call takes 1275 ms pack-on against 14 ms pack-off on the same run.
  `HOOK_TIME_REASON` is that fact in one sentence; `views.time_anatomy` shows it as the hook-time reason.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

from harness_bench.driver import TIMELINE_PROMPT, TIMELINE_RESPONSE
from harness_bench.telemetry import (
    Extraction,
    HarnessEvent,
    ModelCall,
    ProcessTrace,
    PromptPart,
    ProviderError,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    ToolInput,
    as_dict,
    as_list,
    as_status,
    as_str,
    is_count,
    not_recorded,
    rows,
    unexpected_status,
)

__all__ = ["HOOK_TIME_REASON", "ProviderError", "read", "tool_inputs"]

# Why a cell's hook time is not recorded, for `views.time_anatomy` (a reader module may state one; see its docstring, C4).
HOOK_TIME_REASON = "Claude Code records a tool hook's time only when the hook prints output"

TOOL_CLASSES = {"Bash": "shell", "PowerShell": "shell", "Edit": "edit", "Write": "edit", "MultiEdit": "edit",
                "NotebookEdit": "edit", "Read": "read", "Glob": "read", "Grep": "read",
                "ToolSearch": "meta",  # R-54 (a): loads a deferred tool's schema, invokes nothing; counted, never scored
                "Agent": "delegate",  # R-74 item 1: starts a sub-agent; in profile only in a scenario-6 cell (views)
                "mcp__scripted_user__ask_user": "scripted user"}  # R-37 c2: the task's own MCP tool (a1-capture-1)
# Account connectors as the pinned 2.1.282 record advertises them: prompt_snapshot tools and deferred_tools_delta.
_ACCOUNT_CONNECTOR = re.compile(r"mcp__claude_ai_[A-Za-z0-9_]+")
# design pack-improvement-section.md section 4.3: is_write true for Write, Edit, MultiEdit, NotebookEdit.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _text(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "".join(texts) if texts else None
    return None


EXIT_CODE = re.compile(r"Exit code (-?\d+)(?:\n|$)")  # how Claude Code opens a failed Bash result (int-claude-code-20261015T1529)


def _outcome(block: dict) -> str | None:
    """A failed result's `exit_<N>` when its text opens `Exit code N` (the command ran and returned N; Codex's and
    Copilot's `exit_<N>`); None for a success, and for any other failure (the record does not say which kind)."""
    if not block.get("is_error"):
        return None
    match = EXIT_CODE.match(_text(block.get("content")) or "")
    return f"exit_{match.group(1)}" if match else None


def _tool_use_blocks(n: int, message: dict):
    """Every `tool_use` block in one assistant row's content, in native order: `(native_ordinal,
    block)`. The one walker `read()`'s `ToolCall`s and `tool_inputs()`'s `ToolInput`s both project
    from (R-85 condition 1: two independently written loops over `tool_use` blocks would give two
    counts of "tool calls per cell"; PI-T6 asserts the counts equal on a fixture with no out-of-band
    tool source)."""
    for block in as_list(message.get("content")):
        if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("id"), str):
            yield n, block


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


SRC_EFFORT = "transcript:assistant.effort"
SRC_MODEL = "transcript:attachment.identity.modelId"
SRC_ACP_SIZE = "acp:usage_update.size"
SRC_TIMELINE_SIZE = "acp-timeline.jsonl:usage_update.size"  # + "@<line>" of the size's first line
TIMELINE = "acp-timeline.jsonl"  # driver.TIMELINE (only driver.py speaks ACP, so the name is repeated here)
NO_AUTHORITATIVE = "no authoritative window (adapter seed only)"
_END, _OTHER = (None, "end"), (None, "")  # a prompt response, and any other message, in a record's update sequence


def _served(efforts: list[str], models: list[str], acp: Path | None, record: Path) -> tuple[ServedSettings, ...]:
    """One `ServedSettings` per distinct value of a field, in record order (DR2): a second value repeats the first
    settings' other fields, so its rows de-duplicate in `served_rows` and only the differing value adds a row."""
    base = ServedSettings(
        model_requested=not_recorded("the plan's, never a served row"),
        model_served=models[0] if models else not_recorded("no model attachment in the transcript"),
        model_api=not_recorded("Claude Code has no model_api source (ADR-0024 s4)"),
        effort=efforts[0] if efforts else not_recorded("no assistant row carries effort"),
        context_tokens=not_recorded("the transcript does not record the context size"),
        context_tier=not_recorded("Claude Code has no context tier"),
        reasoning_summary=not_recorded("the thinking display is a session/new option the transcript does not record"),
        sources={**({"model_served": SRC_MODEL} if models else {}), **({"effort": SRC_EFFORT} if efforts else {})})
    sizes = [(s, SRC_ACP_SIZE) for s in _acp_sizes(acp)] if acp is not None else _timeline_sizes(record)
    if sizes is not None and not sizes:  # a timeline whose turns end with no post-result usage_update
        base = replace(base, context_tokens=not_recorded(NO_AUTHORITATIVE))
    out = [base]
    out += [replace(base, model_served=m) for m in models[1:]]
    out += [replace(base, effort=e) for e in efforts[1:]]
    out += [replace(base, context_tokens=s, sources={**base.sources, "context_tokens": src}) for s, src in sizes or ()]
    return tuple(out)


def _authoritative(seen: list[tuple[int | None, str]]) -> list[tuple[int, str]]:
    """The distinct authoritative sizes, in order: `seen` is the record's sequence, (size, source) for a usage_update,
    `_END` for a prompt response and `_OTHER` for anything else.

    Leader ruling on PROBE-FIX-2 item D (option a), from claude-agent-acp 0.81.2 (dist/acp-agent.js): every in-turn
    usage_update sends `size: session.contextWindowSize` (~4241), which session/new seeds from a cache, a text heuristic
    or a default with `contextWindowAuthoritative` false (~6683-6735); on the turn's `result` the adapter sets it from
    `result.modelUsage[model].contextWindow`, marks it authoritative and sends one more usage_update, then answers the
    prompt (~3755-3795). So the served window is the size of the usage_update directly before a prompt response; an
    earlier size is the seed (devprobe-rerun-1 and ccprobe-rerun-1: 200000 in turn, 1000000 after the result)."""
    sizes: list[tuple[int, str]] = []
    for (size, source), after in pairwise(seen):
        if size is not None and after == _END and size not in [s for s, _ in sizes]:
            sizes.append((size, source))
    return sizes


def _timeline_sizes(record: Path) -> list[tuple[int, str]] | None:
    """(size, source) per distinct authoritative `usage_update` size in the cell home's ACP timeline, in order; None
    without a timeline. The timeline collapses same-kind runs, so a result update that repeats the seed's size is the
    run that ends right before the response, and the run's first line is its source."""
    home = next((p.parent for p in record.parents if p.name == "projects"), None)
    timeline = home / TIMELINE if home is not None else None
    if timeline is None or not timeline.is_file():
        return None
    try:
        lines = timeline.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    out: list[tuple[int | None, str]] = []
    for n, line in enumerate(lines, 1):
        try:
            row = as_dict(json.loads(line))
        except ValueError:
            continue
        size = row.get("size")
        if row.get("update_kind") == "usage_update" and isinstance(size, int):
            out.append((size, f"{SRC_TIMELINE_SIZE}@{n}"))
        else:
            out.append(_END if row.get("update_kind") == TIMELINE_RESPONSE and row.get("method") == TIMELINE_PROMPT
                       else _OTHER)
    return _authoritative(out)


def _acp_sizes(acp: Path) -> list[int]:
    """The distinct authoritative sizes by the same rule, from a file of ACP JSON-RPC messages (one per line): a prompt
    response is a result carrying `stopReason`."""
    seen: list[tuple[int | None, str]] = []
    for line in acp.read_text(encoding="utf-8").splitlines():
        try:
            msg = as_dict(json.loads(line))
        except ValueError:
            continue
        update = as_dict(as_dict(msg.get("params")).get("update"))
        size = update.get("size")
        if update.get("sessionUpdate") == "usage_update" and isinstance(size, int):
            seen.append((size, SRC_ACP_SIZE))
        else:
            seen.append(_END if "stopReason" in as_dict(msg.get("result")) else _OTHER)
    return [s for s, _ in _authoritative(seen)]


def _keep(values: list[str], value) -> None:
    if isinstance(value, str) and value not in values:
        values.append(value)


def _rel(path: str | None, cwd: str | None) -> str | None:
    """An instruction file's path relative to the session's cwd when it lies under it (cell paths differ per cell)."""
    if path is None:
        return None
    path = path.replace("\\", "/")
    root = (cwd or "").replace("\\", "/").rstrip("/") + "/"
    return path[len(root):] if cwd and path.lower().startswith(root.lower()) else path


def _note_parts(parts: list[PromptPart], seen: set[str], row: dict) -> None:
    """The fixed prefix's parts, each from the first attachment that shows it."""
    att = as_dict(row.get("attachment"))
    kind = att.get("type")
    if kind == "instructions":
        for f in as_list(att.get("files")):
            content = as_str(f.get("content")) if isinstance(f, dict) else None
            path = _rel(as_str(f.get("path")), as_str(row.get("cwd"))) if isinstance(f, dict) else None
            if path is None or f"file:{path}" in seen:
                continue
            seen.add(f"file:{path}")
            part = "agents_md" if path.replace("\\", "/").rsplit("/", 1)[-1] == "AGENTS.md" else "instruction_file"
            parts.append(PromptPart(len(parts), part, path, len(content) if content is not None else None, "inlined",
                                    "transcript:attachment.instructions"))
    elif kind == "prompt_snapshot":
        system = att.get("systemPrompt")
        if "system" not in seen and isinstance(system, list) and all(isinstance(s, str) for s in system):
            seen.add("system")
            parts.append(PromptPart(len(parts), "system", None, sum(len(s) for s in system), "inlined",
                                    "transcript:attachment.prompt_snapshot.systemPrompt"))
        tools = att.get("tools")
        if "tools" not in seen and isinstance(tools, list) and tools:
            seen.add("tools")  # chars of the recorded tools array as compact JSON (the record keeps no wire bytes)
            parts.append(PromptPart(len(parts), "tools", None, len(json.dumps(tools, ensure_ascii=False, separators=(",", ":"))),
                                    "inlined", "transcript:attachment.prompt_snapshot.tools"))
    elif kind == "skill_listing" and "skills" not in seen and isinstance(att.get("content"), str):
        seen.add("skills")
        parts.append(PromptPart(len(parts), "skills", None, len(att["content"]), "listed", "transcript:attachment.skill_listing"))


def _hook_events(row: dict, stamp: str | None) -> list[HarnessEvent]:
    """A `stop_hook_summary` row: one hook event per `hookInfos` entry (ordinal set later). `ok` is 1 only when the
    row lists no `hookErrors`; with errors the record does not say which hook failed, so `ok` is None. A `hook_success`
    attachment (a tool or prompt hook that printed): one event, `ok` from its `exitCode`. `start` is None on both and
    the duration rides in `detail` (module docstring, C4: the silent invocations are not in the record)."""
    att = as_dict(row.get("attachment"))
    if att.get("type") == "hook_success":
        code = att.get("exitCode")
        return [HarnessEvent(0, "hook", as_str(att.get("command")), None, stamp, code == 0 if type(code) is int else None,
                             f"{as_str(att.get('hookName'))} durationMs={att.get('durationMs')}")]
    if row.get("type") != "system" or row.get("subtype") != "stop_hook_summary":
        return []
    errors = row.get("hookErrors")
    ok = True if errors == [] else None
    return [HarnessEvent(0, "hook", as_str(info.get("command")), None, stamp, ok,
                         f"Stop durationMs={info.get('durationMs')}")
            for info in as_list(row.get("hookInfos")) if isinstance(info, dict)]


def _reasoning(n: int, start: int, message: dict) -> list[ReasoningItem]:
    items = []
    for block in as_list(message.get("content")):
        if not isinstance(block, dict) or block.get("type") not in ("thinking", "redacted_thinking"):
            continue
        text = as_str(block.get("thinking"))
        opaque = as_str(block.get("signature")) if block.get("type") == "thinking" else as_str(block.get("data"))
        k = start + len(items)
        if text:
            items.append(ReasoningItem(n, k, "summary", text, len(text), None, None))
        elif opaque:
            items.append(ReasoningItem(n, k, "encrypted-only", None, None, None, hashlib.sha256(opaque.encode()).hexdigest()))
    return items


def read(path: Path, acp: Path | None = None) -> Extraction:
    """The native record; `acp`, when given, is the turn's ACP messages (one JSON-RPC message per line), read for the
    served context size instead of the cell home's timeline. With neither, that field is `not recorded`."""
    ex = Extraction()
    seen_messages: set[str] = set()
    call_line: dict[str, int] = {}  # request key -> its ModelCall's native_ordinal
    item_counts: dict[str, int] = {}
    open_tools: dict[str, dict] = {}
    advertised: list[str] = []
    efforts: list[str] = []
    models: list[str] = []
    parts: list[PromptPart] = []
    part_seen: set[str] = set()
    reasoning: list[ReasoningItem] = []
    events: list[tuple[int, HarnessEvent]] = []
    skills: dict[str, dict] = {}
    for n, row in rows(path, ex):
        _note_advertised(advertised, row)
        _note_parts(parts, part_seen, row)
        kind = row.get("type")
        message = as_dict(row.get("message"))
        stamp = as_str(row.get("timestamp"))
        if ex.session_id is None:
            ex.session_id = as_str(row.get("sessionId"))
        att = as_dict(row.get("attachment"))
        if att.get("type") == "model":
            _keep(models, as_dict(att.get("identity")).get("modelId"))
        events += [(n, e) for e in _hook_events(row, stamp)]
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
                                                  tool["start"], stamp, not bool(block.get("is_error")), _outcome(block)))
                if tool_id in skills:
                    skill = skills.pop(tool_id)
                    events.append((skill["n"], HarnessEvent(0, "skill_load", skill["name"], skill["start"], stamp,
                                                            not bool(block.get("is_error")), None)))
            continue
        if kind != "assistant":
            continue
        if row.get("isApiErrorMessage"):
            text = _text(message.get("content")) or ""
            status = as_status(row.get("apiErrorStatus"))
            if status is None:  # no status field: the CLI text may carry `unexpected status NNN`
                status = unexpected_status(f"{text}\n{as_str(row.get('error')) or ''}")
            ex.errors.append(ProviderError(n, status, as_str(row.get("error")) or "unknown", text[:300]))
            continue
        model = message.get("model")
        if not isinstance(model, str) or model == "<synthetic>":
            continue
        _keep(efforts, row.get("effort"))
        # ADR-0026 s2: one row per request, keyed by `requestId` (a record without one keys by `message.id`).
        key = as_str(row.get("requestId")) or as_str(message.get("id"))
        if key is not None and key not in seen_messages:
            seen_messages.add(key)
            call_line[key] = n
            usage = as_dict(message.get("usage"))
            thinking = as_dict(usage.get("output_tokens_details")).get("thinking_tokens")
            ex.model_calls.append(ModelCall(n, model, ex.count(n, usage, "input_tokens"), ex.count(n, usage, "cache_read_input_tokens"),
                                            ex.count(n, usage, "cache_creation_input_tokens"), ex.count(n, usage, "output_tokens"),
                                            thinking if is_count(thinking) else None, stamp, stamp))
        if key is not None:
            items = _reasoning(call_line[key], item_counts.get(key, 0), message)
            item_counts[key] = item_counts.get(key, 0) + len(items)
            reasoning += items
        for _, block in _tool_use_blocks(n, message):
            name = as_str(block.get("name")) or "unknown"
            open_tools[block["id"]] = {"n": n, "name": name, "start": stamp}
            if name == "Skill":  # the Skill tool's schema (prompt_snapshot `tools`) takes `skill`, the skill's name
                skills[block["id"]] = {"n": n, "name": as_str(as_dict(block.get("input")).get("skill")), "start": stamp}
    for tool in open_tools.values():  # a call with no result (killed turn)
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], TOOL_CLASSES.get(tool["name"], "other"), tool["start"], None, None))
    events += [(s["n"], HarnessEvent(0, "skill_load", s["name"], s["start"], None, None, None)) for s in skills.values()]
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    ex.account_connector_tools = len({name for name in advertised if _ACCOUNT_CONNECTOR.fullmatch(name)})
    ex.served = _served(efforts, models, acp, path)
    ex.reasoning = reasoning
    ex.prompt_parts = parts
    # DR1: native_ordinal is the event's position among the record's events (two hooks share one row's line).
    ex.harness_events = [replace(e, native_ordinal=i) for i, (_, e) in enumerate(sorted(events, key=lambda t: t[0]), 1)]
    return ex


def _result_bytes(content: object) -> int | None:
    """The UTF-8 size of one `tool_result` (ADR-0026 s4): a string, or the text parts of a list. A list holding a
    non-text part (an image, a tool reference) is not recorded: the record gives no size for that part."""
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    parts = [p for p in as_list(content) if isinstance(p, dict)]
    if parts and all(p.get("type") == "text" and isinstance(p.get("text"), str) for p in parts):
        return sum(len(p["text"].encode("utf-8")) for p in parts)
    return None


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from each `tool_use` block, in native order, plus this record's own first
    assistant text block (design pack-improvement-section.md section 4.3, slice S2). A row with
    `isApiErrorMessage` is a provider error (module docstring), never a text block or a tool call.
    `bytes_returned` is the paired `tool_result`'s size (None with no result row or a non-text part). The assistant
    text count (I2) is every non-blank `text` block of a model row: thinking and tool input are not counted, and a
    record that lost a line reports none."""
    ex = Extraction()
    first_text: str | None = None
    calls: list[ToolInput] = []
    call_ids: dict[str, int] = {}
    returned: dict[str, int | None] = {}
    chars = messages = 0
    for n, row in rows(path, ex):
        if row.get("type") == "user":
            for block in as_list(as_dict(row.get("message")).get("content")):
                if isinstance(block, dict) and block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
                    returned.setdefault(block["tool_use_id"], _result_bytes(block.get("content")))
            continue
        if row.get("type") != "assistant" or row.get("isApiErrorMessage"):
            continue
        message = as_dict(row.get("message"))
        model = message.get("model")
        if not isinstance(model, str) or model == "<synthetic>":  # same gate read() applies (module docstring)
            continue
        texts = [b.get("text") for b in as_list(message.get("content"))
                 if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        if first_text is None and texts:
            first_text = "".join(texts)
        visible = [t for t in texts if t.strip()]
        chars += sum(len(t) for t in visible)
        messages += bool(visible)
        for _, block in _tool_use_blocks(n, message):
            name = as_str(block.get("name")) or "unknown"
            inp = as_dict(block.get("input"))
            paths = tuple(p for p in (as_str(inp.get("file_path")), as_str(inp.get("path")), as_str(inp.get("notebook_path"))) if p)
            command = as_str(inp.get("command"))
            call_ids.setdefault(block["id"], len(calls))
            calls.append(ToolInput(n, name, paths, command, name in WRITE_TOOLS))
    for call_id, i in call_ids.items():
        if returned.get(call_id) is not None:
            calls[i] = replace(calls[i], bytes_returned=returned[call_id])
    lost = ex.truncated or ex.malformed_lines
    return ProcessTrace(first_text, tuple(calls), None if lost else chars, None if lost else messages)
