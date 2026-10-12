"""Pinned harness builds (ADR-0013 section 2; US-12; ADR-0025 s8): resolved by path, hashed, re-checked at every cell
start. Grok is an npm build; Antigravity a vendored exe pinned in bench/tools/vendored.json; Copilot's adapter is a
repo-local script pinned in bench/adapters/copilot_p_acp.pin.json (a fixture pin here, never the real one)."""

import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_bench import preflight, tools
from harness_bench.errors import BenchError, Cause

ROOT = Path(__file__).resolve().parents[1]
AGY_BYTES = b"agy-binary"
ADAPTER_BYTES = b"# copilot -p behind ACP (fixture)\n"
AGENT_REASON = "ACP initialize.agentInfo.version requires a live handshake; not recorded at plan time"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fake_root(base: Path) -> Path:
    """A bench root holding only the two pin files resolve reads: a fixture Copilot adapter and its pin, and
    vendored.json pinning agy to AGY_BYTES."""
    root = base / "repo"
    (root / "bench" / "adapters").mkdir(parents=True, exist_ok=True)
    (root / "bench" / "tools").mkdir(parents=True, exist_ok=True)
    (root / "bench" / "adapters" / "copilot_p_acp.py").write_bytes(ADAPTER_BYTES)
    _write_pin(root, version="0.1.0", sha256=_sha(ADAPTER_BYTES))
    (root / "bench" / "tools" / "vendored.json").write_text(
        json.dumps({"agy": {"version": "1.3.3", "sha256": _sha(AGY_BYTES)}}), encoding="utf-8")
    return root


def _write_pin(root: Path, **fields) -> None:
    pin = {"path": "bench/adapters/copilot_p_acp.py", **fields}
    (root / "bench" / "adapters" / "copilot_p_acp.pin.json").write_text(json.dumps(pin), encoding="utf-8")


def _fake_tree(base: Path, harnesses=None) -> Path:
    """A pinned-tools tree for the *running host's* platform (`tools.LAYOUT`), so this fixture matches
    whatever platform `tools.resolve` looks for -- win32-x64 on Windows, darwin-{arm64,x64} on macOS
    (ADR-0013 Amendment 1, section 5). The frozen values (versions, hashable binary contents) are
    unchanged from before the port. Only the npm builds: a vendored exe is installed by `_install_agy`.
    `harnesses` limits the tree to those harnesses (default: every npm build)."""
    nm = base / "node_modules"
    version_payload = {
        "claude-code": {"version": "0.3.274", "claudeCodeVersion": "2.1.274"},
        "codex": {"version": "0.156.0"},
        "copilot": {"version": "1.0.89-1"},
        "grok": {"version": "1.0.41"},
    }
    adapter_version = {"claude-code": "0.79.0", "codex": "1.12.0"}
    for harness, layout in tools.LAYOUT.items():
        if layout.version_file is None or (harnesses is not None and harness not in harnesses):
            continue
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


def _resolve(tree: Path) -> dict:
    return tools.resolve(tree, _fake_root(tree))


def _install_agy(tmp_path: Path, data: bytes = AGY_BYTES) -> tuple[Path, Path, Path]:
    """tools_dir, root, and the installed exe: the vendored source copied by `install_vendored`."""
    tools_dir = _fake_tree(tmp_path / "harness")
    root = _fake_root(tools_dir)
    source = tmp_path / "src" / "agy.exe"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(data)
    build = tools.install_vendored(source, tools_dir, root)
    return tools_dir, root, build.exe


def _writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def test_resolve_names_version_executable_adapter_and_hash(tmp_path):
    builds = _resolve(_fake_tree(tmp_path))
    claude, codex = builds["claude-code"], builds["codex"]
    assert (claude.version, codex.version) == ("2.1.274", "0.156.0")
    assert claude.exe.name == Path(tools.LAYOUT["claude-code"].exe).name
    assert codex.exe.name == Path(tools.LAYOUT["codex"].exe).name
    assert claude.adapter.name == "index.js" and "claude-agent-acp" in claude.adapter.as_posix()
    assert len(claude.sha256) == 64 and claude.sha256 != codex.sha256
    assert claude.record() == {"version": "2.1.274", "sha256": claude.sha256, "adapter_version": "0.79.0",
                               "adapter_sha256": claude.adapter_sha256, "agent_version": None,
                               "agent_version_reason": AGENT_REASON,
                               "python_version": sys.version, "python_path": sys.executable}


def test_hash_covers_the_adapter_too(tmp_path):
    before = _resolve(_fake_tree(tmp_path))["claude-code"]
    (tmp_path / "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js").write_text("changed", encoding="utf-8")
    after = _resolve(tmp_path)["claude-code"]
    assert after.adapter_sha256 != before.adapter_sha256


