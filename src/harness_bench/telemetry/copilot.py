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
  null too when there is no `error` object.
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
"""

from __future__ import annotations

from pathlib import Path

from harness_bench.telemetry import (
    Extraction,
    MissingField,
    ModelCall,
    ProviderError,
    ToolCall,
    as_dict,
    as_list,
    as_str,
    is_count,
    rows,
)

__all__ = ["ProviderError", "read"]

SUPPORTED_EVENT_VERSIONS = {1}

TOOL_CLASS = {"powershell": "shell", "list_powershell": "shell", "read_powershell": "shell", "stop_powershell": "shell",
              "bash": "shell", "shell": "shell", "apply_patch": "edit", "write": "edit",
              "edit": "edit", "create": "edit", "view": "read", "glob": "read", "rg": "read", "grep": "read",
              "skill": "read",
              "scripted_user-ask_user": "scripted user"}  # R-37 c2: the task's own MCP tool (a1-capture-1)


def _tool_class(name: str) -> str:
    return TOOL_CLASS.get(name, "other")


def read(path: Path) -> Extraction:
    ex = Extraction()
    version_seen = False
    version_ok = False
    last_shutdown: tuple[int, str | None, dict] | None = None  # (native_ordinal, row timestamp, data)
    open_tools: dict[str, dict] = {}
    hook_starts = 0
    hook_failures = 0
    saw_main_user = False

    for n, row in rows(path, ex):
        kind = row.get("type")
        data = as_dict(row.get("data"))
        stamp = as_str(row.get("timestamp"))

        if kind == "session.start":
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
        elif kind == "tool.execution_complete":
            tool_call_id = as_str(data.get("toolCallId"))
            if tool_call_id in open_tools:
                tool = open_tools.pop(tool_call_id)
                success = data.get("success")
                ok = success if isinstance(success, bool) else None
                error = as_dict(data.get("error"))
                outcome_code = None if ok is True else as_str(error.get("code"))
                ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], stamp, ok,
                                              outcome_code))
        elif kind == "hook.start":
            hook_starts += 1
        elif kind == "hook.end":
            if data.get("success") is not True:
                hook_failures += 1
        elif kind == "session.error":
            ex.errors.append(ProviderError(n, None, as_str(data.get("errorType")) or "unknown",
                                           (as_str(data.get("message")) or "")[:300]))
        elif kind == "session.usage_checkpoint":
            advertised = []
            for state in as_list(data.get("promptCacheBreakState")):
                for model in as_dict(as_dict(state).get("models")).values():
                    for tool in as_list(as_dict(model).get("tools")):
                        name = as_str(as_dict(tool).get("name"))
                        if name is not None:
                            advertised.append(name)
            ex.tools_advertised = list(dict.fromkeys(advertised)) or None
        elif kind == "session.shutdown":
            last_shutdown = (n, stamp, data)

    for tool in open_tools.values():  # a start with no matching complete (killed turn)
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)

    if ex.session_id is None:  # no session.start, or no sessionId on it: the record's own directory name
        ex.session_id = path.parent.name

    if not (version_seen and version_ok):
        ex.missing.append(MissingField(0, "events.version"))
        return ex

    ex.hook_starts = hook_starts  # counted whether or not any hooks fired (US-9 live signal, design 4.5)
    ex.hook_failures = hook_failures

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

    return ex


def us14_valid(tool_calls: list[dict]) -> bool:
    """US-14 for Copilot (R-27 c2, design section 13): a valid cell has **zero hook denials** (no
    `tool_calls` row with `outcome_code == "denied"`) **and** at least one successful tool call (the
    positive control, R-27 c1 -- a cell with zero tool calls does not pass by default). Takes ledger
    rows, as `normalize.tool_call_rows` emits or `views.rows(run_dir, "tool_calls")` reads, never an
    in-memory `Extraction` (design D&P C-d), so it reflects what a cell actually recorded."""
    return not any(r.get("outcome_code") == "denied" for r in tool_calls) and any(r.get("ok") == 1 for r in tool_calls)
