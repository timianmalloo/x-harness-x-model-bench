"""Antigravity native record reader (ADR-0025 s6, ADR-0026 s1).

Pattern: Anti-Corruption Layer, the same shapes as the other readers. It reads the teed stream (`agy-stream.ndjson`,
stream_driver.STREAM_RECORD) and the conversation store beside it, `<cell home>/.gemini/antigravity-cli/conversations/
<conversation id>.db` (the spike's layout; bench/profiles/agy.yaml `record_glob`). It reads the stream's event bodies
(`init`, `step_update`, tool steps) only; the input event and the outcome grammar stay in `stream_driver.py`
(tests/test_architecture.py), so no denial or turn status is read here.

- served: `model_served` is `init.model`. The stream carries no context window, effort or reasoning summary.
- model calls: one per `agent_response` step in state DONE with `usage`, at that line. `reasoning` is
  `thinking_tokens`, a component of `output_tokens` (215 of 216 on the spike's one-word turn).
- tool calls: one per tool step, at its first line. A DONE state is not success (the spike's turn1 `run_command` reached
  DONE while agy denied it), so `ok` is None; an ERROR state is `ok` False with the native `error.type`.
- reasoning: decoded from `steps.step_payload` (row `idx` = the stream's `step_index`) by the stdlib protobuf wire
  decoder below. Field map, from the three spike dbs (agy 1.3.3, no published schema): field 20 is the planner
  response; 20.1 its reply text; 20.7 a tool call (20.7.2 the name, 20.7.3 the JSON arguments); 20.3, when present,
  UTF-8 thought text; 20.14.2.1 (beside a text reply) and 20.7.7.2.1 (inside a tool call) an opaque payload,
  high-entropy and not a protobuf message, whose size grows with `thinking_tokens` (986 B for 215, 3,963 B for 909).
  20.3 is a `summary`, never `text`: the one recorded (432 chars) stands for 909 thinking tokens, so it is not the
  whole reasoning. Each opaque payload is `encrypted-only` with its sha256. A payload that does not decode, a missing
  row, or a response with neither gives one `omitted` row with the step's `thinking_tokens`. A changed format reads as
  `omitted` or `not recorded`, never as wrong text.
- prompt parts: `gen_metadata.data` field 1 is a request; 1.1 is its full prompt. The first request with a prompt
  gives the `system` part and one `instruction_file` part per `<RULE[<path>]>...</RULE[<path>]>` block (agy inlines
  AGENTS.md, GEMINI.md and the home rules that way; `path` is the label as stored, `chars` the body between the tags).
- harness events: not read (steps are a Flagged source, ADR-0026 s1).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    MissingField,
    ModelCall,
    PromptPart,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    as_dict,
    as_str,
    is_count,
    not_recorded,
    rows,
)

__all__ = ["TOOL_CLASS", "read"]

# Every tool agy 1.3.3 advertises (its `init.tools`, 60 ids), in ADR-0004's classes. Only shell, file read and file edit
# are in the profile. agy's grant kinds cannot deny every other class (Leader ruling on R-TRANSPORT seam 5): web search,
# browser, image, sub-agent, MCP, scheduling and messaging tools run under the profile's rules, so a call to one is
# detected here as class `other` (HB-VAL-008), not prevented. An id missing from this map is `other` too.
_SHELL = ("run_command", "send_command_input", "command_status")
_EDIT = ("write_to_file", "replace_file_content", "multi_replace_file_content", "sed_file", "notebook_edit")
_READ = ("view_file", "list_dir", "find_by_name", "grep_search")
_OTHER = (
    # browser
    "browser_click_element", "browser_drag_pixel_to_pixel", "browser_get_dom", "browser_get_network_request",
    "browser_input", "browser_list_network_requests", "browser_mouse_down", "browser_mouse_up", "browser_move_mouse",
    "browser_press_key", "browser_refresh_page", "browser_resize_window", "browser_scroll", "browser_scroll_dom",
    "browser_select_option", "capture_browser_console_logs", "capture_browser_screenshot", "click_browser_pixel",
    "execute_browser_javascript", "list_browser_pages", "open_browser_url", "read_browser_page",
    # web, image, MCP and resources
    "search_web", "read_url_content", "generate_image", "call_mcp_tool", "list_resources", "read_resource",
    # sub-agents (out of profile on every cell by the ruling, never `delegate`)
    "browser_subagent", "invoke_subagent", "define_subagent", "manage_subagents",
    # scheduling, messaging, tasks, workflows, plugins, knowledge
    "schedule", "send_message", "manage_inbox", "manage_task", "run_workflow", "search_marketplace",
    "list_plugin_accounts", "delete_knowledge", "notebook_execution",
    # the user and permissions (no scripted user on agy, ADR-0028 s7)
    "ask_question", "ask_permission", "ask_custom_permission", "list_permissions",
    # turn control: they touch nothing in the workspace, but ADR-0004 allows only the three classes above
    "finish", "wait", "wait_5_seconds",
)
TOOL_CLASS = (dict.fromkeys(_SHELL, "shell") | dict.fromkeys(_EDIT, "edit") | dict.fromkeys(_READ, "read")
              | dict.fromkeys(_OTHER, "other"))

STORE = (".gemini", "antigravity-cli", "conversations")
_CONVERSATION_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{0,127}")  # a file name: no separator, dot or drive
_RULE = re.compile(r"<RULE\[(?P<path>[^\]\r\n]{1,1024})\]>(?P<body>.*?)</RULE\[(?P=path)\]>", re.DOTALL)
PROMPT_SOURCE = "conversations/<id>.db gen_metadata.data 1.1"
RULE_SOURCE = PROMPT_SOURCE + " <RULE[...]>"
NO_DB = "not recorded: conversation db not found"


class WireError(ValueError):
    """A byte string that is not a well-formed protobuf message."""


def _varint(b: bytes, i: int) -> tuple[int, int]:
    n = shift = 0
    while shift < 70:
        if i >= len(b):
            raise WireError("truncated varint")
        c = b[i]
        i += 1
        n |= (c & 0x7F) << shift
        if not c & 0x80:
            return n, i
        shift += 7
    raise WireError("varint over 10 bytes")


def fields(b: bytes) -> list[tuple[int, int, int | bytes]]:
    """(field number, wire type, value) for every field of one message, all or nothing: varint (0), fixed64 (1),
    length-delimited (2) and fixed32 (5). A value is an int (varint) or bytes."""
    out: list[tuple[int, int, int | bytes]] = []
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise WireError("field number 0")
        if wire == 0:
            value, i = _varint(b, i)
        elif wire in (1, 2, 5):
            size, i = (_varint(b, i) if wire == 2 else (8 if wire == 1 else 4, i))
            if i + size > len(b):
                raise WireError("truncated field")
            value, i = b[i:i + size], i + size
        else:
            raise WireError(f"wire type {wire}")
        out.append((number, wire, value))
    return out


def _at(b: bytes, *path: int) -> list[bytes]:
    """Every length-delimited value at `path` (a repeated field at any level gives several)."""
    level = [b]
    for number in path:
        level = [v for m in level for f, w, v in fields(m) if f == number and w == 2]
    return level


def _thoughts(payload: bytes | None) -> list[tuple[str, str | bytes]] | None:
    """A planner-response step's reasoning items in order: ("summary", text) per field 20.3, then ("opaque", bytes) per
    20.14.2.1 and 20.7.7.2.1. None when the payload is absent, does not decode, or 20.3 is not UTF-8."""
    if payload is None:
        return None
    try:
        out: list[tuple[str, str | bytes]] = []
        for response in _at(payload, 20):
            out += [("summary", v.decode("utf-8")) for v in _at(response, 3)]
            out += [("opaque", v) for v in _at(response, 14, 2, 1)]
            out += [("opaque", v) for call in _at(response, 7) for v in _at(call, 7, 2, 1)]
        return out
    except (WireError, UnicodeDecodeError):
        return None


def _prompt(blobs: list[bytes]) -> str | None:
    """The full prompt (field 1.1) of the first request in `gen_metadata` that has one."""
    for data in blobs:
        try:
            prompts = _at(data, 1, 1)
            if prompts:
                return prompts[0].decode("utf-8")
        except (WireError, UnicodeDecodeError):
            continue
    return None


def _store(path: Path, conversation_id: str | None) -> Path | None:
    if conversation_id is None or not _CONVERSATION_ID.fullmatch(conversation_id):
        return None
    db = path.parent.joinpath(*STORE, conversation_id + ".db")
    return db if db.is_file() else None


def _read_store(db: Path) -> tuple[dict[int, bytes], list[bytes]]:
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        steps = {idx: bytes(p) for idx, p in con.execute("select idx, step_payload from steps")
                 if type(idx) is int and isinstance(p, bytes)}
        gens = [bytes(d) for (d,) in con.execute("select data from gen_metadata order by idx") if isinstance(d, bytes)]
    return steps, gens


def _reasoning(calls: list[tuple[int | None, int, int | None]], steps: dict[int, bytes]) -> list[ReasoningItem]:
    items: list[ReasoningItem] = []
    for index, n, thinking in calls:
        found = _thoughts(steps.get(index)) if index is not None else None
        if not found:
            items.append(ReasoningItem(n, 0, "omitted", None, None, thinking, None))
            continue
        for k, (kind, value) in enumerate(found):  # the request's thinking count rides on its first item only
            tokens = thinking if k == 0 else None
            items.append(ReasoningItem(n, k, "summary", value, len(value), tokens, None) if kind == "summary" else
                         ReasoningItem(n, k, "encrypted-only", None, None, tokens, hashlib.sha256(value).hexdigest()))
    return items


def _prompt_parts(gens: list[bytes]) -> list[PromptPart] | str:
    text = _prompt(gens)
    if text is None:
        return not_recorded("no request prompt in gen_metadata")[1]
    return [PromptPart("system", None, len(text), "inlined", PROMPT_SOURCE)] + [
        PromptPart("instruction_file", m["path"], len(m["body"]), "inlined", RULE_SOURCE) for m in _RULE.finditer(text)]


def read(path: Path) -> Extraction:
    ex = Extraction()
    model: str | None = None
    calls: list[tuple[int | None, int, int | None]] = []  # (step_index, line, thinking_tokens) per model call
    tools: dict[object, dict] = {}
    for n, row in rows(path, ex):
        kind = row.get("event")
        if kind == "init":
            ex.session_id = ex.session_id or as_str(row.get("conversation_id"))
            model = model or as_str(as_dict(row.get("init")).get("model"))
            continue
        if kind != "step_update":
            continue
        step = as_dict(row.get("step_update"))
        index = step.get("step_index") if type(step.get("step_index")) is int else None
        state, info = step.get("state"), as_dict(step.get("tool_info"))
        usage = step.get("usage")
        if step.get("step_type") == "agent_response" and state == "DONE" and isinstance(usage, dict):
            if model is None:
                ex.missing.append(MissingField(n, "model"))
            cache_read = ex.count(n, usage, "cache_read_tokens")
            # assume: agy's input_tokens includes cache_read_tokens (as Gemini's promptTokenCount includes cached
            # content). Confirm: a cached turn where input_tokens < cache_read_tokens would refute it (every spike value
            # is 0). Breaks: uncached_input on a cached turn. agy reports no cache-write bucket: cache_write is 0.
            uncached = max(ex.count(n, usage, "input_tokens") - cache_read, 0)
            thinking = usage.get("thinking_tokens") if is_count(usage.get("thinking_tokens")) else None
            ex.model_calls.append(ModelCall(n, model or "NOT_RECORDED", uncached, cache_read, 0,
                                            ex.count(n, usage, "output_tokens"), thinking))
            calls.append((index, n, thinking))
        elif step.get("step_type") == "tool":
            name = as_str(step.get("tool_name")) or as_str(info.get("name")) or "NOT_RECORDED"
            tool = tools.setdefault(index if index is not None else ("line", n), {"n": n, "name": name, "ok": None,
                                                                                   "code": None})
            if state == "ERROR":
                tool["ok"], tool["code"] = False, as_str(as_dict(info.get("error")).get("type"))
    ex.tool_calls = [ToolCall(t["n"], t["name"], TOOL_CLASS.get(t["name"], "other"), None, None, t["ok"], t["code"])
                     for t in sorted(tools.values(), key=lambda t: t["n"])]
    no_context = not_recorded("the agy stream carries no context window")
    ex.served = ServedSettings(
        model_served=model or not_recorded("no init.model in the agy stream"),
        model_api=not_recorded("the agy stream names only the served model"),
        effort=not_recorded("the agy stream carries no effort"),
        context_tokens=no_context, context_tier=no_context,
        reasoning_summary=not_recorded("the agy stream carries no reasoning-summary setting"),
        sources={"model_served": "agy-stream.ndjson init.model"} if model else {})
    ex.harness_events = not_recorded("agy steps are a Flagged source for hooks, skills and compaction; not read")[1]
    db = _store(path, ex.session_id)
    if db is None:
        ex.reasoning = ex.prompt_parts = NO_DB
        return ex
    try:
        steps, gens = _read_store(db)
    except sqlite3.Error as exc:
        ex.reasoning = ex.prompt_parts = not_recorded(f"conversation db unreadable ({type(exc).__name__})")[1]
        return ex
    ex.reasoning = _reasoning(calls, steps)
    ex.prompt_parts = _prompt_parts(gens)
    return ex
