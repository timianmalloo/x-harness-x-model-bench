"""X-C3a proof: pilot attach, pilot pass, admit, register, the content reader (W1-C section 13: C-18 register, C-20, C-21,
C-23..C-33, C-35, C-47 rows, C-48, I-1, I-2, L-11).

Stubs (their real partner is X-INT-1): `gates.pilot`, `gates.admission`, the three `readiness` readers and `views.load` (C-23, C-26,
C-48). Everything else is real: the CLI, the session and lock, the ledger, the content files, sealed grading segments.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
import threading
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_cli_campaign import (
    CID,
    QUESTION,
    TREAT_COMMIT,
    attempt,
    baselined,
    bench,
    cdir,
    code_of,
    commit_all,
    edit_src,
    git,
    ledger_path,
    power_file,
    rows_of,
    snapshot,
    tree,
    write_plan,
)

from harness_bench import campaign, cli, gates, ledger, plan, power

ROOT = Path(__file__).resolve().parents[1]
GID = "grade-20261004T101112-0a1b2c"
GID2 = "grade-20261004T111213-1b2c3d"
RING = {"tag": "pilot", "hash": "r" * 64}


def grade_pass(root: Path, run_id: str, gid: str = GID, *, seal: bool = True, score: str = "a", facts=("events", "scores")) -> None:
    """Real grading segments (events and scores) of one pass, sealed or not."""
    run = root / "runs" / run_id
    for fact in facts:
        rows = ([{"kind": "grading.started", "grading_id": gid}, {"kind": "grading.completed", "grading_id": gid}] if fact == "events"
                else [{"kind": "score.recorded", "grading_id": gid, "cell_id": "c1", "metric_id": "m", "value": score}])
        with ledger.SegmentWriter.create(run / fact, gid) as writer:
            for row in rows:
                writer.append(ledger.stamp(row))
            if seal:
                writer.seal()


@pytest.fixture
def stubs(monkeypatch):
    seen = SimpleNamespace(pilot=[], items=[], na={"T1": frozenset({"verified_before_use"})}, admission=lambda tasks: {t: (1, "") for t in tasks})

    def fake_pilot(view, hidden, unbiased, *, expected_na=gates.EMPTY):
        seen.pilot.append(SimpleNamespace(hidden=hidden, unbiased=unbiased, expected_na=expected_na))
        return list(seen.items)

    def fake_view(run_dir, *a, **k):
        current = max((run_dir / "events").glob("grade-*.jsonl")).stem
        return SimpleNamespace(grading_id=current, plan=plan.load_confirmed(run_dir), cells=[])

    monkeypatch.setattr(campaign.gates, "pilot", fake_pilot)
    monkeypatch.setattr(campaign.gates, "admission", lambda view, tasks, off_arm="off": seen.admission(list(tasks)))
    monkeypatch.setattr(campaign.readiness, "hidden_test_disagreements", lambda run_dir, gid: [])
    monkeypatch.setattr(campaign.readiness, "unbiased_failures", lambda run_dir, gid: [])
    monkeypatch.setattr(campaign.readiness, "expected_na", lambda root, tasks: seen.na)
    monkeypatch.setattr(campaign.views, "load", fake_view)
    return seen


def cmd(root, capsys, *argv):
    capsys.readouterr()
    rc = bench(root, "campaign", *argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def stmt(root: Path, name: str = "prereg.json", **over) -> tuple[Path, str]:
    body = {"schema": "bench-prereg/1", "question": QUESTION, "arms": {"treat": {"commit": TREAT_COMMIT, "revision": "r1"}},
            "primary_metric": {"security": "property_check_pass"}, "mde": {"security": "0.3"}, "alpha": "0.05", "power": "0.8",
            "correction": {"method": "bonferroni", "m": 2}, "pairing_unit": "unpaired", "method": "paired-bootstrap", "exclusions": [],
            "min_pairs": 3, **over}
    path = root / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path, hashlib.sha256(ledger.canonical(body)).hexdigest()


STAGES = ("plan", "attached", "passed", "powered", "admitted")


def ready(root: Path, upto: str) -> None:
    """A baselined campaign, a pilot plan and one sealed pass, then the real commands up to `upto`."""
    baselined(root, "T1", "T2")
    write_plan(root, "P1", prereg_hash=None, ring=RING, tasks=("T1", "T2"))
    grade_pass(root, "P1")
    steps = {"attached": ["pilot", "attach", CID, "P1"], "passed": ["pilot", "pass", CID, "P1"],
             "powered": ["power", CID, "--inputs", str(power_file(root))], "admitted": ["admit", CID]}
    for name in STAGES[1 : STAGES.index(upto) + 1]:
        assert bench(root, "campaign", *steps[name]) == 0, name


def kinds_of(root: Path) -> list[str]:
    return [r["kind"] for r in rows_of(root)]


# --- C-20, C-21: pilot attach ------------------------------------------------------------------------------------------

def test_pilot_attach_refuses_a_foreign_plan_a_missing_plan_and_a_ringless_plan_c20(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    baselined(root, "T1", "T2")
    write_plan(root, "F1", prereg_hash=None, ring=RING, cid="other")
    write_plan(root, "N1", prereg_hash=None, ring=None)
    for run in ("F1", "N1", "GONE"):
        before = ledger_path(root).read_bytes()
        rc, _, err = cmd(root, capsys, "pilot", "attach", CID, run)
        assert rc == 1 and "HB-CMP-002" in err, run
        assert ledger_path(root).read_bytes() == before
    write_plan(root, "P1", prereg_hash=None, ring=RING, tasks=("T1", "T2"))
    assert cmd(root, capsys, "pilot", "attach", CID, "P1")[0] == 0
    row = rows_of(root)[-1]
    assert row["kind"] == "ring_run.attached" and row["ring_hash"] == "r" * 64 and "tag" not in row
    assert row["plan_hash"] == plan.load_confirmed(root / "runs" / "P1")["plan_hash"]


def test_pilot_attach_refuses_a_non_pilot_ring_c21(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    baselined(root, "T1", "T2")
    write_plan(root, "C1", prereg_hash=None, ring={"tag": "comparison", "hash": "r" * 64})
    rc, _, err = cmd(root, capsys, "pilot", "attach", CID, "C1")
    assert rc == 1 and "HB-CMP-002" in err and "comparison" in err
    assert "ring_run.attached" not in kinds_of(root)


# --- C-23..C-25, C-48: pilot pass ----------------------------------------------------------------------------------------

def test_pilot_pass_refuses_on_gate_items_and_passes_expected_na_c23(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "attached")
    stubs.items = [gates.GateItem("primary-not-recorded", "T1/m", "no value")]
    rc, _, err = cmd(root, capsys, "pilot", "pass", CID, "P1")
    assert rc == 1 and "HB-CMP-008" in err and "primary-not-recorded" in err and "T1/m" in err
    assert "pilot.passed" not in kinds_of(root)
    assert stubs.pilot[-1].expected_na == {"T1": frozenset({"verified_before_use"})}  # the keyword, from readiness.expected_na
    stubs.items = []
    assert cmd(root, capsys, "pilot", "pass", CID, "P1")[0] == 0
    assert kinds_of(root)[-1] == "pilot.passed" and campaign.read(root, CID).state == "piloted"


def test_pilot_gate_input_hash_changes_with_the_segment_heads_c24(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "attached")
    assert cmd(root, capsys, "pilot", "pass", CID, "P1")[0] == 0
    grade_pass(root, "P1", GID2, score="b")
    assert cmd(root, capsys, "pilot", "pass", CID, "P1", "--grading-id", GID2)[0] == 0
    passes = [r for r in rows_of(root) if r["kind"] == "pilot.passed"]
    assert [r["grading_id"] for r in passes] == [GID, GID2]
    heads = [ledger.verify_segment(root / "runs" / "P1" / f / f"{g}.jsonl").head_hash for g in (GID, GID2) for f in ("scores", "events")]
    want = [hashlib.sha256(ledger.canonical({"grading_id": g, "scores_head": heads[2 * i], "events_head": heads[2 * i + 1]})).hexdigest()
            for i, g in enumerate((GID, GID2))]
    assert [r["gate_input_hash"] for r in passes] == want and want[0] != want[1]


def test_pilot_pass_refuses_an_unsealed_pass_and_an_unattached_run_c25(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "plan")
    rc, _, err = cmd(root, capsys, "pilot", "pass", CID, "P1")  # never attached
    assert rc == 1 and "HB-CMP-002" in err and "not attached" in err
    assert cmd(root, capsys, "pilot", "attach", CID, "P1")[0] == 0
    for fact in ("events", "scores"):
        (root / "runs" / "P1" / fact / f"{GID}.jsonl").unlink()
    grade_pass(root, "P1", seal=False)
    rc, _, err = cmd(root, capsys, "pilot", "pass", CID, "P1")
    assert rc == 1 and "HB-CMP-002" in err and "not complete" in err
    assert "pilot.passed" not in kinds_of(root)


@pytest.mark.parametrize("reader", ["hidden_test_disagreements", "unbiased_failures", "expected_na"])
def test_a_failed_reader_writes_no_row_and_prints_its_text_c48(tmp_path, capsys, stubs, monkeypatch, reader):
    root = tree(tmp_path)
    ready(root, "attached")

    def boom(*a, **k):
        raise campaign.BenchError("HB-USR-002", f"{reader} cannot read the ledger of the pass")

    monkeypatch.setattr(campaign.readiness, reader, boom)
    rc, _, err = cmd(root, capsys, "pilot", "pass", CID, "P1")
    assert rc == 1 and "HB-CMP-008" in err and f"readiness.{reader}" in err and f"{reader} cannot read the ledger of the pass" in err
    assert "pilot.passed" not in kinds_of(root) and stubs.pilot == []  # the gate was not evaluated


# --- C-26, C-27: admit ----------------------------------------------------------------------------------------------------

def test_admit_records_gates_admission_output_c26(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "powered")
    stubs.admission = lambda tasks: {"T1": (0, "saturated"), "T2": (1, "")}
    assert cmd(root, capsys, "admit", CID)[0] == 0
    rows = [r for r in rows_of(root) if r["kind"] == "admission.decided"]
    assert [(r["task"], r["admitted"], r["reason"]) for r in rows] == [("T1", 0, "saturated"), ("T2", 1, "")]
    assert all(type(r["admitted"]) is int for r in rows)


def test_admit_refuses_a_not_recorded_primary_and_writes_no_row_c26(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "powered")

    def refuse(tasks):
        raise campaign.BenchError("HB-USR-002", 'admission: task T1 cell c1 has no primary (not recorded). Rerun the pilot')

    stubs.admission = refuse
    rc, _, err = cmd(root, capsys, "admit", CID)
    assert rc == 1 and "HB-USR-002" in err and "admission.decided" not in kinds_of(root)


def test_admit_is_current_only_after_the_latest_pilot_pass_c27(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    before = ledger_path(root).read_bytes()
    rc, out, _ = cmd(root, capsys, "admit", CID)
    assert rc == 0 and out.startswith("no change:") and ledger_path(root).read_bytes() == before
    grade_pass(root, "P1", GID2, score="b")
    assert cmd(root, capsys, "pilot", "pass", CID, "P1", "--grading-id", GID2)[0] == 0  # a new pass, same decisions
    assert cmd(root, capsys, "admit", CID)[0] == 0
    assert kinds_of(root).count("admission.decided") == 4


# --- C-28..C-32, C-35: register -------------------------------------------------------------------------------------------

def test_register_preview_writes_nothing_and_prints_level_rule_and_warning_c28(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    before = snapshot(root)
    rc, out, _ = cmd(root, capsys, "register", CID, "--prereg", str(path))
    assert rc == 0 and snapshot(root) == before
    per_test, rule = power.level_for("bonferroni", Decimal("0.05"), 2)
    assert digest in out and f"alpha_per_test {per_test}" in out and rule in out
    assert "min_pairs" in out and "security" in out and "warning" in out.lower()  # 3 is below the required n


def test_register_confirm_writes_file_then_row_c29(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    before = snapshot(root)
    for bad in ("0" * 12, ""):
        rc, _, err = cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", bad)
        assert rc == 1 and "HB-CMP-008" in err and snapshot(root) == before, bad
    assert cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", digest[:12])[0] == 0
    file = cdir(root) / "prereg" / f"{digest}.json"
    assert file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == digest
    assert rows_of(root)[-1]["kind"] == "registered" and rows_of(root)[-1]["prereg_hash"] == digest
    path2, _ = stmt(root, "edited.json")  # edited between preview and confirm: the hash the operator saw is not this file's
    path2.write_text(path.read_text(encoding="utf-8").replace('"min_pairs": 3', '"min_pairs": 2'), encoding="utf-8")
    assert cmd(root, capsys, "register", CID, "--prereg", str(path2), "--confirm", digest[:12])[0] == 1
    assert kinds_of(root).count("registered") == 1


def break_heads(root):
    (root / "runs" / "P1" / "scores" / f"{GID}.jsonl").unlink()
    grade_pass(root, "P1", score="tampered", facts=("scores",))


def fix_after_power(root):
    effective = campaign.effective_identity(root, campaign.read(root, CID))["components"]
    key = "src/harness_bench/engine.py"
    campaign_append(root, "defect_fix.admitted", changes={key: [effective[key], "b" * 64]})


def campaign_append(root, kind, **fields):
    from test_cli_campaign import append

    append(root, kind, **fields)


C30_CASES = [
    ("question", {"question": "another question"}, None, "question"),
    ("mde", {"mde": {"security": "0.2"}}, None, "mde"),
    ("fix", {}, fix_after_power, "predate"),
    ("admission", {}, "skip-admit", "admission"),
    ("coverage", {"arms": {"ghost": {"commit": TREAT_COMMIT, "revision": "r1"}}}, None, "did not cover"),
    ("heads", {}, break_heads, "heads"),
    ("source", {"arms": {"treat": {"commit": TREAT_COMMIT, "revision": "r1", "source": "C:\\Users\\x\\ai-forward"}}}, None, "local path"),
]


@pytest.mark.parametrize(("label", "over", "setup", "phrase"), C30_CASES, ids=[c[0] for c in C30_CASES])
def test_register_refuses_each_unmet_precondition_c30_c32(tmp_path, capsys, stubs, label, over, setup, phrase):
    root = tree(tmp_path)
    ready(root, "powered" if setup == "skip-admit" else "admitted")
    if callable(setup):
        setup(root)
        if label == "fix":
            stubs.items = []
            assert cmd(root, capsys, "pilot", "pass", CID, "P1")[0] == 0  # piloted again
            assert cmd(root, capsys, "admit", CID)[0] == 0  # admit is current after the new pass; the final power is not
    path, digest = stmt(root, **over)
    before = ledger_path(root).read_bytes()
    rc, _, err = cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", digest[:12])
    assert rc == 1 and "HB-CMP-008" in err and phrase in err, err
    assert ledger_path(root).read_bytes() == before and not list((cdir(root) / "prereg").glob("*.json"))


def attach_row_plan(root, prereg_hash):
    write_plan(root, "R2", prereg_hash=prereg_hash, harness="claude-code", tasks=("T1", "T2"))


def test_register_with_another_hash_before_attach_appends_and_latest_wins_c31(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    hashes = []
    for count in (3, 4):
        path, digest = stmt(root, f"p{count}.json", min_pairs=count)
        assert cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", digest[:12])[0] == 0
        hashes.append(digest)
    assert [r["prereg_hash"] for r in rows_of(root) if r["kind"] == "registered"] == hashes
    assert campaign.read(root, CID).state == "registered" and len(list((cdir(root) / "prereg").glob("*.json"))) == 2


def test_register_is_refused_once_a_grid_is_attached_c35(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    assert cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", digest[:12])[0] == 0
    attach_row_plan(root, digest)
    assert cmd(root, capsys, "attach", CID, "R2")[0] == 0
    path2, digest2 = stmt(root, "p2.json", min_pairs=5)
    rc, _, err = cmd(root, capsys, "register", CID, "--prereg", str(path2), "--confirm", digest2[:12])
    assert rc == 1 and "HB-CMP-009" in err and "R2" in err and kinds_of(root).count("registered") == 1


def test_crash_between_file_and_row_recovers_for_register_c18(tmp_path, stubs, monkeypatch):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    real, fired = campaign._append, []

    def flaky(sess, kind, **fields):
        if kind == "registered" and not fired:
            fired.append(1)
            raise OSError("disk went away")
        return real(sess, kind, **fields)

    monkeypatch.setattr(campaign, "_append", flaky)
    assert isinstance(attempt(campaign.register, root, CID, path, digest[:12]), OSError)
    assert (cdir(root) / "prereg" / f"{digest}.json").is_file() and "registered" not in kinds_of(root)
    campaign.register(root, CID, path, digest[:12])
    assert kinds_of(root).count("registered") == 1 and len(list((cdir(root) / "prereg").glob("*.json"))) == 1


# --- C-33: the walk on the real CLI -----------------------------------------------------------------------------------------

def test_a_fix_in_registered_re_pilots_and_re_registers_c33(tmp_path, capsys, stubs):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    confirm = ["register", CID, "--prereg", str(path), "--confirm", digest[:12]]
    assert cmd(root, capsys, *confirm)[0] == 0 and campaign.read(root, CID).state == "registered"
    edit_src(root, "engine.py")
    commit_all(root, "fix engine")
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    assert cmd(root, capsys, "fix", CID, "--class", "MOD-A", "--commit", head, "--component", "src/harness_bench/engine.py")[0] == 0
    assert campaign.read(root, CID).state == "baselined"
    rc, _, err = cmd(root, capsys, *confirm)
    assert rc == 1 and "HB-CMP-002" in err  # state
    for argv in (["pilot", "attach", CID, "P1"], ["pilot", "pass", CID, "P1"], ["power", CID, "--inputs", str(power_file(root))], ["admit", CID]):
        assert cmd(root, capsys, *argv)[0] == 0, argv
    assert campaign.read(root, CID).state == "piloted"
    assert cmd(root, capsys, *confirm)[0] == 0
    assert campaign.read(root, CID).state == "registered" and kinds_of(root).count("registered") == 2


# --- C-47: the four new rows --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sub", ["pilot attach", "pilot pass", "admit", "register"])
def test_rerun_is_a_noop_c47(tmp_path, capsys, stubs, sub):
    root = tree(tmp_path)
    ready(root, {"pilot attach": "plan", "pilot pass": "attached", "admit": "powered", "register": "admitted"}[sub])
    argv = {"pilot attach": ["pilot", "attach", CID, "P1"], "pilot pass": ["pilot", "pass", CID, "P1"], "admit": ["admit", CID]}.get(sub)
    if argv is None:
        path, digest = stmt(root)
        argv = ["register", CID, "--prereg", str(path), "--confirm", digest[:12]]
    assert cmd(root, capsys, *argv)[0] == 0
    before = ledger_path(root).read_bytes()
    rc, out, _ = cmd(root, capsys, *argv)
    assert rc == 0 and out.startswith("no change:") and ledger_path(root).read_bytes() == before


# --- I-1, I-2: the freeze order, with real threads ------------------------------------------------------------------------------

def interleave(monkeypatch, winner, loser, winner_kind):
    """`winner` appends under the lock only after `loser` is waiting for it (hand-off on events, no wall time)."""
    held, waiting, real, errors = threading.Event(), threading.Event(), campaign._append, {}
    real_sleep = campaign.time.sleep

    def sleep(seconds):
        waiting.set()
        real_sleep(0.05)

    def gated(sess, kind, **fields):
        if kind == winner_kind:
            held.set()
            assert waiting.wait(30), "the loser never waited for the lock"
        return real(sess, kind, **fields)

    monkeypatch.setattr(campaign, "_append", gated)
    monkeypatch.setattr(campaign.time, "sleep", sleep)
    threads = [threading.Thread(target=lambda n=name, fn=fn: errors.__setitem__(n, attempt(fn))) for name, fn in (("winner", winner), ("loser", loser))]
    threads[0].start()
    assert held.wait(30), "the winner never reached its append"
    threads[1].start()
    for thread in threads:
        thread.join(60)
    return errors


def two_statements(root, capsys):
    ready(root, "admitted")
    x_path, x = stmt(root, "x.json", min_pairs=3)
    y_path, y = stmt(root, "y.json", min_pairs=4)
    assert cmd(root, capsys, "register", CID, "--prereg", str(x_path), "--confirm", x[:12])[0] == 0
    attach_row_plan(root, x)
    return x, (y_path, y)


def test_register_then_attach_interleaving_i1(tmp_path, capsys, stubs, monkeypatch):
    root = tree(tmp_path)
    _x, (y_path, y) = two_statements(root, capsys)
    errors = interleave(monkeypatch, lambda: campaign.register(root, CID, y_path, y[:12], wait_s=30),
                        lambda: campaign.attach(root, CID, "R2", wait_s=30), "registered")
    assert errors["winner"] is None and code_of(errors["loser"]) == "HB-CMP-010"
    assert rows_of(root)[-1]["prereg_hash"] == y and "grid.attached" not in kinds_of(root)


def test_attach_then_register_interleaving_i2(tmp_path, capsys, stubs, monkeypatch):
    root = tree(tmp_path)
    x, (y_path, y) = two_statements(root, capsys)
    errors = interleave(monkeypatch, lambda: campaign.attach(root, CID, "R2", wait_s=30),
                        lambda: campaign.register(root, CID, y_path, y[:12], wait_s=30), "grid.attached")
    assert errors["winner"] is None and code_of(errors["loser"]) == "HB-CMP-009"
    rows = rows_of(root)
    assert [r["prereg_hash"] for r in rows if r["kind"] == "registered"] == [x]
    assert rows[-1]["kind"] == "grid.attached" and rows[-1]["plan_hash"] == plan.load_confirmed(root / "runs" / "R2")["plan_hash"]


# --- L-11: every write goes through `session` ------------------------------------------------------------------------------------

def unsessioned_appends(source: str) -> list[str]:
    """Functions with a `_append(` call that is not inside a `with session(...)` block."""
    out = []
    for fn in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)):
        guarded = {id(c) for w in ast.walk(fn) if isinstance(w, ast.With) and any("session(" in ast.unparse(i.context_expr) for i in w.items)
                   for c in ast.walk(w)}
        out += [fn.name for c in ast.walk(fn) if isinstance(c, ast.Call) and ast.unparse(c.func) == "_append" and id(c) not in guarded]
    return out


def test_every_writing_command_goes_through_session_l11():
    assert unsessioned_appends("def rogue(root):\n    _append(None, 'concluded')\n") == ["rogue"]  # the red fixture
    source = (ROOT / "src" / "harness_bench" / "campaign.py").read_text(encoding="utf-8")
    assert unsessioned_appends(source) == []
    writers = {fn.name for fn in ast.walk(ast.parse(source)) if isinstance(fn, ast.FunctionDef)
               and any(isinstance(c, ast.Call) and ast.unparse(c.func) == "_append" for c in ast.walk(fn))}
    reached = {}
    for name, command in cli.CAMPAIGN_COMMANDS.items():
        called = {c.func.attr for c in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(command))))
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and ast.unparse(c.func.value) == "campaign"}
        reached[name] = called
    for name, called in reached.items():
        if name in ("status", "verify"):
            assert not called & writers, name  # reads never reach an appender
        else:
            assert called and called <= writers, (name, called - writers)
    assert writers == set().union(*(c for n, c in reached.items() if n not in ("status", "verify")))


# --- the content reader ---------------------------------------------------------------------------------------------------------

def test_content_reads_one_file_and_refuses_an_unreadable_or_unparseable_one_with_hb_cmp_003(tmp_path):
    root = tree(tmp_path)
    baselined(root, "T1")
    digest = rows_of(root)[-1]["identity_hash"]
    assert campaign.content(root, CID, "identity", digest).get("schema") == "bench-identity/1"
    junk = cdir(root) / "prereg" / ("c" * 64 + ".json")
    junk.parent.mkdir(exist_ok=True)
    junk.write_bytes(b"not json")
    for name in ("c" * 64, "d" * 64):  # unparseable, then absent
        err = attempt(campaign.content, root, CID, "prereg", name)
        assert code_of(err) == "HB-CMP-003" and f"{name}.json" in err.message
    assert code_of(attempt(campaign.content, root, CID, "elsewhere", digest)) is None  # not a campaign folder: a programming error, not a record fault


def test_both_inline_readers_go_through_content_and_the_register_row_reads_the_statement_through_it(tmp_path, capsys, stubs, monkeypatch):
    root = tree(tmp_path)
    ready(root, "admitted")
    path, digest = stmt(root)
    assert cmd(root, capsys, "register", CID, "--prereg", str(path), "--confirm", digest[:12])[0] == 0
    attach_row_plan(root, digest)
    calls, real = [], campaign.content
    monkeypatch.setattr(campaign, "content", lambda r, c, folder, d: calls.append(folder) or real(r, c, folder, d))
    campaign.effective_identity(root, campaign.read(root, CID))
    assert calls == ["identity"]
    assert cmd(root, capsys, "attach", CID, "R2")[0] == 0
    assert {"identity", "prereg"} <= set(calls)
