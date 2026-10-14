"""Codex native record: `sessions/YYYY/MM/DD/rollout-*-<session id>.jsonl` (spike 1.2, W3; golden fixture 2026-09-23).

- The model comes from the latest `turn_context`.
- Each API call is an `event_msg`/`token_count` with `info.last_token_usage`; a repeated event with an
  unchanged `total_token_usage` is not a new call. OpenAI-style `input_tokens` includes cached tokens,
  so uncached = input - cached (ADR-0006 disjoint buckets). Reasoning is a component of output.
- The record is complete for this harness (profile usage_source native_record); the adapter's prompt
  response reports only the last call.
- Tool calls are `response_item` `custom_tool_call` / `function_call` / `local_shell_call`, closed by
  their `*_output` row with the same `call_id`; a `web_search_call` is a standalone out-of-profile row.
- Code-mode MCP calls also appear as `event_msg` `item_completed` / `McpToolCall` items. Their
  server and tool fields form one server-qualified, out-of-profile tool row.
- An error is `event_msg`/`task_complete` with `error.message`, which embeds a JSON body with `status`
  and `error.type` (probe W3). When that body has no status field, `unexpected status NNN` in the text
  is the status. The message stored on the row is the CLI text, unchanged.
- The first user message that is not tagged system context (`<environment_context>` and the like) is
  the prompt (US-10). A pack-on cell's first user message also carries a harness-injected AGENTS.md
  block shaped `# AGENTS.md instructions for <cwd>\n\n<INSTRUCTIONS>\n...\n</INSTRUCTIONS>`; that block
  is context too, and is skipped the same way (real E2E, US-10, T8 defect 1).

The lean re-run's reader facts (ADR-0024 s4, ADR-0026 s1; R-READ-CODEX):
- `served`: `model_served`, `effort` and `reasoning_summary` from each `turn_context` (`model`, `effort`, `summary`);
  `context_tokens` is the nominal window (Leader ruling 2026-10-12): `task_started.model_context_window` (the
  effective one) / (the cell's own catalog percent / 100), from the catalog its config.toml names
  (`model_catalog_json`), else `<home>/models_cache.json`, the served model's
  `effective_context_window_percent`, where home is the parent of the record's `sessions` folder; an exact integer,
  else not recorded. Its source keeps the effective value and the percent. A value that changes between turns is a
  second `ServedSettings` (DR2), so both are written. The rollout carries no API model and Codex has no context tier: both not recorded.
- `reasoning`: one item per `response_item` `reasoning`. Kind `text` when it carries `content` text, else `summary`
  (its `summary_text` parts joined by a blank line), else `encrypted-only`, else `omitted`. `opaque_sha256` is the
  sha256 of `encrypted_content`; nothing is reconstructed. `native_ordinal` is the request: the line of the first new
  `token_count` after the item (the `ModelCall`'s own ordinal); an item no reported call follows keeps its own line.
  `reasoning_tokens` is None: the record counts reasoning per request, which `ModelCall.reasoning` already holds.
- `prompt_parts`: `session_meta.base_instructions` (`system`), then every developer content part and every injected
  user context part before the first prompt text: the AGENTS.md block is `instruction_file` (`AGENTS.md`, inlined),
  `<skills_instructions>` is `skills` (listed), the rest `system`. Tools are not in the record.
- `harness_events`: not recorded (hooks and compaction are Flagged in ADR-0026 s1).
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import tomllib
from dataclasses import replace
from pathlib import Path

from harness_bench.telemetry import (
    MAX_FILE,
    Extraction,
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
    as_status,
    as_str,
    is_count,
    not_recorded,
    patch_header_paths,
    rows,
    unexpected_status,
)

CALL_TYPES = ("custom_tool_call", "function_call", "local_shell_call")
OUTPUT_TYPES = ("custom_tool_call_output", "function_call_output", "local_shell_call_output")
SHELL_NAMES = ("exec", "shell", "exec_command", "local_shell", "container.exec")
EDIT_NAMES = ("apply_patch", "write_file", "edit")
# R-74 item 5: the collaboration ids the pinned 0.156.0 system message names (ok.jsonl:4). qual-r74-codex-1 issued
# spawn_agent and wait_agent. 0.160.0 offers exactly these six as `collaboration.*` tools when the catalog entry names
# multi_agent_version v2 (request captured, fix/codex-profile-0160). Static here, as the Claude and Copilot readers; in
# profile only in a scenario-6 cell (views).
DELEGATE_NAMES = ("spawn_agent", "send_message", "followup_task", "wait_agent", "interrupt_agent", "list_agents")
MCP_CLASSES = {"scripted_user.ask_user": "scripted user"}  # R-37 c2: the task's own MCP tool; every other MCP call is other

# Quoted `key: value` pairs inside a call's own input text (design section 4.3). Verified 2026-09-24
# capture: a `custom_tool_call`'s `input` is not JSON -- it is a JS-source snippet, e.g.
# `tools.exec_command({cmd:'...', workdir:'...'})` or `tools.apply_patch("*** Begin Patch\n...")` -- so
# this reads key/value pairs by regex rather than by parsing JSON, tolerant of either quote character.
_KV = re.compile(r"""(?P<key>cmd|command|path|file_path)\s*:\s*(?P<q>['"])(?P<val>(?:\\.|(?!(?P=q)).)*)(?P=q)""")


def _is_injected_context(text: str) -> bool:
    """A harness-injected context part, not something the user (or the prompt) wrote: a `<tagged>`
    block, or the AGENTS.md instructions block Codex prepends for a pack-on cell (US-10)."""
    stripped = text.lstrip()
    return stripped.startswith(("<", "# AGENTS.md instructions for "))


def _open_call(kind: str, ptype, call_id: str | None) -> bool:
    """A `response_item` row that opens a tracked tool call: `function_call`, `custom_tool_call` or
    `local_shell_call` (R-85 conditions 1-2). The one predicate `read()`'s `ToolCall`s and
    `tool_inputs()`'s `ToolInput`s both key off for this call family -- out-of-band calls
    (`web_search_call`, an MCP `item_completed`) are each their own row kind and are not part of
    this walk (design section 4.3 names only the three `CALL_TYPES`; PI-T6 compares counts on a
    fixture with no out-of-band call)."""
    return kind == "response_item" and ptype in CALL_TYPES and call_id is not None


def _tool_class(name: str) -> str:
    if name in SHELL_NAMES:
        return "shell"
    if name in EDIT_NAMES:
        return "edit"
    if name in DELEGATE_NAMES:
        return "delegate"
    return "other"


def _parse_error(message: str) -> tuple[int | None, str]:
    """Status from a JSON body. With no status field, `unexpected status NNN` in the text is the status."""
    status, etype = None, "unknown"
    try:
        body = json.loads(message)
    except (ValueError, RecursionError):
        body = None
    if isinstance(body, dict):
        etype = as_str(as_dict(body.get("error")).get("type")) or as_str(body.get("type")) or "unknown"
        status = as_status(body.get("status"))
    if status is None:
        status = unexpected_status(message)
    return status, etype


_TURN_FIELDS = (("model", "model_served"), ("effort", "effort"), ("summary", "reasoning_summary"))
_CONTEXT_SOURCE = "rollout:task_started.model_context_window"


def _catalog_file(home: Path) -> Path:
    """The catalog the cell's Codex read: the file its config.toml names (`model_catalog_json`, resolved beside it;
    Codex then fetches none, fix/codex-profile-0160), else the fetched `<home>/models_cache.json`."""
    config = home / "config.toml"
    try:
        named = tomllib.loads(config.read_text(encoding="utf-8")).get("model_catalog_json") \
            if config.is_file() and config.stat().st_size <= MAX_FILE else None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        named = None
    return home / named if isinstance(named, str) and named else home / "models_cache.json"


def _catalog_percent(path: Path, model: str | None) -> tuple[int | None, str]:
    """(the served model's `effective_context_window_percent`, its source note), or (None, the reason) (ADR-0024 s4):
    the catalog in `<home>` (`_catalog_file`), where home is the parent of the record's nearest `sessions` folder."""
    home = next((p.parent for p in path.parents if p.name == "sessions"), path.parent)
    catalog = _catalog_file(home)
    name = catalog.name
    if not catalog.is_file():
        return None, f"no {name} beside the record"
    if model is None:
        return None, "no served model to look up"
    try:
        if catalog.stat().st_size > MAX_FILE:
            return None, f"{name} over the size bound"
        body = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None, f"{name} does not parse"
    entry = next((m for m in as_list(as_dict(body).get("models")) if isinstance(m, dict) and m.get("slug") == model), None)
    if entry is None:
        return None, f"{name} has no {model}"
    percent, ceiling = entry.get("effective_context_window_percent"), entry.get("max_context_window")
    if not is_count(percent) or percent == 0:
        return None, f"{name} {model} has no effective_context_window_percent"
    tail = f" (max_context_window={ceiling})" if is_count(ceiling) else ""
    return percent, f"{name} models[{model}].effective_context_window_percent={percent} / 100){tail}"


def _nominal(window: int, percent: int | None, note: str) -> tuple[int | tuple, str]:
    """(the nominal window, its source) from one effective `model_context_window` (Leader ruling 2026-10-12): the
    effective value / (the catalog percent / 100), an exact integer, else not recorded. The source keeps both inputs,
    so two different windows are two sources (views.KEYS `served`)."""
    effective = f"{_CONTEXT_SOURCE}={window}"
    if percent is None:
        return not_recorded(f"nominal window needs the catalog percent: {note}"), effective
    if window * 100 % percent:
        return not_recorded(f"{window} / ({percent} / 100) is not an integer"), effective
    return window * 100 // percent, f"nominal = {effective} / ({note}"


def _served(path: Path, seen: dict[str, list]) -> ServedSettings | tuple[ServedSettings, ...]:
    """One `ServedSettings` from each field's first reading, plus one more per later different reading (DR2)."""
    reasons = {"model_served": "no turn_context.model", "effort": "no turn_context.effort",
               "reasoning_summary": "no turn_context.summary", "context_tokens": "no task_started.model_context_window"}
    model = seen["model_served"][0] if seen["model_served"] else None
    percent, note = _catalog_percent(path, model)
    windows = [_nominal(w, percent, note) for w in seen["context_tokens"]]
    seen = {**seen, "context_tokens": [value for value, _ in windows]}
    first = {f: (vals[0] if vals else not_recorded(reasons[f])) for f, vals in seen.items()}
    sources = {f: f"rollout:turn_context.{k}" for k, f in _TURN_FIELDS if seen[f]}
    if windows:
        sources["context_tokens"] = windows[0][1]
    base = ServedSettings(model_api=not_recorded("the rollout carries no API model"),
                          context_tier=not_recorded("codex has no context tier"), sources=sources, **first)
    extra = [replace(base, **{f: v}) for f, vals in seen.items() if f != "context_tokens" for v in vals[1:]]
    extra += [replace(base, context_tokens=v, sources={**sources, "context_tokens": s}) for v, s in windows[1:]]
    return (base, *extra) if extra else base


def _reasoning_item(n: int, payload: dict) -> ReasoningItem:
    def texts(key: str) -> list[str]:
        return [p["text"] for p in as_list(payload.get(key)) if isinstance(p, dict) and isinstance(p.get("text"), str)]
    opaque = as_str(payload.get("encrypted_content"))
    sha = hashlib.sha256(opaque.encode("utf-8")).hexdigest() if opaque else None
    content, summary = texts("content"), texts("summary")
    kind, text = (("text", "".join(content)) if content else ("summary", "\n\n".join(summary)) if summary
                  else ("encrypted-only", None) if opaque else ("omitted", None))
    return ReasoningItem(n, 0, kind, text, None if text is None else len(text), None, sha)


def _prompt_part(n: int, text: str, role: str) -> PromptPart:
    source = f"rollout:response_item.message[{role}]"
    stripped = text.lstrip()
    if stripped.startswith("# AGENTS.md instructions for "):
        return PromptPart(n, "instruction_file", "AGENTS.md", len(text), "inlined", source)
    if stripped.startswith("<skills_instructions>"):
        return PromptPart(n, "skills", None, len(text), "listed", source)
    return PromptPart(n, "system", None, len(text), "inlined", source)


def read(path: Path) -> Extraction:
    ex = Extraction()
    model = None
    last_total = None
    open_tools: dict[str, dict] = {}
    seen: dict[str, list] = {"model_served": [], "effort": [], "reasoning_summary": [], "context_tokens": []}
    reasoning: list[ReasoningItem] = []
    pending: list[ReasoningItem] = []  # reasoning items whose request has not been reported yet
    parts: list[PromptPart] = []
    prefix_open = True  # the fixed prefix ends at the first prompt text
    for n, row in rows(path, ex):
        kind = row.get("type")
        payload = as_dict(row.get("payload"))
        item = as_dict(payload.get("item"))
        ptype = payload.get("type")
        stamp = as_str(row.get("timestamp"))
        call_id = as_str(payload.get("call_id"))
        if kind == "session_meta" and ex.session_id is None:
            ex.session_id = as_str(payload.get("id")) or as_str(payload.get("session_id"))
            base = payload.get("base_instructions")
            base = as_str(as_dict(base).get("text")) if isinstance(base, dict) else as_str(base)
            if base is not None and prefix_open:
                parts.append(PromptPart(len(parts), "system", None, len(base), "inlined", "rollout:session_meta.base_instructions"))
        elif kind == "turn_context":
            for key, name in _TURN_FIELDS:
                value = as_str(payload.get(key))
                if value is not None and value not in seen[name]:
                    seen[name].append(value)
            if isinstance(payload.get("model"), str):
                model = payload["model"]
        elif kind == "event_msg" and ptype == "task_started":
            window = payload.get("model_context_window")
            if is_count(window) and window not in seen["context_tokens"]:
                seen["context_tokens"].append(window)
        elif kind == "response_item" and ptype == "reasoning":
            pending.append(_reasoning_item(n, payload))
        elif kind == "event_msg" and ptype == "token_count":
            info = as_dict(payload.get("info"))
            total, last = info.get("total_token_usage"), as_dict(info.get("last_token_usage"))
            if not last or total == last_total:
                continue
            last_total = total
            if model is None:
                ex.missing.append(MissingField(n, "model"))
            cached = ex.count(n, last, "cached_input_tokens")
            ex.model_calls.append(ModelCall(n, model or "NOT_RECORDED", max(ex.count(n, last, "input_tokens") - cached, 0), cached,
                                            ex.count(n, last, "cache_write_input_tokens"), ex.count(n, last, "output_tokens"),
                                            ex.count(n, last, "reasoning_output_tokens"), stamp, stamp))
            reasoning.extend(replace(r, native_ordinal=n, item_ordinal=i) for i, r in enumerate(pending))
            pending.clear()
        elif kind == "event_msg" and ptype == "task_complete":
            err = as_dict(payload.get("error"))
            if err:
                message = as_str(err.get("message")) or ""
                status, etype = _parse_error(message)
                ex.errors.append(ProviderError(n, status, etype, message[:300]))
        elif kind == "response_item" and ptype == "message" and payload.get("role") in ("developer", "user"):
            role = payload["role"]
            texts = [c.get("text") for c in as_list(payload.get("content")) if isinstance(c, dict) and isinstance(c.get("text"), str)]
            prompt = role == "user" and bool(texts) and not all(_is_injected_context(t) for t in texts)
            if prefix_open:
                for t in texts:
                    if role == "developer" or _is_injected_context(t):
                        parts.append(_prompt_part(len(parts), t, role))
                prefix_open = not prompt
            if prompt and ex.first_user_text is None:
                ex.first_user_text = "".join(t for t in texts if not _is_injected_context(t))
        elif kind == "response_item" and ptype == "web_search_call":
            ex.tool_calls.append(ToolCall(n, "web_search", "other", stamp,
                                          stamp if payload.get("status") == "completed" else None, None))
        elif kind == "event_msg" and ptype == "item_completed" and item.get("type") == "McpToolCall":
            server, tool = as_str(item.get("server")), as_str(item.get("tool"))
            if server and tool:
                ok = {"completed": True, "failed": False}.get(as_str(item.get("status")))
                name = f"{server}.{tool}"
                ex.tool_calls.append(ToolCall(n, name, MCP_CLASSES.get(name, "other"), None, stamp, ok))
        elif _open_call(kind, ptype, call_id):
            open_tools[call_id] = {"n": n, "name": as_str(payload.get("name")) or ptype, "start": stamp}
        elif kind == "response_item" and ptype in OUTPUT_TYPES and call_id in open_tools:
            tool = open_tools.pop(call_id)
            ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], stamp, None))
    for tool in open_tools.values():
        ex.tool_calls.append(ToolCall(tool["n"], tool["name"], _tool_class(tool["name"]), tool["start"], None, None))
    ex.tool_calls.sort(key=lambda t: t.native_ordinal)
    reasoning.extend(pending)  # no reported call followed: each keeps its own line
    ex.served = _served(path, seen)
    ex.reasoning = reasoning
    ex.prompt_parts = parts if parts else not_recorded("no prefix items in the rollout")[1]
    ex.harness_events = not_recorded("codex hooks and compaction are not verified in the rollout (ADR-0026 s1, Flagged)")[1]
    return ex


