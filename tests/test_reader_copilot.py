"""R-READ-COPILOT: the Copilot reader's four fact streams and per-request rows (ADR-0026 s1-2, ADR-0024 s4).

Fixtures `tests/fixtures/copilot/rerun-{off,on}` are R-COPILOT-P's real `copilot -p` X1 turns (pack-off, pack-on;
gpt-6.1-sol, effort high, `--context long_context`, `--log-level debug`); `rerun-fast` is the settings spike's
gpt-5.6-sol-fast session (ACP mode, debug log). Built and scrubbed by the builder named in
`rerun-provenance.json`, which also states what was trimmed. Reasoning and hooks come from the committed
`native/copilot/{on,on-rev92}` records (the -p records fired no hooks)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from harness_bench import telemetry
from harness_bench.telemetry import copilot, normalize

FIX = Path(__file__).parent / "fixtures"
RERUN = FIX / "copilot"


def _record(root: Path) -> Path:
    return next((root / "home" / "session-state").glob("*/events.jsonl"))


OFF, ON, FAST = (_record(RERUN / f"rerun-{arm}") for arm in ("off", "on", "fast"))
NATIVE_ON = next((FIX / "native" / "copilot" / "on").rglob("events.jsonl"))
NATIVE_REV92 = next((FIX / "native" / "copilot" / "on-rev92").rglob("events.jsonl"))
SESSION = "events.jsonl:session.start"
DEBUG = "debug-log"


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _shutdown(path: Path) -> dict:
    return [e for e in _events(path) if e.get("type") == "session.shutdown"][-1]["data"]["modelMetrics"]


def _served(ex: telemetry.Extraction) -> dict[tuple[str, str | None], tuple]:
    assert isinstance(ex.served, tuple), ex.served  # one ServedSettings per source
    rows = normalize.served_rows("r", "c", "s", ex, "x")
    return {(r["field"], r["source"]): (r["value"], r["not_recorded"]) for r in rows}


def _record_only(tmp_path: Path, src: Path, edit=None) -> Path:
    """The session record alone, in a cell home with no debug log; `edit` rewrites the events first."""
    dest = tmp_path / "home" / "session-state" / src.parent.name / "events.jsonl"
    dest.parent.mkdir(parents=True)
    if edit is None:
        shutil.copyfile(src, dest)
    else:
        dest.write_text("".join(json.dumps(edit(e)) + "\n" for e in _events(src)), encoding="utf-8")
    return dest


# --- 1. served settings from the -p session record ---------------------------------------------------------------

def test_served_settings_from_the_p_session_record():
    served = _served(copilot.read(OFF))
    assert served[("model_served", f"{SESSION}.selectedModel")] == ("gpt-6.1-sol", None)
    assert served[("effort", f"{SESSION}.reasoningEffort")] == ("high", None)
    assert served[("context_tier", f"{SESSION}.contextTier")] == ("long_context", None)
    value, reason = served[("context_tokens", f"{SESSION}")]
    assert value is None and reason.startswith("not recorded: ")  # -p judges the window by tier; no usage_update.size


def test_a_null_context_tier_is_a_measured_null_and_an_absent_one_is_not_recorded(tmp_path):
    # seam from R-VALIDITY: null -> value None, not_recorded None (HB-VAL-010); absent -> a reason (HB-VAL-011)
    assert _served(copilot.read(FAST))[("context_tier", f"{SESSION}.contextTier")] == (None, None)

    def drop_tier(e):
        if e.get("type") == "session.start":
            e["data"].pop("contextTier")
        return e
    value, reason = _served(copilot.read(_record_only(tmp_path, OFF, drop_tier)))[("context_tier", f"{SESSION}.contextTier")]
    assert value is None and reason == "not recorded: session.start carries no contextTier"


# --- 2. Sol Fast: model_api from the debug log's response model ---------------------------------------------------

def test_sol_fast_is_served_with_model_api_from_the_debug_log_response():
    served = _served(copilot.read(FAST))
    assert served[("model_served", f"{SESSION}.selectedModel")] == ("gpt-5.6-sol-fast", None)
    assert served[("model_api", f"{DEBUG}:response.model")] == ("gpt-5.6-sol", None)
    assert served[("model_served", f"{DEBUG}:request.model")] == ("gpt-5.6-sol-fast", None)


def test_without_the_debug_log_model_api_is_not_recorded(tmp_path):
    served = _served(copilot.read(_record_only(tmp_path, FAST)))
    value, reason = served[("model_api", f"{SESSION}")]
    assert value is None and reason == "not recorded: no debug process log in the cell home"
    assert not any(source and source.startswith(DEBUG) for _, source in served)


# --- 3. per-request model_calls from the debug log ----------------------------------------------------------------

def _totals(calls) -> tuple:
    return tuple(sum(getattr(c, k) for c in calls) for k in ("uncached_input", "cache_read", "cache_write", "output", "reasoning"))


def _metric_totals(metrics: dict) -> tuple:
    usage = metrics["usage"]
    return (metrics["tokenDetails"]["input"]["tokenCount"], usage["cacheReadTokens"], usage["cacheWriteTokens"],
            usage["outputTokens"], usage["reasoningTokens"])


def test_per_request_rows_from_the_debug_log_sum_to_the_session_total():
    for record, n in ((OFF, 5), (ON, 12)):
        ex = copilot.read(record)
        metrics = _shutdown(record)["gpt-6.1-sol"]
        assert len(ex.model_calls) == n == metrics["requests"]["count"]
        assert {(c.model, c.requests) for c in ex.model_calls} == {("gpt-6.1-sol", 1)}
        assert _totals(ex.model_calls) == _metric_totals(metrics)
        lines = [i for i, e in enumerate(_events(record), 1) if e.get("type") == "assistant.message"]
        assert [c.native_ordinal for c in ex.model_calls] == lines  # keyed by the message whose apiCallId is the response id
        assert all(c.start and c.end and c.start <= c.end for c in ex.model_calls)  # the log's own request/response stamps
        assert not ex.missing


def test_off_per_request_buckets_are_the_logged_usage():
    first = copilot.read(OFF).model_calls[0]  # prompt 6207, cached 0, cache_write 6204, completion 98, reasoning 0
    assert (first.uncached_input, first.cache_read, first.cache_write, first.output, first.reasoning) == (3, 0, 6204, 98, 0)


def test_without_the_debug_log_the_rows_are_the_per_session_totals(tmp_path):
    ex = copilot.read(_record_only(tmp_path, OFF))
    assert [(c.model, c.requests, c.start, c.end) for c in ex.model_calls] == [("gpt-6.1-sol", 5, None, None)]
    assert _totals(ex.model_calls) == _metric_totals(_shutdown(OFF)["gpt-6.1-sol"])


def test_a_debug_log_that_does_not_sum_to_the_session_total_falls_back_to_it(tmp_path):
    home = RERUN / "rerun-off" / "home"
    record = _record_only(tmp_path, OFF)
    log = next((home / "logs").glob("process-*.log"))
    text = log.read_text(encoding="utf-8")
    cut = text.rfind("[rust:model_wire] Wire request: ")  # drop the last request and its response
    (tmp_path / "home" / "logs").mkdir()
    (tmp_path / "home" / "logs" / log.name).write_text(text[:text.rfind("\n", 0, cut) + 1], encoding="utf-8")
    assert [(c.requests, c.start) for c in copilot.read(record).model_calls] == [(5, None)]


# --- 4. reasoning --------------------------------------------------------------------------------------------------

def test_reasoning_rows_of_kind_summary_carry_the_reasoning_text():
    ex = copilot.read(NATIVE_ON)
    assert isinstance(ex.reasoning, list), ex.reasoning
    texts = [(n, e["data"]["reasoningText"]) for n, e in enumerate(_events(NATIVE_ON), 1)
             if e.get("type") == "assistant.message" and e["data"].get("reasoningText")]
    summaries = [r for r in ex.reasoning if r.source_kind == "summary"]
    assert len(texts) == 6  # 8 messages carry the key; 2 hold "" and are encrypted-only items, never empty summaries
    assert [(r.native_ordinal, r.text, r.chars) for r in summaries] == [(n, t, len(t)) for n, t in texts]
    rows = normalize.reasoning_rows("r", "c", "s", ex, "x")
    assert {r["source_kind"] for r in rows} <= {"summary", "encrypted-only"}


def test_reasoning_tokens_come_from_the_debug_log_and_opaque_items_are_hashed():
    ex = copilot.read(ON)
    assert isinstance(ex.reasoning, list), ex.reasoning
    by_line = {c.native_ordinal: c.reasoning for c in ex.model_calls}
    assert ex.reasoning and all(r.reasoning_tokens == by_line[r.native_ordinal] for r in ex.reasoning)
    assert sum(r.reasoning_tokens for r in ex.reasoning) == _shutdown(ON)["gpt-6.1-sol"]["usage"]["reasoningTokens"]
    opaque = [r for r in ex.reasoning if r.source_kind == "encrypted-only"]
    assert opaque and all(r.text is None and len(r.opaque_sha256) == 64 for r in opaque)


# --- 5. harness events -----------------------------------------------------------------------------------------------

def test_hook_rows_pair_hook_start_with_hook_end():
    ex = copilot.read(NATIVE_ON)
    assert isinstance(ex.harness_events, list), ex.harness_events
    hooks = [e for e in ex.harness_events if e.event == "hook"]
    starts = [(n, e) for n, e in enumerate(_events(NATIVE_ON), 1) if e.get("type") == "hook.start"]
    assert len(hooks) == len(starts) == 27
    assert [(h.native_ordinal, h.name, h.start) for h in hooks] == [(n, e["data"]["hookType"], e["timestamp"]) for n, e in starts]
    assert all(h.ok is True and h.end and h.end >= h.start for h in hooks)
    failed = [e for e in copilot.read(NATIVE_REV92).harness_events if e.event == "hook"]
    assert len(failed) == 8 and all(h.ok is False and h.detail for h in failed)


def test_skill_loads_come_from_the_skill_tool_calls():
    events = copilot.read(ON).harness_events
    assert isinstance(events, list), events
    loads = [(e.name, e.ok) for e in events if e.event == "skill_load"]
    assert loads == [("implement", True), ("optimize-graph", True)]
    rows = normalize.harness_event_rows("r", "c", "s", copilot.read(ON), "x")
    assert {r["event"] for r in rows} == {"skill_load"} and all(r["ok"] == 1 for r in rows)


# --- 6. prompt parts: instruction files on pack-on, none on pack-off --------------------------------------------------

def _parts(record: Path, kind: str) -> list[telemetry.PromptPart]:
    parts = copilot.read(record).prompt_parts
    assert isinstance(parts, list), parts
    return [p for p in parts if p.part == kind]


def test_instruction_file_parts_on_pack_on_and_none_on_pack_off():
    on = _parts(ON, "instruction_file")
    assert len(on) >= 1 and all(p.source.startswith(DEBUG) for p in on)
    assert any(p.path and p.path.endswith("AGENTS.md") and p.delivery == "inlined" for p in on)
    assert any(p.delivery == "listed" and p.path.endswith(".instructions.md") for p in on)
    assert _parts(OFF, "instruction_file") == []
    for record in (OFF, ON):  # the inlined parts partition the first request's instructions exactly
        log = next((record.parents[2] / "logs").glob("process-*.log"))
        instructions = next(body for kind, _, body in copilot._wire(log) if kind == "request")["instructions"]
        parts = copilot.read(record).prompt_parts
        assert sum(p.chars for p in parts if p.chars is not None) == len(instructions)
    assert len(_parts(OFF, "system")) == 1 and len(_parts(OFF, "skills")) == 2


def test_a_listed_instruction_row_carries_its_own_table_row_and_the_parts_partition_exactly():
    """Leader ruling (J2-FIX DR, option c): each `listed` instruction_file part counts the characters of its own
    table row, taken out of the `system` part, so every part has a count and the parts still partition the first
    request's instructions exactly."""
    parts = copilot.read(ON).prompt_parts
    assert isinstance(parts, list), parts
    listed = [p for p in parts if p.part == "instruction_file" and p.delivery == "listed"]
    assert len(listed) == 6 and all(p.chars for p in listed)
    log = next((ON.parents[2] / "logs").glob("process-*.log"))
    text = next(body for kind, _, body in copilot._wire(log) if kind == "request")["instructions"]
    row = next(line for line in text.splitlines(keepends=True) if "csharp-style-guide.instructions.md" in line)
    assert next(p.chars for p in listed if p.path.endswith("csharp-style-guide.instructions.md")) == len(row)
    assert all(p.chars is not None for p in parts if p.part == "instruction_file")
    assert sum(p.chars for p in parts if p.chars is not None) == len(text)