def test_copilot_resolves_platform_build_with_its_repo_local_adapter(tmp_path):
    tree = _fake_tree(tmp_path)
    root = _fake_root(tree)
    copilot = tools.resolve(tree, root)["copilot"]
    assert copilot.version == "1.0.89-1"
    assert copilot.exe.name == Path(tools.LAYOUT["copilot"].exe).name
    assert len(copilot.sha256) == 64
    assert copilot.adapter == (root / "bench" / "adapters" / "copilot_p_acp.py").resolve()
    assert copilot.record() == {"version": "1.0.89-1", "sha256": copilot.sha256,
                                "adapter_version": "0.1.0", "adapter_sha256": _sha(ADAPTER_BYTES), "agent_version": None,
                                "agent_version_reason": AGENT_REASON,
                                "python_version": sys.version, "python_path": sys.executable}
    tools.check_build(copilot, copilot.record())


def test_copilot_missing_exe_is_hb_pre_007(tmp_path):
    tree = _fake_tree(tmp_path)
    (tree / "node_modules" / tools.LAYOUT["copilot"].exe).unlink()
    with pytest.raises(BenchError) as error:
        _resolve(tree)
    assert error.value.code == "HB-PRE-007"


def test_resolve_requires_an_adapter_entry_script(tmp_path):
    tree = _fake_tree(tmp_path)
    missing = tree / "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js"
    missing.unlink()
    with pytest.raises(BenchError) as error:
        _resolve(tree)
    assert error.value.code == "HB-PRE-007"
    assert str(missing) in str(error.value)


def test_copilot_binary_change_is_detected_at_cell_start(tmp_path):
    tree = _fake_tree(tmp_path)
    planned = _resolve(tree)["copilot"].record()
    (tree / "node_modules" / tools.LAYOUT["copilot"].exe).write_text("changed", encoding="utf-8")
    with pytest.raises(tools.BuildChanged) as error:
        tools.check_build(_resolve(tree)["copilot"], planned)
    assert error.value.cause is Cause.build_changed


def test_check_passes_on_the_planned_build(tmp_path):
    builds = _resolve(_fake_tree(tmp_path))
    tools.check_build(builds["codex"], builds["codex"].record())


def test_a_changed_binary_after_planning_is_build_changed_at_cell_start(tmp_path):  # T-CELL-build
    builds = _resolve(_fake_tree(tmp_path))
    planned = builds["codex"].record()
    builds["codex"].exe.write_text("auto-updated", encoding="utf-8")
    with pytest.raises(tools.BuildChanged) as e:
        tools.check_build(_resolve(tmp_path)["codex"], planned)
    assert e.value.cause is Cause.build_changed


def test_a_missing_build_is_hb_pre_007(tmp_path):
    with pytest.raises(BenchError) as e:
        _resolve(tmp_path)
    assert e.value.code == "HB-PRE-007"


# Grok and Antigravity (ADR-0025 s8) ----------------------------------------------------------------

def test_layout_has_a_grok_and_an_agy_entry():
    assert {"grok", "agy"} <= set(tools.LAYOUT)
    grok, agy = tools._layout("win32-x64")["grok"], tools._layout("win32-x64")["agy"]
    # read from a scratch `npm ci` of the pinned lockfile (C:\tf\r-builds\tools): the platform package ships only
    # bin/grok.exe.br; its postinstall unpacks it into $GROK_HOME/bin, which install points inside node_modules.
    assert grok.version_file == "@xai-official/grok-win32-x64/package.json"
    assert grok.exe == ".grok-home/bin/grok.exe" and grok.adapter is None
    assert agy.version_file is None and agy.exe == "agy.exe" and agy.adapter is None
    assert tools._layout("darwin-arm64")["grok"].exe == ".grok-home/bin/grok"


def test_resolve_finds_grok_and_the_vendored_agy(tmp_path):
    tools_dir, root, exe = _install_agy(tmp_path)
    builds = tools.resolve(tools_dir, root)
    assert builds["grok"].version == "1.0.41" and builds["grok"].adapter is None
    grok = builds["grok"].record()
    assert (grok["adapter_version"], grok["adapter_sha256"]) == (None, None)  # an adapterless build records no adapter
    assert builds["agy"].version == "1.3.3" and builds["agy"].sha256 == _sha(AGY_BYTES)
    assert builds["agy"].exe == exe == tmp_path / "agy" / "1.3.3" / "agy.exe"  # .tools/agy/1.3.3/ beside .tools/harness


