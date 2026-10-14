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
def test_git_config_global_is_a_file_in_the_cell_home(tmp_path, harness):
    """Leader ruling (r-settings-rerun-2): one global git config per cell, inside its home, never a shared file."""
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    env_a = p.cell_env(dict(PARENT), tmp_path / "a", _build(tmp_path, harness), "m", "")
    env_b = p.cell_env(dict(PARENT), tmp_path / "b", _build(tmp_path, harness), "m", "")
    assert env_a["GIT_CONFIG_GLOBAL"] == str(tmp_path / "a" / profiles.CELL_GITCONFIG_NAME)
    assert env_b["GIT_CONFIG_GLOBAL"] == str(tmp_path / "b" / profiles.CELL_GITCONFIG_NAME)
    assert "GIT_CONFIG_GLOBAL" not in profiles.CELL_ENV


def test_a_cell_git_config_write_is_not_visible_to_another_cell(tmp_path):
    p = profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",))
    homes = [tmp_path / "a", tmp_path / "b"]
    for home in homes:
        p.seed_home(home, "m")
    with (homes[0] / profiles.CELL_GITCONFIG_NAME).open("a", encoding="utf-8") as f:
        f.write("[core]\n\tpager = planted\n")
    assert "planted" not in (homes[1] / profiles.CELL_GITCONFIG_NAME).read_text(encoding="utf-8")


