"""Harness profiles (ADR-0003, ADR-0004, ADR-0013): per-cell home, credential copy, static permissions, env."""

import importlib.util
import json
import shutil
import subprocess
import time
import tomllib
from pathlib import Path

import pytest

from harness_bench import driver, procs, profiles, tools
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def copilot_canary_module():
    spec = importlib.util.spec_from_file_location("us13_canary_setup", ROOT / "tests" / "e2e" / "test_us13_canary.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("removed", ["instruction", "skill", "hook", "settings model"])
def test_each_missing_copilot_control_class_is_void(copilot_canary_module, tmp_path, removed):
    home = tmp_path / "home"
    home.mkdir()
    pairs = copilot_canary_module._seed_copilot_control(home)  # also plants the two skill-root canaries at home/..
    assert (home / "copilot-instructions.md").is_file()
    assert (home / "skills" / copilot_canary_module.COPILOT_SKILL / "SKILL.md").is_file()
    assert json.loads((home / "hooks" / "us13-canary.json").read_text(encoding="utf-8"))["hooks"]["sessionStart"]
    assert json.loads((home / "settings.json").read_text(encoding="utf-8"))["model"] == copilot_canary_module.COPILOT_SETTINGS_MODEL

    marker = home / copilot_canary_module.COPILOT_HOOK_FILE
    marker.write_text(copilot_canary_module.COPILOT_HOOK, encoding="utf-8")
    record = "\n".join(canary for canary, cls in pairs if cls not in {"hook", "settings model"})
    models = {copilot_canary_module.COPILOT_SETTINGS_MODEL}
    assert all(copilot_canary_module._copilot_shown(record, models, home).values())

    if removed == "instruction":
        record = record.replace(copilot_canary_module.COPILOT_INSTRUCTION, "")
    elif removed == "skill":
        record = record.replace(copilot_canary_module.COPILOT_SKILL, "")
    elif removed == "hook":
        marker.unlink()
    else:
        models.clear()
    shown = copilot_canary_module._copilot_shown(record, models, home)
    assert [name for name, present in shown.items() if not present] == [removed]


def test_copilot_canary_model_oracle_reads_native_assistant_messages(copilot_canary_module):
    records = list((ROOT / "tests" / "fixtures" / "native" / "copilot" / "off").rglob("events.jsonl"))
    assert len(records) == 1
    assert copilot_canary_module._copilot_models(records) == {"gpt-6-sol"}


def test_copilot_settings_canary_is_advertised_and_not_the_pin(copilot_canary_module):  # TA W1-COP-I finding 2
    def model_lists(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from ([value] if key == "available_model_ids" else model_lists(value))
        elif isinstance(node, list):
            for value in node:
                yield from model_lists(value)

    provenance = json.loads((ROOT / "tests" / "fixtures" / "native" / "copilot" / "provenance.json").read_text(encoding="utf-8"))
    lists = list(model_lists(provenance))
    canary = copilot_canary_module.COPILOT_SETTINGS_MODEL
    assert lists and all(canary in advertised for advertised in lists)
    assert canary not in ("gpt-6-sol", "auto", copilot_canary_module.MODELS["copilot"])


def test_every_copilot_canary_turn_sees_the_fake_profile(copilot_canary_module, tmp_path, monkeypatch):  # TA finding 1
    """The blocker: the probe had the operator's real USERPROFILE/HOME, so a profile leak could not show. Now every turn
    sees the fake profile; only the isolated probe keeps the engine's COPILOT_HOME."""
    operator = tmp_path / "operator"
    for key, value in (("USERPROFILE", operator), ("HOME", operator), ("COPILOT_HOME", operator / ".copilot")):
        monkeypatch.setenv(key, str(value))
    p = profiles.load(ROOT, "copilot")
    profile = copilot_canary_module._fake_profile(tmp_path / "probe")
    assert profile == tmp_path / "probe" / "profile" and not operator.exists()
    dot = profile / ".copilot"
    assert {path.relative_to(dot).as_posix() for path in dot.rglob("*") if path.is_file()} == {
        "copilot-instructions.md", f"skills/{copilot_canary_module.COPILOT_SKILL}/SKILL.md", "hooks/us13-canary.json",
        "settings.json"}
    home = tmp_path / "probe" / "home"

    probe = copilot_canary_module._copilot_env(p, home, FakeBuild(), profile, isolated=True)
    assert (probe["COPILOT_HOME"], probe["USERPROFILE"], probe["HOME"]) == (str(home), str(profile), str(profile))
    control = copilot_canary_module._copilot_env(p, home, FakeBuild(), profile, isolated=False)
    assert not any(key.upper() == "COPILOT_HOME" for key in control)  # Copilot falls back to <USERPROFILE>/.copilot
    assert (control["USERPROFILE"], control["HOME"]) == (str(profile), str(profile))
    assert {k: v for k, v in control.items() if k != "COPILOT_HOME"} == {k: v for k, v in probe.items() if k != "COPILOT_HOME"}


def test_the_copilot_canary_profile_refuses_the_operators_profile(copilot_canary_module, tmp_path, monkeypatch):
    monkeypatch.setattr(copilot_canary_module, "USER", tmp_path / "profile")
    with pytest.raises(AssertionError, match="operator's profile"):
        copilot_canary_module._fake_profile(tmp_path)
    assert not (tmp_path / "profile").exists()


@pytest.mark.skipif(not (shutil.which("pwsh") or shutil.which("powershell")), reason="no PowerShell")
def test_the_copilot_hook_canary_writes_its_marker(copilot_canary_module, tmp_path):
    dot = copilot_canary_module._fake_profile(tmp_path / "control") / ".copilot"
    assert not copilot_canary_module._copilot_shown("", set(), dot)["hook"]
    (hook,) = json.loads((dot / "hooks" / "us13-canary.json").read_text(encoding="utf-8"))["hooks"]["sessionStart"]
    shell = shutil.which("pwsh") or shutil.which("powershell")
    subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", hook["powershell"]], check=True, timeout=60, cwd=tmp_path)
    assert copilot_canary_module._copilot_shown("", set(), dot)["hook"]


class FakeBuild:
    exe = Path("C:/tools/codex.exe")
    adapter = Path("C:/tools/adapter/dist/index.js")


def test_profile_registry_has_one_reader_build_and_yaml_per_harness():
    yaml_stems = {path.stem for path in (ROOT / "bench" / "profiles").glob("*.yaml")}
    assert set(profiles.HARNESSES) == set(profiles.READERS) == set(tools.LAYOUT) == yaml_stems


def test_copilot_profile_declares_native_acp_and_credential_store(tmp_path):
    p = profiles.load(ROOT, "copilot")
    assert (p.harness, p.home_env, p.credential_source, p.credential_name) == ("copilot", "COPILOT_HOME", None, None)
    assert p.files == {} and p.mode is None
    assert p.command[:8] == ("{exe}", "--acp", "--model", "{model}", "--allow-tool", "shell", "--allow-tool", "write")
    assert p.env == {"COPILOT_AUTO_UPDATE": "false"}
    assert (p.set_model, p.credential_kind) == (True, "subscription login (credential store)")
    assert (p.record_glob, p.usage_source, p.auxiliary_models) == (
        "session-state/{session_id}/events.jsonl", "native_record", ())


def test_copilot_null_credential_seeds_and_cleans_without_touching_other_files(tmp_path):
    p = profiles.Profile("copilot", "COPILOT_HOME", None, None, ("{exe}",))
    home = tmp_path / "home"
    p.seed_home(home, model="gpt-6-sol")
    sentinel = home / "events.jsonl"
    sentinel.write_text("native record", encoding="utf-8")
    p.clean_home(home)
    assert sentinel.read_text(encoding="utf-8") == "native record"
    assert profiles.ProfileLauncher(p, tmp_path, {}).credential_names == frozenset()


def test_existing_profiles_declare_commands_equal_to_the_old_adapter_argv(tmp_path):
    import shutil

    for harness in ("claude-code", "codex"):
        p = profiles.load(ROOT, harness, credential_source=tmp_path / "c")
        assert p.command == ("{node}", "{adapter}")
        assert p.argv(FakeBuild(), "model-is-unused") == [shutil.which("node"), str(FakeBuild.adapter)]


def test_existing_adapter_profiles_keep_the_old_argv_call_shape(tmp_path):
    import shutil

    for harness in ("claude-code", "codex"):
        p = profiles.load(ROOT, harness, credential_source=tmp_path / "c")
        assert p.argv(FakeBuild()) == [shutil.which("node"), str(FakeBuild.adapter)]


def test_copilot_argv_uses_the_pinned_exe_and_each_cells_model():
    p = profiles.load(ROOT, "copilot")
    for model in ("gpt-6-sol", "other-advertised-model"):
        assert p.argv(FakeBuild(), model)[:8] == [str(FakeBuild.exe), "--acp", "--model", model,
                                                   "--allow-tool", "shell", "--allow-tool", "write"]


def test_copilot_profile_has_r45_static_tool_flags():
    command = profiles.load(ROOT, "copilot").command
    required = ("--disable-builtin-mcps", "--available-tools", "powershell", "list_powershell",
                "read_powershell", "stop_powershell", "apply_patch", "view", "glob", "rg", "skill")
    missing = [flag for flag in required if flag not in command]
    assert not missing, f"Copilot profile missing R-45 flags/tools: {missing}"
    start = command.index("--available-tools")
    assert command[start + 1:] == required[2:]


def test_command_template_preserves_literal_braces(tmp_path):
    p = profiles.Profile("copilot", "COPILOT_HOME", None, None, ("{exe}", "{model}", "{literal}"))
    assert p.argv(FakeBuild(), "gpt-6-sol") == [str(FakeBuild.exe), "gpt-6-sol", "{literal}"]


@pytest.mark.parametrize("command", [None, []])
def test_profile_load_rejects_missing_or_empty_command(tmp_path, command):
    # W3-MUT-SWEEP: shutdown_grace_seconds is set so this raises for the command guard alone -- an
    # omitted grace also raises HB-USR-002 (line 133), which masked "profile command cannot be
    # empty" (tests/mutations/copilot.json) for the command=[] case: that mutation removed `not
    # command` from the line-127 check, the empty-command case fell through, and the test still
    # passed because the later grace check raised the same coded error for an unrelated reason. The Leader added vendor at the W3-S6 join (R-73 made it required and it masked the same guard).
    profile_dir = tmp_path / "bench" / "profiles"
    profile_dir.mkdir(parents=True)
    data = {"harness": "copilot", "home_env": "COPILOT_HOME", "credential": None,
            "record_glob": "events.jsonl", "shutdown_grace_seconds": 10, "vendor": "openai"}
    if command is not None:
        data["command"] = command
    import yaml

    (profile_dir / "copilot.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(BenchError, match="HB-USR-002"):
        profiles.load(tmp_path, "copilot")


def test_copilot_command_requires_an_explicit_model():
    p = profiles.load(ROOT, "copilot")
    with pytest.raises(ValueError, match="model is required"):
        p.argv(FakeBuild())


def test_command_template_rejects_an_adapter_placeholder_without_an_adapter(tmp_path):
    from harness_bench.errors import BenchError

    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "c")
    build = FakeBuild()
    build.adapter = None
    with pytest.raises(BenchError, match="HB-PRE-007"):
        p.argv(build, "gpt-6-sol")


def test_native_copilot_command_does_not_need_node_or_an_adapter(monkeypatch):
    p = profiles.load(ROOT, "copilot")
    build = FakeBuild()
    build.adapter = None
    monkeypatch.setattr(profiles.shutil, "which", lambda _: None)
    assert p.argv(build, "gpt-6-sol")[:8] == [str(build.exe), "--acp", "--model", "gpt-6-sol",
                                              "--allow-tool", "shell", "--allow-tool", "write"]


def test_adapter_command_rejects_missing_node(monkeypatch, tmp_path):
    from harness_bench.errors import BenchError

    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "c")
    monkeypatch.setattr(profiles.shutil, "which", lambda _: None)
    with pytest.raises(BenchError, match="HB-PRE-007"):
        p.argv(FakeBuild(), "gpt-6-sol")


def test_copilot_cell_env_drops_hosted_github_credentials_and_copilot_overrides(tmp_path):
    p = profiles.load(ROOT, "copilot")
    seeded = {name: "leak" for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN",
                                        "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR", "COPILOT_CUSTOM_INSTRUCTIONS_DIRS",
                                        "COPILOT_MODEL", "COPILOT_ALLOW_ALL")}
    env = p.cell_env({**seeded, "PATH": "safe"}, tmp_path / "home", FakeBuild(), "gpt-6-sol", "")
    assert all(name not in env for name in seeded)
    assert env["COPILOT_HOME"] == str(tmp_path / "home")
    assert env["COPILOT_AUTO_UPDATE"] == "false"
    assert env["PATH"] == "safe"


