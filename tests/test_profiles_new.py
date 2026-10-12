"""The Grok and Antigravity cell profiles (ADR-0025 s5, s6): what a cell launches with, read through the real loader
and launcher from `bench/profiles/{grok,agy}.yaml`."""

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_bench import archive, engine, profiles, stream_driver

ROOT = Path(__file__).resolve().parents[1]
BUILD = SimpleNamespace(exe=Path("C:/tools/harness.exe"), adapter=None)
PARENT_ENV = {"PATH": "C:/Windows", "XAI_API_KEY": "xai-not-a-key", "HOME": "C:/real-home", "USERPROFILE": "C:/real-home"}


def _launch(harness: str, tmp_path: Path, pack: str = "off", model: str = "grok-4.7", effort: str = "high"):
    """One cell laid out as the engine lays it out (cell_dir/home, cell_dir/ws): (argv, env, home, ws)."""
    cell_dir = tmp_path / pack
    home, ws = cell_dir / "home", cell_dir / "ws"
    ws.mkdir(parents=True)
    for name in profiles.load(ROOT, harness).files:  # R-SETTINGS's seed_home creates parents; not this test's subject
        (home / name).parent.mkdir(parents=True, exist_ok=True)
    bench_home = tmp_path / "bench-home"  # Grok seeds from the operator's bench credential home (ADR-0025 s7)
    bench_home.mkdir(exist_ok=True)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HB_GROK_CRED_HOME", str(bench_home))
        launcher = profiles.ProfileLauncher(profiles.load(ROOT, harness), tmp_path / "tools", {})
    launcher.build = BUILD
    cell = {"model": model, "pack": pack, "scenario": None, "effort": effort, "context": "default"}
    launcher.seed(home, cell)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(profiles.os, "environ", dict(PARENT_ENV))
        argv, env = launcher.argv_env(cell, home, "")
    return argv, env, home, ws, launcher


# --- Grok -------------------------------------------------------------------------------------------------------

def test_grok_env_puts_every_home_variable_in_the_cell(tmp_path):
    _, env, home, _, _ = _launch("grok", tmp_path)
    assert (env["HOME"], env["USERPROFILE"], env["GROK_HOME"]) == (str(home), str(home), f"{home}/.grok")


def test_grok_env_lacks_xai_api_key(tmp_path):  # R-SETTINGS dropped it
    _, env, _, _, _ = _launch("grok", tmp_path)
    assert "XAI_API_KEY" not in env


def test_grok_argv_pins_model_and_effort_before_stdio(tmp_path):
    argv, _, _, _, launcher = _launch("grok", tmp_path)
    assert argv == [str(BUILD.exe), "agent", "--model", "grok-4.7", "--reasoning-effort", "high", "stdio"]
    assert argv.index("--model") < argv.index("stdio") and argv.index("--reasoning-effort") < argv.index("stdio")
    assert launcher.set_model is True and launcher.transport == "acp"


def test_grok_config_turns_self_update_off(tmp_path):
    _, _, home, _, _ = _launch("grok", tmp_path)
    assert tomllib.loads((home / ".grok" / "config.toml").read_text(encoding="utf-8"))["cli"]["auto_update"] is False


@pytest.mark.parametrize("pack", ["on", "off"])  # seed_files {worktree}
def test_grok_trusts_the_worktree_in_both_arms(tmp_path, pack):
    _, _, home, ws, _ = _launch("grok", tmp_path, pack)
    folders = tomllib.loads((home / ".grok" / "trusted_folders.toml").read_text(encoding="utf-8"))["folders"]
    assert folders == {str(ws): {"trusted": True, "decided_at": 1791740000}}


def test_grok_never_copies_a_worker_credential(tmp_path):
    p = profiles.load(ROOT, "grok")
    # the source is resolved against the bench credential home, never the operator's own ~/.grok (CRED-COPY-A)
    assert (p.credential_source, p.credential_name, p.credential_home_env) == (
        Path("auth.json"), ".grok/auth.json", "HB_GROK_CRED_HOME")
    _, _, home, _, launcher = _launch("grok", tmp_path)  # an empty bench home: nothing to copy
    assert not list(home.rglob("auth.json"))
    launcher.clean(home)


def test_a_grok_cell_archive_excludes_its_seeded_credential(tmp_path, monkeypatch):  # R-TRANSPORT seam 4
    bench_home = tmp_path / "bench-home"
    bench_home.mkdir()
    (bench_home / "auth.json").write_text('{"token": "x"}', encoding="utf-8")
    monkeypatch.setenv("HB_GROK_CRED_HOME", str(bench_home))
    launcher = profiles.ProfileLauncher(profiles.load(ROOT, "grok"), tmp_path / "tools", {})
    cell_dir = tmp_path / "cell"
    (cell_dir / "ws").mkdir(parents=True)
    launcher.seed(cell_dir / "home", {"model": "grok-4.7", "scenario": None, "effort": "high", "context": "default"})
    try:
        assert (cell_dir / "home" / ".grok" / "auth.json").is_file()  # seeded from the bench home
        result = archive.archive_cell(cell_dir, tmp_path / "archive", 1, launcher.credential_names)
    finally:
        launcher.clean(cell_dir / "home")
    paths = {r["path"] for r in result.rows}
    assert "home/.grok/config.toml" in paths and not [p for p in paths if p.endswith("auth.json")]


def test_grok_reads_its_session_directory_and_its_alias():
    p = profiles.load(ROOT, "grok")
    assert (p.vendor, p.record_glob, p.usage_source) == ("xai", ".grok/sessions/*/{session_id}", "native_record")
    assert p.model_aliases == {"grok-4.7": ("grok-4.7-build",)}
    assert p.settings["effort"].values == ("low", "medium", "high", "xhigh")


# --- Antigravity --------------------------------------------------------------------------------------------------

def test_agy_env_disables_self_update_and_isolates_the_home(tmp_path):
    _, env, home, _, _ = _launch("agy", tmp_path, model="gemini-3.8-flash-high")
    assert env["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true"
    assert (env["HOME"], env["USERPROFILE"]) == (str(home), str(home))


def test_agy_argv_ends_with_p_equals_and_is_driven_by_the_stream_driver(tmp_path):
    argv, _, _, _, launcher = _launch("agy", tmp_path, model="gemini-3.8-flash-high")
    assert argv == [str(BUILD.exe), "--input-format", "stream-json", "--output-format", "stream-json",
                    "--model", "gemini-3.8-flash-high", "-p="]
    assert argv[-1] == "-p=" and "--dangerously-skip-permissions" not in argv
    assert engine.protocol_module(launcher) is stream_driver and launcher.set_model is False


def test_agy_seeds_the_allow_and_deny_rules(tmp_path):
    _, _, home, _, _ = _launch("agy", tmp_path, model="gemini-3.8-flash-high")
    settings = json.loads((home / ".gemini" / "antigravity-cli" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"permissions": {"allow": ["command(*)", "read_file(*)", "write_file(*)"],
                                        "deny": ["mcp(*)", "read_url(*)", "execute_url(*)"]}}


def test_agy_reads_the_teed_stream():
    p = profiles.load(ROOT, "agy")
    assert (p.vendor, p.record_glob, p.scripted_user) == ("google", stream_driver.STREAM_RECORD, "unsupported")
    assert p.credential_source is None and p.settings["effort"].apply == "model_id"


def test_both_new_harnesses_are_registered_with_their_readers():
    from harness_bench.telemetry import agy, grok

    assert {"grok", "agy"} <= set(profiles.HARNESSES)
    assert (profiles.READERS["grok"], profiles.READERS["agy"]) == (grok.read, agy.read)
