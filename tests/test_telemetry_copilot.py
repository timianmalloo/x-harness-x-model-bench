"""Copilot telemetry reader (design docs/design/phase2-copilot-profile.md section 4.4; the section 13
promise-to-test table rows owned by W1-COP-R). Golden fixtures: `tests/fixtures/native/copilot/{off,on}`
(`9c6c615`, rescrubbed `f952f87`); `on/` is now the revision-95 pack-on recapture (R-27 c3, W1-CAP2 phase B)
-- the revision-92 sample moved to `on-rev92/` and is kept as the negative control (8 denied tool calls,
8/8 hook failures, us14_valid False)."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from harness_bench import profiles
from harness_bench.telemetry import copilot, normalize

FIX = Path(__file__).parent / "fixtures"
COPILOT_FIX = FIX / "native" / "copilot"
OFF = next((COPILOT_FIX / "off").rglob("events.jsonl"))
ON = next((COPILOT_FIX / "on").rglob("events.jsonl"))  # revision-95 pack-on recapture (R-27 c3)
ON_REV92 = next((COPILOT_FIX / "on-rev92").rglob("events.jsonl"))  # revision-92 pack-on (negative control)
PROVENANCE = json.loads((COPILOT_FIX / "provenance.json").read_text(encoding="utf-8"))

# provenance.json: capture.prompt_sha256 (the same prompt both arms; tasks/X1/prompt.md's own hash)
PROMPT_SHA256 = PROVENANCE["capture"]["prompt_sha256"]


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


def _load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _system_message_markers(path: Path) -> list[str]:
    """The scrubbed `system.message` line's own `markers=[...]` annotation (`scrub_sample.py`): a
    fixture-provenance fact, never a US-9 proof (design section 13)."""
    content = next(r["data"]["content"] for r in _load_events(path) if r["type"] == "system.message")
    match = re.search(r"markers=(\[.*\])>", content)
    assert match, "no scrub annotation on system.message"
    return ast.literal_eval(match.group(1))


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


def test_on_yields_one_row_per_model_in_the_last_shutdown_with_requests():  # rev-95 (R-27 c3)
    ex = copilot.read(ON)
    assert len(ex.model_calls) == 1
    call = ex.model_calls[0]
    assert call.model == "gpt-6-sol" and call.requests == 9 and (call.start, call.end) == (None, None)
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output, call.reasoning) == (27, 787795, 102909, 1778, 545)
    assert ex.missing == []


def test_on_rev92_yields_one_row_per_model_in_the_last_shutdown_with_requests():  # negative control
    ex = copilot.read(ON_REV92)
    assert len(ex.model_calls) == 1
    call = ex.model_calls[0]
    assert call.model == "gpt-6-sol" and call.requests == 6 and (call.start, call.end) == (None, None)
    assert (call.uncached_input, call.cache_read, call.cache_write, call.output, call.reasoning) == (18, 439386, 88237, 525, 170)
    assert ex.missing == []


@pytest.mark.parametrize("arm, path", [("off", OFF), ("on", ON)])
def test_golden_sample_cross_check_against_the_acp_usage_oracle(arm, path):  # R-26 C3
    """Σ(uncached, cache_read, cache_write, output) == the independent oracle's ACP usage.totalTokens,
    read from provenance.json's own `facts.<arm>.acp_prompt_usage.totalTokens` (never a hardcoded
    number, so a re-capture can't silently drift from what this test checks); reasoning is a
    component of output and is not added."""
    total_tokens = PROVENANCE["facts"][arm]["acp_prompt_usage"]["totalTokens"]
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
    assert (copilot.read(ON_REV92).hook_starts, copilot.read(ON_REV92).hook_failures) == (8, 8)


def test_on_rev95_hooks_all_succeeded():  # R-27 c3: 27 hook.end, all success
    assert (copilot.read(ON).hook_starts, copilot.read(ON).hook_failures) == (27, 0)


def test_claude_code_and_codex_extractions_never_set_hook_fields():
    from harness_bench.telemetry import claude_code

    ex = claude_code.read(FIX / "native/claude-code/ok.jsonl")
    assert (ex.hook_starts, ex.hook_failures) == (None, None)


def test_off_tool_calls_succeed_and_on_rev92_are_all_denied():
    off = copilot.read(OFF).tool_calls
    assert len(off) == 6 and all((t.ok, t.outcome_code) == (True, None) for t in off)
    on92 = copilot.read(ON_REV92).tool_calls
    assert len(on92) == 8 and all((t.ok, t.outcome_code) == (False, "denied") for t in on92)
    assert {t.name for t in on92} == {"skill", "glob", "powershell", "view", "rg"}
    assert next(t.tool_class for t in on92 if t.name == "skill") == "other"  # C: skill is other (design 4.4)


def test_on_rev95_tool_calls_are_16_success_and_1_ordinary_failure_not_denied():  # R-27 c3
    on = copilot.read(ON).tool_calls
    assert len(on) == 17
    assert sum((t.ok, t.outcome_code) == (True, None) for t in on) == 16
    failed = [t for t in on if not t.ok]
    assert len(failed) == 1 and failed[0].outcome_code == "failure" and failed[0].outcome_code != "denied"
    assert sum(t.outcome_code == "denied" for t in on) == 0
    assert any(t.name == "apply_patch" for t in on)


def test_r14c1_skill_tool_calls_requested_on_rev92_none_off():  # R-14 c1: skill calls, derived from tool_calls
    assert sum(t.name == "skill" for t in copilot.read(ON_REV92).tool_calls) == 2
    assert not any(t.name == "skill" for t in copilot.read(OFF).tool_calls)


@pytest.mark.parametrize("name, cls", [
    ("powershell", "shell"), ("bash", "shell"), ("shell", "shell"), ("apply_patch", "edit"), ("write", "edit"),
    ("edit", "edit"), ("create", "edit"), ("view", "read"), ("glob", "read"), ("rg", "read"), ("grep", "read"),
    ("skill", "other"), ("some-unknown-tool", "other"),
])
def test_tool_class_mapping(name, cls):  # TA8
    assert copilot._tool_class(name) == cls


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
    """The real `off` record, with only the key under `session.shutdown.data.modelMetrics` renamed.
    `currentModel` (real, holding the pin `gpt-6-sol`), `session.start.data.selectedModel` and every
    `assistant.message.model` are untouched. The reader must still name the model from the
    `modelMetrics` key, never from the pin or `currentModel` -- otherwise a real model mismatch goes
    undetected (US-11 clause 3; would feed `views` `invalid (model mismatch)` once wired, W1-COP-I)."""
    events = _load_events(OFF)
    for row in events:
        if row["type"] == "session.shutdown":
            row["data"]["modelMetrics"] = {"renamed-model": row["data"]["modelMetrics"].pop("gpt-6-sol")}
            assert row["data"]["currentModel"] == "gpt-6-sol"  # untouched by the mutation
    path = _write(tmp_path, events)
    ex = copilot.read(path)
    assert [c.model for c in ex.model_calls] == ["renamed-model"]
    served = normalize.served_models("native_record", ex, [])
    assert "gpt-6-sol" not in served and served == {"renamed-model"}
    assert not profiles.model_allowed("renamed-model", "gpt-6-sol", [])


def test_us11_an_emptied_modelmetrics_yields_no_model_calls(tmp_path):
    path = _write(tmp_path, [_start(), _user("prompt"), _shutdown({})])
    ex = copilot.read(path)
    assert ex.model_calls == []


# The version gate (F6): fail closed on an unsupported version, or on no session.start -----------------

@pytest.mark.parametrize("version", [2, True, 1.0], ids=["unsupported-int", "bool-true", "float-one"])
def test_f6_an_unsupported_or_wrongly_typed_version_gates_model_calls_and_hooks(tmp_path, version):
    # `True`/`1.0` are the Minor: `== 1` (or a bare `in {1}`) would wrongly accept them since
    # `bool` is an `int` subclass and `1.0 == 1`; the gate requires `type(version) is int`.
    path = _write(tmp_path, [_start(version=version), _user("prompt"), _row("hook.start", {"hookType": "x"}),
                              _row("hook.end", {"hookType": "x", "success": True}), _shutdown(_model_metrics())])
    ex = copilot.read(path)
    assert ex.model_calls == [] and (ex.hook_starts, ex.hook_failures) == (None, None)
    assert ("HB-TEL-001", "events.version") in {(m.code, m.field) for m in ex.missing}


def test_f6_an_unhashable_version_does_not_crash(tmp_path):  # T-TEL-fuzz D2 regression: version=[1]
    path = _write(tmp_path, [_start(version=[1]), _user("prompt"), _shutdown(_model_metrics())])
    ex = copilot.read(path)  # must not raise TypeError: unhashable type: 'list'
    assert ex.model_calls == []
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


def test_a_single_request_report_takes_the_shutdown_timestamp(tmp_path):  # TA2
    """`start`/`end` are set only for a single-request report (`requests == 1`), from the shutdown
    row's own timestamp -- Copilot keeps no per-call clock, so a multi-request report's model time
    stays NOT_RECORDED (design section 3, and the golden-sample tests above)."""
    shutdown = _shutdown(_model_metrics(count=1), ts="2026-01-01T00:12:34.000Z")
    path = _write(tmp_path, [_start(), _user("prompt"), shutdown])
    ex = copilot.read(path)
    call = ex.model_calls[0]
    assert call.requests == 1
    assert call.start == call.end == "2026-01-01T00:12:34.000Z"


def test_session_id_falls_back_to_the_session_state_directory_name(tmp_path):  # design section 4.4
    path = _write(tmp_path, [_row("session.start", {"version": 1}), _user("prompt"), _shutdown(_model_metrics())],
                  session_id="dir-sid")
    assert copilot.read(path).session_id == "dir-sid"


def test_fixture_provenance_system_message_markers():  # design section 13: a provenance fact, not a US-9 proof
    assert _system_message_markers(OFF) == []
    assert _system_message_markers(ON) == ["AI-Forward Pack", "Agent Knowledge Pack", "Rigor Protocol"]


def test_model_call_and_tool_call_rows_carry_requests_and_outcome_code():  # TA9, TA10
    off_ex = copilot.read(OFF)
    model_rows = normalize.model_call_rows("r1", "c1", off_ex.session_id, off_ex, "x")
    assert model_rows[0]["requests"] == 5  # a pre-amendment reader's `.get("requests", 1)` would under-count 5x

    on92_ex = copilot.read(ON_REV92)  # the revision-92 negative control: 8/8 denied
    on92_rows = normalize.tool_call_rows("r1", "c1", on92_ex.session_id, on92_ex, "x")
    assert sum(r["outcome_code"] == "denied" for r in on92_rows) == 8


# The toolCallId correlation, and outcome_code null on success (Codex cross-vendor review F1/F2) --------

def test_tool_calls_pair_by_toolcallid_even_when_completions_are_out_of_order(tmp_path):  # F1
    events = [
        _start(), _user("prompt"),
        _row("tool.execution_start", {"toolCallId": "A", "toolName": "glob"}, ts="2026-01-01T00:00:01.000Z"),
        _row("tool.execution_start", {"toolCallId": "B", "toolName": "view"}, ts="2026-01-01T00:00:02.000Z"),
        _row("tool.execution_complete", {"toolCallId": "B", "success": True}, ts="2026-01-01T00:00:03.000Z"),
        _row("tool.execution_complete", {"toolCallId": "A", "success": True}, ts="2026-01-01T00:00:04.000Z"),
        _shutdown(_model_metrics()),
    ]
    path = _write(tmp_path, events)
    ex = copilot.read(path)
    assert len(ex.tool_calls) == 2  # nothing left open
    calls = {t.name: t for t in ex.tool_calls}
    assert (calls["glob"].start, calls["glob"].end) == ("2026-01-01T00:00:01.000Z", "2026-01-01T00:00:04.000Z")
    assert (calls["view"].start, calls["view"].end) == ("2026-01-01T00:00:02.000Z", "2026-01-01T00:00:03.000Z")


def test_outcome_code_is_null_on_success_even_with_a_stale_error_code(tmp_path):  # F2
    events = [
        _start(), _user("prompt"),
        _row("tool.execution_start", {"toolCallId": "A", "toolName": "glob"}, ts="2026-01-01T00:00:01.000Z"),
        _row("tool.execution_complete", {"toolCallId": "A", "success": True, "error": {"code": "stale"}},
             ts="2026-01-01T00:00:02.000Z"),
        _shutdown(_model_metrics()),
    ]
    path = _write(tmp_path, events)
    ex = copilot.read(path)
    assert (ex.tool_calls[0].ok, ex.tool_calls[0].outcome_code) == (True, None)


# US-14: zero hook denials AND a successful tool call, one named assertion function --------------------

def test_us14_zero_hook_denials_and_a_successful_tool_call():
    off_ex = copilot.read(OFF)
    off_rows = normalize.tool_call_rows("r1", "c1", off_ex.session_id, off_ex, "x")
    assert copilot.us14_valid(off_rows) is True

    on92_ex = copilot.read(ON_REV92)  # the revision-92 negative control: 8/8 denied
    on92_rows = normalize.tool_call_rows("r1", "c1", on92_ex.session_id, on92_ex, "x")
    assert copilot.us14_valid(on92_rows) is False


def test_us14_valid_on_rev95_pack_on_zero_denials_and_a_successful_tool_call():  # R-27 c3
    on_ex = copilot.read(ON)
    on_rows = normalize.tool_call_rows("r1", "c1", on_ex.session_id, on_ex, "x")
    assert copilot.us14_valid(on_rows) is True


def test_us14_no_tool_calls_at_all_is_not_valid_by_default():  # R-27 c1: the positive control
    assert copilot.us14_valid([]) is False


def test_us14_one_denial_among_successes_is_not_valid(tmp_path):  # TA1, TA9 (R-27 c2: BOTH halves matter)
    """A cell can have a successful tool call AND a denied one at the same time (a real cell is not
    all-or-nothing): the zero-denial half of `us14_valid` must fail it on its own -- the positive
    control (>=1 `ok==1`) is not enough by itself."""
    events = [
        _start(), _user("prompt"),
        _row("tool.execution_start", {"toolCallId": "ok-1", "toolName": "glob"}, ts="2026-01-01T00:00:01.000Z"),
        _row("tool.execution_complete", {"toolCallId": "ok-1", "success": True}, ts="2026-01-01T00:00:02.000Z"),
        _row("tool.execution_start", {"toolCallId": "denied-1", "toolName": "write"}, ts="2026-01-01T00:00:03.000Z"),
        _row("tool.execution_complete", {"toolCallId": "denied-1", "success": False, "error": {"code": "denied"}},
             ts="2026-01-01T00:00:04.000Z"),
        _shutdown(_model_metrics()),
    ]
    path = _write(tmp_path, events)
    ex = copilot.read(path)
    rows = normalize.tool_call_rows("r1", "c1", ex.session_id, ex, "x")
    assert any(r["ok"] == 1 for r in rows) and any(r["outcome_code"] == "denied" for r in rows)
    assert copilot.us14_valid(rows) is False


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
