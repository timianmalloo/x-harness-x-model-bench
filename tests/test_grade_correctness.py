"""Correctness grader: the C-2 move, build_and_suite_clean and DR-G4 decided by cause (design phase3-graders, GR-CODE c1).

- The gate-run test grades the archived cells of `HB_GATE_RUNS` in place, read-only: every output goes under
  `tmp_path`, and the archive's bytes are compared before and after (F9). It skips when the runs are not on this host.
- The D1 fixtures are the frozen `tasks/D1/workspace` in a temporary git repo that reproduces the archive's commits
  (G9), with a seeded overlay. They need the pinned dotnet SDK and the offline NuGet cache; without them they skip,
  and with `HB_REQUIRE_DOTNET=1` they fail instead (the design's slow-ring rule).
"""

import hashlib
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT

from harness_bench import config, plan, views
from harness_bench.grade import CellInput, correctness
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


def test_an_empty_nuget_cache_is_na_restore_never_0(tmp_path, d1_dotnet, monkeypatch):  # F13: a failure before the build
    (tmp_path / "empty-nuget").mkdir()
    monkeypatch.setenv("NUGET_PACKAGES", str(tmp_path / "empty-nuget"))
    got = grade_d1(tmp_path, *d1_cell(tmp_path, REFERENCE))
    assert {m: got.get(m) for m in BUILT_CORRECTNESS} == \
        dict.fromkeys(BUILT_CORRECTNESS, (None, "infrastructure failure before build: restore"))
