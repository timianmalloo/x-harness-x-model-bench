"""W1-K K2: plan-level resume, every ADR-0021 section 4 window by node id (docs/design/eval-resume.md section 4).

Technique T1 throughout: a real engine run against tests/fake_acp_agent.py is the golden ledger; a window is the
golden ledger cut after row i (rows are fsynced in order, so a prefix is exactly what a crash leaves) plus the
folder state the real functions leave at that point. `resume.classify`, `resume.stop_recorded` and the real
`resume.has_work` do not exist yet (K1b), so each test reaches an absent symbol only through an assertion
(`_need`), never an ImportError or AttributeError (RED-C). The classifier's action shape is the one assumption
these tests make: an object per plan cell with `cell_id`, `rule` ("C0".."C7"), `outcome` ("failed", "stopped" or
None) and `code` (HB-CELL-117/118/119 or None); K1b reconciles it with `classify` (recorded in the K2 handoff).
Every test that needs the resume engine (K1c) fails today on the skeleton's HB-USR-002 or on its own assertion.
"""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_engine import FakeLauncher, _build_workspace, _engine_run, _events, _plan
from test_multiturn import CellClock
from test_tools import _fake_tree

from harness_bench import (
    archive,
    atomic,
    cli,
    engine,
    host,
    identity,
    ledger,
    oslock,
    plan,
    resume,
    status,
    views,
)
from harness_bench.errors import BenchError

FACTS = ("events", "turn_usage", "archive_files")

# The golden ledgers, counted at the K2 commit on base c8c6390d: one cell is run.started + 13 cell rows + run.completed;
# two cells are run.started + 2 x 13 + run.completed.
N1 = 15
N2 = 28
# `rg run.completed src --count-matches` on base c8c6390d: 12 matching lines (views 6, status 1, engine 2, lifecycle 1,
# report/html 2). Query scope: the recursive `src` tree, matching lines.
BASE_COMPLETED_HITS = 12

CELL_ROWS = ["cell.launch_intent", "cell.workspace_built", "attempt.process_started", "attempt.session_opened",
             "cell.prompt_sent", "cell.turn_ended", "cell.turn_snapshot_archived", "cell.prompt_sent",
             "cell.turn_ended", "attempt.process_ended", "cell.outcome", "cell.archived", "cell.workspace_deleted"]
# cell rows kept per classifier state: C2 crashed turn 1, C4 turn ended with the snapshot event absent, C3 snapshot
# recorded, C5 last turn ended, C6 launched not prompted, C7 nothing, C0 everything.
STATE_ROWS = {"C0": 13, "C2": 5, "C3": 7, "C4": 6, "C5": 9, "C6": 4, "C7": 0}

# Independent oracles, written from ADR-0021 section 4's wording (not from classify's predicates), keyed by the kind of
# the cell's last row: (rule, outcome, code). A turn_ended row is keyed by what it says is owed next.
NOT_STOPPED = {
    "none": ("C7", None, None), "cell.launch_intent": ("C6", None, None), "cell.workspace_built": ("C6", None, None),
    "attempt.process_started": ("C6", None, None), "attempt.session_opened": ("C6", None, None),
    "cell.prompt_sent": ("C2", "failed", "HB-CELL-118"),
    "cell.turn_ended/snapshot": ("C4", "failed", "HB-CELL-119"),
    "cell.turn_snapshot_archived": ("C3", "failed", "HB-CELL-119"),
    "cell.turn_ended/final": ("C5", "failed", "HB-CELL-118"), "cell.turn_ended/stop": ("C5", "failed", "HB-CELL-118"),
    "attempt.process_ended": ("C5", "failed", "HB-CELL-118"),
    "cell.outcome": ("C1", None, None), "cell.archived": ("C0", None, None), "cell.workspace_deleted": ("C0", None, None),
}
STOPPED = {
    **NOT_STOPPED,
    "none": ("C7", None, None),
    "cell.launch_intent": ("C6", "stopped", None), "cell.workspace_built": ("C6", "stopped", None),
    "attempt.process_started": ("C6", "stopped", None), "attempt.session_opened": ("C6", "stopped", None),
    "cell.prompt_sent": ("C2", "stopped", None), "cell.turn_ended/snapshot": ("C4", "stopped", None),
    "cell.turn_snapshot_archived": ("C3", "stopped", None), "cell.turn_ended/final": ("C5", "stopped", None),
    "cell.turn_ended/stop": ("C5", "stopped", None), "attempt.process_ended": ("C5", "stopped", None),
}
PREFIXES = ["W1_no_launch_intent", "p02_launch_intent", "p03_workspace_built", "p04_process_started",
            "W2_session_opened", "W3_turn1_crashed", "W4_turn_ended_event_absent", "W6_between_turns_snapshot_recorded",
            "W3b_turn2_crashed", "W8_final_turn_ended", "p11_process_ended", "W9_outcome_unarchived", "W11_archived",
            "p14_workspace_deleted", "p15_run_completed"]


def _need(module, name):
    """An absent future symbol is a failed assertion that names the turn, never an AttributeError."""
    found = getattr(module, name, None)
    assert found is not None, f"{module.__name__}.{name} is not implemented yet (W1-K K4/K5)"
    return found


def _strip(row):
    return {k: v for k, v in row.items() if k not in ledger.CHAIN_FIELDS}


def _rows(run_dir):
    return [_strip(r) for r in _events(run_dir)]


# ---------------------------------------------------------------- the golden ledger helper

def _golden(base, n_cells, parallelism, **params):
    """One real engine run (two turns per cell) against tests/fake_acp_agent.py: the golden ledger and its disk."""
    p = _plan(n_cells, parallelism=parallelism)
    p["profiles"] = {"fake": {"usage_source": FakeLauncher.usage_source, "vendor": "fake", "auxiliary_models": []}}
    p["tasks"]["X1"]["turns"] = [{"n": 2, "prompt": "Repair it.\n", "sha256": hashlib.sha256(b"Repair it.\n").hexdigest()}]
    p["parameters"].update(params)
    behaviours = {c["label"]: {"model": "fake-model", "prompts_log": str(base / f"golden-{c['cell_id']}.jsonl"),
                               "per_turn": [{"files": {"a.txt": "1"}}, {"files": {"a.txt": "2"}}]} for c in p["cells"]}
    run_dir = base / "golden" / "runs" / p["run_id"]
    config = engine.EngineConfig(run_dir, base / "golden" / "cells", {"fake": FakeLauncher(behaviours)}, _build_workspace,
                                 None, loop_interval=0.01, clock=CellClock())
    p["plan_hash"] = plan.plan_hash(p)
    plan.confirm(run_dir, p)
    spend = []
    with pytest.MonkeyPatch.context() as mp:
        count = engine.Engine._count_spend
        mp.setattr(engine.Engine, "_count_spend", lambda self, record: (spend.append(record["tokens"]), count(self, record))[1])
        _engine_run(p, config, limit=120)
    return SimpleNamespace(plan=p, run_dir=run_dir, rows=_rows(run_dir), spend=spend,
                           stems={f: next((run_dir / f).glob("*.jsonl")).stem for f in FACTS},
                           cells=[c["cell_id"] for c in p["cells"]])


@pytest.fixture(scope="module")
def golden1(tmp_path_factory):
    return _golden(tmp_path_factory.mktemp("g1"), 1, 1)


@pytest.fixture(scope="module")
def golden2(tmp_path_factory):
    return _golden(tmp_path_factory.mktemp("g2"), 2, 2)


