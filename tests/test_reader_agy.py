"""R-READ-AGY: the Antigravity reader (telemetry/agy.py) on scrubbed spike records (tests/fixtures/agy/reader).

Fixtures (provenance.json beside them): `pack-on` (spike turn2, a repo with AGENTS.md and GEMINI.md), `pack-off` (spike
perm, a repo with only README.md; one run_command), `turn1` (spike turn1: view_file and a denied run_command, and the
one step whose planner response holds thought text). Each `<home>` holds the teed `agy-stream.ndjson` and
`.gemini/antigravity-cli/conversations/<conversation id>.db`.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from harness_bench import views
from harness_bench.telemetry import (
    ModelCall,
    PromptPart,
    ReasoningItem,
    ServedSettings,
    ToolCall,
    agy,
    is_not_recorded,
    normalize,
)

FIXTURES = Path(__file__).parent / "fixtures" / "agy" / "reader"
PACK_ON, PACK_OFF, TURN1 = (FIXTURES / name / "agy-stream.ndjson" for name in ("pack-on", "pack-off", "turn1"))
MODEL = "gemini-3.8-flash-high"
# sha256 of each fixture's opaque step_payload bytes (the scrub's synthetic stand-ins, same length as recorded)
SHA_986 = "ef1dcf0aa41f6e733771c51074c555f06972387f67750e929f648806cd93427c"  # pack-on step 1, field 20.14.2.1
SHA_705 = "d28ba9087cb93627fb9b1693ebaace0ae297c428e684cc71e64361b4560dd21c"  # pack-off step 1, field 20.7.7.2.1
SHA_512 = "dd3daeb934c89d4e651ddd0b57730b6acebb83a6d2aa5e9db876310e22081e8f"  # pack-off step 3, field 20.14.2.1
SHA_733 = "ed2607ad77cf6c23de2a74d3833daca25b40105f1e3b035f96fbe7a1e8f1b3cd"  # turn1 step 1, field 20.7.7.2.1
SHA_3963 = "1256f785ffcfde30f7ebf3efe4e40fe46fda6a0c76f8ac24ee263114d5e7b727"  # turn1 step 3, field 20.7.7.2.1
# turn1 step 3's field 20.3, as stored (the scrub changed only the path): 432 chars for 909 thinking tokens, so it is a
# condensed account of the thinking, never the whole of it
THOUGHT = ('the content of [readme.md](file:///readme.md) reveals the first word is "banana." the agent must remember the'
           ' rule for lowercase replies. also, the agent needs to create clickable links for files and code symbols.\n\n\n'
           'The first word is "banana," and the response must be in lowercase. A clickable link is needed for the file '
           'reference. Therefore, the output should be `banana ([readme.md](file:///c:/cell/fixture/repo/readme.md))`.'
           '\n\n\n')
OUT_OF_PROFILE = (
    "browser_click_element", "browser_drag_pixel_to_pixel", "browser_get_dom", "browser_get_network_request",
    "browser_input", "browser_list_network_requests", "browser_mouse_down", "browser_mouse_up", "browser_move_mouse",
    "browser_press_key", "browser_refresh_page", "browser_resize_window", "browser_scroll", "browser_scroll_dom",
    "browser_select_option", "browser_subagent", "search_web", "read_url_content", "generate_image", "invoke_subagent",
    "define_subagent", "manage_subagents", "call_mcp_tool", "schedule", "send_message", "manage_inbox")


def _conversation_db(home: Path) -> Path:
    return next((home / ".gemini" / "antigravity-cli" / "conversations").glob("*.db"))


def test_served_model_is_init_model_and_the_context_window_is_not_recorded():
    ex = agy.read(PACK_ON)
    assert isinstance(ex.served, ServedSettings)
    assert ex.served.model_served == MODEL
    assert ex.served.sources["model_served"] == "agy-stream.ndjson init.model"
    assert is_not_recorded(ex.served.context_tokens) and is_not_recorded(ex.served.context_tier)
    rows = {r["field"]: r for r in normalize.served_rows("run", "cell", "sid", ex, "x")}
    assert (rows["model_served"]["value"], rows["model_served"]["source"]) == (MODEL, "agy-stream.ndjson init.model")
    assert rows["context_tokens"]["value"] is None and rows["context_tokens"]["not_recorded"].startswith("not recorded: ")
    assert ex.session_id == "00000000-0000-4000-8000-000000000001"


def test_one_model_call_per_agent_response_step_with_thinking_as_a_component_of_output():
    assert agy.read(PACK_ON).model_calls == [ModelCall(4, MODEL, 11885, 0, 0, 216, 215)]
    assert agy.read(PACK_OFF).model_calls == [ModelCall(3, MODEL, 11692, 0, 0, 227, 165),
                                              ModelCall(7, MODEL, 12062, 0, 0, 88, 85)]


def test_tool_steps_give_tool_calls_at_their_first_line_closed_by_their_terminal_state():
    # turn1's run_command reached DONE although agy denied it (its result lists the denial), so DONE is not success:
    # ok stays None (not recorded), never True.
    assert agy.read(TURN1).tool_calls == [ToolCall(4, "view_file", "read", None, None, None),
                                          ToolCall(7, "run_command", "shell", None, None, None)]


def test_reasoning_is_the_opaque_step_payload_as_encrypted_only_with_its_sha256():
    assert agy.read(PACK_ON).reasoning == [ReasoningItem(4, 0, "encrypted-only", None, None, 215, SHA_986)]
    assert agy.read(PACK_OFF).reasoning == [ReasoningItem(3, 0, "encrypted-only", None, None, 165, SHA_705),
                                            ReasoningItem(7, 0, "encrypted-only", None, None, 85, SHA_512)]
    assert agy.read(TURN1).reasoning == [ReasoningItem(3, 0, "encrypted-only", None, None, 181, SHA_733),
                                         ReasoningItem(6, 0, "summary", THOUGHT, 432, 909, None),
                                         ReasoningItem(6, 1, "encrypted-only", None, None, None, SHA_3963)]
    rows = normalize.reasoning_rows("run", "cell", "sid", agy.read(PACK_ON), "x")
    assert [(r["source_kind"], r["text"], r["reasoning_tokens"]) for r in rows] == [("encrypted-only", None, 215)]


def test_a_truncated_step_payload_is_omitted_with_the_steps_thinking_tokens(tmp_path):
    home = tmp_path / "home"
    shutil.copytree(PACK_ON.parent, home)
    con = sqlite3.connect(_conversation_db(home))
    con.execute("update steps set step_payload = substr(step_payload, 1, length(step_payload) - 100) where idx = 1")
    con.commit()
    con.close()
    assert agy.read(home / "agy-stream.ndjson").reasoning == [ReasoningItem(4, 0, "omitted", None, None, 215, None)]


def test_instruction_files_are_the_rule_blocks_of_the_request_prompt():
    parts = agy.read(PACK_ON).prompt_parts
    assert isinstance(parts, list)
    rules = [p for p in parts if p.part == "instruction_file"]
    assert rules == [
        PromptPart("instruction_file", "user_global", len("\nprobe user gemini md marker\n\n"), "inlined",
                   "conversations/<id>.db gen_metadata.data 1.1 <RULE[...]>"),
        PromptPart("instruction_file", "C:\\cell\\fixture\\repo\\AGENTS.md", len("\nReply in lowercase.\n\n"), "inlined",
                   "conversations/<id>.db gen_metadata.data 1.1 <RULE[...]>"),
        PromptPart("instruction_file", "C:\\cell\\fixture\\repo\\GEMINI.md", len("\nprobe gemini md marker\n\n"),
                   "inlined", "conversations/<id>.db gen_metadata.data 1.1 <RULE[...]>")]
    assert [p for p in parts if p.part == "system"] == [
        PromptPart("system", None, 14895, "inlined", "conversations/<id>.db gen_metadata.data 1.1")]
    off = agy.read(PACK_OFF).prompt_parts
    assert [p for p in off if p.part == "instruction_file"] == []
    assert [p.chars for p in off if p.part == "system"] == [14259]


def test_a_stream_without_its_conversation_db_still_gives_served_and_steps(tmp_path):
    shutil.copy(TURN1, tmp_path / "agy-stream.ndjson")
    ex = agy.read(tmp_path / "agy-stream.ndjson")
    assert isinstance(ex.served, ServedSettings)
    assert ex.served.model_served == MODEL
    assert [c.reasoning for c in ex.model_calls] == [181, 909]
    assert ex.reasoning == "not recorded: conversation db not found"
    assert ex.prompt_parts == "not recorded: conversation db not found"


def test_harness_events_are_not_recorded_with_a_reason():
    reason = normalize.stream_reason(agy.read(PACK_ON).harness_events)
    assert reason is not None and reason.startswith("not recorded: ")


def test_tool_class_covers_every_tool_the_pinned_build_advertises():
    init = json.loads(PACK_ON.read_text(encoding="utf-8").splitlines()[0])
    advertised = init["init"]["tools"]
    assert len(advertised) == 60
    assert sorted(agy.TOOL_CLASS) == sorted(advertised)
    assert set(agy.TOOL_CLASS.values()) <= {"shell", "edit", "read", "other"}
    assert {name: agy.TOOL_CLASS[name] for name in OUT_OF_PROFILE} == dict.fromkeys(OUT_OF_PROFILE, "other")


def _web_stream(tmp_path: Path) -> Path:
    """The pack-on init, then a search_web call that ran and a read_url_content call that ended in a tool ERROR (the
    shapes of R-TRANSPORT's recorded denial-tool-error stream, cut to these steps; the error message left out)."""
    cid = "00000000-0000-4000-8000-000000000001"
    steps = [{"step_index": 1, "state": "ACTIVE", "step_type": "tool", "tool_name": "search_web"},
             {"step_index": 1, "state": "DONE", "step_type": "tool", "tool_name": "search_web", "duration_seconds": 2.7},
             {"step_index": 2, "state": "ACTIVE", "step_type": "tool", "tool_name": "read_url_content"},
             {"step_index": 2, "state": "ERROR", "step_type": "tool", "tool_name": "read_url_content",
              "tool_info": {"name": "read_url_content", "error": {"type": "TOOL_ERROR"}}}]
    lines = [PACK_ON.read_text(encoding="utf-8").splitlines()[0]] + [
        json.dumps({"event": "step_update", "step_update": {"conversation_id": cid} | s}) for s in steps]
    path = tmp_path / "agy-stream.ndjson"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_an_out_of_profile_tool_that_ran_fires_hb_val_008(tmp_path):
    ex = agy.read(_web_stream(tmp_path))
    assert ex.tool_calls == [ToolCall(2, "search_web", "other", None, None, None),
                             ToolCall(4, "read_url_content", "other", None, None, False, "TOOL_ERROR")]
    error, _ = views._out_of_profile(normalize.tool_call_rows("run", "cell", "sid", ex, "x"), None)
    assert error is not None and error.code == "HB-VAL-008"
    assert "search_web" in error.message


@pytest.mark.parametrize("name", ["pack-on", "pack-off", "turn1"])
def test_committed_fixture_bytes_carry_no_spike_path_or_secret_shape(name):
    for f in (FIXTURES / name).rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            for shape in (b"spike-agy", b"Bearer ", b"Authorization", b"eyJ", b"\\Users\\"):
                assert shape not in data, (f, shape)