def _kv_fields(text: str) -> tuple[tuple[str, ...], str | None]:
    """`path`/`file_path`/`cmd`/`command` values from a call's own input text, plus any
    `apply_patch` header paths (design section 4.3). The first `cmd`/`command` match wins;
    every `path`/`file_path` match is kept."""
    paths: list[str] = []
    command: str | None = None
    for m in _KV.finditer(text):
        quote = m.group("q")
        value = m.group("val").replace(f"\\{quote}", quote)
        if m.group("key") in ("path", "file_path"):
            paths.append(value)
        elif command is None:
            command = value
    paths.extend(patch_header_paths(text))
    return tuple(paths), command


# --- The shell-read classifier (R-READ-CODEX; Leader ruling on R-DRIFT's DR2) ---------------------------------------
# Codex reads files through its shell, so a read's targets live only in the command text. The rule, stated:
# - the command is split into statements on `;` `&&` `||` `&`, and each statement into pipeline stages on `|`; quotes
#   are honoured and a backslash is literal (Windows paths);
# - a statement is a read or a list only when its first stage is one of the commands below and every later stage is
#   a stdin filter (`_FILTERS`); `2>` to a null sink and `2>&1` are dropped; any other redirect, a `(`/`)`, a
#   `$`-variable, a backtick, an unknown PowerShell parameter or unbalanced quotes make the statement unparsed;
# - read: cat, type, less, more, gc, Get-Content, head, tail, sed -n (never -i), grep/egrep/fgrep/rg (the path
#   arguments, never the pattern), Select-String/sls, and `python -c` whose every `open(...)` is a literal path in a
#   read mode; list: ls, dir, gci, Get-ChildItem, and `rg --files`; `bash|sh|zsh -c`, `pwsh|powershell -Command` and
#   `cmd /c` are unwrapped once;
# - the call's paths are the targets of every read or list statement, verbatim; an unparsed statement names none
#   (never a guess). `shell_read_kind` is "read" when every statement is a read or a list and one is a read, "list"
#   when every statement is a list, else None.
_SEPARATORS = {";", "&&", "||", "&"}
_FILTERS = {"head", "tail", "grep", "egrep", "fgrep", "rg", "sort", "uniq", "wc", "cut", "tr", "nl", "jq", "more", "less",
            "findstr", "select-object", "select", "select-string", "sls", "measure-object", "measure", "sort-object",
            "format-table", "ft", "format-list", "fl", "out-string", "out-host"}
