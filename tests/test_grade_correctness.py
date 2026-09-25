"""Correctness grader: the C-2 move, build_and_suite_clean and DR-G4 decided by cause (design phase3-graders, GR-CODE c1).

- The gate-run test grades the archived cells of `HB_GATE_RUNS` in place, read-only: every output goes under
  `tmp_path`, and the archive's bytes are compared before and after (F9). It skips when the runs are not on this host.
- The D1 fixtures are the frozen `tasks/D1/workspace` in a temporary git repo that reproduces the archive's commits
  (G9), with a seeded overlay. They need the pinned dotnet SDK and the offline NuGet cache; without them they skip,
  and with `HB_REQUIRE_DOTNET=1` they fail instead (the design's slow-ring rule).
"""

import dataclasses
import hashlib
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT

from harness_bench import config, plan, views
from harness_bench.grade import CellInput, Score, correctness
from harness_bench.grade.runner import applicable

GATE_RUNS = Path(os.environ.get("HB_GATE_RUNS") or ROOT / "runs")
CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
SCALES = {m["id"]: m.get("scale") for a in CATALOG["areas"].values() for m in a.get("metrics") or []}


def encode(score) -> tuple:
    """(value, reason) as the runner writes them: a Decimal at the catalog scale."""
    v = score.value
    return (f"{v:.{SCALES['partial_credit']}f}" if isinstance(v, Decimal) else v), score.reason


def tree_digest(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def cell_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    task = config.load_yaml(task_dir / "task.yaml")
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": timeout}}, cell=cell, task=task,
                     task_dir=task_dir, archive=archive, out_dir=out_dir, events=(), record_reason=None, model_calls=(),
                     tool_calls=(), turn_usage=(), metrics=applicable(CATALOG, ["correctness"])["correctness"],
                     allow_model_calls=False, extraction=None, prices=None)


# --- seam C-2: pass_at_1 and partial_credit equal the 0.3 values on the gate runs (read-only) ----------------------


GATE = sorted(config.load_yaml(ROOT / "bench" / "regrade-baseline-0.3.yaml")["runs"])


@pytest.mark.parametrize("name", GATE)
def test_the_moved_grader_gives_the_gate_runs_0_3_correctness_and_leaves_the_archive_unchanged(tmp_path, name):
    run = GATE_RUNS / name
    if not (run / "plan.json").is_file():
        pytest.skip(f"gate run {name} is not on this host (set HB_GATE_RUNS to the runs folder)")
    was = {c.cell_id: {m: (s.value, s.reason) for m, s in c.scores.items() if m in ("pass_at_1", "partial_credit")}
           for c in views.load(run, "0.3").cells}
    attempts = {e["cell_id"]: e["archive_attempt"] for e in views.rows(run, "events") if e["kind"] == "cell.archived"}
    cells = {c["cell_id"]: c for c in plan.load_confirmed(run)["cells"]}
    got = {}
    for cid, attempt in sorted(attempts.items()):
        folder = run / "archive" / cid / f"attempt-{attempt}"
        before = tree_digest(folder)
        out = correctness.grade_cell(cell_input(tmp_path, folder, cells[cid], tmp_path / "grading" / cid / "correctness"))
        got[cid] = {m: encode(out[m]) for m in ("pass_at_1", "partial_credit")}
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
    assert got == was


# --- D1 fixtures: the frozen workspace in a git repo that reproduces the archive's commits (G9) --------------------

D1 = ROOT / "tasks" / "D1"
D1_VERSION = plan.task_version_hash(D1)
PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
REFERENCE = {PROJECTION: (D1 / "oracle" / "reference" / PROJECTION).read_text(encoding="utf-8")}
BROKEN = {"src/AiDe.Core/Projections/Broken.cs":  # CS1002 at (5,31): the spike's syntax-error seed
          "namespace AiDe.Core.Projections;\n\npublic static class Broken\n{\n    public static int X() => 1\n}\n"}
PACKAGES = (("xunit", "2.9.3"), ("xunit.runner.visualstudio", "3.1.4"), ("microsoft.net.test.sdk", "17.14.1"))


