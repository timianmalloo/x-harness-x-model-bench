"""Telemetry from native records and the adapter's turn usage (ADR-0008 as amended; probe W3; golden
fixtures captured 2026-09-23 with the pinned builds)."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench.errors import Cause
from harness_bench.telemetry import (
    Extraction,
    claude_code,
    codex,
    copilot,
    normalize,
    patch_header_paths,
)

FIX = Path(__file__).parent / "fixtures"
PROMPT = 'Run this shell command: python -c "print(6*7)" and write its exact output to answer.txt in the current directory. Then reply DONE.'


# Claude Code ------------------------------------------------------------------------------------

def test_claude_rows_of_one_api_message_are_one_model_call():
    ex = claude_code.read(FIX / "native/claude-code/ok.jsonl")
    assert len(ex.model_calls) == 1  # thinking + tool_use rows share message.id and repeat the usage
    call = ex.model_calls[0]
    assert call.model == "claude-sonnet-5"
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output) == (2, 23729, 9302, 116)


def test_claude_tool_calls_are_classified_and_closed_by_their_result():
    ex = claude_code.read(FIX / "native/claude-code/ok.jsonl")
    assert [(t.name, t.tool_class, t.ok) for t in ex.tool_calls] == [("Bash", "shell", True)]
    assert ex.tool_calls[0].start and ex.tool_calls[0].end


def test_claude_tool_search_is_class_meta(tmp_path):  # R-54 (a): it loads a schema and invokes nothing
    rows = [{"type": "assistant", "timestamp": "2026-09-25T05:20:53.616Z",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": {},
                         "content": [{"type": "tool_use", "id": "t1", "name": "ToolSearch", "input": {"query": "select:WebFetch"}}]}},
            {"type": "user", "timestamp": "2026-09-25T05:20:54.244Z",
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "loaded"}]}}]
    record = tmp_path / "s.jsonl"
    record.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert [(t.name, t.tool_class, t.ok) for t in claude_code.read(record).tool_calls] == [("ToolSearch", "meta", True)]


def test_claude_first_user_text_is_the_prompt():
    assert claude_code.read(FIX / "native/claude-code/ok.jsonl").first_user_text == PROMPT


def test_claude_api_error_rows_are_errors_never_model_calls():  # probe W3
    ex = claude_code.read(FIX / "native/claude-code/model-not-found.jsonl")
    assert ex.model_calls == []
    assert [(e.status, e.error_type) for e in ex.errors] == [(404, "model_not_found")]


def test_claude_account_connector_tools_counts_two_distinct_advertised_names():  # R-36, R-43
    """Example_one is advertised twice (loaded and deferred) and Example_two once: two tools.
    Bash, Read and NotebookEdit are not account connectors; a removed name is not advertised."""
    ex = claude_code.read(FIX / "native/claude-code/account-connectors.jsonl")
    assert ex.account_connector_tools == 2


def test_claude_account_connector_tools_is_zero_when_a_read_record_advertises_none():  # R-43
    assert claude_code.read(FIX / "native/claude-code/ok.jsonl").account_connector_tools == 0


def test_account_connector_tools_is_none_when_the_claude_reader_did_not_read_the_record():  # R-43: not read, never 0
    """Only the Claude Code reader reads the field; any other extraction leaves it not recorded."""
    assert Extraction().account_connector_tools is None
    assert codex.read(FIX / "native/codex/ok.jsonl").account_connector_tools is None


# Codex --------------------------------------------------------------------------------------------

def test_codex_token_counts_become_disjoint_buckets():
    ex = codex.read(FIX / "native/codex/ok.jsonl")
    assert len(ex.model_calls) == 3 and {c.model for c in ex.model_calls} == {"gpt-6-sol"}
    first = ex.model_calls[0]
    # OpenAI-style input includes cached tokens; the bucket is uncached = input - cached (ADR-0006)
    assert (first.uncached_input, first.cache_read, first.cache_write, first.output, first.reasoning) == (14920 - 11904, 11904, 0, 393, 313)
    assert sum(c.uncached_input + c.cache_read for c in ex.model_calls) == 45888


def test_codex_first_user_text_skips_tagged_context():
    assert codex.read(FIX / "native/codex/ok.jsonl").first_user_text == PROMPT


X1_PROMPT = ("Implement the function `slugify` in `slug.py` so that it does exactly what its docstring says. "
             "Keep the function name and signature. Do not add dependencies.\n")


def test_codex_first_user_text_skips_the_agents_md_instructions_block():  # US-10, real E2E (T8 defect 1)
    """The pack-on cell's first user message is <recommended_plugins> + '# AGENTS.md instructions for
    ...<INSTRUCTIONS>...</INSTRUCTIONS>' + <environment_context>: none of those is the prompt, which is
    the next user message, verbatim."""
    assert codex.read(FIX / "native/codex/pack-on.jsonl").first_user_text == X1_PROMPT


def test_codex_tool_calls_are_found():
    ex = codex.read(FIX / "native/codex/ok.jsonl")
    assert len(ex.tool_calls) == 2 and all(t.tool_class == "shell" for t in ex.tool_calls)
    assert all(t.end for t in ex.tool_calls)


def test_codex_web_search_call_is_an_out_of_profile_tool_row(tmp_path):
    record = tmp_path / "rollout.jsonl"
    record.write_text(json.dumps({"type": "response_item", "timestamp": "2026-01-01T00:00:00Z",
                                  "payload": {"type": "web_search_call", "id": "ws-1", "status": "completed",
                                              "action": {"type": "search", "query": "example"}}}) + "\n", encoding="utf-8")
    calls = codex.read(record).tool_calls
    assert [(call.name, call.tool_class, call.native_ordinal) for call in calls] == [("web_search", "other", 1)]


def test_codex_mcp_item_inside_exec_is_an_out_of_profile_tool_row():
    # qual-r45-1, rollout item_completed/McpToolCall; fixture keeps only its structural fields.
    ex = codex.read(FIX / "native/codex/mcp-inside-exec.jsonl")
    assert [(call.name, call.tool_class, call.native_ordinal, call.ok) for call in ex.tool_calls] == [
        ("codex_apps.higgsfield.create_website", "other", 1, False)]
    rows = normalize.tool_call_rows("r", "c", ex.session_id, ex, "x")
    assert [(row["name"], row["tool_class"]) for row in rows] == [
        ("codex_apps.higgsfield.create_website", "other")]


def test_codex_task_complete_error_is_a_provider_error_row():  # probe W3
    ex = codex.read(FIX / "native/codex/model-error.jsonl")
    assert [(e.status, e.error_type) for e in ex.errors] == [(400, "invalid_request_error")]
    assert ex.model_calls == []


def _codex_task_complete(tmp_path, message: str):
    """A placeholder rollout: task_complete carries only error text, no status field. The key is the masked `sk-****`."""
    record = tmp_path / "rollout.jsonl"
    row = {"type": "event_msg", "payload": {"type": "task_complete", "error": {"message": message}}}
    record.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return codex.read(record)


def test_codex_unexpected_status_401_is_blocked_auth(tmp_path):  # R-23: 401 in the CLI text is an auth block
    message = "unexpected status 401 Unauthorized: Incorrect API key provided: sk-****"
    ex = _codex_task_complete(tmp_path, message)
    assert ex.errors[0].message == message  # stored as the CLI printed it; the key stays masked
    assert (ex.errors[0].status, normalize.classify(ex.errors)) == (401, Cause.blocked_auth)


def test_codex_unexpected_status_403_is_blocked_auth(tmp_path):  # R-23: 403 is an auth block too
    message = "unexpected status 403 Forbidden: Incorrect API key provided: sk-****"
    ex = _codex_task_complete(tmp_path, message)
    assert ex.errors[0].message == message
    assert (ex.errors[0].status, normalize.classify(ex.errors)) == (403, Cause.blocked_auth)


def test_codex_unexpected_status_404_stays_model_unavailable(tmp_path):  # R-23: any other status stays model_unavailable
    message = "unexpected status 404 Not Found: model missing sk-****"
    ex = _codex_task_complete(tmp_path, message)
    assert ex.errors[0].message == message
    assert (ex.errors[0].status, normalize.classify(ex.errors)) == (404, Cause.model_unavailable)


def test_codex_unexpected_status_429_stays_provider(tmp_path):  # R-23: 429 stays provider
    message = "unexpected status 429 Too Many Requests: rate limit sk-****"
    ex = _codex_task_complete(tmp_path, message)
    assert ex.errors[0].message == message
    assert (ex.errors[0].status, normalize.classify(ex.errors)) == (429, Cause.provider)


def test_a_codex_status_field_wins_over_unexpected_status_text(tmp_path):
    """A JSON status field is the status. The text is stored as printed, including a masked key."""
    message = ('{"status": 400, "error": {"type": "invalid_request_error", "message": '
               '"unexpected status 401 Unauthorized: sk-****"}}')
    ex = _codex_task_complete(tmp_path, message)
    assert ex.errors[0].message == message
    assert (ex.errors[0].status, ex.errors[0].error_type, normalize.classify(ex.errors)) == (
        400, "invalid_request_error", Cause.model_unavailable)


def test_unexpected_status_text_is_a_status_for_every_reader(tmp_path):
    """Claude and Copilot records have no status field either; the same phrase fills ProviderError.status."""
    message = "unexpected status 401 Unauthorized: Incorrect API key provided: sk-****"
    claude = tmp_path / "claude.jsonl"
    claude.write_text(json.dumps({"type": "assistant", "isApiErrorMessage": True, "message": {"content": message}}) + "\n",
                      encoding="utf-8")
    claude_ex = claude_code.read(claude)
    assert claude_ex.errors[0].message == message
    assert (claude_ex.errors[0].status, normalize.classify(claude_ex.errors)) == (401, Cause.blocked_auth)
    copilot_record = tmp_path / "events.jsonl"
    copilot_record.write_text(json.dumps({"type": "session.error", "data": {"message": message}}) + "\n", encoding="utf-8")
    copilot_ex = copilot.read(copilot_record)
    assert copilot_ex.errors[0].message == message
    assert (copilot_ex.errors[0].status, normalize.classify(copilot_ex.errors)) == (401, Cause.blocked_auth)


# classification (design: failure taxonomy; W3) -------------------------------------------------

@pytest.mark.parametrize("status, etype, cause", [
    (429, "rate_limit_error", Cause.provider), (529, "overloaded_error", Cause.provider),
    (500, "api_error", Cause.provider), (408, "timeout", Cause.provider), (None, "overloaded_error", Cause.provider),
    (404, "model_not_found", Cause.model_unavailable), (400, "invalid_request_error", Cause.model_unavailable),
    (401, "api_error", Cause.blocked_auth), (403, "api_error", Cause.blocked_auth),  # status decides before the type
])
def test_error_classification(status, etype, cause):
    assert normalize.classify([claude_code.ProviderError(1, status, etype, "")]) is cause


def test_no_errors_classify_to_none():
    assert normalize.classify([]) is None


# status-less text classification (CAUSE-A: grid-2 cc-opus and copilot-sol both silently fell to model_unavailable,
# which opens a combo-scoped qualification_gap and skips the whole combo instead of blocking the harness or
# counting as infrastructure; the native-record scan and driver._prompt_error_cause now share this one rule) ---

def test_grid2_cc_opus_auth_row_is_blocked_auth():
    """Redacted from runs/grid-2/archive/9b4c563f3d520ee6 (attempt-1 native record, line 16): no apiErrorStatus
    field at all, error 'authentication_failed', message 'Failed to authenticate: OAuth session expired and
    could not be refreshed'. Was HB-CELL-116 (model_unavailable); must be blocked_auth (HB-CELL-202)."""
    e = claude_code.ProviderError(1, None, "authentication_failed",
                                  "Failed to authenticate: OAuth session expired and could not be refreshed")
    assert (e.status, normalize.classify([e])) == (None, Cause.blocked_auth)


