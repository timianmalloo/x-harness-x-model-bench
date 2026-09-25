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