@pytest.fixture(scope="module")
def golden5(tmp_path_factory):
    return _golden(tmp_path_factory.mktemp("g5"), 5, 1)


def _of(rows, cid):
    return [r for r in rows if r.get("cell_id") == cid]


def _golden_segment(g, fact):
    return [r for r in ledger.read_segment(g.run_dir / fact / f"{g.stems[fact]}.jsonl") if r["kind"] != ledger.SEAL]


def _materialize(g, dest, rows, *, snap_rows="auto", final_rows="auto", tmp_dirs=(), no_workspace=(), no_attempt=(),
                 snapshots=(), attempts=(), extra=(), stray=()):
    """A crashed run on disk: the plan, the ledger `rows` (re-chained, unsealed), and the folders its rows imply."""
    run_dir, cells_root = dest / "runs" / g.plan["run_id"], dest / "cells"
    run_dir.mkdir(parents=True)
    shutil.copy2(g.run_dir / "plan.json", run_dir / "plan.json")
    (run_dir / ".lock").touch()
    snapped = {r["cell_id"] for r in rows if r["kind"] == "cell.turn_snapshot_archived"} | set(snapshots)
    archived = ({r["cell_id"] for r in rows if r["kind"] == "cell.archived"} | set(attempts)) - set(no_attempt)
    ended = {r["cell_id"] for r in rows if r["kind"] == "cell.outcome"}

    def pick(items, mode):
        return {"none": [], "partial": items[:len(items) // 2], "all": items}[mode]

    files = []
    for cid in g.cells:
        mine = [r for r in _golden_segment(g, "archive_files") if r.get("cell_id") == cid]
        snap = [r for r in mine if r.get("snapshot")]
        final = [r for r in mine if not r.get("snapshot")]
        files += pick(snap, snap_rows if snap_rows != "auto" else ("all" if cid in snapped else "none"))
        files += pick(final, final_rows if final_rows != "auto" else ("all" if cid in archived else "none"))
        if cid in snapped:
            shutil.copytree(g.run_dir / "archive" / cid / "turn-1", run_dir / "archive" / cid / "turn-1")
        if cid in archived:
            shutil.copytree(g.run_dir / "archive" / cid / "attempt-1", run_dir / "archive" / cid / "attempt-1")
    for cid, name in tmp_dirs:
        (run_dir / "archive" / cid / name / "ws").mkdir(parents=True)
        (run_dir / "archive" / cid / name / "ws" / "half.txt").write_text("half", encoding="utf-8")
    usage = [r for r in _golden_segment(g, "turn_usage") if r.get("cell_id") in ended]
    for fact, content in (("events", rows), ("turn_usage", usage), ("archive_files", files)):
        with ledger.SegmentWriter.create(run_dir / fact, g.stems[fact]) as w:
            for r in content:
                w.append(_strip(r))
    for fact, suffix, content in extra:
        with ledger.SegmentWriter.create(run_dir / fact, f"{g.stems[fact]}{suffix}") as w:
            for r in content:
                w.append(_strip(ledger.stamp(r)))
    for name in stray:
        (run_dir / "events" / f"{g.stems['events']}{name}.jsonl").touch()
    for cid in g.cells:
        mine = _of(rows, cid)
        if cid in no_workspace or not any(r["kind"] == "cell.workspace_built" for r in mine) \
                or any(r["kind"] == "cell.workspace_deleted" for r in mine):
            continue
        cell = next(c for c in g.plan["cells"] if c["cell_id"] == cid)
        cell_dir = cells_root / g.plan["run_id"] / cid
        _build_workspace(cell, cell_dir)
        turn2 = any(r["kind"] == "cell.turn_ended" and r.get("turn") == 2 for r in mine)
        (cell_dir / "ws" / "a.txt").write_text("2" if turn2 else "1", encoding="utf-8")
    log = dest / "resumed-prompts.jsonl"
    behaviours = {c["label"]: {"model": "fake-model", "prompts_log": str(log),
                               "per_turn": [{"files": {"a.txt": "1"}}, {"files": {"a.txt": "2"}}]} for c in g.plan["cells"]}
    cfg = engine.EngineConfig(run_dir, cells_root, {"fake": FakeLauncher(behaviours)}, _build_workspace,
                              lambda d: {"passes": 1}, loop_interval=0.01, clock=CellClock(), verify=views.verify)
    return SimpleNamespace(run_dir=run_dir, plan=copy.deepcopy(g.plan), cfg=cfg, root=dest / "root", log=log, g=g, rows=rows)


def _prefix(g, dest, i, **kw):
    return _materialize(g, dest, g.rows[:i], **kw)


def _resume(env):
    return _need(resume, "resume_run")(env.run_dir, env.root, env.plan, env.cfg)


def _post(env):
    """The ledger rows after the last run.resumed (the resume's own segment)."""
    rows = _rows(env.run_dir)
    last = max((i for i, r in enumerate(rows) if r["kind"] == "run.resumed"), default=-1)
    assert last >= 0, "no run.resumed row: the resume did not open its segment"
    return rows[last:]


def _outcome_map(env):
    return {r["cell_id"]: (r["outcome"], r.get("code")) for r in _rows(env.run_dir) if r["kind"] == "cell.outcome"}


def _kinds(rows, kind, **match):
    return [r for r in rows if r["kind"] == kind and all(r.get(k) == v for k, v in match.items())]


def _tmp_left(run_dir):
    return [p for p in (run_dir / "archive").rglob("*") if atomic.is_temp_name(p.name)]


def _tree_hash(run_dir):
    digest = hashlib.sha256()
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file() and p.name != ".lock"):
        digest.update(path.relative_to(run_dir).as_posix().encode() + path.read_bytes())
    return digest.hexdigest()


def _stop_rows(kind, run_id):
    if kind == "control_applied":
        rows = [{"kind": "control.applied", "uuid": "a" * 32, "control": "stop", "decision_id": None, "effect": "applied"}]
    elif kind == "decision_resolved":
        rows = [{"kind": "decision.opened", "decision_id": "D1", "decision_kind": "spend_cap", "subject": run_id,
                 "cause_code": "HB-RUN-007", "options": ["stop", "continue"], "default": "stop"},
                {"kind": "decision.resolved", "decision_id": "D1", "state": "answered", "option": "stop"}]
    else:
        rows = [{"kind": "run.stopped", "code": "HB-RUN-006", "decision_id": None}]
    return [ledger.stamp(r) for r in rows]


def _stop_ledger(g5, dest, kind, states=("C2", "C3", "C5", "C6", "C7"), **kw):
    """The W12 fixture: five cells, one per classifier state (C7 has no launch_intent), and one of the three stop windows."""
    rows = [g5.rows[0]]
    for cid, state in zip(g5.cells, states, strict=True):
        rows += _of(g5.rows, cid)[:STATE_ROWS[state]]
    rows += _stop_rows(kind, g5.plan["run_id"])
    return _materialize(g5, dest, rows, **kw)


def _last_key(rows):
    if not rows:
        return "none"
    last = rows[-1]
    return f"{last['kind']}/{last['next']}" if last["kind"] == "cell.turn_ended" else last["kind"]


# assume: the classifier's Action is an object per plan cell with cell_id, rule ("C0".."C7"), outcome ("failed"/"stopped"/
# None) and code (HB-CELL-117/118/119/None); deferred to K1b's resume.classify, which reconciles it with W1-K section 4.
# If K1b names the fields differently, _verdict and _action below are the only readers to change.
def _verdict(action):
    miss = "<missing>"
    return (getattr(action, "rule", miss), getattr(action, "outcome", miss), getattr(action, "code", miss))


def _action(actions, cid):
    found = [a for a in actions if getattr(a, "cell_id", None) == cid]
    assert len(found) == 1, f"classify returned {len(found)} actions for cell {cid}"
    return found[0]


# ---------------------------------------------------------------- the exhaustive net

@pytest.mark.parametrize("i,name", [(i + 1, n) for i, n in enumerate(PREFIXES)] + [(7, "W7_next_stop")])
def test_every_ledger_prefix_matches_the_adr_table(golden1, i, name):
    classify = _need(resume, "classify")
    assert len(golden1.rows) == N1, "the golden ledger changed: recount N1"
    rows = [dict(r) for r in golden1.rows[:i]]
    if name == "W7_next_stop":
        rows[-1]["next"] = "stop"  # a turn that ended with next = stop took no snapshot and owes none
    cid = golden1.cells[0]
    key = _last_key([r for r in rows if r.get("cell_id") == cid])
    for stopped, table in ((False, NOT_STOPPED), (True, STOPPED)):
        got = _verdict(_action(classify(golden1.plan, rows, stopped), cid))
        assert got == table[key], f"prefix {i} ({key}), stopped={stopped}: {got} != {table[key]}"


def test_every_two_cell_ledger_prefix_matches_the_adr_table(golden2):
    classify = _need(resume, "classify")
    assert len(golden2.rows) == N2, "the two-cell golden ledger changed: recount N2"
    assert {r["cell_id"] for r in golden2.rows if "cell_id" in r} == set(golden2.cells)
    for i in range(1, N2 + 1):
        for stopped, table in ((False, NOT_STOPPED), (True, STOPPED)):
            actions = classify(golden2.plan, golden2.rows[:i], stopped)
            for cid in golden2.cells:
                key = _last_key(_of(golden2.rows[:i], cid))
                assert _verdict(_action(actions, cid)) == table[key], f"prefix {i}, cell {cid}, stopped={stopped}"


# ---------------------------------------------------------------- T2: a real `cli.py run`, killed, run again

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = Path(cli.__file__).resolve().parent.parent
T2_WAIT_S = 90  # a bound on the poll: the barrier makes the target row certain, so this is a failure bound, never a pace

# The child bootstrap composes the fixture dependencies of cmd_run (profiles, workspace builder, preflight, grade,
# identity, campaign) and, for the first child only, an Engine subclass whose barrier blocks AFTER a real durable
# target row. Engine.run is the real one; the second child resumes through the real cmd_run branch.
T2_BOOTSTRAP = """
import json, os, sys, threading
sys.path[:0] = [{tests!r}, {src!r}]
from test_engine import FakeLauncher, _build_workspace
from harness_bench import cli, engine
conf = json.loads(os.environ["HB_T2"])
launcher = FakeLauncher(conf["behaviours"])
cli.profiles.load = lambda root, harness: None
cli.profiles.ProfileLauncher = lambda *a: launcher
cli.preflight.check = lambda *a: None
cli.plan.task_version_hash = lambda d: "v"
cli.plan.require_scripted_user_inputs = lambda *a: None
cli._workspace_builder = lambda *a: _build_workspace
cli.identity.launch_check = lambda *a: None
cli.campaign.run_side_check = lambda *a: None
cli.runner.run_pass = lambda *a, **k: type("Pass", (), {{"summary": lambda self: {{"passes": 1}}}})()
target = conf.get("target")
if target:
    class ObservedEngine(engine.Engine):
        def _append_now(self, fact, record):
            out = super()._append_now(fact, record)  # the row is durable here
            if fact == "events" and all(record.get(k) == v for k, v in target.items()):
                print("TARGET", flush=True)
                threading.Event().wait()  # held until the parent kills this PID
            return out
    engine.Engine = ObservedEngine
sys.exit(cli.main(sys.argv[1:]))
"""


def _t2_plan(base):
    p = _plan(1, parallelism=1)
    p["profiles"] = {"fake": {"usage_source": FakeLauncher.usage_source, "vendor": "fake", "auxiliary_models": []}}
    p["tasks"]["X1"]["turns"] = [{"n": 2, "prompt": "Repair it.\n", "sha256": hashlib.sha256(b"Repair it.\n").hexdigest()}]
    p["tasks"]["X1"]["version_hash"] = "v"
    p["plan_hash"] = plan.plan_hash(p)
    run_dir = base / "runs" / p["run_id"]
    plan.confirm(run_dir, p)
    return p, run_dir


def _t2_child_env(base, p, first_behaviour, target):
    log = base / "prompts.jsonl"
    behaviours = {c["label"]: {"model": "fake-model", "prompts_log": str(log),
                               "per_turn": [{"files": {"a.txt": "1"}}, {"files": {"a.txt": "2"}}], **first_behaviour}
                  for c in p["cells"]}
    return dict(os.environ, HB_T2=json.dumps({"behaviours": behaviours, "target": target})), log


def _t2_kill_and_resume(base, *, behaviour, target):
    """Run `cli.py run` in a child, wait for the real durable target row, check the child is alive, kill only that
    PID, then run `cli.py run` on the same run in a second child. Returns the plan, both children's output and the env."""
    p, run_dir = _t2_plan(base)
    boot = base / "boot.py"
    boot.write_text(T2_BOOTSTRAP.format(tests=str(TESTS_DIR), src=str(SRC_DIR)), encoding="utf-8")
    args = ["--root", str(base / "root"), "--runs", str(run_dir.parent), "--cells-root", str(base / "cells"),
            "--tools-dir", str(_fake_tree(base / "tools")), "run", p["run_id"]]
    env1, _ = _t2_child_env(base, p, behaviour, target)
    first = subprocess.Popen([sys.executable, str(boot), *args], env=env1, stdout=subprocess.PIPE,
                             stderr=(base / "first.err").open("w"), text=True)
    reached, seen = threading.Event(), []

    def read():
        for line in first.stdout:
            seen.append(line)
            if line.strip() == "TARGET":
                reached.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        assert reached.wait(T2_WAIT_S), "the first child never reached its durable target row"
        assert first.poll() is None, "the first child must still be alive when it is killed"
        target_rows = [r for r in _rows(run_dir) if all(r.get(k) == v for k, v in target.items())]
        assert target_rows, "the target row is durably in the ledger before the kill"
    finally:
        if first.poll() is None:
            if sys.platform == "win32":  # this Popen's own tree only: the fake agent is its grandchild
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(first.pid)], capture_output=True, check=False)
            else:
                first.kill()
        first.wait(timeout=30)
        reader.join(timeout=30)
    env2, log = _t2_child_env(base, p, {}, None)
    second = subprocess.run([sys.executable, str(boot), *args], env=env2, capture_output=True, text=True, timeout=180,
                            check=False)
    return SimpleNamespace(plan=p, run_dir=run_dir, cell=p["cells"][0]["cell_id"], log=log, second=second,
                           cells_root=base / "cells")


