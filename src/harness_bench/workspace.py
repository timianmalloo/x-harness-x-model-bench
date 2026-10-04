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

import hashlib
import json
import os  # noqa: F401 - tests patch workspace.os.replace; rename_with_retry reads it on this module
import shutil
import sys
import tarfile
import uuid
from pathlib import Path

from harness_bench import atomic, config, gitsafe, procs
from harness_bench.errors import BenchError

INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md", "GEMINI.md", ".github/copilot-instructions.md")
INSTRUCTION_DIRS = (".github/instructions",)
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
        for name in INSTRUCTION_DIRS:
            for path in (folder / name).rglob("*.instructions.md"):
                if path.is_file():
                    raise BenchError("HB-PRE-002", f"{path} is above the cells root {root}; every cell would load it")


# grade/runner.py's grading-copy-outside-repo fix (measured 2026-09-30, runs/grid-2, grading id
# grade-20260930T204453-43f5b9): E2-E5's `uv run --python ... pytest ...` (no `--no-project`), run with cwd inside
# the repo, discovered *this* repository's own pyproject.toml/.python-version and rebuilt the engine's own .venv
# with the wrong Python (deleting site-packages; "error: failed to remove directory `.venv\Scripts`: Access is
# denied"). Defect class ORCL-B (sibling of ORCL-A, docs/lessons/defect-classes.md): an upward-discovering tool (uv
# today; pip, dotnet's global.json, npm, git config are the same class) must never see a project file that belongs
# to the harness itself.
UPWARD_DISCOVERY_FILES = ("pyproject.toml", ".python-version")


def check_grading_root(root: Path) -> None:
    """Refuse a grading root with an upward-discovering tool's own project file (`pyproject.toml`,
    `.python-version`) in it or in any ancestor (HB-GRD-006). Checked once per grading pass
    (grade/runner.py's run_pass), before any grader builds a working copy under it."""
    resolved = root.resolve()
    for folder in (resolved, *resolved.parents):
        for name in UPWARD_DISCOVERY_FILES:
            if (folder / name).is_file():
                raise BenchError("HB-GRD-006", f"{folder / name} is above the grading root {root}; a grading step's "
                                                "own upward-discovering tool (uv, pip, dotnet, ...) would reach it")


def _fresh(dest: Path) -> Path:
    tmp = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
    tmp.mkdir(parents=True)
    return tmp


def _discard(tmp: Path) -> None:
    """Best-effort cleanup of a losing or abandoned tmp build. Git leaves its object files read-only
    on Windows, so a plain rmtree fails silently (that failure is the T9-1 disk leak); make_writable
    (atomic.py) clears the bit first. A cleanup failure is still swallowed here rather than raised:
    this runs in a `finally`, often while a real build exception is already propagating, and a
    cleanup error must never replace or mask that exception."""
    if tmp.exists():
        try:
            shutil.rmtree(tmp, onexc=atomic.make_writable)
        except OSError:
            pass


def _land(tmp: Path, dest: Path, valid) -> Path:
    """Publish tmp as dest. A build is content-addressed and written once: when two callers race to
    build the same dest, the rename fails for whichever lands second (HB-CELL-113, Windows cannot
    rename onto a non-empty dest). If dest is by then a valid build, the other writer won; discard
    tmp (the caller's `finally` does that) and hand back dest. Any other failure is real and propagates.
    """
    try:
        atomic.rename_with_retry(tmp, dest, replace=True, settled=lambda: valid(dest))
    except OSError:
        if not valid(dest):
            raise
    return dest


