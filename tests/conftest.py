import functools
import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from slow_ring import dotnet_gate

from harness_bench import archive, procs

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


def pytest_runtest_setup(item):
    if item.get_closest_marker("slow") is not None:
        dotnet_gate(os.environ)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if item.get_closest_marker("slow") is None:
        real_run = procs.run

        @functools.wraps(real_run)  # keeps procs.run's signature for tests that inspect it
        def guarded_run(argv, *args, **kwargs):
            executable = Path(argv[0]).name.lower() if argv else ""
            if executable in ("dotnet", "dotnet.exe"):
                pytest.fail(f"unmarked test {item.nodeid} started real dotnet process: {argv[0]}")
            return real_run(argv, *args, **kwargs)

        procs.run = guarded_run
        try:
            yield
        finally:
            procs.run = real_run
    else:
        yield
