"""Drift grader: scope_creep, scope_creep_files and convention_drift (design phase3-graders, section Drift, GR-CODE c3).

- The D1 fixtures are the frozen `tasks/D1/workspace` in a temporary git repo that reproduces the archive's commits
  (G9; `d1_cell` from the correctness tests, the same builder c1's change-reader tests use). They need git only.
- Every grade asserts the archive's bytes did not move (F9).
"""

from decimal import Decimal
from pathlib import Path

from archived_runs import ROOT
from test_grade_correctness import d1_cell, tree_digest

from harness_bench import config
from harness_bench.grade import CellInput, drift
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
MEASURED = ("scope_creep", "scope_creep_files", "convention_drift")


def encode(score) -> tuple:
    """(value, reason); convention_drift is a Decimal written at scale 2 (design: per 100 changed lines, scale 2)."""
    v = score.value
    return (f"{v:.2f}" if isinstance(v, Decimal) else v), score.reason


def drift_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": timeout}}, cell=cell,
                     task=config.load_yaml(task_dir / "task.yaml"), task_dir=task_dir, archive=archive, out_dir=out_dir,
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(),
                     metrics=applicable(CATALOG, ["drift"])["drift"], allow_model_calls=False, extraction=None, prices=None)


def grade_d1(tmp_path: Path, folder: Path, cell: dict) -> dict[str, tuple]:
    """Every drift Score of the cell as (value, reason); the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = drift.grade_cell(drift_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "drift"))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return {m: encode(s) for m, s in out.items()}


# --- the design's seeds ----------------------------------------------------------------------------------------------

MCP = "src/AiDe.Mcp/ServerContext.cs"


def test_a_3_line_edit_outside_the_blast_radius_is_scope_creep_3_in_1_file(tmp_path):  # design: Seeded
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {MCP: lambda text: "// one\n// two\n// three\n" + text}))
    assert {m: got.get(m) for m in MEASURED} == \
        {"scope_creep": (3, None), "scope_creep_files": (1, None), "convention_drift": ("0.00", None)}


PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
REFERENCE = {PROJECTION: (ROOT / "tasks" / "D1" / "oracle" / "reference" / PROJECTION).read_text(encoding="utf-8")}


def test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep(tmp_path):  # design: Seeded, pack-on
    got = grade_d1(tmp_path, *d1_cell(tmp_path, REFERENCE, pack=True))  # .editorconfig and docs/pack/: outside the radius
    assert {m: got.get(m) for m in ("scope_creep", "scope_creep_files")} == {"scope_creep": (0, None), "scope_creep_files": (0, None)}
