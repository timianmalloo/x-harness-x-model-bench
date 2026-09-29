"""Native pytest oracle contract: `--junitxml=<file>` (a bare JUnit XML file name) parsed strictly, mirroring the
dotnet TRX runner (test_correctness_dotnet.py). A pytest collection error still writes a report with `errors`
counted against the total, so it is read like any other failure (0), never NA -- observed with the pinned pytest
on this host (`docs/design/phase3-graders.md`, Correctness).

Real `python -m pytest` subprocesses grade the pass, partial-credit, collection-error and no-tests-collected
branches. The missing/duplicate/unparsable-report branches use a small real Python subprocess that stands in
for the oracle step (mirroring the dotnet fixture's modes in test_correctness_dotnet.py) -- a real pytest run
cannot deterministically produce those without hand control, so hand-writing the report there is the practical
choice; nothing here hand-writes the *parsed* pass/fail XML.
"""

import sys
from decimal import Decimal
from pathlib import Path

from harness_bench.grade import correctness

VALID_ONE = '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0" /></testsuites>'


def _hidden(task_dir: Path, body: str) -> None:
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests" / "test_hidden.py").write_text(body, encoding="utf-8")


def _grade(tmp_path: Path, command: list[str]) -> correctness.Result:
    ws = tmp_path / "ws"
    ws.mkdir()
    run = tmp_path / "run"
    return correctness.grade(ws, tmp_path / "task", {"runner": "pytest", "command": command}, run / "out", run, 60)


def _pytest_grade(tmp_path: Path, body: str, junitxml: str = "report.xml") -> correctness.Result:
    _hidden(tmp_path / "task", body)
    command = [sys.executable, "-m", "pytest", "-q", f"--junitxml={junitxml}", "test_hidden.py"]
    return _grade(tmp_path, command)


def test_a_passing_pytest_report_scores_full_credit(tmp_path):
    result = _pytest_grade(tmp_path, "def test_a():\n    assert 1 == 1\n")
    assert (result.passed, result.partial_credit, result.reason) == (1, Decimal(1), None)


def test_a_failing_pytest_report_gets_partial_credit(tmp_path):
    body = "def test_a():\n    assert 1 == 1\n\n\ndef test_b():\n    assert 1 == 2\n"
    result = _pytest_grade(tmp_path, body)
    assert (result.passed, result.partial_credit, result.reason) == (0, Decimal(1) / Decimal(2), None)


def test_a_collection_error_scores_0_not_na(tmp_path):  # the report still carries errors=1, tests=1
    result = _pytest_grade(tmp_path, "def test_a(:\n    pass\n")
    assert (result.passed, result.partial_credit, result.reason) == (0, Decimal(0), None)


def test_no_test_collected_is_na_no_hidden_test_ran(tmp_path):
    result = _pytest_grade(tmp_path, "# no tests here\n")
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "no hidden test ran")


def test_a_command_that_names_no_report_is_na(tmp_path):
    _hidden(tmp_path / "task", "def test_a():\n    assert 1 == 1\n")
    command = [sys.executable, "-m", "pytest", "-q", "test_hidden.py"]  # no --junitxml
    result = _grade(tmp_path, command)
    assert (result.passed, result.partial_credit, result.reason) == \
        (None, None, "oracle command has no named JUnit XML report")


def test_a_nested_junitxml_path_is_rejected_as_no_report_named(tmp_path):  # _pytest_spec: a bare name only
    result = _pytest_grade(tmp_path, "def test_a():\n    assert 1 == 1\n", junitxml="nested/report.xml")
    assert (result.passed, result.partial_credit, result.reason) == \
        (None, None, "oracle command has no named JUnit XML report")


def test_a_non_xml_junitxml_suffix_is_rejected_as_no_report_named(tmp_path):
    result = _pytest_grade(tmp_path, "def test_a():\n    assert 1 == 1\n", junitxml="report.txt")
    assert (result.passed, result.partial_credit, result.reason) == \
        (None, None, "oracle command has no named JUnit XML report")


def test_a_stale_report_is_removed_and_a_process_that_writes_none_is_na(tmp_path):
    # A command that names a report but never runs pytest (so it writes none): a stale copy already in the
    # archived working copy must not be read as if it were fresh (mirrors test_dotnet_oracle_does_not_read_stale_trx).
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "report.xml").write_text(VALID_ONE, encoding="utf-8")
    _hidden(tmp_path / "task", "def test_a():\n    assert 1 == 1\n")
    run = tmp_path / "run"
    command = [sys.executable, "-c", "import sys; sys.exit(1)", "--junitxml=report.xml"]
    result = correctness.grade(ws, tmp_path / "task", {"runner": "pytest", "command": command}, run / "out", run, 60)
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "named JUnit XML report missing")


def test_multiple_named_reports_are_na(tmp_path):
    _hidden(tmp_path / "task", "def test_a():\n    assert 1 == 1\n")
    helper = tmp_path / "task" / "tests" / "write_two.py"
    helper.write_text(
        "import pathlib\n"
        f"content = {VALID_ONE!r}\n"
        "pathlib.Path('a').mkdir()\n"
        "pathlib.Path('b').mkdir()\n"
        "pathlib.Path('a/report.xml').write_text(content)\n"
        "pathlib.Path('b/report.xml').write_text(content)\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(helper), "--junitxml=report.xml"]
    result = _grade(tmp_path, command)
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "multiple named JUnit XML reports")


def test_an_unparsable_report_is_na_never_0(tmp_path):
    _hidden(tmp_path / "task", "def test_a():\n    assert 1 == 1\n")
    helper = tmp_path / "task" / "tests" / "write_garbage.py"
    helper.write_text("import pathlib\npathlib.Path('report.xml').write_text('<testsuites')\n", encoding="utf-8")
    command = [sys.executable, str(helper), "--junitxml=report.xml"]
    result = _grade(tmp_path, command)
    assert (result.passed, result.partial_credit, result.reason) == (None, None, "named JUnit XML report is unparsable")


def test_the_pytest_report_reader_sums_every_testsuite_element(tmp_path):
    path = tmp_path / "r.xml"
    path.write_text(
        '<testsuites><testsuite tests="2" failures="1" errors="0" skipped="0" />'
        '<testsuite tests="3" failures="0" errors="1" skipped="1" /></testsuites>',
        encoding="utf-8",
    )
    assert hasattr(correctness, "parse_pytest"), "correctness.parse_pytest is not built yet"
    assert correctness.parse_pytest(path) == (5, 2)  # 5 - (1 failure + 1 error + 1 skipped) = 2 passed


def test_the_pytest_report_reader_accepts_a_bare_testsuite_root(tmp_path):
    path = tmp_path / "r.xml"
    path.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0" />', encoding="utf-8")
    assert hasattr(correctness, "parse_pytest"), "correctness.parse_pytest is not built yet"
    assert correctness.parse_pytest(path) == (1, 1)
