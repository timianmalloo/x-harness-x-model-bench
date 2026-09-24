"""The mutation checker counts a kill only when a named test fails (Test Architect review, 2026-09-24).

A collection error, a timeout, or a failure of some other test is not evidence that the guard is tested.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("mutate_check", Path(__file__).resolve().parents[1] / "tools" / "mutate_check.py")
mutate_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mutate_check)

NAMED = ["tests/test_engine.py::test_parallelism_is_never_exceeded"]


@pytest.mark.parametrize(("returncode", "output", "expected"), [
    (1, "FAILED tests/test_engine.py::test_parallelism_is_never_exceeded - assert 3 <= 2\n1 failed", "killed"),
    (1, "FAILED tests/test_engine.py::test_other_thing - boom\n1 failed", "survived"),  # the wrong test failed
    (2, "ERROR tests/test_engine.py - SyntaxError\n1 error", "error"),  # collection error: not a kill
    (0, "1 passed", "survived"),
    (None, "", "timeout"),  # a hang is not a kill
    # T2/W1-ACP join finding: the .venv vanished mid-run (the interpreter itself is gone). No
    # pytest summary line and no FAILED line ever appears -- a broken environment, not a real
    # test outcome -- regardless of what exit code the shell happens to report.
    (1, "python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
        "[Errno 2] No such file or directory\n", "error"),
    (0, "python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
        "[Errno 2] No such file or directory\n", "error"),  # exit 0 with no summary is not a pass
])
def test_only_a_named_failure_is_a_kill(returncode, output, expected):
    assert mutate_check.verdict(returncode, output, NAMED) == expected


def test_a_named_parametrized_test_matches_its_cases():
    output = "FAILED tests/test_grade.py::test_parse[stderr6-None] - assert\n"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse_other"]) == "survived"


def test_a_named_file_matches_any_test_in_it():
    output = "FAILED tests/test_engine.py::test_parallelism_is_never_exceeded - x\n"
    assert mutate_check.verdict(1, output, ["tests/test_engine.py"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_views.py"]) == "survived"


def test_a_same_size_mutation_leaves_no_stale_bytecode(tmp_path, monkeypatch):
    """TOOL-A (found by T10): a mutant compiled to .pyc, restored in the same mtime second with the same size, is
    still what `import` loads, so the next run tests the mutant while `git status` is clean. The race is made
    deterministic here: the restored source is given the mtime recorded in any .pyc the run left behind."""
    (tmp_path / "m.py").write_bytes(b"X = 30.0\n")  # LF, as the repo's sources are: the mutant then has the same size
    (tmp_path / "test_m.py").write_bytes(b"import m\n\n\ndef test_x():\n    assert m.X == 30.0\n")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps([{"name": "cap", "file": "m.py", "find": "X = 30.0", "replace": "X = 60.0",
                                 "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)  # an ambient value would hide a revert of the fix
    assert mutate_check.main([str(spec)]) == 0  # the mutation is killed
    for pyc in (tmp_path / "__pycache__").glob("m.*.pyc"):
        recorded = int.from_bytes(pyc.read_bytes()[8:12], "little")  # PEP 552 header: source mtime at compile time
        os.utime(tmp_path / "m.py", (recorded, recorded))
    loaded = subprocess.run([sys.executable, "-c", "import m; print(m.X)"], cwd=tmp_path, capture_output=True, text=True,
                            timeout=60, check=True)
    assert loaded.stdout.strip() == "30.0"


# --- TOOL-B: a cosmic-ray "killed" is re-derived from a named test failing --------------------
#
# cosmic-ray 8.7.0's WorkResult (cosmic_ray/work_item.py) has no exit code: `testing.run_tests`
# (read at C:\Users\malla\AppData\Local\uv\cache\archive-v0\PdlzIZscLpkdaw3H\Lib\site-packages\
# cosmic_ray\testing.py:73-75, cosmic-ray 8.7.0) calls TestOutcome.KILLED for *any* non-zero exit
# from the test command -- a real test failure, a collection error, or any other non-zero exit
# alike -- and KILLED with output=="timeout" (the literal sentinel string) for a hang. Only a
# `FAILED <node id>` line naming one of the mutation's own tests is evidence of a real kill; a
# collection error or an unrelated pytest failure carries no such line and must not be counted.
# `cli.py:dump` (the only way session data leaves cosmic-ray; `cosmic_ray.commands.dump` is not a
# module) serialises each WorkResult as {"worker_outcome", "output", "test_outcome", "diff"}.

CR_NAMED = ["tests/test_ledger.py::test_tail_repaired", "tests/test_ledger.py"]


@pytest.mark.parametrize(("result", "expected_verdict", "expected_test"), [
    (
        {"worker_outcome": "normal", "test_outcome": "killed",
         "output": "FAILED tests/test_ledger.py::test_tail_repaired - assert 1 == 2\n1 failed", "diff": "x"},
        "killed", "tests/test_ledger.py::test_tail_repaired",
    ),
    (
        {"worker_outcome": "normal", "test_outcome": "survived", "output": "5 passed", "diff": "x"},
        "survived", None,
    ),
    (
        # the wrong test failed: a real pytest run, exit 1, but no FAILED line names this mutant's test
        {"worker_outcome": "normal", "test_outcome": "killed",
         "output": "FAILED tests/test_views.py::test_other - boom\n1 failed", "diff": "x"},
        "survived", None,
    ),
    (
        # a collection error (an ImportError before any test runs): cosmic-ray still calls this
        # KILLED (testing.py:73, returncode != 0), but no FAILED line ever appears -- not a kill.
        {"worker_outcome": "normal", "test_outcome": "killed",
         "output": "ERRORS\nERROR tests/test_ledger.py - ImportError: cannot import name 'x'\n"
                    "!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n1 error in 0.31s",
         "diff": "x"},
        "error", None,
    ),
    (
        # an exit-2 run interrupted before producing a single FAILED line (e.g. -x on a fixture
        # crash): still non-zero exit, still KILLED per cosmic-ray, still not a named kill.
        {"worker_outcome": "normal", "test_outcome": "killed",
         "output": "!!!!!!!!!!!!!!!!!!! Interrupted: fixture 'base' failed !!!!!!!!!!!!!!!!!!!!\n2 errors in 4.01s",
         "diff": "x"},
        "error", None,
    ),
    (
        # cosmic-ray's own timeout sentinel (testing.py:69-71): a hang is not a kill.
        {"worker_outcome": "normal", "test_outcome": "killed", "output": "timeout", "diff": None},
        "timeout", None,
    ),
    (
        # a launch failure (e.g. a bad interpreter path, T2's record): INCOMPETENT, not a kill.
        {"worker_outcome": "normal", "test_outcome": "incompetent",
         "output": "Traceback (most recent call last):\nFileNotFoundError", "diff": None},
        "error", None,
    ),
    (
        # the worker itself crashed applying the mutation (mutating.py's outer except): not a kill.
        {"worker_outcome": "exception", "test_outcome": "incompetent", "output": "Traceback...", "diff": None},
        "error", None,
    ),
    (
        # no result yet (dump's pending_work_items: WorkResult is null).
        None, "pending", None,
    ),
    (
        # T2/W1-ACP join finding: worker_outcome is "normal" and cosmic-ray still calls this
        # "killed" (non-zero exit, testing.py:73), but the .venv vanished mid-run -- no FAILED
        # line, no pytest summary at all. Not a kill.
        {"worker_outcome": "normal", "test_outcome": "killed",
         "output": "python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
                    "[Errno 2] No such file or directory\n", "diff": "x"},
        "error", None,
    ),
    (
        # same broken environment, but this time the shell's exit code happened to be 0 --
        # cosmic-ray calls it "survived". Still no summary line: still an error, not a pass.
        {"worker_outcome": "normal", "test_outcome": "survived",
         "output": "python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
                    "[Errno 2] No such file or directory\n", "diff": "x"},
        "error", None,
    ),
])
def test_cosmic_ray_verdict_only_a_named_failure_is_a_kill(result, expected_verdict, expected_test):
    assert mutate_check.cosmic_ray_verdict(result, CR_NAMED) == (expected_verdict, expected_test)


def test_named_tests_for_matches_exact_file_then_directory_prefix_then_nothing():
    test_map = {
        "src/harness_bench/ledger.py": ["tests/test_ledger.py"],
        "src/harness_bench/grade": ["tests/test_grade.py", "tests/test_report.py"],
    }
    assert mutate_check.named_tests_for(["src/harness_bench/ledger.py"], test_map) == ["tests/test_ledger.py"]
    assert mutate_check.named_tests_for(["src/harness_bench/grade/runner.py"], test_map) == \
        ["tests/test_grade.py", "tests/test_report.py"]
    assert mutate_check.named_tests_for(["src/harness_bench/views.py"], test_map) == []


def test_named_tests_for_normalises_windows_separators():
    # cosmic-ray's dump stringifies module_path with Path.__str__, which is backslash-separated
    # on Windows (cli.py:_work_item_to_dict), and this ran natively on Windows (mutation-record-t2.md).
    test_map = {"src/harness_bench/grade": ["tests/test_grade.py"]}
    assert mutate_check.named_tests_for([r"src\harness_bench\grade\runner.py"], test_map) == ["tests/test_grade.py"]


def _dump_line(job_id, module_path, result):
    work_item = {"job_id": job_id, "mutations": [
        {"module_path": module_path, "operator_name": "op", "occurrence": 0,
         "start_pos": [1, 0], "end_pos": [1, 1], "operator_args": {}, "definition_name": None},
    ]}
    return json.dumps([work_item, result])


def test_derive_cosmic_ray_counts_overstated_kills():
    test_map = {"src/harness_bench/ledger.py": ["tests/test_ledger.py::test_tail_repaired"]}
    lines = [
        _dump_line("j1", "src/harness_bench/ledger.py",
                   {"worker_outcome": "normal", "test_outcome": "killed",
                    "output": "FAILED tests/test_ledger.py::test_tail_repaired - x\n1 failed", "diff": "x"}),
        _dump_line("j2", "src/harness_bench/ledger.py",
                   {"worker_outcome": "normal", "test_outcome": "killed",
                    "output": "ERROR tests/test_ledger.py - SyntaxError\n1 error", "diff": "x"}),
        _dump_line("j3", "src/harness_bench/ledger.py",
                   {"worker_outcome": "normal", "test_outcome": "survived", "output": "1 passed", "diff": "x"}),
    ]
    records, overstated = mutate_check.derive_cosmic_ray(lines, test_map)
    assert [r["verdict"] for r in records] == ["killed", "error", "survived"]
    assert overstated == 1  # j2: cosmic-ray called it killed, no named test failed


def test_cli_cosmic_ray_mode_exits_1_on_an_overstated_kill(tmp_path, capsys):
    test_map = tmp_path / "test-map.json"
    test_map.write_text(json.dumps({"src/harness_bench/ledger.py": ["tests/test_ledger.py"]}), encoding="utf-8")
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        _dump_line("j1", "src/harness_bench/ledger.py",
                    {"worker_outcome": "normal", "test_outcome": "killed", "output": "timeout", "diff": None}) + "\n",
        encoding="utf-8",
    )
    rc = mutate_check.main(["--cosmic-ray", str(test_map), str(dump)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "timeout" in out
    assert "1 overstated" in out


def test_cli_cosmic_ray_mode_exits_0_when_every_kill_is_named(tmp_path, capsys):
    test_map = tmp_path / "test-map.json"
    test_map.write_text(json.dumps({"src/harness_bench/ledger.py": ["tests/test_ledger.py::test_x"]}), encoding="utf-8")
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        _dump_line("j1", "src/harness_bench/ledger.py",
                    {"worker_outcome": "normal", "test_outcome": "killed",
                     "output": "FAILED tests/test_ledger.py::test_x - x\n1 failed", "diff": "x"}) + "\n",
        encoding="utf-8",
    )
    rc = mutate_check.main(["--cosmic-ray", str(test_map), str(dump)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 overstated" in out
