import os
import shutil
import sys
import uuid
from collections.abc import Callable, Mapping
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



def dotnet_gate(env: Mapping[str, str], which: Callable[[str], str | None] = shutil.which) -> None:
    """The slow ring's opt-in (design phase3-graders, Catalog-version rule 4; V-4): without HB_REQUIRE_DOTNET=1 a slow
    test skips; with it, a missing dotnet fails the test instead of skipping, so the grading host cannot pass vacuously."""
    if env.get("HB_REQUIRE_DOTNET") != "1":
        pytest.skip("dotnet not required")
    if which("dotnet") is None:
        pytest.fail("HB_REQUIRE_DOTNET=1 but dotnet is not on PATH")


@pytest.fixture
def require_dotnet() -> None:
    """Use in every `@pytest.mark.slow` test that runs the real dotnet."""
    dotnet_gate(os.environ)


def pytest_configure(config):
    config.addinivalue_line("markers", "native: needs Windows Job Objects and real processes")
    config.addinivalue_line("markers", "credentials: needs the operator's harness logins (real model calls)")


def pytest_collection_modifyitems(config, items):
    if sys.platform != "win32":
        skip = pytest.mark.skip(reason="Windows only (NG9): Job Objects")
        for item in items:
            if "native" in item.keywords:
                item.add_marker(skip)
