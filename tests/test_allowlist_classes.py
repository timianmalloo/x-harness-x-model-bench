"""R-34: the Claude Code allowlist covers every tool id in its declared classes, per platform and pinned build.

ADR-0004 allows *classes* (file read and edit in the workspace, shell); the ids that make up a class are per
platform and per pinned build. The source of the ids is the build itself, never memory: the tool list the pinned
build advertised to the model, as its own native record writes it (`attachment.type == "prompt_snapshot"`, loaded
tools; `deferred_tools_delta`, tools behind ToolSearch). Only an authenticated session writes that list (an
unauthenticated `claude -p` init omits `PowerShell` on 2.1.282 unless CLAUDE_CODE_USE_POWERSHELL_TOOL is set,
observed 2026-09-25), so the fixture is cut from a real cell's record:
`tests/fixtures/native/claude-code/tools-2.1.282-win32.jsonl` holds the four rows of the native record of cell
17efb75ce2d5fc6d, run e2e-wave1-1790302505 (Claude Code 2.1.282, win32), trimmed to type, version, sessionId,
the platform, tool names, and each tool description's first line.

On a pin bump: the native test below goes red until the fixture is recut from a cell record of the new build
(`advertised()` reads a full native record as well as the trimmed one). A new id in the new build then makes
`test_every_tool_id_the_pinned_build_advertises_is_classified` red until it is classified: this is the control
for the defect class "a per-platform tool id missing from a class allowlist" (docs/lessons/defect-classes.md).
"""

import json
import sys
from pathlib import Path

import pytest

from harness_bench import profiles, tools
from harness_bench.telemetry import claude_code

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
TOOL_LIST = FIX / "native" / "claude-code" / "tools-2.1.282-win32.jsonl"
NEGATIVE = FIX / "ledger" / "r34-cc-opus-pack-on-powershell-denied.json"
COPILOT_ON = next((FIX / "native" / "copilot" / "on").rglob("events.jsonl"))

# The ADR-0004 classes, by the build's own description of each id (the fixture's first description lines).
# NotebookEdit is deferred (ToolSearch-gated) on 2.1.282, so the trimmed fixture carries its name only, no
# description line (`deferred_tools_delta.addedNames`, checked directly against the fixture, not memory).
# R-35: in-class -- it edits a file in the workspace (a `.ipynb`), the same class as Edit and Write.
CLASSES = {
    "shell": {"Bash", "PowerShell"},  # "Executes a bash command ..." / "Executes a given PowerShell command ..."
    "file edit": {"Edit", "Write", "NotebookEdit"},  # "Performs exact string replacement ..." / "Writes a file ..." / deferred, no description line (R-35)
    "file read": {"Read", "Glob", "Grep"},  # "Reads a file ..." / "Fast file pattern matching" / "Content search"
}
# Outside every declared class: ADR-0004 denies them ("any other tool the harness offers", web tools, MCP servers).
# R-54 (a): class `meta` loads a deferred tool's schema and invokes nothing. It runs with no permission callback, so it
# needs no allowlist entry, and it is outside CLASSES (the allowlist tests below) on purpose.
META = {"ToolSearch"}
OUT_OF_PROFILE = {
    "Agent", "ListAgents", "ReportFindings", "ScheduleWakeup", "Skill", "Workflow",
    "CronCreate", "CronDelete", "CronList", "DesignSync", "EnterPlanMode", "EnterWorktree", "ExitPlanMode",
    "ExitWorktree", "Monitor", "PushNotification", "RemoteTrigger", "SendMessage", "TaskStop", "WebFetch", "WebSearch",
}

# R-45: Copilot's `skill` reads a workspace SKILL.md. The pinned build's checkpoint below supplies
# the ids; the ruling supplies the class boundary. Every github-mcp-server-* id is outside it.
COPILOT_CLASSES = {
    "shell": {"powershell", "list_powershell", "read_powershell", "stop_powershell"},
    "file edit": {"apply_patch"},
    "file read": {"view", "glob", "rg", "skill"},
}
COPILOT_OUT_OF_PROFILE = {"web_search", "web_fetch", "task", "write_agent", "read_agent",
                          "list_agents", "sql"}


def copilot_advertised(record: Path) -> set[str]:
    """Tool ids from the pinned Copilot build's session.usage_checkpoint, independent of the reader."""
    ids: set[str] = set()
    for line in record.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("type") != "session.usage_checkpoint":
            continue
        for state in row["data"]["promptCacheBreakState"]:
            for model in state["models"].values():
                ids.update(tool["name"] for tool in model["tools"])
    return ids


def copilot_allowlist() -> set[str]:
    command = profiles.load(ROOT, "copilot").command
    if "--available-tools" not in command:
        return set()
    start = command.index("--available-tools")
    return set(command[start + 1:])


def test_copilot_pinned_build_tool_ids_are_all_classified():
    ids = copilot_advertised(COPILOT_ON)
    assert len(ids) == 21  # the committed pack-on sample; a recut has its own check below
    known = set().union(*COPILOT_CLASSES.values()) | COPILOT_OUT_OF_PROFILE
    assert {i for i in ids if i not in known and not i.startswith("github-mcp-server-")} == set()
    assert {i for i in ids if i.startswith("github-mcp-server-")}  # exercise the prefix class


def test_copilot_allowlist_covers_every_in_class_id_and_nothing_outside_it():
    ids = copilot_advertised(COPILOT_ON)
    in_class = ids & set().union(*COPILOT_CLASSES.values())
    allowed = copilot_allowlist()
    assert in_class - allowed == set()
    assert allowed - in_class == set()
    assert allowed & COPILOT_OUT_OF_PROFILE == set()
    assert not any(i.startswith("github-mcp-server-") for i in allowed)