def _verify_commit(clone: Path, commit: str) -> None:
    """Refuse a pin that is not the exact commit id (a short prefix, a moved tag, the wrong repo) --
    `rev-parse --verify <commit>^{commit}` resolves a prefix to its full oid, so an exact string
    comparison is what tells "verified to be exactly that commit" from merely "reachable"."""
    result = gitsafe.git(["rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=clone, timeout=GIT_TIMEOUT)
    if result.stdout.strip() != commit:
        raise BenchError("HB-PRE-007", f"{clone}: {commit!r} is not the exact upstream commit id (resolved to "
                                        f"{result.stdout.strip()!r})")


def upstream_tree(repo: str, commit: str, upstream_root: Path) -> Path:
    """A bench-owned, `--no-checkout` clone of one pinned upstream commit (fetched once, cached under
    `upstream_root`, keyed by repo+commit, and reused by every task version that pins it). Kept
    checkout-free so many `task_source` builds can `git archive` its tree concurrently with nothing
    to race on; the clone itself is never modified after landing."""
    key = hashlib.sha256(f"{repo}@{commit}".encode()).hexdigest()[:16]
    dest = upstream_root / key
    if (dest / ".git").is_dir():
        _verify_commit(dest, commit)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        gitsafe.git(["clone", "--quiet", "--no-checkout", repo, str(tmp)], cwd=dest.parent, timeout=GIT_TIMEOUT * 5)
        _verify_commit(tmp, commit)
        return _land(tmp, dest, lambda d: (d / ".git").is_dir())
    finally:
        _discard(tmp)


def _extract_upstream_tree(clone: Path, commit: str, dest: Path) -> None:
    """`git archive` the clone's tree at `commit` into the already-created, empty `dest` -- a tree, not a
    repository (R-83): no `.git`, no history, no reflog. Extracted through a tar file rather than a
    captured stdout pipe, because `procs.run` decodes stdout as UTF-8 text (`decode(...,
    errors="replace")`), which would corrupt a binary tar stream."""
    tar_path = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:8]}.tar"
    try:
        gitsafe.git(["archive", "--format=tar", f"--output={tar_path}", commit], cwd=clone, timeout=GIT_TIMEOUT * 5)
        with tarfile.open(tar_path) as tar:
            tar.extractall(dest, filter="data")
    finally:
        tar_path.unlink(missing_ok=True)


def task_source(task_dir: Path, version: str, sources_root: Path, upstream_root: Path | None = None) -> Path:
    """The bench-owned repository of one task version's base tree (created once, then reused).

    A workspace/-only task (the default) commits `tasks/<ID>/workspace/` as-is, exactly as before. A
    task whose `task.yaml` sets `source.workspace_from: source` opts in instead: the base tree is the
    pinned `source.repo` at `source.commit` (a cached, verified upstream clone's tree, via `git
    archive`), with `tasks/<ID>/workspace/` overlaid on top -- so a large public task's base tree
    never vendors the upstream repository into this one, and the cell still sees one tree with one
    base commit, never the upstream's history (R-83)."""
    dest = sources_root / task_dir.name / version[:16]
    if (dest / ".git").is_dir():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = _fresh(dest)
    try:
        source = config.load_yaml(task_dir / "task.yaml").get("source") or {}
        if source.get("workspace_from") == "source":
            if upstream_root is None:
                raise BenchError("HB-PRE-007", f"{task_dir.name}: source.workspace_from: source needs an upstream "
                                                "cache root")
            clone = upstream_tree(source["repo"], source["commit"], upstream_root)
            _extract_upstream_tree(clone, source["commit"], tmp)
        # Bytecode a test wrote into the task folder is not part of the version hash (plan.py) and never part of a base tree.
        shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        gitsafe.git(["init", "-q", "-b", "main"], cwd=tmp, timeout=GIT_TIMEOUT)
        gitsafe.git(["add", "-A"], cwd=tmp, timeout=GIT_TIMEOUT)
        gitsafe.git(["commit", "-q", "-m", f"{task_dir.name} base ({version[:12]})"], cwd=tmp, timeout=GIT_TIMEOUT, identity=True)
        return _land(tmp, dest, lambda d: (d / ".git").is_dir())
    finally:
        _discard(tmp)


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
        _discard(tmp)


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
