"""The platform-conditional pieces of process control that are portable to test (ADR-0013 Amendment 1,
section 5: the macOS port). Unlike tests/test_procs.py, this file carries no blanket `native` marker
(the module-level pytestmark that skips it off Windows) -- every test here runs, for real, on both the
Windows and the macos-latest CI jobs.

The POSIX Job/spawn implementation itself (`procs.py`'s `else` branch: `Job`, `_spawn_posix`,
`_pgrep_pids`, ...) only *exists* in the module namespace on a POSIX host, so it cannot be unit-tested
here even by monkeypatching. What is tested here instead: (1) the pure pgrep-output parser the POSIX
termination confirmation depends on (`_parse_pgrep`, defined unconditionally); (2) the platform branches
that already live in the always-defined, shared code (`SpawnError`'s message, `CellProcess.wait`'s
masking), read live from `sys.platform` so a monkeypatch exercises the POSIX branch without needing a
POSIX host. The real spawn-based POSIX coverage is tests/test_procs_posix.py (`pytest.mark.posix`,
skipped on Windows, run for real only by the macos-latest CI job)."""

from types import SimpleNamespace

from harness_bench import procs


def test_parse_pgrep_reads_every_pid_pgrep_printed():
    assert procs._parse_pgrep("123\n456\n") == {123, 456}
    assert procs._parse_pgrep("789") == {789}


def test_parse_pgrep_of_no_output_is_a_real_empty_set_not_a_false_one():
    assert procs._parse_pgrep("") == set()
    assert procs._parse_pgrep("   \n  ") == set()


def test_spawn_error_names_errno_off_windows(monkeypatch):
    monkeypatch.setattr(procs.sys, "platform", "darwin")
    err = procs.SpawnError("cannot start x", 2)
    assert "errno 2" in str(err) and "win32 error" not in str(err)


def test_spawn_error_names_win32_error_on_windows(monkeypatch):
    monkeypatch.setattr(procs.sys, "platform", "win32")
    err = procs.SpawnError("cannot start x", 2)
    assert "win32 error 2" in str(err)


def test_cell_process_wait_is_not_masked_off_windows(monkeypatch):
    """A POSIX signal death is a small negative int (e.g. -15 for SIGTERM); masking it the Windows way
    would turn it into a misleading large positive number that means nothing on POSIX."""
    monkeypatch.setattr(procs.sys, "platform", "darwin")
    fake_proc = SimpleNamespace(wait=lambda timeout=None: -15)
    cell = procs.CellProcess(proc=fake_proc, job=None)
    assert cell.wait() == -15


def test_cell_process_wait_masks_on_windows(monkeypatch):
    monkeypatch.setattr(procs.sys, "platform", "win32")
    fake_proc = SimpleNamespace(wait=lambda timeout=None: 0xC0000017)
    cell = procs.CellProcess(proc=fake_proc, job=None)
    assert cell.wait() == 0xC0000017
