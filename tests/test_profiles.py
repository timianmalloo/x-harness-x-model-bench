"""Harness profiles (ADR-0003, ADR-0004, ADR-0013): per-cell home, credential copy, static permissions, env."""

import json
import time
from pathlib import Path

import pytest

from harness_bench import driver, procs, profiles, tools

ROOT = Path(__file__).resolve().parents[1]


class FakeBuild:
    exe = Path("C:/tools/codex.exe")
    adapter = Path("C:/tools/adapter/dist/index.js")


def test_claude_profile_seeds_settings_and_a_credential_copy(tmp_path):
    cred = tmp_path / "src-cred.json"
    cred.write_text('{"secret": "x"}', encoding="utf-8")
    p = profiles.load(ROOT, "claude-code", credential_source=cred)
    home = tmp_path / "home"
    p.seed_home(home, model="claude-sonnet-5")
    settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["defaultMode"] == "dontAsk"
    assert set(settings["permissions"]["allow"]) == {"Bash", "Edit", "Write", "Read", "Glob", "Grep"}
    assert (home / ".credentials.json").read_text(encoding="utf-8") == '{"secret": "x"}'
    p.clean_home(home)  # T-CELL-credclean (profile half)
    assert not (home / ".credentials.json").exists() and (home / "settings.json").exists()


def test_codex_profile_pins_the_model_and_uses_full_access(tmp_path):
    cred = tmp_path / "auth.json"
    cred.write_text("{}", encoding="utf-8")
    p = profiles.load(ROOT, "codex", credential_source=cred)
    p.seed_home(tmp_path / "home", model="gpt-6-sol")
    assert 'model = "gpt-6-sol"' in (tmp_path / "home" / "config.toml").read_text(encoding="utf-8")
    assert p.mode == "agent-full-access"


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
    argv = p.argv(FakeBuild())
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
        cell = procs.spawn(p.argv(build), cwd=str(ws), env=env)
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