@pytest.fixture(scope="module")
def d1_dotnet():
    """The pinned SDK and the offline cache, checked without the code under test (a skip must never hide a mutant)."""
    cache = Path(os.environ.get("NUGET_PACKAGES") or Path.home() / ".nuget" / "packages")
    if shutil.which("dotnet") is None or not all((cache / name / version).is_dir() for name, version in PACKAGES):
        if os.environ.get("HB_REQUIRE_DOTNET") == "1":
            pytest.fail("dotnet or the offline NuGet cache is missing and HB_REQUIRE_DOTNET=1")
        pytest.skip("dotnet not required: the D1 toolchain is not on this host (HB_REQUIRE_DOTNET=1 fails instead)")


def git(ws: Path, *args: str) -> str:
    from harness_bench import gitsafe

    return gitsafe.git(list(args), cwd=ws, timeout=120, identity=True).stdout.strip()


def without_member(text: str) -> str:
    """PathComparison.cs with `ForThisFileSystem` deleted; nine unchanged vendored call sites use it (spike: CS0117)."""
    return text[:text.index("    public static StringComparison ForThisFileSystem")].rstrip() + "\n}\n"


def d1_cell(tmp_path: Path, overlay: dict, pack: bool = False, commit: str | None = None) -> tuple[Path, dict]:
    """(archive folder, plan cell): the base commit, the pack stand-in commit when `pack`, then `overlay`
    (path -> text, or a function of the current text), uncommitted unless `commit` names a commit message."""
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    ws = folder / "ws"
    shutil.copytree(D1 / "workspace", ws)
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", f"D1 base ({D1_VERSION[:12]})")
    if pack:  # stand-in files outside the blast radius, and no pack material (design: Fixtures)
        (ws / ".editorconfig").write_text("root = true\n", encoding="utf-8")
        (ws / "docs" / "pack").mkdir(parents=True)
        (ws / "docs" / "pack" / "stand-in.md").write_text("pack stand-in\n", encoding="utf-8")
        git(ws, "add", "-A")
        git(ws, "commit", "-q", "-m", "ai-forward pack revision 95")
    for rel, text in overlay.items():
        path = ws / rel
        if callable(text):
            text = text(path.read_text(encoding="utf-8"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    if commit:
        git(ws, "add", "-A")
        git(ws, "commit", "-q", "-m", commit)
    cell = {"cell_id": "c1", "task": "D1", "task_version": D1_VERSION, "pack": "on" if pack else "off"}
    return folder, cell


def grade_d1(tmp_path: Path, folder: Path, cell: dict) -> dict[str, tuple]:
    """Every correctness Score of the cell as the runner writes it; the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = correctness.grade_cell(cell_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "correctness"))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return {m: encode(s) for m, s in out.items()}


BUILT_CORRECTNESS = ("pass_at_1", "partial_credit", "build_and_suite_clean")


def test_d1_base_plus_a_file_with_a_syntax_error_scores_0_not_na(tmp_path, d1_dotnet):  # DR-G4, R-67 c1
    got = grade_d1(tmp_path, *d1_cell(tmp_path, BROKEN))
    assert {m: got.get(m) for m in BUILT_CORRECTNESS} == \
        {"pass_at_1": (0, None), "partial_credit": ("0.0000", None), "build_and_suite_clean": (0, None)}


def test_d1_reference_with_a_member_deleted_that_unchanged_files_use_scores_0(tmp_path, d1_dotnet):  # TA 9: by cause
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {**REFERENCE, "src/AiDe.Core/PathComparison.cs": without_member}))
    assert {m: got.get(m) for m in BUILT_CORRECTNESS} == \
        {"pass_at_1": (0, None), "partial_credit": ("0.0000", None), "build_and_suite_clean": (0, None)}


IPC_TESTS = "tests/AiDe.Core.Tests/IpcFramingTests.cs"
IPC_KEY = "AiDe.Core.Tests.IpcFramingTests.Utf8Content_SurvivesIntact"


def inverted(text: str) -> str:
    """IpcFramingTests.cs with the one assertion of `Utf8Content_SurvivesIntact` inverted (it passes on the base)."""
    head, method, tail = text.partition("public async Task Utf8Content_SurvivesIntact()")
    body, rest = tail.split("[Fact]", 1)
    assert body.count("Assert.Equal(payload, result);") == 1
    return head + method + body.replace("Assert.Equal(payload, result);", "Assert.NotEqual(payload, result);") + "[Fact]" + rest


def test_d1_base_with_one_public_assertion_inverted_has_exactly_1_regression(tmp_path, d1_dotnet):  # GR-CODE c2
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {IPC_TESTS: inverted}))
    assert got.get("regression_count") == (1, None)
    log = tmp_path / "run" / "grading" / "g" / "c1" / "correctness" / "regressions" / "regressions.log"
    assert log.read_text(encoding="utf-8").splitlines()[-1:] == [f"regressed {IPC_KEY}"]


def test_an_empty_nuget_cache_is_na_restore_never_0(tmp_path, d1_dotnet, monkeypatch):  # F13: a failure before the build
    (tmp_path / "empty-nuget").mkdir()
    monkeypatch.setenv("NUGET_PACKAGES", str(tmp_path / "empty-nuget"))
    got = grade_d1(tmp_path, *d1_cell(tmp_path, REFERENCE))
    assert {m: got.get(m) for m in BUILT_CORRECTNESS} == \
        dict.fromkeys(BUILT_CORRECTNESS, (None, "infrastructure failure before build: restore"))


# --- the shared change reader: the pre-turn commit and the change set (git only; no dotnet) -------------------------


def changes_of(tmp_path: Path, folder: Path, cell: dict) -> tuple[str | None, dict[str, str] | None]:
    """(pre-turn commit, change set against it); the archive's bytes must not move (F9)."""
    from harness_bench.grade import _changes

    ws, out = folder / "ws", tmp_path / "out"
    before = tree_digest(folder)
    commit = _changes.pre_turn_commit(ws, cell, 120)
    changed = None
    if commit is not None:
        with _changes.pre_turn_tree(ws, commit, out / "pre-turn", 120) as base, _changes.grading_copy(ws, out / "copy") as copy:
            changed = _changes.change_set(base, copy)
        assert not (out / "pre-turn").exists() and not (out / "copy").exists(), "a disposable tree was left behind"
    assert tree_digest(folder) == before, "reading the changes wrote under the archive"
    return commit, changed


@pytest.mark.parametrize("committed", [None, "Add evidence census projection"])  # uncommitted, or 3ff0's own commit
def test_the_pack_on_base_is_the_pack_commit_so_the_pack_is_not_a_change(tmp_path, committed):  # F10
    folder, cell = d1_cell(tmp_path, {}, pack=True)
    pack_commit = git(folder / "ws", "rev-parse", "HEAD")
    for rel, text in REFERENCE.items():
        (folder / "ws" / rel).write_text(text, encoding="utf-8", newline="")
    (folder / "ws" / "src" / "AiDe.Core" / "bin").mkdir()  # build output never counts
    (folder / "ws" / "src" / "AiDe.Core" / "bin" / "AiDe.Core.dll").write_bytes(b"MZ")
    if committed:
        git(folder / "ws", "add", PROJECTION)
        git(folder / "ws", "commit", "-q", "-m", committed)
    assert changes_of(tmp_path, folder, cell) == (pack_commit, {PROJECTION: "added"})


def test_a_pack_off_cell_takes_the_root_even_when_its_second_commit_looks_like_a_pack(tmp_path):  # tamper rule
    folder, cell = d1_cell(tmp_path, {}, pack=True)
    root = git(folder / "ws", "rev-list", "--max-parents=0", "HEAD")
    cell["pack"] = "off"
    assert changes_of(tmp_path, folder, cell) == (root, {".editorconfig": "added", "docs/pack/stand-in.md": "added"})


def test_a_later_look_alike_pack_commit_is_ignored(tmp_path):  # tamper rule: only the root's first-parent child
    folder, cell = d1_cell(tmp_path, {}, pack=True)
    pack_commit = git(folder / "ws", "rev-parse", "HEAD")
    path = folder / "ws" / "src" / "AiDe.Core" / "PathComparison.cs"
    path.write_text(path.read_text(encoding="utf-8").replace("How two", "How 2"), encoding="utf-8", newline="")
    git(folder / "ws", "commit", "-q", "-a", "-m", "ai-forward pack revision 96")
    assert changes_of(tmp_path, folder, cell) == (pack_commit, {"src/AiDe.Core/PathComparison.cs": "changed"})


@pytest.mark.parametrize("fault", ["base message", "no pack commit"])
def test_no_builder_commit_is_na_pre_turn_commit_not_found(tmp_path, fault):  # F11
    folder, cell = d1_cell(tmp_path, {})
    if fault == "base message":  # history rewritten: the root no longer carries the builder's exact message
        git(folder / "ws", "commit", "-q", "--amend", "-m", f"D1 base ({D1_VERSION[:11]})")
    else:  # a pack-on cell whose pack commit is missing
        cell["pack"] = "on"
    assert changes_of(tmp_path, folder, cell) == (None, None)


def test_a_crlf_only_difference_and_a_deletion_are_read_by_content(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    ws = folder / "ws"
    path = ws / "src" / "AiDe.Core" / "PathComparison.cs"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))  # CRLF-normalised: not a change
    (ws / "LICENSE").unlink()
    assert changes_of(tmp_path, folder, cell)[1] == {"LICENSE": "deleted"}


# --- every disposition branch, fast: a fake dotnet (paired with the real D1 fixtures above, D7) ---------------------

RESTORE_LINE = r"C:\w\src\A\A.csproj : error NU1101: Unable to find package xunit. No packages exist with this id [x]"
COMPILE_LINE = r"C:\w\src\A\B.cs(5,31): error CS1002: ; expected [C:\w\src\A\A.csproj]"


def done(returncode=0, stdout="", timed_out=False):
    from harness_bench import procs

    return procs.Completed(returncode, stdout, "", timed_out, False, 0.0)


@pytest.mark.parametrize(("output", "cause"), [
    (RESTORE_LINE, "restore"), (COMPILE_LINE, "compile"), (COMPILE_LINE + "\n" + RESTORE_LINE, "restore"),
    ("warning MSB9008: The referenced project ../N/N.csproj does not exist.", None), ("", None),
])
def test_a_build_failure_is_classified_by_its_error_codes_restore_first(output, cause):
    assert correctness.build_failure(output) == cause


def fake_dotnet(monkeypatch, *results) -> list:
    """procs.run answers `results` in order (the same object for any further call); returns the argv seen."""
    seen, queue = [], list(results)

    def run(argv, **kwargs):
        seen.append(argv)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(correctness.procs, "run", run)
    return seen


def d1_input(tmp_path: Path, projects=("src/A/A.csproj", "tests/A.Tests/A.Tests.csproj")) -> CellInput:
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    for rel in projects:
        (folder / "ws" / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / "ws" / rel).write_text("<Project />", encoding="utf-8")
    (folder / "ws").mkdir(parents=True, exist_ok=True)
    cell = {"cell_id": "c1", "task": "D1", "task_version": D1_VERSION, "pack": "off"}
    return cell_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "correctness", timeout=60)


