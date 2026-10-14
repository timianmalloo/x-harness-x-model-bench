"""Copilot native record: a per-cell ACP home's `session-state/<session id>/events.jsonl` (design
docs/design/phase2-copilot-profile.md section 4.4; capture window 1, fixture `9c6c615`, rescrubbed
`f952f87`). There is no `session-store.db`: a per-cell ACP home holds none (O6).

Patterns: a Format Indicator with a fail-closed version gate, and a Tolerant Reader for fields
(design section 4.4). `session.start.data.version` must be in `SUPPORTED_EVENT_VERSIONS`; when it is
not, or there is no `session.start`, model calls and hook counts degrade to HB-TEL-001 rather than a
best-effort read of an unknown format (F6). Every other harness's reader stays a plain Tolerant Reader
because its record carries the CLI build version, not a distinct format version (design section 4.4).

- `model_calls`: one `ModelCall` per key of the **last** `session.shutdown.data.modelMetrics`
  (ADR-0006 Amendment 1; `native_ordinal` is that line, shared by every model reported on it). The
  buckets are disjoint (design's arithmetic check: `tokenDetails.input + cacheRead + cacheWrite ==
  usage.inputTokens`, else HB-TEL-001 `input_tokens`, F7); `reasoning` is a component of output and is
  never added into it. `start`/`end` are set only for a single-request report (`requests == 1`), from
  the shutdown row's own timestamp -- Copilot keeps no per-call clock (design section 3), so a
  multi-request report's model time is NOT_RECORDED. `total_nano_aiu` is
  `modelMetrics.<model>.totalNanoAiu`, stored verbatim (ADR-0006 Amendment 2, R-15 Q6); null, never 0,
  when the key is absent or not an int -- no second definition of tokens is derived from it. Its absence
  is **not** added to `ex.missing`: no reader consumes it yet, and `ex.missing` gates `cost_usd`
  (`grade/runner.py`); the null on the row is its own "not recorded" evidence (R-15 Q6 loop-back).
- `tool_calls`: `tool.execution_start` paired with `tool.execution_complete` by `toolCallId` (the
  Correlation Identifier), even when completions arrive interleaved or out of order across several
  open calls. `outcome_code` is `data.error.code`, but only when the call did not succeed: **null on
  `success: true`** regardless of a stray `error.code` (`ToolCall.outcome_code`'s own contract), and
  null too when there is no `error` object. `ok` follows Claude Code, Codex and agy (W14): a `success: true` call
  whose `shellExecution.exitCode` is a non-zero int is `ok` False with `outcome_code` `exit_<N>` (on the 6.1 lean run
  260 of 906 powershell calls); `success` alone says the tool ran. A denial keeps `denied`.
- `hook_starts` / `hook_failures` (US-9's live signal, design section 4.5): counted only once the
  version gate passes -- otherwise, like the model calls, NOT_RECORDED (`None`). `tool_calls` and
  `first_user_text` are **not** gated by the version check (the design scopes the gate to model rows
  only, section 4.4): a consumer must not treat them as measured when `Extraction.missing` carries
  `events.version` -- only `model_calls` and the hook counts are NOT_RECORDED in that case.
- `first_user_text` (US-10): the first `user.message` with no top-level `agentId` (a sub-agent's
  message always carries one; `assume:` confirmed by `session-profile.py:708-716` and the operator-log
  census, O7 revision 2; breaks if a sub-agent's prompt were compared instead -- covered by a synthetic
  sub-agent-first sample). Its `data.content`, never `data.transformedContent` (the scrubbed value).
- `session_id`: `session.start.data.sessionId`, else the record's own directory name
  (`session-state/<session id>/events.jsonl`), so a session is still identified when the record itself
  omits it.
- The version gate is `type(version) is int and version in SUPPORTED_EVENT_VERSIONS` (never a bare
  `in`, which raises on an unhashable `version` such as a list -- T-TEL-fuzz D2); a bare `True` or
  `1.0` fails the gate too (`type(...) is int` excludes `bool` and `float`, unlike `==`).

The lean re-run's facts (ADR-0026 s1-2, ADR-0024 s4; R-READ-COPILOT), filled only once the version gate passes
(otherwise each stream is one `not recorded` reason). The second source is the cell home's `--log-level debug`
process logs (`logs/process-<ms>-<pid>.log`, one per `-p` turn child, joined in name order): each
`[rust:model_wire] Wire request:` body and each `[rust:model_wire] data:` response body, multi-line JSON up to
the next stamped line. A request pairs with the next response (first in, first out), and only requests whose
`X-Client-Session-Id` is this session count. A response's `id` is its `assistant.message.apiCallId` (Verified on
the R-COPILOT-P and Sol Fast records), which keys every per-request fact to the record's own line.
- `served`: one `ServedSettings` per source. The session record: `session.start.{selectedModel,
  reasoningEffort, contextTier}`; a field the row carries as null is a measured null (value None, no reason),
  one it does not carry is `not recorded` (seam from R-VALIDITY: HB-VAL-010 vs HB-VAL-011). `-p` judges the
  window by tier, so `context_tokens` is `not recorded`. The debug log: the request's `model`,
  `reasoning.effort` and `reasoning.summary`, and the response's `model` as `model_api` (gpt-5.6-sol for
  gpt-5.6-sol-fast); one settings per distinct combination, so a disagreement is two rows the view refuses.
- `model_calls`: per response from the debug log, `uncached = prompt_tokens - cached_tokens -
  cache_write_tokens`, `start`/`end` the request and response log stamps, `total_nano_aiu` null (the log
  shows none per request). They replace the shutdown rows only when, per model, their request count and every
  bucket equal the shutdown's; otherwise (no log, a lost turn log, a torn body) the shutdown rows stay, which are
  the per-session totals (`requests` > 1, no clock).
- `reasoning`: one item per `assistant.message`: `summary` with `reasoningText`, else `encrypted-only` with the
  sha256 of `encryptedContent` (or `reasoningOpaque`), else `omitted` when the log shows reasoning tokens.
  `reasoning_tokens` is the response's, on the first message of that response.
- `prompt_parts`: the first request's `instructions`, partitioned: each `<custom_instruction>` and each
  `<imported_custom_instruction source=...>` inside it, each `---\\napplyTo:` instruction file after them, each
  `<available_skills>` entry (`skills`, listed), the rest `system`; the "instruction files" table rows are
  `instruction_file` listed (no chars). Tools are one `tools` row, listed: the log carries names and digests only.
  A7 (lean runs lean-20261013T222133 and lean-20261013T222416, `copilot -p`): the full tool definitions are in no
  file of the cell home (events.jsonl, the `-p` output stream, the debug process log), so the part has no character
  count. Their size is recorded only in tokens: `session.usage_checkpoint.data.promptCacheBreakState[].models[].
  tool_tokens` (2187 for 9 tools on both runs) beside `tool_count`; the count is `Extraction.tools_advertised` (the
  same checkpoint's `tools[].name`). The `tools` part carries the token size in `PromptPart.tokens` (ADR-0026
  amendment, 2026-10-14): the first checkpoint that states one size for its models; None when none does.
- `harness_events`: `hook.start`/`hook.end` paired by `hookInvocationId`; skill loads are `skill` tool calls.
  Compaction is not mapped: no record seen carries one (Flagged, ADR-0026 s1). C4: under `copilot -p` hook time is
  not recorded by the harness. The pack-on cells of both lean runs (.github/hooks/ai-forward.json wires preToolUse
  and postToolUse hooks) hold no `hook.start`/`hook.end` row, no hook event in the `-p` stream, and only hook-policy
  lines in the debug log, so `hook_starts` reads 0 there although hooks were configured. No cheap per-cell bound:
  the gap from the tool request (`assistant.message.toolRequests`) to `tool.execution_start` is 2-3 ms median both
  pack-on and pack-off. Inferred, not emitted: the median `view` call takes 60 ms on against 9 ms off (gpt-5.5) and
  730 ms against 46 ms (gpt-6.1-sol), which would put any hook time inside the tool call's interval.
  Did the hooks run under `copilot -p`? (W14 item 3, archived pack-on cells, 30 per run, both lean runs.) NOT
  DETERMINED. Checked for the hooks' side effects in each cell's `ws`: the sessionStart hook (`session-start.py`)
  writes a `__harness__:<session>` marker to `.agents/log/audit/.run-starts.json`, which the cells of Claude Code (20 of
  30 hold one, the rest consumed by the agent's own audit append) and agy (24 of 30) hold, and which no Copilot cell
  holds (0 of 60; the 5 empty `.run-starts.json` files of the 6.1 run are consumed markers, with no key left). The
  reread-guard's state file (`ai-forward-reread-guard-<sessionId>.json` in the temp dir) matches none of the 60 pack-on
  cells' session ids. That is absence of a trace, not proof: `session-start.py` exits silently when the payload carries
  no session id, heartbeat writes only with `AGENT_SESSION`, and the other hooks leave no file. So `hook_starts` 0 means
  "no `hook.start` row", NOT "no hook ran", and nothing reads it (`Extraction.hook_starts` has no consumer); the
  time-anatomy surface already says `no hook rows; a reader that reads none is not told apart from a cell that ran
  none` (`views.NO_HOOKS`). What would settle it: one short `copilot -p` run in a scratch repo whose
  `.github/hooks` wires a hook that writes a file.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from harness_bench.telemetry import (
    MAX_FILE,
    MAX_LINE,
    PATH_VERIFICATION,
    Extraction,
    HarnessEvent,
    MissingField,
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
    as_str,
    is_count,
    not_recorded,
    patch_header_paths,
    rows,
    unexpected_status,
)

__all__ = ["ProviderError", "read", "tool_inputs"]

SUPPORTED_EVENT_VERSIONS = {1}

# design pack-improvement-section.md section 4.3: is_write true for create, edit, str_replace_editor, apply_patch.
WRITE_TOOLS = {"create", "edit", "str_replace_editor", "apply_patch"}

TOOL_CLASS = {"powershell": "shell", "list_powershell": "shell", "read_powershell": "shell", "stop_powershell": "shell",
              "bash": "shell", "shell": "shell", "apply_patch": "edit", "write": "edit",
              "edit": "edit", "create": "edit", "view": "read", "glob": "read", "rg": "read", "grep": "read",
              "skill": "read",
              # R-74 item 1: start, address or read a sub-agent; in profile only in a scenario-6 cell (views)
              "task": "delegate", "write_agent": "delegate", "read_agent": "delegate", "list_agents": "delegate",
              "scripted_user-ask_user": "scripted user"}  # R-37 c2: the task's own MCP tool (a1-capture-1)


def _tool_class(name: str) -> str:
    return TOOL_CLASS.get(name, "other")


def read(path: Path) -> Extraction:
    ex = Extraction()
    version_seen = False
    version_ok = False
    last_shutdown: tuple[int, str | None, dict] | None = None  # (native_ordinal, row timestamp, data)
    open_tools: dict[str, dict] = {}
    path_requests: set[str] = set()  # requestId of a permission request whose `promptRequest.kind` is "path" (B10)
    path_denied: set[str] = set()  # toolCallId of a call that request was denied for
    hook_starts = 0
    hook_failures = 0
    saw_main_user = False
    start_data: dict | None = None
    messages: list[tuple[int, dict]] = []
    hooks: dict[str, list] = {}  # hookInvocationId -> [n, hookType, start, end, ok, detail]
    skills: dict[str, list] = {}  # toolCallId of a `skill` call -> [n, skill, start, end, ok]
    tool_tokens: int | None = None  # A7: the tool catalogue's size, in tokens, from the first usage checkpoint that states it

    for n, row in rows(path, ex):
        kind = row.get("type")
        data = as_dict(row.get("data"))
        stamp = as_str(row.get("timestamp"))

        if kind == "assistant.message":
            messages.append((n, data))
        if kind == "session.start":
            start_data = data if start_data is None else start_data
            version_seen = True
            version = data.get("version")
            version_ok = type(version) is int and version in SUPPORTED_EVENT_VERSIONS
            if ex.session_id is None:
                ex.session_id = as_str(data.get("sessionId"))
        elif kind == "user.message":
            if not saw_main_user and "agentId" not in row:
                text = as_str(data.get("content"))
                if text is not None:
                    ex.first_user_text = text
                    saw_main_user = True
        elif kind == "tool.execution_start":
            tool_call_id = as_str(data.get("toolCallId"))
            if tool_call_id is not None:
                open_tools[tool_call_id] = {"n": n, "name": as_str(data.get("toolName")) or "unknown", "start": stamp}
                if data.get("toolName") == "skill":
                    skills[tool_call_id] = [n, as_str(as_dict(data.get("arguments")).get("skill")), stamp, None, None]
        elif kind == "tool.execution_complete":
            tool_call_id = as_str(data.get("toolCallId"))
            if tool_call_id in skills and skills[tool_call_id][3] is None:
                success = data.get("success")
                skills[tool_call_id][3:] = [stamp, success if isinstance(success, bool) else None]
            if tool_call_id in open_tools:
                tool = open_tools.pop(tool_call_id)
                success = data.get("success")
                ok = success if isinstance(success, bool) else None
                error = as_dict(data.get("error"))
                outcome_code = None if ok is True else as_str(error.get("code"))
                exit_code = as_dict(data.get("shellExecution")).get("exitCode")
                if ok is True and type(exit_code) is int and exit_code != 0:  # `success` says the tool ran; the exit code is the outcome (W14)
                    ok, outcome_code = False, f"exit_{exit_code}"
                basis = PATH_VERIFICATION if outcome_code == "denied" and tool_call_id in path_denied else None
                ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], stamp, ok,
                                              outcome_code, basis))
        elif kind == "permission.requested":
            # Verified on the lean runs of 2026-10-13: `data.promptRequest` {kind: "path", accessKind, paths} beside
            # `permissionRequest` (kind "shell"). A preToolUse hook denial writes no permission.* row.
            request_id = as_str(data.get("requestId"))
            if request_id is not None and as_dict(data.get("promptRequest")).get("kind") == "path":
                path_requests.add(request_id)
        elif kind == "permission.completed":
            denied = (as_str(as_dict(data.get("result")).get("kind")) or "").startswith("denied")
            call_id = as_str(data.get("toolCallId"))
            if denied and call_id is not None and as_str(data.get("requestId")) in path_requests:
                path_denied.add(call_id)
        elif kind == "hook.start":
            hook_starts += 1
            hook_id = as_str(data.get("hookInvocationId"))
            if hook_id is not None and hook_id not in hooks:
                hooks[hook_id] = [n, as_str(data.get("hookType")), stamp, None, None, None]
        elif kind == "hook.end":
            if data.get("success") is not True:
                hook_failures += 1
            hook = hooks.get(as_str(data.get("hookInvocationId")) or "")
            if hook is not None and hook[3] is None:
                success = data.get("success")
                ok = success if isinstance(success, bool) else None
                detail = None if ok is True else as_str(as_dict(data.get("error")).get("message"))
                hook[3:] = [stamp, ok, detail[:300] if detail else None]
        elif kind == "session.error":
            raw = as_str(data.get("message")) or ""  # no status field; `unexpected status NNN` in the text is the status
            ex.errors.append(ProviderError(n, unexpected_status(raw), as_str(data.get("errorType")) or "unknown", raw[:300]))
        elif kind == "session.usage_checkpoint":
            advertised, listed = [], False  # listed: some model carries a tools list, even an empty one (R-63 c1)
            sizes = set()  # `tool_tokens` of every model in this checkpoint
            for state in as_list(data.get("promptCacheBreakState")):
                for model in as_dict(as_dict(state).get("models")).values():
                    listed = listed or isinstance(as_dict(model).get("tools"), list)
                    if is_count(as_dict(model).get("tool_tokens")):
                        sizes.add(as_dict(model)["tool_tokens"])
                    for tool in as_list(as_dict(model).get("tools")):
                        name = as_str(as_dict(tool).get("name"))
                        if name is not None:
                            advertised.append(name)
            ex.tools_advertised = list(dict.fromkeys(advertised)) if listed else None
            if tool_tokens is None and len(sizes) == 1:  # the first checkpoint that states one size; models that differ are ambiguous
                tool_tokens = sizes.pop()
        elif kind == "session.shutdown":
            last_shutdown = (n, stamp, data)

    for tool in open_tools.values():  # a start with no matching complete (killed turn)
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)

    if ex.session_id is None:  # no session.start, or no sessionId on it: the record's own directory name
        ex.session_id = path.parent.name

    if not (version_seen and version_ok):
        ex.missing.append(MissingField(0, "events.version"))
        ex.served = ex.reasoning = ex.prompt_parts = ex.harness_events = _UNSUPPORTED
        return ex

    ex.hook_starts = hook_starts  # counted whether or not any hooks fired (US-9 live signal, design 4.5)
    ex.hook_failures = hook_failures

    logs = _debug_logs(path)
    pairs = _pairs(logs, ex.session_id)
    line_by_call: dict[str, int] = {}
    for n, data in messages:
        if (call := as_str(data.get("apiCallId"))) is not None:
            line_by_call.setdefault(call, n)
    ex.served = _served(start_data or {}, logs, pairs)
    ex.reasoning = _reasoning(messages, pairs, line_by_call)
    ex.prompt_parts = _prompt_parts(logs, pairs, tool_tokens)
    ex.harness_events = sorted([HarnessEvent(h[0], "hook", h[1], h[2], h[3], h[4], h[5]) for h in hooks.values()]
                               + [HarnessEvent(s[0], "skill_load", s[1], s[2], s[3], s[4], None) for s in skills.values()],
                               key=lambda e: e.native_ordinal)

    if last_shutdown is None:
        ex.missing.append(MissingField(0, "session.shutdown"))
        return ex

    n, stamp, shutdown_data = last_shutdown
    model_metrics = as_dict(shutdown_data.get("modelMetrics"))
    for model in sorted(model_metrics):
        metrics = as_dict(model_metrics[model])
        requests = ex.count(n, as_dict(metrics.get("requests")), "count")
        token_details = as_dict(metrics.get("tokenDetails"))
        usage = as_dict(metrics.get("usage"))
        uncached_input = ex.count(n, as_dict(token_details.get("input")), "tokenCount")
        cache_read = ex.count(n, usage, "cacheReadTokens")
        cache_write = ex.count(n, usage, "cacheWriteTokens")
        output = ex.count(n, usage, "outputTokens")
        reasoning = ex.count(n, usage, "reasoningTokens")
        # Not flagged in ex.missing (R-15 Q6 loop-back, D&P condition 1): no reader consumes this column
        # yet, and ex.missing gates cost_usd (grade/runner.py) -- a column with no consumer must not null
        # a scored metric. The null on the row itself is the "not recorded" evidence (ADR-0006 Amendment 2).
        raw_nano_aiu = metrics.get("totalNanoAiu")
        total_nano_aiu = raw_nano_aiu if is_count(raw_nano_aiu) else None

        usage_input = usage.get("inputTokens")
        if not (type(usage_input) is int and uncached_input + cache_read + cache_write == usage_input):
            ex.missing.append(MissingField(n, "input_tokens"))

        single_request = requests == 1
        ex.model_calls.append(ModelCall(n, model, uncached_input, cache_read, cache_write, output, reasoning,
                                        stamp if single_request else None, stamp if single_request else None, requests,
                                        total_nano_aiu=total_nano_aiu))

    per_request = _per_request(pairs, line_by_call)
    if per_request and _sums(per_request) == _sums(ex.model_calls):  # else the shutdown's per-session totals stay
        ex.model_calls = per_request
    return ex


_UNSUPPORTED = not_recorded("unsupported events.version")[1]
_NO_LOG = "no debug process log in the cell home"
_SESSION = "events.jsonl:session.start"
_DEBUG = "debug-log"
FINGERPRINT = "copilotToolsFingerprint"  # the `tools` prompt part's path: `copilotToolsFingerprint:<digest>`
_STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+Z) \[")
_REQUEST = "[rust:model_wire] Wire request: "
_DATA = "[rust:model_wire] data:"
_OPEN = "[rust:model_wire] {"
_LOG_NAME = re.compile(r"process-(\d+)-(\d+)\.log")
# simplify: one body is held whole (the pack-on instructions are 330 kB); ceiling 4 x MAX_LINE, past which the body
# is dropped and the per-request rows fall back to the session totals. Upgrade trigger: a measured body near 32 MiB.
_MAX_BODY = 4 * MAX_LINE


def _debug_logs(path: Path) -> list[Path]:
    """The cell home's debug process logs, oldest first: `<home>/session-state/<id>/events.jsonl` -> `<home>/logs`."""
    if path.parent.parent.name != "session-state":
        return []
    logs = path.parent.parent.parent / "logs"
    found = [p for p in logs.glob("process-*.log") if _LOG_NAME.fullmatch(p.name)] if logs.is_dir() else []
    return sorted(found, key=lambda p: tuple(int(g) for g in _LOG_NAME.fullmatch(p.name).groups()))


