"""R21-3 (design 16.2, ruling R-21): a Copilot cell the engine ends at its budget still
records `session.shutdown`, and the ledger records its tokens.

One real copilot-sol cell (harness copilot, model gpt-6-sol, pinned, pack off). The live
turn is the Leader's: this file is marked credentials, so the default ring never runs it.

Budget. The engine ends the cell when `now - prompt_mono > cell["budget_seconds"]`
(`engine._check_budgets`). That number is copied from the BOM task's `budget_minutes * 60`
at plan time (`plan.expand`). The matrix has no budget field, and plan parameters have no
cell-budget key (the CLI only overrides `decision_timeout` and `spend_cap_tokens`). BOM
minutes are integers of at least 1, so 45 s cannot be written there. The confirmed plan is
what the engine reads, and `load_confirmed` accepts a plan whose `plan_hash` matches, so
this test reseals the one cell's `budget_seconds` (and the task record and envelope that
quote it) to 45 before `bench run`.

Task. Not X1. The recorded copilot-sol pack-off X1 cell finished in 20.0 s
(`docs/proof/wave1-e2e-last.json`, wall from process start to process end, and the budget
clock starts later, at `cell.prompt_sent`). A 45 s budget would not end it. C1's prompt
(a mergeable heap plus a six-section architecture) keeps the model working past that.
C1 grades with Python, so the run does not start dotnet.
"""

import json
import os
import shutil
import time
from pathlib import Path

import pytest

from harness_bench import archive, cli, config, plan, profiles, views
from harness_bench.report import cell_tokens
from harness_bench.telemetry import copilot

pytestmark = pytest.mark.native
ROOT = Path(__file__).resolve().parents[2]
# What `_check_budgets` compares. About 45 s: long enough for a session to be in flight,
# short of C1's 30-minute BOM budget.
BUDGET_SECONDS = 45
TASK_ID = "C1"
MATRIX = """\
schema: bench-matrix/1
run_id: r21-3
bom: { file: bench/bom.yaml, subset: [C1] }
repetitions: 1
packs: ["off"]
combos:
  - { id: copilot-sol, harness: copilot, model: gpt-6-sol }
"""


@pytest.fixture
def kept(clean_parent):
    """A clean-ancestry folder the test removes only after every assertion, so a failed run stays as evidence."""
    folder = clean_parent / f"e2e-r21-3-{int(time.time())}"
    folder.mkdir(parents=True)
    return folder


def _reseal_budget(run_dir: Path, seconds: int) -> dict:
    """Write `seconds` onto the confirmed plan's cell and task budgets and re-seal `plan_hash`."""
    path = run_dir / "plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for cell in data["cells"]:
        cell["budget_seconds"] = seconds
    for task in data["tasks"].values():
        task["budget_seconds"] = seconds
    cells = [plan.Cell(c["task"], c["task_version"], c["scenario"], c["combo"], c["harness"], c["model"],
                       c["pack"], c["rep"], seconds) for c in data["cells"]]
    data["envelope_seconds"] = plan.envelope_seconds(cells, data["parameters"]["parallelism"])
    data["plan_hash"] = plan.plan_hash(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return plan.load_confirmed(run_dir)


def _record_types(record: Path) -> list[str]:
    found = []
    for raw in record.read_bytes().splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("type"), str):
            found.append(row["type"])
    return found


@pytest.mark.credentials
def test_copilot_budget_kill_records_session_shutdown(kept, capsys):
    tools_dir = ROOT / ".tools" / "harness"  # installed by the e2e conftest
    runs, cells = kept / "runs", kept / "cells"
    rid = kept.name
    matrix_path = kept / "matrix.yaml"
    matrix_path.write_text(MATRIX, encoding="utf-8")
    common = ["--root", str(ROOT), "--runs", str(runs), "--cells-root", str(cells), "--tools-dir", str(tools_dir)]

    plan_args = [*common, "plan", "--matrix", str(matrix_path), "--run-id", rid, "--parallelism", "1", "--confirm"]
    if os.environ.get("HB_PACK_SOURCE"):
        plan_args.extend(("--pack-source", os.environ["HB_PACK_SOURCE"]))
    assert cli.main(plan_args) == 0, capsys.readouterr()
    sealed = _reseal_budget(runs / rid, BUDGET_SECONDS)
    assert [c["task"] for c in sealed["cells"]] == [TASK_ID]
    assert [(c["harness"], c["model"], c["pack"], c["combo"], c["budget_seconds"]) for c in sealed["cells"]] == [
        ("copilot", "gpt-6-sol", "off", "copilot-sol", BUDGET_SECONDS)]
    assert sealed["tasks"][TASK_ID]["budget_seconds"] == BUDGET_SECONDS

    assert cli.main([*common, "run", rid]) == 0, capsys.readouterr()
    run_dir = runs / rid
    # the catalog's own version: a .dev pass is never current (V-1), so a bare load reads "not graded"
    view = views.load(run_dir, str(config.load_yaml(ROOT / "bench" / "metrics.yaml")["version"]))
    events = views.rows(run_dir, "events")
    (cell,) = view.cells
    (outcome,) = [e for e in events if e["kind"] == "cell.outcome"]
    (prompt_sent,) = [e for e in events if e["kind"] == "cell.prompt_sent"]

    # The budget end: timed_out / HB-CELL-301, and the clock ran past the sealed budget.
    assert cell.outcome == "timed_out", (cell.outcome, cell.cause, cell.code)
    assert outcome["outcome"] == "timed_out"
    assert outcome["cause"] == "timed_out"
    assert outcome["code"] == "HB-CELL-301"
    assert cell.cause == "timed_out" and cell.code == "HB-CELL-301"
    assert outcome["mono_ns"] - prompt_sent["mono_ns"] > BUDGET_SECONDS * 1_000_000_000

    # The archived Copilot record contains session.shutdown (R-21: modelMetrics live on that event).
    sessions = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
    home = run_dir / "archive" / cell.cell_id / "attempt-1" / "home"
    (record,) = profiles.find_records(home, sealed["profiles"]["copilot"]["record_glob"], sessions[cell.cell_id])
    assert "session.shutdown" in _record_types(record), record
    extraction = copilot.read(record)
    assert not any(item.field == "session.shutdown" for item in extraction.missing), extraction.missing

    # Tokens are recorded. R-21 c2: a missing shutdown reads "tokens: not recorded", never a zero.
    calls = [r for r in views.rows(run_dir, "model_calls") if r["cell_id"] == cell.cell_id]
    assert calls, "model_calls: none"
    assert sum(r["uncached_input"] + r["cache_read"] + r["cache_write"] + r["output"] for r in calls) > 0, calls
    graded = next(e for e in events if e["kind"] == "grading.completed")
    assert cell.cell_id not in graded.get("unreadable_records", {}), graded.get("unreadable_records")
    assert cell.tokens, cell.tokens_reason
    assert cell.tokens_reason is None
    shown = cell_tokens(cell.tokens, cell.tokens_reason)
    assert "not recorded" not in shown, shown

    assert cli.main([*common, "teardown", rid]) == 0
    shutil.rmtree(kept, onexc=archive.make_writable)
    assert not kept.exists()
