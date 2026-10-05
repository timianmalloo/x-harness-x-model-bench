"""CACHE-B: a cached base whose working tree drifted from its own HEAD is repaired, never served damaged."""
from __future__ import annotations

from pathlib import Path

import ring_cache

from harness_bench import gitsafe


def _task(tmp_path: Path) -> Path:
    task = tmp_path / "T1"
    (task / "workspace" / "pkg").mkdir(parents=True)
    (task / "workspace" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (task / "workspace" / "a.txt").write_text("content", encoding="utf-8")
    (task / "workspace" / "b.txt").write_text("more", encoding="utf-8")
    (task / "task.yaml").write_text("id: T1\n", encoding="utf-8")
    return task


def _pinned(base: Path) -> list[str]:
    out = gitsafe.git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=base, timeout=30).stdout
    return sorted(out.split())


def _on_disk(base: Path) -> list[str]:
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file() and ".git" not in p.parts)


def test_damaged_cached_base_is_not_served(tmp_path, monkeypatch):
    monkeypatch.setattr(ring_cache, "ring_root", lambda name: tmp_path / f"hb-{name}-ring")
    task = _task(tmp_path)
    base = ring_cache.cached_base(task, "g")
    (base / "pkg" / "__init__.py").unlink()
    (base / "a.txt").unlink()
    again = ring_cache.cached_base(task, "g")
    assert _on_disk(again) == _pinned(again)
    assert (again / "a.txt").read_text(encoding="utf-8") == "content"


def test_undamaged_cached_base_is_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(ring_cache, "ring_root", lambda name: tmp_path / f"hb-{name}-ring")
    task = _task(tmp_path)
    first = ring_cache.cached_base(task, "g")
    marker = first / "marker.untracked"
    marker.write_text("x", encoding="utf-8")
    assert ring_cache.cached_base(task, "g") == first
    assert marker.exists()