def test_the_tools_part_carries_the_fingerprint_digest_and_no_character_count():
    """Leader ruling (J2-FIX tools-part DR): the `tools` part stays listed with no count, its `path` the request's
    tool-fingerprint digest (no schema text), so two cells' catalogues compare exactly."""
    tools = {arm: [p for p in copilot.read(rec).prompt_parts if p.part == "tools"] for arm, rec in (("off", OFF), ("on", ON))}
    assert {arm: [(p.path, p.chars, p.delivery) for p in ps] for arm, ps in tools.items()} == {
        "off": [("copilotToolsFingerprint:6907acb0", None, "listed")],
        "on": [("copilotToolsFingerprint:6907acb0", None, "listed")]}
    fast = [p.path for p in copilot.read(FAST).prompt_parts if p.part == "tools"]
    assert fast == ["copilotToolsFingerprint:360fbf8f"]  # a different catalogue, a different digest


def _without_tool_tokens(event: dict) -> dict:
    for state in event.get("data", {}).get("promptCacheBreakState", []):
        for model in state.get("models", {}).values():
            model.pop("tool_tokens", None)
    return event


def test_the_tools_part_carries_the_catalogue_size_in_tokens_from_the_usage_checkpoint(tmp_path):
    """A7: Copilot records the tool definitions' size only as `tool_tokens` beside `tool_count` in the usage
    checkpoint (2187 for 9 tools on both lean runs). The `tools` part carries it in `tokens`; every other part has none,
    and a checkpoint without it is None (not recorded), never 0."""
    tokens = {name: [p.tokens for p in copilot.read(rec).prompt_parts if p.part == "tools"]
              for name, rec in (("off", OFF), ("on", ON), ("fast", FAST))}
    assert tokens == {"off": [2187], "on": [2187], "fast": [1996]}  # the fast build's catalogue has 8 tools
    assert all(p.tokens is None for p in copilot.read(ON).prompt_parts if p.part != "tools")

    shutil.copytree(RERUN / "rerun-on" / "home", tmp_path / "home")
    record = _record(tmp_path)
    record.write_text("".join(json.dumps(_without_tool_tokens(e)) + "\n" for e in _events(record)), encoding="utf-8")
    assert [p.tokens for p in copilot.read(record).prompt_parts if p.part == "tools"] == [None]
    (row,) = [r for r in normalize.prompt_part_rows("r", "c", "s", copilot.read(ON), "x") if r["part"] == "tools"]
    assert row["tokens"] == 2187


