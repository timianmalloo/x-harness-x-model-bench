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

Lean re-run (ADR-0025 s8, ADR-0028):
- Grok 1.0.41 is an npm build. Its platform package ships only `bin/grok.exe.br`; the wrapper's postinstall unpacks
  it into `$GROK_HOME/bin/` (default `~/.grok`, the operator's real home) and rewrites `$GROK_HOME/config.toml`. So
  `npm ci` runs with `GROK_HOME` inside `node_modules`, and the cell runs that exe directly, never the npm shim
  (verified: a scratch `npm ci` of the pinned lockfile; the unpacked exe's sha256 is the spike copy's, 6db593f5...).
- Antigravity is a vendored exe: `bench/tools/vendored.json` pins its version and sha256, and `install_vendored`
  copies a named source into `.tools/agy/<version>/` (beside `.tools/harness`, so `npm ci` never removes it) only
  when the hash matches.
- Copilot's ACP adapter is a repo-local script whose path, version and sha256 live in
  `bench/adapters/copilot_p_acp.pin.json`, so an adapter fix edits that data file, never this module.
- Installed executables are made read-only. A harness none of whose installed files exist is left out of `resolve`,
  so a run needs only the builds its plan uses; a planned one that is absent is HB-PRE-007 at plan and preflight.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from harness_bench import config, procs
from harness_bench.errors import BenchError, Cause

STAMP = ".lock-sha256"
GROK_HOME_DIR = ".grok-home"  # under node_modules: `npm ci` removes it, so every install unpacks Grok afresh
VENDORED = Path("bench") / "tools" / "vendored.json"
COPILOT_PIN = "bench/adapters/copilot_p_acp.pin.json"  # R-COPILOT-P's data file: {path, version, sha256}

_DARWIN_TARGET_TRIPLE = {"arm64": "aarch64-apple-darwin", "x64": "x86_64-apple-darwin"}


@dataclass(frozen=True)
class ToolLayout:
    version_file: str | None  # None: a vendored exe, whose version is its pin in bench/tools/vendored.json
    version_key: str
    exe: str
    adapter: str | None  # an npm adapter package
    adapter_pin: str | None = None  # a repo-local adapter: its pin file, relative to the bench root


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
        suffix = ".exe"
    else:  # darwin
        arch = tag.rsplit("-", 1)[1]
        claude_exe, copilot_exe = f"@anthropic-ai/claude-agent-sdk-{tag}/claude", f"@github/copilot-{tag}/copilot"
        codex_exe = f"@openai/codex-{tag}/vendor/{_DARWIN_TARGET_TRIPLE[arch]}/bin/codex"
        suffix = ""
    return {
        "claude-code": ToolLayout("@anthropic-ai/claude-agent-sdk/package.json", "claudeCodeVersion", claude_exe,
                                  "@agentclientprotocol/claude-agent-acp"),
        "codex": ToolLayout("@openai/codex/package.json", "version", codex_exe, "@agentclientprotocol/codex-acp"),
        "copilot": ToolLayout(f"@github/copilot-{tag}/package.json", "version", copilot_exe, None, COPILOT_PIN),
        "grok": ToolLayout(f"@xai-official/grok-{tag}/package.json", "version", f"{GROK_HOME_DIR}/bin/grok{suffix}", None),
        "agy": ToolLayout(None, "version", f"agy{suffix}", None),
    }


LAYOUT = _layout(platform_tag())


class BuildChanged(Exception):
    """The planned build is not the one about to run (HB-CELL-115)."""

    def __init__(self, harness: str, detail: str) -> None:
        super().__init__(f"{Cause.build_changed.code}: {harness}: {detail}")
        self.cause = Cause.build_changed


class PinMismatch(BuildChanged, BenchError):
    """Installed bytes differ from their committed pin. A BenchError (HB-PRE-007) for plan and preflight, and a
    BuildChanged for the engine's cell-start check, which catches only BuildChanged (engine.py `launcher.check_build`),
    so a file changed during a run stops the run instead of escaping the cell thread."""

    def __init__(self, harness: str, detail: str) -> None:
        BenchError.__init__(self, "HB-PRE-007", f"{harness}: {detail}")
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
    adapter: Path | None  # the adapter's entry script: an npm package's, run with node, or a repo-local one's
    adapter_version: str | None
    adapter_sha256: str | None
    python_version: str = sys.version  # the bench interpreter: `{python}` in a profile command runs it
    python_path: str = sys.executable

    def record(self) -> dict:
        """What the plan freezes and every cell start re-checks. The interpreter identity is in every harness's
        record, so a plan frozen before it existed fails check_build on resume (HB-CELL-115; accepted, Leader addendum)."""
        return {"version": self.version, "sha256": self.sha256, "adapter_version": self.adapter_version,
                "adapter_sha256": self.adapter_sha256, "agent_version": None,
                "agent_version_reason": "ACP initialize.agentInfo.version requires a live handshake; not recorded at plan time",
                "python_version": self.python_version, "python_path": self.python_path}


def bench_root() -> Path:
    """The bench repository this module belongs to (cwd-independent): where the committed pin files live."""
    return config.repo_root(Path(__file__).resolve().parent)


def _pin(path: Path, harness: str, keys: tuple[str, ...], keyed: bool) -> dict:
    """One harness's committed pin (`keyed`: the file maps harness -> pin), refused (HB-PRE-007) when the file or a
    key is absent."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pin = data[harness] if keyed else data
        return {k: str(pin[k]) for k in keys}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BenchError("HB-PRE-007", f"{harness}: no usable pin in {path} ({type(exc).__name__}: {exc}); "
                                       f"it needs {list(keys)}") from exc


def vendored_exe(tools_dir: Path, harness: str, version: str) -> Path:
    return tools_dir.parent / harness / version / Path(LAYOUT[harness].exe).name


def _vendored_build(harness: str, tools_dir: Path, root: Path) -> Build | None:
    pin = _pin(root / VENDORED, harness, ("version", "sha256"), keyed=True)
    exe = vendored_exe(tools_dir, harness, pin["version"])
    if not exe.is_file():
        return None
    sha = _sha_file(exe)
    if sha != pin["sha256"]:
        raise PinMismatch(harness, f"{exe} sha256 {sha} differs from its pin {pin['sha256']} in {VENDORED.as_posix()}")
    return Build(harness, pin["version"], exe, sha, None, None, None)


def _pinned_adapter(harness: str, root: Path, pin_file: str) -> tuple[Path, str, str]:
    pin = _pin(root / pin_file, harness, ("path", "version", "sha256"), keyed=False)
    adapter = (root / pin["path"]).resolve()
    if root.resolve() not in adapter.parents:
        raise BenchError("HB-PRE-007", f"{harness}: adapter path {pin['path']!r} in {pin_file} is outside {root}")
    if not adapter.is_file():
        raise BenchError("HB-PRE-007", f"{harness}: missing adapter {adapter} (pinned in {pin_file})")
    sha = _sha_file(adapter)
    if sha != pin["sha256"]:
        raise PinMismatch(harness, f"adapter {adapter} sha256 {sha} differs from its pin {pin['sha256']} in {pin_file}")
    return adapter, pin["version"], sha


def resolve(tools_dir: Path, root: Path | None = None) -> dict[str, Build]:
    """Every installed harness build, re-hashed now; root holds the pin files (default: this repository)."""
    root = root or bench_root()
    nm = tools_dir / "node_modules"
    builds = {}
    for harness, spec in LAYOUT.items():
        if spec.version_file is None:
            vendored = _vendored_build(harness, tools_dir, root)
            if vendored is not None:
                builds[harness] = vendored
            continue
        version_file, exe = nm / spec.version_file, nm / spec.exe
        adapter_dir = nm / spec.adapter if spec.adapter is not None else None
        adapter = adapter_dir / "dist" / "index.js" if adapter_dir is not None else None
        required = (version_file, exe, adapter) if adapter is not None else (version_file, exe)
        missing = [p for p in required if not p.is_file()]
        if len(missing) == len(required):
            continue  # not installed: only a plan that uses it needs it (plan.build_plan and preflight refuse it then)
        if missing:
            raise BenchError("HB-PRE-007", f"{harness}: missing {missing[0]}; run `bench tools install`")
        version = json.loads(version_file.read_text(encoding="utf-8"))[spec.version_key]
        adapter_version = (json.loads((adapter_dir / "package.json").read_text(encoding="utf-8"))["version"]
                           if adapter_dir is not None else None)
        adapter_sha256 = _sha_tree(adapter_dir / "dist") if adapter_dir is not None else None
        if spec.adapter_pin is not None:
            adapter, adapter_version, adapter_sha256 = _pinned_adapter(harness, root, spec.adapter_pin)
        builds[harness] = Build(harness, version, exe, _sha_file(exe), adapter, adapter_version, adapter_sha256)
    if not builds:
        raise BenchError("HB-PRE-007", f"no harness build under {tools_dir}; run `bench tools install`")
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
    env = {**os.environ, "GROK_HOME": str(dest / "node_modules" / GROK_HOME_DIR)}  # Grok's postinstall writes there
    result = procs.run([node, str(cli), "ci", "--no-audit", "--no-fund"], cwd=str(dest), env=env, timeout=timeout)
    if result.timed_out or result.returncode != 0:
        raise BenchError("HB-PRE-007", f"npm ci failed ({result.returncode}): {result.stderr.strip()[-400:]}")


def _set_writable(path: Path, writable: bool) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(mode | stat.S_IWUSR if writable else mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _npm_exes(dest: Path) -> list[Path]:
    nm = dest / "node_modules"
    return [nm / s.exe for s in LAYOUT.values() if s.version_file is not None and (nm / s.exe).is_file()]


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
    for exe in _npm_exes(dest):  # npm ci removes node_modules, and a read-only file can refuse its removal
        _set_writable(exe, True)
    _npm_ci(src, dest, timeout)
    for exe in _npm_exes(dest):
        _set_writable(exe, False)
    stamp.write_text(digest, encoding="utf-8")


def install_vendored(source: Path, tools_dir: Path, root: Path | None = None) -> Build:
    """Copy a vendored harness exe into `.tools/<harness>/<version>/`, read-only, only when its sha256 is a pin in
    bench/tools/vendored.json (ADR-0025 s8); the pin it matches names the harness."""
    root = root or bench_root()
    if not source.is_file():
        raise BenchError("HB-PRE-007", f"no vendored source at {source}")
    sha = _sha_file(source)
    pins = {h: _pin(root / VENDORED, h, ("version", "sha256"), keyed=True)
            for h, spec in LAYOUT.items() if spec.version_file is None}
    harness = next((h for h, pin in pins.items() if pin["sha256"] == sha), None)
    if harness is None:
        pinned = ", ".join(f"{h} {p['version']} {p['sha256']}" for h, p in pins.items())
        raise BenchError("HB-PRE-007", f"{source}: sha256 {sha} matches no pin in {VENDORED.as_posix()} ({pinned})")
    dest = vendored_exe(tools_dir, harness, pins[harness]["version"])
    if not (dest.is_file() and _sha_file(dest) == sha):
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".partial")
        shutil.copyfile(source, tmp)
        if dest.exists():
            _set_writable(dest, True)
        os.replace(tmp, dest)
        _set_writable(dest, False)
    build = _vendored_build(harness, tools_dir, root)  # re-hashes the installed copy against the pin
    if build is None:
        raise BenchError("HB-PRE-007", f"{dest} is absent after the copy")
    return build


def cli_main(args) -> int:
    """`bench tools install --vendored SOURCE` (cli.cmd_tools; ADR-0025 s8)."""
    b = install_vendored(Path(args.vendored), Path(args.tools_dir), Path(args.root))
    print(f"{b.harness} {b.version} ({b.sha256[:12]}) installed read-only at {b.exe}")
    return 0
