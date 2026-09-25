"""R-74: the scenario-6 `delegate` allowance. The class is static in each reader (item 1); the allowance is carried per
cell, never per harness file (item 3); a Claude Code cell's sub-agent records are read (item 4). The scenario rule
itself lives only in views._out_of_profile (tests/test_views.py)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_bench import profiles
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code, codex, copilot

ROOT = Path(__file__).resolve().parents[1]
BUILD = SimpleNamespace(exe=Path("harness.exe"), adapter=Path("adapter.js"))
COPILOT_DELEGATE = ["task", "write_agent", "read_agent", "list_agents"]  # the operator's list, R-74 ruling
STAYS_OUT = ["ListAgents", "SendMessage", "TaskStop", "Workflow"]  # R-74 item 1: never a widening


def _claude_rows(name: str) -> list[dict]:
    return [{"type": "assistant", "timestamp": "2026-09-25T05:20:53.616Z", "sessionId": "sess-a",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": {},
                         "content": [{"type": "tool_use", "id": "t1", "name": name, "input": {"prompt": "write one file"}}]}},
            {"type": "user", "timestamp": "2026-09-25T05:20:54.244Z",
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "done"}]}}]


def _write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


# --- item 1, condition 3: the class is static in each reader ------------------------------------------------------


def test_claude_code_classes_agent_as_delegate_from_a_synthetic_row(tmp_path):
    ex = claude_code.read(_write(tmp_path / "s.jsonl", _claude_rows("Agent")))
    assert [(t.name, t.tool_class, t.ok) for t in ex.tool_calls] == [("Agent", "delegate", True)]


@pytest.mark.parametrize("name", STAYS_OUT)
def test_the_other_claude_code_agent_ids_stay_out_of_profile(tmp_path, name):
    ex = claude_code.read(_write(tmp_path / "s.jsonl", _claude_rows(name)))
    assert [(t.name, t.tool_class) for t in ex.tool_calls] == [(name, "other")]


def test_each_reader_delegate_set_is_exactly_the_operators_list():
    assert [n for n, c in claude_code.TOOL_CLASSES.items() if c == "delegate"] == ["Agent"]
    assert [n for n, c in copilot.TOOL_CLASS.items() if c == "delegate"] == COPILOT_DELEGATE
    # Codex: measured before allowed (item 5). The ids its own system message names (ok.jsonl:4) stay `other` until then.
    assert {codex._tool_class(n) for n in ("spawn_agent", "send_message", "followup_task", "wait_agent",
                                           "interrupt_agent", "list_agents")} == {"other"}


def test_copilot_classes_the_four_ids_as_delegate_from_synthetic_rows(tmp_path):
    rows = [{"type": "session.start", "data": {"sessionId": "syn", "version": 1}, "timestamp": "2026-01-01T00:00:00.000Z"}]
    for n, name in enumerate(COPILOT_DELEGATE):
        rows += [{"type": "tool.execution_start", "data": {"toolCallId": f"c{n}", "toolName": name},
                  "timestamp": f"2026-01-01T00:00:0{n}.000Z"},
                 {"type": "tool.execution_complete", "data": {"toolCallId": f"c{n}", "success": True},
                  "timestamp": f"2026-01-01T00:00:0{n}.500Z"}]
    ex = copilot.read(_write(tmp_path / "session-state" / "syn" / "events.jsonl", rows))
    assert [(t.name, t.tool_class, t.ok) for t in ex.tool_calls] == [(n, "delegate", True) for n in COPILOT_DELEGATE]


def test_a_copilot_sub_agent_tool_call_reaches_tool_calls(tmp_path):  # item 4: sub-agent rows carry a top-level agentId
    rows = [{"type": "session.start", "data": {"sessionId": "syn", "version": 1}, "timestamp": "2026-01-01T00:00:00.000Z"},
            {"type": "tool.execution_start", "agentId": "sub-1", "data": {"toolCallId": "s1", "toolName": "web_fetch"},
             "timestamp": "2026-01-01T00:00:01.000Z"},
            {"type": "tool.execution_complete", "agentId": "sub-1", "data": {"toolCallId": "s1", "success": True},
             "timestamp": "2026-01-01T00:00:02.000Z"}]
    ex = copilot.read(_write(tmp_path / "session-state" / "syn" / "events.jsonl", rows))
    assert [(t.name, t.tool_class, t.ok) for t in ex.tool_calls] == [("web_fetch", "other", True)]


# --- item 3: the allowance is carried per cell (seed_home and argv take the scenario) --------------------------------


def _claude_allow(tmp_path: Path, scenario) -> list[str]:
    home = tmp_path / f"home-{scenario}"
    profiles.load(ROOT, "claude-code", credential_source=tmp_path / "none").seed_home(home, "claude-opus-5-5", scenario=scenario)
    return json.loads((home / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]


def test_a_scenario6_claude_code_cell_is_seeded_with_agent_and_every_other_cell_exactly_as_before(tmp_path):
    before = ["Bash", "PowerShell", "Edit", "Write", "NotebookEdit", "Read", "Glob", "Grep", "mcp__scripted_user__ask_user"]
    assert _claude_allow(tmp_path, 6) == [*before, "Agent"]
    for scenario in (None, 1, 5, 7):
        assert _claude_allow(tmp_path, scenario) == before
    home = tmp_path / "plain"
    profiles.load(ROOT, "claude-code", credential_source=tmp_path / "none").seed_home(home, "claude-opus-5-5")
    assert (home / "settings.json").read_text(encoding="utf-8") == (tmp_path / "home-5" / "settings.json").read_text(encoding="utf-8")


def _copilot_tools(argv: list[str]) -> list[str]:
    start = argv.index("--available-tools") + 1
    end = next((i for i in range(start, len(argv)) if argv[i].startswith("--")), len(argv))
    return argv[start:end]


def test_a_scenario6_copilot_cell_advertises_the_four_ids_and_every_other_cell_exactly_as_before():
    p = profiles.load(ROOT, "copilot")
    before = p.argv(BUILD, "gpt-6-sol")
    assert p.argv(BUILD, "gpt-6-sol", scenario=6) == [*before, *COPILOT_DELEGATE]
    for scenario in (None, 1, 5, 7):
        assert p.argv(BUILD, "gpt-6-sol", scenario=scenario) == before
    assert not set(COPILOT_DELEGATE) & set(_copilot_tools(before))


def test_the_scenario6_ids_come_before_the_scripted_user_additions(tmp_path):  # one --available-tools list
    argv = profiles.load(ROOT, "copilot").argv(BUILD, "gpt-6-sol", mcp_config=tmp_path / "m.json", scenario=6)
    assert _copilot_tools(argv)[-5:] == [*COPILOT_DELEGATE, "scripted_user-ask_user"]


def test_a_codex_scenario6_cell_is_seeded_and_launched_exactly_as_before(tmp_path):  # no allowance before item 5
    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "none")
    p.seed_home(tmp_path / "a", "gpt-6-sol", scenario=6)
    p.seed_home(tmp_path / "b", "gpt-6-sol")
    assert (tmp_path / "a" / "config.toml").read_bytes() == (tmp_path / "b" / "config.toml").read_bytes()


def test_the_launcher_seeds_from_the_cell(tmp_path):  # engine.py passes the cell (R-74 item 3)
    launcher = profiles.ProfileLauncher(profiles.load(ROOT, "claude-code", credential_source=tmp_path / "none"), tmp_path, {})
    launcher.seed(tmp_path / "home", {"model": "claude-opus-5-5", "scenario": 6})
    allow = json.loads((tmp_path / "home" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
    assert allow[-1] == "Agent"


def test_a_copilot_profile_without_the_tool_list_refuses_a_scenario6_launch():
    p = profiles.Profile("copilot", "COPILOT_HOME", None, None, ("{exe}", "--acp"))
    with pytest.raises(BenchError) as err:
        p.argv(BUILD, "gpt-6-sol", scenario=6)
    assert (err.value.code, err.value.message) == ("HB-USR-002", "a scenario-6 launch needs the Copilot tool allowlist (R-74 item 3)")


# --- item 4: a Claude Code cell's sub-agent records are read -------------------------------------------------------


def test_the_claude_code_profile_names_the_sub_agent_records_of_a_session(tmp_path):
    p = profiles.load(ROOT, "claude-code")
    main = _write(tmp_path / "projects" / "C--cells-x" / "sess-a.jsonl", _claude_rows("Agent"))
    sub = _write(tmp_path / "projects" / "C--cells-x" / "sess-a" / "subagents" / "agent-a1b2.jsonl", _claude_rows("Write"))
    _write(tmp_path / "projects" / "C--cells-x" / "sess-b" / "subagents" / "agent-zz.jsonl", _claude_rows("Write"))
    assert p.native_records(tmp_path, "sess-a") == [main]  # the main record stays one file (the runner needs exactly one)
    assert p.subagent_records(tmp_path, "sess-a") == [sub]
    assert profiles.load(ROOT, "copilot").subagent_records(tmp_path, "sess-a") == []  # Copilot: one events.jsonl
