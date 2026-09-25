"""Architecture grader: architecture_conformance (design phase3-graders, section Architecture, GR-CODE c4).

- The C1 and D1 fixtures are the frozen `tasks/<id>/workspace` in a temporary git repo that reproduces the archive's
  commits (`d1_cell` from the correctness tests; `c1_cell` below builds C1 the same way). They need git only.
- A value is asserted as `str(Decimal)`, so the scale of 4 is part of the expectation (rules passed / rules, scale 4).
- Every grade asserts the archive's bytes did not move (F9).
"""

import shutil
from decimal import Decimal
from pathlib import Path

from archived_runs import ROOT
from test_grade_correctness import git, tree_digest

from harness_bench import config, plan
from harness_bench.grade import CellInput, architecture
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
METRIC = "architecture_conformance"
C1 = ROOT / "tasks" / "C1"
C1_VERSION = plan.task_version_hash(C1)
C1_REFERENCE = {rel: (C1 / "oracle" / "reference" / rel).read_text(encoding="utf-8")
                for rel in ("priority_queue.py", "docs/architecture.md")}


def encode(score) -> tuple:
    """(value, reason); a Decimal as its own string, so `1.0000` and `1` differ (scale 4)."""
    v = score.value
    return (str(v) if isinstance(v, Decimal) else v), score.reason


def c1_cell(tmp_path: Path, overlay: dict) -> tuple[Path, dict]:
    """(archive folder, plan cell): C1's base commit, then `overlay` (path -> text), uncommitted; pack off."""
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    ws = folder / "ws"
    shutil.copytree(C1 / "workspace", ws)
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", f"C1 base ({C1_VERSION[:12]})")
    for rel, text in overlay.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8", newline="")
    return folder, {"cell_id": "c1", "task": "C1", "task_version": C1_VERSION, "pack": "off"}


def arch_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": timeout}}, cell=cell,
                     task=config.load_yaml(task_dir / "task.yaml"), task_dir=task_dir, archive=archive, out_dir=out_dir,
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(),
                     metrics=applicable(CATALOG, ["architecture"])["architecture"], allow_model_calls=False,
                     extraction=None, prices=None)


def grade(tmp_path: Path, folder: Path, cell: dict) -> tuple:
    """architecture_conformance as (value, reason); the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = architecture.grade_cell(arch_input(tmp_path / "run", folder, cell,
                                             tmp_path / "run" / "grading" / "g" / "c1" / "architecture"))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return encode(out[METRIC])


# --- the design's exact fixtures ------------------------------------------------------------------------------------


def test_the_c1_reference_with_no_imports_is_1(tmp_path):  # design: Architecture, Fixtures
    assert grade(tmp_path, *c1_cell(tmp_path, C1_REFERENCE)) == ("1.0000", None)
