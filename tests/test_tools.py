"""Pinned harness builds (ADR-0013 section 2; US-12): resolved by path, hashed, re-checked at every cell start."""

import json
from pathlib import Path

import pytest

from harness_bench import tools
from harness_bench.errors import BenchError, Cause

ROOT = Path(__file__).resolve().parents[1]


def _fake_tree(base: Path) -> Path:
    nm = base / "node_modules"
    files = {
        "@anthropic-ai/claude-agent-sdk/package.json": json.dumps({"version": "0.3.274", "claudeCodeVersion": "2.1.274"}),
        "@anthropic-ai/claude-agent-sdk-win32-x64/claude.exe": "claude-binary",
        "@agentclientprotocol/claude-agent-acp/dist/index.js": "adapter",
        "@agentclientprotocol/claude-agent-acp/package.json": json.dumps({"version": "0.79.0"}),
        "@openai/codex/package.json": json.dumps({"version": "0.156.0"}),
        "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe": "codex-binary",
        "@agentclientprotocol/codex-acp/dist/index.js": "adapter2",
        "@agentclientprotocol/codex-acp/package.json": json.dumps({"version": "1.12.0"}),
        "@github/copilot-win32-x64/package.json": json.dumps({"version": "1.0.89-1"}),
        "@github/copilot-win32-x64/copilot.exe": "copilot-binary",
    }
    for rel, text in files.items():
        f = nm / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return base


def test_resolve_names_version_executable_adapter_and_hash(tmp_path):
    builds = tools.resolve(_fake_tree(tmp_path))
    claude, codex = builds["claude-code"], builds["codex"]
    assert (claude.version, codex.version) == ("2.1.274", "0.156.0")
    assert claude.exe.name == "claude.exe" and codex.exe.name == "codex.exe"
    assert claude.adapter.name == "index.js" and "claude-agent-acp" in claude.adapter.as_posix()
    assert len(claude.sha256) == 64 and claude.sha256 != codex.sha256
    assert claude.record() == {"version": "2.1.274", "sha256": claude.sha256, "adapter_version": "0.79.0",
                               "adapter_sha256": claude.adapter_sha256}


def test_hash_covers_the_adapter_too(tmp_path):
    before = tools.resolve(_fake_tree(tmp_path))["claude-code"]
    (tmp_path / "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js").write_text("changed", encoding="utf-8")
    after = tools.resolve(tmp_path)["claude-code"]
    assert after.adapter_sha256 != before.adapter_sha256


def test_copilot_resolves_platform_build_without_adapter(tmp_path):
    copilot = tools.resolve(_fake_tree(tmp_path))["copilot"]
    assert copilot.version == "1.0.89-1"
    assert copilot.exe.name == "copilot.exe"
    assert len(copilot.sha256) == 64
    assert copilot.adapter is None
    assert copilot.record() == {"version": "1.0.89-1", "sha256": copilot.sha256,
                                "adapter_version": None, "adapter_sha256": None}
    tools.check_build(copilot, copilot.record())


def test_copilot_missing_exe_is_hb_pre_007(tmp_path):
    tree = _fake_tree(tmp_path)
    (tree / "node_modules/@github/copilot-win32-x64/copilot.exe").unlink()
    with pytest.raises(BenchError) as error:
        tools.resolve(tree)
    assert error.value.code == "HB-PRE-007"


def test_copilot_binary_change_is_detected_at_cell_start(tmp_path):
    tree = _fake_tree(tmp_path)
    planned = tools.resolve(tree)["copilot"].record()
    (tree / "node_modules/@github/copilot-win32-x64/copilot.exe").write_text("changed", encoding="utf-8")
    with pytest.raises(tools.BuildChanged) as error:
        tools.check_build(tools.resolve(tree)["copilot"], planned)
    assert error.value.cause is Cause.build_changed


def test_check_passes_on_the_planned_build(tmp_path):
    builds = tools.resolve(_fake_tree(tmp_path))
    tools.check_build(builds["codex"], builds["codex"].record())


def test_a_changed_binary_after_planning_is_build_changed_at_cell_start(tmp_path):  # T-CELL-build
    builds = tools.resolve(_fake_tree(tmp_path))
    planned = builds["codex"].record()
    builds["codex"].exe.write_text("auto-updated", encoding="utf-8")
    with pytest.raises(tools.BuildChanged) as e:
        tools.check_build(tools.resolve(tmp_path)["codex"], planned)
    assert e.value.cause is Cause.build_changed


def test_a_missing_build_is_hb_pre_007(tmp_path):
    with pytest.raises(BenchError) as e:
        tools.resolve(tmp_path)
    assert e.value.code == "HB-PRE-007"


def test_install_is_skipped_when_the_lockfile_is_unchanged(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "_npm_ci", lambda src, dest, timeout: calls.append(dest) or _fake_tree(dest))
    dest = tmp_path / "harness"
    tools.install(ROOT / "bench" / "tools", dest)
    tools.install(ROOT / "bench" / "tools", dest)
    assert len(calls) == 1


@pytest.mark.native
def test_real_install_resolves_the_pinned_builds():
    dest = ROOT / ".tools" / "harness"
    tools.install(ROOT / "bench" / "tools", dest, timeout=900)
    builds = tools.resolve(dest)
    assert builds["claude-code"].version == "2.1.282"
    assert builds["codex"].version == "0.156.0"
    assert builds["copilot"].version == "1.0.89-1"
    assert builds["copilot"].adapter is None
    assert builds["codex"].exe.is_file() and builds["claude-code"].exe.is_file()
