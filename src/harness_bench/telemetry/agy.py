"""Antigravity native record reader (ADR-0025 s6, ADR-0026 s1).

Pattern: Anti-Corruption Layer, the same shapes as the other readers. It reads the teed stream (`agy-stream.ndjson`,
stream_driver.STREAM_RECORD) and the conversation store beside it, `<cell home>/.gemini/antigravity-cli/conversations/
<conversation id>.db` (the spike's layout; bench/profiles/agy.yaml `record_glob`). It reads the stream's event bodies
(`init`, `step_update`, tool steps) only; the input event and the outcome grammar stay in `stream_driver.py`
(tests/test_architecture.py), so no denial or turn status is read here.

- served: `model_served` is `init.model`; `effort` is its `-low|-medium|-high` suffix (none: not recorded). The stream
  carries no context window or reasoning summary.
- model calls: one per `agent_response` step in state DONE with `usage`, at that line. `reasoning` is
  `thinking_tokens`, a component of `output_tokens` (215 of 216 on the spike's one-word turn).
- tool calls: one per tool step, at its first line. A DONE state is not success (the spike's turn1 `run_command` reached
  DONE while agy denied it); an ERROR state is `ok` False with the native `error.type`. Otherwise `ok` comes from the
  conversation db row of the same `step_index` (W13, `_outcome`): status 3 completed (a `run_command` by its exit code,
  non-zero is `exit_<N>`), status 6 refused or cancelled (`status_6`); None when there is no db or the row does not say.
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
  A7 (lean run lean-20261013T222840): the recorded prompt holds no tool declarations (no schema; one prose mention of
  `view_file`), so there is no `tools` part. Whether another `gen_metadata` field holds them is not decoded (Inferred
  gap; confirm by decoding the remaining fields of a request).
- harness events: not read (steps are a Flagged source, ADR-0026 s1). C4: hook time is not recorded by the harness.
  In all 30 pack-on cells of that run `cli.log` says `loaded 5 named hooks from 1 hooks.json file(s)`, yet no stream
  line, step type or log line records a hook invocation, and tool steps carry no times, so no bound is derivable.
- `tool_inputs` (the report's and attention drift's trace): the same tool steps as `read`, keyed by step index. A step's
  parameters ride on its first line; its `output` on the closing line.
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
    ProcessTrace,
    PromptPart,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    ToolInput,
    as_dict,
    as_str,
    is_count,
    not_recorded,
    rows,
)

__all__ = ["TOOL_CLASS", "read", "read_db", "tool_inputs", "tool_inputs_db"]

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
    "send_message", "manage_inbox", "run_workflow", "search_marketplace",
    "list_plugin_accounts", "delete_knowledge", "notebook_execution",
    # permission requests (no scripted user on agy, ADR-0028 s7): they ask for a grant, so they stay out of profile
    "ask_permission", "ask_custom_permission",
)
# Workspace-inert (Leader ruling agy-meta-rerun, as Grok's todo_write ruling J1A-FIX item 24 and ToolSearch R-54 (a),
# claude_code.py): the task list, the question to an absent user, the grant listing and turn control touch nothing in
# the workspace, so they are counted, never scored. Measured: probe-rerun-1's agy cells were HB-VAL-008 on manage_task only.
# Amendment 2026-10-14 (owner decision, lean runs of 2026-10-13 plan row B16): `schedule` is turn control too. NG1 pack-on
# r1 called schedule(DurationSeconds=30, ...) as a timer to wait for its own background command; agy cancelled it at once.
_META = ("manage_task", "ask_question", "list_permissions", "finish", "wait", "wait_5_seconds",
         "schedule")  # B16, owner decision 2026-10-14: a `schedule` used as a wait touches nothing, as `wait` does
TOOL_CLASS = (dict.fromkeys(_SHELL, "shell") | dict.fromkeys(_EDIT, "edit") | dict.fromkeys(_READ, "read")
              | dict.fromkeys(_META, "meta")
              | dict.fromkeys(_OTHER, "other"))

STORE = (".gemini", "antigravity-cli", "conversations")
_CONVERSATION_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{0,127}")  # a file name: no separator, dot or drive
_RULE = re.compile(r"<RULE\[(?P<path>[^\]\r\n]{1,1024})\]>(?P<body>.*?)</RULE\[(?P=path)\]>", re.DOTALL)
PROMPT_SOURCE = "conversations/<id>.db gen_metadata.data 1.1"
RULE_SOURCE = PROMPT_SOURCE + " <RULE[...]>"
NO_DB = "not recorded: conversation db not found"
# Leader ruling PROBE-FIX-2 B (DR option a): agy names the effort in the model id (`gemini-3.8-flash-high`), so the served
# effort is the served init.model's level suffix; an id with none records no effort.
_EFFORT_SUFFIX = re.compile(r"-(low|medium|high)$")
EFFORT_SOURCE = "agy-stream.ndjson init.model suffix"


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


def _read_store(db: Path) -> tuple[dict[int, bytes], list[bytes], dict[int, int]]:
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        rows_ = [(idx, st, p) for idx, st, p in con.execute("select idx, status, step_payload from steps")
                 if type(idx) is int and isinstance(p, bytes)]
        gens = [bytes(d) for (d,) in con.execute("select data from gen_metadata order by idx") if isinstance(d, bytes)]
    return {idx: bytes(p) for idx, _, p in rows_}, gens, {idx: st for idx, st, _ in rows_ if type(st) is int}


# `steps.status` (W13; Verified on the lean run of 2026-10-13: 1,900 tool steps): 3 the step completed, 7 it errored
# (the stream says ERROR too), 6 it was refused or cancelled (the stream says DONE, as for the spike's denied run_command;
# one real "context canceled" step). The result text of a completed run_command, field 140.2.1, opens with
# "The command exited with code N." (every one of 752 completed run_commands). The stream carries neither.
_EXIT = re.compile(r"\s*The command exited with code (-?\d+)\.")


def _exit_code(payload: bytes | None) -> int | None:
    try:
        text = next((v.decode("utf-8") for v in _at(payload, 140, 2, 1)), "") if payload else ""
    except (WireError, UnicodeDecodeError):
        return None
    found = _EXIT.match(text)
    return int(found.group(1)) if found else None


def _outcome(name: str, status: int | None, payload: bytes | None) -> tuple[bool | None, str | None]:
    """`(ok, outcome_code)` of one tool step from the db row; a stream ERROR is decided by the caller. A failed command
    (non-zero exit, a failing test run included) is `exit_<N>`, a refused or cancelled step `status_6`. None when the db
    does not say: no db, an unknown status, or a run_command whose result names no exit code."""
    if status == 6:
        return False, "status_6"
    if status != 3:
        return None, None
    if name != "run_command":
        return True, None
    code = _exit_code(payload)
    return (None, None) if code is None else (True, None) if code == 0 else (False, f"exit_{code}")


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
    return [PromptPart(0, "system", None, len(text), "inlined", PROMPT_SOURCE)] + [
        PromptPart(n, "instruction_file", m["path"], len(m["body"]), "inlined", RULE_SOURCE)
        for n, m in enumerate(_RULE.finditer(text), 1)]


# A parameter that names a file or directory. Verified on the lean agy run: view_file.AbsolutePath, write_to_file and
# replace_file_content.TargetFile. Inferred for the tools that run did not call (list_dir, find_by_name, grep_search,
# multi_replace_file_content...): agy ships no tool schema in any record, so the suffix rule stands in for it. Confirmed
# by: one archived call of each; breaks if false: that tool's path is missed, so attention drift undercounts its targets.
_PATH_PARAM = re.compile(r"(?:Path|File|Dir|Directory)$")
# view_file's `output` is "<n> lines, <m> bytes": the viewed file's size, not what came back (a 175,676-byte file gave a
# 61,837-byte step payload), so it is no result size.
_FILE_STATS = re.compile(r"\d+ lines, \d+ bytes")


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from the stream's tool steps, in native order (the line a step first appears on), plus the
    user-visible reply text. The tool steps are `read`'s: one per step index, so the two counts are equal (R-85
    condition 1). `bytes_returned` is the UTF-8 size of a step's `output` text (run_command, manage_task...); None when
    the step has no output text or only the file-stats line. Reply text is the `text_delta`s of each `agent_response`
    step joined (Verified on the lean agy run: a turn's `result.response` is exactly these joined, 72 of 72); thinking
    is never streamed, so none is counted. A step whose text is blank is no message. None for both counts when the
    stream shows no reply step or was cut short."""
    ex = Extraction()
    tools: dict[object, dict] = {}
    replies: dict[object, list[str]] = {}
    for n, row in rows(path, ex):
        if row.get("event") != "step_update":
            continue
        step = as_dict(row.get("step_update"))
        index = step.get("step_index") if type(step.get("step_index")) is int else None
        if step.get("step_type") == "agent_response":
            texts = replies.setdefault((step.get("conversation_id"), index), [])
            if (delta := as_str(step.get("text_delta"))):
                texts.append(delta)
        elif step.get("step_type") == "tool":
            info = as_dict(step.get("tool_info"))
            tool = tools.setdefault(index if index is not None else ("line", n), {"n": n, "name": None, "params": {}, "output": None})
            tool["name"] = tool["name"] or as_str(step.get("tool_name")) or as_str(info.get("name"))
            tool["params"] = tool["params"] or as_dict(info.get("parameters"))
            if (output := as_str(info.get("output"))) is not None:
                tool["output"] = output
    calls: list[ToolInput] = []
    for tool in sorted(tools.values(), key=lambda t: t["n"]):
        name, params, output = tool["name"] or "NOT_RECORDED", tool["params"], tool["output"]
        paths = tuple(dict.fromkeys(v for k, v in params.items() if _PATH_PARAM.search(k) and isinstance(v, str) and v))
        size = None if output is None or _FILE_STATS.fullmatch(output) else len(output.encode("utf-8"))
        calls.append(ToolInput(tool["n"], name, paths, as_str(params.get("CommandLine")),
                               TOOL_CLASS.get(name, "other") == "edit", size))
    messages = ["".join(t) for t in replies.values() if "".join(t).strip()]
    counted = bool(replies) and not ex.truncated
    return ProcessTrace(messages[0] if messages else None, tuple(calls), sum(map(len, messages)) if counted else None,
                        len(messages) if counted else None)


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
            # input_tokens excludes cache_read_tokens (Verified, devprobe-rerun-1 agy-off step 13: input 3302 beside
            # cache_read 16260, total_tokens = input + output), so it is the uncached input as recorded. agy reports no
            # cache-write bucket: cache_write is 0.
            uncached, cache_read = ex.count(n, usage, "input_tokens"), ex.count(n, usage, "cache_read_tokens")
            thinking = usage.get("thinking_tokens") if is_count(usage.get("thinking_tokens")) else None
            ex.model_calls.append(ModelCall(n, model or "NOT_RECORDED", uncached, cache_read, 0,
                                            ex.count(n, usage, "output_tokens"), thinking))
            calls.append((index, n, thinking))
        elif step.get("step_type") == "tool":
            name = as_str(step.get("tool_name")) or as_str(info.get("name")) or "NOT_RECORDED"
            tool = tools.setdefault(index if index is not None else ("line", n), {"n": n, "name": name, "ok": None,
                                                                                   "code": None, "index": index})
            if state == "ERROR":
                tool["ok"], tool["code"] = False, as_str(as_dict(info.get("error")).get("type"))
    db = _store(path, ex.session_id)
    store, unread = None, NO_DB
    if db is not None:
        try:
            store = _read_store(db)
        except sqlite3.Error as exc:
            unread = not_recorded(f"conversation db unreadable ({type(exc).__name__})")[1]
    steps, gens, statuses = store or ({}, [], {})
    ex.tool_calls = []
    for t in sorted(tools.values(), key=lambda t: t["n"]):  # a stream ERROR decides; else the db row, if there is one
        ok, code = (t["ok"], t["code"]) if t["ok"] is not None else _outcome(t["name"], statuses.get(t["index"]),
                                                                           steps.get(t["index"]))
        ex.tool_calls.append(ToolCall(t["n"], t["name"], TOOL_CLASS.get(t["name"], "other"), None, None, ok, code))
    no_context = not_recorded("the agy stream carries no context window")
    effort = _EFFORT_SUFFIX.search(model or "")
    sources = {"model_served": "agy-stream.ndjson init.model"} if model else {}
    if effort:
        sources["effort"] = EFFORT_SOURCE
    ex.served = ServedSettings(
        model_served=model or not_recorded("no init.model in the agy stream"),
        model_api=not_recorded("the agy stream names only the served model"),
        effort=effort.group(1) if effort else not_recorded("the served init.model carries no effort suffix"),
        context_tokens=no_context, context_tier=no_context,
        reasoning_summary=not_recorded("the agy stream carries no reasoning-summary setting"),
        sources=sources)
    ex.harness_events = not_recorded("agy steps are a Flagged source for hooks, skills and compaction; not read")[1]
    if store is None:
        ex.reasoning = ex.prompt_parts = unread
        return ex
    ex.reasoning = _reasoning(calls, steps)
    ex.prompt_parts = _prompt_parts(gens)
    return ex


