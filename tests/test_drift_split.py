"""Catalog 0.8's drift split and attention drift (ADR-0026 s5; DRIFT-MACHINE-A's and RADIUS-TEST-A's controls).

- The fixture is a lean-shaped task (graders `[correctness, property]`, a one-file radius) in a temporary git repo
  whose root commit carries the builder's message, so `_changes.pre_turn_commit` finds it (a pack-off cell).
- Drift is the changed lines outside the radius, split three ways: machine-written (tool caches and the pack's hook
  and audit files), task-implied (a test path) and discretionary (`scope_creep`, redefined).
"""

import json
from decimal import Decimal
from pathlib import Path

import yaml
from archived_runs import ROOT, make_root, make_run, pass_rows
from test_grade_correctness import git

from harness_bench import config
from harness_bench.grade import CellInput, _changes, drift, runner
from harness_bench.telemetry import claude_code, normalize

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
SPLIT = ("drift_machine_lines", "drift_task_implied_lines", "scope_creep", "attention_drift")
VERSION = "0" * 64
CID = "c1"
SESSION = "sess-1"
RADIUS = ["src/limiter.py"]
PROMPT = "Add a limiter in `src/limiter.py`. Build it on `vendor/q` and keep `README.md` true. Add tests in `tests/test_limiter.py`.\n"
BASE = {"src/limiter.py": "from . import helper\nimport json\n\n\ndef limit():\n    return helper.x\n",
        "src/helper.py": "x = 1\n", "src/other.py": "y = 2\n", "README.md": "# demo\n\nold line\n",
        "docs/guide.md": "guide\n", "vendor/q/gate.py": "class Gate:\n    pass\n"}


def lean_cell(tmp_path: Path, overlay: dict[str, str]) -> tuple[Path, dict, dict]:
    """(archive folder, plan cell, task): the base as the root commit `L1 base (<ver12>)`, then `overlay` uncommitted."""
    folder = tmp_path / "run" / "archive" / CID / "attempt-1"
    ws = folder / "ws"
    for rel, text in BASE.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8", newline="")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "config", "gc.auto", "0")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", f"L1 base ({VERSION[:12]})")
    for rel, text in overlay.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8", newline="")
    task_dir = tmp_path / "tasks" / "L1"
    task_dir.mkdir(parents=True)
    (task_dir / "prompt.md").write_text(PROMPT, encoding="utf-8")
    task = {"id": "L1", "graders": ["correctness", "property"], "blast_radius": RADIUS}
    return folder, {"cell_id": CID, "task": "L1", "task_version": VERSION, "pack": "off", "harness": "claude-code"}, task


def lean_input(tmp_path: Path, folder: Path, cell: dict, task: dict, metrics: dict, *, events=(), tool_calls=()) -> CellInput:
    run_dir = tmp_path / "run"
    out_dir = run_dir / "grading" / "g" / CID / "drift"
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = {"parameters": {"grading_step_timeout": 900}, "profiles": {"claude-code": {
        "record_glob": "projects/**/{session_id}.jsonl", "subagent_glob": "projects/**/{session_id}/subagents/agent-*.jsonl"}}}
    return CellInput(run_dir=run_dir, root=ROOT, plan=plan, cell=cell, task=task, task_dir=tmp_path / "tasks" / "L1",
                     archive=folder, out_dir=out_dir, events=events, record_reason=None, model_calls=(), tool_calls=tool_calls,
                     turn_usage=(), metrics=metrics, allow_model_calls=False, extraction=None, prices=None)


def by_id(*ids: str) -> dict:
    return {m["id"]: m for area in CATALOG["areas"].values() for m in area["metrics"] if m["id"] in ids}


# --- 1. the split: a cache, a hook log, a test file and a README edit (DRIFT-MACHINE-A's control) ---------------------

SPLIT_OVERLAY = {".pytest_cache/x": "a\nb\nc\n",  # 3 machine lines (a tool cache)
                 "docs/audit/.run-starts.json": "{}\n",  # 1 machine line (the session-start hook's audit-log.py start)
                 "tests/test_limiter.py": "def test_x():\n    assert True\n",  # 2 task-implied lines (outside the radius)
                 "README.md": "# demo\n\nnew line\n",  # 1 line out, 1 in: 2 discretionary lines
                 "src/limiter.py": BASE["src/limiter.py"] + "# inside\n"}  # inside the radius: no drift