def test_grid2_copilot_sol_dns_row_is_provider():
    """Redacted from runs/grid-2/archive/dd44b0981d5f34f5 (session.error, events.jsonl line 34): errorType
    'query', message '...client error (Connect): dns error: error resolving DNS: No such host is known.
    (os error 11001) [ENOTFOUND]'. Was HB-CELL-116 (model_unavailable); must be provider (HB-CELL-108)."""
    message = ("Execution failed: Failed to get response from the AI model; retried 5 times (total retry wait "
               "time: 23.00 seconds) Last error: Failed native model HTTP request: error sending request for url "
               "(https://api.enterprise.githubcopilot.com/responses): client error (Connect): dns error: error "
               "resolving DNS: No such host is known. (os error 11001) [ENOTFOUND]")
    e = copilot.ProviderError(1, None, "query", message[:300])
    assert (e.status, normalize.classify([e])) == (None, Cause.provider)


def test_grid2_cc_opus_row_through_the_reader_is_blocked_auth(tmp_path):
    """The full path: claude_code.read() builds the ProviderError from the redacted row, then classify()."""
    record = tmp_path / "session.jsonl"
    record.write_text(json.dumps({"type": "assistant", "isApiErrorMessage": True, "error": "authentication_failed",
                                  "message": {"content": "Failed to authenticate: OAuth session expired and "
                                                          "could not be refreshed"}}) + "\n", encoding="utf-8")
    ex = claude_code.read(record)
    assert (ex.errors[0].status, ex.errors[0].error_type) == (None, "authentication_failed")
    assert normalize.classify(ex.errors) == Cause.blocked_auth


