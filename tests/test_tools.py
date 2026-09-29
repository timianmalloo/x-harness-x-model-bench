"""Pinned harness builds (ADR-0013 section 2; US-12): resolved by path, hashed, re-checked at every cell start."""

import json
from pathlib import Path

import pytest

from harness_bench import tools
from harness_bench.errors import BenchError, Cause

ROOT = Path(__file__).resolve().parents[1]


def _fake_tree(base: Path) -> Path:
    """A pinned-tools tree for the *running host's* platform (`tools.LAYOUT`), so this fixture matches
    whatever platform `tools.resolve` looks for -- win32-x64 on Windows, darwin-{arm64,x64} on macOS
    (ADR-0013 Amendment 1, section 5). The frozen values (versions, hashable binary contents) are
    unchanged from before the port."""
    nm = base / "node_modules"
    version_payload = {
        "claude-code": {"version": "0.3.274", "claudeCodeVersion": "2.1.274"},
        "codex": {"version": "0.156.0"},
        "copilot": {"version": "1.0.89-1"},
    }
    adapter_version = {"claude-code": "0.79.0", "codex": "1.12.0"}
    for harness, layout in tools.LAYOUT.items():
        vf = nm / layout.version_file
        vf.parent.mkdir(parents=True, exist_ok=True)
        vf.write_text(json.dumps(version_payload[harness]), encoding="utf-8")
        exe = nm / layout.exe
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text(f"{harness}-binary", encoding="utf-8")
        if layout.adapter is not None:
            adapter_dir = nm / layout.adapter
            (adapter_dir / "dist").mkdir(parents=True, exist_ok=True)
            (adapter_dir / "dist" / "index.js").write_text("adapter", encoding="utf-8")
            (adapter_dir / "package.json").write_text(json.dumps({"version": adapter_version[harness]}), encoding="utf-8")
    return base


def test_resolve_names_version_executable_adapter_and_hash(tmp_path):
    builds = tools.resolve(_fake_tree(tmp_path))
    claude, codex = builds["claude-code"], builds["codex"]
    assert (claude.version, codex.version) == ("2.1.274", "0.156.0")
    assert claude.exe.name == "claude.exe" and codex.exe.name == "codex.exe"
    assert claude.adapter.name == "index.js" and "claude-agent-acp" in claude.adapter.as_posix()
    assert len(claude.sha256) == 64 and claude.sha256 != codex.sha256
    assert claude.record() == {"version": "2.1.274", "sha256": claude.sha256, "adapter_version": "0.79.0",
                               "adapter_sha256": claude.adapter_sha256, "agent_version": None,
                               "agent_version_reason": "ACP initialize.agentInfo.version requires a live handshake; not recorded at plan time"}


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
                                "adapter_version": None, "adapter_sha256": None, "agent_version": None,
                                "agent_version_reason": "ACP initialize.agentInfo.version requires a live handshake; not recorded at plan time"}
    tools.check_build(copilot, copilot.record())


def test_copilot_missing_exe_is_hb_pre_007(tmp_path):
    tree = _fake_tree(tmp_path)
    (tree / "node_modules/@github/copilot-win32-x64/copilot.exe").unlink()
    with pytest.raises(BenchError) as error:
        tools.resolve(tree)
    assert error.value.code == "HB-PRE-007"


def test_resolve_requires_an_adapter_entry_script(tmp_path):
    tree = _fake_tree(tmp_path)
    missing = tree / "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js"
    missing.unlink()
    with pytest.raises(BenchError) as error:
        tools.resolve(tree)
    assert error.value.code == "HB-PRE-007"
    assert str(missing) in str(error.value)


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


# macOS port (ADR-0013 Amendment 1, section 5) -------------------------------------------------

def test_platform_tag_is_win32_x64_on_windows():
    assert tools.platform_tag("win32") == "win32-x64"


def test_platform_tag_is_darwin_arm64_or_x64_by_host_arch(monkeypatch):
    monkeypatch.setattr(tools.platform, "machine", lambda: "arm64")
    assert tools.platform_tag("darwin") == "darwin-arm64"
    monkeypatch.setattr(tools.platform, "machine", lambda: "x86_64")
    assert tools.platform_tag("darwin") == "darwin-x64"
    monkeypatch.setattr(tools.platform, "machine", lambda: "aarch64")  # some Python builds report this on arm64
    assert tools.platform_tag("darwin") == "darwin-arm64"


def test_platform_tag_refuses_an_unsupported_host():  # ADR-0013 section 5: Windows or macOS only
    with pytest.raises(BenchError) as e:
        tools.platform_tag("linux")
    assert e.value.code == "HB-PRE-007"


@pytest.mark.parametrize("arch,triple", [("arm64", "aarch64-apple-darwin"), ("x64", "x86_64-apple-darwin")])
def test_darwin_layout_names_the_published_npm_packages_and_their_binary_path(arch, triple):
    """Every path checked against the real npm registry and tarball contents (module doc): the wrapper
    packages ship `claude`/`copilot` at their root, `@openai/codex-darwin-<arch>` (an npm alias, same
    shape as the existing win32-x64 row) ships `codex` under `vendor/<target-triple>/bin/`."""
    layout = tools._layout(f"darwin-{arch}")
    assert layout["claude-code"].exe == f"@anthropic-ai/claude-agent-sdk-darwin-{arch}/claude"
    assert layout["codex"].exe == f"@openai/codex-darwin-{arch}/vendor/{triple}/bin/codex"
    assert layout["copilot"].exe == f"@github/copilot-darwin-{arch}/copilot"
    assert layout["copilot"].version_file == f"@github/copilot-darwin-{arch}/package.json"
    # the wrapper-package version files and adapter names never change with platform
    assert layout["claude-code"].version_file == "@anthropic-ai/claude-agent-sdk/package.json"
    assert layout["codex"].version_file == "@openai/codex/package.json"
    assert layout["claude-code"].adapter == "@agentclientprotocol/claude-agent-acp"
    assert layout["codex"].adapter == "@agentclientprotocol/codex-acp"
    assert layout["copilot"].adapter is None


def test_win32_layout_is_unchanged_by_the_darwin_port():
    layout = tools._layout("win32-x64")
    assert layout["claude-code"].exe == "@anthropic-ai/claude-agent-sdk-win32-x64/claude.exe"
    assert layout["codex"].exe == "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    assert layout["copilot"].exe == "@github/copilot-win32-x64/copilot.exe"


def test_resolve_on_a_fake_darwin_tree_finds_the_darwin_binaries(tmp_path, monkeypatch):
    """resolve() reads `tools.LAYOUT`, so pointing LAYOUT at the darwin tag (as import would on a real
    macOS host) makes it resolve a darwin-shaped tree, without needing that host to run this test."""
    monkeypatch.setattr(tools, "LAYOUT", tools._layout("darwin-arm64"))
    builds = tools.resolve(_fake_tree(tmp_path))
    assert builds["claude-code"].exe.as_posix().endswith("claude-agent-sdk-darwin-arm64/claude")
    assert builds["codex"].exe.as_posix().endswith("vendor/aarch64-apple-darwin/bin/codex")
    assert builds["copilot"].exe.as_posix().endswith("copilot-darwin-arm64/copilot")


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