@pytest.mark.parametrize(("version", "oracle", "reason", "compile_error"), [
    (done(1), done(0), "infrastructure failure before build: sdk", False),
    (done(0, "10.0.303"), done(1, RESTORE_LINE), "infrastructure failure before build: restore", False),
    (done(0, "10.0.303"), done(1, COMPILE_LINE), "named TRX result file missing", True),
    (done(0, "10.0.303"), done(1, "no error line"), "named TRX result file missing", False),
])
def test_the_hidden_test_step_is_na_by_cause_and_flags_a_compile_error(tmp_path, monkeypatch, version, oracle, reason,
                                                                          compile_error):
    fake_dotnet(monkeypatch, version, oracle)
    inp = d1_input(tmp_path)
    c = correctness.grade(inp.archive / "ws", inp.task_dir, inp.task["oracle"], inp.out_dir, inp.run_dir, 60)
    assert (c.passed, c.partial_credit, c.reason, c.compile_error) == (None, None, reason, compile_error)


@pytest.mark.parametrize(("results", "expected"), [
    ((done(0, "10.0.303"), done(0)), (1, None)),
    ((done(0, "10.0.303"), done(1, COMPILE_LINE), done(0)), (0, None)),  # the first failure decides
    ((done(0, "10.0.303"), done(1, "warning only, exit 1")), (0, None)),
    ((done(0, "10.0.303"), done(1, RESTORE_LINE)), (None, "infrastructure failure before build: restore")),
    ((done(1),), (None, "infrastructure failure before build: sdk")),
    ((done(0, "10.0.303"), done(None, timed_out=True)), (None, "HB-GRD-002 grading step timeout after 60 s")),
])
def test_build_and_suite_clean_builds_every_project_and_is_na_only_before_the_build(tmp_path, monkeypatch, results,
                                                                                    expected):
    seen = fake_dotnet(monkeypatch, *results)
    inp = d1_input(tmp_path)
    got = correctness.build_and_suite_clean(inp, inp.task["oracle"], 60)
    assert (got.value, got.reason) == expected
    assert got.evidence == "grading/g/c1/correctness/build/build.log"
    assert seen[0] == ["dotnet", "--version"]
    assert [a[:3] for a in seen[1:]] == [["dotnet", "build", p] for p in ("src/A/A.csproj", "tests/A.Tests/A.Tests.csproj")][:len(seen) - 1]
    assert all(a[3:] == ["-p:RestoreSources=.", "-p:NuGetAudit=false", "-v:q", "-nologo"] for a in seen[1:])