def _t2_w2(golden1, tmp_path, monkeypatch):
    t2 = _t2_kill_and_resume(tmp_path, behaviour={"mode": "hang_handshake"}, target={"kind": "attempt.process_started"})
    assert t2.second.returncode == 0, t2.second.stderr
    rows = _rows(t2.run_dir)
    assert len(_kinds(rows, "cell.launch_intent")) == 2, "the relaunch writes a second launch_intent"
    assert _outcome_map(t2) == {t2.cell: ("completed", None)}
    logged = [json.loads(s) for s in t2.log.read_text(encoding="utf-8").splitlines()]
    assert [r["n"] for r in logged if r["kind"] == "session/prompt"] == [1, 2]


def _t2_w11(golden1, tmp_path, monkeypatch):
    t2 = _t2_kill_and_resume(tmp_path, behaviour={}, target={"kind": "cell.archived"})
    workspace = t2.cells_root / t2.plan["run_id"] / t2.cell
    assert workspace.is_dir(), "the kill leaves the workspace behind"
    before = _of(_rows(t2.run_dir), t2.cell)
    assert t2.second.returncode == 0, t2.second.stderr
    assert _of(_rows(t2.run_dir), t2.cell) == before, "a cell with outcome and cell.archived gains no row"
    assert workspace.is_dir(), "a leftover workspace is bench teardown's, not the resume's"