def _wire(log: Path) -> Iterator[tuple[str, str, dict]]:
    """(`request` | `response`, its log stamp, its JSON body) for each model_wire body, in log order, bounded like
    `rows` (MAX_FILE per log). A body that does not parse is skipped."""
    kind, stamp, buf, size, data_stamp, read = None, "", [], 0, None, 0
    with log.open("rb") as f:
        while raw := f.readline(MAX_LINE + 1):
            read += len(raw)
            if read > MAX_FILE:
                break
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            stamped = _STAMP.match(line)
            if stamped is None:
                if kind is not None:
                    buf.append(line)
                    size += len(line)
                    kind = None if size > _MAX_BODY else kind
                continue
            if kind is not None:
                yield from _body(kind, stamp, buf)
            kind = None
            if _REQUEST in line:
                kind, stamp, buf = "request", stamped.group(1), [line.split(_REQUEST, 1)[1]]
            elif line.endswith(_OPEN) and data_stamp is not None:
                kind, stamp, buf = "response", data_stamp, ["{"]
            size = len(buf[0]) if buf else 0
            data_stamp = stamped.group(1) if line.endswith(_DATA) else None
    if kind is not None:
        yield from _body(kind, stamp, buf)


def _body(kind: str, stamp: str, buf: list[str]) -> Iterator[tuple[str, str, dict]]:
    try:
        body = json.loads("\n".join(buf))
    except (ValueError, RecursionError):
        return
    if isinstance(body, dict):
        yield kind, stamp, body