def test_a_dotnet_working_copy_with_no_project_is_not_a_clean_build(tmp_path, monkeypatch):
    fake_dotnet(monkeypatch, done(0, "10.0.303"))
    inp = d1_input(tmp_path, projects=())
    got = correctness.build_and_suite_clean(inp, inp.task["oracle"], 60)
    assert (got.value, got.reason) == (0, None)


@pytest.mark.parametrize(("source", "value"), [("def slugify(text):\n    return (\n", 0), ("x = 1\n", 1)])
def test_build_and_suite_clean_compiles_a_python_copy(tmp_path, source, value):  # the seeded .py syntax error -> 0
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    (folder / "ws").mkdir(parents=True)
    (folder / "ws" / "slug.py").write_text(source, encoding="utf-8")
    inp = cell_input(tmp_path / "run", folder, {"cell_id": "c1", "task": "X1"}, tmp_path / "run" / "grading" / "g" / "c1" / "correctness")
    before = tree_digest(folder)
    got = correctness.build_and_suite_clean(inp, inp.task["oracle"], 60)
    assert (got.value, got.reason) == (value, None)
    assert tree_digest(folder) == before  # compileall wrote its .pyc into the copy, never the archive


# --- DR-G4's pre-turn control (R-67 c1), with the oracle faked and a real two-commit repository ----------------------

