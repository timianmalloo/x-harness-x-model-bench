"""R-READ-CC: the Claude Code reader's four ADR-0026 s1 hooks, read through the normalize row builders.

Fixtures (scrubbed real turns of the pinned build: Claude Code 2.1.282, claude-agent-acp 0.81.2, SDK 0.3.282):
- `rerun-1m-settings*`: the settings spike (2026-10-11), `ANTHROPIC_MODEL=claude-opus-5-5[1m]`, effort high, thinking
  display `summarized`, copied-credential login. Served the 1M model.
- `rerun-x1-packon*`: one pack-on X1 turn (2026-10-12), the same settings, `CLAUDE_CODE_OAUTH_TOKEN` login. The
  adapter's model menu offered `opus`, not `opus[1m]`; its in-turn usage_updates say 200,000 (the adapter's
  seed) and its post-result one 1,000,000 (the authoritative window; PROBE-FIX-2 D).
Each `-acp.jsonl` holds the turn's inbound ACP usage_update notifications and its prompt result, one JSON-RPC message
per line."""

from __future__ import annotations

import json
from pathlib import Path

from harness_bench import views
from harness_bench.telemetry import claude_code, normalize

FIX = Path(__file__).parent / "fixtures" / "claude"
ONE_M, PACK_ON = FIX / "rerun-1m-settings.jsonl", FIX / "rerun-x1-packon.jsonl"
ARGS = ("run", "cell", "sid")


def _acp(path: Path) -> Path:
    return path.with_name(path.stem + "-acp.jsonl")


def _read(path: Path):
    return claude_code.read(path, acp=_acp(path))


def _served(path: Path) -> dict[tuple[str, str | None], list]:
    out: dict[tuple[str, str | None], list] = {}
    for row in normalize.served_rows(*ARGS, _read(path), "x"):
        out.setdefault((row["field"], row["source"]), []).append(row["value"] if row["value"] is not None else row["not_recorded"])
    return out


def _acp_output_total(path: Path) -> int:
    for line in _acp(path).read_text(encoding="utf-8").splitlines():
        msg = json.loads(line)
        if "stopReason" in (msg.get("result") or {}):
            return msg["result"]["usage"]["outputTokens"]
    raise AssertionError("no prompt result in the ACP fixture")


# --- served (ADR-0024 s4) -----------------------------------------------------------------------------------------

def test_served_reads_effort_model_and_the_acp_context_size_each_with_its_source():
    served = _served(ONE_M)
    assert served[("effort", "transcript:assistant.effort")] == ["high"]
    assert served[("model_served", "transcript:attachment.identity.modelId")] == ["claude-opus-5-5[1m]"]
    assert served[("context_tokens", "acp:usage_update.size")] == [1_000_000]


def test_only_the_post_result_size_is_a_served_context_row():
    # PROBE-FIX-2 D (a): the in-turn 200k sizes are the adapter's seed; the usage_update before the prompt result
    # carries result.modelUsage.contextWindow, the authoritative window (claude_code._authoritative)
    served = _served(PACK_ON)
    assert served[("model_served", "transcript:attachment.identity.modelId")] == ["claude-opus-5-5"]
    assert served[("context_tokens", "acp:usage_update.size")] == [1_000_000]


def test_a_source_showing_two_context_sizes_writes_both_so_the_view_refuses_them(tmp_path):
    # two turns whose post-result updates disagree (PROBE-FIX-2 D: a genuine disagreement, never a seed)
    def update(size):
        return {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "s", "update": {
            "sessionUpdate": "usage_update", "used": 900, "size": size}}}
    end = {"jsonrpc": "2.0", "id": 3, "result": {"stopReason": "end_turn"}}
    acp = tmp_path / "two-acp.jsonl"
    acp.write_text("".join(json.dumps(m) + "\n" for m in (update(200_000), end, update(1_000_000), end)), encoding="utf-8")
    rows = [r for r in normalize.served_rows(*ARGS, claude_code.read(ONE_M, acp=acp), "x")
            if r["field"] == "context_tokens" and r["value"] is not None]
    assert [r["value"] for r in rows] == [200_000, 1_000_000]


def test_without_an_acp_record_the_context_size_is_not_recorded_never_a_guess():
    rows = normalize.served_rows(*ARGS, claude_code.read(ONE_M), "x")
    ctx = [r for r in rows if r["field"] == "context_tokens"]
    assert [(r["value"], r["not_recorded"]) for r in ctx] == [(None, "not recorded: the transcript does not record the context size")]


# --- reasoning ----------------------------------------------------------------------------------------------------