@pytest.mark.parametrize("name", ["T2"])
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_cli_run_resumes(tmp_path, name):
    t2 = _t2_kill_and_resume(tmp_path, behaviour={}, target={"kind": "cell.turn_snapshot_archived", "turn": 1})
    assert t2.second.returncode == 0, t2.second.stderr
    assert _outcome_map(t2) == {t2.cell: ("completed", None)}


# ---------------------------------------------------------------- windows (T1, T2 for W2/W11)

def _w2b(golden1, tmp_path, monkeypatch):
    env = _prefix(golden1, tmp_path, 5, no_workspace=golden1.cells)
    assert _resume(env).exit_code == 0
    assert _outcome_map(env) == {golden1.cells[0]: ("completed", None)}


def _w4(golden1, tmp_path, monkeypatch):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 7, tmp_dirs=[(cid, "turn-1.tmp-1-ab")])
    assert _resume(env).exit_code == 0
    assert not _tmp_left(env.run_dir)
    assert _kinds(_post(env), "cell.turn_snapshot_archived", turn=1), "the redo records the snapshot event"
    assert _outcome_map(env) == {cid: ("failed", "HB-CELL-119")}


def _w4b(golden1, tmp_path, monkeypatch):
    stop = _stop_rows("run_stopped", golden1.plan["run_id"])
    env = _materialize(golden1, tmp_path, golden1.rows[:7] + stop)
    assert _resume(env).exit_code == 3
    assert archive.snapshot_folder(env.run_dir, golden1.cells[0], 1).is_dir(), "the archive must hold the turn-1 tree"
    assert _outcome_map(env) == {golden1.cells[0]: ("stopped", None)}


def _w4c(golden1, tmp_path, monkeypatch):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 7)

    def refuse(final, fill, verify):
        raise OSError("publish refused")

    monkeypatch.setattr(atomic, "publish_dir", refuse)
    assert _resume(env).exit_code == 0
    outcome = _kinds(_rows(env.run_dir), "cell.outcome", cell_id=cid)[-1]
    assert (outcome["code"], outcome["resume"]["phase"]) == ("HB-CELL-117", "between-turns")
    assert _kinds(_rows(env.run_dir), "cell.archived", cell_id=cid)


def _w5(golden1, tmp_path, mode):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 7, snapshots={cid}, snap_rows=mode)
    assert _resume(env).exit_code == 0
    assert _kinds(_post(env), "cell.turn_snapshot_archived", turn=1)
    paths = [r["path"] for r in views.rows(env.run_dir, "archive_files") if r.get("snapshot") == "turn-1"]
    assert sorted(paths) == sorted({r["path"] for r in _golden_segment(golden1, "archive_files") if r.get("snapshot") == "turn-1"})


def _w9(golden1, tmp_path, monkeypatch):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 12, tmp_dirs=[(cid, "attempt-1.tmp-1-ab")])
    before = _kinds(_rows(env.run_dir), "cell.outcome")
    assert _resume(env).exit_code == 0
    assert not _tmp_left(env.run_dir)
    assert (env.run_dir / "archive" / cid / "attempt-1").is_dir()
    assert _kinds(_rows(env.run_dir), "cell.archived", cell_id=cid)
    assert _kinds(_rows(env.run_dir), "cell.outcome") == before, "a recorded outcome is never rewritten"


def _w10(golden1, tmp_path, mode):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 12, attempts={cid}, final_rows=mode)
    assert _resume(env).exit_code == 0
    assert _kinds(_post(env), "cell.archived", cell_id=cid)
    final = [r["path"] for r in views.rows(env.run_dir, "archive_files") if not r.get("snapshot")]
    assert sorted(final) == sorted(r["path"] for r in _golden_segment(golden1, "archive_files") if not r.get("snapshot"))


WINDOWS = {
    "W2_launched_not_prompted": _t2_w2,
    "W2b_folder_already_gone": _w2b,
    "W4_snapshot_tmp": _w4,
    "W4b_snapshot_event_absent_under_stop": _w4b,
    "W4c_redo_fails": _w4c,
    "W5a_rows_none": lambda g, t, m: _w5(g, t, "none"),
    "W5b_rows_partial": lambda g, t, m: _w5(g, t, "partial"),
    "W5c_rows_all": lambda g, t, m: _w5(g, t, "all"),
    "W9_archive_tmp": _w9,
    "W10a_rows_none": lambda g, t, m: _w10(g, t, "none"),
    "W10b_rows_partial": lambda g, t, m: _w10(g, t, "partial"),
    "W10c_rows_all": lambda g, t, m: _w10(g, t, "all"),
    "W11_done_skip": _t2_w11,
}


@pytest.mark.parametrize("name", list(WINDOWS))
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_window(golden1, tmp_path, monkeypatch, name):
    WINDOWS[name](golden1, tmp_path, monkeypatch)


# ---------------------------------------------------------------- stop windows

STOP_WINDOWS = ["control_applied", "decision_resolved", "run_stopped", "control_applied_c4"]


@pytest.mark.parametrize("window", STOP_WINDOWS)
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_resume_finishes_the_stop(golden5, tmp_path, window, capsys):
    states = ("C2", "C4", "C5", "C6", "C7") if window.endswith("c4") else ("C2", "C3", "C5", "C6", "C7")
    env = _stop_ledger(golden5, tmp_path, window.removesuffix("_c4"), states)
    intents_before = len(_kinds(_rows(env.run_dir), "cell.launch_intent"))
    assert _resume(env).exit_code == 3
    rows, post = _rows(env.run_dir), _post(env)
    c7 = golden5.cells[4]
    for cid in golden5.cells[:4]:
        outcome = _kinds(post, "cell.outcome", cell_id=cid)
        assert len(outcome) == 1 and outcome[0]["outcome"] == "stopped" and outcome[0]["resume"]["segment_id"], cid
        assert _kinds(rows, "cell.archived", cell_id=cid), f"{cid} is archived"
    assert not _of(post, c7), "the never-launched C7 cell gains no launch_intent and no outcome"
    assert len(_kinds(rows, "cell.launch_intent")) == intents_before, "nothing launches after a stop"
    assert len(_kinds(rows, "run.stopped")) == 1
    completed = _kinds(post, "run.completed")
    assert len(completed) == 1 and "grading" in completed[0] and completed[0]["grading"], "the grading pass ran"
    assert not [f for f in views.verify(env.run_dir) if f.level == "error"]
    assert "run is stopped" in capsys.readouterr().out


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_launch_stopped_is_not_a_stop(golden2, tmp_path):  # W12d
    rows = [golden2.rows[0], ledger.stamp({"kind": "run.launch_stopped", "code": "HB-RUN-004", "reason": "disk low"})]
    env = _materialize(golden2, tmp_path, rows)
    assert not _need(resume, "stop_recorded")(rows)
    assert _resume(env).exit_code == 0
    assert set(_outcome_map(env)) == set(golden2.cells), "the unlaunched cells launch and finish"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_finish_the_stop_is_idempotent(golden5, tmp_path, capsys):  # W12e
    env = _stop_ledger(golden5, tmp_path, "run_stopped")
    assert _resume(env).exit_code == 3
    capsys.readouterr()
    ledger_after_first, rows = _tree_hash(env.run_dir), _rows(env.run_dir)
    assert not _need(resume, "has_work")(env.plan, rows)
    assert _resume(env).exit_code == 3
    assert _tree_hash(env.run_dir) == ledger_after_first, "no run.completed, no segment, a byte-identical ledger"
    assert "run is stopped: 0 cells recorded stopped" in capsys.readouterr().out


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_finished_stop_with_unlaunched_cell_is_a_noop(golden5, tmp_path):  # W12f
    rows = [golden5.rows[0]] + [r for cid in golden5.cells[:2] for r in _of(golden5.rows, cid)[:12]]
    rows += _stop_rows("run_stopped", golden5.plan["run_id"])
    rows += [ledger.stamp({"kind": "run.resumed", "run_id": golden5.plan["run_id"], "plan_hash": golden5.plan["plan_hash"],
                           "segment_id": "x", "trace_id": golden5.plan["trace_id"]}),
             ledger.stamp({"kind": "run.completed", "run_id": golden5.plan["run_id"], "segment_heads": {}, "cells_ended": 2,
                           "grading": {"passes": 1}})]
    env = _materialize(golden5, tmp_path, rows)
    before = _tree_hash(env.run_dir)
    assert _resume(env).exit_code == 3
    assert _tree_hash(env.run_dir) == before, "a finished stop with a C7 cell writes nothing"


