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
    # C6 is reasoning tokens over tool calls (50 / 2); a measure the record cannot give is None with its reason, never 0
    assert a1["m"]["reasoning_per_tool_call"] == 25 and a1["m"]["planning_calls"] == 0
    assert a1["m"]["tool_error_rate"] is None and "outcome missing" in a1["why"]["tool_error_rate"]
    assert a1["m"]["rereads"] is None and a1["why"]["rereads"] and a1["m"]["outside_before"] is None
    assert sorted(p.relative_to(run) for p in run.rglob("*")) == before  # nothing written into the run


def test_a_run_whose_grading_pass_is_still_running_is_skipped(tmp_path):
    run = _run(tmp_path / "runs", "r2", completed=False)
    assert bm.main(["--run", str(run), "--out", str(tmp_path / "out")]) == 0
    assert json.loads((tmp_path / "out" / "behaviour-cells.json").read_text(encoding="utf-8")) == []
    assert "r2" in (tmp_path / "out" / "behaviour.md").read_text(encoding="utf-8")


# --- instrumentation W1: spread, tool use, drift files, attention split, session compliance ---------------------------

from harness_bench.telemetry import ProcessTrace, ToolInput


def test_spread_is_the_inclusive_quartiles_and_range_of_the_recorded_values():
    assert bm.spread([4, 1, 2, 3, 100]) == {"n": 5, "median": 3, "p25": 2, "p75": 4, "min": 1, "max": 100}
    assert bm.spread([7]) == {"n": 1, "median": 7, "p25": 7, "p75": 7, "min": 7, "max": 7}
    assert bm.spread([]) is None


def test_process_measures_read_the_score_first_then_the_graders_own_rule_over_the_tool_rows():
    rows = [{"native_ordinal": i, "name": "exec", "tool_class": "shell", "ok": ok} for i, ok in enumerate([1, 0, 0, 0, 1])]
    rows.append({"native_ordinal": 9, "name": "ToolSearch", "tool_class": "meta", "ok": 0})  # meta rows are excluded
    got = bm.process_measures({}, {}, rows)
    assert got["tool_error_rate"] == (0.6, None) and got["stuck_loops"] == (1, None)
    # a graded score wins over recomputing
    assert bm.process_measures({"stuck_loops": "4"}, {}, rows)["stuck_loops"] == (4.0, None)
    # a missing per-call outcome is not recorded, with the grader's reason, never 0
    unknown = bm.process_measures({}, {}, [{"native_ordinal": 1, "name": "x", "tool_class": "shell", "ok": None}])
    assert unknown["tool_error_rate"][0] is None and "outcome missing" in unknown["tool_error_rate"][1]


def test_trace_measures_count_rereads_bytes_and_first_edit_and_leave_unknown_text_not_recorded():
    calls = (ToolInput(1, "view", ("a.py",), None, False, 10), ToolInput(2, "view", ("a.py",), None, False, 5),
             ToolInput(3, "edit", ("a.py",), None, True, 1), ToolInput(4, "view", ("a.py",), None, False, 2))
    got = bm.trace_measures(ProcessTrace(None, calls))
    assert got["rereads"] == 1 and got["tool_result_bytes"] == 18 and got["first_edit_ordinal"] == 3
    assert got["assistant_chars"] is None and "does not count" in got["why"]["assistant_chars"]
    with_text = bm.trace_measures(ProcessTrace(None, calls, assistant_chars=120, assistant_messages=4))
    assert with_text["assistant_chars"] == 120 and with_text["assistant_messages"] == 4
    nobytes = bm.trace_measures(ProcessTrace(None, (ToolInput(1, "view", ("a",), None, False),)))
    assert nobytes["tool_result_bytes"] is None and "not in the record" in nobytes["why"]["tool_result_bytes"]


def test_attention_split_counts_outside_reads_before_and_after_the_first_edit_and_skips_pathless_rows():
    log = ("events.jsonl\t5\tskill\t-\tno-path\r\n"
           "events.jsonl\t12\tview\ta/outside.md\toutside\r\n"
           "events.jsonl\t12\tview\tsrc/in.py\tinside\r\n"   # same turn as the edit: cannot have seen it
           "events.jsonl\t30\tview\tb/outside.md\toutside\r\n")
    assert bm.attention_split(log, 12) == {"outside_before": 1, "outside_after": 1, "inside_before": 1, "inside_after": 0}
    assert bm.attention_split(log, None)["outside_after"] == 0  # never edited: every read is before
    assert bm.attention_split("", 3) == {"outside_before": 0, "outside_after": 0, "inside_before": 0, "inside_after": 0}
    assert bm.attention_split("a.jsonl\t1\tview\tx\toutside\nb.jsonl\t2\tview\ty\toutside\n", 5) is None  # two records


def test_top_drift_files_rank_discretionary_files_by_lines_and_name_how_many_cells_wrote_them(tmp_path):
    def cell(cid, files):
        return {"combo": "cx", "arm": "on", "cell_id": cid, "drift": {"discretionary_files": files}}
    got = bm.top_drift_files([cell("a", {"NOTES.md": 20, "x.txt": 3}), cell("b", {"NOTES.md": 10}), cell("c", {})], top=1)
    assert got == {("cx", "on"): [("NOTES.md", 30, 2)]}


