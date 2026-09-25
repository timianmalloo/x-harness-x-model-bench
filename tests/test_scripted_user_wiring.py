"""R-37/R-51: one task-owned scripted user reaches only its intended cell."""

import json
from pathlib import Path

import pytest

from harness_bench import config, engine, plan, profiles, tools
from harness_bench.scripted_user import clarifications, matcher, server
from test_engine import FakeLauncher, _build_workspace, _engine_run, _plan, _run

pytestmark = pytest.mark.native
ROOT = Path(__file__).resolve().parents[1]
CLARIFICATIONS = ROOT / "tasks" / "A1" / "oracle" / "clarifications.yaml"


def _archived(base, p, cell):
    return base / "runs" / p["run_id"] / "archive" / cell["cell_id"] / "attempt-1"


def _scripted_task():
    return {"prompt": "Ask when needed.", "scripted_user": True,
            "clarifications_path": str(CLARIFICATIONS),
            "clarifications_sha256": clarifications.load(CLARIFICATIONS).sha256,
            "matcher_version": matcher.MATCHER_VERSION}


def test_engine_supplies_server_only_to_scripted_task_and_closes_log_before_archive(base):
    p = _plan()
    scripted, ordinary = p["cells"]
    ordinary["task"] = "X2"
    p["tasks"] = {"X1": _scripted_task(), "X2": {"prompt": "Do the task.", "scripted_user": False}}
    log_path = base / "cells" / p["run_id"] / scripted["cell_id"] / "scripted-user.jsonl"
    launcher = FakeLauncher({scripted["label"]: {"scripted_user_log": str(log_path)}})

    summary, _, _ = _run(base, p, launcher)
    assert all(row["outcome"] == "completed" for row in summary.outcomes.values())
    sent = json.loads((_archived(base, p, scripted) / "ws" / ".fake-session-new.json").read_text(encoding="utf-8"))
    assert sent["mcpServers"] == [server.entry(CLARIFICATIONS, log_path)]
    ordinary_sent = json.loads((_archived(base, p, ordinary) / "ws" / ".fake-session-new.json").read_text(encoding="utf-8"))
    assert ordinary_sent["mcpServers"] == []
    rows = [json.loads(line) for line in (_archived(base, p, scripted) / "scripted-user.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1] == {"kind": "end", "calls": 0, "client_initialized": False,
                        "tool_listed": True, "note": "no question asked"}
    assert not (_archived(base, p, ordinary) / "scripted-user.jsonl").exists()


def test_copilot_scripted_cell_uses_launch_config_and_never_session_mcp_servers(base):
    p = _plan(n_cells=1)
    cell = p["cells"][0]
    cell["harness"] = "copilot"
    p["tasks"] = {"X1": _scripted_task()}
    launcher = FakeLauncher({})
    cfg = engine.EngineConfig(run_dir=base / "runs" / p["run_id"], cells_root=base / "cells",
                              launchers={"copilot": launcher}, build_workspace=_build_workspace,
                              grade=None, end_grace=5)
    summary = _engine_run(p, cfg)
    assert summary.outcomes[cell["cell_id"]]["outcome"] == "completed"
    archived = _archived(base, p, cell)
    sent = json.loads((archived / "ws" / ".fake-session-new.json").read_text(encoding="utf-8"))
    assert sent["mcpServers"] == []
    log_path = base / "cells" / p["run_id"] / cell["cell_id"] / "scripted-user.jsonl"
    cfg = json.loads((archived / "mcp-config.json").read_text(encoding="utf-8"))
    entry = server.entry(CLARIFICATIONS, log_path)
    assert cfg == {"mcpServers": {"scripted_user": {"type": "local", "command": entry["command"],
                                     "args": entry["args"], "tools": ["*"],
                                     "env": {"SCRIPTED_USER_LOG": str(log_path)}}}}
    end = json.loads((archived / "scripted-user.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert end["note"] == "tool not reached" and end["tool_listed"] is False


def test_copilot_argv_is_exact_for_scripted_and_ordinary_cells(tmp_path):
    profile = profiles.load(ROOT, "copilot")
    build = tools.Build("copilot", "1.0.89-1", tmp_path / "copilot.exe", "a" * 64, None, None, None)
    base = [str(build.exe), "--acp", "--model", "gpt-6-sol", "--allow-tool", "shell", "--allow-tool", "write",
            "--disable-builtin-mcps", "--available-tools", "powershell", "list_powershell", "read_powershell",
            "stop_powershell", "apply_patch", "view", "glob", "rg", "skill"]
    assert profile.argv(build, "gpt-6-sol") == base
    cfg = tmp_path / "cell" / "mcp-config.json"
    assert profile.argv(build, "gpt-6-sol", mcp_config=cfg) == [
        *base, "scripted_user-ask_user", "--allow-tool", "scripted_user", "--additional-mcp-config", f"@{cfg}"]


def test_plan_freezes_scripted_user_hash_and_matcher_version():
    matrix = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    matrix["bom"]["subset"] = ["A1"]
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    builds = {"claude-code": {"version": "2.1.282", "sha256": "a" * 64},
              "codex": {"version": "0.156.0", "sha256": "b" * 64}}
    p = plan.build_plan(ROOT, matrix, bom, "scripted-user-plan", builds,
                        {"source": "../ai-forward", "commit": "c" * 40, "revision": 92})
    task = p["tasks"]["A1"]
    assert task["scripted_user"] is True
    assert task["clarifications_sha256"] == clarifications.load(CLARIFICATIONS).sha256
    assert task["matcher_version"] == matcher.MATCHER_VERSION
    assert Path(task["clarifications_path"]) == CLARIFICATIONS


def test_validate_rejects_malformed_scenario_one_clarifications(tmp_path):
    task_dir = tmp_path / "A1"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text((ROOT / "tasks" / "A1" / "task.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    oracle = task_dir / "oracle"
    oracle.mkdir()
    (oracle / "clarifications.yaml").write_text("schema: wrong\n", encoding="utf-8")
    problems = config.Problems()
    config.validate_task(task_dir, {"id": "A1", "scenario": 1, "budget_minutes": 15}, problems,
                         config.grader_modules(ROOT), [])
    assert any("clarifications.yaml" in item and "schema" in item for item in problems.items)
