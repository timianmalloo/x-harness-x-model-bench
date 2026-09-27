"""The mutation checker counts a kill only when a named test fails (Test Architect review, 2026-09-24).

A collection error, a timeout, or a failure of some other test is not evidence that the guard is tested.
"""

import base64
import hashlib
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
    (1, ("python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
         "[Errno 2] No such file or directory\n"), "error"),
    (0, ("python: can't open file 'C:\\\\proj\\\\.venv\\\\Scripts\\\\python.exe': "
         "[Errno 2] No such file or directory\n"), "error"),  # exit 0 with no summary is not a pass
])
def test_only_a_named_failure_is_a_kill(returncode, output, expected):
    assert mutate_check.verdict(returncode, output, NAMED) == expected


def test_a_named_parametrized_test_matches_its_cases():
    output = "FAILED tests/test_grade.py::test_parse[stderr6-None] - assert\n"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_grade.py::test_parse_other"]) == "survived"


def test_a_parametrized_case_whose_id_has_spaces_can_be_named():
    # W2-STOP-I slice 5: `\S+` cut the node id at the first space, so a case id with spaces could never be a kill.
    case = "tests/test_engine.py::test_tick_order[answer and timeout in one tick]"
    output = f"FAILED {case} - AssertionError: x\n"
    assert mutate_check.verdict(1, output, [case]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_engine.py::test_tick_order[answer only]"]) == "survived"


def test_a_named_file_matches_any_test_in_it():
    output = "FAILED tests/test_engine.py::test_parallelism_is_never_exceeded - x\n"
    assert mutate_check.verdict(1, output, ["tests/test_engine.py"]) == "killed"
    assert mutate_check.verdict(1, output, ["tests/test_views.py"]) == "survived"


# --- a named killer runs whatever its marker; a skip or deselect is "not run" ----------------
#
# pyproject addopts is `-m 'not credentials and not slow'`. pytest prepends addopts and `-m` is
# store, so the later `-m` wins, and an empty markexpr does not deselect (pytest 9.1.1
# `_pytest/mark/__init__.py:deselect_by_mark`; a named `@pytest.mark.slow` test is
# "1 deselected" exit 5 under that addopts, and runs under `-m ""`). A killer that still does
# not execute — skipped, or deselected by an option `-m` does not clear — is "not run".


def _killer_spec(tmp_path, test_source: str, pyproject: str | None = None) -> Path:
    (tmp_path / "m.py").write_bytes(b"X = 1\n")
    (tmp_path / "test_m.py").write_text(test_source, encoding="utf-8")
    if pyproject is not None:
        (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps([{
        "name": "cap", "file": "m.py", "find": "X = 1", "replace": "X = 2",
        "tests": ["test_m.py::test_x"],
    }]), encoding="utf-8")
    return spec


def test_a_named_test_with_a_deselected_marker_still_runs_and_is_killed(tmp_path, monkeypatch, capsys):
    """The marker filter in addopts must not hide a killer. This fails while the named test is deselected."""
    spec = _killer_spec(
        tmp_path,
        "import pytest\nimport m\n\n@pytest.mark.slow\ndef test_x():\n    assert m.X == 1\n",
        "[tool.pytest.ini_options]\naddopts = \"-m 'not slow'\"\nmarkers = [\"slow: slow\"]\n",
    )
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    rc = mutate_check.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert out.splitlines()[0].startswith("killed")
    assert (tmp_path / "m.py").read_bytes() == b"X = 1\n"


def test_a_named_test_that_skips_is_not_run(tmp_path, monkeypatch, capsys):
    """A skip is not a kill and not an error. The pytest reason line is part of the outcome."""
    spec = _killer_spec(
        tmp_path,
        "import pytest\nimport m\n\ndef test_x():\n    pytest.skip('killer not exercised')\n    assert m.X == 1\n",
    )
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    rc = mutate_check.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert out.splitlines()[0].startswith("not run")
    assert "killer not exercised" in out
    assert "1 not killed" in out
    assert (tmp_path / "m.py").read_bytes() == b"X = 1\n"


def test_a_named_test_deselected_by_something_other_than_the_marker_is_not_run(tmp_path, monkeypatch, capsys):
    """`--deselect` is not cleared by `-m ""`. Exit 5 with every test deselected is "not run", not "error"."""
    spec = _killer_spec(
        tmp_path,
        "import m\n\ndef test_x():\n    assert m.X == 1\n",
        "[tool.pytest.ini_options]\naddopts = \"--deselect=test_m.py::test_x\"\n",
    )
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    rc = mutate_check.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert out.splitlines()[0].startswith("not run")
    assert "deselected" in out
    assert "1 not killed" in out
    assert (tmp_path / "m.py").read_bytes() == b"X = 1\n"


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


def test_non_ascii_test_output_is_decoded_as_utf8_not_the_locale(tmp_path, monkeypatch):
    """W2-USER-M finding: pytest's output was decoded with the locale codec (cp1252 here), so a failing test whose
    message holds U+3041 (UTF-8 E3 81 81; 0x81 is undefined in cp1252) crashed the tool instead of counting a kill."""
    (tmp_path / "m.py").write_bytes(b"X = 1\n")
    (tmp_path / "test_m.py").write_text('import m\n\n\ndef test_x():\n    assert m.X == 1, "ぁ"\n', encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps([{"name": "one", "file": "m.py", "find": "X = 1", "replace": "X = 2",
                                 "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    monkeypatch.setattr(mutate_check, "ROOT", tmp_path)
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")  # the child writes UTF-8 bytes, as pytest did in the finding
    assert mutate_check.main([str(spec)]) == 0  # killed, and no UnicodeDecodeError


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


# --- W3-MUT-SWEEP control: a mutation's `find` must occur exactly once in its `file` -----------
#
# W3-GW-I slice 3 found ~16 mutants across several files whose `find` text no longer occurred (or,
# after a guard split into two near-identical branches, occurred twice) in its `file`, because the
# guarded code moved under a later commit and the mutation spec was never re-pointed. mutate_check's
# own SKIP path silently counts that as "not killed" and prints one line among many, so it was easy
# to miss (validity.json's R-15 sweep and views_copilot.json's two mapper mutants, named in the
# W3-MUT-SWEEP brief). This is a fast, mutation-free count check -- it never runs pytest, never
# writes a source file -- so it can run on every push and catch the drift the day the guarded code
# moves, not the next time someone happens to run the slow full mutate_check.py pass by file.

MUTATIONS_DIR = mutate_check.ROOT / "tests" / "mutations"


def _mutation_files() -> list[Path]:
    return sorted(MUTATIONS_DIR.glob("*.json"))


def _find_text_occurrences() -> list[tuple[str, str, str, int]]:
    """(mutation_file_name, mutation_name, target_file, occurrence_count) for every mutation in
    every tests/mutations/*.json, reading each target file at most once."""
    cache: dict[str, str] = {}
    rows: list[tuple[str, str, str, int]] = []
    for jf in _mutation_files():
        spec = json.loads(jf.read_text(encoding="utf-8"))
        for m in spec:
            if m["file"] not in cache:
                target = mutate_check.ROOT / m["file"]
                cache[m["file"]] = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.is_file() else ""
            rows.append((jf.name, m["name"], m["file"], cache[m["file"]].count(m["find"])))
    return rows


def test_every_mutation_find_text_occurs_exactly_once_in_its_target_file():
    stale = [(jf, name, tfile, n) for jf, name, tfile, n in _find_text_occurrences() if n != 1]
    assert not stale, "stale or ambiguous mutation finds (file, mutant, target, occurrences):\n" + "\n".join(
        f"  {jf}: {name!r} in {tfile} occurs {n} time(s)" for jf, name, tfile, n in stale)


# --- MUT-A: a kill between apply and restore leaves the mutant in the tree -------------------
#
# try/finally does not run when the process tree is killed. KeyboardInterrupt would still run it,
# so these tests call the apply half and stop, which is the kill. Every repo here is git init'd
# under tmp_path. Nothing touches the checkout this suite was launched from.


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE"}}


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, env=_git_env())
    return path


def _sidecar_of(repo: Path) -> Path:
    """The sidecar path the contract names: `<git rev-parse --git-dir>/mutate-applied.json`."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8", env=_git_env(),
    )
    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    return git_dir / "mutate-applied.json"


def _plant_sidecar(repo: Path, rel: str, original: bytes) -> Path:
    path = _sidecar_of(repo)
    path.write_text(json.dumps({
        "file": rel,
        "sha256": hashlib.sha256(original).hexdigest(),
        "original_b64": base64.b64encode(original).decode("ascii"),
    }), encoding="utf-8")
    return path


def test_an_interrupted_apply_leaves_a_sidecar_and_restore_returns_the_original_bytes(tmp_path, monkeypatch, capsys):
    """Sidecar before the mutant bytes, in this worktree's git dir; --restore writes the original back."""
    env = _git_env()
    main_repo = _git_init(tmp_path / "main")
    original = b"X = 1\n"
    (main_repo / "m.py").write_bytes(original)
    subprocess.run(["git", "add", "m.py"], cwd=main_repo, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "-c", "user.email=muta@example.com", "-c", "user.name=muta", "commit", "-m", "init"],
        cwd=main_repo, check=True, capture_output=True, env=env,
    )
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
        cwd=main_repo, check=True, capture_output=True, env=env,
    )
    monkeypatch.setattr(mutate_check, "ROOT", worktree)
    target = worktree / "m.py"
    mutated = b"X = 2\n"
    real_write = Path.write_bytes

    def write_bytes(self, data):
        if Path(self) == target and data == mutated:
            side = _sidecar_of(worktree)
            assert side.is_file()
            record = json.loads(side.read_text(encoding="utf-8"))
            assert record["file"] == "m.py"
            assert record["sha256"] == hashlib.sha256(original).hexdigest()
            assert base64.b64decode(record["original_b64"]) == original
            assert not (main_repo / ".git" / "mutate-applied.json").exists()
        if Path(self) == target and data == original:
            assert _sidecar_of(worktree).is_file()
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    try:
        mutate_check.apply_mutation("m.py", original, mutated)
        side = _sidecar_of(worktree)
        assert target.read_bytes() == mutated
        assert side.is_file()
        rc = mutate_check.main(["--restore"])
        out = capsys.readouterr().out
        assert rc == 0
        assert target.read_bytes() == original
        assert not side.exists()
        assert "restored" in out
        assert "m.py" in out
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=main_repo, capture_output=True, env=env, check=False,
        )


def test_restore_removes_a_sidecar_when_the_file_already_matches(tmp_path, monkeypatch, capsys):
    repo = _git_init(tmp_path / "repo")
    original = b"X = 1\n"
    (repo / "m.py").write_bytes(original)
    monkeypatch.setattr(mutate_check, "ROOT", repo)
    side = _plant_sidecar(repo, "m.py", original)
    rc = mutate_check.main(["--restore"])
    out = capsys.readouterr().out
    assert rc == 0
    assert not side.exists()
    assert (repo / "m.py").read_bytes() == original
    assert "m.py" in out


def test_restore_with_no_sidecar_says_nothing_to_restore(tmp_path, monkeypatch, capsys):
    repo = _git_init(tmp_path / "repo")
    monkeypatch.setattr(mutate_check, "ROOT", repo)
    rc = mutate_check.main(["--restore"])
    assert rc == 0
    assert "nothing to restore" in capsys.readouterr().out


def test_a_normal_run_leaves_no_sidecar(tmp_path, monkeypatch):
    repo = _git_init(tmp_path / "repo")
    (repo / "m.py").write_bytes(b"X = 1\n")
    (repo / "test_m.py").write_bytes(b"import m\n\n\ndef test_x():\n    assert m.X == 1\n")
    spec = repo / "spec.json"
    spec.write_text(json.dumps([{"name": "one", "file": "m.py", "find": "X = 1", "replace": "X = 2",
                                 "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    monkeypatch.setattr(mutate_check, "ROOT", repo)
    assert mutate_check.main([str(spec)]) == 0
    assert (repo / "m.py").read_bytes() == b"X = 1\n"
    assert not _sidecar_of(repo).exists()


def test_a_run_refuses_to_start_while_a_sidecar_exists(tmp_path, monkeypatch, capsys):
    repo = _git_init(tmp_path / "repo")
    original = b"X = 1\n"
    mutated = b"X = 2\n"
    (repo / "m.py").write_bytes(mutated)
    (repo / "test_m.py").write_bytes(b"import m\n\n\ndef test_x():\n    assert m.X == 1\n")
    spec = repo / "spec.json"
    spec.write_text(json.dumps([{"name": "one", "file": "m.py", "find": "X = 1", "replace": "X = 9",
                                 "tests": ["test_m.py::test_x"]}]), encoding="utf-8")
    monkeypatch.setattr(mutate_check, "ROOT", repo)
    side = _plant_sidecar(repo, "m.py", original)
    rc = mutate_check.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 2
    assert "m.py" in out
    assert "--restore" in out
    assert (repo / "m.py").read_bytes() == mutated
    assert side.is_file()


@pytest.mark.parametrize(("recorded_file", "expected_rc"), [
    (None, 0),
    ("m.py", 1),
])
def test_check_clean_exits_1_naming_the_file_only_when_a_sidecar_exists(
        tmp_path, monkeypatch, capsys, recorded_file, expected_rc):
    repo = _git_init(tmp_path / "repo")
    monkeypatch.setattr(mutate_check, "ROOT", repo)
    if recorded_file is not None:
        _plant_sidecar(repo, recorded_file, b"X = 1\n")
    rc = mutate_check.main(["--check-clean"])
    out = capsys.readouterr().out
    assert rc == expected_rc
    if recorded_file is not None:
        assert recorded_file in out