def test_copilot_launcher_reports_model_setter_and_credential_store(tmp_path):
    p = profiles.load(ROOT, "copilot")
    launcher = profiles.ProfileLauncher(p, tmp_path, {})
    assert (launcher.set_model, launcher.credential_kind, launcher.credential_names) == (
        True, "subscription login (credential store)", frozenset())


def test_copilot_launcher_fills_each_cells_model_and_finds_its_record(tmp_path):
    p = profiles.load(ROOT, "copilot")
    launcher = profiles.ProfileLauncher(p, tmp_path, {})
    launcher.build = FakeBuild()
    for model in ("gpt-6-sol", "second-model"):
        argv, _ = launcher.argv_env({"model": model}, tmp_path / "home", "")
        assert argv[3] == model
    record = tmp_path / "home" / "session-state" / "session-a" / "events.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text("{}\n", encoding="utf-8")
    assert launcher.records(tmp_path / "home", "session-a") == [record]


def test_claude_profile_seeds_settings_and_a_credential_copy(tmp_path):
    cred = tmp_path / "src-cred.json"
    cred.write_text('{"secret": "x"}', encoding="utf-8")
    p = profiles.load(ROOT, "claude-code", credential_source=cred)
    home = tmp_path / "home"
    p.seed_home(home, model="claude-sonnet-5")
    settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["defaultMode"] == "default"  # PR-2
    assert settings["disableClaudeAiConnectors"] is True  # R-56 c1, R-57 gate 2: no claude.ai MCP cloud connectors
    assert set(settings["permissions"]["allow"]) == {
        "Bash", "PowerShell", "Edit", "Write", "NotebookEdit", "Read", "Glob", "Grep",
        "mcp__scripted_user__ask_user"}  # R-34, R-35, R-37
    assert (home / ".credentials.json").read_text(encoding="utf-8") == '{"secret": "x"}'
    p.clean_home(home)  # T-CELL-credclean (profile half)
    assert not (home / ".credentials.json").exists() and (home / "settings.json").exists()


