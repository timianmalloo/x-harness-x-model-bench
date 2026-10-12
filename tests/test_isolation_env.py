"""R-SETTINGS: a cell's environment and home are the bench's, never the operator's (ADR-0025 s8; TEST-E found GROK_HOME,
AGY_X, GEMINI_API_KEY and GOOGLE_CLOUD_PROJECT reaching a codex cell, and no GIT_CONFIG_GLOBAL)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_bench import profiles, tools

ROOT = Path(__file__).resolve().parents[1]
PARENT = {"PATH": "p", "GROK_HOME": "C:/Users/op/.grok", "AGY_X": "1", "GEMINI_API_KEY": "k", "GOOGLE_CLOUD_PROJECT": "g",
          "gemini_lower": "k", "XAI_API_KEY": "k", "HB_GROK_CRED_HOME": "C:/bench/grok-cred",
          "GIT_CONFIG_GLOBAL": "C:/Users/op/.gitconfig"}


def _build(tmp_path: Path, harness: str) -> tools.Build:
    return tools.Build(harness, "1", tmp_path / "x.exe", "0" * 64, tmp_path / "adapter.js", "1", "0" * 64)


@pytest.mark.parametrize("harness", ["claude-code", "codex", "copilot"])
def test_no_grok_agy_gemini_or_google_variable_reaches_a_cell(tmp_path, harness):
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    env = p.cell_env(dict(PARENT), tmp_path, _build(tmp_path, harness), "m", "")
    leaked = sorted(k for k in env if k.upper().startswith(("GROK_", "AGY_", "GEMINI_", "GOOGLE_")))
    assert leaked == []
    assert "XAI_API_KEY" not in env and "HB_GROK_CRED_HOME" not in env
    assert env["PATH"] == "p"


@pytest.mark.parametrize("harness", ["claude-code", "codex", "copilot"])
def test_git_config_global_names_the_one_bench_file(tmp_path, harness):
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    env = p.cell_env(dict(PARENT), tmp_path, _build(tmp_path, harness), "m", "")
    assert env["GIT_CONFIG_GLOBAL"] == str(profiles.CELL_GITCONFIG)
    assert profiles.CELL_ENV["GIT_CONFIG_GLOBAL"] == str(profiles.CELL_GITCONFIG)


def test_the_cell_git_config_is_not_the_host_side_safe_config():
    """ADR-0010 B6: host git reads gitsafe's file; a cell that writes `git config --global` must not reach it."""
    from harness_bench import gitsafe

    assert profiles.CELL_GITCONFIG != gitsafe._safe_paths()[1]


def test_seed_home_creates_the_bench_git_config(tmp_path, monkeypatch):
    target = tmp_path / "bench-git" / "gitconfig"
    monkeypatch.setattr(profiles, "CELL_GITCONFIG", target)
    profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",)).seed_home(tmp_path / "home", "m")
    assert target.is_file()


def test_seed_home_creates_the_parents_of_a_nested_template(tmp_path):
    p = profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",), files={"a/b/c.toml": 'model = "{model}"'})
    p.seed_home(tmp_path / "home", "m")
    assert (tmp_path / "home" / "a" / "b" / "c.toml").read_text(encoding="utf-8") == 'model = "m"\n'


def test_seed_home_creates_the_parents_of_a_nested_credential_copy(tmp_path):
    source = tmp_path / "auth.json"
    source.write_text("tok", encoding="utf-8")
    p = profiles.Profile("grok", "GROK_HOME", source, ".grok/auth.json", ("{exe}",))
    p.seed_home(tmp_path / "home", "m")
    assert (tmp_path / "home" / ".grok" / "auth.json").read_text(encoding="utf-8") == "tok"