def test_a_cache_a_hook_log_a_test_file_and_a_readme_edit_split_into_machine_task_implied_and_discretionary(tmp_path):
    folder, cell, task = lean_cell(tmp_path, SPLIT_OVERLAY)
    inp = lean_input(tmp_path, folder, cell, task, by_id("scope_creep", "scope_creep_files", "drift_machine_lines",
                                                          "drift_task_implied_lines"))
    got = drift.grade_cell(inp)
    log = (inp.out_dir / "drift.log").read_text(encoding="utf-8").splitlines()
    rows = {f[1]: f[5] if f[2] == "outside" else f[2] for f in (line.split("\t") for line in log)}
    assert sorted(p for p, c in rows.items() if c.startswith("machine")) == [".pytest_cache/x", "docs/audit/.run-starts.json"]
    assert [p for p, c in rows.items() if c == "task-implied"] == ["tests/test_limiter.py"]
    assert [p for p, c in rows.items() if c == "discretionary"] == ["README.md"]
    assert rows["src/limiter.py"] == "inside"
    assert {m: (s.value, s.reason) for m, s in got.items()} == {
        "drift_machine_lines": (4, None), "drift_task_implied_lines": (2, None),
        "scope_creep": (2, None), "scope_creep_files": (1, None)}


def test_the_machine_written_list_names_the_caches_and_the_exact_audit_files_never_a_docs_audit_glob():
    assert _changes.TOOL_CACHES >= config.GENERATED_DIR_NAMES | {".mypy_cache", ".ruff_cache"}
    assert not _changes.TOOL_CACHES & _changes.BUILD_OUTPUT - config.GENERATED_DIR_NAMES  # BUILD_OUTPUT does not move
    assert _changes.BUILD_OUTPUT == {".git", "bin", "obj", "TestResults", "__pycache__"}
    script = (ROOT / "docs" / "ai-forward-pack" / "scripts" / "audit-log.py").read_text(encoding="utf-8")
    for name in _changes.AUDIT_FILES:  # read from the pack's own writer, so the list cannot name a file it never writes
        assert f'"{name}"' in script, name
    assert {_changes.machine_written(p) for p in ("a/.mypy_cache/x", ".ruff_cache/y", "src/.pytest_cache/v/z")} == {"cache"}
    # 2026-10-13 lean runs: an agent's own virtual environment in the task tree (uv/pip create it) scored ~837k
    # discretionary lines of scope creep per RS2 cell; it is machine-written like any tool cache.
    assert _changes.machine_written(".venv/Lib/site-packages/pkg/__init__.py") == "cache"
    assert {_changes.machine_written(p) for p in ("docs/audit/audit-log.jsonl", ".agents/log/audit/.run-starts.json",
                                                  ".agents/log/lean-rerun-leader.jsonl")} == {"pack-log"}
    for authored in ("docs/audit/notes.md", "docs/audit/sub/audit-log.jsonl", ".agents/log/sub/x.jsonl", "README.md",
                     ".pytest_cache"):  # a file named like a cache dir is not under one
        assert _changes.machine_written(authored) is None, authored


# --- 2. a lean task (graders [correctness, property]) yields all four drift scores: the point of `all_tasks` ---------

def test_the_four_drift_metrics_apply_to_every_task_with_a_radius_and_a_lean_task_yields_all_four(tmp_path):
    flagged = {m["id"] for area in CATALOG["areas"].values() for m in area["metrics"] if m.get("all_tasks") is True}
    assert flagged == set(SPLIT)
    lean = runner.applicable(CATALOG, ["correctness", "property"], "no-guessing", has_radius=True)
    assert set(lean["drift"]) == set(SPLIT)
    assert "drift" not in runner.applicable(CATALOG, ["correctness", "property"], "no-guessing")  # no radius: none
    folder, cell, task = lean_cell(tmp_path, SPLIT_OVERLAY)
    got = drift.grade_cell(lean_input(tmp_path, folder, cell, task, lean["drift"]))
    assert set(got) == set(SPLIT)
    assert {m: s.value for m, s in got.items() if m != "attention_drift"} == {
        "drift_machine_lines": 4, "drift_task_implied_lines": 2, "scope_creep": 2}
    assert got["attention_drift"].reason == drift.NO_SESSION  # no session in this cell's events: NA, never 0


