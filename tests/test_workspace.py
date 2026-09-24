"""Per-cell working copies (ADR-0013; US-8, US-9, US-49) and safe host git (ADR-0010 B6)."""

import subprocess
import threading
from pathlib import Path

import pytest

from harness_bench import gitsafe, workspace
from harness_bench.errors import BenchError

pytestmark = pytest.mark.native
ROOT = Path(__file__).resolve().parents[1]
X1 = ROOT / "tasks" / "X1"
PACK_SOURCE = (ROOT / ".." / "ai-forward").resolve()


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False).stdout


def _local_pack_repo(path):  # mirrors tests/test_cli.py::_pack_repo; no dependency on ../ai-forward
    (path / "pack" / "adapters").mkdir(parents=True)
    (path / "pack" / "adapters" / "INSTALL.md").write_text("revision: 7\n", encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "pack"]):
        gitsafe.git(args, cwd=path, timeout=60, identity=True)
    return gitsafe.git(["rev-parse", "HEAD"], cwd=path, timeout=60).stdout.strip()


def _run_concurrently(build) -> list:
    """Run `build()` on two threads released together by a barrier; collect each result or exception."""
    results: list = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        try:
            results.append(build())
        except Exception as exc:  # noqa: BLE001 - the test asserts on what actually happened
            results.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_task_source_built_concurrently_gives_every_caller_the_same_dest(base):  # T6-1 (HB-CELL-113)
    sources_root = base / "sources"
    dest = sources_root / "X1" / "v-race"[:16]
    results = _run_concurrently(lambda: workspace.task_source(X1, "v-race", sources_root))
    assert results == [dest, dest], results
    assert (dest / ".git").is_dir()


def test_task_source_reraises_when_a_colliding_dest_is_not_a_valid_build(base):
    sources_root = base / "sources"
    dest = sources_root / "X1" / "v-bad"[:16]
    dest.mkdir(parents=True)
    (dest / "not-a-build").write_text("x", encoding="utf-8")  # occupies dest but has no .git
    with pytest.raises(OSError):
        workspace.task_source(X1, "v-bad", sources_root)


def test_pack_checkout_built_concurrently_gives_every_caller_the_same_dest(base):  # T6-2 (HB-CELL-113)
    pack_src = base / "ai-forward"
    pack_src.mkdir()
    commit = _local_pack_repo(pack_src)
    tools_root = base / "tools"
    dest = tools_root / commit[:12]
    results = _run_concurrently(lambda: workspace.pack_checkout(pack_src, commit, tools_root))
    assert results == [dest, dest], results
    assert _git(dest, "rev-parse", "HEAD").strip() == commit


def test_pack_checkout_reraises_when_a_colliding_dest_is_not_a_valid_build(base):
    pack_src = base / "ai-forward"
    pack_src.mkdir()
    commit = _local_pack_repo(pack_src)
    tools_root = base / "tools"
    dest = tools_root / commit[:12]
    dest.mkdir(parents=True)
    (dest / "not-a-build").write_text("x", encoding="utf-8")  # occupies dest but has no .git
    with pytest.raises(OSError):
        workspace.pack_checkout(pack_src, commit, tools_root)


@pytest.fixture
def source(tmp_path):
    return workspace.task_source(X1, "v-test", tmp_path / "cells" / "_sources")


def test_task_source_holds_only_the_base_tree(source):
    files = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file() and ".git" not in p.parts)
    base = sorted(p.relative_to(X1 / "workspace").as_posix() for p in (X1 / "workspace").rglob("*") if p.is_file())
    assert files == base
    assert _git(source, "remote").strip() == ""


def test_hidden_tests_are_never_in_the_working_copy_or_its_history(source, tmp_path):  # T-WS-oracle
    ws = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "c1" / "ws")
    assert not (ws / "tests").exists() and not (ws / "oracle").exists()
    objects = _git(ws, "rev-list", "--all", "--objects")
    for hidden in (X1 / "tests").rglob("*"):
        if hidden.is_file():
            blob = _git(ws, "hash-object", str(hidden)).strip()
            assert blob not in objects


def test_a_cell_working_copy_has_no_remote(source, tmp_path):  # T-WS-noremote
    ws = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "c1" / "ws")
    assert _git(ws, "remote").strip() == ""
    assert "origin/" not in _git(ws, "branch", "-a")


