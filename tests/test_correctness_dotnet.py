"""Native dotnet oracle contract (R-41), including real SDK and Job Object behavior."""

import os
import shutil
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_bench import host, procs
from harness_bench.grade import correctness
from harness_bench.profiles import CELL_ENV

FIXTURE = Path(__file__).parent / "fixtures" / "dotnet" / "OracleFixture.csproj"


@pytest.mark.parametrize("runner", ["dotnet", "unittest"])
@pytest.mark.parametrize("nuget_packages", [None, r"Z:\host-cache"])
def test_grading_step_uses_host_profile_only_for_dotnet(tmp_path, monkeypatch, runner, nuget_packages):
    profile = {
        "USERPROFILE": r"Z:\host-user",
        "APPDATA": r"Z:\host-user\Roaming",
        "LOCALAPPDATA": r"Z:\host-user\Local",
        "HOMEDRIVE": "Z:",
        "HOMEPATH": r"\host-user",
        "ProgramData": r"Z:\ProgramData",
        "ProgramFiles": r"Z:\Program Files",
    }
    for key, value in profile.items():
        monkeypatch.setenv(key, value)
    if nuget_packages is None:
        monkeypatch.delenv("NUGET_PACKAGES", raising=False)
    else:
        monkeypatch.setenv("NUGET_PACKAGES", nuget_packages)

    seen = []
    done = SimpleNamespace(returncode=0, stdout="10.0.303", stderr="Ran 1 test in 0.0s\n\nOK\n", timed_out=False)

    def capture(argv, **kwargs):
        seen.append((argv, kwargs["env"]))
        return done

    monkeypatch.setattr(correctness.procs, "run", capture)
    (tmp_path / "ws").mkdir()
    (tmp_path / "task" / "tests").mkdir(parents=True)
    command = ["dotnet", "test", "--logger", "trx;LogFileName=results.trx"] if runner == "dotnet" else ["{python}", "-m", "unittest"]
    correctness.grade(tmp_path / "ws", tmp_path / "task", {"runner": runner, "command": command},
                      tmp_path / "run" / "out", tmp_path / "run", 30)

    expected = {key: os.environ[key] for key in correctness.HOST_ENV if key in os.environ}
    expected.update(CELL_ENV)
    expected.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0", PYTHONUTF8="1")
    if runner == "dotnet":
        expected.update(profile)
        if nuget_packages is not None:
            expected["NUGET_PACKAGES"] = nuget_packages
    assert len(seen) == (2 if runner == "dotnet" else 1)
    assert all(env == expected for _, env in seen)


@pytest.fixture(scope="module")
def built_fixture(tmp_path_factory):
    output = tmp_path_factory.mktemp("dotnet-fixture")
    source = tmp_path_factory.mktemp("dotnet-source")
    for name in ("OracleFixture.csproj", "Program.cs", "NuGet.Config"):
        shutil.copy2(FIXTURE.parent / name, source / name)
    done = procs.run(["dotnet", "build", str(source / FIXTURE.name), "-o", str(output), "--ignore-failed-sources",
                      "-p:UseSharedCompilation=false"],
                     cwd=source, env={**os.environ, "MSBUILDDISABLENODEREUSE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}, timeout=90)
    assert done.returncode == 0 and not done.timed_out, done.stdout + done.stderr
    return output


def _grade(tmp_path, built_fixture, mode, *extra, stale=False):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "marker.txt").write_text("archived working copy", encoding="utf-8")
    if stale:
        old = ws / "TestResults" / "results.trx"
        old.parent.mkdir()
        old.write_text('<TestRun><ResultSummary><Counters total="1" passed="1" /></ResultSummary></TestRun>', encoding="utf-8")
    hidden = tmp_path / "task" / "tests"
    hidden.mkdir(parents=True)
    (hidden / "hidden.txt").write_text("hidden test", encoding="utf-8")
    for source in built_fixture.iterdir():
        if source.is_file():
            shutil.copy2(source, hidden / source.name)
    run = tmp_path / "run"
    out = run / "grading"
    command = ["dotnet", "OracleFixture.dll", mode, *extra, "--logger", "trx; LogFileName=results.trx"]
    result = correctness.grade(ws, hidden.parent, {"runner": "dotnet", "command": command}, out, run, 2 if mode == "hang" else 30)
    return result, out, ws


@pytest.mark.slow
def test_dotnet_oracle_runs_in_grading_copy_and_records_version(tmp_path, built_fixture):
    result, out, ws = _grade(tmp_path, built_fixture, "pass")
    assert (result.passed, result.partial_credit, result.reason) == (1, Decimal(1), None)
    assert "dotnet --version" in (out / "oracle.log").read_text(encoding="utf-8")
    assert "10.0.303" in (out / "oracle.log").read_text(encoding="utf-8")
    assert not (out / "work").exists()
    assert not (ws / "hidden.txt").exists()


@pytest.mark.slow
def test_dotnet_oracle_failed_tests_get_partial_credit(tmp_path, built_fixture):
    result, _, _ = _grade(tmp_path, built_fixture, "partial")
    assert (result.passed, result.partial_credit) == (0, Decimal("0.5"))


@pytest.mark.slow
def test_dotnet_oracle_nonzero_exit_is_not_a_pass_with_all_tests_passing(tmp_path, built_fixture):
    result, _, _ = _grade(tmp_path, built_fixture, "exit-one")
    assert (result.passed, result.partial_credit) == (0, Decimal(1))


@pytest.mark.slow
def test_dotnet_oracle_reads_named_trx_beside_nested_project(tmp_path, built_fixture):
    result, _, _ = _grade(tmp_path, built_fixture, "nested")
    assert (result.passed, result.partial_credit, result.reason) == (1, Decimal(1), None)


@pytest.mark.slow
def test_dotnet_oracle_does_not_read_stale_trx_from_archive(tmp_path, built_fixture):
    result, _, _ = _grade(tmp_path, built_fixture, "missing", stale=True)
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "named TRX result file missing")


@pytest.mark.slow
def test_dotnet_oracle_multiple_named_trx_files_are_na(tmp_path, built_fixture):
    result, _, _ = _grade(tmp_path, built_fixture, "duplicate")
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "multiple named TRX result files")


@pytest.mark.slow
@pytest.mark.parametrize(("mode", "reason"), [
    ("missing", "named TRX result file missing"),
    ("malformed", "named TRX result is unparsable"),
    ("zero", "no hidden test ran"),
    ("wrong-file", "named TRX result file missing"),
])
def test_dotnet_oracle_missing_or_invalid_named_summary_is_na(tmp_path, built_fixture, mode, reason):
    result, _, _ = _grade(tmp_path, built_fixture, mode)
    assert (result.passed, result.partial_credit, result.reason) == (None, None, reason)


@pytest.mark.slow
def test_dotnet_oracle_timeout_is_na_and_leaves_no_process(tmp_path, built_fixture):
    pid_file = tmp_path / "pid.txt"
    result, _, _ = _grade(tmp_path, built_fixture, "hang", str(pid_file))
    assert pid_file.is_file(), "dotnet fixture did not start"
    pid = int(pid_file.read_text(encoding="utf-8"))
    # Not os.kill(pid, 0): it does not raise while any party still holds a handle to the ended process object (AV,
    # another tool), the probable cause of the one unreproduced failure (Test Architect, STOP-I join). The exit code
    # decides. assume: the pid is not reused by a new live process within the 2 s window; breaks: a false "alive".
    assert not host.process_alive(pid, host.creation_time(pid))
    assert result.passed is None and result.partial_credit is None
    assert result.reason.startswith("HB-GRD-002")