# ---------------------------------------------------------------- resume of a resume

def _resumed_segment(g, rows_after, ordinal="-r001"):
    """A previous resume's segments: run.resumed plus the abandoned markers, then `rows_after`; the other facts' are empty."""
    return [("events", ordinal, [{"kind": "run.resumed", "run_id": g.plan["run_id"], "plan_hash": g.plan["plan_hash"],
                                  "segment_id": f"{g.stems['events']}{ordinal}", "trace_id": g.plan["trace_id"]}, *rows_after]),
            ("turn_usage", ordinal, []), ("archive_files", ordinal, [])]


def _dead_marker(env, fact="events"):
    path = next((env.run_dir / fact).glob("*.jsonl"))
    report = ledger.verify_segment(path)
    return {"kind": "segment.abandoned", "code": "HB-LED-004", "fact": fact, "segment_id": path.stem,
            "line_count": report.lines, "head_hash": report.head_hash, "error": "engine died"}


def _uninterrupted(g, tmp_path, i, **kw):
    clean = _prefix(g, tmp_path / "clean", i, **kw)
    assert _resume(clean).exit_code == 0
    return _outcome_map(clean)


def _w13_w14(golden1, tmp_path, name, i):
    want = _uninterrupted(golden1, tmp_path, i)
    marker = _dead_marker(_prefix(golden1, tmp_path / "crashed", i))
    after = []
    if name == "W14":  # a reconciled outcome row is already in the resume's own segment
        after = [{"kind": "cell.outcome", "cell_id": golden1.cells[0], "outcome": "failed", "code": "HB-CELL-118",
                  "resume": {"segment_id": f"{golden1.stems['events']}-r001", "turn": 1, "phase": "turn-complete",
                             "rule": "C5"}}]
    env = _prefix(golden1, tmp_path / "crashed2", i, extra=_resumed_segment(golden1, [marker, *after]))
    assert _resume(env).exit_code == 0
    assert _outcome_map(env) == want
    abandoned = [(r["fact"], r["segment_id"]) for r in _kinds(_rows(env.run_dir), "segment.abandoned")]
    assert len(abandoned) == len(set(abandoned)), "a segment already named is never named twice"


def _w13b(golden1, tmp_path, monkeypatch):
    env = _prefix(golden1, tmp_path, 6, stray=["-r002"])
    assert _resume(env).exit_code == 0
    assert (env.run_dir / "events" / f"{golden1.stems['events']}-r003.jsonl").is_file(), "the ordinal skips a stray r002"


def _w13c(golden1, tmp_path, monkeypatch):
    env = _prefix(golden1, tmp_path, 6)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() - 3600)
    assert _resume(env).exit_code == 0
    names = [p.stem for p in views.segment_paths(env.run_dir, "events")]
    assert names == sorted(names) and names[-1].endswith("-r001"), "the new segment sorts after the old ones"
    kinds = [r["kind"] for r in views.rows(env.run_dir, "events")]
    assert kinds.index("run.resumed") > kinds.index("run.started")


def _w15(golden1, tmp_path):
    env = _materialize(golden1, tmp_path, [])
    assert _resume(env).exit_code == 0
    assert _kinds(_rows(env.run_dir), "run.started")
    assert _outcome_map(env) == {golden1.cells[0]: ("completed", None)}


def _w16(golden2, tmp_path):
    run_id = golden2.plan["run_id"]
    rows = [golden2.rows[0], ledger.stamp({"kind": "run.launch_stopped", "code": "HB-RUN-004", "reason": "disk low"}),
            ledger.stamp({"kind": "run.completed", "run_id": run_id, "segment_heads": {}, "cells_ended": 0, "grading": None})]
    env = _materialize(golden2, tmp_path, rows)
    resumed = _materialize(golden2, tmp_path / "mid", rows + [ledger.stamp(
        {"kind": "run.resumed", "run_id": run_id, "plan_hash": golden2.plan["plan_hash"], "segment_id": "x",
         "trace_id": golden2.plan["trace_id"]})])
    assert status.build(resumed.run_dir).completion == "in progress", "complete iff run.completed follows the last run.resumed"
    assert _resume(env).exit_code == 0
    assert set(_outcome_map(env)) == set(golden2.cells)
    assert status.build(env.run_dir).completion == "complete"


@pytest.mark.parametrize("name", ["W13", "W13b_stray_segment", "W13c_clock_back", "W14"])
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_resume_of_a_resume(golden1, tmp_path, monkeypatch, name):
    if name == "W13b_stray_segment":
        return _w13b(golden1, tmp_path, monkeypatch)
    if name == "W13c_clock_back":
        return _w13c(golden1, tmp_path, monkeypatch)
    return _w13_w14(golden1, tmp_path, name, 6 if name == "W13" else 9)


@pytest.mark.parametrize("name", ["W15"])
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_run_started_by_resume(golden1, tmp_path, name):
    _w15(golden1, tmp_path)


@pytest.mark.parametrize("name", ["W16"])
@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_resume_after_launch_stop(golden2, tmp_path, name):
    _w16(golden2, tmp_path)


# ---------------------------------------------------------------- run-level state and liveness