def test_a_pass_grades_an_all_tasks_metric_for_a_task_whose_graders_omit_its_grader(tmp_path):
    """The runner reads the task's radius: X1 names only correctness, yet `all_tasks` puts scope_creep in the pass."""
    root = make_root(tmp_path)
    path = root / "bench" / "metrics.yaml"
    text = path.read_text(encoding="utf-8")
    old = "{ id: scope_creep,            source: [D],"
    assert text.count(old) == 1
    path.write_text(text.replace(old, "{ id: scope_creep, all_tasks: true, source: [D],"), encoding="utf-8")
    spec = root / "tasks" / "X1" / "task.yaml"
    x1 = yaml.safe_load(spec.read_text(encoding="utf-8"))
    x1["graders"] = ["correctness"]
    spec.write_text(yaml.safe_dump(x1, sort_keys=False), encoding="utf-8")
    run_dir = make_run(root, tmp_path, {"a": "def slugify(s):\n    return s\n"})
    metrics = {r["metric_id"] for r in pass_rows(run_dir, "scores", runner.run_pass(run_dir, root).grading_id)}
    assert "scope_creep" in metrics and "scope_creep_files" not in metrics


# --- 3. attention drift equals a hand count ----------------------------------------------------------------------

def _use(n: int, name: str, inp: dict) -> str:
    return json.dumps({"type": "assistant", "message": {"model": "claude-test", "content": [
        {"type": "tool_use", "id": f"t{n}", "name": name, "input": inp}]}})


def _result(n: int) -> str:
    return json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{n}"}]}})


def test_attention_drift_on_a_fixture_tool_sequence_equals_a_hand_count(tmp_path):
    folder, cell, task = lean_cell(tmp_path, {})
    live_ws = f"C:/bench-cells/r1/{CID}/ws"  # the live cell's working copy: the record's absolute paths name it
    calls = [("Read", {"file_path": f"{live_ws}/src/limiter.py"}),  # inside: the radius
             ("Read", {"file_path": "src/helper.py"}),  # inside: limiter.py imports it (`from . import helper`)
             ("Read", {"file_path": "src/other.py"}),  # OUTSIDE
             ("Grep", {"pattern": "Gate", "path": "vendor/q"}),  # inside: the prompt names `vendor/q`
             ("Read", {"file_path": f"{live_ws}\\vendor\\q\\gate.py"}),  # inside: under a named path
             ("Glob", {"pattern": "**/*.py"}),  # no path: excluded, counted
             ("Read", {"file_path": "docs/guide.md"}),  # OUTSIDE
             ("Read", {"file_path": "tests/test_limiter.py"}),  # inside: a test path
             ("Bash", {"command": "cat src/other.py"}),  # a shell call: not a read or search call
             ("Edit", {"file_path": "src/limiter.py"}),  # a write: not a read or search call
             ("Grep", {"pattern": "x", "path": "src"}),  # inside: the radius file's own directory
             ("Read", {"file_path": "README.md"}),  # inside: the prompt names it
             ("Read", {"file_path": "C:/Users/someone/.claude/settings.json"})]  # OUTSIDE: not in the working copy
    record = folder / "home" / "projects" / "p" / f"{SESSION}.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text("".join(f"{_use(n, name, i)}\n{_result(n)}\n" for n, (name, i) in enumerate(calls)), encoding="utf-8")
    rows = normalize.tool_call_rows("r1", CID, SESSION, claude_code.read(record), "x")
    events = ({"kind": "attempt.session_opened", "cell_id": CID, "session_id": SESSION},)
    inp = lean_input(tmp_path, folder, cell, task, by_id("attention_drift"), events=events, tool_calls=tuple(rows))
    got = drift.grade_cell(inp)["attention_drift"]
    assert (got.value, got.reason) == (Decimal(3) / Decimal(10), None)  # 3 outside of 10 read and search targets
    log = (inp.out_dir / "attention.log").read_text(encoding="utf-8").splitlines()
    assert [line.split("\t")[-1] for line in log].count("no-path") == 1  # the Glob: excluded and counted
    assert sorted(line.split("\t")[3] for line in log if line.endswith("\toutside")) == [
        ".../.claude/settings.json", "docs/guide.md", "src/other.py"]  # an outside absolute path: its last two segments
