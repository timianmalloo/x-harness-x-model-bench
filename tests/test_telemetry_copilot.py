"""Copilot telemetry reader (design docs/design/phase2-copilot-profile.md section 4.4; the section 13
promise-to-test table rows owned by W1-COP-R). Golden fixtures: capture window 1, `tests/fixtures/native/
copilot/{off,on}` (`9c6c615`, rescrubbed `f952f87`; `on/` is the revision-92 pack-on sample, R-27 c3 --
kept as the negative control until a revision-95 capture replaces it for every other check)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness_bench.telemetry import copilot, normalize

FIX = Path(__file__).parent / "fixtures"
COPILOT_FIX = FIX / "native" / "copilot"
OFF = next((COPILOT_FIX / "off").rglob("events.jsonl"))
ON = next((COPILOT_FIX / "on").rglob("events.jsonl"))  # revision-92 pack-on (negative control)

# provenance.json: capture.prompt_sha256, and each arm's shutdown/acp_prompt_usage (Leader capture window 1)
PROMPT_SHA256 = "802dfde4c609549fd864c9b6cdc5c65bd5a5a2fe1f43246563d00c5e4dd9dc49"


def _us10_hash(text: str) -> str:
    """The spec's US-10 normaliser (docs/specs/harness-bench.md US-10): UTF-8, LF line endings, no
    BOM, one trailing newline, then hashed."""
    data = text.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    data = data.rstrip(b"\n") + b"\n"
    return hashlib.sha256(data).hexdigest()


def _write(tmp_path: Path, lines: list[dict], session_id: str = "syn-sid") -> Path:
    d = tmp_path / "session-state" / session_id
    d.mkdir(parents=True)
    path = d / "events.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def _row(kind: str, data: dict, ts: str = "2026-01-01T00:00:00.000Z", **extra) -> dict:
    row = {"type": kind, "data": data, "id": f"e-{kind}", "timestamp": ts, "parentId": None}
    row.update(extra)
    return row


def _start(version=1, session_id="syn-sid"):
    return _row("session.start", {"sessionId": session_id, "version": version})


def _user(content, transformed=None, agent_id: str | None = None, ts="2026-01-01T00:00:01.000Z"):
    extra = {"agentId": agent_id} if agent_id is not None else {}
    return _row("user.message", {"content": content, "transformedContent": transformed if transformed is not None else content},
                ts=ts, **extra)


def _model_metrics(model="gpt-6-sol", count=5, uncached=15, cache_read=100, cache_write=10, output=50, reasoning=5,
                    input_tokens=None):
    if input_tokens is None:
        input_tokens = uncached + cache_read + cache_write
    return {model: {"requests": {"count": count, "cost": 1}, "totalNanoAiu": 1,
                     "usage": {"inputTokens": input_tokens, "outputTokens": output, "cacheReadTokens": cache_read,
                               "cacheWriteTokens": cache_write, "reasoningTokens": reasoning},
                     "tokenDetails": {"input": {"tokenCount": uncached}, "cache_read": {"tokenCount": cache_read},
                                      "cache_write": {"tokenCount": cache_write}, "output": {"tokenCount": output}}}}


def _shutdown(model_metrics, ts="2026-01-01T00:10:00.000Z"):
    return _row("session.shutdown", {"shutdownType": "routine", "modelMetrics": model_metrics}, ts=ts)


# Golden samples: grain, buckets, hooks, the cross-check (R-26 C3) --------------------------------------

def test_off_yields_one_row_per_model_in_the_last_shutdown_with_requests():
    ex = copilot.read(OFF)
    assert len(ex.model_calls) == 1
    call = ex.model_calls[0]
    assert call.model == "gpt-6-sol" and call.requests == 5 and (call.start, call.end) == (None, None)
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output, call.reasoning) == (15, 46801, 12170, 515, 166)
    assert ex.missing == []


def test_on_yields_one_row_per_model_in_the_last_shutdown_with_requests():
    ex = copilot.read(ON)
    assert len(ex.model_calls) == 1
    call = ex.model_calls[0]
    assert call.model == "gpt-6-sol" and call.requests == 6 and (call.start, call.end) == (None, None)
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output, call.reasoning) == (18, 439386, 88237, 525, 170)
    assert ex.missing == []


@pytest.mark.parametrize("path, total_tokens", [(OFF, 59501), (ON, 528166)], ids=["off", "on"])
def test_golden_sample_cross_check_against_the_acp_usage_oracle(path, total_tokens):  # R-26 C3
    """Σ(uncached, cache_read, cache_write, output) == the independent oracle's ACP usage.totalTokens
    (provenance.json's acp_prompt_usage); reasoning is a component of output and is not added."""
    call = copilot.read(path).model_calls[0]
    assert call.uncached_input + call.cache_read + call.cache_write + call.output == total_tokens


def test_claude_code_and_codex_still_default_requests_to_one():  # design section 3: no change to other readers
    from harness_bench.telemetry import claude_code, codex

    claude_call = claude_code.read(FIX / "native/claude-code/ok.jsonl").model_calls[0]
    codex_calls = codex.read(FIX / "native/codex/ok.jsonl").model_calls
    assert claude_call.requests == 1
    assert codex_calls and all(c.requests == 1 for c in codex_calls)


def test_off_hooks_are_zero_not_none_and_on_rev92_is_eight_and_eight():  # section 4.5 / 13 reader test
    assert (copilot.read(OFF).hook_starts, copilot.read(OFF).hook_failures) == (0, 0)
    assert (copilot.read(ON).hook_starts, copilot.read(ON).hook_failures) == (8, 8)


def test_claude_code_and_codex_extractions_never_set_hook_fields():
    from harness_bench.telemetry import claude_code

    ex = claude_code.read(FIX / "native/claude-code/ok.jsonl")
    assert (ex.hook_starts, ex.hook_failures) == (None, None)


def test_off_tool_calls_succeed_and_on_rev92_are_all_denied():
    off = copilot.read(OFF).tool_calls
    assert len(off) == 6 and all((t.ok, t.outcome_code) == (True, None) for t in off)
    on = copilot.read(ON).tool_calls
    assert len(on) == 8 and all((t.ok, t.outcome_code) == (False, "denied") for t in on)
    assert {t.name for t in on} == {"skill", "glob", "powershell", "view", "rg"}
    assert next(t.tool_class for t in on if t.name == "skill") == "other"  # C: skill is other (design 4.4)


# US-10: the first user message, the normaliser, the sub-agent and later-message edge cases -----------

@pytest.mark.parametrize("path", [OFF, ON], ids=["off", "on"])
def test_us10_first_user_text_hash_matches_prompt_md_on_both_arms(path):
    assert _us10_hash(copilot.read(path).first_user_text) == PROMPT_SHA256


def test_us10_content_never_transformed_content(tmp_path):
    path = _write(tmp_path, [_start(), _user("real prompt", transformed="<scrubbed sha256=... markers=[]>"), _shutdown(_model_metrics())])
    assert copilot.read(path).first_user_text == "real prompt"


def test_us10_skips_a_sub_agent_message_before_the_main_one(tmp_path):
    """`assume:` a sub-agent's `user.message` always carries a top-level `agentId` (design section
    4.4, O7 revision 2). Confirmed here with a synthetic sub-agent-first sample."""
    path = _write(tmp_path, [
        _start(),
        _user("sub-agent prompt", agent_id="sub-1", ts="2026-01-01T00:00:00.500Z"),
        _user("main prompt", ts="2026-01-01T00:00:01.000Z"),
        _shutdown(_model_metrics()),
    ])
    assert copilot.read(path).first_user_text == "main prompt"


def test_us10_takes_the_first_of_two_main_user_messages(tmp_path):
    path = _write(tmp_path, [
        _start(),
        _user("first prompt"),
        _user("second prompt", ts="2026-01-01T00:05:00.000Z"),
        _shutdown(_model_metrics()),
    ])
    assert copilot.read(path).first_user_text == "first prompt"


# US-11: a renamed modelMetrics key, and an emptied modelMetrics ---------------------------------------

def test_us11_a_renamed_modelmetrics_key_is_not_the_pinned_model(tmp_path):
    """Only the key under `session.shutdown.data.modelMetrics` is renamed; `currentModel` (present on
    the real record, holding the pin) and every `assistant.message.model` are untouched. The reader
    must still name the model from the `modelMetrics` key, never from the pin or `currentModel` --
    otherwise a real model mismatch goes undetected (US-11 clause 3; would feed `views`
    `invalid (model mismatch)` once wired, W1-COP-I)."""
    metrics = _model_metrics()
    renamed = {"renamed-model": metrics["gpt-6-sol"]}
    shutdown = _shutdown(renamed)
    shutdown["data"]["currentModel"] = "gpt-6-sol"  # the pin, untouched by the mutation
    path = _write(tmp_path, [_start(), _user("prompt"), shutdown])
    ex = copilot.read(path)
    assert [c.model for c in ex.model_calls] == ["renamed-model"]
    served = normalize.served_models("native_record", ex, [])
    assert "gpt-6-sol" not in served and served == {"renamed-model"}


def test_us11_an_emptied_modelmetrics_yields_no_model_calls(tmp_path):
    path = _write(tmp_path, [_start(), _user("prompt"), _shutdown({})])
    ex = copilot.read(path)
    assert ex.model_calls == []


# The version gate (F6): fail closed on an unsupported version, or on no session.start -----------------

def test_f6_an_unsupported_version_gates_model_calls_and_hooks(tmp_path):
    path = _write(tmp_path, [_start(version=2), _user("prompt"), _row("hook.start", {"hookType": "x"}),
                              _row("hook.end", {"hookType": "x", "success": True}), _shutdown(_model_metrics())])
    ex = copilot.read(path)
    assert ex.model_calls == [] and (ex.hook_starts, ex.hook_failures) == (None, None)
    assert ("HB-TEL-001", "events.version") in {(m.code, m.field) for m in ex.missing}


def test_f6_no_session_start_gates_model_calls(tmp_path):
    path = _write(tmp_path, [_user("prompt"), _shutdown(_model_metrics())])
    ex = copilot.read(path)
    assert ex.model_calls == []
    assert ("HB-TEL-001", "events.version") in {(m.code, m.field) for m in ex.missing}


def test_f5_no_shutdown_is_hb_tel_001_and_no_model_rows(tmp_path):  # R-15/R-21 pin: wave 1 has no rows here
    path = _write(tmp_path, [_start(), _user("prompt")])
    ex = copilot.read(path)
    assert ex.model_calls == []
    assert ("HB-TEL-001", "session.shutdown") in {(m.code, m.field) for m in ex.missing}


# Reader bounds: F7 arithmetic, F8 a bad bucket type, F9 two models, F10 an over-sized line -------------

def test_f7_an_arithmetic_mismatch_is_hb_tel_001_input_tokens(tmp_path):
    metrics = _model_metrics(uncached=15, cache_read=100, cache_write=10, input_tokens=999)  # 15+100+10 != 999
    path = _write(tmp_path, [_start(), _user("prompt"), _shutdown(metrics)])
    ex = copilot.read(path)
    assert ("HB-TEL-001", "input_tokens") in {(m.code, m.field) for m in ex.missing}
    assert ex.model_calls[0].uncached_input == 15  # the bucket itself is unchanged; only flagged


def test_f8_a_bad_bucket_type_degrades_via_count_not_a_crash(tmp_path):
    metrics = _model_metrics()
    metrics["gpt-6-sol"]["usage"]["outputTokens"] = "five"  # a bad bucket type
    path = _write(tmp_path, [_start(), _user("prompt"), _shutdown(metrics)])
    ex = copilot.read(path)
    call = ex.model_calls[0]
    assert call.output == 0
    assert ("HB-TEL-001", "outputTokens") in {(m.code, m.field) for m in ex.missing}


def test_f9_two_models_in_one_shutdown_are_two_rows_one_ordinal(tmp_path):
    metrics = _model_metrics(model="gpt-6-sol", uncached=1) | _model_metrics(model="claude-sonnet-5", uncached=2)
    path = _write(tmp_path, [_start(), _user("prompt"), _shutdown(metrics)])
    ex = copilot.read(path)
    assert len(ex.model_calls) == 2
    assert {c.model for c in ex.model_calls} == {"claude-sonnet-5", "gpt-6-sol"}  # sorted by key
    assert len({c.native_ordinal for c in ex.model_calls}) == 1  # one shutdown line for both


def test_f10_an_over_sized_system_message_line_is_malformed_not_crashing(tmp_path):  # F10; the MAX_LINE bound (1 MiB)
    huge = _row("system.message", {"role": "system", "content": "x" * (1200 * 1024)})
    path = _write(tmp_path, [_start(), huge, _user("prompt"), _shutdown(_model_metrics())])
    ex = copilot.read(path)
    assert ex.malformed_lines == 1
    assert ex.first_user_text == "prompt" and len(ex.model_calls) == 1  # the rest of the record is read whole


def test_last_shutdown_wins_over_first(tmp_path):
    first = _shutdown(_model_metrics(count=1, uncached=1, cache_read=1, cache_write=1, output=1), ts="2026-01-01T00:05:00.000Z")
    last = _shutdown(_model_metrics(count=9, uncached=9, cache_read=9, cache_write=9, output=9), ts="2026-01-01T00:10:00.000Z")
    path = _write(tmp_path, [_start(), _user("prompt"), first, last])
    ex = copilot.read(path)
    assert len(ex.model_calls) == 1
    call = ex.model_calls[0]
    assert call.requests == 9 and call.uncached_input == 9


# US-14: zero hook denials AND a successful tool call, one named assertion function --------------------

def test_us14_zero_hook_denials_and_a_successful_tool_call():
    off_ex = copilot.read(OFF)
    off_rows = normalize.tool_call_rows("r1", "c1", off_ex.session_id, off_ex, "x")
    assert copilot.us14_valid(off_rows) is True

    on_ex = copilot.read(ON)  # the revision-92 negative control: 8/8 denied
    on_rows = normalize.tool_call_rows("r1", "c1", on_ex.session_id, on_ex, "x")
    assert copilot.us14_valid(on_rows) is False


def test_us14_no_tool_calls_at_all_is_not_valid_by_default():  # R-27 c1: the positive control
    assert copilot.us14_valid([]) is False


# Bounds: the shared MAX_LINE/MAX_FILE caps apply unchanged to the Copilot reader -----------------------

def test_a_newline_free_copilot_record_is_read_in_bounded_memory(tmp_path, monkeypatch):
    import tracemalloc

    from harness_bench import telemetry

    monkeypatch.setattr(telemetry, "MAX_LINE", 1024)
    d = tmp_path / "session-state" / "sid1"
    d.mkdir(parents=True)
    path = d / "events.jsonl"
    path.write_bytes(b"x" * (8 << 20) + b"\n" + json.dumps(_start(session_id="sid1")).encode() + b"\n")
    tracemalloc.start()
    try:
        ex = copilot.read(path)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 1 << 20, f"peak {peak} bytes for an 8 MiB line"
    assert ex.malformed_lines == 1 and ex.session_id == "sid1"