def test_one_cells_git_state_is_invisible_to_another(source, tmp_path):  # T-WS-gitleak
    a = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "a" / "ws")
    b = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "b" / "ws")
    (a / "solution.txt").write_text("answer", encoding="utf-8")
    _git(a, "add", "solution.txt")
    _git(a, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "solve")
    (a / "wip.txt").write_text("wip", encoding="utf-8")
    _git(a, "add", "wip.txt")
    _git(a, "stash")
    _git(a, "remote", "add", "leak", "https://example.invalid/r.git")
    assert "solve" not in _git(b, "log", "--all", "--oneline")
    assert _git(b, "stash", "list").strip() == ""
    assert _git(b, "remote").strip() == ""
    assert not (b / "solution.txt").exists()


@pytest.fixture
def clean_base():
    """A folder under C:/Projects with no instruction file above it (pytest's tmp_path is under the profile)."""
    import shutil
    import uuid
    base = Path("C:/Projects/bench-test") / uuid.uuid4().hex[:8]
    base.mkdir(parents=True)
    yield base
    shutil.rmtree(base, ignore_errors=True)
    if not any(base.parent.iterdir()):
        base.parent.rmdir()


def test_cells_root_below_an_instruction_file_is_refused(clean_base):  # T-PRE-ancestor
    (clean_base / "CLAUDE.md").write_text("personal instructions", encoding="utf-8")
    with pytest.raises(BenchError) as e:
        workspace.check_cells_root(clean_base / "bench-cells")
    assert e.value.code == "HB-PRE-002" and "CLAUDE.md" in e.value.message


def test_cells_root_below_a_dot_claude_instruction_file_is_refused(clean_base):
    (clean_base / ".claude").mkdir()
    (clean_base / ".claude" / "CLAUDE.md").write_text("x", encoding="utf-8")
    with pytest.raises(BenchError):
        workspace.check_cells_root(clean_base / "a" / "bench-cells")


def test_cells_root_below_an_agents_md_is_refused(clean_base):
    (clean_base / "AGENTS.md").write_text("x", encoding="utf-8")
    with pytest.raises(BenchError):
        workspace.check_cells_root(clean_base / "bench-cells")


def test_a_clean_cells_root_is_accepted(clean_base):
    workspace.check_cells_root(clean_base / "bench-cells")


def test_a_cells_root_under_the_user_profile_is_refused(tmp_path):
    # the operator's ~/.claude/CLAUDE.md is above every folder in the profile (spike R1.3)
    if not (Path.home() / ".claude" / "CLAUDE.md").exists():
        pytest.skip("no ~/.claude/CLAUDE.md on this machine")
    with pytest.raises(BenchError):
        workspace.check_cells_root(tmp_path / "bench-cells")


def test_host_git_never_runs_repo_hooks(tmp_path):  # T-B6-fsmonitor (hooks half)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text(f"#!/bin/sh\necho ran > '{marker.as_posix()}'\n", encoding="utf-8")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    gitsafe.git(["add", "f.txt"], cwd=repo, timeout=60)
    gitsafe.git(["-c", "user.name=b", "-c", "user.email=b@b", "commit", "-qm", "m"], cwd=repo, timeout=60)
    assert not marker.exists()


def test_host_git_ignores_an_agent_written_fsmonitor(tmp_path):  # T-B6-fsmonitor
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    marker = tmp_path / "fsmonitor-ran"
    script = repo / "mon.cmd"
    script.write_text(f"@echo ran> \"{marker}\"\n", encoding="utf-8")
    _git(repo, "config", "core.fsmonitor", str(script))
    gitsafe.git(["status", "--porcelain"], cwd=repo, timeout=60)
    assert not marker.exists()


@pytest.mark.skipif(not (PACK_SOURCE / "pack" / "scripts" / "pack-apply.py").exists(), reason="no ai-forward clone")
def test_pack_on_differs_from_pack_off_by_exactly_the_manifest(source, tmp_path):  # US-9
    commit = _git(PACK_SOURCE, "rev-parse", "HEAD").strip()
    pack = workspace.pack_checkout(PACK_SOURCE, commit, tmp_path / "tools" / "pack")
    on = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "on" / "ws")
    manifest = workspace.install_pack(pack, on, project="X1", timeout=300)
    off = workspace.cell_working_copy(source, tmp_path / "cells" / "r" / "off" / "ws")

    def tree(ws):
        return {p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file() and ".git" not in p.parts}

    assert manifest and tree(on) - tree(off) == set(manifest)
    assert tree(off) <= tree(on)
    assert _git(on, "status", "--porcelain").strip() == ""  # the pack is committed before the clock starts