def test_drift_lines_keep_the_added_lines_per_discretionary_file(tmp_path):
    log = tmp_path / "drift.log"
    log.write_text("added\tNOTES.md\toutside\t+20 -0\t\tdiscretionary\r\nadded\t.venv/x.py\toutside\t+9 -0\t\tdiscretionary\r\n"
                   "ignored\t.pytest_cache/a\r\n", encoding="utf-8")
    assert bm.drift_lines(log)["discretionary_files"] == {"NOTES.md": 20}  # the machine-written .venv path is relabelled


def _call(minute, command, ok=True, write=False):
    return (f"2026-10-13T10:{minute:02d}:00Z", ToolInput(1, "shell", (), command, write), ok)


def test_session_compliance_reads_cadence_steps_and_a_handoff_without_its_file():
    prompt = "Check it with `BENCH status <RUN_ID>` every 10 minutes; report each check."
    events = [_call(0, "uv run bench --cells-root C:/c plan --matrix m.yaml --confirm"),
              _call(1, "uv run bench --cells-root C:/c run lean-1"),
              _call(2, "& C:/sp/bench.ps1 status lean-1"),
              _call(4, r"& C:\sp\bench.ps1 status lean-1"),
              _call(14, "uv run bench status lean-1"),
              _call(20, r"Get-Content C:\Projects\x-harness-x-model-bench\README.md status")]  # a path, not the bench CLI
    got = bm.session_compliance(events, [prompt], ["done\nHANDOFF: lean-1@C:/wt"])
    assert got["status_checks"] == 3 and got["median_interval_min"] == 6.0 and got["asked_interval_min"] == 10
    assert got["intervals_under_half_asked"] == 1 and got["intervals"] == 2
    assert got["steps"]["plan_confirmed"] and got["steps"]["run_started"] and not got["steps"]["verified"]
    assert got["steps_done"] == 3 and got["steps_required"] == len(bm.STEPS)
    assert got["handoff_printed"] is True and got["handoff_json_written"] is False
    assert got["handoff_without_json"] is True
    # Codex keeps its shell commands inside JavaScript; a status loop in one call is a watcher, not a status check gap
    js = events + [_call(25, "const r=await tools.exec_command({cmd:`uv run bench --cells-root ${s.cells_root} status ${s.run_id} --json`});"
                              "await new Promise(r=>setTimeout(r,55000));")]
    assert bm.session_compliance(js, [prompt], [])["watcher_calls"] == 1
    # writing handoff.json (a write-class call, or a shell write naming it) clears the flag; a quoted placeholder is no hand-off
    done = events + [("2026-10-13T10:30:00Z", ToolInput(2, "Write", (r"C:\wt\runs\x\handoff.json",), None, True), True)]
    assert bm.session_compliance(done, [prompt], ["HANDOFF: lean-1@C:/wt"])["handoff_without_json"] is False
    assert bm.session_compliance(events, [prompt], ["print HANDOFF: <RUN_ID>@<WT> last"])["handoff_printed"] is False
    assert bm.session_compliance(events, [], None)["handoff_printed"] is None  # no text reader: not recorded


def test_session_compliance_lets_the_files_on_disk_decide_over_the_calls(tmp_path):
    run = tmp_path / "runs" / "lean-1"
    run.mkdir(parents=True)
    (tmp_path / "runs" / "lean-1.matrix.yaml").write_text("x", encoding="utf-8")
    (run / "plan.json").write_text("{}", encoding="utf-8")
    (run / "handoff.json").write_text('{"verify": "failed: exit 5"}', encoding="utf-8")
    # the calls claim a summary was written and the run verified; the disk has no run-summary and a failed verify
    events = [("2026-10-13T10:00:00Z", ToolInput(1, "shell", (), "uv run bench verify lean-1", False), True),
              ("2026-10-13T10:01:00Z", ToolInput(2, "shell", (), "python s.py > runs/lean-1/run-summary.md", False), True)]
    got = bm.session_compliance(events, [], ["HANDOFF: lean-1@x"], run_dir=run)
    assert got["steps_call"]["run_summary_written"] and got["steps_disk"]["run_summary_written"] is False
    assert got["steps"]["run_summary_written"] is False and got["steps"]["verified"] is False  # disk wins
    assert got["steps"]["handoff_json_written"] and got["steps"]["matrix_written"] and got["steps"]["plan_confirmed"]
    assert got["steps_disk"]["status_checked"] is None and got["steps"]["status_checked"] is False  # no disk proof: calls
    assert got["handoff_without_json"] is False
    # a call-only read is unchanged and says so
    assert bm.session_compliance(events, [], None)["steps_disk"] is None


def test_run_folder_comes_from_the_explicit_spec_else_from_the_handoff_line(tmp_path):
    (tmp_path / "wt" / "runs" / "lean-1").mkdir(parents=True)
    assert bm.run_folder(["HANDOFF: lean-1@" + str(tmp_path / "wt")], None) == (tmp_path / "wt" / "runs" / "lean-1", "HANDOFF line")
    assert bm.run_folder([], str(tmp_path)) == (tmp_path, "--session spec")
    assert bm.run_folder(["HANDOFF: lean-9@" + str(tmp_path / "gone")], None) == (None, "the HANDOFF line names a folder that does not exist")
    assert bm.run_folder([], None)[0] is None
