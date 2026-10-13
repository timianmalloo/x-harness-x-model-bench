"""A harness is registered by its own files, never by an edit to a list in code (docs/runbooks/add-a-harness.md): its
profile bench/profiles/<name>.yaml, its reader src/harness_bench/telemetry/<name>.py, its build entry in
bench/tools/builds.yaml and, for a vendored exe, its pin in bench/tools/vendored.json. Its isolation rules (environment
variables to drop, instruction files to keep out of a base tree) are optional keys of its own profile."""

import json
from pathlib import Path

import pytest
import yaml

from harness_bench import config, identity, profiles, tools, workspace
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code

ROOT = config.repo_root(Path(__file__).resolve().parent)


class FakeBuild:
    exe = Path("C:/tools/codex.exe")
    adapter = Path("C:/tools/adapter/dist/index.js")


def _profile(root: Path, name: str, **extra) -> None:
    folder = root / "bench" / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(yaml.safe_dump({"harness": name, **extra}), encoding="utf-8")


def test_the_harness_list_is_the_profile_files(tmp_path):
    _profile(tmp_path, "zeta")
    _profile(tmp_path, "alpha")
    assert config.harness_names(tmp_path) == ("alpha", "zeta")


def test_the_repo_registry_is_its_profile_files():
    stems = tuple(sorted(p.stem for p in (ROOT / "bench" / "profiles").glob("*.yaml")))
    assert config.HARNESSES == profiles.HARNESSES == stems


def test_a_reader_is_found_by_its_module_name():
    assert profiles.reader_for("claude-code") is claude_code.read


def test_a_profile_without_its_reader_module_is_refused_by_name():
    with pytest.raises(BenchError) as exc:
        profiles.reader_for("no-such-cli")
    assert exc.value.code == "HB-USR-002"
    assert "telemetry/no_such_cli.py" in str(exc.value)


def test_a_build_layout_comes_from_builds_yaml(tmp_path):
    (tmp_path / "bench" / "tools").mkdir(parents=True)
    (tmp_path / "bench" / "tools" / "builds.yaml").write_text('newcli:\n  exe: "newcli{suffix}"\n', encoding="utf-8")
    assert tools._layout("win32-x64", tmp_path) == {"newcli": tools.ToolLayout(None, "version", "newcli.exe", None, None)}
    assert tools._layout("darwin-arm64", tmp_path)["newcli"].exe == "newcli"


@pytest.mark.parametrize(("tag", "suffix", "triple"), [("win32-x64", ".exe", "x86_64-pc-windows-msvc"),
                                                       ("darwin-arm64", "", "aarch64-apple-darwin"),
                                                       ("darwin-x64", "", "x86_64-apple-darwin")])
def test_the_five_layouts_are_the_ones_the_code_held(tag, suffix, triple):
    """Characterization: the layouts read from builds.yaml equal the literals tools._layout held before the move."""
    assert tools._layout(tag) == {
        "claude-code": tools.ToolLayout("@anthropic-ai/claude-agent-sdk/package.json", "claudeCodeVersion",
                                        f"@anthropic-ai/claude-agent-sdk-{tag}/claude{suffix}",
                                        "@agentclientprotocol/claude-agent-acp"),
        "codex": tools.ToolLayout("@openai/codex/package.json", "version", f"@openai/codex-{tag}/vendor/{triple}/bin/codex{suffix}",
                                  "@agentclientprotocol/codex-acp"),
        "copilot": tools.ToolLayout(f"@github/copilot-{tag}/package.json", "version", f"@github/copilot-{tag}/copilot{suffix}",
                                    None, "bench/adapters/copilot_p_acp.pin.json"),
        "grok": tools.ToolLayout(f"@xai-official/grok-{tag}/package.json", "version", f".grok-home/bin/grok{suffix}", None),
        "agy": tools.ToolLayout(None, "version", f"agy{suffix}", None),
    }


def test_the_grok_exe_is_where_install_unpacks_it():
    """builds.yaml names the folder tools.install points Grok's postinstall at; the two must not drift."""
    assert tools.LAYOUT["grok"].exe.startswith(f"{tools.GROK_HOME_DIR}/")


def test_every_vendored_build_has_its_pin():
    pins = json.loads((ROOT / "bench" / "tools" / "vendored.json").read_text(encoding="utf-8"))
    assert {h for h, spec in tools.LAYOUT.items() if spec.version_file is None} <= set(pins)


def test_a_new_reader_module_needs_no_class_entry(tmp_path):
    folder = tmp_path / "src" / "harness_bench" / "telemetry"
    folder.mkdir(parents=True)
    (folder / "newcli.py").write_text("", encoding="utf-8")
    assert identity.unclassed(tmp_path, identity.CLASSES, identity.PLANNED) == []
    assert identity._class("src/harness_bench/telemetry/newcli.py") == "run"


def test_a_profile_declares_its_own_isolation_rules(tmp_path):
    _profile(tmp_path, "older")
    _profile(tmp_path, "newcli", drop_env=["NEWCLI_*", "NEWCLI_KEY"],
             instruction_paths={"files": ["NEWCLI.md"], "trees": [".newcli"]})
    assert config.profile_isolation(tmp_path) == {"drop_env": ("NEWCLI_*", "NEWCLI_KEY"), "files": ("NEWCLI.md",),
                                                  "trees": (".newcli",)}


@pytest.mark.parametrize("extra", [{"drop_env": "NEWCLI_*"}, {"instruction_paths": {"files": "NEWCLI.md"}},
                                   {"instruction_paths": {"dirs": ["x"]}}])
def test_a_malformed_isolation_rule_is_refused(tmp_path, extra):
    _profile(tmp_path, "newcli", **extra)
    with pytest.raises(BenchError) as exc:
        config.profile_isolation(tmp_path)
    assert exc.value.code == "HB-USR-002"


def test_a_profile_drop_rule_reaches_every_harness_cell(monkeypatch):
    """Another harness's variables reach no cell: the drop rules are the union over every profile, not the cell's own."""
    monkeypatch.setattr(profiles, "PROFILE_DROPS", ("NEWCLI_*", "NEWCLI_KEY"))
    env = profiles.load(ROOT, "codex").cell_env({"NEWCLI_HOME": "x", "newcli_key": "k", "KEEP": "1"}, Path("C:/h"),
                                                FakeBuild, "gpt", "")
    assert "NEWCLI_HOME" not in env and "newcli_key" not in env and env["KEEP"] == "1"


def test_a_profile_instruction_rule_joins_the_built_in_ones(tmp_path):
    _profile(tmp_path, "newcli", instruction_paths={"files": ["NEWCLI.md"], "trees": [".newcli"]})
    files, trees = workspace.instruction_rules(tmp_path)
    assert {"AGENTS.md", "NEWCLI.md"} <= set(files)
    assert {".grok", ".newcli"} <= set(trees)