T9_VERSION = "ab" * 32


def control_cell(tmp_path: Path, base_message: str = f"T9 base ({T9_VERSION[:12]})") -> CellInput:
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    (folder / "ws").mkdir(parents=True)
    (folder / "ws" / "a.cs").write_text("class A {}\n", encoding="utf-8")
    git(folder / "ws", "init", "-q", "-b", "main")
    git(folder / "ws", "add", "-A")
    git(folder / "ws", "commit", "-q", "-m", base_message)
    (folder / "ws" / "a.cs").write_text("class A {\n", encoding="utf-8")  # the cell's uncommitted break
    cell = {"cell_id": "c1", "task": "D1", "task_version": D1_VERSION, "pack": "off"}
    inp = cell_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "correctness")
    return dataclasses.replace(inp, cell={**cell, "task": "T9", "task_version": T9_VERSION})


CELL_BROKE = correctness.Result(None, None, "named TRX result file missing", "grading/g/c1/correctness/oracle.log", True)


@pytest.mark.parametrize(("control", "expected"), [
    (correctness.Result(0, Decimal(0), None, "x"), (0, "0.0000", None)),  # the pre-turn tree compiles and its tests run
    (correctness.Result(None, None, "named TRX result file missing", "x", True), (None, None, "pre-turn tree does not build")),
    (correctness.Result(None, None, "named TRX result file missing", "x"), (None, None, "pre-turn tree does not build")),
    (correctness.Result(None, None, "infrastructure failure before build: restore", "x"),
     (None, None, "infrastructure failure before build: restore")),
    (correctness.Result(None, None, "infrastructure failure before build: sdk", "x"),
     (None, None, "infrastructure failure before build: sdk")),
    (correctness.Result(None, None, "HB-GRD-002 grading step timeout after 60 s", "x"),
     (None, None, "HB-GRD-002 grading step timeout after 60 s")),
])
def test_a_compile_error_is_0_only_when_the_pre_turn_tree_builds(tmp_path, monkeypatch, control, expected):
    inp = control_cell(tmp_path)
    trees = []

    def fake_grade(ws, *args):
        trees.append(sorted(p.name for p in ws.iterdir()))
        return CELL_BROKE if len(trees) == 1 else control

    monkeypatch.setattr(correctness, "grade", fake_grade)
    monkeypatch.setattr(correctness, "build_and_suite_clean", lambda *a: Score(0, None))
    out = correctness.grade_cell(inp)
    assert tuple(encode(out[m]) for m in ("pass_at_1", "partial_credit")) == \
        ((expected[0], expected[2]), (expected[1], expected[2]))
    assert out["pass_at_1"].evidence == "grading/g/c1/correctness/oracle.log"  # the cell's own log
    assert trees == [[".git", "a.cs"], ["a.cs"]]  # the control ran on the pre-turn tree, not the cell's
    assert not (inp.out_dir / "pre-turn").exists()


