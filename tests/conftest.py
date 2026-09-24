import shutil
import sys
import uuid
from pathlib import Path

import pytest

# A folder with no agent instruction file in any ancestor (HB-PRE-002). The operator's profile, where
# pytest's tmp_path lives, holds ~/.claude/CLAUDE.md, so cells cannot be built there.
CLEAN_PARENT = Path("C:/Projects/bench-test")


@pytest.fixture
def base():
    root = CLEAN_PARENT / uuid.uuid4().hex[:8]
    root.mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)
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