def test_grid2_copilot_sol_row_through_the_reader_is_provider(tmp_path):
    """The full path: copilot.read() builds the ProviderError from the redacted row, then classify()."""
    message = ("Execution failed: Failed to get response from the AI model; retried 5 times (total retry wait "
               "time: 23.00 seconds) Last error: Failed native model HTTP request: error sending request for url "
               "(https://api.enterprise.githubcopilot.com/responses): client error (Connect): dns error: error "
               "resolving DNS: No such host is known. (os error 11001) [ENOTFOUND]")
    record = tmp_path / "events.jsonl"
    record.write_text(json.dumps({"type": "session.error", "data": {"errorType": "query", "message": message}}) + "\n",
                      encoding="utf-8")
    ex = copilot.read(record)
    assert (ex.errors[0].status, ex.errors[0].error_type) == (None, "query")
    assert normalize.classify(ex.errors) == Cause.provider


@pytest.mark.parametrize("message", [
    "Login failed: your session has expired, please sign in again",  # 'login', no 'auth'
    "invalid credential: token not found",  # 'credential', no 'auth'
])
def test_other_status_less_auth_texts_are_blocked_auth(message):
    e = claude_code.ProviderError(1, None, "unknown", message)
    assert normalize.classify([e]) == Cause.blocked_auth


