"""The shared `base` fixture leaves no folder behind (CLN-A, residual 11).

A read-only file stands in for a git object. The fixed fixture clears that bit and removes
the folder. The assertion runs after `base` tears down and states the count that remains.
"""

import stat

import pytest


@pytest.fixture
def folders_before(clean_parent):
    clean_parent.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in clean_parent.iterdir() if p.is_dir()}
    yield before
    after = {p.name for p in clean_parent.iterdir() if p.is_dir()} if clean_parent.exists() else set()
    left = sorted(after - before)
    assert left == [], f"{len(left)} folder(s) left behind: {left}"


def test_the_base_fixture_leaves_zero_folders(folders_before, base):
    locked = base / "objects" / "pack"
    locked.parent.mkdir()
    locked.write_bytes(b"readonly-git-object")
    locked.chmod(stat.S_IREAD)
    assert base.is_dir()
