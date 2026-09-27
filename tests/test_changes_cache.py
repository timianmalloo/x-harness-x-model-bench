"""Tests for pre-turn tree digest caching in harness_bench.grade._changes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_bench import gitsafe
from harness_bench.grade import _changes


def _make_symlink(link_path: Path, target_str: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Create a symlink or mock is_symlink/readlink if Windows lacks privileges."""
    try:
        link_path.symlink_to(target_str)
    except OSError:
        # On Windows without SeCreateSymbolicLinkPrivilege, write placeholder and mock
        link_path.write_text(f"symlink-placeholder:{target_str}", encoding="utf-8")
        orig_is_symlink = Path.is_symlink

        def patched_is_symlink(self: Path) -> bool:
            if self.resolve() == link_path.resolve():
                return True
            return orig_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", patched_is_symlink)
        orig_readlink = os.readlink

        def patched_readlink(path: str | bytes | os.PathLike) -> str:
            p = Path(path).resolve()
            if p == link_path.resolve():
                return target_str
            return orig_readlink(path)

        monkeypatch.setattr(_changes.os, "readlink", patched_readlink)


def test_differential_cache_equals_uncached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) Differential: on fixtures with CRLF, UTF-8 BOM, symlink, and binary, cached == uncached."""
    _changes.clear_pre_turn_cache()

    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()

    # 1. CRLF fixture: unchanged when normalized, changed when content differs
    (before / "crlf_same.txt").write_bytes(b"line1\r\nline2\r\n")
    (after / "crlf_same.txt").write_bytes(b"line1\nline2\n")

    (before / "crlf_diff.txt").write_bytes(b"line1\r\nline2\r\n")
    (after / "crlf_diff.txt").write_bytes(b"line1\r\nline_diff\r\n")

    # 2. UTF-8 BOM fixture: unchanged vs changed
    (before / "bom_same.txt").write_bytes(b"\xef\xbb\xbfalpha\nbeta\n")
    (after / "bom_same.txt").write_bytes(b"\xef\xbb\xbfalpha\nbeta\n")

    (before / "bom_diff.txt").write_bytes(b"\xef\xbb\xbfgamma\n")
    (after / "bom_diff.txt").write_bytes(b"\xef\xbb\xbfdelta\n")

    # 3. Symlink fixture: unchanged vs changed target
    _make_symlink(before / "link_same.txt", "common_target", monkeypatch)
    _make_symlink(after / "link_same.txt", "common_target", monkeypatch)

    _make_symlink(before / "link_diff.txt", "target_v1", monkeypatch)
    _make_symlink(after / "link_diff.txt", "target_v2", monkeypatch)

    # 4. Binary fixture: unchanged vs changed bytes
    (before / "binary_same.bin").write_bytes(b"\x00\x01\xfe\xff\x00")
    (after / "binary_same.bin").write_bytes(b"\x00\x01\xfe\xff\x00")

    (before / "binary_diff.bin").write_bytes(b"\x00\x01\xfe\xff\x01")
    (after / "binary_diff.bin").write_bytes(b"\x00\x01\xfe\xff\x02")

    # 5. Added and deleted files
    (after / "added.txt").write_bytes(b"newly added")
    (before / "deleted.txt").write_bytes(b"to be deleted")

    # 6. Build output directory ignored on both sides
    (before / "bin").mkdir()
    (before / "bin" / "ignored.dll").write_bytes(b"MZ")
    (after / "bin").mkdir()
    (after / "bin" / "ignored.dll").write_bytes(b"MZ-different")

    # Run with cache enabled (primes the cache)
    tree_id = "test-tree-differential-12345678"
    cached = _changes.change_set(before, after, tree_id=tree_id, bypass_cache=False)

    # Run with cache bypassed
    uncached = _changes.change_set(before, after, tree_id=tree_id, bypass_cache=True)

    expected = {
        "added.txt": "added",
        "binary_diff.bin": "changed",
        "bom_diff.txt": "changed",
        "crlf_diff.txt": "changed",
        "deleted.txt": "deleted",
        "link_diff.txt": "changed",
    }

    assert cached == uncached, "cached change_set differs from uncached change_set"
    assert cached == expected, f"expected {expected}, got {cached}"

    # Verify second cached call still matches
    cached_again = _changes.change_set(before, after, tree_id=tree_id, bypass_cache=False)
    assert cached_again == uncached


def test_isolation_different_tree_ids_never_share_entry(tmp_path: Path) -> None:
    """(b) Isolation: two pre-turn trees with different tree ids never share an entry;
    a changed file in the second is seen.
    """
    _changes.clear_pre_turn_cache()

    work = tmp_path / "work"
    work.mkdir()
    (work / "file.txt").write_text("v1", encoding="utf-8")

    tree1 = tmp_path / "tree1"
    tree1.mkdir()
    (tree1 / "file.txt").write_text("v1", encoding="utf-8")

    tree2 = tmp_path / "tree2"
    tree2.mkdir()
    (tree2 / "file.txt").write_text("v2", encoding="utf-8")

    # Tree 1 has tree_id "tree-id-1" and matches work tree -> no changes
    res1 = _changes.change_set(tree1, work, tree_id="tree-id-1")
    assert res1 == {}, f"expected empty change set for tree1, got {res1}"

    # Tree 2 has different tree_id "tree-id-2" and has "v2" vs work's "v1" -> changed file seen
    res2 = _changes.change_set(tree2, work, tree_id="tree-id-2")
    assert res2 == {"file.txt": "changed"}, (
        f"expected {{'file.txt': 'changed'}} for tree2, got {res2} (isolation failure)"
    )


def test_isolation_same_tree_id_at_different_path_shares_entry(tmp_path: Path) -> None:
    """(b) Isolation: the same tree id at a different path shares the cached entry."""
    _changes.clear_pre_turn_cache()

    work = tmp_path / "work"
    work.mkdir()
    (work / "shared.txt").write_text("original", encoding="utf-8")

    path1 = tmp_path / "path1"
    path1.mkdir()
    (path1 / "shared.txt").write_text("original", encoding="utf-8")

    # Prime the cache for "tree-id-shared"
    res1 = _changes.change_set(path1, work, tree_id="tree-id-shared")
    assert res1 == {}

    # Path 2 is at a different path with the SAME tree_id
    path2 = tmp_path / "path2"
    path2.mkdir()
    # Write altered bytes to path2 to prove it reads from the cache, not path2 on disk
    (path2 / "shared.txt").write_text("altered-bytes-on-disk", encoding="utf-8")

    res2 = _changes.change_set(path2, work, tree_id="tree-id-shared")
    # Because path2 shares the cached digests of "tree-id-shared", it sees "original" == work's "original" -> {}
    assert res2 == {}, (
        f"expected path2 to share cache entry for tree-id-shared, but got {res2}"
    )


def test_unreadable_tree_id_does_not_cache(tmp_path: Path) -> None:
    """When tree id cannot be read (None), it does not cache and falls back to computing."""
    _changes.clear_pre_turn_cache()

    work = tmp_path / "work"
    work.mkdir()
    (work / "doc.txt").write_text("v1", encoding="utf-8")

    tree_u1 = tmp_path / "tree_u1"
    tree_u1.mkdir()
    (tree_u1 / "doc.txt").write_text("v1", encoding="utf-8")

    # Unreadable tree id 1: computes, does not cache
    res1 = _changes.change_set(tree_u1, work, tree_id=None)
    assert res1 == {}

    # Unreadable tree id 2 at different path with different content:
    tree_u2 = tmp_path / "tree_u2"
    tree_u2.mkdir()
    (tree_u2 / "doc.txt").write_text("v2", encoding="utf-8")

    # If it improperly cached on tree_id=None, it would get v1 from cache and return {}
    # Because it does not cache when unreadable, it computes from disk and sees "changed"
    res2 = _changes.change_set(tree_u2, work, tree_id=None)
    assert res2 == {"doc.txt": "changed"}, (
        f"expected {{'doc.txt': 'changed'}} for unreadable tree2, got {res2}"
    )


def test_pre_turn_tree_attaches_tree_id_from_git(tmp_path: Path) -> None:
    """pre_turn_tree attaches git tree object ID to yielded path and change_set uses it."""
    _changes.clear_pre_turn_cache()

    ws = tmp_path / "ws"
    ws.mkdir()
    gitsafe.git(["init", "-q"], cwd=ws, timeout=30)
    (ws / "sample.txt").write_text("base content\n", encoding="utf-8")
    gitsafe.git(["add", "sample.txt"], cwd=ws, timeout=30)
    gitsafe.git(["commit", "-q", "-m", "task base (v1.0.0)"], cwd=ws, timeout=30, identity=True)

    commit = gitsafe.git(["rev-parse", "HEAD"], cwd=ws, timeout=30).stdout.strip()
    expected_tree_id = gitsafe.git(["rev-parse", f"{commit}^{{tree}}"], cwd=ws, timeout=30).stdout.strip()

    dest = tmp_path / "extracted_base"
    with _changes.pre_turn_tree(ws, commit, dest, timeout=30) as base:
        assert getattr(base, "tree_id", None) == expected_tree_id

        # Grade against a working tree
        work = tmp_path / "work"
        work.mkdir()
        (work / "sample.txt").write_text("base content\n", encoding="utf-8")
        (work / "new.txt").write_text("new content\n", encoding="utf-8")

        diff = _changes.change_set(base, work)
        assert diff == {"new.txt": "added"}
