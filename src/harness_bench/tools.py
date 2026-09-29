"""Pinned harness builds in a bench-owned tools folder (ADR-0013 section 2; US-12).

Why: the report must name the build that was measured, and harness CLIs update themselves (the
installed Claude Code went 2.1.280 -> 2.1.281 during the 2026-09-23 session). So cells never run a CLI
from PATH: `bench/tools/package-lock.json` pins both ACP adapters, the Claude Code build bundled with
the adapter's SDK, Codex 0.156.0 (0.154.0 rejects gpt-6-sol, spike R11.5), and Copilot 1.0.89-1.
`npm ci` installs them
into `.tools/harness/`; each build is invoked by path and re-hashed at every cell start.

Platform (ADR-0013 Amendment 1, section 5): `bench/tools/package.json` depends on each harness's
platform-neutral wrapper package (`@anthropic-ai/claude-agent-sdk`, `@openai/codex`, `@github/copilot`);
npm's own `optionalDependencies` resolution installs only the folder matching the running host's
`os`/`cpu` (`win32-x64`, `darwin-arm64`, `darwin-x64`, ...) -- the pinned `package-lock.json` already
lists every platform variant (verified: `node_modules/@anthropic-ai/claude-agent-sdk-darwin-{arm64,x64}`,
`@openai/codex-darwin-{arm64,x64}` and `@github/copilot-darwin-{arm64,x64}` are all present rows), so no
lockfile change was needed for this port. `LAYOUT` below picks the matching folder name and binary path
for the current host; each name and its binary's path inside the package were checked against the
published npm registry (`registry.npmjs.org`) and the real tarball contents, not guessed:
- `@anthropic-ai/claude-agent-sdk-darwin-{arm64,x64}` (registry: package exists, 200) ships `claude` at
  its package root (verified: tarball listing of `claude-agent-sdk-darwin-arm64@0.3.284`).
- `@openai/codex-darwin-{arm64,x64}` is an npm alias (`"@openai/codex-darwin-x64": "npm:@openai/codex@<ver>-darwin-x64"`,
  read from `@openai/codex`'s own `optionalDependencies`, matching the existing win32-x64 row's alias
  shape) that still creates a `node_modules/@openai/codex-darwin-{arch}` folder; its binary is at
  `vendor/<target-triple>/bin/codex` (verified: tarball listing of `codex@0.156.0-darwin-arm64` and
  `-darwin-x64`, target triples `aarch64-apple-darwin` and `x86_64-apple-darwin`).
- `@github/copilot-darwin-{arm64,x64}` (registry: package exists, 200) ships `copilot` at its package
  root (verified: tarball listing of `copilot-darwin-arm64@1.0.89`).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from harness_bench import procs
from harness_bench.errors import BenchError, Cause

STAMP = ".lock-sha256"

_DARWIN_TARGET_TRIPLE = {"arm64": "aarch64-apple-darwin", "x64": "x86_64-apple-darwin"}


@dataclass(frozen=True)
class ToolLayout:
    version_file: str
    version_key: str
    exe: str
    adapter: str | None


def host_arch() -> str:
    """npm's own `cpu` tag for the running host: `arm64`, else `x64` (x86_64/AMD64; win32 pins x64 only,
    unchanged, ADR-0013 section 2: the operator's workstation)."""
    return "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"


def platform_tag(plat: str = sys.platform) -> str:
    """The npm platform suffix each harness publishes a package for (`win32-x64`, `darwin-arm64`,
    `darwin-x64`); ADR-0013 section 5 names Windows and macOS as the only supported hosts."""
    if plat == "win32":
        return "win32-x64"
    if plat == "darwin":
        return f"darwin-{host_arch()}"
    raise BenchError("HB-PRE-007", f"unsupported host platform {plat!r} (ADR-0013 section 5: Windows or macOS only)")


def _layout(tag: str) -> dict[str, ToolLayout]:
    if tag.startswith("win32"):
        claude_exe, copilot_exe = f"@anthropic-ai/claude-agent-sdk-{tag}/claude.exe", f"@github/copilot-{tag}/copilot.exe"
        codex_exe = f"@openai/codex-{tag}/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    else:  # darwin
        arch = tag.rsplit("-", 1)[1]
        claude_exe, copilot_exe = f"@anthropic-ai/claude-agent-sdk-{tag}/claude", f"@github/copilot-{tag}/copilot"
        codex_exe = f"@openai/codex-{tag}/vendor/{_DARWIN_TARGET_TRIPLE[arch]}/bin/codex"
    return {
        "claude-code": ToolLayout("@anthropic-ai/claude-agent-sdk/package.json", "claudeCodeVersion", claude_exe,
                                  "@agentclientprotocol/claude-agent-acp"),
        "codex": ToolLayout("@openai/codex/package.json", "version", codex_exe, "@agentclientprotocol/codex-acp"),
        "copilot": ToolLayout(f"@github/copilot-{tag}/package.json", "version", copilot_exe, None),
    }