def test_pack_on_parts_carry_distinct_ordinals_and_load_in_a_view(tmp_path, monkeypatch):
    """J2-FIX item 10: `PromptPart.native_ordinal` (J1A-FIX item 28) is the part's position in its record, so the
    pack-on parts never share a key and a pass that writes them loads without HB-LED-003."""
    from archived_runs import GOOD, make_root, make_run, pass_rows

    from harness_bench import profiles, views
    from harness_bench.grade import runner

    parts = copilot.read(ON).prompt_parts
    assert isinstance(parts, list), parts
    assert [p.native_ordinal for p in parts] == list(range(len(parts)))
    real = profiles.READERS["codex"]

    def reader(path):
        ex = real(path)
        ex.prompt_parts = parts
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", reader)
    root = make_root(tmp_path / "r")
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert len(pass_rows(run_dir, "prompt_parts", gid)) == len(parts)
    assert views.load(run_dir).cells[0].extraction_id is not None  # no HB-LED-003: every part's key differs


def test_without_the_debug_log_prompt_parts_are_not_recorded(tmp_path):
    assert copilot.read(_record_only(tmp_path, ON)).prompt_parts == "not recorded: no debug process log in the cell home"


def test_requests_of_another_session_are_not_this_cells(tmp_path):
    record = _record_only(tmp_path, OFF)
    log = next((RERUN / "rerun-off" / "home" / "logs").glob("process-*.log"))
    (tmp_path / "home" / "logs").mkdir()
    (tmp_path / "home" / "logs" / log.name).write_text(log.read_text(encoding="utf-8").replace(record.parent.name, "another-session"),
                                                     encoding="utf-8")
    ex = copilot.read(record)
    assert [(c.requests, c.start) for c in ex.model_calls] == [(5, None)]
    assert not any(source and source.startswith(DEBUG) for _, source in _served(ex))


def test_parallel_tool_requests_in_one_message_are_keyed_by_their_own_start_lines():
    # PROBE-FIX sweep (the Grok HB-LED-003 shape): one assistant.message holds several toolRequests (rerun-off lines 5
    # and 14, as in devprobe-rerun-1); each call is keyed by its own tool.execution_start line, so no two share a key.
    events = _events(OFF)
    requested = [t["toolCallId"] for e in events if e.get("type") == "assistant.message"
                 for t in e["data"].get("toolRequests") or []]
    starts = {e["data"]["toolCallId"]: n for n, e in enumerate(events, 1) if e.get("type") == "tool.execution_start"}
    assert max(len(e["data"].get("toolRequests") or []) for e in events if e.get("type") == "assistant.message") > 1
    rows = normalize.tool_call_rows("run", "cell", "sid", copilot.read(OFF), "x")
    assert sorted(r["native_ordinal"] for r in rows) == sorted(starts[c] for c in requested)
    assert len({r["native_ordinal"] for r in rows}) == len(rows) == len(requested)
