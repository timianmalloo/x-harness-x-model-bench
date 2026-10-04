import functools
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
import suite_lock
from ambient_credentials import listed_credential_names
from slow_ring import dotnet_gate

from harness_bench import archive, procs

# A folder with no agent instruction file in any ancestor (HB-PRE-002). The operator's profile, where
# pytest's tmp_path lives, holds ~/.claude/CLAUDE.md, so cells cannot be built there.
#
# `Path("C:/Projects/bench-test")` is a Windows drive-letter path; POSIX pathlib does not recognise the
# `C:` prefix as a root, so on macOS the fixture's own `root.mkdir(parents=True)` silently created it as
# a *relative* path under the process's cwd -- the CI checkout -- landing every cell inside the repo
# that carries CLAUDE.md at its root and turning `HB-PRE-002` on for tests/test_calibrate.py,
# tests/test_preflight.py and tests/test_report_judges.py wholesale (ADR-0013 Amendment 1, macOS port).
# `tempfile.gettempdir()` is already proven clean of any instruction file on both hosts: it is where
# pytest's own `tmp_path` lives on macOS (the errors above showed `/private/var/folders/.../T/...`), and
# on Windows it stays the pinned `C:/Projects/bench-test` unchanged, per the comment above.
#
# `.resolve()`: on macOS, `/var` is a symlink to `/private/var`, so `tempfile.gettempdir()` itself
# ("/var/folders/...") and the canonical path a spawned child's own `os.getcwd()` reports
# ("/private/var/folders/...") name the same real folder but do not `==` as unresolved `Path`s.
# tests/test_gateway_headless.py's `assert Path(seen["cwd"]) == call / "work"` compares exactly that
# (a fake harness's real `os.getcwd()` against a path built by joining onto `base`), so `base` is
# resolved once here to the canonical form every OS-reported path already uses, rather than resolving
# at each comparison site.
CLEAN_PARENT = Path("C:/Projects/bench-test") if sys.platform == "win32" else Path(tempfile.gettempdir()).resolve() / "bench-test"


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



@pytest.fixture
def require_dotnet() -> None:
    """Use in every `@pytest.mark.slow` test that runs the real dotnet."""
    dotnet_gate(os.environ)


@pytest.fixture(autouse=True)
def clear_ambient_credentials(request, monkeypatch):
    """Hermetic tests do not see ambient credentials. A ``credentials`` test keeps the operator environment."""
    if request.node.get_closest_marker("credentials") is None:
        for name in listed_credential_names():
            monkeypatch.delenv(name, raising=False)
    yield


_SUITE_LOCK = pytest.StashKey()


def pytest_configure(config):
    config.addinivalue_line("markers", "native: needs Windows Job Objects and real processes")
    config.addinivalue_line("markers", "posix: needs POSIX process groups and real processes (setsid, killpg, pgrep)")
    config.addinivalue_line("markers", "credentials: needs the operator's harness logins (real model calls)")
    # SUITE-LOCK: one heavy run per machine (tests/suite_lock.py). An xdist worker inherits its controller's
    # HB_SUITE_LOCK_PARENT=1, so it runs under the controller's hold and never waits on it.
    heavy = suite_lock.is_heavy(config.getoption("numprocesses", None), config.getoption("collectonly"), config.args,
                                config.args_source != pytest.Config.ArgsSource.ARGS, config.invocation_params.dir)
    lock = None
    if heavy:
        capture = config.pluginmanager.getplugin("capturemanager")

        def tell(line):
            with capture.global_and_fixture_disabled():
                print(line, file=sys.stderr, flush=True)

        lock = suite_lock.acquire(os.environ, f"pytest {' '.join(config.invocation_params.args)}", tell)
    os.environ[suite_lock.PARENT_ENV] = "1"  # a light run too: a test's own nested pytest or mutate_check never waits
    config.stash[_SUITE_LOCK] = lock


def pytest_unconfigure(config):
    suite_lock.release(config.stash.get(_SUITE_LOCK, None), os.environ)


def pytest_collection_modifyitems(config, items):
    # Symmetric, explicit skips (ADR-0013 Amendment 1 s5): a `native` test needs Windows Job Objects and
    # is skipped everywhere else; a `posix` test needs a real POSIX process group (setsid/killpg/pgrep)
    # and is skipped on Windows, where those calls do not exist. Neither skip is silent (pytest prints
    # the reason); the macos-latest CI job is the only host where `posix` tests run for real.
    if sys.platform != "win32":
        skip = pytest.mark.skip(reason="Windows only (NG9): Job Objects")
        for item in items:
            if "native" in item.keywords:
                item.add_marker(skip)
    else:
        skip = pytest.mark.skip(reason="POSIX only (ADR-0013 Amendment 1 s5): process groups (setsid, killpg, pgrep)")
        for item in items:
            if "posix" in item.keywords:
                item.add_marker(skip)


def pytest_runtest_setup(item):
    if item.get_closest_marker("slow") is not None:
        dotnet_gate(os.environ)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if item.get_closest_marker("slow") is None and item.get_closest_marker("gate") is None:
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