@pytest.mark.parametrize("message", [
    "connect ECONNREFUSED 127.0.0.1:443",
    "read ECONNRESET",
    "socket hang up: connection reset by peer",
])
def test_other_status_less_network_texts_are_provider(message):
    e = claude_code.ProviderError(1, None, "unknown", message)
    assert normalize.classify([e]) == Cause.provider


def test_a_status_still_decides_first_even_with_auth_or_network_words_in_the_text():
    """The text rule applies only when there is no status (CAUSE-A): a 4xx with 'auth' in the message stays whatever
    the status decides, matching the existing status-first precedence (test_error_classification)."""
    e = claude_code.ProviderError(1, 400, "invalid_request_error", "authentication context: model not found")
    assert normalize.classify([e]) == Cause.model_unavailable


# the adapter's turn usage (authoritative for Claude, a cross-check for Codex) ------------------------

def test_claude_turn_usage_names_every_model_including_the_auxiliary_one():
    resp = json.loads((FIX / "acp/claude-code-prompt-response.json").read_text(encoding="utf-8"))
    usage = normalize.turn_usage(resp)
    assert {u.model for u in usage} == {"claude-sonnet-5", "claude-haiku-4-5-20251001"}
    sonnet = next(u for u in usage if u.model == "claude-sonnet-5")
    assert (sonnet.uncached_input, sonnet.cache_read, sonnet.cache_write, sonnet.output) == (4, 56760, 12297, 121)


def test_authoritative_totals_follow_the_profile_source():
    claude_resp = json.loads((FIX / "acp/claude-code-prompt-response.json").read_text(encoding="utf-8"))
    claude_ex = claude_code.read(FIX / "native/claude-code/ok.jsonl")
    totals = normalize.totals("acp_turn", claude_ex, normalize.turn_usage(claude_resp))
    assert totals["claude-sonnet-5"]["cache_read"] == 56760  # not the record's 23729 (it misses the last call)
    codex_resp = json.loads((FIX / "acp/codex-prompt-response.json").read_text(encoding="utf-8"))
    codex_ex = codex.read(FIX / "native/codex/ok.jsonl")
    totals = normalize.totals("native_record", codex_ex, normalize.turn_usage(codex_resp))
    assert totals["gpt-6-sol"]["uncached_input"] + totals["gpt-6-sol"]["cache_read"] == 45888  # not the adapter's last call


def test_served_models_and_the_one_call_rule():  # US-11
    claude_resp = json.loads((FIX / "acp/claude-code-prompt-response.json").read_text(encoding="utf-8"))
    served = normalize.served_models("acp_turn", claude_code.read(FIX / "native/claude-code/ok.jsonl"), normalize.turn_usage(claude_resp))
    assert served == {"claude-sonnet-5", "claude-haiku-4-5-20251001"}
    assert normalize.served_models("native_record", codex.read(FIX / "native/codex/model-error.jsonl"), []) == set()


# base_model_id / context_window_tag (R-32): a trailing bracketed context-window tag is not identity ------

