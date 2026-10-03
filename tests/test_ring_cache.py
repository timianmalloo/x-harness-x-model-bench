"""CACHE-A: a ring cache is keyed by content, so a stale or foreign build is never served."""
from __future__ import annotations

from pathlib import Path

import ring_cache

from harness_bench import workspace


def _task(tmp_path: Path, text: str) -> Path:
    task = tmp_path / "T1"
    (task / "workspace").mkdir(parents=True, exist_ok=True)
    (task / "workspace" / "a.txt").write_text(text, encoding="utf-8")
    (task / "task.yaml").write_text("id: T1\n", encoding="utf-8")
    return task


def test_changed_task_content_is_not_served_from_an_older_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ring_cache, "ring_root", lambda name: tmp_path / f"hb-{name}-ring")
    task = _task(tmp_path, "old")
    first = ring_cache.cached_base(task, "x")
    (task / "workspace" / "a.txt").write_text("new", encoding="utf-8")
    second = ring_cache.cached_base(task, "x")
    assert first != second
    assert (second / "a.txt").read_text(encoding="utf-8") == "new"
    assert (first / "a.txt").read_text(encoding="utf-8") == "old"


def test_changed_builder_code_gets_a_new_key(tmp_path, monkeypatch):
    task = _task(tmp_path, "same")
    before = ring_cache.content_version(task)
    fake = tmp_path / "workspace.py"
    fake.write_text("different builder", encoding="utf-8")
    monkeypatch.setattr(workspace, "__file__", str(fake))
    assert ring_cache.content_version(task) != before


def test_two_builders_racing_on_one_key_share_one_valid_tree(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(ring_cache, "ring_root", lambda name: tmp_path / f"hb-{name}-ring")
    task = _task(tmp_path, "race")
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: ring_cache.cached_base(task, "x"), range(6)))
    assert len(set(results)) == 1
    assert (results[0] / "a.txt").read_text(encoding="utf-8") == "race"
    assert not [p for p in results[0].parent.iterdir() if p.name.endswith(".tmp")]