def test_shutdown_grace_is_a_bounded_profile_datum_and_reaches_launcher(tmp_path):  # PR-1
    from harness_bench import config

    for harness in ("claude-code", "codex", "copilot"):
        p = profiles.load(ROOT, harness)
        assert p.shutdown_grace == 10
        assert profiles.ProfileLauncher(p, ROOT / ".tools" / "harness", {}).shutdown_grace == 10
    target = tmp_path / "bench" / "profiles"
    target.mkdir(parents=True)
    source = config.load_yaml(ROOT / "bench" / "profiles" / "codex.yaml")
    source["shutdown_grace_seconds"] = 0.5
    import yaml

    (target / "codex.yaml").write_text(yaml.safe_dump(source), encoding="utf-8")
    assert profiles.load(tmp_path, "codex").shutdown_grace == 0.5
    from harness_bench import plan

    assert plan.profile_record(tmp_path, "codex")["shutdown_grace_seconds"] == "0.5"
    source["shutdown_grace_seconds"] = 11
    (target / "codex.yaml").write_text(yaml.safe_dump(source), encoding="utf-8")
    with pytest.raises(BenchError) as error:
        profiles.load(tmp_path, "codex")
    assert error.value.code == "HB-USR-002"


def test_claude_declared_mode_matches_the_recorded_effective_mode(tmp_path):  # PR-3, R-34 c4
    profile = profiles.load(ROOT, "claude-code", credential_source=tmp_path / "none")
    profile.seed_home(tmp_path / "home", "claude-opus-5-5")  # the seeded file: the template has a {delegate} slot (R-74)
    declared = json.loads((tmp_path / "home" / "settings.json").read_text(encoding="utf-8"))["permissions"]["defaultMode"]
    recording = ROOT / "tests" / "fixtures" / "acp" / "recordings" / "claude-code-x1.jsonl"
    messages = (json.loads(row["text"]) for line in recording.read_text(encoding="utf-8").splitlines()
                if (row := json.loads(line)).get("dir") == "to_client")
    effective = next(msg["result"]["modes"]["currentModeId"] for msg in messages
                     if msg.get("id") == 2 and "result" in msg)
    assert declared == effective == "default"


