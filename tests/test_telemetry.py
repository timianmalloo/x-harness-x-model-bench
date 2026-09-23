"""Telemetry from native records and the adapter's turn usage (ADR-0008 as amended; probe W3; golden
fixtures captured 2026-09-23 with the pinned builds)."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench.errors import Cause
from harness_bench.telemetry import claude_code, codex, normalize

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


# bounded readers never crash (D2) ------------------------------------------------------------------

@settings(max_examples=150, deadline=None)
@given(st.lists(st.one_of(st.binary(max_size=200).map(lambda b: b.decode("latin-1")),
                          st.dictionaries(st.sampled_from(["type", "message", "payload", "isApiErrorMessage"]),
                                          st.one_of(st.none(), st.integers(), st.text(max_size=10),
                                                    st.dictionaries(st.text(max_size=5), st.integers(), max_size=3)),
                                          max_size=4).map(json.dumps)), max_size=12))
def test_fuzzed_records_never_crash_either_reader(tmp_path_factory, lines):
    path = tmp_path_factory.mktemp("fz") / "r.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
    for reader in (claude_code, codex):
        ex = reader.read(path)
        assert isinstance(ex.model_calls, list)


def test_deeply_nested_and_huge_lines_are_skipped_as_malformed(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text("[" * 100_000 + "\n" + "x" * (2 << 20) + "\n", encoding="utf-8")
    ex = claude_code.read(path)
    assert ex.model_calls == [] and ex.malformed_lines == 2


def test_extraction_id_is_the_normaliser_build_hash():
    a = normalize.extraction_id()
    assert len(a) == 64 and a == normalize.extraction_id()
