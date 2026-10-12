"""R-READ-GROK: the Grok reader (`telemetry/grok.py`) on hand-built session fixtures in the 1.0.41 record's shape.

The fixtures under tests/fixtures/grok/rerun-* are synthetic (rerun-provenance.json): keys and row order follow the
spike sessions, every value is invented. Each stream is tested through its `normalize` row builder (ADR-0026 s1).
"""

import hashlib
import json
import shutil
from pathlib import Path

from harness_bench import profiles, views
from harness_bench.telemetry import Extraction, ToolCall, grok, normalize

FIX = Path(__file__).resolve().parent / "fixtures" / "grok"
ON = FIX / "rerun-pack-on" / "00000000-0000-4000-8000-0000000000e1"
OFF = FIX / "rerun-pack-off" / "00000000-0000-4000-8000-0000000000e2"
WEB = FIX / "rerun-web-fetch" / "00000000-0000-4000-8000-0000000000e3"
ARGS = ("run", "cell", "sid")


def _served(ex: Extraction) -> dict[str, dict]:
    return {r["field"]: r for r in normalize.served_rows(*ARGS, ex, "x1")}


def _profile(aliases: dict) -> profiles.Profile:
    return profiles.Profile(harness="grok", home_env="GROK_HOME", credential_source=None, credential_name=None,
                            command=("grok", "agent", "stdio"), model_aliases=aliases)


def test_model_served_is_the_records_model_id_and_the_exact_alias_table_allows_it():
    rows = _served(grok.read(ON))
    assert "model_served" in rows
    served = rows["model_served"]
    assert (served["value"], served["source"]) == ("grok-4.7-build", "chat_history.jsonl:assistant.model_id")
    aliases = _profile({"grok-4.7": ("grok-4.7-build",)}).model_aliases["grok-4.7"]
    assert served["value"] in aliases
    assert "grok-4.7-build-fast" not in aliases  # exact, never a prefix (ADR-0024 s5)


def test_a_session_dir_or_its_chat_history_file_reads_the_same():
    from_file = _served(grok.read(ON / "chat_history.jsonl"))
    assert from_file and from_file == _served(grok.read(ON))


def test_effort_and_context_tokens_come_from_the_record_with_their_sources():
    rows = _served(grok.read(ON))
    assert {"effort", "context_tokens", "model_api", "context_tier", "reasoning_summary"} <= rows.keys()
    assert (rows["effort"]["value"], rows["effort"]["source"]) == ("high", "chat_history.jsonl:assistant.reasoning_effort")
    assert (rows["context_tokens"]["value"], rows["context_tokens"]["source"]) == (256_000, "signals.json:contextWindowTokens")
    for name in ("model_api", "context_tier", "reasoning_summary"):
        assert rows[name]["value"] is None and rows[name]["not_recorded"].startswith("not recorded: ")


