"""The shared `base` fixture leaves no folder behind (CLN-A, residual 11).

A read-only file stands in for a git object. The fixed fixture clears that bit and removes
the folder. The assertion runs after `base` tears down and checks only this test's own folder.
"""

import stat

import pytest


@pytest.fixture
def own_base():
    """Hold this test's `base` path. Set up first, so teardown runs after `base` removes it."""
    seen = {}
    yield seen
    path = seen["path"]
    assert not path.exists(), f"base folder still exists: {path}"


def test_the_base_fixture_leaves_zero_folders(own_base, base):
    own_base["path"] = base
    locked = base / "objects" / "pack"
    locked.parent.mkdir()
    locked.write_bytes(b"readonly-git-object")
    locked.chmod(stat.S_IREAD)
    assert base.is_dir()


def test_base_teardown_tolerates_concurrent_sibling_folder_creation(monkeypatch, tmp_path):
    import sys
    import threading
    from pathlib import Path

    conftest = sys.modules["conftest"]

    shared = tmp_path / "bench-test-shared"
    shared.mkdir()
    monkeypatch.setattr(conftest, "CLEAN_PARENT", shared)

    gen = conftest.base.__wrapped__()
    root = next(gen)
    assert root.is_dir()

    sibling = shared / "concurrent-worker-cell"
    orig_iterdir = Path.iterdir

    def hook_iterdir(self):
        it = orig_iterdir(self)
        if self == shared:
            items = list(it)
            t = threading.Thread(target=sibling.mkdir)
            t.start()
            t.join()
            return iter(items)
        return it

    monkeypatch.setattr(Path, "iterdir", hook_iterdir)
    next(gen, None)
    assert sibling.is_dir()
    assert not root.exists()