_NULL_SINKS = {"/dev/null", "$null", "nul"}
_CONTENT = {"cat", "type", "less", "more", "gc", "get-content"}
_HEAD_TAIL = {"head", "tail"}
_GREP = {"grep", "egrep", "fgrep", "rg"}
_LIST = {"ls", "dir", "gci", "get-childitem"}
_PS_STRICT = {"gc", "get-content", "gci", "get-childitem", "select-string", "sls"}  # cmdlets: an unknown parameter is unparsed
# PowerShell parameters (lower case): the ones whose value is a path, other value-taking ones, and switches.
_PS_PATH = {"-path", "-literalpath", "-lp", "-pspath"}
_PS_VALUE = {"content": {"-totalcount", "-head", "-first", "-tail", "-last", "-readcount", "-encoding", "-delimiter",
                         "-stream", "-filter", "-include", "-exclude"},
             "list": {"-filter", "-include", "-exclude", "-depth", "-attributes"},
             "sls": {"-pattern", "-encoding", "-context", "-include", "-exclude"}}
_PS_SWITCH = {"content": {"-raw", "-wait", "-force", "-asbytestream"},
              "list": {"-recurse", "-force", "-file", "-directory", "-name", "-hidden", "-readonly", "-system",
                       "-followsymlink"},
              "sls": {"-simplematch", "-casesensitive", "-quiet", "-list", "-notmatch", "-allmatches", "-raw"}}