def test_a_plan_with_only_claude_code_resolves_without_a_grok_or_agy_build(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools", harnesses={"claude-code"})
    root = _fake_root(tmp_path)
    builds = tools.resolve(tools_dir, root)
    assert set(builds) == {"claude-code"}
    plan = {"builds": {"claude-code": builds["claude-code"].record()}}
    assert preflight.check(plan, base / "cells", tools_dir, min_free=1, long_paths=lambda: True)["free_bytes"] > 0


def test_a_partly_installed_grok_is_hb_pre_007(tmp_path):
    tree = _fake_tree(tmp_path)
    (tree / "node_modules" / tools.LAYOUT["grok"].exe).unlink()
    with pytest.raises(BenchError) as e:
        _resolve(tree)
    assert e.value.code == "HB-PRE-007" and "grok" in str(e.value)


def test_a_vendored_source_with_another_hash_is_refused(tmp_path):
    tools_dir = _fake_tree(tmp_path / "harness")
    source = tmp_path / "agy.exe"
    source.write_bytes(AGY_BYTES + b"!")
    with pytest.raises(BenchError) as e:
        tools.install_vendored(source, tools_dir, _fake_root(tools_dir))
    assert e.value.code == "HB-PRE-007" and _sha(AGY_BYTES + b"!") in str(e.value)
    assert not (tmp_path / "agy").exists()


def test_the_installed_vendored_exe_is_read_only_and_a_reinstall_keeps_it(tmp_path):
    tools_dir, root, exe = _install_agy(tmp_path)
    assert exe.read_bytes() == AGY_BYTES and not _writable(exe)
    source = tmp_path / "src" / "agy.exe"
    assert tools.install_vendored(source, tools_dir, root).exe == exe and not _writable(exe)


def test_install_makes_the_npm_executables_read_only_and_keeps_grok_out_of_the_real_home(tmp_path, monkeypatch):
    seen = []

    def fake_run(argv, cwd, env, timeout):
        seen.append(env)
        _fake_tree(Path(cwd))  # a reinstall rewrites every exe: it fails if the previous install left them read-only
        return SimpleNamespace(returncode=0, timed_out=False, stderr="")

    monkeypatch.setattr(tools.shutil, "which", lambda name: f"C:/fake/{name}")
    monkeypatch.setattr(tools.procs, "run", fake_run)
    dest = tmp_path / "harness"
    tools.install(ROOT / "bench" / "tools", dest)
    (dest / tools.STAMP).write_text("an older lockfile", encoding="utf-8")
    tools.install(ROOT / "bench" / "tools", dest)
    assert len(seen) == 2
    assert seen[0]["GROK_HOME"] == str(dest / "node_modules" / ".grok-home")  # Grok's postinstall writes $GROK_HOME
    for layout in tools.LAYOUT.values():
        if layout.version_file is not None:
            assert not _writable(dest / "node_modules" / layout.exe), layout.exe


def test_check_build_detects_a_one_byte_change_to_grok(tmp_path):
    tree = _fake_tree(tmp_path)
    planned = _resolve(tree)["grok"].record()
    exe = tree / "node_modules" / tools.LAYOUT["grok"].exe
    exe.write_bytes(exe.read_bytes() + b"x")
    with pytest.raises(tools.BuildChanged) as e:
        tools.check_build(_resolve(tree)["grok"], planned)
    assert e.value.cause is Cause.build_changed


def test_a_one_byte_change_to_the_vendored_exe_is_refused_at_resolve(tmp_path):
    tools_dir, root, exe = _install_agy(tmp_path)
    exe.chmod(0o666)
    exe.write_bytes(AGY_BYTES + b"x")
    with pytest.raises(tools.PinMismatch) as e:
        tools.resolve(tools_dir, root)
    # both: the CLI and preflight read HB-PRE-007, the engine's cell-start check catches BuildChanged (HB-CELL-115)
    assert isinstance(e.value, BenchError) and e.value.code == "HB-PRE-007"
    assert isinstance(e.value, tools.BuildChanged) and e.value.cause is Cause.build_changed


def test_a_new_vendored_build_after_planning_is_build_changed(tmp_path):
    tools_dir, root, _ = _install_agy(tmp_path)
    planned = tools.resolve(tools_dir, root)["agy"].record()
    newer = b"agy-binary-1.3.4"
    (root / "bench" / "tools" / "vendored.json").write_text(
        json.dumps({"agy": {"version": "1.3.4", "sha256": _sha(newer)}}), encoding="utf-8")
    source = tmp_path / "newer.exe"
    source.write_bytes(newer)
    tools.install_vendored(source, tools_dir, root)
    with pytest.raises(tools.BuildChanged) as e:
        tools.check_build(tools.resolve(tools_dir, root)["agy"], planned)
    assert "sha256" in str(e.value) and "version" in str(e.value)


def test_a_local_adapter_whose_bytes_differ_from_its_pin_is_refused_at_resolve(tmp_path):
    tree = _fake_tree(tmp_path)
    root = _fake_root(tree)
    (root / "bench" / "adapters" / "copilot_p_acp.py").write_bytes(ADAPTER_BYTES + b"# edited\n")
    with pytest.raises(tools.PinMismatch) as e:
        tools.resolve(tree, root)
    assert e.value.code == "HB-PRE-007" and "copilot" in str(e.value)


def test_a_local_adapter_changed_with_its_pin_after_planning_is_build_changed(tmp_path):
    tree = _fake_tree(tmp_path)
    root = _fake_root(tree)
    planned = tools.resolve(tree, root)["copilot"].record()
    fixed = ADAPTER_BYTES + b"# a later fix\n"
    (root / "bench" / "adapters" / "copilot_p_acp.py").write_bytes(fixed)
    _write_pin(root, version="0.1.1", sha256=_sha(fixed))
    with pytest.raises(tools.BuildChanged) as e:
        tools.check_build(tools.resolve(tree, root)["copilot"], planned)
    assert "adapter_sha256" in str(e.value) and "adapter_version" in str(e.value)


@pytest.mark.parametrize("pin", [None, {"path": "../outside.py", "version": "0.1.0", "sha256": _sha(ADAPTER_BYTES)},
                                 {"path": "bench/adapters/copilot_p_acp.py", "version": "0.1.0"}])
def test_a_missing_escaping_or_incomplete_adapter_pin_is_hb_pre_007(tmp_path, pin):
    tree = _fake_tree(tmp_path)
    root = _fake_root(tree)
    (root.parent / "outside.py").write_bytes(ADAPTER_BYTES)  # a real file whose hash matches: only the path check refuses it
    pin_file = root / "bench" / "adapters" / "copilot_p_acp.pin.json"
    if pin is None:
        pin_file.unlink()
    else:
        pin_file.write_text(json.dumps(pin), encoding="utf-8")
    with pytest.raises(BenchError) as e:
        tools.resolve(tree, root)
    assert e.value.code == "HB-PRE-007" and "copilot" in str(e.value)


def test_the_build_record_carries_the_bench_interpreter_and_an_older_record_is_build_changed(tmp_path):
    codex = _resolve(_fake_tree(tmp_path))["codex"]
    record = codex.record()
    assert (record["python_version"], record["python_path"]) == (sys.version, sys.executable)
    # The resume consequence (Leader addendum, accepted): a plan frozen before this field existed fails check_build.
    older = {k: v for k, v in record.items() if k not in ("python_version", "python_path")}
    with pytest.raises(tools.BuildChanged):
        tools.check_build(codex, older)


def test_cli_main_installs_the_vendored_source_and_names_it(tmp_path, capsys):
    tools_dir = _fake_tree(tmp_path / "harness")
    root = _fake_root(tools_dir)
    source = tmp_path / "agy.exe"
    source.write_bytes(AGY_BYTES)
    args = SimpleNamespace(root=str(root), tools_dir=str(tools_dir), vendored=str(source))
    assert tools.cli_main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"agy 1.3.3 ({_sha(AGY_BYTES)[:12]})") and str(tmp_path / "agy" / "1.3.3" / "agy.exe") in out


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
    assert layout["copilot"].adapter_pin == "bench/adapters/copilot_p_acp.pin.json"