def _pairs(logs: list[Path], session_id: str | None) -> list[dict]:
    """This session's (request, response) pairs across the joined logs, in order; only the first request keeps its
    `instructions` (the fixed prefix), so memory does not grow with the request count."""
    pending: list[dict] = []
    out: list[dict] = []
    prefix_kept = False
    for log in logs:
        for kind, stamp, body in _wire(log):
            if kind == "request":
                sid = as_str(as_dict(body.get("headers")).get("X-Client-Session-Id"))
                ours = sid is None or sid == session_id
                reasoning = as_dict(body.get("reasoning"))
                pending.append({"ours": ours, "start": stamp, "model": as_str(body.get("model")),
                                "effort": as_str(reasoning.get("effort")), "summary": as_str(reasoning.get("summary")),
                                "tools": body.get("copilotToolsFingerprint"),
                                "instructions": as_str(body.get("instructions")) if ours and not prefix_kept else None})
                prefix_kept = prefix_kept or ours
            elif pending:
                request = pending.pop(0)
                if request["ours"]:
                    out.append(request | {"end": stamp, "id": as_str(body.get("id")), "api_model": as_str(body.get("model")),
                                          "usage": as_dict(body.get("usage"))})
    return out


def _session_value(data: dict, key: str):
    """A session.start field: present (even null) is the measured value; absent is `not recorded`."""
    if key not in data:
        return not_recorded(f"session.start carries no {key}")
    value = data[key]
    return value if value is None or isinstance(value, str) else not_recorded(f"session.start.{key} is not a string")