def test_a_compile_error_with_no_builder_commit_is_na_not_found(tmp_path, monkeypatch):  # F11
    inp = control_cell(tmp_path, base_message="squashed by the agent")
    monkeypatch.setattr(correctness, "grade", lambda *a: CELL_BROKE)
    monkeypatch.setattr(correctness, "build_and_suite_clean", lambda *a: Score(0, None))
    out = correctness.grade_cell(inp)
    assert encode(out["pass_at_1"]) == (None, "pre-turn commit not found in the working copy")


# --- GR-CODE c2: regression_count and the behavioural_equivalence NA, with a fake public suite ----------------------

NS = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
PUBLIC = "tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj"  # D1's one public test project (Microsoft.NET.Test.Sdk)
C2 = ("regression_count", "behavioural_equivalence")


def trx(results: dict, marker: str = "") -> str:
    """A TRX in the measured shape (docs/notes/spike-gr-code-trx.md): one UnitTest per case, a theory's cases sharing
    className.name. `marker` fills every host-identifying attribute and every time; empty leaves them out."""
    host = lambda **kw: "".join(f' {k}="{v}"' for k, v in kw.items()) if marker else ""
    units, rows, n = [], [], 0
    for key, outcomes in results.items():
        cls, _, name = key.rpartition(".")
        for outcome in [outcomes] if isinstance(outcomes, str) else outcomes:
            n += 1
            units.append(f'<UnitTest name="{key}" id="t{n}"{host(storage=marker)}><TestMethod className="{cls}" '
                         f'name="{name}" adapterTypeName="executor://xunit/VsTestRunner3/netcore/"{host(codeBase=marker)} /></UnitTest>')
            rows.append(f'<UnitTestResult executionId="e{n}" testId="t{n}" testName="{key}" outcome="{outcome}"'
                        f'{host(computerName=marker, startTime=marker, endTime=marker, duration=marker)} />')
    return (f'<?xml version="1.0" encoding="utf-8"?><TestRun id="r" name="n"{host(runUser=marker)} xmlns="{NS}">'
            f'{f"<Times creation={marker!r} />" if marker else ""}<Results>{"".join(rows)}</Results>'
            f'<TestDefinitions>{"".join(units)}</TestDefinitions><ResultSummary outcome="Failed"><Counters total="{n}" '
            f'passed="0" /></ResultSummary></TestRun>')