def test_a_thinking_block_is_a_summary_row_with_its_text_as_stored():
    ex = claude_code.read(ONE_M)
    rows = normalize.reasoning_rows(*ARGS, ex, "x")
    assert [r["source_kind"] for r in rows] == ["summary"]
    text = rows[0]["text"]
    assert text and rows[0]["chars"] == len(text)
    raw = [json.loads(line) for line in ONE_M.read_text(encoding="utf-8").splitlines()]
    stored = [b["thinking"] for r in raw if r.get("type") == "assistant" for b in r["message"]["content"] if b.get("type") == "thinking"]
    assert stored == [text]
    assert rows[0]["native_ordinal"] in {c.native_ordinal for c in ex.model_calls}  # keyed by its request


# --- per-request model_calls (ADR-0026 s2) ------------------------------------------------------------------------

def test_model_calls_are_one_per_request_id_and_sum_to_the_acp_output_total():
    for path in (ONE_M, PACK_ON):
        ex = claude_code.read(path)
        raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        request_ids = {r["requestId"] for r in raw if r.get("type") == "assistant" and r.get("requestId")}
        assert len(ex.model_calls) == len(request_ids)
        assert sum(c.output for c in ex.model_calls) == _acp_output_total(path)


# --- the five Flagged sources (ADR-0026 s1) -------------------------------------------------------------------------

def _parts(path: Path) -> list[dict]:
    return normalize.prompt_part_rows(*ARGS, claude_code.read(path), "x")


def test_flagged_1_instruction_files_from_the_instructions_attachment():
    files = [(p["part"], p["path"], p["delivery"]) for p in _parts(PACK_ON) if p["part"] in ("instruction_file", "agents_md")]
    assert files == [("instruction_file", "CLAUDE.md", "inlined"), ("agents_md", "AGENTS.md", "inlined")]
    assert [p for p in _parts(ONE_M) if p["part"] in ("instruction_file", "agents_md")] == []  # no instruction file there


def test_flagged_2_system_prompt_and_tools_from_the_prompt_snapshot():
    parts = {p["part"]: p for p in _parts(PACK_ON)}
    raw = [json.loads(line) for line in PACK_ON.read_text(encoding="utf-8").splitlines()]
    snaps = [r["attachment"] for r in raw if (r.get("attachment") or {}).get("type") == "prompt_snapshot"]
    assert parts["system"]["chars"] == sum(len(s) for s in snaps[0]["systemPrompt"])
    tools = next(s["tools"] for s in snaps if s.get("tools"))
    assert parts["tools"]["chars"] == len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")))
    assert parts["skills"]["delivery"] == "listed" and parts["skills"]["chars"] > 0


def test_flagged_3_stop_hooks_from_the_stop_hook_summary_row():
    events = normalize.harness_event_rows(*ARGS, claude_code.read(PACK_ON), "x")
    hooks = [e for e in events if e["event"] == "hook"]
    assert [e["name"].split()[-5] for e in hooks] == ["heartbeat.py", "owner-review-gate.py"]
    assert {e["ok"] for e in hooks} == {1}
    assert len({e["native_ordinal"] for e in events}) == len(events)  # DR1: identical events never share a key