@pytest.mark.parametrize("model, base, tag", [
    ("claude-opus-5-5[1m]", "claude-opus-5-5", "1m"),  # the measured defect (run e2e-wave1-1790299304)
    ("claude-opus-5-5", "claude-opus-5-5", None),  # no trailing bracket: unchanged, no tag
    ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001", None),  # the auxiliary model, untouched
    ("claude-sonnet-5[1m]", "claude-sonnet-5", "1m"),  # a genuinely different served model, still tagged
])
def test_base_model_id_strips_only_a_trailing_bracket_tag(model, base, tag):
    assert normalize.base_model_id(model) == base
    assert normalize.context_window_tag(model) == tag


def test_base_model_id_never_strips_a_bracket_that_is_not_trailing():
    assert normalize.base_model_id("weird[legacy]-model") == "weird[legacy]-model"
    assert normalize.context_window_tag("weird[legacy]-model") is None


# real cc-opus turn_usage rows, run e2e-wave1-1790299304 cell 17efb75ce2d5fc6d (pin claude-opus-5-5)
CC_OPUS_USAGE = [normalize.TurnUsage("claude-haiku-4-5-20251001", 929, 0, 0, 14, 0),
                 normalize.TurnUsage("claude-opus-5-5[1m]", 10, 179401, 27730, 1385, 0)]


def test_served_models_reads_the_base_id_not_the_tagged_served_id():  # R-32
    assert normalize.served_models("acp_turn", Extraction(), CC_OPUS_USAGE) == {"claude-haiku-4-5-20251001", "claude-opus-5-5"}


def test_totals_groups_a_tagged_and_an_untagged_served_id_under_one_base_model():  # R-32
    usage = [*CC_OPUS_USAGE, normalize.TurnUsage("claude-opus-5-5", 2, 100, 0, 50, 0)]
    totals = normalize.totals("acp_turn", Extraction(), usage)
    assert set(totals) == {"claude-haiku-4-5-20251001", "claude-opus-5-5"}
    assert totals["claude-opus-5-5"]["output"] == 1385 + 50  # the tagged and untagged rows summed as one model


# bounded readers never crash (D2) ------------------------------------------------------------------

# Every key and enum value either reader looks at, so fuzzed rows reach deep into all three readers.
_WORDS = ["type", "message", "payload", "content", "id", "model", "usage", "tool_use_id", "tool_use", "tool_result", "name",
          "call_id", "info", "total_token_usage", "last_token_usage", "error", "isApiErrorMessage", "apiErrorStatus",
          "sessionId", "session_id", "timestamp", "role", "text", "is_error", "user", "assistant", "session_meta",
          "turn_context", "event_msg", "response_item", "token_count", "task_complete", "function_call",
          "function_call_output", "custom_tool_call", "local_shell_call_output", "input_tokens", "output_tokens",
          "cached_input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "cache_write_input_tokens",
          "reasoning_output_tokens", "status", "claude-sonnet-5", "<synthetic>", "Bash", "shell", "t1",
          # Copilot (telemetry/copilot.py): event types, the version gate, model_calls/tool_calls/hooks fields.
          "data", "version", "session.start", "session.shutdown", "session.error", "user.message", "agentId",
          "toolCallId", "toolName", "toolType", "success", "code", "modelMetrics", "requests", "count",
          "tokenDetails", "cacheReadTokens", "cacheWriteTokens", "outputTokens", "reasoningTokens", "inputTokens",
          "tool.execution_start", "tool.execution_complete", "hook.start", "hook.end", "hookType",
          "transformedContent", "currentModel", "errorType", "gpt-6-sol"]
_LEAF = st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.sampled_from(_WORDS),
                  st.text(max_size=8))
_VALUE = st.recursive(_LEAF, lambda kids: st.one_of(st.lists(kids, max_size=4),
                                                    st.dictionaries(st.sampled_from(_WORDS), kids, max_size=5)), max_leaves=30)
_ROW = st.dictionaries(st.sampled_from(_WORDS), _VALUE, max_size=6).map(json.dumps)
_WRONG = st.one_of(st.lists(_LEAF, max_size=3), st.dictionaries(st.sampled_from(_WORDS), _LEAF, max_size=3),
                   st.integers(), st.floats(allow_nan=False), st.booleans(), st.text(max_size=8))  # wrong type or range
