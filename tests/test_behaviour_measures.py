"""tools/behaviour_measures.py: the analysis layer's drift / ceremony / over-thinking measures read a run's own facts,
skip a run whose grading pass has not completed (a half-written pass once made half a run look empty), and never
write into the run."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("behaviour_measures", ROOT / "tools" / "behaviour_measures.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _run(root: Path, name: str, completed: bool) -> Path:
    run = root / name
    cells = [{"cell_id": "a1", "combo": "cx", "harness": "codex", "model": "m", "arm": "off", "task": "S1", "rep": 1},
             {"cell_id": "b2", "combo": "cx", "harness": "codex", "model": "m", "arm": "on", "task": "S1", "rep": 1}]
    run.mkdir(parents=True)
    (run / "plan.json").write_text(json.dumps({"cells": cells, "profiles": {"codex": {"auxiliary_models": ["aux"]}}}),
                                   encoding="utf-8")
    kinds = ["grading.started", "grading.completed"] if completed else ["grading.started"]
    _jsonl(run / "events" / "grade-1.jsonl", [{"kind": k} for k in kinds])
    _jsonl(run / "events" / "engine-1.jsonl", [
        {"cell_id": "a1", "kind": "attempt.process_started", "recorded_at": "2026-10-13T10:00:00Z"},
        {"cell_id": "a1", "kind": "attempt.process_ended", "recorded_at": "2026-10-13T10:03:00Z"}])
    _jsonl(run / "model_calls" / "grade-1.jsonl", [
        {"cell_id": "a1", "model": "m", "output": 100, "reasoning": 40, "uncached_input": 5, "requests": 1},
        {"cell_id": "a1", "model": "m", "output": 50, "reasoning": 10, "requests": 1},
        {"cell_id": "a1", "model": "aux-title", "output": 999, "requests": 1}])
    _jsonl(run / "tool_calls" / "grade-1.jsonl", [
        {"cell_id": "a1", "name": "Read", "tool_class": "read", "native_ordinal": 1},
        {"cell_id": "a1", "name": "Edit", "tool_class": "edit", "native_ordinal": 2}])
    _jsonl(run / "scores" / "grade-1.jsonl", [{"cell_id": "a1", "metric_id": "pass_at_1", "value": "1"}])
    drift = run / "grading" / "grade-1" / "a1" / "drift" / "drift.log"
    drift.parent.mkdir(parents=True)
    drift.write_text("changed\tsrc/x.py\tinside\t+8 -1\t\n"
                     "added\t.agents/log/a.json\toutside\t+3 -0\t\tmachine:pack-log\n"
                     "added\tNOTES.md\toutside\t+20 -0\t\tdiscretionary\n"
                     "added\t.venv/Lib/x.py\toutside\t+500 -0\t\tdiscretionary\n", encoding="utf-8")
    return run


def test_a_completed_run_is_measured_from_its_own_facts(tmp_path):
    run = _run(tmp_path / "runs", "r1", completed=True)
    before = sorted(p.relative_to(run) for p in run.rglob("*"))
    assert bm.main(["--run", str(run), "--out", str(tmp_path / "out")]) == 0
    a1 = next(c for c in json.loads((tmp_path / "out" / "behaviour-cells.json").read_text(encoding="utf-8"))
              if c["cell_id"] == "a1")
    assert a1["tokens"]["output"] == 150 and a1["tokens"]["reasoning"] == 50  # the auxiliary model is left out
    assert a1["calls_before_first_edit"] == 1 and a1["wall_s"] == 180
    # a pass graded before .venv joined the machine list is re-labelled with the bench's current list, and says so
    assert a1["drift"]["lines"] == {"inside": 8, "machine:pack-log": 3, "discretionary": 20, "machine:cache": 500}
    assert a1["drift"]["relabelled_lines"] == 500
    assert sorted(p.relative_to(run) for p in run.rglob("*")) == before  # nothing written into the run


def test_a_run_whose_grading_pass_is_still_running_is_skipped(tmp_path):
    run = _run(tmp_path / "runs", "r2", completed=False)
    assert bm.main(["--run", str(run), "--out", str(tmp_path / "out")]) == 0
    assert json.loads((tmp_path / "out" / "behaviour-cells.json").read_text(encoding="utf-8")) == []
    assert "r2" in (tmp_path / "out" / "behaviour.md").read_text(encoding="utf-8")
