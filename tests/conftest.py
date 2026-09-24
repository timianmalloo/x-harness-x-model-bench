import shutil
import sys
import uuid
from pathlib import Path

import pytest

from harness_bench import archive

# A folder with no agent instruction file in any ancestor (HB-PRE-002). The operator's profile, where
# pytest's tmp_path lives, holds ~/.claude/CLAUDE.md, so cells cannot be built there.
CLEAN_PARENT = Path("C:/Projects/bench-test")


@pytest.fixture
def clean_parent() -> Path:
    return CLEAN_PARENT


@pytest.fixture
def base():
    # a full uuid: an 8-hex name collided with a leftover folder and turned a test into a false mutation kill (CLN-A)
    root = CLEAN_PARENT / uuid.uuid4().hex
    root.mkdir(parents=True)
    yield root
    try:  # git writes read-only objects; a plain rmtree(ignore_errors=True) left them behind (CLN-A)
        shutil.rmtree(root, onexc=archive.make_writable)
    except OSError:  # a file this test process still holds open; tools/clean_bench_test.py removes it later
        pass
    if root.parent.exists() and not any(root.parent.iterdir()):
        root.parent.rmdir()


def pytest_configure(config):
    config.addinivalue_line("markers", "native: needs Windows Job Objects and real processes")
    config.addinivalue_line("markers", "credentials: needs the operator's harness logins (real model calls)")


def pytest_collection_modifyitems(config, items):
    if sys.platform != "win32":
        skip = pytest.mark.skip(reason="Windows only (NG9): Job Objects")
        for item in items:
            if "native" in item.keywords:
                item.add_marker(skip)