_PUNCTUATION = set("();<>|&")
_HEAD_TAIL_VALUE = {"-n", "-c", "--lines", "--bytes"}
_GREP_COMMON = {"-e", "-f", "-m", "-A", "-B", "-C", "--regexp", "--file", "--max-count", "--context", "--after-context",
                "--before-context", "--color"}
_GREP_VALUE = {"grep": _GREP_COMMON | {"-d", "-D", "--include", "--exclude", "--exclude-dir", "--label", "--binary-files"},
               "rg": _GREP_COMMON | {"-g", "-t", "-T", "-M", "-j", "-r", "-E", "-d", "--glob", "--iglob", "--type",
                                     "--type-not", "--type-add", "--max-columns", "--threads", "--replace", "--encoding",
                                     "--max-depth", "--sort", "--sortr", "--colors", "--pre", "--pre-glob",
                                     "--max-filesize"}}
_SED_VALUE = {"-e", "-f", "-l", "--expression", "--file"}
_OPEN = re.compile(r"""\bopen\(\s*(['"])([^'"]+)\1\s*(?:,\s*(['"])([^'"]*)\3\s*)?\)""")


class _Unparsed(Exception):
    """A statement the rule cannot read: it names no path."""


def _lex(command: str) -> list[str]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""  # a backslash is a Windows path separator, never an escape
    try:
        return list(lexer)
    except ValueError as exc:  # unbalanced quotes
        raise _Unparsed from exc