# --- The conversation db alone: an interactive session writes no stream (bench interactive, 2026-10-14) -------------
# Field map Verified against the lean run of 2026-10-13 (60 cells, 1,542 stream model calls paired with 1,542 db rows,
# every value equal): a response step (`steps.step_type` 15) carries its request's usage in `steps.metadata` field 9 -
# 9.2 uncached input, 9.3 output (thinking included), 9.5 cache read, 9.9 thinking; a field is absent when 0, and there
# is no cache-write bucket. `steps.metadata` is the more complete source: two interactive dbs lacked the last request's
# `gen_metadata` row. The served model is `gen_metadata` 1.19 (a string); the effort is in no db field.
RESPONSE_STEP = 15
DB_SOURCE = "conversations/<id>.db steps.metadata 9 (step_type 15)"


def _db_rows(db: Path) -> tuple[list[tuple[int, int, bytes | None, bytes | None, int | None]], list[bytes]]:
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        steps = [(idx, st, bytes(m) if isinstance(m, bytes) else None, bytes(p) if isinstance(p, bytes) else None,
                  s if type(s) is int else None)
                 for idx, st, m, p, s in con.execute("select idx, step_type, metadata, step_payload, status from steps order by idx")
                 if type(idx) is int]
        gens = [bytes(d) for (d,) in con.execute("select data from gen_metadata order by idx") if isinstance(d, bytes)]
    return steps, gens