def test_two_served_ids_in_one_record_are_both_written(tmp_path):
    d = shutil.copytree(ON, tmp_path / "s")
    lines = (d / "chat_history.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1]) | {"model_id": "grok-4.7-build-fast"}
    (d / "chat_history.jsonl").write_text("\n".join([*lines[:-1], json.dumps(last)]) + "\n", encoding="utf-8")
    rows = normalize.served_rows(*ARGS, grok.read(d), "x1")
    assert [r["value"] for r in rows if r["field"] == "model_served"] == ["grok-4.7-build", "grok-4.7-build-fast"]


def test_usage_is_one_model_call_per_turn_and_model_with_requests_from_model_calls():
    ex = grok.read(ON)
    rows = normalize.model_call_rows(*ARGS, ex, "x1")
    assert [(r["native_ordinal"], r["model"], r["requests"]) for r in rows] == [(1, "grok-4.7-build", 2)]
    c = ex.model_calls[0]
    assert (c.uncached_input, c.cache_read, c.cache_write, c.output, c.reasoning) == (1000, 2000, 0, 160, 120)
    assert c.end == "2026-10-11T20:12:27.000000000+00:00" and c.start is None
    assert grok.PER_REQUEST == "not recorded: per-turn totals only"
    assert ex.missing == []


def test_a_full_prompt_below_its_cached_part_is_hb_tel_001_never_a_plausible_uncached_count(tmp_path):
    d = shutil.copytree(ON, tmp_path / "s")
    usage = json.loads((d / "usage.json").read_text(encoding="utf-8"))
    usage["turns"][0]["modelUsage"]["grok-4.7-build"]["inputTokens"] = 100
    (d / "usage.json").write_text(json.dumps(usage), encoding="utf-8")
    assert [(m.native_ordinal, m.field) for m in grok.read(d).missing] == [(1, "inputTokens")]


def test_an_absent_usage_file_makes_the_record_unreadable_never_zero_calls(tmp_path):
    d = shutil.copytree(ON, tmp_path / "s")
    (d / "usage.json").unlink()
    ex = grok.read(d)
    assert ex.model_calls == []
    assert normalize.record_unreadable(ex) == "native record fields missing: usage.json:turns"


def test_a_turn_field_the_record_lacks_is_hb_tel_001_never_a_silent_zero(tmp_path):
    d = shutil.copytree(ON, tmp_path / "s")
    usage = json.loads((d / "usage.json").read_text(encoding="utf-8"))
    del usage["turns"][0]["modelUsage"]["grok-4.7-build"]["outputTokens"]
    (d / "usage.json").write_text(json.dumps(usage), encoding="utf-8")
    ex = grok.read(d)
    assert [(m.native_ordinal, m.field, m.code) for m in ex.missing] == [(1, "outputTokens", "HB-TEL-001")]


def test_reasoning_rows_are_summary_text_on_pack_on_and_encrypted_only_with_sha256_on_pack_off():
    on = normalize.reasoning_rows(*ARGS, grok.read(ON), "x1")
    assert [(r["native_ordinal"], r["item_ordinal"], r["source_kind"], r["text"], r["chars"]) for r in on] == [
        (5, 0, "summary", "I will read the file and reply.", 31), (9, 0, "summary", "Reading the file to answer.", 27)]
    off = normalize.reasoning_rows(*ARGS, grok.read(OFF), "x1")
    payload = json.loads((OFF / "chat_history.jsonl").read_text(encoding="utf-8").splitlines()[4])["encrypted_content"]
    assert [(r["source_kind"], r["text"], r["chars"]) for r in off] == [("encrypted-only", None, None)] * 2
    assert off[0]["opaque_sha256"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert all(r["reasoning_tokens"] is None for r in on + off)  # usage.json gives per-turn totals only


def test_instruction_files_from_agents_md_files_and_system_and_tools_parts_with_chars():
    on = normalize.prompt_part_rows(*ARGS, grok.read(ON), "x1")
    by = {r["part"]: r for r in on}
    assert [(r["path"], r["chars"], r["delivery"], r["source"]) for r in on if r["part"] == "instruction_file"] == [
        ("C:\\work\\repo\\Agents.md", 20, "inlined", "prompt_context.json:agents_md_files")]
    assert (by["system"]["chars"], by["system"]["source"]) == (
        len((ON / "system_prompt.txt").read_text(encoding="utf-8")), "system_prompt.txt")
    assert (by["tools"]["chars"], by["tools"]["source"]) == (
        len((ON / "tool_definitions.json").read_text(encoding="utf-8")), "tool_definitions.json")
    off = normalize.prompt_part_rows(*ARGS, grok.read(OFF), "x1")
    assert [r for r in off if r["part"] == "instruction_file"] == [] and {r["part"] for r in off} == {"system", "tools"}


def test_an_absent_prompt_context_is_not_recorded_never_zero_instruction_files(tmp_path):
    d = shutil.copytree(OFF, tmp_path / "s")
    (d / "prompt_context.json").unlink()
    ex = grok.read(d)
    assert ex.prompt_parts == "not recorded: prompt_context.json absent or unreadable"
    assert normalize.stream_reason(ex.prompt_parts) == ex.prompt_parts


def test_a_web_fetch_call_is_class_other_and_a_read_file_call_is_read_with_its_outcome():
    web = normalize.tool_call_rows(*ARGS, grok.read(WEB), "x1")
    assert [(r["native_ordinal"], r["name"], r["tool_class"], r["ok"]) for r in web] == [(1, "web_fetch", "other", 1)]
    on = normalize.tool_call_rows(*ARGS, grok.read(ON), "x1")
    assert [(r["name"], r["tool_class"], r["start"], r["end"], r["ok"]) for r in on] == [
        ("read_file", "read", "2026-10-11T20:12:25.167Z", "2026-10-11T20:12:25.172Z", 1)]


def test_two_tool_calls_in_one_assistant_line_get_distinct_native_ordinals_in_native_order(tmp_path):
    # PROBE-FIX: the 1.0.41 build writes parallel calls as one assistant row (devprobe-rerun-1: list_dir + grep on
    # one line); two rows sharing (session, native_ordinal) made HB-LED-003 refuse the run's view.
    d = shutil.copytree(ON, tmp_path / "s")
    lines = (d / "chat_history.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[5])
    row["tool_calls"].append({"id": "call-00000000-0000-4000-8000-0000000000c1-1", "name": "grep", "arguments": "{}"})
    lines[5] = json.dumps(row)
    (d / "chat_history.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = normalize.tool_call_rows(*ARGS, grok.read(d), "x1")
    assert [(r["native_ordinal"], r["name"]) for r in rows] == [(1, "read_file"), (2, "grep")]


def test_tool_class_covers_every_advertised_tool_and_classes_the_out_of_profile_ones_other():
    advertised = [t["function"]["name"] for t in json.loads((ON / "tool_definitions.json").read_text(encoding="utf-8"))]
    assert sorted(grok.TOOL_CLASS) == sorted(advertised) and len(advertised) == 26
    shell = {"run_terminal_command", "get_command_or_subagent_output", "kill_command_or_subagent", "monitor"}
    assert {n for n, c in grok.TOOL_CLASS.items() if c == "shell"} == shell
    assert {n for n, c in grok.TOOL_CLASS.items() if c == "read"} == {"read_file", "list_dir", "grep"}
    assert {n for n, c in grok.TOOL_CLASS.items() if c == "edit"} == {"search_replace", "write"}
    assert {n for n, c in grok.TOOL_CLASS.items() if c == "meta"} == {"search_tool", *INERT}
    out = {"web_fetch", "image_gen", "image_edit", "image_to_video", "reference_to_video", "spawn_subagent",
           "scheduler_create", "scheduler_delete", "scheduler_list", "workflow", "use_tool"}
    assert out <= {n for n, c in grok.TOOL_CLASS.items() if c == "other"}
    assert grok.tool_class("a_tool_no_build_advertised") == "other"


INERT = {"todo_write", "enter_plan_mode", "exit_plan_mode", "ask_user_question", "send_feedback"}


def test_a_workspace_inert_tool_call_is_meta_and_never_hb_val_008():  # Leader ruling on R-READ-GROK's DR
    ex = Extraction()
    ex.tool_calls = [ToolCall(n, name, grok.tool_class(name), None, None, True) for n, name in enumerate(sorted(INERT), 1)]
    error, warning = views._out_of_profile(normalize.tool_call_rows(*ARGS, ex, "x1"), None)
    assert (error, warning) == (None, None)
    ex.tool_calls = [ToolCall(9, "web_fetch", grok.tool_class("web_fetch"), None, None, True)]
    assert views._out_of_profile(normalize.tool_call_rows(*ARGS, ex, "x1"), None)[0].code == "HB-VAL-008"


def test_hooks_and_compaction_are_flagged_so_the_stream_is_not_recorded():
    ex = grok.read(ON)
    assert ex.harness_events == "not recorded: grok hook and compaction events are Flagged (no record shows their shape)"
    assert normalize.harness_event_rows(*ARGS, ex, "x1") == []
