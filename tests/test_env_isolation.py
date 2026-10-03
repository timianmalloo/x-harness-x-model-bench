"""ENV-C: hermetic tests do not read an ambient credential from the operator shell.

The three tests that failed the Q0 join when ``HB_CLAUDE_OAUTH_TOKEN`` was set are re-run
in-process, through pytest, with every listed credential planted. They pass only when the
autouse fixture in ``tests/conftest.py`` clears those names. A ``credentials`` test keeps them.
"""

import os
from pathlib import Path

import pytest
from conftest import listed_credential_names

from harness_bench import profiles

NAMED = (
    "tests/test_gateway_headless.py::test_t_gw_10_the_credential_is_present_during_the_call_and_gone_after_it",
    "tests/test_gateway_headless.py::test_t_gw_10_the_credential_is_gone_after_a_timeout_and_after_an_exception_past_the_copy",
    "tests/test_profiles.py::test_the_launcher_reports_no_model_setter_and_a_copied_login[claude-code]",
)
PLANTED = "dummy-kept"
WITNESS = "HB_ENV_ISOLATION_WITNESS"


class _Failures:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def pytest_runtest_logreport(self, report) -> None:
        if not report.failed:
            return
        text = getattr(report, "longreprtext", "") or ""
        interesting = [line.strip() for line in text.splitlines()
                       if "AssertionError" in line or line.strip().startswith("E   assert")]
        if interesting:
            last = interesting[-1]
        elif text.strip():
            last = text.strip().splitlines()[-1]
        else:
            last = report.outcome
        self.lines.append(f"{report.nodeid}: {last}")


def _rerun(nodeids: tuple[str, ...] | list[str], extra: list[str] | None = None) -> tuple[int, list[str]]:
    captured = _Failures()
    args = ["-q", "--tb=short", "--color=no", "-p", "no:cacheprovider", *(extra or []), *nodeids]
    code = int(pytest.main(args, plugins=[captured]))
    return code, captured.lines


def test_the_three_named_tests_pass_with_every_listed_credential_set(monkeypatch):
    names = listed_credential_names()
    assert profiles.OAUTH_TOKEN_ENV in names
    for name in names:
        monkeypatch.setenv(name, "dummy")
    code, failed = _rerun(NAMED)
    assert code == 0 and not failed, "\n".join(failed) or f"exit {code}"


def test_a_credentials_mark_keeps_the_planted_variable(monkeypatch, tmp_path):
    witness = tmp_path / "seen"
    monkeypatch.setenv(profiles.OAUTH_TOKEN_ENV, PLANTED)
    monkeypatch.setenv(WITNESS, str(witness))
    node = "tests/test_env_isolation.py::test_a_credentials_marked_test_still_sees_the_planted_variable"
    code, failed = _rerun((node,), ["-m", "credentials"])
    assert code == 0 and not failed, "\n".join(failed) or f"exit {code}"
    assert witness.is_file() and witness.read_text(encoding="utf-8") == PLANTED


@pytest.mark.credentials
def test_a_credentials_marked_test_still_sees_the_planted_variable():
    witness = os.environ.get(WITNESS)
    if not witness:
        pytest.skip("planted only by the isolation driver")
    seen = os.environ.get(profiles.OAUTH_TOKEN_ENV)
    Path(witness).write_text(seen or "", encoding="utf-8")
    assert seen == PLANTED