LAYOUT = _layout(platform_tag())


class BuildChanged(Exception):
    """The planned build is not the one about to run (HB-CELL-115)."""

    def __init__(self, harness: str, detail: str) -> None:
        super().__init__(f"{Cause.build_changed.code}: {harness}: {detail}")
        self.cause = Cause.build_changed


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_tree(folder: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in folder.rglob("*") if p.is_file()):
        h.update(f.relative_to(folder).as_posix().encode() + b"\0")
        h.update(_sha_file(f).encode())
    return h.hexdigest()


@dataclass(frozen=True)
class Build:
    harness: str
    version: str
    exe: Path
    sha256: str
    adapter: Path | None  # the adapter's entry script, run with node when present
    adapter_version: str | None
    adapter_sha256: str | None

    def record(self) -> dict:
        """What the plan freezes and every cell start re-checks."""
        return {"version": self.version, "sha256": self.sha256, "adapter_version": self.adapter_version,
                "adapter_sha256": self.adapter_sha256, "agent_version": None,
                "agent_version_reason": "ACP initialize.agentInfo.version requires a live handshake; not recorded at plan time"}


def resolve(tools_dir: Path) -> dict[str, Build]:
    nm = tools_dir / "node_modules"
    builds = {}
    for harness, spec in LAYOUT.items():
        version_file, exe = nm / spec.version_file, nm / spec.exe
        adapter_dir = nm / spec.adapter if spec.adapter is not None else None
        adapter = adapter_dir / "dist" / "index.js" if adapter_dir is not None else None
        required = (version_file, exe, adapter) if adapter is not None else (version_file, exe)
        missing = [p for p in required if not p.is_file()]
        if missing:
            raise BenchError("HB-PRE-007", f"{harness}: missing {missing[0]}; run `bench tools install`")
        version = json.loads(version_file.read_text(encoding="utf-8"))[spec.version_key]
        adapter_version = (json.loads((adapter_dir / "package.json").read_text(encoding="utf-8"))["version"]
                           if adapter_dir is not None else None)
        adapter_sha256 = _sha_tree(adapter_dir / "dist") if adapter_dir is not None else None
        builds[harness] = Build(harness, version, exe, _sha_file(exe), adapter, adapter_version, adapter_sha256)
    return builds


def check_build(build: Build, planned: dict) -> None:
    """Raise BuildChanged unless the build about to run is exactly the planned one (US-12 AC1)."""
    actual = build.record()
    if actual != planned:
        changed = sorted(k for k in planned if planned.get(k) != actual.get(k))
        raise BuildChanged(build.harness, f"differs from the plan in {changed}")


def measured_version(argv: list[str], cwd: Path, timeout: float) -> str | None:
    """The last stdout line of a tool's version command, run now (R-59 c4: grading's tool versions are measured).
    None when it cannot be measured: not on PATH, cannot start, a non-zero exit, a timeout, or no output. Never a guess."""
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        done = procs.run([exe, *argv[1:]], cwd=str(cwd), env=dict(os.environ), timeout=timeout)
    except OSError:
        return None
    lines = done.stdout.strip().splitlines()
    return lines[-1].strip() if done.returncode == 0 and not done.timed_out and lines else None


def _npm_ci(src: Path, dest: Path, timeout: float) -> None:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        raise BenchError("HB-PRE-007", "node and npm are required to install the pinned harness builds")
    cli = Path(npm).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    result = procs.run([node, str(cli), "ci", "--no-audit", "--no-fund"], cwd=str(dest), env=None, timeout=timeout)
    if result.timed_out or result.returncode != 0:
        raise BenchError("HB-PRE-007", f"npm ci failed ({result.returncode}): {result.stderr.strip()[-400:]}")


def install(src: Path, dest: Path, timeout: float = 900) -> None:
    """Install the pinned set into dest; skipped when dest already holds this exact lockfile."""
    lock = src / "package-lock.json"
    digest = _sha_file(lock)
    stamp = dest / STAMP
    if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == digest and (dest / "node_modules").is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(src / name, dest / name)
    _npm_ci(src, dest, timeout)
    stamp.write_text(digest, encoding="utf-8")