def test_flagged_4_a_skill_load_is_a_skill_tool_call(tmp_path):
    rows = [{"type": "assistant", "requestId": "req_1", "timestamp": "t1", "message": {"id": "m1", "model": "claude-opus-5-5",
             "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
             "content": [{"type": "tool_use", "id": "toolu_1", "name": "Skill", "input": {"skill": "implement"}}]}},
            {"type": "user", "timestamp": "t2", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_1"}]}}]
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    events = normalize.harness_event_rows(*ARGS, claude_code.read(path), "x")
    assert [(e["event"], e["name"], e["start"], e["end"], e["ok"]) for e in events] == [("skill_load", "implement", "t1", "t2", 1)]
    assert [e for e in normalize.harness_event_rows(*ARGS, claude_code.read(PACK_ON), "x") if e["event"] == "skill_load"] == []


def test_flagged_5_no_compaction_row_in_a_one_turn_record():
    events = normalize.harness_event_rows(*ARGS, claude_code.read(PACK_ON), "x")
    assert [e for e in events if e["event"] == "compaction"] == []


# --- J1A-FIX items 22 and 23: the context size from the cell home's ACP timeline; reasoning tokens per request -------

def _cell_home(tmp_path: Path, sizes: list[int] | None) -> Path:
    """ONE_M laid out as a cell home holds it: home/projects/<slug>/<session>.jsonl, the driver's timeline at home."""
    record = tmp_path / "home" / "projects" / "C--cells-a-ws" / "s.jsonl"
    record.parent.mkdir(parents=True)
    record.write_bytes(ONE_M.read_bytes())
    if sizes is not None:
        lines = [{"first_mono_ns": 1, "last_mono_ns": 1, "count": 1, "method": "session/prompt", "update_kind": "sent",
                  "tool_call_id": None}]
        for s in sizes:  # PROBE-FIX-2 D (a): each size is a turn's post-result update, right before its prompt response
            lines += [{"first_mono_ns": 2, "last_mono_ns": 3, "count": 2, "method": "session/update",
                       "update_kind": "usage_update", "tool_call_id": None, "used": 900, "size": s},
                      {"first_mono_ns": 4, "last_mono_ns": 4, "count": 1, "method": "session/prompt",
                       "update_kind": "response", "tool_call_id": None}]
        (tmp_path / "home" / "acp-timeline.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return record


def _context_rows(record: Path) -> list[dict]:
    return [r for r in normalize.served_rows(*ARGS, claude_code.read(record), "x") if r["field"] == "context_tokens"]


def test_the_served_context_size_is_read_from_the_cell_homes_acp_timeline(tmp_path):
    rows = _context_rows(_cell_home(tmp_path, [1_000_000]))
    assert [(r["value"], r["source"]) for r in rows if r["value"] is not None] == [
        (1_000_000, "acp-timeline.jsonl:usage_update.size@2")]


def test_without_a_timeline_beside_the_record_the_context_size_is_not_recorded(tmp_path):
    rows = _context_rows(_cell_home(tmp_path, None))
    assert [(r["value"], r["not_recorded"]) for r in rows] == [
        (None, "not recorded: the transcript does not record the context size")]


def test_two_timeline_sizes_are_two_served_rows_and_the_disagreement_is_hb_val_010(tmp_path):
    rows = [r for r in _context_rows(_cell_home(tmp_path, [200_000, 1_000_000])) if r["value"] is not None]
    assert [r["value"] for r in rows] == [200_000, 1_000_000] and len({r["source"] for r in rows}) == 2
    cell = {"cell_id": "a", "harness": "claude-code", "model": "claude-opus-5-5", "effort": "default", "context": "default"}
    prof = {"auxiliary_models": [], "settings": {"context": {"default_serves": 200000}, "effort": {}}}
    finding, _ = views._served_settings(cell, prof, rows)
    assert finding is not None and finding.code == "HB-VAL-010" and "1000000" in finding.message


def test_model_call_reasoning_is_the_requests_thinking_tokens():  # usage.output_tokens_details.thinking_tokens
    assert [c.reasoning for c in claude_code.read(PACK_ON).model_calls] == [34, 0, 367, 0, 10, 31, 80]
    assert [c.reasoning for c in claude_code.read(ONE_M).model_calls] == [0, 98]


# --- C3 / C5 (plan 2026-10-14): ceremony text and tool-result bytes in `tool_inputs` ----------------------------------

def _assistant(mid, *blocks, model="claude-opus-5-5"):
    return {"type": "assistant", "message": {"id": mid, "model": model, "usage": {}, "content": list(blocks)}}


def _result(*results):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": content, **extra} for tid, content, extra in results]}}


def test_tool_inputs_counts_visible_text_only_and_sizes_each_result_by_its_text(tmp_path):
    use = lambda tid: {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": "x"}}
    rows = [
        _assistant("m1", {"type": "thinking", "thinking": "hidden hidden"}),
        _assistant("m2", {"type": "text", "text": "Goal: é"}, use("t1")),  # 7 chars, 8 bytes
        _result(("t1", "out é", {})),  # a string result: its UTF-8 size, 6 bytes
        _assistant("m3", use("t2")),
        _result(("t2", [{"type": "text", "text": "ab"}, {"type": "text", "text": "cd"}], {})),  # text parts summed: 4
        _assistant("m4", use("t3")),
        _result(("t3", [{"type": "tool_reference", "tool_name": "X"}], {})),  # no text to size: not recorded
        _assistant("m5", {"type": "text", "text": "  "}),  # blank text is not a message
        _assistant("m6", {"type": "text", "text": "synthetic"}, model="<synthetic>"),  # not the model's output
        _assistant("m7", use("t4")),  # no result row (killed turn): not recorded
        _assistant("m8", {"type": "text", "text": "Done."}),  # 5 chars
    ]
    record = tmp_path / "s.jsonl"
    record.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    trace = claude_code.tool_inputs(record)
    assert (trace.assistant_chars, trace.assistant_messages) == (7 + 5, 2)
    assert [c.bytes_returned for c in trace.calls] == [6, 4, None, None]


def test_tool_inputs_text_count_is_not_recorded_when_the_record_lost_lines(tmp_path):
    record = tmp_path / "s.jsonl"
    record.write_text(json.dumps(_assistant("m1", {"type": "text", "text": "hi"})) + "\n{not json\n", encoding="utf-8")
    trace = claude_code.tool_inputs(record)
    assert (trace.assistant_chars, trace.assistant_messages) == (None, None)