@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_stop_window_with_open_decision(golden5, tmp_path):
    opened = ledger.stamp({"kind": "decision.opened", "decision_id": "D1", "decision_kind": "spend_cap",
                           "subject": golden5.plan["run_id"], "cause_code": "HB-RUN-007", "options": ["stop", "continue"],
                           "default": "stop"})
    env = _stop_ledger(golden5, tmp_path, "run_stopped")
    rows = _rows(env.run_dir)
    env = _materialize(golden5, tmp_path / "d", [*rows[:-1], opened, rows[-1]])
    assert _resume(env).exit_code == 3
    resolved = _kinds(_post(env), "decision.resolved", decision_id="D1")
    assert resolved and resolved[0]["state"].startswith("superseded")
    assert not _kinds(_post(env), "cell.launch_intent"), "launching is not paused, it is stopped"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_leftover_applied_control_not_duplicated(golden5, tmp_path):
    env = _stop_ledger(golden5, tmp_path, "control_applied")
    control = env.run_dir / "control" / f"{'a' * 32}.json"
    control.parent.mkdir()
    control.write_text(json.dumps({"schema": "bench-control/1", "uuid": "a" * 32, "control": "stop", "decision_id": None,
                                   "option": None, "requested_at": "2026-10-06T00:00:00Z"}), encoding="utf-8")
    assert _resume(env).exit_code == 3
    assert len(_kinds(_rows(env.run_dir), "control.applied", uuid="a" * 32)) == 1
    assert not control.exists(), "a control whose uuid is in the ledger is removed, not re-applied"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_spend_total_survives_resume(golden2, tmp_path):
    first, second = golden2.cells
    one = golden2.spend[0]
    p = {**golden2.plan, "parameters": {**golden2.plan["parameters"], "spend_cap_tokens": one + 1}}
    rows = [golden2.rows[0], *_of(golden2.rows, first)]
    env = _materialize(golden2, tmp_path, rows)
    env.plan["parameters"] = p["parameters"]
    _resume(env)
    assert _kinds(_rows(env.run_dir), "decision.opened", decision_kind="spend_cap"), \
        f"the restored total ({one}) plus {second}'s spend must pass the cap {one + 1}"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_stop_control_file_honoured_before_relaunch(golden2, tmp_path):
    first, second = golden2.cells
    rows = [golden2.rows[0], *_of(golden2.rows, first)[:9]]
    env = _materialize(golden2, tmp_path, rows)
    (env.run_dir / "control").mkdir()
    (env.run_dir / "control" / f"{'b' * 32}.json").write_text(json.dumps(
        {"schema": "bench-control/1", "uuid": "b" * 32, "control": "stop", "decision_id": None, "option": None,
         "requested_at": "2026-10-06T00:00:00Z"}), encoding="utf-8")
    assert _resume(env).exit_code == 3
    assert not _of(_post(env), second) or not _kinds(_of(_post(env), second), "cell.launch_intent")
    assert _kinds(_rows(env.run_dir), "run.stopped", code="HB-RUN-006")


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_stop_code_read_from_decision_kind(golden5, tmp_path):
    env = _stop_ledger(golden5, tmp_path, "decision_resolved")
    assert _resume(env).exit_code == 3
    assert _kinds(_post(env), "run.stopped")[0]["code"] == "HB-RUN-007"


def _sleeper():
    proc = subprocess.Popen([sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "up"  # the child announces itself: no timed wait
    return proc, host.creation_time(proc.pid)


def _with_live_pid(golden1, tmp_path, created_shift=0, **params):
    """A crashed turn whose recorded pid belongs to a process this test owns."""
    proc, created = _sleeper()
    rows = [dict(r) for r in golden1.rows[:6]]
    rows[3] = {**rows[3], "pid": proc.pid, "created_at": created + created_shift}
    env = _materialize(golden1, tmp_path, rows)
    # assume: plan.parameters.pid_wait_s is the bounded wait for a live lock holder (W1-K liveness); confirm in K1c
    # (resume.py / plan.DEFAULT_PARAMETERS); if the name or unit differs, only this fixture line and the bound below change.
    env.plan["parameters"].update({"pid_wait_s": 1, **params})
    return env, proc


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_resume_heartbeats_the_lock(golden1, tmp_path):
    env, proc = _with_live_pid(golden1, tmp_path, lock_staleness=1)
    seen, box = set(), {}

    def target():
        try:
            box["summary"] = _resume(env)
        except BenchError as exc:
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    try:
        thread.start()
        while thread.is_alive():
            seen.add(status.build(env.run_dir).liveness)
            thread.join(0.2)
    finally:
        proc.kill()
        proc.wait()
    assert "alive" in seen and "stalled" not in seen, f"liveness while the pid wait ran: {seen}"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_recycled_pid_is_gone(golden1, tmp_path):
    env, proc = _with_live_pid(golden1, tmp_path, created_shift=1)
    try:
        started = time.monotonic()
        assert _resume(env).exit_code == 0
        waited = time.monotonic() - started
        assert waited < env.plan["parameters"]["pid_wait_s"], "a recycled pid is not waited for"
        assert proc.poll() is None, "a foreign process is never terminated"
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_pid_alive_defers_and_writes_no_completed(golden1, tmp_path, capsys):
    env, proc = _with_live_pid(golden1, tmp_path)
    try:
        assert _resume(env).exit_code == 3
        post = _post(env)
        assert not _kinds(post, "run.completed")
        assert _need(resume, "has_work")(env.plan, _rows(env.run_dir)) is True
        assert _kinds(post, "resume.cell_deferred") or "run is not finished" in capsys.readouterr().out
        assert proc.poll() is None, "the check never terminates the foreign process"
    finally:
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------- refusals

def _refusal(case, golden1, golden5, tmp_path):
    """(env, expected code) for one refusal; nothing may be written by any of them."""
    if case == "live_lock":
        env, code = _prefix(golden1, tmp_path, 6), "HB-RUN-005"
    elif case == "identity_drift":
        env, code = _prefix(golden1, tmp_path, 6), "HB-IDN-001"
        env.cfg.identity_check = lambda: identity.CheckResult(["tasks/X1 changed"], False)
    elif case == "verify_failure":
        env, code = _prefix(golden1, tmp_path, 12), "HB-RUN-009"
        path = next((env.run_dir / "events").glob("*.jsonl"))
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 3] ^= 0x01
        path.write_bytes(bytes(raw))
    elif case == "archive_missing":
        env, code = _prefix(golden1, tmp_path, 13, no_attempt=golden1.cells), "HB-LED-005"
        shutil.rmtree(env.run_dir / "archive" / golden1.cells[0] / "attempt-1", ignore_errors=True)
    else:  # stopped_with_drift: a stop is not a refusal, but an untrusted ledger is never finished
        env, code = _stop_ledger(golden5, tmp_path, "run_stopped"), "HB-IDN-001"
        env.cfg.identity_check = lambda: identity.CheckResult(["tasks/X1 changed"], False)
    return env, code


REFUSALS = ["live_lock", "identity_drift", "verify_failure", "archive_missing", "stopped_with_drift"]


def _refuse(case, golden1, golden5, tmp_path):
    env, code = _refusal(case, golden1, golden5, tmp_path)
    lock = oslock.RunLock.acquire(env.run_dir / ".lock") if case == "live_lock" else None
    before = _tree_hash(env.run_dir)
    try:
        with pytest.raises(BenchError) as raised:
            _resume(env)
    finally:
        if lock:
            lock.release()
    return raised.value, code, before, _tree_hash(env.run_dir), env


def test_refused_live_lock(golden1, golden5, tmp_path):
    exc, code, *_ = _refuse("live_lock", golden1, golden5, tmp_path)
    assert exc.code == code and "heartbeat" in str(exc), "the message holds the heartbeat age, not a PID"


def test_refused_identity_drift(golden1, golden5, tmp_path):
    assert _refuse("identity_drift", golden1, golden5, tmp_path)[0].code == "HB-IDN-001"


def test_refused_verify_failure_names_segment(golden1, golden5, tmp_path):
    exc, code, *_, env = _refuse("verify_failure", golden1, golden5, tmp_path)
    assert exc.code == code and next((env.run_dir / "events").glob("*.jsonl")).stem in str(exc)


def test_refused_unrepairable_archive_writes_nothing(golden1, golden5, tmp_path):
    exc, code, before, after, _env = _refuse("archive_missing", golden1, golden5, tmp_path)
    assert exc.code == code and "attempt-1" in str(exc) and before == after


def test_refusal_order(golden1, golden5, tmp_path):
    env, _ = _refusal("verify_failure", golden1, golden5, tmp_path)
    env.cfg.identity_check = lambda: identity.CheckResult(["tasks/X1 changed"], False)
    with pytest.raises(BenchError) as raised:
        _resume(env)
    assert raised.value.code == "HB-IDN-001", "identity is judged before the chain"
    exc, *_ = _refuse("stopped_with_drift", golden1, golden5, tmp_path / "s")
    assert exc.code == "HB-IDN-001", "a stopped ledger with a drifted identity is refused, never finished"


@pytest.mark.parametrize("case", REFUSALS)
def test_refusal_writes_nothing(golden1, golden5, tmp_path, case):
    exc, code, before, after, env = _refuse(case, golden1, golden5, tmp_path)
    assert exc.code == code, f"{case} is refused with {code}"
    assert before == after, "a refusal changes no file: no segment, no row"
    assert not (env.run_dir / ".alarm_check").exists()


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_sweep_pairing_refuses_wrong_lock(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 6)
    other = tmp_path / "other"
    other.mkdir()
    with oslock.RunLock.acquire(other / ".lock") as lock, pytest.raises(ValueError):
        _need(resume, "sweep_archives")(env.run_dir, lock)


def test_sweep_archives_cleans_root_and_each_cell(golden1, tmp_path):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 6, tmp_dirs=[(cid, "attempt-1.tmp-123-" + "a" * 32)])
    root_temp = env.run_dir / "archive" / (cid + ".tmp-123-" + "b" * 32)
    root_temp.mkdir()
    sweep = _need(resume, "sweep_archives")
    with oslock.RunLock.acquire(env.run_dir / ".lock") as lock:
        sweep(env.run_dir, lock)
    assert not _tmp_left(env.run_dir)


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_abandoned_marker_pins_head(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 6)
    assert _resume(env).exit_code == 0
    dead = next((env.run_dir / "events").glob(f"{golden1.stems['events']}.jsonl"))
    lines = dead.read_bytes().splitlines(keepends=True)
    dead.write_bytes(b"".join(lines[:-1]))
    assert any(f.code == "HB-LED-002" for f in views.verify(env.run_dir)), "a cut dead segment must fail verify"


