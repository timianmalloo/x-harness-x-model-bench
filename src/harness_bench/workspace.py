"""Each cell's own working copy (ADR-0013; US-8, US-9, US-49).

- The task source: one bench-owned local repository per task version, holding only the task's base
  tree (`tasks/<ID>/workspace/`), never its hidden tests or oracle, with no remote.
- A cell's working copy: `git clone --local` of the task source (objects hardlinked; refs, stash and
  config not shared), then `git remote remove origin`, so the cell has no remote and cannot see any
  other cell's git state. (Worktrees of one clone share refs and stash: rejected at the design gate.)
- pack=on: the pinned pack revision is installed with `pack-apply.py apply --install --json` (probe
  W1) and committed before the clock starts; its JSON rows are the pack manifest (US-9).
- The cells root must have no agent instruction file above it (HB-PRE-002, spike R1.3).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

from harness_bench import gitsafe, procs
from harness_bench.errors import BenchError

INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md")
GIT_TIMEOUT = 120
# pack-apply rows that wrote a file; SKIP and UNCHANGED rows name no change (probe W1)
WRITE_ACTIONS = ("ADD", "UPDATE", "MERGE")


def check_cells_root(root: Path) -> None:
    """Refuse a cells root with an agent instruction file in it or in any ancestor (HB-PRE-002)."""
    resolved = root.resolve()
    for folder in (resolved, *resolved.parents):
        for name in INSTRUCTION_FILES:
            if (folder / name).is_file():
                raise BenchError("HB-PRE-002", f"{folder / name} is above the cells root {root}; every cell would load it")


def _fresh(dest: Path) -> Path:
    tmp = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
    tmp.mkdir(parents=True)
    return tmp


def _land(tmp: Path, dest: Path, valid) -> Path:
    """Publish tmp as dest. A build is content-addressed and written once: when two callers race to
    build the same dest, `os.replace` fails for whichever lands second (HB-CELL-113, Windows cannot
    rename onto a non-empty dest). If dest is by then a valid build, the other writer won; discard
    tmp (the caller's `finally` does that) and hand back dest. Any other failure is real and propagates.
    """
    try:
        os.replace(tmp, dest)
    except OSError:
        if not valid(dest):
            raise
    return dest


def task_source(task_dir: Path, version: str, sources_root: Path) -> Path:
    """The bench-owned repository of one task version's base tree (created once, then reused)."""
    dest = sources_root / task_dir.name / version[:16]
    if (dest / ".git").is_dir():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = _fresh(dest)
    try:
        shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True)
        gitsafe.git(["init", "-q", "-b", "main"], cwd=tmp, timeout=GIT_TIMEOUT)
        gitsafe.git(["add", "-A"], cwd=tmp, timeout=GIT_TIMEOUT)
        gitsafe.git(["commit", "-q", "-m", f"{task_dir.name} base ({version[:12]})"], cwd=tmp, timeout=GIT_TIMEOUT, identity=True)
        return _land(tmp, dest, lambda d: (d / ".git").is_dir())
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def cell_working_copy(source: Path, dest: Path) -> Path:
    """A fresh `git clone --local` of the task source, with its remote removed."""
    if dest.exists():
        raise BenchError("HB-USR-002", f"{dest} already exists; a cell's working copy is built once")
    dest.parent.mkdir(parents=True, exist_ok=True)
    gitsafe.git(["clone", "--local", "--quiet", str(source), str(dest)], cwd=dest.parent, timeout=GIT_TIMEOUT)
    gitsafe.git(["remote", "remove", "origin"], cwd=dest, timeout=GIT_TIMEOUT)
    return dest


def _pack_head(dest: Path) -> str:
    return gitsafe.git(["rev-parse", "HEAD"], cwd=dest, timeout=GIT_TIMEOUT).stdout.strip()


def pack_checkout(source: Path, commit: str, tools_root: Path) -> Path:
    """A bench-owned checkout of the pinned ai-forward commit (the source clone is never modified)."""
    dest = tools_root / commit[:12]
    if (dest / ".git").is_dir():
        head = _pack_head(dest)
        if head == commit:
            return dest
        raise BenchError("HB-PRE-007", f"{dest} is at {head}, not the pinned pack commit {commit}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        gitsafe.git(["clone", "--quiet", "--no-checkout", str(source), str(tmp)], cwd=dest.parent, timeout=GIT_TIMEOUT * 5)
        gitsafe.git(["checkout", "--quiet", commit], cwd=tmp, timeout=GIT_TIMEOUT * 5)
        return _land(tmp, dest, lambda d: (d / ".git").is_dir() and _pack_head(d) == commit)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def pack_revision(pack_dir: Path) -> int:
    for line in (pack_dir / "pack" / "adapters" / "INSTALL.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("revision:"):
            return int(line.split(":", 1)[1])
    raise BenchError("HB-PRE-007", f"no revision in {pack_dir}/pack/adapters/INSTALL.md")


def install_pack(pack_dir: Path, ws: Path, project: str, timeout: float) -> list[str]:
    """Install the pinned pack into a working copy, commit it, and return the manifest (paths written)."""
    script = pack_dir / "pack" / "scripts" / "pack-apply.py"
    result = procs.run([sys.executable, str(script), "apply", "--source", str(pack_dir), "--target", str(ws), "--install",
                        "--no-baselines", "--json", "--project", project], cwd=str(ws), env=None, timeout=timeout,
                       max_output=32 << 20)
    if result.timed_out or result.returncode != 0:
        raise BenchError("HB-PRE-007", f"pack-apply failed ({result.returncode}): {result.stderr.strip()[-300:]}")
    rows = json.loads(result.stdout)["rows"]
    manifest = sorted({r["path"] for r in rows if r.get("status") == "ok" and r.get("action") in WRITE_ACTIONS})
    gitsafe.git(["add", "-A"], cwd=ws, timeout=GIT_TIMEOUT)
    gitsafe.git(["commit", "-q", "-m", f"ai-forward pack revision {pack_revision(pack_dir)}"], cwd=ws, timeout=GIT_TIMEOUT,
                identity=True)
    return manifest