def fake_public(monkeypatch, cell=None, pre=None, marker: str = "") -> list:
    """`dotnet test` answered per tree (the grading copy's folder name: `cell` or `pre-turn`): a dict writes a TRX
    and exits 0 or 1, a Completed is returned as is. Every other command (git) runs for real. Returns (tree, argv)."""
    real, seen = correctness.procs.run, []

    def run(argv, cwd, **kwargs):
        if argv[:2] != ["dotnet", "test"]:
            return real(argv, cwd=cwd, **kwargs)
        tree = Path(cwd).name
        seen.append((tree, argv))
        answer = {"cell": cell, "pre-turn": pre}[tree]
        if not isinstance(answer, dict):
            return answer
        path = Path(cwd) / "TestResults" / argv[argv.index("--logger") + 1].partition("LogFileName=")[2]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trx(answer, marker), encoding="utf-8")
        return done(int(any(o != "Passed" for v in answer.values() for o in ([v] if isinstance(v, str) else v))),
                    f"Results File: {marker or 'X'}/TestResults/x.trx")

    monkeypatch.setattr(correctness.procs, "run", run)
    return seen


def graded_elsewhere(monkeypatch) -> None:
    """The hidden-test step and the build are c1's, faked here so only c2's metrics run."""
    monkeypatch.setattr(correctness, "grade", lambda *a: correctness.Result(1, Decimal(1), None, "x"))
    monkeypatch.setattr(correctness, "build_and_suite_clean", lambda *a: Score(1, None))


def c2_of(out: dict) -> dict:
    return {m: (out[m].value, out[m].reason) if m in out else None for m in C2}


@pytest.mark.parametrize("task", ["A1", "C1", "E6"])
def test_a_task_with_no_public_tests_is_na_and_not_a_d_task(tmp_path, monkeypatch, task):  # N4, a recorded deviation
    graded_elsewhere(monkeypatch)
    seen = fake_public(monkeypatch)
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    shutil.copytree(ROOT / "tasks" / task / "workspace", folder / "ws")
    inp = cell_input(tmp_path / "run", folder, {"cell_id": "c1", "task": task, "pack": "off"},
                     tmp_path / "run" / "grading" / "g" / "c1" / "correctness")
    assert c2_of(correctness.grade_cell(inp)) == \
        {"regression_count": (None, "task has no public tests"), "behavioural_equivalence": (None, "not a D-task")}
    assert seen == []  # no public suite ran


def public_cell(tmp_path: Path, base_message: str = f"T9 base ({T9_VERSION[:12]})", project: bool = True) -> CellInput:
    """A D1 cell (D1's task.yaml, so D1's public project) whose working copy is a two-file stand-in: the base commit
    holds the public project's file and a.cs; the cell's uncommitted change edits a.cs, or deletes the project."""
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    ws = folder / "ws"
    (ws / PUBLIC).parent.mkdir(parents=True)
    (ws / PUBLIC).write_text("<Project />", encoding="utf-8")
    (ws / "a.cs").write_text("class A {}\n", encoding="utf-8")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", base_message)
    (ws / "a.cs").write_text("class A { }\n", encoding="utf-8")
    if not project:
        (ws / PUBLIC).unlink()
    cell = {"cell_id": "c1", "task": "D1", "task_version": D1_VERSION, "pack": "off"}
    inp = cell_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "correctness", timeout=60)
    return dataclasses.replace(inp, cell={**cell, "task": "T9", "task_version": T9_VERSION})


def test_d1_behavioural_equivalence_is_na_no_differential_oracle(tmp_path, monkeypatch):  # R-68 1: keep, re-source later
    graded_elsewhere(monkeypatch)
    fake_public(monkeypatch, cell={"N.A.a": "Passed"}, pre={"N.A.a": "Passed"})
    assert c2_of(correctness.grade_cell(public_cell(tmp_path))) == \
        {"regression_count": (0, None), "behavioural_equivalence": (None, "no differential oracle in this task version")}