@pytest.mark.xfail(strict=True, reason="K1c: the resume engine (W1-K K5/K6) turns this window green")
def test_abandoned_set_equals_unsealed_engine_facts(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12)
    assert _resume(env).exit_code == 0
    assert {r["fact"] for r in _kinds(_rows(env.run_dir), "segment.abandoned")} == set(engine.FACTS)


# ---------------------------------------------------------------- one definition of "completed" and of "work left"

def test_completed_has_one_definition():
    _need(views, "completed")  # D-K5: complete iff a run.completed row follows the last run.resumed
    root = Path(__file__).resolve().parents[1] / "src"
    hits = {str(p.relative_to(root)): sum("run.completed" in line for line in p.read_text(encoding="utf-8").splitlines())
            for p in root.rglob("*.py")}
    assert sum(hits.values()) == BASE_COMPLETED_HITS, f"run.completed matching lines moved: {hits}"


def _work_ledger(g, upto, *extra):
    return [g.rows[0], *_of(g.rows, g.cells[0])[:upto], *extra]


def test_finished_stop_is_silent(golden5):  # R-102: a C7 cell in the fixture
    rows = [golden5.rows[0]] + [r for cid in golden5.cells[:2] for r in _of(golden5.rows, cid)[:12]]
    rows += _stop_rows("run_stopped", golden5.plan["run_id"])
    rows += [ledger.stamp({"kind": "run.resumed", "run_id": golden5.plan["run_id"], "plan_hash": "p", "segment_id": "x",
                           "trace_id": "t"}), ledger.stamp({"kind": "run.completed", "run_id": golden5.plan["run_id"]})]
    assert _need(resume, "has_work")(golden5.plan, rows) is False


def test_alarm_fires_after_crash_in_grading(golden1):
    rows = golden1.rows[:14]  # every cell archived, no run.completed
    assert _need(resume, "has_work")(golden1.plan, rows) is True


def test_alarm_fires_after_crash_before_last_archive(golden1):
    rows = golden1.rows[:12]  # outcome recorded, cell.archived absent
    assert _need(resume, "has_work")(golden1.plan, rows) is True


def test_launch_stop_alarms(golden2):
    rows = [golden2.rows[0], ledger.stamp({"kind": "run.launch_stopped", "code": "HB-RUN-004", "reason": "disk low"})]
    assert _need(resume, "has_work")(golden2.plan, rows) is True


def _recover_final(env, *, archived=False):
    recover = _need(archive, "recover_archive")
    cid = env.g.cells[0]
    present = [r for r in ledger.read_segment(env.run_dir / "archive_files" / f"{env.g.stems['archive_files']}.jsonl")
               if archive.snapshot_of(r) == "final" and r["cell_id"] == cid]
    with oslock.RunLock.acquire(env.run_dir / ".lock") as lock:
        return recover(env.cfg.cells_root / env.plan["run_id"] / cid, env.run_dir / "archive" / cid,
                       1, set(), present, run_lock=lock, recorded_archived=archived)


def _assert_recovery(env, missing):
    recovered = _recover_final(env)
    cid = env.g.cells[0]
    want = [r for r in _golden_segment(env.g, "archive_files") if r["cell_id"] == cid and not r.get("snapshot")]
    assert recovered.result.archive_hash == archive.archive_hash(want)
    assert len(recovered.missing_rows) == missing
    archive.verify(recovered.result.folder, recovered.result.rows)
    assert not _tmp_left(env.run_dir)


def _recover_source(env):
    """Use the actual golden copy, including its session files, as the surviving source."""
    cid = env.g.cells[0]
    cell_dir = env.cfg.cells_root / env.plan["run_id"] / cid
    if cell_dir.exists():
        shutil.rmtree(cell_dir)
    shutil.copytree(env.g.run_dir / "archive" / cid / "attempt-1", cell_dir)


def test_recover_archive_without_final_sweeps_then_copies(golden1, tmp_path):
    cid = golden1.cells[0]
    env = _prefix(golden1, tmp_path, 12, tmp_dirs=[(cid, "attempt-1.tmp-123-" + "a" * 32)])
    _recover_source(env)
    want = [r for r in _golden_segment(golden1, "archive_files") if not r.get("snapshot")]
    _assert_recovery(env, len(want))


def test_recover_archive_final_rows_absent(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, attempts=golden1.cells, final_rows="none")
    _recover_source(env)
    want = [r for r in _golden_segment(golden1, "archive_files") if not r.get("snapshot")]
    _assert_recovery(env, len(want))


