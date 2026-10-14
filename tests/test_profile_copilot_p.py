"""ADR-0028 s3, s5, s7: the Copilot profile launches copilot -p through the local adapter with the combo's settings."""

import sys
from pathlib import Path

import pytest

from harness_bench import profiles, tools
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "bench" / "adapters" / "copilot_p_acp.py"
BUILD = tools.Build("copilot", "1.0.89-1", Path("C:/t/copilot.exe"), "a" * 64, ADAPTER, "0.1.0", "b" * 64)
TOOLS = ["powershell", "list_powershell", "read_powershell", "stop_powershell", "apply_patch", "view", "glob", "rg",
         "skill"]


def _child(home: Path, context="default", scenario=None) -> list[str]:
    argv = profiles.load(ROOT, "copilot").argv(BUILD, "gpt-6.1-sol", scenario=scenario, effort="high",
                                                context=context, home=home)
    assert argv[:5] == [sys.executable, str(ADAPTER), "--exe", str(BUILD.exe), "--"], "the bench python runs the adapter"
    return argv[5:]


def test_context_922000_puts_long_context_in_the_child_argv_and_default_puts_nothing(tmp_path):
    long, default = _child(tmp_path, "922000"), _child(tmp_path)
    i = long.index("--context")
    assert long[i:i + 2] == ["--context", "long_context"]
    assert "--context" not in default and "long_context" not in default
    assert long[:i] + long[i + 2:] == default


def test_the_child_argv_is_adr_0028s_with_the_tool_list_last(tmp_path, monkeypatch):
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(tmp_path / "no-uv-store"))  # the host's own store is not this test's subject
    assert _child(tmp_path) == [
        "--output-format", "json", "--model", "gpt-6.1-sol", "--reasoning-effort", "high",
        "--allow-tool", "shell", "--allow-tool", "write", "--add-dir", str(tmp_path), "--no-ask-user",
        "--disable-builtin-mcps",
        "--log-level", "debug", "--log-dir", f"{tmp_path}/logs", "--available-tools", *TOOLS]
    assert "--allow-all-tools" not in _child(tmp_path), "spike q1: the allowlist holds without it"


def test_a_scenario6_launch_extends_the_tool_list(tmp_path):  # profiles.argv appends the delegate ids at the end
    child = _child(tmp_path, scenario=6)
    assert child[child.index("--available-tools") + 1:] == [*TOOLS, *profiles.DELEGATE_IDS["copilot"]]


def test_the_settings_block_and_the_scripted_user_flag():
    p = profiles.load(ROOT, "copilot")
    assert p.scripted_user == "unsupported"
    assert p.settings["context"].values == ("default", "922000") and p.settings["context"].default_serves == 272000
    assert p.settings["context"].args == {"default": (), "922000": ("--context", "long_context")}
    assert "high" in p.settings["effort"].values and p.settings["effort"].apply == "placeholder"
    assert (p.mode, p.set_model, p.env["COPILOT_AUTO_UPDATE"]) == (None, False, "false")


def test_the_cell_home_is_HOME_USERPROFILE_and_an_allowed_directory_in_both_transports(tmp_path):
    """instr/w16 (owner decision 2026-10-14): a command naming $env:USERPROFILE or ~ stays inside the cell. Spike: with
    the variables at the cell home Copilot still denies the path unless the home is an allowed directory (--add-dir)."""
    p = profiles.load(ROOT, "copilot")
    env = p.cell_env({"PATH": "p", "HOME": "C:/Users/op", "USERPROFILE": "C:/Users/op", "APPDATA": "C:/Users/op/AppData"},
                     tmp_path / "home", BUILD, "gpt-6.1-sol", "")
    assert (env["HOME"], env["USERPROFILE"], env["COPILOT_HOME"]) == (str(tmp_path / "home"),) * 3
    assert env["APPDATA"] == "C:/Users/op/AppData", "uv's Python store lives under APPDATA, so it is left alone"
    for profile in (p, p.for_transport("acp")):
        argv = profile.argv(BUILD, "gpt-6.1-sol", effort="high", home=tmp_path / "home")
        assert argv[argv.index("--add-dir") + 1] == str(tmp_path / "home")
        assert argv.index("--add-dir") < argv.index("--available-tools"), "the tool list stays last"


def test_an_unmapped_context_is_refused(tmp_path):
    with pytest.raises(BenchError, match="HB-USR-002"):
        _child(tmp_path, "1000000")


@pytest.mark.parametrize("transport", [None, "acp"])
@pytest.mark.parametrize("pack", ["on", "off"])
def test_the_seeded_config_trusts_the_cell_worktree_in_both_arms_and_transports(tmp_path, pack, transport):
    """instr/w17 (coordinator decision 2026-10-14): `copilot -p` runs repo hooks only for a folder in the home's
    trustedFolders, so every cell seeds its worktree there, whatever the arm and the transport (Grok's precedent)."""
    import json

    profile = profiles.load(ROOT, "copilot")
    profile = profile if transport is None else profile.for_transport(transport)
    home, ws = tmp_path / pack / "home", tmp_path / pack / "ws"
    profile.seed_home(home, "gpt-6.1-sol", worktree=ws)
    config = json.loads((home / "config.json").read_text(encoding="utf-8"))
    assert config["trustedFolders"] == [str(ws)], "the backslashes of a Windows path are JSON-escaped"


@pytest.mark.parametrize("transport", [None, "acp"])
def test_the_hosts_uv_python_store_is_an_allowed_directory_when_it_exists(tmp_path, monkeypatch, transport):
    """instr/w17: a command listing the uv store under APPDATA was denied by Copilot's path verification (spike 2026-10-14),
    which makes the cell invalid (HB-VAL-012); the store is added as an allowed directory, resolved from the host."""
    store = tmp_path / "AppData" / "uv" / "python"
    store.mkdir(parents=True)
    monkeypatch.delenv("UV_PYTHON_INSTALL_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    profile = profiles.load(ROOT, "copilot")
    profile = profile if transport is None else profile.for_transport(transport)
    argv = profile.argv(BUILD, "gpt-6.1-sol", effort="high", home=tmp_path / "home")
    dirs = [argv[i + 1] for i, a in enumerate(argv) if a == "--add-dir"]
    assert dirs == [str(tmp_path / "home"), str(store)]
    assert max(i for i, a in enumerate(argv) if a == "--add-dir") < argv.index("--available-tools")
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(tmp_path / "elsewhere"))  # named but absent: no flag, no guess
    assert profile.argv(BUILD, "gpt-6.1-sol", effort="high", home=tmp_path / "home").count("--add-dir") == 1