def test_the_cell_git_config_carries_the_bench_identity_and_is_not_host_git_s(tmp_path):
    """An agent's commit works the same in every harness; ADR-0010 B6: host git's own file is never the cell's."""
    import subprocess

    from harness_bench import gitsafe

    p = profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",))
    p.seed_home(tmp_path / "home", "m")
    path = tmp_path / "home" / profiles.CELL_GITCONFIG_NAME
    assert path != gitsafe._safe_paths()[1]
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"], env["GIT_CONFIG_NOSYSTEM"] = str(path), "1"
    got = [subprocess.run(["git", "config", "--global", key], capture_output=True, text=True, env=env, check=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
           for key in ("user.name", "user.email")]
    assert got == [gitsafe.BENCH_IDENTITY["GIT_AUTHOR_NAME"], gitsafe.BENCH_IDENTITY["GIT_AUTHOR_EMAIL"]]


# --- user_home_vars and seed_files (ADR-0025 s5-s6; Leader ruling r-settings-rerun-2) ---------------------------

def test_user_home_vars_name_the_cell_home(tmp_path):
    p = profiles.Profile("grok", "GROK_HOME", None, None, ("{exe}",), user_home_vars=("HOME", "USERPROFILE"),
                         env={"GROK_HOME": "{home}/.grok"})
    env = p.cell_env({"PATH": "p", "HOME": "C:/Users/op", "USERPROFILE": "C:/Users/op"}, tmp_path / "home",
                     _build(tmp_path, "grok"), "m", "")
    assert (env["HOME"], env["USERPROFILE"]) == (str(tmp_path / "home"), str(tmp_path / "home"))
    assert env["GROK_HOME"] == f"{tmp_path / 'home'}/.grok"


def test_seed_files_are_written_with_the_home_and_the_worktree(tmp_path):
    p = profiles.Profile("grok", "GROK_HOME", None, None, ("{exe}",), seed_files={
        ".grok/trusted_folders.toml": "[[folders]]\npath = '{worktree}'\n",
        ".grok/config.toml": "[cli]\nauto_update = false\nhome = '{home}'",
    })
    home, ws = tmp_path / "home", tmp_path / "ws"
    p.seed_home(home, "m", worktree=ws)
    assert (home / ".grok" / "trusted_folders.toml").read_text(encoding="utf-8") == f"[[folders]]\npath = '{ws}'\n"
    assert (home / ".grok" / "config.toml").read_text(encoding="utf-8") == \
        f"[cli]\nauto_update = false\nhome = '{home}'\n"


def test_a_seed_file_naming_the_worktree_needs_one(tmp_path):
    from harness_bench.errors import BenchError

    p = profiles.Profile("grok", "GROK_HOME", None, None, ("{exe}",), seed_files={"t.toml": "path = '{worktree}'"})
    with pytest.raises(BenchError) as err:
        p.seed_home(tmp_path / "home", "m")
    assert err.value.code == "HB-USR-002" and "{worktree}" in err.value.message


def test_the_launcher_seeds_the_worktree_beside_the_cell_home(tmp_path):
    """The engine lays a cell out as <cell>/home and <cell>/ws (engine._run_cell); the launcher's worktree is that ws."""
    import inspect

    from harness_bench import engine

    assert 'home, ws = cell_dir / "home", cell_dir / "ws"' in inspect.getsource(engine.Engine._run_cell)
    p = profiles.Profile("grok", "GROK_HOME", None, None, ("{exe}",), seed_files={"t.toml": "path = '{worktree}'"})
    profiles.ProfileLauncher(p, tmp_path, {}).seed(tmp_path / "cell" / "home", {"model": "m"})
    assert (tmp_path / "cell" / "home" / "t.toml").read_text(encoding="utf-8") == f"path = '{tmp_path / 'cell' / 'ws'}'\n"


@pytest.mark.parametrize("harness", ["claude-code", "codex"])  # Copilot differs since instr/w16 (owner decision 2026-10-14)
def test_the_existing_profiles_declare_no_home_vars_or_seed_files(tmp_path, harness):
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    assert (p.user_home_vars, p.seed_files) == ((), {})
    env = p.cell_env({"PATH": "p", "HOME": "C:/Users/op"}, tmp_path, _build(tmp_path, harness), "m", "")
    assert env["HOME"] == "C:/Users/op"


# --- host_skill_roots (instr/w10, owner decision B12) ----------------------------------------------------------------

def test_host_skill_roots_are_disabled_one_by_one_in_the_cell_config(tmp_path):
    """Codex finds ~/.agents/skills through the Windows known folder, so moving HOME and USERPROFILE does not hide it
    (spike 2026-10-14). The cell config names each host skill file disabled; a repo skill is a different path."""
    import tomllib

    host = tmp_path / "host" / ".agents" / "skills"
    for name in ("alpha", "alpha/nested", "beta"):
        (host / name).mkdir(parents=True)
        (host / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    (host / "beta" / "notes.md").write_text("not a skill", encoding="utf-8")
    p = profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",), files={"config.toml": 'model = "{model}"'},
                         host_skill_roots=(str(host), str(tmp_path / "absent")))
    p.seed_home(tmp_path / "home", "m")
    cfg = tomllib.loads((tmp_path / "home" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["model"] == "m"
    assert sorted(cfg["skills"]["config"], key=lambda e: e["path"]) == sorted(
        ({"path": (host / name / "SKILL.md").as_posix(), "enabled": False} for name in ("alpha", "alpha/nested", "beta")),
        key=lambda e: e["path"])


def test_a_profile_without_host_skill_roots_writes_its_config_unchanged(tmp_path):
    p = profiles.Profile("codex", "CODEX_HOME", None, None, ("{exe}",), files={"config.toml": 'model = "{model}"'})
    p.seed_home(tmp_path / "home", "m")
    assert (tmp_path / "home" / "config.toml").read_text(encoding="utf-8") == 'model = "m"\n'


def test_the_codex_profile_hides_the_operator_skills_and_keeps_the_cell_home(tmp_path):
    p = profiles.load(ROOT, "codex", credential_source=tmp_path / "absent")
    assert p.host_skill_roots == ("~/.agents/skills",)
    env = p.cell_env(dict(PARENT), tmp_path / "home", _build(tmp_path, "codex"), "m", "")
    assert env["CODEX_HOME"] == str(tmp_path / "home")


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