def test_recover_archive_final_rows_partial(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, attempts=golden1.cells, final_rows="partial")
    _recover_source(env)
    want = [r for r in _golden_segment(golden1, "archive_files") if not r.get("snapshot")]
    _assert_recovery(env, len(want) - len(want) // 2)


def test_recover_archive_final_rows_complete(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, attempts=golden1.cells, final_rows="all", no_workspace=golden1.cells)
    _assert_recovery(env, 0)


def test_recover_archive_recorded_rows_without_folder_refuses(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, final_rows="all")
    before = _tree_hash(env.run_dir)
    with pytest.raises(BenchError, match="attempt-1") as raised:
        _recover_final(env)
    assert raised.value.code == "HB-LED-005" and before == _tree_hash(env.run_dir)


def test_recover_archive_recorded_event_without_folder_refuses(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 13, final_rows="none", no_attempt=golden1.cells)
    before = _tree_hash(env.run_dir)
    with pytest.raises(BenchError, match="attempt-1") as raised:
        _recover_final(env, archived=True)
    assert raised.value.code == "HB-LED-005" and before == _tree_hash(env.run_dir)


def test_recover_archive_changed_source_refuses_read_only(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, attempts=golden1.cells, final_rows="none")
    _recover_source(env)
    (env.cfg.cells_root / env.plan["run_id"] / golden1.cells[0] / "ws" / "a.txt").write_text("changed", encoding="utf-8")
    before = _tree_hash(env.run_dir)
    with pytest.raises(BenchError, match="a.txt") as raised:
        _recover_final(env)
    assert raised.value.code == "HB-LED-005" and before == _tree_hash(env.run_dir)


def test_recover_archive_differing_recorded_row_refuses_read_only(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, attempts=golden1.cells, final_rows="all")
    _recover_source(env)
    recover = _need(archive, "recover_archive")
    cid = golden1.cells[0]
    present = [copy.deepcopy(r) for r in _golden_segment(golden1, "archive_files") if not r.get("snapshot")]
    present[0]["sha256"] = "0" * 64
    before = _tree_hash(env.run_dir)
    with oslock.RunLock.acquire(env.run_dir / ".lock") as lock, pytest.raises(BenchError, match=present[0]["path"]):
        recover(env.cfg.cells_root / env.plan["run_id"] / cid, env.run_dir / "archive" / cid, 1, set(), present,
                run_lock=lock)
    assert before == _tree_hash(env.run_dir)


def test_resume_requires_verify_callback(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 6)
    env.cfg.verify = None
    before = _tree_hash(env.run_dir)
    with pytest.raises(ValueError, match="verify"):
        _resume(env)
    assert before == _tree_hash(env.run_dir)


def test_resume_refusal_releases_run_lock(golden1, golden5, tmp_path):
    env, code = _refusal("identity_drift", golden1, golden5, tmp_path)
    with pytest.raises(BenchError) as raised:
        _resume(env)
    assert raised.value.code == code
    assert not oslock.is_held(env.run_dir / ".lock")


def test_resume_archive_file_without_folder_refuses(golden1, tmp_path):
    env = _prefix(golden1, tmp_path, 12, final_rows="partial")
    before = _tree_hash(env.run_dir)
    with pytest.raises(BenchError, match="attempt-1") as raised:
        _resume(env)
    assert raised.value.code == "HB-LED-005" and before == _tree_hash(env.run_dir)




@pytest.mark.parametrize("kinds,expected", [
    ([], False), (["run.completed"], True), (["run.completed", "run.resumed"], False),
    (["run.completed", "run.resumed", "run.completed"], True),
    (["run.completed", "run.resumed", "run.completed", "run.resumed"], False),
])
def test_completed_uses_the_latest_resume_boundary(kinds, expected):
    assert _need(views, "completed")([{"kind": kind} for kind in kinds]) is expected


def test_segment_rows_keeps_engine_segments_and_filters_dead_grading(tmp_path):
    run_dir = tmp_path / "segments"
    for sid in ("engine-1", "engine-1-r001", "grade-dead", "grade-done"):
        with ledger.SegmentWriter.create(run_dir / "events", sid) as writer:
            kind = "grading.completed" if sid == "grade-done" else "run.started"
            writer.append(ledger.stamp({"kind": kind, "grading_id": sid}))
            if sid == "grade-done":
                writer.seal()
    grouped = _need(views, "segment_rows")(run_dir, "events")
    assert [sid for sid, _ in grouped] == ["engine-1", "engine-1-r001", "grade-done"]
    assert [row for _, segment in grouped for row in segment] == views.rows(run_dir, "events")


def test_load_reads_completion_after_a_resume(golden1, tmp_path):
    run_dir = tmp_path / "run"
    shutil.copytree(golden1.run_dir, run_dir)
    assert views.load(run_dir, any_kind=True).completed is True
    first = views.segment_paths(run_dir, "events")[0].stem
    sid = first + "-r001"
    with ledger.SegmentWriter.create(run_dir / "events", sid) as writer:
        writer.append(ledger.stamp({"kind": "run.resumed", "segment_id": sid}))
    assert views.load(run_dir, any_kind=True).completed is False
    assert views.load(golden1.run_dir, any_kind=True).completed is True  # the shared golden ledger stays immutable


@pytest.mark.parametrize("fault", ["none", "cut", "count", "head", "sealed", "missing", "broken"])
def test_hand_built_abandoned_engine_segment_pins_its_head(golden1, tmp_path, fault):
    env = _materialize(golden1, tmp_path, golden1.rows[:1])
    sid = golden1.stems["events"] + "-r001"
    path = env.run_dir / "events" / f"{sid}.jsonl"
    with ledger.SegmentWriter.create(env.run_dir / "events", sid) as writer:
        writer.append(ledger.stamp({"kind": "run.resumed", "segment_id": sid}))
        writer.append(ledger.stamp({"kind": "run.launch_stopped", "code": "HB-RUN-004"}))
    report = ledger.verify_segment(path)
    marker = {"kind": "segment.abandoned", "code": "HB-LED-004", "fact": "events", "segment_id": sid,
              "line_count": report.lines, "head_hash": report.head_hash, "error": "unsealed engine"}
    if fault == "count":
        marker["line_count"] += 1
    if fault == "head":
        marker["head_hash"] = "0" * 64
    with ledger.SegmentWriter.create(env.run_dir / "events", golden1.stems["events"] + "-r002") as writer:
        writer.append(ledger.stamp(marker))
    if fault == "cut":
        path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])  # still a sound chain, but cut by one row
    elif fault == "sealed":
        with ledger.SegmentWriter.reopen(path) as writer:
            writer.seal()
    elif fault == "missing":
        path.unlink()
    elif fault == "broken":
        lines = path.read_bytes().splitlines(keepends=True)
        row = json.loads(lines[0])
        row["hash"] = "0" * 64
        path.write_bytes(ledger.canonical(row) + b"\n" + b"".join(lines[1:]))
    errors = [finding for finding in views.verify(env.run_dir) if finding.level == "error"]
    if fault == "none":
        assert errors == []
    else:
        assert any(finding.code == "HB-LED-002" and sid in finding.message for finding in errors), errors


# ---------------------------------------------------------------- K4: the stop predicate (D-K4) and has_work clause 1

@pytest.mark.parametrize("row,expected", [
    ({"kind": "run.stopped"}, True),
    ({"kind": "control.applied", "control": "stop", "effect": "applied"}, True),
    ({"kind": "decision.resolved", "option": "stop"}, True),
    ({"kind": "run.launch_stopped", "code": "HB-RUN-004"}, False),
    ({"kind": "control.applied", "control": "stop", "effect": "ignored"}, False),
    ({"kind": "control.applied", "control": "continue", "effect": "applied"}, False),
    ({"kind": "decision.resolved", "option": "continue"}, False),
])
def test_stop_recorded_reads_the_three_rows(row, expected):
    assert _need(resume, "stop_recorded")([{"kind": "run.started"}, row]) is expected


def test_has_work_while_a_launched_cell_has_no_outcome(golden1):
    rows = golden1.rows[:5]  # launch_intent recorded, no outcome, no run.completed
    assert _need(resume, "has_work")(golden1.plan, rows) is True