_GOLDEN = [[json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
           for f in sorted((FIX / "native").glob("**/*.jsonl"))]  # "**" also reaches native/copilot/{off,on}/session-state/<sid>/


def _paths(value, prefix=()):
    yield prefix
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for k, v in items:
        yield from _paths(v, (*prefix, k))


@st.composite
def _mutated_golden(draw) -> list[str]:
    """A real record with one to five values (anywhere in it) replaced by fuzz: ids still pair up, so the
    fuzz reaches every reader branch (model calls, tool calls closed by their results, errors)."""
    rows = json.loads(json.dumps(draw(st.sampled_from(_GOLDEN))))
    for _ in range(draw(st.integers(1, 5))):
        row = draw(st.sampled_from(rows))
        path = draw(st.sampled_from([p for p in _paths(row) if p and p[-1] in _WORDS] or [("type",)]))
        parent = row
        for k in path[:-1]:
            parent = parent[k]
        parent[path[-1]] = draw(_WRONG)
    return [json.dumps(r) for r in rows]


_NESTED = st.integers(min_value=1, max_value=100_000).flatmap(
    lambda n: st.sampled_from(["[" * n, '{"a":' * n, '{"type":"user","timestamp":' + "[" * n]))
_LINE = st.one_of(_ROW, _ROW, _ROW, st.binary(max_size=200).map(lambda b: b.decode("latin-1")), _NESTED)
_BUCKETS = ("uncached_input", "cache_read", "cache_write", "output")


def _assert_typed(ex) -> None:
    """The reader's output is the canonical shape, whatever the record held: no foreign type leaks into a row."""
    assert ex.session_id is None or isinstance(ex.session_id, str)
    assert ex.first_user_text is None or isinstance(ex.first_user_text, str)
    for c in ex.model_calls:
        assert type(c.native_ordinal) is int and isinstance(c.model, str)
        assert all(type(getattr(c, b)) is int and 0 <= getattr(c, b) < 1 << 63 for b in _BUCKETS)
        assert c.reasoning is None or (type(c.reasoning) is int and 0 <= c.reasoning < 1 << 63)
        assert all(v is None or isinstance(v, str) for v in (c.start, c.end))
    for t in ex.tool_calls:
        assert isinstance(t.name, str) and t.tool_class in ("shell", "edit", "read", "meta", "delegate", "scripted user", "other")
        assert all(v is None or isinstance(v, str) for v in (t.start, t.end)) and t.ok in (True, False, None)
    for e in ex.errors:
        assert (e.status is None or type(e.status) is int) and isinstance(e.error_type, str) and isinstance(e.message, str)
    json.dumps(normalize.model_call_rows("r", "c", "s", ex, "x") + normalize.tool_call_rows("r", "c", "s", ex, "x"))


@settings(max_examples=300, deadline=None)
@given(st.one_of(st.lists(_LINE, max_size=12), _mutated_golden()))
def test_fuzzed_records_never_crash_either_reader_and_stay_typed(tmp_path_factory, lines):  # T-TEL-fuzz (D2)
    path = tmp_path_factory.mktemp("fz") / "r.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
    for reader in (claude_code, codex, copilot):
        _assert_typed(reader.read(path))


@pytest.mark.parametrize("line", [
    '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":[1]}]}}',
    '{"type":"response_item","payload":{"type":"function_call_output","call_id":{"a":1}}}',
    '{"type":"session_meta","payload":{"id":[1]}}',
    '{"type":"response_item","timestamp":[1],"payload":{"type":"function_call","call_id":"c1","name":["x"]}}',
    '{"type":"session.start","data":{"version":[1]}}',
    '{"type":"session.start","data":{"version":{"a":1}}}',
], ids=["claude-list-tool-id", "codex-dict-call-id", "codex-list-session-id", "codex-list-timestamp-and-name",
        "copilot-list-version", "copilot-dict-version"])
def test_foreign_types_in_known_fields_are_ignored_not_crashed_on(tmp_path, line):  # T-TEL-fuzz regressions
    path = tmp_path / "r.jsonl"
    path.write_text(line + "\n", encoding="utf-8")
    for reader in (claude_code, codex, copilot):
        _assert_typed(reader.read(path))


@pytest.mark.parametrize("reader", [claude_code, codex, copilot], ids=["claude-code", "codex", "copilot"])
def test_deeply_nested_and_huge_lines_are_skipped_as_malformed(tmp_path, reader):  # T-TEL-fuzz: 100,000-deep nesting
    path = tmp_path / "r.jsonl"
    # 10 MiB -- past the 8 MiB bound (HB-CELL-107 fix), so this stays malformed/skipped either way.
    path.write_text("[" * 100_000 + "\n" + '{"a":' * 100_000 + "\n" + "x" * (10 << 20) + "\n", encoding="utf-8")
    ex = reader.read(path)
    assert ex.model_calls == [] and ex.malformed_lines == 3


@pytest.mark.parametrize("reader", [claude_code, codex, copilot], ids=["claude-code", "codex", "copilot"])
def test_a_large_legitimate_line_within_the_raised_bound_is_not_skipped(tmp_path, reader):
    """grid-3's archived evidence: a Claude Code image tool_result and a Codex verbose-stdout
    CommandExecution both wrote a single native-record line of 1.0-2.3 MiB -- valid JSON, not
    malformed, just a large tool-result payload. The reader's own 1 MiB bound (sized without
    measuring real payloads, like driver.py's identical HB-CELL-107 bound) silently dropped a line
    this size as malformed, losing that row's data. Raised to 8 MiB (same margin, same measurement)."""
    path = tmp_path / "r.jsonl"
    big_line = json.dumps({"big": "x" * (2 << 20)})
    path.write_text(big_line + "\n", encoding="utf-8")
    ex = reader.read(path)
    assert ex.malformed_lines == 0


def _without(src: Path, dest: Path, usage_key: str, field: str) -> None:
    """Copy a golden record, dropping one usage field from every row that carries it."""
    out = []
    for line in src.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for holder in (row.get("message", {}).get("usage"), row.get("payload", {}).get("info", {}).get(usage_key)):
            if isinstance(holder, dict):
                holder.pop(field, None)
        out.append(json.dumps(row))
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")


@pytest.mark.parametrize("reader, golden, field", [
    (claude_code, "claude-code/ok.jsonl", "output_tokens"),
    (codex, "codex/ok.jsonl", "cache_write_input_tokens"),
], ids=["claude-code", "codex"])
def test_a_missing_usage_field_is_hb_tel_001_not_a_silent_zero(tmp_path, reader, golden, field):  # T-TEL-missing
    from harness_bench.errors import RUN_CODES
    whole = reader.read(FIX / "native" / golden)
    assert whole.missing == []
    _without(FIX / "native" / golden, tmp_path / "r.jsonl", "last_token_usage", field)
    ex = reader.read(tmp_path / "r.jsonl")
    assert ex.missing and {(m.code, m.field) for m in ex.missing} == {("HB-TEL-001", field)}
    assert {m.native_ordinal for m in ex.missing} == {c.native_ordinal for c in ex.model_calls}
    assert "HB-TEL-001" in RUN_CODES


def test_a_negative_or_oversized_count_is_hb_tel_001_not_a_number(tmp_path):  # a count must fit a signed 64-bit column
    usage = {"input_tokens": -5, "output_tokens": 1 << 70, "cache_read_input_tokens": True, "cache_creation_input_tokens": 3}
    row = {"type": "assistant", "message": {"id": "m1", "model": "claude-sonnet-5", "usage": usage}}
    (tmp_path / "r.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    ex = claude_code.read(tmp_path / "r.jsonl")
    call = ex.model_calls[0]
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output) == (0, 0, 3, 0)
    assert {m.field for m in ex.missing} == {"input_tokens", "output_tokens", "cache_read_input_tokens"}


def test_a_newline_free_record_is_read_in_bounded_memory(tmp_path, monkeypatch):  # the reader holds one line at most
    import tracemalloc

    from harness_bench import telemetry
    monkeypatch.setattr(telemetry, "MAX_LINE", 1024)
    path = tmp_path / "r.jsonl"
    path.write_bytes(b"x" * (8 << 20) + b"\n" + json.dumps({"type": "user", "sessionId": "s1"}).encode() + b"\n")
    tracemalloc.start()
    try:
        ex = claude_code.read(path)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 1 << 20, f"peak {peak} bytes for an 8 MiB line"
    assert ex.malformed_lines == 1 and ex.session_id == "s1"  # the long line is skipped whole; the next line is read


def test_extraction_id_is_the_normaliser_build_hash():
    a = normalize.extraction_id()
    assert len(a) == 64 and a == normalize.extraction_id()


# PI-T6 (design pack-improvement-section.md section 11, slice S2): each harness's `tool_inputs`, read
# from the same committed fixtures `read()` already uses, returns the paths, commands and `is_write`
# the pack-improvement report section's ceremony/drift indicators are built on.

def test_pi_t6_claude_code_tool_inputs_reads_command_and_no_text_block():
    trace = claude_code.tool_inputs(FIX / "native/claude-code/ok.jsonl")
    assert trace.first_assistant_text is None  # this fixture's only assistant row is the tool call itself
    assert [(c.name, c.paths, c.command, c.is_write) for c in trace.calls] == [
        ("Bash", (), 'python -c "print(6*7)" > answer.txt && cat answer.txt', False),
    ]


def test_pi_t6_claude_code_tool_inputs_marks_write_tools_and_reads_paths(tmp_path):
    rows = [
        {"type": "assistant", "timestamp": "2026-09-25T05:20:53.616Z",
         "message": {"id": "m1", "model": "claude-opus-5-5", "usage": {},
                     "content": [{"type": "text", "text": "Goal: fix the bug."},
                                 {"type": "tool_use", "id": "t1", "name": "Edit",
                                  "input": {"file_path": "src/a.py", "command": "replace"}}]}},
    ]
    record = tmp_path / "s.jsonl"
    record.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    trace = claude_code.tool_inputs(record)
    assert trace.first_assistant_text == "Goal: fix the bug."
    assert trace.calls == (claude_code.ToolInput(1, "Edit", ("src/a.py",), "replace", True),)


def test_pi_t6_codex_tool_inputs_reads_exec_commands():
    trace = codex.tool_inputs(FIX / "native/codex/ok.jsonl")
    assert trace.first_assistant_text == "I’ll run the command and write its stdout bytes to `answer.txt`."
    assert [(c.name, c.paths, c.command, c.is_write) for c in trace.calls] == [
        ("exec", (), 'python -c "print(6*7)"', False),
        ("exec", (), "[System.IO.File]::WriteAllBytes((Join-Path (Get-Location) 'answer.txt'), [byte[]](52,50,13,10))", False),
    ]


# Regression (Leader forensic review, 2026-09-30, verified bug 2): the old `_PATCH_HEADER` pattern
# excluded backslash outright, so a Windows absolute path in a Copilot `apply_patch` body truncated
# to "C:" -- confirmed against the real archive, `runs/grid-1/archive/4a6250261f80ded4/attempt-1/
# home/session-state/d72fa471-ad50-4c41-97a2-8cb4a164683c/events.jsonl:126` (a Copilot D1 cell).

def test_patch_header_paths_keeps_a_windows_absolute_path_with_backslashes():
    text = (
        '*** Begin Patch\n*** Add File: C:\\Projects\\bench-cells\\grid-1\\4a6250261f80ded4\\'
        'ws-evidence-census\\tests\\AiDe.Core.Tests\\EvidenceCensusProjectionTests.cs\n'
        '+using AiDe.Core.Facts;\n*** End Patch\n'
    )
    expected_path = (
        'C:\\Projects\\bench-cells\\grid-1\\4a6250261f80ded4\\ws-evidence-census\\tests\\'
        'AiDe.Core.Tests\\EvidenceCensusProjectionTests.cs'
    )
    assert patch_header_paths(text) == (expected_path,)


def test_patch_header_paths_keeps_a_posix_absolute_path():
    text = '*** Begin Patch\n*** Update File: /home/user/repo/src/a.py\n@@\n*** End Patch\n'  # machine-path-ok: patch-header parser input
    assert patch_header_paths(text) == ('/home/user/repo/src/a.py',)  # machine-path-ok: patch-header parser input


def test_pi_t6_codex_tool_inputs_apply_patch_update_header_is_a_write():
    trace = codex.tool_inputs(FIX / "native/codex/pack-on.jsonl")
    writes = [c for c in trace.calls if c.is_write]
    assert len(writes) == 1
    assert writes[0].paths == ("../ws-slugify/slug.py",)
    assert writes[0].command is None
    assert trace.first_assistant_text.startswith("Goal: make `slugify` match its docstring.")


@pytest.mark.parametrize(
    ("reader", "fixture"),
    [
        (claude_code, "native/claude-code/ok.jsonl"),
        (codex, "native/codex/ok.jsonl"),
        # pack-on.jsonl has no MCP/web_search rows (checked 2026-09-30): every ToolCall on this
        # fixture comes from the same `function_call`/`custom_tool_call`/`local_shell_call` family
        # `tool_inputs` walks, so the counts are directly comparable (R-85 condition 1's scope,
        # "codex.py:41 CALL_TYPES" -- not the out-of-band MCP/web_search rows `mcp-inside-exec.jsonl`
        # covers, which `tool_inputs` does not claim to count).
        (codex, "native/codex/pack-on.jsonl"),
    ],
)
def test_pi_t6_trace_length_equals_extractor_tool_call_count(reader, fixture):
    """R-85 condition 1: `tool_inputs` and `read` are two projections of the one call family, so a
    fixture with no out-of-band call source gives the same count from both."""
    path = FIX / fixture
    assert len(reader.tool_inputs(path).calls) == len(reader.read(path).tool_calls)