def test_codex_profile_pins_the_model_and_uses_full_access(tmp_path):
    cred = tmp_path / "auth.json"
    cred.write_text("{}", encoding="utf-8")
    p = profiles.load(ROOT, "codex", credential_source=cred)
    p.seed_home(tmp_path / "home", model="gpt-6-sol")
    assert 'model = "gpt-6-sol"' in (tmp_path / "home" / "config.toml").read_text(encoding="utf-8")
    assert 'web_search = "disabled"' in (tmp_path / "home" / "config.toml").read_text(encoding="utf-8")
    assert p.mode == "agent-full-access"


def test_codex_profile_disables_account_apps_in_each_seeded_home(tmp_path):
    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "auth.json")
    home = tmp_path / "home"
    p.seed_home(home, model="gpt-6-sol")
    config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    assert config["features"]["apps"] is False


def test_cell_env_is_clean_pinned_and_turns_build_servers_off(tmp_path):
    p = profiles.load(ROOT, "claude-code", credential_source=tmp_path / "c")
    base = {"PATH": "x", "CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli", "ANTHROPIC_API_KEY": "sk-leak",
            "OPENAI_API_KEY": "sk-leak", "CODEX_HOME": "C:/Users/me/.codex", "CLAUDE_CONFIG_DIR": "C:/Users/me/.claude"}
    env = p.cell_env(base, home=tmp_path / "home", build=FakeBuild(), model="claude-sonnet-5", traceparent="00-t-s-01")
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "home")
    assert env["ANTHROPIC_MODEL"] == "claude-sonnet-5"
    assert env["CLAUDE_CODE_EXECUTABLE"] == str(FakeBuild.exe)
    for gone in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_HOME"):
        assert gone not in env, gone
    assert env["MSBUILDDISABLENODEREUSE"] == "1" and env["UseSharedCompilation"] == "false"
    assert (env["GIT_CONFIG_COUNT"], env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == ("2", "core.fsmonitor", "false")
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("core.longpaths", "true")  # HB-PRE-005 for the agent's git
    assert env["TRACEPARENT"] == "00-t-s-01" and env["PATH"] == "x"


def _launcher(tmp_path, harness="codex"):
    from test_tools import _fake_tree
    tools_dir = _fake_tree(tmp_path / "tools")
    planned = tools.resolve(tools_dir)[harness].record()
    return profiles.ProfileLauncher(profiles.load(ROOT, harness, credential_source=tmp_path / "c"), tools_dir, planned), tools_dir


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
def test_the_launcher_reports_no_model_setter_and_a_copied_login(tmp_path, harness):  # R-13 condition 2
    launcher, _ = _launcher(tmp_path, harness)
    assert (launcher.set_model, launcher.credential_kind) == (False, "subscription login (copied)")


@pytest.mark.native
def test_a_real_profile_launcher_gets_the_engine_past_attempt_start(base, tmp_path):  # R-13: no AttributeError
    """The engine reads set_model and credential_kind from every launcher; a real ProfileLauncher (only its argv
    swapped for the fake agent, so no node is needed) must carry both."""
    import os
    import sys

    from test_engine import FAKE, _plan, _run
    launcher, _ = _launcher(tmp_path, "codex")
    launcher.argv_env = lambda cell, home, tp: ([sys.executable, str(FAKE)], launcher.profile.cell_env(
        dict(os.environ), home, launcher.build, cell["model"], tp))
    p = _plan(n_cells=1)
    _, events, _ = _run(base, p, launcher)
    started = [e for e in events if e["kind"] == "attempt.process_started"]
    assert [e["credential_kind"] for e in started] == ["subscription login (copied)"]
    assert [e for e in events if e["kind"] == "attempt.session_opened"]  # the turn ran past the handshake


def test_the_launcher_rehashes_the_build_at_every_cell_start(tmp_path):  # US-12, HB-CELL-115
    launcher, tools_dir = _launcher(tmp_path)
    assert launcher.check_build()["version"] == "0.156.0"
    exe = tools_dir / "node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    exe.write_text("self-updated", encoding="utf-8")
    with pytest.raises(tools.BuildChanged):
        launcher.check_build()


def test_the_launcher_speaks_for_its_profile(tmp_path):
    launcher, _ = _launcher(tmp_path)
    assert (launcher.harness, launcher.usage_source, launcher.credential_names) == ("codex", "native_record", frozenset({"auth.json"}))
    launcher.check_build()
    argv, env = launcher.argv_env({"model": "gpt-6-sol"}, tmp_path / "home", "00-t-s-01")
    assert argv[1].endswith("index.js") and env["CODEX_HOME"] == str(tmp_path / "home") and env["TRACEPARENT"] == "00-t-s-01"
    assert "OPENAI_API_KEY" not in env
    ex = launcher.read(ROOT / "tests" / "fixtures" / "native" / "codex" / "ok.jsonl")
    assert len(ex.model_calls) == 3


def test_argv_runs_the_pinned_adapter_with_node(tmp_path):
    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "c")
    argv = p.argv(FakeBuild(), "gpt-6-sol")
    assert argv[0].lower().endswith(("node.exe", "node")) and argv[1] == str(FakeBuild.adapter)