def test_win32_layout_is_unchanged_by_the_darwin_port():
    layout = tools._layout("win32-x64")
    assert layout["claude-code"].exe == "@anthropic-ai/claude-agent-sdk-win32-x64/claude.exe"
    assert layout["codex"].exe == "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    assert layout["copilot"].exe == "@github/copilot-win32-x64/copilot.exe"


def test_resolve_on_a_fake_darwin_tree_finds_the_darwin_binaries(tmp_path, monkeypatch):
    """resolve() reads `tools.LAYOUT`, so pointing LAYOUT at the darwin tag (as import would on a real
    macOS host) makes it resolve a darwin-shaped tree, without needing that host to run this test."""
    monkeypatch.setattr(tools, "LAYOUT", tools._layout("darwin-arm64"))
    builds = _resolve(_fake_tree(tmp_path))
    assert builds["claude-code"].exe.as_posix().endswith("claude-agent-sdk-darwin-arm64/claude")
    assert builds["codex"].exe.as_posix().endswith("vendor/aarch64-apple-darwin/bin/codex")
    assert builds["copilot"].exe.as_posix().endswith("copilot-darwin-arm64/copilot")
    assert builds["grok"].exe.as_posix().endswith(".grok-home/bin/grok")


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
    assert builds["codex"].version == "0.160.0"
    assert builds["copilot"].version == "1.0.89-1"
    assert builds["grok"].version == "1.0.41"
    assert builds["grok"].sha256 == "6db593f5aeb1e12b1f4f36fac7fad34c2dfe8f9fcb853bff5fc01928c95c53fa"
    assert builds["copilot"].adapter.name == "copilot_p_acp.py"
    assert builds["codex"].exe.is_file() and builds["claude-code"].exe.is_file()