def _served(start: dict, logs: list[Path], pairs: list[dict]) -> tuple[ServedSettings, ...]:
    api_reason = _NO_LOG if not logs else "the session record names no API model" if pairs else \
        "no model response in the debug process log"
    session = ServedSettings(
        model_served=_session_value(start, "selectedModel"), model_api=not_recorded(api_reason),
        effort=_session_value(start, "reasoningEffort"),
        context_tokens=not_recorded("the -p session record states the context tier, not a token count"),
        context_tier=_session_value(start, "contextTier"),
        reasoning_summary=not_recorded("the session record does not show it"),
        sources={"model_served": f"{_SESSION}.selectedModel", "model_api": _SESSION, "effort": f"{_SESSION}.reasoningEffort",
                 "context_tokens": _SESSION, "context_tier": f"{_SESSION}.contextTier", "reasoning_summary": _SESSION})
    seen = dict.fromkeys((p["model"], p["api_model"], p["effort"], p["summary"]) for p in pairs)

    def shown(value: str | None, what: str):
        return value if value is not None else not_recorded(f"the debug log does not show {what}")
    logged = tuple(ServedSettings(
        model_served=shown(model, "request.model"), model_api=shown(api, "response.model"),
        effort=shown(effort, "request.reasoning.effort"),
        context_tokens=not_recorded("the debug log's request shows no context window"),
        context_tier=not_recorded("the debug log's request shows no context tier"),
        reasoning_summary=shown(summary, "request.reasoning.summary"),
        sources={"model_served": f"{_DEBUG}:request.model", "model_api": f"{_DEBUG}:response.model",
                 "effort": f"{_DEBUG}:request.reasoning.effort", "context_tokens": _DEBUG, "context_tier": _DEBUG,
                 "reasoning_summary": f"{_DEBUG}:request.reasoning.summary"}) for model, api, effort, summary in seen)
    return (session, *logged)