def _db_model(gens: list[bytes]) -> str | None:
    for data in gens:
        try:
            names = _at(data, 1, 19)
            if names:
                return names[0].decode("utf-8")
        except (WireError, UnicodeDecodeError):
            continue
    return None


def _db_tool_calls(payload: bytes | None) -> list[tuple[str, dict]]:
    """(name, arguments) of every tool call in one response step's planner response (20.7.2 name, 20.7.3 JSON)."""
    import json

    out = []
    try:
        for call in (c for r in _at(payload, 20) for c in _at(r, 7)) if payload else ():
            name = next((v.decode("utf-8") for v in _at(call, 2)), "NOT_RECORDED")
            raw = next((v.decode("utf-8") for v in _at(call, 3)), "")
            try:
                args = json.loads(raw) if raw else {}
            except ValueError:
                args = {}
            out.append((name, args if isinstance(args, dict) else {}))
    except (WireError, UnicodeDecodeError):
        return out
    return out


def read_db(db: Path) -> Extraction:
    """The model calls (one per response step with usage) and tool calls (the planner's calls, at the step that made
    them) of a conversation db alone. A tool call's outcome is not joined here (`ok` None): the tool's own step is not
    keyed to the call in any field decoded so far."""
    ex = Extraction(session_id=db.stem)
    steps, gens = _db_rows(db)
    model = _db_model(gens)
    for idx, step_type, meta, payload, _status in steps:
        if step_type != RESPONSE_STEP:
            continue
        try:
            usage = _at(meta, 9) if meta else []
            counts = {f: v for f, w, v in fields(usage[0]) if w == 0} if usage else None
        except WireError:
            counts = None
        if counts is not None:
            ex.model_calls.append(ModelCall(idx, model or "NOT_RECORDED", counts.get(2, 0), counts.get(5, 0), 0,
                                            counts.get(3, 0), counts.get(9, 0)))
        for name, _args in _db_tool_calls(payload):
            ex.tool_calls.append(ToolCall(idx, name, TOOL_CLASS.get(name, "other"), None, None, None))
    unmapped = not_recorded("the agy db's context figure (1.9.10.4) is not mapped to a served window")
    ex.served = ServedSettings(
        model_served=model or not_recorded("no model name (gen_metadata 1.19) in the db"),
        model_api=not_recorded("the agy db names only the served model"),
        effort=not_recorded("the agy db names no effort"), context_tokens=unmapped, context_tier=unmapped,
        reasoning_summary=not_recorded("the agy db carries no reasoning-summary setting"),
        sources={"model_served": "conversations/<id>.db gen_metadata 1.19"} if model else {})
    ex.harness_events = not_recorded("agy steps are a Flagged source for hooks, skills and compaction; not read")[1]
    ex.prompt_parts = _prompt_parts(gens)
    return ex


def tool_inputs_db(db: Path) -> ProcessTrace:
    """`ToolInput`s of a conversation db alone, at the response step that made each call (as `read_db`)."""
    steps, _gens = _db_rows(db)
    calls = []
    for idx, step_type, _meta, payload, _status in steps:
        if step_type != RESPONSE_STEP:
            continue
        for name, args in _db_tool_calls(payload):
            paths = tuple(dict.fromkeys(v for k, v in args.items() if _PATH_PARAM.search(k) and isinstance(v, str) and v))
            calls.append(ToolInput(idx, name, paths, as_str(args.get("CommandLine")), TOOL_CLASS.get(name, "other") == "edit"))
    return ProcessTrace(None, tuple(calls))