def _split(tokens: list[str], marks: set[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for t in tokens:
        if t in marks:
            out.append([])
        else:
            out[-1].append(t)
    return [part for part in out if part]


def _drop_null_redirects(stage: list[str]) -> list[str]:
    """The stage without `2>&1` and `2>` a null sink; any other redirect or grouping (a token made only of shell
    punctuation), a variable or a backtick is unparsed."""
    out, i = [], 0
    while i < len(stage):
        t = stage[i]
        sink = stage[i + 2].lower() if i + 2 < len(stage) else None
        if t == "2" and (stage[i + 1:i + 3] == [">&", "1"] or (stage[i + 1:i + 2] == [">"] and sink in _NULL_SINKS)):
            i += 3
        elif (t and set(t) <= _PUNCTUATION) or "`" in t or t.startswith(("$", "@(")):
            raise _Unparsed
        else:
            out.append(t)
            i += 1
    return out


def _ps_args(args: list[str], family: str, strict: bool) -> list[str]:
    """Path arguments of a PowerShell-style command: `-Path`/`-LiteralPath` values and positionals."""
    paths, i = [], 0
    while i < len(args):
        a, low = args[i], args[i].lower()
        if low == "--":
            paths.extend(args[i + 1:])
            break
        if low.startswith("-") and len(low) > 1:
            if low in _PS_PATH and i + 1 < len(args):
                paths.append(args[i + 1])
                i += 2
                continue
            if low in _PS_VALUE[family]:
                i += 2
                continue
            if low in _PS_SWITCH[family] or not strict:
                i += 1
                continue
            raise _Unparsed
        paths.append(a)
        i += 1
    return paths


def _option_args(args: list[str], value_opts: set[str]) -> tuple[list[str], set[str]]:
    """POSIX-style: (positionals, options seen). A value option consumes the next token; `--opt=v` and `-A3` do not."""
    positionals, seen, i = [], set(), 0
    while i < len(args):
        a = args[i]
        if a == "--":
            positionals.extend(args[i + 1:])
            break
        if a.startswith("-") and len(a) > 1:
            name = a.split("=", 1)[0]
            seen.add(name)
            if a.startswith("--"):
                i += 2 if name in value_opts and "=" not in a else 1
                continue
            letters = a[1:]
            seen.update(f"-{c}" for c in letters if c.isalpha())
            consumes = letters.isalpha() and f"-{letters[-1]}" in value_opts
            i += 2 if consumes else 1
            continue
        positionals.append(a)
        i += 1
    return positionals, seen


def _value_of(args: list[str], flags: tuple[str, ...]) -> bool:
    return any(a in flags or a.startswith(tuple(f"{f}=" for f in flags if f.startswith("--"))) for a in args)


def _stage(stage: list[str]) -> tuple[str, tuple[str, ...]] | None:
    """(kind, paths) of one statement's first stage, or None when it is not a read or a list."""
    name, args = Path(stage[0].replace("\\", "/")).name.lower().removesuffix(".exe"), stage[1:]
    if name in ("bash", "sh", "zsh") and len(args) == 2 and args[0] in ("-c", "-lc"):
        return _statement_kind(args[1])
    if name in ("pwsh", "powershell"):
        rest = [a for a in args if a.lower() not in ("-noprofile", "-nologo", "-noninteractive")]
        if rest and rest[0].lower() in ("-command", "-c"):
            return _statement_kind(" ".join(rest[1:]))
        return None
    if name == "cmd" and args and args[0].lower() == "/c":
        return _statement_kind(" ".join(args[1:]))
    if name in _CONTENT:
        return "read", tuple(_ps_args(args, "content", name in _PS_STRICT))
    if name in _HEAD_TAIL:
        positionals, _ = _option_args(args, _HEAD_TAIL_VALUE)
        return "read", tuple(positionals)
    if name == "sed":
        positionals, seen = _option_args(args, _SED_VALUE)
        if "-n" not in seen or any(s.startswith(("-i", "--in-place")) for s in seen):
            return None
        return "read", tuple(positionals if _value_of(args, ("-e", "--expression", "-f", "--file")) else positionals[1:])
    if name in _GREP:
        positionals, seen = _option_args(args, _GREP_VALUE["rg" if name == "rg" else "grep"])
        if name == "rg" and "--files" in seen:
            return "list", tuple(positionals)
        named = _value_of(args, ("-e", "--regexp", "-f", "--file"))
        return "read", tuple(positionals if named else positionals[1:])
    if name in ("select-string", "sls"):
        positionals = _ps_args(args, "sls", True)
        named = any(a.lower() == "-pattern" for a in args)
        explicit = [args[i + 1] for i, a in enumerate(args[:-1]) if a.lower() in _PS_PATH]
        rest = [p for p in positionals if p not in explicit]
        return "read", tuple(explicit + (rest if named else rest[1:]))
    if name in _LIST:
        return "list", tuple(_ps_args(args, "list", name in _PS_STRICT))
    if name in ("python", "python3", "py") and "-c" in args:
        code = args[args.index("-c") + 1] if args.index("-c") + 1 < len(args) else ""
        opens = list(_OPEN.finditer(code))
        if not opens or code.count("open(") != len(opens) or any(set(m.group(4) or "r") - set("rbt") for m in opens):
            return None
        return "read", tuple(m.group(2) for m in opens)
    return None


def _statement_kind(command: str) -> tuple[str, tuple[str, ...]] | None:
    """Unwrapped shell text: (kind, paths) when every statement is a read or a list, else None."""
    results = _statements(command)
    if not results or any(r is None for r in results):
        return None
    kinds = {r[0] for r in results}
    return ("read" if "read" in kinds else "list"), tuple(p for r in results for p in r[1])


def _statements(command: str) -> list[tuple[str, tuple[str, ...]] | None]:
    """One (kind, paths) or None per statement of `command`."""
    try:
        tokens = _lex(command)
    except _Unparsed:
        return [None]
    out: list[tuple[str, tuple[str, ...]] | None] = []
    for statement in _split(tokens, _SEPARATORS):
        try:
            stages = [_drop_null_redirects(s) for s in _split(statement, {"|"})]
        except _Unparsed:
            out.append(None)
            continue
        later = [Path(s[0].replace("\\", "/")).name.lower().removesuffix(".exe") for s in stages[1:] if s]
        try:
            out.append(_stage(stages[0]) if stages and stages[0] and all(n in _FILTERS for n in later) else None)
        except _Unparsed:
            out.append(None)
    return out


def shell_read_paths(command: str | None) -> tuple[str, ...]:
    """The read and list targets a shell command names, verbatim; an unparsed statement names none."""
    if not command:
        return ()
    return tuple(p for r in _statements(command) if r is not None for p in r[1])


def shell_read_kind(command: str | None) -> str | None:
    """The read classifier for a Codex shell call: "read", "list" or None (see the rule above)."""
    found = _statement_kind(command) if command else None
    return found[0] if found else None


def _output_bytes(payload: dict) -> int | None:
    """The UTF-8 size of a call's output row: a string, or the text parts of a list (ADR-0026 s4)."""
    output = payload.get("output")
    if isinstance(output, str):
        return len(output.encode("utf-8"))
    if isinstance(output, list):
        return sum(len(p["text"].encode("utf-8")) for p in output if isinstance(p, dict) and isinstance(p.get("text"), str))
    return None


def tool_inputs(path: Path) -> ProcessTrace:
    """`ToolInput`s from `function_call`/`custom_tool_call`/`local_shell_call` payloads (`_open_call`,
    the walker `read()`'s `ToolCall`s also key off -- R-85 condition 1), in native order, plus this
    record's own first assistant text block (design section 4.3, slice S2). A shell call's paths also hold its
    shell-read targets (`shell_read_paths`); `bytes_returned` is its output row's size (None with no output row).
    The assistant text count (I2) is every non-blank `output_text` of an assistant `message` item (commentary and the
    final answer alike): reasoning items and tool input are not counted, and a record that lost a line reports none."""
    ex = Extraction()
    first_text: str | None = None
    chars = messages = 0
    calls: list[ToolInput] = []
    call_ids: dict[str, int] = {}
    returned: dict[str, int | None] = {}
    for n, row in rows(path, ex):
        kind = row.get("type")
        if kind != "response_item":
            continue
        payload = as_dict(row.get("payload"))
        ptype = payload.get("type")
        call_id = as_str(payload.get("call_id"))
        if ptype in OUTPUT_TYPES and call_id is not None:
            returned.setdefault(call_id, _output_bytes(payload))
            continue
        if ptype == "message" and payload.get("role") == "assistant":
            texts = [c.get("text") for c in as_list(payload.get("content")) if isinstance(c, dict) and isinstance(c.get("text"), str)]
            if first_text is None and texts:
                first_text = "".join(texts)
            visible = [t for t in texts if t.strip()]
            chars += sum(len(t) for t in visible)
            messages += bool(visible)
            continue
        if not _open_call(kind, ptype, call_id):
            continue
        name = as_str(payload.get("name")) or ptype
        arguments = payload.get("arguments")
        text = arguments if isinstance(arguments, str) else payload.get("input")
        text = text if isinstance(text, str) else ""
        paths, command = _kv_fields(text)
        call_ids[call_id] = len(calls)
        calls.append(ToolInput(n, name, paths + shell_read_paths(command), command, bool(patch_header_paths(text))))
    for call_id, i in call_ids.items():
        if call_id in returned:
            calls[i] = replace(calls[i], bytes_returned=returned[call_id])
    lost = ex.truncated or ex.malformed_lines
    return ProcessTrace(first_text, tuple(calls), None if lost else chars, None if lost else messages)