def _reasoning_tokens(pair: dict) -> int | None:
    value = as_dict(pair["usage"].get("completion_tokens_details")).get("reasoning_tokens")
    return value if is_count(value) else None


def _reasoning(messages: list[tuple[int, dict]], pairs: list[dict], line_by_call: dict[str, int]) -> list[ReasoningItem]:
    tokens = {line_by_call[p["id"]]: _reasoning_tokens(p) for p in pairs if p["id"] in line_by_call}
    items = []
    for n, data in messages:
        text = as_str(data.get("reasoningText")) or None
        opaque = as_str(data.get("encryptedContent")) or as_str(data.get("reasoningOpaque"))
        digest = hashlib.sha256(opaque.encode("utf-8")).hexdigest() if opaque else None
        count = tokens.get(n)
        if text is not None:
            items.append(ReasoningItem(n, 0, "summary", text, len(text), count, digest))
        elif digest is not None:
            items.append(ReasoningItem(n, 0, "encrypted-only", None, None, count, digest))
        elif count:
            items.append(ReasoningItem(n, 0, "omitted", None, None, count, None))
    return items


def _per_request(pairs: list[dict], line_by_call: dict[str, int]) -> list[ModelCall] | None:
    """One ModelCall per response, or None when any response lacks a bucket, a model or its record line."""
    calls = []
    for p in pairs:
        usage = p["usage"]
        details = as_dict(usage.get("prompt_tokens_details"))
        prompt, cached, write = usage.get("prompt_tokens"), details.get("cached_tokens"), details.get("cache_write_tokens")
        output, reasoning = usage.get("completion_tokens"), _reasoning_tokens(p)
        n = line_by_call.get(p["id"]) if p["id"] is not None else None
        if n is None or p["model"] is None or not all(is_count(v) for v in (prompt, cached, write, output, reasoning)) \
                or prompt < cached + write:
            return None
        calls.append(ModelCall(n, p["model"], prompt - cached - write, cached, write, output, reasoning, p["start"], p["end"]))
    return calls