def test_native_records_are_found_by_session_id(tmp_path):
    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "c")
    home = tmp_path / "home"
    rec = home / "sessions" / "2026" / "09" / "23" / "rollout-2026-09-23T00-00-00-abc-123.jsonl"
    rec.parent.mkdir(parents=True)
    rec.write_text("{}\n", encoding="utf-8")
    assert p.native_records(home, "abc-123") == [rec]
    assert p.native_records(home, "other") == []


def test_token_source_and_auxiliary_models_are_declared_per_harness(tmp_path):
    claude = profiles.load(ROOT, "claude-code", credential_source=tmp_path / "c")
    codex = profiles.load(ROOT, "codex", credential_source=tmp_path / "c")
    assert (claude.usage_source, codex.usage_source) == ("acp_turn", "native_record")
    assert claude.model_allowed("claude-haiku-4-5-20251001", "claude-sonnet-5")
    assert claude.model_allowed("claude-sonnet-5", "claude-sonnet-5")
    assert not claude.model_allowed("claude-opus-5", "claude-sonnet-5")
    assert not codex.model_allowed("gpt-5", "gpt-6-sol")


def test_unknown_harness_is_refused():
    with pytest.raises(ValueError):
        profiles.load(ROOT, "grok")


# A real handshake per harness with the pinned builds and a per-cell home (no prompt, no model call).
@pytest.mark.native
@pytest.mark.credentials
@pytest.mark.parametrize("harness, model", [("claude-code", "claude-sonnet-5"), ("codex", "gpt-6-sol")])
def test_real_handshake_with_the_pinned_build(harness, model, tmp_path):
    base = Path("C:/Projects/bench-test") / f"hs-{harness}-{int(time.time())}"
    ws, home = base / "ws", base / "home"
    ws.mkdir(parents=True)
    p = profiles.load(ROOT, harness)
    build = tools.resolve(ROOT / ".tools" / "harness")[harness]
    p.seed_home(home, model=model)
    try:
        env = p.cell_env(dict(__import__("os").environ), home=home, build=build, model=model, traceparent="")
        cell = procs.spawn(p.argv(build, model), cwd=str(ws), env=env)
        try:
            result = driver.run_turn(cell, cwd=ws, prompt="unused", mode=p.mode, handshake_timeout=60,
                                     before_send=lambda sid: (_ for _ in ()).throw(KeyboardInterrupt))
        except KeyboardInterrupt:  # stop at the barrier: the handshake succeeded, no prompt is sent
            result = None
        finally:
            cell.terminate_and_confirm(timeout=15)
            cell.close()
        assert result is None, f"handshake failed: {result.cause} {result.detail}" if result else ""
    finally:
        p.clean_home(home)
        assert not any(home.glob(p.credential_name))
        import shutil
        shutil.rmtree(base, ignore_errors=True)