def test_old_copilot_fixture_records_out_of_profile_ids():
    ids = copilot_advertised(COPILOT_ON)
    assert COPILOT_OUT_OF_PROFILE <= ids
    assert any(i.startswith("github-mcp-server-") for i in ids)


def test_fixed_copilot_profile_advertises_no_out_of_profile_ids():  # R-45 c1: fixture recut from run qual-r45-1
    record = next((FIX / "native" / "copilot" / "fixed").rglob("events.jsonl"))
    ids = copilot_advertised(record)
    in_class = set().union(*COPILOT_CLASSES.values())
    assert ids <= in_class
    assert not any(i.startswith("github-mcp-server-") for i in ids)


def advertised(record: Path) -> tuple[set[str], set[str], set[str]]:
    """(tool ids, build versions, platforms) from a Claude Code native record, full or trimmed."""
    ids: set[str] = set()
    versions: set[str] = set()
    platforms: set[str] = set()
    for line in record.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        att = row.get("attachment") if isinstance(row.get("attachment"), dict) else {}
        kind = att.get("type")
        if kind == "environment":
            platforms.add(att["snapshot"]["platform"])
        elif kind == "prompt_snapshot" and att.get("tools"):
            ids |= {t["name"] for t in att["tools"]}
        elif kind == "deferred_tools_delta":
            ids = (ids | set(att.get("addedNames", []))) - set(att.get("removedNames", []))
        else:
            continue
        versions.add(row["version"])
    return ids, versions, platforms


def claude_allowlist(tmp_path: Path) -> set[str]:
    """The allowlist a Claude Code cell is seeded with (the real profile path, not a copy of the YAML)."""
    cred = tmp_path / "cred.json"
    cred.write_text("{}", encoding="utf-8")
    home = tmp_path / "home"
    profiles.load(ROOT, "claude-code", credential_source=cred).seed_home(home, model="claude-opus-5-5")
    return set(json.loads((home / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"])


def test_the_tool_list_fixture_is_one_build_on_one_platform():
    ids, versions, platforms = advertised(TOOL_LIST)
    assert versions == {"2.1.282"} and platforms == {"win32"}
    assert {"Bash", "PowerShell", "Edit", "Write", "Read", "Glob", "Grep"} <= ids  # the reader found both lists


def test_the_claude_code_allowlist_covers_every_class_id_the_pinned_build_advertises(tmp_path):  # R-34 condition 2
    ids, _, _ = advertised(TOOL_LIST)
    in_class = ids & set().union(*CLASSES.values())
    assert in_class - claude_allowlist(tmp_path) == set()


def test_the_claude_code_allowlist_names_nothing_outside_the_declared_classes(tmp_path):  # ADR-0004: no widening
    assert claude_allowlist(tmp_path) <= set().union(*CLASSES.values())


def test_every_tool_id_the_pinned_build_advertises_is_classified():  # a new id in a later build is red here
    ids, _, _ = advertised(TOOL_LIST)
    known = set().union(*CLASSES.values()) | META | OUT_OF_PROFILE
    assert {i for i in ids if i not in known and not i.startswith("mcp__")} == set()


def test_the_meta_class_is_exactly_tool_search_in_the_reader_and_here():  # R-54 c1
    assert META == {"ToolSearch"} and META <= advertised(TOOL_LIST)[0]
    assert {name for name, cls in claude_code.TOOL_CLASSES.items() if cls == "meta"} == META
    assert not META & OUT_OF_PROFILE


@pytest.mark.native
def test_the_tool_list_fixture_is_the_pinned_build_on_this_platform():  # a pin bump is red until the fixture is recut
    dest = ROOT / ".tools" / "harness"
    tools.install(ROOT / "bench" / "tools", dest, timeout=900)
    _, versions, platforms = advertised(TOOL_LIST)
    assert versions == {tools.resolve(dest)["claude-code"].version}
    assert platforms == {sys.platform}


# --- R-34 condition 1: the negative fixture, kept -------------------------------------------------------------
# The cc-opus pack-on cell of e2e-wave1-1790302505: the model called PowerShell once, the allowlist of the day did
# not name it, the driver refused the permission request, and US-14 failed on [0,1,0,0,0,0].


def _negative() -> dict:
    return json.loads(NEGATIVE.read_text(encoding="utf-8"))


def test_the_negative_fixture_shows_the_one_denied_powershell_call():  # the negative control: stays true
    fx = _negative()
    allowed_then = set(fx["settings_json"]["permissions"]["allow"])
    outside = [c for c in fx["tool_calls"] if c["name"] not in allowed_then]
    outcome = next(e for e in fx["events"] if e["kind"] == "cell.outcome")
    assert [(c["name"], c["ok"]) for c in outside] == [("PowerShell", 0)]
    assert outcome["permission_requests"] == len(outside) == 1
    assert all(c["ok"] == 1 for c in fx["tool_calls"] if c["name"] in allowed_then)
    assert fx["adapter_stderr"] == [('permissions.defaultMode "dontAsk" is not available in this session; '
                                     'falling back to "default".')]


def test_the_current_allowlist_admits_every_tool_the_negative_fixture_called(tmp_path):  # R-34 regression
    called = {c["name"] for c in _negative()["tool_calls"]}
    assert called - claude_allowlist(tmp_path) == set()