def _sums(calls: list[ModelCall]) -> dict[str, tuple[int, ...]]:
    out: dict[str, tuple[int, ...]] = {}
    for c in calls:
        row = (c.requests, c.uncached_input, c.cache_read, c.cache_write, c.output, c.reasoning or 0)
        out[c.model] = tuple(a + b for a, b in zip(out.get(c.model, (0,) * 6), row, strict=True))
    return out


_CUSTOM = re.compile(r"<custom_instruction>.*?</custom_instruction>", re.DOTALL)
_IMPORTED = re.compile(r'<imported_custom_instruction source="([^"\n]*)">.*?</imported_custom_instruction>', re.DOTALL)
_SKILLS = re.compile(r"<available_skills>(.*?)</available_skills>", re.DOTALL)
_SKILL = re.compile(r"<skill>.*?</skill>", re.DOTALL)
_LOCATION = re.compile(r"<location>\s*(.*?)\s*</location>", re.DOTALL)
_APPLY = re.compile(r"(?m)^---\napplyTo:")
_TOP_TAG = re.compile(r"(?m)^<[a-z_]+>$")
_LISTED = "Here is a list of instruction files"
_LISTED_ROW = re.compile(r"(?m)^\|[^|\n]*\| '([^'\n]+)' \|")


def _path(text: str) -> str:
    return text.replace("\\\\", "/").replace("\\", "/")


