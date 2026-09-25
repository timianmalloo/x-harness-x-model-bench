"""Telemetry from native records and the adapter's turn usage (ADR-0008 as amended; probe W3; golden
fixtures captured 2026-09-23 with the pinned builds)."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench.errors import Cause
from harness_bench.telemetry import Extraction, claude_code, codex, copilot, normalize

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


def test_codex_task_complete_error_is_a_provider_error_row():  # probe W3
    ex = codex.read(FIX / "native/codex/model-error.jsonl")
    assert [(e.status, e.error_type) for e in ex.errors] == [(400, "invalid_request_error")]
    assert ex.model_calls == []


# classification (design: failure taxonomy; W3) -------------------------------------------------

@pytest.mark.parametrize("status, etype, cause", [
    (429, "rate_limit_error", Cause.provider), (529, "overloaded_error", Cause.provider),
    (500, "api_error", Cause.provider), (408, "timeout", Cause.provider), (None, "overloaded_error", Cause.provider),
    (404, "model_not_found", Cause.model_unavailable), (400, "invalid_request_error", Cause.model_unavailable),
])
def test_error_classification(status, etype, cause):
    assert normalize.classify([claude_code.ProviderError(1, status, etype, "")]) is cause


def test_no_errors_classify_to_none():
    assert normalize.classify([]) is None


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
        assert isinstance(t.name, str) and t.tool_class in ("shell", "edit", "read", "other")
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
    path.write_text("[" * 100_000 + "\n" + '{"a":' * 100_000 + "\n" + "x" * (2 << 20) + "\n", encoding="utf-8")
    ex = reader.read(path)
    assert ex.model_calls == [] and ex.malformed_lines == 3


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