def _prompt_parts(logs: list[Path], pairs: list[dict], tool_tokens: int | None) -> list[PromptPart] | str:
    if not logs:
        return not_recorded(_NO_LOG)[1]
    text = pairs[0]["instructions"] if pairs else None
    if text is None:
        return not_recorded("no request instructions in the debug process log")[1]
    source = f"{_DEBUG}:request.instructions"
    parts: list[tuple] = []  # (part, path, chars, delivery, source[, tokens]); each becomes a PromptPart numbered by position
    covered = 0
    custom = [(m.start(), m.end()) for m in _CUSTOM.finditer(text)]
    for start, end in custom:
        imported = list(_IMPORTED.finditer(text, start, end))
        inner = sum(m.end() - m.start() for m in imported)
        parts.append(("instruction_file", None, end - start - inner, "inlined", source))
        parts += [("instruction_file", _path(m.group(1)), m.end() - m.start(), "inlined", source) for m in imported]
        covered += end - start
    starts = [m.start() for m in _APPLY.finditer(text) if not any(s <= m.start() < e for s, e in custom)]
    for i, start in enumerate(starts):
        if i + 1 < len(starts):
            end = starts[i + 1]
        else:
            listed = text.find(_LISTED, start)
            tag = _TOP_TAG.search(text, start)
            end = listed if listed != -1 else tag.start() if tag else len(text)
        parts.append(("instruction_file", None, end - start, "inlined", source))
        covered += end - start
    listed = text.find(_LISTED)
    if listed != -1:  # each listed file counts its own table row, line end included (Leader ruling, J2-FIX DR c)
        for m in _LISTED_ROW.finditer(text, listed):
            end = text.find("\n", m.end())
            row = (len(text) if end == -1 else end + 1) - m.start()
            parts.append(("instruction_file", _path(m.group(1)), row, "listed", source))
            covered += row
    for block in _SKILLS.finditer(text):
        for entry in _SKILL.finditer(text, block.start(1), block.end(1)):
            location = _LOCATION.search(entry.group(0))
            parts.append(("skills", _path(location.group(1)) if location else None, entry.end() - entry.start(),
                          "listed", source))
            covered += entry.end() - entry.start()
    parts.insert(0, ("system", None, len(text) - covered, "inlined", source))
    if pairs[0]["tools"] is not None:
        # no character count (names and digests only); the fingerprint's digest is kept in `path` so two cells' tool
        # catalogues compare exactly (Leader ruling, J2-FIX tools-part DR); None when the record gives no digest.
        # `tokens` is the usage checkpoint's `tool_tokens` (A7, ADR-0026 amendment 2026-10-14); None when it states none
        digest = as_str(as_dict(pairs[0]["tools"]).get("digest"))
        parts.append(("tools", f"{FINGERPRINT}:{digest}" if digest else None, None, "listed",
                      f"{_DEBUG}:request.copilotToolsFingerprint (names and digests only)", tool_tokens))
    # native_ordinal is the part's position in the record's parts (J1A-FIX item 28), so no two share a key
    return [PromptPart(n, *part) for n, part in enumerate(parts)]


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from each `assistant.message.data.toolRequests[]`, in native order, plus this
    record's own first non-empty assistant text (design section 4.3, slice S2). `arguments` is
    either a JSON object (path/file_path/command by the same field names as Codex) or, observed in
    the committed `apply_patch` captures, a plain string holding the patch body -- its own
    `*** Add File: ` / `*** Update File: ` headers are the paths, and the call is a write regardless
    of headers (the name alone decides, per the design's write-tool list).

    R-85 condition 1 (PI-T6's count-equality assertion): unlike Claude Code and Codex, `ToolCall`
    and `ToolInput` here are not two projections of one walked row set -- Copilot's own record
    announces a tool call twice, as an `assistant.message` request (this reader's source) and as a
    paired `tool.execution_start`/`tool.execution_complete` (`read()`'s source), and the two streams
    are 1:1 by the harness's own construction (verified on the committed `off`/`on`/`fixed`
    fixtures: 6/6, 17/17, 11/11) -- not by a shared predicate, because there is none to share.

    `bytes_returned` is the UTF-8 size of the paired `tool.execution_complete`'s `result.content` (what the model
    receives; `detailedContent` is the display copy). A failed call has no `result`: it takes the record's own
    `toolTelemetry.metrics.resultForLlmLength` (characters, equal to the content length on 1,767 of 1,802 successful
    calls checked) and is None without it. The assistant text count (I2) is every non-blank `assistant.message`
    `content` (`reasoningText` is thinking and is not counted); a record that lost a line reports none."""
    ex = Extraction()
    first_text: str | None = None
    calls: list[ToolInput] = []
    call_ids: dict[str, int] = {}
    returned: dict[str, int] = {}
    chars = messages = 0
    for n, row in rows(path, ex):
        if row.get("type") == "tool.execution_complete":
            data = as_dict(row.get("data"))
            content = as_dict(data.get("result")).get("content")
            sent = as_dict(as_dict(data.get("toolTelemetry")).get("metrics")).get("resultForLlmLength")
            size = len(content.encode("utf-8")) if isinstance(content, str) else (sent if is_count(sent) else None)
            if isinstance(data.get("toolCallId"), str) and size is not None:
                returned.setdefault(data["toolCallId"], size)
            continue
        if row.get("type") != "assistant.message":
            continue
        data = as_dict(row.get("data"))
        text = as_str(data.get("content"))
        if text:
            first_text = first_text or text
            if text.strip():
                chars += len(text)
                messages += 1
        for req in as_list(data.get("toolRequests")):
            if not isinstance(req, dict):
                continue
            name = as_str(req.get("name")) or "unknown"
            arguments = req.get("arguments")
            if isinstance(arguments, dict):
                paths = tuple(p for p in (as_str(arguments.get("path")), as_str(arguments.get("file_path"))) if p)
                command = as_str(arguments.get("command"))
            elif isinstance(arguments, str):
                paths = patch_header_paths(arguments)
                command = None
            else:
                paths, command = (), None
            if isinstance(req.get("toolCallId"), str):
                call_ids.setdefault(req["toolCallId"], len(calls))
            calls.append(ToolInput(n, name, paths, command, name in WRITE_TOOLS))
    for call_id, i in call_ids.items():
        if call_id in returned:
            calls[i] = replace(calls[i], bytes_returned=returned[call_id])
    lost = ex.truncated or ex.malformed_lines
    return ProcessTrace(first_text, tuple(calls), None if lost else chars, None if lost else messages)


def us14_valid(tool_calls: list[dict]) -> bool:
    """US-14 for Copilot (R-27 c2, design section 13): a valid cell has **zero hook denials** (no
    `tool_calls` row with `outcome_code == "denied"`) **and** at least one successful tool call (the
    positive control, R-27 c1 -- a cell with zero tool calls does not pass by default). Takes ledger
    rows, as `normalize.tool_call_rows` emits or `views.rows(run_dir, "tool_calls")` reads, never an
    in-memory `Extraction` (design D&P C-d), so it reflects what a cell actually recorded."""
    return not any(r.get("outcome_code") == "denied" for r in tool_calls) and any(r.get("ok") == 1 for r in tool_calls)
