"""X-C1 proof: fold, rows, commands, names, eligibility (W1-C section 13: F, C, N, E; brief items 12, 25, 38, 40).

Each guard has a red fixture and a mutant in tests/mutations/campaign.json. Red on the skeleton by assertion.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest
from test_cli_campaign import (
    ARGV,
    CID,
    IDENT,
    PREREG,
    QUESTION,
    ROOT,
    attempt,
    baselined,
    bench,
    cdir,
    chain_identity,
    code_of,
    commit_all,
    created,
    defaults,
    edit_src,
    git,
    held_by_another_process,
    kinds,
    ledger_path,
    make_repo,
    power_file,
    put,
    raw_rows,
    register_row,
    registered,
    rows_of,
    set_freeze,
    snapshot,
    tree,
    walk_to,
    write_plan,
    write_text,
)
from test_cli_campaign import append as append_row

from harness_bench import campaign, cli, identity, ledger, plan, status

H64 = "0123456789abcdef" * 4


def findings_for(root, cid=CID):
    return [f for f in campaign.verify(root, cid) if f.level == "error"]


# --- F: fold, rows, state -----------------------------------------------------------------------------------------

WALK_EXPECTED = (("campaign.created", "draft"), ("baseline.recorded", "baselined"), ("pilot.passed", "piloted"),
                 ("registered", "registered"), ("grid.attached", "measuring"), ("concluded", "concluded"))


def test_fold_walks_the_transition_table_f1(tmp_path):
    root = make_repo(tmp_path)
    for kind, expected in WALK_EXPECTED:
        if kind == "campaign.created":
            cdir(root).mkdir(parents=True)
        elif kind == "baseline.recorded":
            put(root, IDENT, "identity")
        elif kind == "registered":
            put(root, PREREG, "prereg")
        append_row(root, kind)
        assert campaign.read(root, CID).state == expected, kind
    assert [r["kind"] for r in campaign.read(root, CID).rows] == [k for k, _ in WALK_EXPECTED]


F2_PREFIX = {
    "draft": [("campaign.created", {})],
    "baselined": [("campaign.created", {}), ("baseline.recorded", {})],
    "piloted": [("campaign.created", {}), ("baseline.recorded", {}), ("pilot.passed", {})],
    "registered": [("campaign.created", {}), ("baseline.recorded", {}), ("pilot.passed", {}), ("registered", {})],
    "concluded": [("campaign.created", {}), ("baseline.recorded", {}), ("pilot.passed", {}), ("registered", {}),
                  ("grid.attached", {}), ("concluded", {})],
    "none": [],
}
F2_CASES = [
    ("baseline first", "none", "baseline.recorded", "none"),
    ("grid in piloted", "piloted", "grid.attached", "piloted"),
    ("registered in baselined", "baselined", "registered", "baselined"),
    ("any kind after concluded", "concluded", "abandoned", "concluded"),
    ("admission in baselined", "baselined", "admission.decided", "baselined"),
    ("power final in baselined", "baselined", "power.recorded", "baselined"),
    ("second created", "draft", "campaign.created", "draft"),
    ("fix in draft", "draft", "defect_fix.admitted", "draft"),
    ("pilot passed in registered", "registered", "pilot.passed", "registered"),
]


@pytest.mark.parametrize(("label", "prefix", "kind", "state"), F2_CASES, ids=[c[0] for c in F2_CASES])
def test_illegal_row_for_its_state_is_hb_cmp_003_f2(tmp_path, label, prefix, kind, state):
    root = make_repo(tmp_path)
    fields = {"role": "final"} if label == "power final in baselined" else {}
    rows = [(k, defaults(k) | f) for k, f in F2_PREFIX[prefix]] + [(kind, defaults(kind) | fields)]
    raw_rows(root, rows)
    seq = len(rows)
    found = [f for f in findings_for(root) if f"seq {seq} kind {kind}" in f.detail]
    assert found, f"{label}: no finding names seq {seq} kind {kind}"
    assert found[0].code == "HB-CMP-003"
    assert f"state {state}" in found[0].detail


@pytest.mark.parametrize("start", ["piloted", "registered"])
def test_fix_demotes_piloted_and_registered_to_baselined_f3(tmp_path, start):
    root = make_repo(tmp_path)
    walk_to(root, start)
    assert campaign.read(root, CID).state == start
    append_row(root, "defect_fix.admitted")
    assert campaign.read(root, CID).state == "baselined"


def test_fix_in_measuring_keeps_measuring_and_a_new_attach_is_legal_f12(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "measuring")
    append_row(root, "defect_fix.admitted")
    assert campaign.read(root, CID).state == "measuring"
    append_row(root, "grid.attached", run_id="R3", plan_hash="s" * 64)
    state = campaign.read(root, CID)
    assert state.state == "measuring"
    assert [r["run_id"] for r in state.rows if r["kind"] == "grid.attached"] == ["R2", "R3"]


F6_BAD = {
    "a state field": ("campaign.created", {"question": "q", "state": "draft"}, None),
    "a missing field": ("baseline.recorded", {"identity_hash": H64}, "draft"),
    "a stale tag": ("ring_run.attached", {"ring_hash": H64, "run_id": "R1", "plan_hash": H64, "tag": "pilot"}, "baselined"),
    "a wrong type": ("admission.decided", {"task": "T1", "admitted": "1", "reason": "r"}, "piloted"),
    "an int where a str": ("registered", {"prereg_hash": 5}, "piloted"),
}


@pytest.mark.parametrize("label", list(F6_BAD))
def test_row_field_sets_are_closed_and_state_is_not_stored_f6(tmp_path, label):
    kind, fields, prefix = F6_BAD[label]
    root = make_repo(tmp_path)
    rows = [(k, defaults(k)) for k, _ in F2_PREFIX[prefix or "none"]]
    path = raw_rows(root, [*rows, (kind, fields)])
    assert path.exists()
    named = [f.detail for f in findings_for(root) if f"seq {len(rows) + 1} kind {kind}" in f.detail]
    assert named, label
    assert any("fields" in d or "type" in d for d in named), (label, named)
    # `_append` refuses the same row before it writes anything
    (tmp_path / "clean").mkdir()
    clean = make_repo(tmp_path / "clean")
    if prefix:
        walk_to(clean, prefix)
    else:
        cdir(clean).mkdir(parents=True)
    before = ledger_path(clean).read_bytes() if ledger_path(clean).exists() else b""
    err = attempt(lambda: campaign_append_raw(clean, kind, fields))
    assert code_of(err) == "HB-CMP-003", (label, err)
    assert (ledger_path(clean).read_bytes() if ledger_path(clean).exists() else b"") == before


def campaign_append_raw(root, kind, fields):
    with campaign.session(root, CID, create=kind == "campaign.created") as s:
        campaign._append(s, kind, **fields)


def test_admission_row_stores_int_and_a_bool_is_refused_before_canonical_f7(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    walk_to(root, "piloted")
    append_row(root, "admission.decided", admitted=1)
    assert b'"admitted":1' in ledger_path(root).read_bytes()
    before = ledger_path(root).read_bytes()
    real = ledger.canonical
    reached = []
    with campaign.session(root, CID) as s:
        monkeypatch.setattr(ledger, "canonical", lambda obj: (reached.append(obj), real(obj))[1])
        err = attempt(campaign._append, s, "admission.decided", task="T2", admitted=True, reason="r")
        monkeypatch.undo()
    assert code_of(err) == "HB-CMP-003"
    assert reached == []  # refused by `_append` itself, never by the canonical form beneath it
    assert ledger_path(root).read_bytes() == before


def test_a_ledger_copied_between_campaigns_fails_verify_f8(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined", cid="camp-a")
    cdir(root, "camp-b").mkdir(parents=True)
    (cdir(root, "camp-b") / "ledger.jsonl").write_bytes(ledger_path(root, "camp-a").read_bytes())
    found = findings_for(root, "camp-b")
    assert found
    assert any("campaign_id" in f.detail for f in found)


def test_a_tail_repaired_row_is_housekeeping_not_a_transition_f9(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    path = ledger_path(root)
    with path.open("ab") as handle:
        handle.write(b'{"kind":"pilot.pas')
    ledger.SegmentWriter.reopen(path).close()
    assert any(r["kind"] == ledger.TAIL_REPAIRED for r in ledger.read_segment(path))
    state = campaign.read(root, CID)
    assert state.state == "baselined"
    assert len(state.rows) == 2  # the earlier rows are still read; the repair row is not a campaign fact
    assert findings_for(root) == []


# --- the verify replay of a fix (W1-C section 7 step 3) -----------------------------------------------------------

def test_verify_replay_names_a_fix_whose_before_is_not_the_effective_value(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    raw_rows(root, [("defect_fix.admitted", defaults("defect_fix.admitted") | {
        "changes": {"src/harness_bench/engine.py": ["9" * 64, "b" * 64]}})])
    found = findings_for(root)
    assert any("before" in f.detail and "engine.py" in f.detail for f in found)


# --- C: commands ---------------------------------------------------------------------------------------------------

def test_create_writes_one_created_row_c1(tmp_path, capsys):
    root = make_repo(tmp_path)
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    assert ledger_path(root).exists()
    rows = ledger.read_segment(ledger_path(root))
    assert [(r["kind"], r["campaign_id"], r["question"]) for r in rows] == [("campaign.created", CID, QUESTION)]
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    assert "no change:" in capsys.readouterr().out
    assert len(ledger.read_segment(ledger_path(root))) == 1


def test_create_with_another_question_is_refused_c2(tmp_path, capsys):
    root = make_repo(tmp_path)
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    assert ledger_path(root).exists()
    before = ledger_path(root).read_bytes()
    assert bench(root, "campaign", "create", CID, "--question", "another") == 1
    assert "HB-CMP-002" in capsys.readouterr().err
    assert ledger_path(root).read_bytes() == before


@pytest.mark.parametrize("argv", [
    ["--", "-a"], ["A"], ["a" * 41], ["x_y"],
], ids=["leading-dash", "uppercase", "41-chars", "underscore"])
def test_a_malformed_id_is_refused_and_creates_nothing_c3(tmp_path, capsys, argv):
    root = make_repo(tmp_path)
    before = snapshot(root)
    assert bench(root, "campaign", "create", "--question", QUESTION, *argv) == 1
    assert "HB-USR-002" in capsys.readouterr().err
    assert snapshot(root) == before


@pytest.mark.parametrize("question", ["q" * 501, "bad\x07text"], ids=["501-chars", "control-char"])
def test_a_bad_question_is_refused_and_creates_nothing_c3(tmp_path, capsys, question):
    root = make_repo(tmp_path)
    before = snapshot(root)
    assert bench(root, "campaign", "create", CID, "--question", question) == 1
    assert "HB-USR-002" in capsys.readouterr().err
    assert snapshot(root) == before


@pytest.mark.parametrize("kind", ["abandoned", "admission.decided"])
@pytest.mark.parametrize("text", ["r" * 501, "tab\there"], ids=["501-chars", "control-char"])
def test_free_text_rows_are_bounded_by_append_c3(tmp_path, kind, text):
    root = make_repo(tmp_path)
    walk_to(root, "piloted")
    before = ledger_path(root).read_bytes()
    err = attempt(campaign_append_raw, root, kind, {**defaults(kind), "reason": text})
    assert code_of(err) == "HB-USR-002"
    assert ledger_path(root).read_bytes() == before


def test_every_id_the_grader_mints_fits_the_run_id_pattern_c3():
    """`status.RUN_ID` is the id pattern of runs, grading passes and tasks; the grader's mint is read from its source."""
    text = (ROOT / "src" / "harness_bench" / "grade" / "runner.py").read_text(encoding="utf-8")
    assert "f\"{views.GRADE_PREFIX}{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}-{secrets.token_hex(3)}\"" in text
    minted = "grade-20261004T101112-0a1b2c"
    assert re.fullmatch(status.RUN_ID, minted)
    assert campaign.validate_id("grading", minted) == minted
    assert code_of(attempt(campaign.validate_id, "grading", "../x")) == "HB-USR-002"


def test_verify_failure_exits_5_c38(tmp_path, capsys):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    path = ledger_path(root)
    path.write_bytes(path.read_bytes().replace(QUESTION.encode(), b"does the pack hexp", 1))
    capsys.readouterr()
    for sub in ("verify", "status"):
        assert bench(root, "campaign", sub, CID) == 5, sub
        assert "HB-CMP-003" in capsys.readouterr().err


# --- N: names and paths --------------------------------------------------------------------------------------------

N1_IDS = ["../../x", "..", "A", "a" * 41]


@pytest.mark.parametrize("sub", sorted(cli.CAMPAIGN_COMMANDS))
@pytest.mark.parametrize("bad", [*N1_IDS, "nope"])
def test_malformed_and_unknown_ids_create_nothing_n1(tmp_path, capsys, sub, bad):
    root = make_repo(tmp_path)
    if sub == "create" and bad == "nope":
        pytest.skip("`nope` is a valid new id: only create may create it")
    before = snapshot(root)
    assert bench(root, "campaign", sub, bad, *ARGV[sub]) == 1
    err = capsys.readouterr().err
    assert ("HB-CMP-005" if bad == "nope" else "HB-USR-002") in err
    assert snapshot(root) == before


def test_the_library_validates_the_id_again_at_session_and_read_n1(tmp_path):
    root = make_repo(tmp_path)
    before = snapshot(root)

    def enter(bad):
        with campaign.session(root, bad):
            pass

    for bad in N1_IDS:
        assert code_of(attempt(enter, bad)) == "HB-USR-002", bad
        assert code_of(attempt(campaign.read, root, bad)) == "HB-USR-002", bad
    assert code_of(attempt(enter, "nope")) == "HB-CMP-005"
    assert snapshot(root) == before


@pytest.mark.parametrize("reserved", ["con", "nul", "com1", "aux"])
def test_a_windows_device_name_is_refused_through_check_segment_and_creates_nothing(tmp_path, capsys, reserved):
    root = make_repo(tmp_path)
    before = snapshot(root)
    assert bench(root, "campaign", "create", reserved, "--question", QUESTION) == 1
    assert "HB-USR-002" in capsys.readouterr().err
    assert snapshot(root) == before
    assert code_of(attempt(campaign.validate_id, "campaign", reserved)) == "HB-USR-002"


# --- item 12: the deleted committed ledger -------------------------------------------------------------------------

def test_a_deleted_committed_ledger_is_hb_cmp_003(tmp_path, capsys):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    commit_all(root, "campaign")
    ledger_path(root).unlink()
    before = snapshot(root)
    capsys.readouterr()
    assert bench(root, "campaign", "verify", CID) == 5
    assert "HB-CMP-003" in capsys.readouterr().err
    assert bench(root, "campaign", "status", CID) == 5  # HB-CMP-003, never HB-CMP-005
    assert "HB-CMP-003" in capsys.readouterr().err
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 5
    assert "HB-CMP-003" in capsys.readouterr().err
    assert snapshot(root) == before  # create wrote nothing


# --- item 38: a merged ledger fails closed -------------------------------------------------------------------------

def test_a_merged_ledger_fails_closed(tmp_path, capsys):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    commit_all(root, "base")
    git(root, "checkout", "-q", "-b", "other")
    append_row(root, "abandoned", reason="side branch")
    commit_all(root, "side")
    git(root, "checkout", "-q", "main")
    append_row(root, "pilot.passed")
    commit_all(root, "main")
    git(root, "merge", "-q", "--no-edit", "-X", "ours", "other")
    assert git(root, "rev-list", "--merges", "-n", "1", "HEAD").stdout.strip(), "the fixture must hold a merge commit"
    capsys.readouterr()
    assert bench(root, "campaign", "verify", CID) == 5
    assert "HB-CMP-003" in capsys.readouterr().err
    before = snapshot(root)
    assert code_of(attempt(campaign_append_raw, root, "abandoned", {"reason": "after the merge"})) == "HB-CMP-003"
    assert snapshot(root) == before


# --- the compute readers over rows and files -----------------------------------------------------------------------

def test_effective_identity_applies_each_fix_up_to_the_given_seq(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    append_row(root, "defect_fix.admitted")  # seq 3: engine a -> b
    state = campaign.read(root, CID)
    engine = "src/harness_bench/engine.py"
    assert campaign.effective_identity(root, state)["components"].get(engine) == "b" * 64
    assert campaign.effective_identity(root, state, upto_seq=2)["components"].get(engine) == "a" * 64
    assert campaign.effective_identity(root, state)["components"].get("tasks/T1") == "d" * 64


def test_run_facts_reads_the_plan_and_the_grading_started_row(tmp_path):
    run_dir = tmp_path / "runs" / "R2"
    run_dir.mkdir(parents=True)
    body = {"run_id": "R2", "campaign": {"campaign_id": CID, "prereg_hash": PH, "identity": {"hash": "i" * 64}}, "ring": {"hash": "r" * 64}}
    body["plan_hash"] = plan.plan_hash(body)
    (run_dir / "plan.json").write_text(json.dumps(body), encoding="utf-8")
    gid = "grade-20261004T000000-abcdef"
    with ledger.SegmentWriter.create(run_dir / "events", gid) as writer:
        writer.append({"kind": "grading.started", "grading_id": gid, "grade_identity_hash": "g" * 64})
    assert campaign.run_facts(run_dir, gid) == campaign.RunFacts("R2", True, body["plan_hash"], CID, PH, "i" * 64, "r" * 64, "g" * 64)
    bare = tmp_path / "runs" / "R3"
    bare.mkdir()
    absent = campaign.run_facts(bare, gid)
    assert (absent.plan_present, absent.grade_identity_hash) == (False, "not recorded")


# --- E: eligibility (pure) -----------------------------------------------------------------------------------------

PH = defaults("registered")["prereg_hash"]
EFF0 = IDENT
RING = "ring-1"


def side_hash(manifest, which):
    return identity.identity_hash(identity.side(manifest, which))


def with_components(**changes):
    return {"schema": IDENT["schema"], "components": {**IDENT["components"], **changes}}


ENGINE_FIX = {"src/harness_bench/engine.py": ["a" * 64, "b" * 64]}
FORMAL_FIX = {"src/harness_bench/grade/formal.py": ["c" * 64, "g" * 64]}
EFF_RUN_FIXED = with_components(**{"src/harness_bench/engine.py": "b" * 64})
EFF_GRADE_FIXED = with_components(**{"src/harness_bench/grade/formal.py": "g" * 64})
EFF_BOTH_FIXED = with_components(**{"src/harness_bench/engine.py": "b" * 64, "src/harness_bench/grade/formal.py": "g" * 64})


def state_of(fix=None, scope="run", skew=False):
    specs = [("campaign.created", defaults("campaign.created")), ("baseline.recorded", defaults("baseline.recorded")),
             ("pilot.passed", defaults("pilot.passed")), ("registered", defaults("registered")),
             ("grid.attached", defaults("grid.attached"))]
    if fix is not None:
        specs.append(("defect_fix.admitted", defaults("defect_fix.admitted") | {"changes": fix, "scope": scope}))
    rows = []
    for i, (kind, fields) in enumerate(specs, 1):
        stamp = {"recorded_at": f"2026-10-04T00:{(59 - i) if skew else i:02d}:00.000Z", "mono_ns": (1000 - i) if skew else i}
        rows.append({"kind": kind, "campaign_id": CID, "seq": i, **stamp, **fields})
    return campaign.fold(rows, CID)


def facts(**over):
    base = campaign.RunFacts("R2", True, "q" * 64, CID, PH, side_hash(EFF0, "run"), RING, side_hash(EFF0, "grade"))
    return dataclasses.replace(base, **over)


def test_eligible_when_every_rule_holds_e1():
    result = campaign.eligibility(state_of(), EFF0, facts(), facts())
    assert result.eligible is True
    assert result.reasons == ()


E2_CASES = [
    ("rule 0 plan absent", {"plan_present": False}, None, "not recorded"),
    ("rule 1 other campaign", {"plan_campaign_id": "other"}, None, "names campaign"),
    ("rule 2 other prereg", {"plan_prereg_hash": "x" * 64}, None, "registered prereg"),
    ("rule 3 plan hash differs", {"plan_hash": "z" * 64}, None, "plan hash differs"),
    ("rule 3 not attached", {"run_id": "R9"}, None, "not attached"),
    ("rule 4 run identity", {"plan_run_identity_hash": "y" * 64}, None, "run identity"),
    ("rule 6 grade identity", {"grade_identity_hash": "n" * 64}, None, "grade identity"),
    ("rule 7 other ring", {"plan_ring_hash": "ring-2"}, None, "first grid run's ring"),
]


@pytest.mark.parametrize(("label", "over", "_", "fragment"), E2_CASES, ids=[c[0] for c in E2_CASES])
def test_each_rule_adds_its_reason_e2(label, over, _, fragment):
    first = facts() if "ring" in label else facts(**over)
    result = campaign.eligibility(state_of(), EFF0, facts(**over), first)
    assert result.eligible is False, label
    assert len(result.reasons) == 1, (label, result.reasons)
    assert fragment in result.reasons[0], (label, result.reasons)


def test_reasons_come_in_the_fixed_rule_order_e2():
    over = {"plan_campaign_id": "other", "plan_prereg_hash": "x" * 64, "plan_hash": "z" * 64, "plan_run_identity_hash": "y" * 64,
            "grade_identity_hash": "n" * 64, "plan_ring_hash": "ring-2"}
    reasons = campaign.eligibility(state_of(), EFF0, facts(**over), facts()).reasons
    fragments = ["names campaign", "registered prereg", "plan hash differs", "run identity", "grade identity", "first grid run's ring"]
    places = [next((i for i, r in enumerate(reasons) if f in r), None) for f in fragments]
    assert None not in places, reasons
    assert places == sorted(places)


def test_grade_side_is_compared_with_the_current_effective_not_the_baseline_e3():
    state = state_of(FORMAL_FIX, scope="grade")
    under_baseline = campaign.eligibility(state, EFF_GRADE_FIXED, facts(), facts())
    assert under_baseline.eligible is False
    assert [("grade identity" in r) for r in under_baseline.reasons] == [True]
    under_current = campaign.eligibility(state, EFF_GRADE_FIXED, facts(grade_identity_hash=side_hash(EFF_GRADE_FIXED, "grade")), facts())
    assert under_current.eligible is True


@pytest.mark.parametrize(("scope", "fix", "eff_now", "run_side_reason"), [
    ("run", ENGINE_FIX, EFF_RUN_FIXED, True),
    ("both", ENGINE_FIX | FORMAL_FIX, EFF_BOTH_FIXED, True),
    ("grade", FORMAL_FIX, EFF_GRADE_FIXED, False),
], ids=["run", "both", "grade"])
def test_run_side_fix_after_attach_makes_the_run_ineligible_grade_fix_does_not_e4(scope, fix, eff_now, run_side_reason):
    result = campaign.eligibility(state_of(fix, scope=scope), eff_now, facts(grade_identity_hash=side_hash(eff_now, "grade")), facts())
    assert any("run-side fix" in r for r in result.reasons) is run_side_reason
    assert result.eligible is (not run_side_reason)


def test_ordering_uses_seq_not_clocks_e5():
    straight = campaign.eligibility(state_of(ENGINE_FIX, skew=False), EFF_RUN_FIXED, facts(), facts())
    skewed = campaign.eligibility(state_of(ENGINE_FIX, skew=True), EFF_RUN_FIXED, facts(), facts())
    assert any("run-side fix" in r for r in straight.reasons)
    assert skewed == straight



# === C2a: baseline, fix, power, attach, conclude, abandon (W1-C section 13: C-4..C-15, C-17..C-19, C-36, C-37, C-41..C-44, C-47, C-49, C-50) ===

def head(root):
    return git(root, "rev-parse", "HEAD").stdout.strip()


def err_of(capsys):
    return capsys.readouterr().err


def test_baseline_records_identity_file_and_row_c4(tmp_path):
    root = tree(tmp_path)
    created(root)
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1,T2") == 0
    rows = [r for r in rows_of(root) if r["kind"] == "baseline.recorded"]
    files = sorted((cdir(root) / "identity").glob("*.json"))
    assert len(rows) == 1 and len(files) == 1
    assert files[0].stem == hashlib.sha256(files[0].read_bytes()).hexdigest()  # computed with hashlib, never with identity_hash
    assert rows[0]["identity_hash"] == files[0].stem
    assert rows[0]["bench_commit"] == head(root)
    components = json.loads(files[0].read_bytes())["components"]
    assert sorted(k for k in components if k.startswith("tasks/")) == ["tasks/T1", "tasks/T2"]
    assert campaign.read(root, CID).state == "baselined"


def test_baseline_without_tasks_takes_the_bom_tasks_that_carry_a_property_c4(tmp_path):
    root = tree(tmp_path)
    assert campaign.default_tasks(root) == ["T1", "T2"]
    write_text(root / "tasks" / "T2" / "task.yaml", "schema: bench-task/1\nid: T2\nstatus: ready\n")  # no property block
    assert campaign.default_tasks(root) == ["T1"]


UNMET = {
    "modified": (lambda root: edit_src(root, "engine.py"), "src/harness_bench/engine.py"),
    "untracked": (lambda root: edit_src(root, "extra.py", "x = 1\n"), "src/harness_bench/extra.py"),
}


@pytest.mark.parametrize("case", sorted(UNMET))
def test_baseline_refuses_a_dirty_component_c5(tmp_path, capsys, case):
    root = tree(tmp_path)
    created(root)
    mutate, name = UNMET[case]
    mutate(root)
    assert any(name in item for item in campaign.baseline_unmet(root, ["T1"]))
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1") == 1
    err = err_of(capsys)
    assert "HB-CMP-006" in err and name in err
    assert kinds(root) == ["campaign.created"]


def test_baseline_refuses_a_task_not_ready_c6(tmp_path, capsys):
    root = tree(tmp_path)
    created(root)
    write_text(root / "tasks" / "T2" / "task.yaml", "schema: bench-task/1\nid: T2\nstatus: stub\n")
    commit_all(root, "stub")
    assert any('task "T2"' in item for item in campaign.baseline_unmet(root, ["T1", "T2"]))
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1,T2") == 1
    err = err_of(capsys)
    assert "HB-CMP-006" in err and "T2" in err
    assert kinds(root) == ["campaign.created"]


@pytest.mark.parametrize("freeze", ["absent", "other-hash"])
def test_baseline_refuses_unfrozen_catalog_c7(tmp_path, capsys, freeze):
    root = tree(tmp_path)
    created(root)
    set_freeze(root, None if freeze == "absent" else "f" * 64)
    commit_all(root, "freeze")
    assert any("catalog 0.7" in item for item in campaign.baseline_unmet(root, ["T1"]))
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1") == 1
    assert "HB-CMP-006" in err_of(capsys)


def test_baseline_refuses_unaccepted_spike_c8(tmp_path, capsys):
    root = tree(tmp_path)
    created(root)
    write_text(root / "docs" / "notes" / "spike-e4-post-turn-prompt.md", "---\nstatus: draft\n---\nbody\n")
    commit_all(root, "spike")
    assert any("spike E4" in item for item in campaign.baseline_unmet(root, ["T1"]))
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1") == 1
    assert "HB-CMP-006" in err_of(capsys)


ENGINE = "src/harness_bench/engine.py"
FORMAL = "src/harness_bench/grade/formal.py"


def fix_argv(root, *components, cls="MOD-A", commit=None):
    args = ["campaign", "fix", CID, "--class", cls, "--commit", commit or head(root)]
    for name in components:
        args += ["--component", name]
    return args


def test_baseline_after_a_tree_change_is_refused_and_after_a_fix_is_a_noop_c9(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    edit_src(root, "engine.py")
    commit_all(root, "engine edit")
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1") == 1
    err = err_of(capsys)
    assert "HB-CMP-006" in err and "engine.py" in err
    assert bench(root, *fix_argv(root, ENGINE)) == 0
    before = ledger_path(root).read_bytes()
    capsys.readouterr()
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1") == 0
    assert capsys.readouterr().out.startswith("no change:")
    assert ledger_path(root).read_bytes() == before


def test_fix_roundtrip_effective_identity_equals_tree_c10(tmp_path):
    root = tree(tmp_path)
    baselined(root, "T1", "T2")
    for name in ("engine.py", "grade/formal.py"):
        edit_src(root, name)
        commit_all(root, f"edit {name}")
        assert bench(root, *fix_argv(root, f"src/harness_bench/{name}")) == 0
    state = campaign.read(root, CID)
    assert campaign.effective_identity(root, state) == identity.manifest(root, ["T1", "T2"])
    assert [r["defect_class"] for r in state.rows if r["kind"] == "defect_fix.admitted"] == ["MOD-A", "MOD-A"]


@pytest.mark.parametrize(("cls", "code"), [("ZZZ-Z", "HB-CMP-007"), (".*", "HB-USR-002"), ("(", "HB-USR-002"),
                                           ("mod-a", "HB-USR-002"), ("MOD-B", "HB-CMP-007")])
def test_fix_refuses_an_unknown_or_malformed_defect_class_c11(tmp_path, capsys, cls, code):
    root = tree(tmp_path)
    baselined(root)
    edit_src(root, "engine.py")
    commit_all(root, "engine edit")
    capsys.readouterr()
    assert bench(root, *fix_argv(root, ENGINE, cls=cls)) == 1
    assert code in err_of(capsys)  # MOD-B is named only inside prose: the heading regex, not a substring, decides
    assert kinds(root) == ["campaign.created", "baseline.recorded"]


def test_fix_refuses_a_commit_not_an_ancestor_c12(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    git(root, "checkout", "-q", "-b", "side")
    edit_src(root, "engine.py", "side edit\n")
    commit_all(root, "side")
    side = head(root)
    git(root, "checkout", "-q", "main")
    edit_src(root, "engine.py", "main edit\n")
    commit_all(root, "main")
    capsys.readouterr()
    assert bench(root, *fix_argv(root, ENGINE, commit=side)) == 1
    err = err_of(capsys)
    assert "HB-CMP-007" in err and "ancestor" in err


def test_fix_names_exactly_the_differing_components_c13(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    edit_src(root, "engine.py")
    commit_all(root, "engine edit")
    capsys.readouterr()
    assert bench(root, *fix_argv(root, FORMAL)) == 1  # one edit, the wrong one named
    assert "changed and no fix names it" in err_of(capsys)
    assert bench(root, *fix_argv(root, ENGINE, FORMAL)) == 1  # one edit, one named plus one unchanged
    assert "named but unchanged" in err_of(capsys)
    assert kinds(root) == ["campaign.created", "baseline.recorded"]


def test_check_fix_refuses_a_wrong_before_hash_c14():
    effective = {"components": {ENGINE: "a" * 64}}
    assert code_of(attempt(campaign.check_fix, effective, {ENGINE: ["b" * 64, "c" * 64]})) == "HB-CMP-007"
    assert attempt(campaign.check_fix, effective, {ENGINE: ["a" * 64, "c" * 64]}) is None


@pytest.mark.parametrize(("edits", "scope"), [(("engine.py",), "run"), (("grade/formal.py",), "grade"), (("engine.py", "grade/formal.py"), "both")],
                         ids=["run", "grade", "both"])
def test_fix_scope_is_computed_never_accepted_c15(tmp_path, capsys, edits, scope):
    root = tree(tmp_path)
    baselined(root)
    for name in edits:
        edit_src(root, name)
    commit_all(root, "edits")
    assert bench(root, *fix_argv(root, *[f"src/harness_bench/{n}" for n in edits])) == 0
    assert [r["scope"] for r in rows_of(root) if r["kind"] == "defect_fix.admitted"] == [scope]
    capsys.readouterr()
    assert bench(root, *fix_argv(root, ENGINE), "--scope", "grade") == 2  # the parser has no --scope


def test_fix_refuses_a_component_unequal_to_its_commit_c50(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    before_edit = head(root)
    edit_src(root, "engine.py")  # uncommitted: the tree does not hold what any commit holds
    capsys.readouterr()
    assert bench(root, *fix_argv(root, ENGINE, commit=before_edit)) == 1
    assert "HB-CMP-007" in err_of(capsys)
    commit_all(root, "engine edit")  # committed, but the named commit is the one before it
    assert bench(root, *fix_argv(root, ENGINE, commit=before_edit)) == 1
    err = err_of(capsys)
    assert "HB-CMP-007" in err and "commit" in err
    assert "defect_fix.admitted" not in kinds(root)


def power_rows(root):
    return [(r["role"], r["input_hash"]) for r in rows_of(root) if r["kind"] == "power.recorded"]


def test_power_role_comes_from_state_c17(tmp_path):
    root = tree(tmp_path)
    baselined(root)
    inputs = power_file(root)
    digest = hashlib.sha256(ledger.canonical({**json.loads(inputs.read_bytes()), "schema": "bench-power-inputs/1"})).hexdigest()
    assert bench(root, "campaign", "power", CID, "--inputs", str(inputs)) == 0
    assert power_rows(root) == [("prior", digest)]
    assert (cdir(root) / "power" / f"{digest}.json").is_file()
    append_row(root, "pilot.passed")  # piloted: the same command writes role final
    other = power_file(root, "other.json", properties={"security": {"mde": "0.25", "tasks": ["T1", "T2"]}})
    assert bench(root, "campaign", "power", CID, "--inputs", str(other)) == 0
    assert [role for role, _ in power_rows(root)] == ["prior", "final"]


def test_a_final_power_then_a_re_registration_then_attach_succeeds_and_a_late_final_power_is_hb_cmp_009_item_31(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    append_row(root, "pilot.passed")
    assert bench(root, "campaign", "power", CID, "--inputs", str(power_file(root))) == 0
    digest = register_row(root)
    write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    assert campaign.read(root, CID).state == "measuring"
    capsys.readouterr()
    assert bench(root, "campaign", "power", CID, "--inputs", str(power_file(root, "late.json", slots=3))) == 1
    assert "HB-CMP-009" in err_of(capsys)


def test_attach_is_refused_after_a_final_power_that_postdates_the_registration_item_31(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    digest = registered(root)
    write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "power", CID, "--inputs", str(power_file(root))) == 0  # final, in `registered`, after the registration
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-002" in err and "re-register after the latest final power" in err
    assert "grid.attached" not in kinds(root)


def test_power_float_or_invalid_inputs_refused_c19(tmp_path, capsys):
    root = tree(tmp_path)
    baselined(root)
    path = root / "float.json"
    path.write_text('{"alpha": 0.05}', encoding="utf-8")
    before = snapshot(cdir(root))
    capsys.readouterr()
    assert bench(root, "campaign", "power", CID, "--inputs", str(path)) == 1
    err = err_of(capsys)
    assert "HB-PWR-001" in err and "alpha" in err
    bad = root / "bad.json"
    bad.write_text(json.dumps({"alpha": "2", "power": "0.8"}), encoding="utf-8")
    assert bench(root, "campaign", "power", CID, "--inputs", str(bad)) == 1
    assert "HB-PWR-001" in err_of(capsys)
    assert snapshot(cdir(root)) == before


def test_a_crash_between_the_power_file_and_its_row_recovers_c18(tmp_path, monkeypatch):
    root = tree(tmp_path)
    baselined(root)
    inputs = power_file(root)
    real, calls = campaign._append, []

    def flaky(sess, kind, **fields):
        if kind == "power.recorded" and not calls:
            calls.append(1)
            raise RuntimeError("forced crash after the content file")
        return real(sess, kind, **fields)

    monkeypatch.setattr(campaign, "_append", flaky)
    assert isinstance(attempt(bench, root, "campaign", "power", CID, "--inputs", str(inputs)), RuntimeError)
    assert len(list((cdir(root) / "power").glob("*.json"))) == 1 and power_rows(root) == []
    assert bench(root, "campaign", "power", CID, "--inputs", str(inputs)) == 0
    assert len(list((cdir(root) / "power").glob("*.json"))) == 1 and len(power_rows(root)) == 1


# --- attach and check_plan (C-36, C-37, C-41, C-49, items 10, 28, 29, 43) ----------------------------------------------

def to_registered(root):
    baselined(root, "T1", "T2")
    return registered(root)


def wrong_components(root):
    ident = chain_identity(root)
    return {"hash": ident["hash"], "components": {**ident["components"], ENGINE: "9" * 64}}  # the right hash over forged components


def consistent_but_not_the_chain(root):
    ident = chain_identity(root)
    components = {**ident["components"], ENGINE: "9" * 64}
    return {"hash": identity.identity_hash({"schema": identity.SCHEMA, "components": components}), "components": components}


def launched_run(root, doc):
    write_text(root / "runs" / doc["run_id"] / "events" / "engine-1.jsonl", '{"kind":"cell.launch_intent"}\n')


ATTACH_CASES = {
    "other-campaign": (lambda root: {"cid": "other-camp"}, "belongs to campaign"),
    "prereg-hash": (lambda root: {"prereg_hash": "0" * 64}, "prereg_hash"),
    "identity-vs-chain": (lambda root: {"ident": consistent_but_not_the_chain(root)}, "effective run-side identity"),
    "forged-components": (lambda root: {"ident": wrong_components(root)}, "do not hash"),
    "arm-commit": (lambda root: {"commit": "b" * 40}, "pre-registered"),
    "launched-run": (lambda root: {}, "already launched"),
}


@pytest.mark.parametrize("case", list(ATTACH_CASES))
def test_attach_refuses_each_plan_mismatch_c36(tmp_path, capsys, case):
    root = tree(tmp_path)
    digest = to_registered(root)
    build, needle = ATTACH_CASES[case]
    doc = write_plan(root, "R2", **{"prereg_hash": digest, **build(root)})
    if case == "launched-run":
        launched_run(root, doc)
    before = ledger_path(root).read_bytes()
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-010" in err and needle in err
    assert ledger_path(root).read_bytes() == before


def test_attach_of_a_matching_plan_writes_the_grid_row_with_the_plans_own_hash_item_28(tmp_path):
    root = tree(tmp_path)
    digest = to_registered(root)
    doc = write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    row = rows_of(root)[-1]
    assert row["kind"] == "grid.attached"
    assert (row["run_id"], row["plan_hash"]) == ("R2", doc["plan_hash"])
    assert campaign.read(root, CID).state == "measuring"


def test_attach_identity_check_compares_with_the_chain_not_the_tree_c37(tmp_path, capsys):
    root = tree(tmp_path)
    digest = to_registered(root)
    edit_src(root, "engine.py")  # the tree drifts after the fix-free baseline; the plan is stamped from the tree
    tree_run = identity.side(identity.manifest(root, ["T1", "T2"]), "run")
    stamp = {"hash": identity.identity_hash(tree_run), "components": tree_run["components"]}
    write_plan(root, "R2", prereg_hash=digest, ident=stamp)
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-010" in err and "effective run-side identity" in err


def test_attach_of_a_pilot_plan_as_a_grid_is_refused_c41(tmp_path, capsys):
    root = tree(tmp_path)
    to_registered(root)
    write_plan(root, "R2", prereg_hash=None)
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-010" in err and "prereg_hash" in err


def test_attach_refuses_a_chain_stamped_plan_over_a_drifted_tree_and_takes_a_subset_plan_c49(tmp_path, capsys):
    root = tree(tmp_path)
    digest = to_registered(root)
    write_plan(root, "R2", prereg_hash=digest)  # stamped with the chain's identity
    edit_src(root, "engine.py")  # then the tree drifts
    before = ledger_path(root).read_bytes()
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-010" in err and "engine.py" in err and "working tree" in err
    assert ledger_path(root).read_bytes() == before
    write_text(root / "src" / "harness_bench" / "engine.py", "original\n")  # restored: a plan over T1 only, a subset of the baseline's two tasks
    write_plan(root, "R3", prereg_hash=digest, tasks=("T1",))
    assert bench(root, "campaign", "attach", CID, "R3") == 0
    assert kinds(root)[-1] == "grid.attached"


PLAN_KINDS = {"discrimination": ({"kind": "discrimination"}, "discrimination"), "unknown": ({"kind": "foo"}, "foo"),
              "synthetic": ({"harness": "synthetic"}, "synthetic")}


@pytest.mark.parametrize("case", list(PLAN_KINDS))
def test_attach_and_the_run_side_check_refuse_a_non_measurement_plan_item_29(tmp_path, capsys, case):
    root = tree(tmp_path)
    digest = to_registered(root)
    options, needle = PLAN_KINDS[case]
    doc = write_plan(root, "R2", prereg_hash=digest, **options)
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "R2") == 1
    err = err_of(capsys)
    assert "HB-CMP-010" in err and needle in err
    exc = attempt(campaign.run_side_check, root, doc, "R2")
    assert code_of(exc) == "HB-CMP-010" and needle in str(exc)


PLAN_ROW_BASES = {"plan_doc", "doc", "p", "plan"}


def plan_kind_reads(source: str) -> list[int]:
    """Lines that read `["kind"]` or `.get("kind")` off a name that holds a plan (a ledger row's own `kind` is not one)."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in PLAN_ROW_BASES
                and isinstance(node.slice, ast.Constant) and node.slice.value == "kind"):
            hits.append(node.lineno)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name) and node.func.value.id in PLAN_ROW_BASES
                and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "kind"):
            hits.append(node.lineno)
    return hits


def test_the_plan_kind_is_read_only_through_kind_of_item_43():
    assert plan_kind_reads('def f(plan_doc):\n    return plan_doc.get("kind")\n') == [2]  # the red fixtures
    assert plan_kind_reads('def f(doc):\n    return doc["kind"]\n') == [2]
    src = ROOT / "src" / "harness_bench"
    campaign_text = (src / "campaign.py").read_text(encoding="utf-8")
    assert plan_kind_reads(campaign_text) == []
    cli_text = (src / "cli.py").read_text(encoding="utf-8")
    assert plan_kind_reads(cli_text[cli_text.index("def cmd_campaign_create"): cli_text.index("def _plain")]) == []
    assert "kind_of(" in campaign_text


def test_a_plan_edited_after_attach_is_refused_at_run_time_and_the_check_opens_nothing_under_the_run_p6(tmp_path, monkeypatch):
    root = tree(tmp_path)
    digest = to_registered(root)
    doc = write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    assert campaign.run_side_check(root, doc, "R2") is None  # the attached plan passes
    edited = write_plan(root, "R2", prereg_hash=digest, tasks=("T1", "T2"))  # plan_hash recomputed over the edit
    exc = attempt(campaign.run_side_check, root, edited, "R2")
    assert code_of(exc) == "HB-CMP-010" and "R2" in str(exc)

    def guarded(real):
        def check(self, *args, **kwargs):
            assert "runs" not in self.parts, f"run_side_check opened {self}"
            return real(self, *args, **kwargs)
        return check

    for name in ("read_bytes", "read_text", "open"):
        monkeypatch.setattr(Path, name, guarded(getattr(Path, name)))
    assert campaign.run_side_check(root, doc, "R2") is None  # the dict the engine parsed, no second read


def test_the_run_side_check_refuses_an_unattached_run_and_a_finished_campaign_item_14(tmp_path):
    root = tree(tmp_path)
    digest = to_registered(root)
    doc = write_plan(root, "R2", prereg_hash=digest)
    assert code_of(attempt(campaign.run_side_check, root, doc, "R2")) == "HB-CMP-010"  # nothing attached yet
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    assert attempt(campaign.run_side_check, root, doc, "R2") is None
    assert bench(root, "campaign", "conclude", CID) == 0
    assert code_of(attempt(campaign.run_side_check, root, doc, "R2")) == "HB-CMP-002"
    plain = {key: value for key, value in doc.items() if key != "campaign"}
    assert attempt(campaign.run_side_check, root, plain, "R9") is None  # a plan with no campaign block is not this check's business


def test_the_run_side_check_refuses_while_the_campaign_lock_is_held_l9(tmp_path):
    root = tree(tmp_path)
    digest = to_registered(root)
    doc = write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    with held_by_another_process(campaign.lock_path(root, CID)):
        assert code_of(attempt(campaign.run_side_check, root, doc, "R2")) == "HB-CMP-001"
    assert attempt(campaign.run_side_check, root, doc, "R2") is None


# --- conclude and abandon (C-42, C-43, C-44) -----------------------------------------------------------------------------

def measuring(root):
    digest = to_registered(root)
    write_plan(root, "R2", prereg_hash=digest)
    assert bench(root, "campaign", "attach", CID, "R2") == 0


@pytest.mark.parametrize("sub", ["conclude", "abandon"])
def test_conclude_and_abandon_refuse_a_live_run_c42(tmp_path, capsys, sub):
    root = tree(tmp_path)
    measuring(root)
    extra = ["--reason", "x"] if sub == "abandon" else []
    before = snapshot(root)
    with held_by_another_process(root / "runs" / "R2" / ".lock"):
        capsys.readouterr()
        assert bench(root, "campaign", sub, CID, *extra) == 1
        err = err_of(capsys)
    assert "HB-CMP-004" in err and ".lock" in err and "R2" in err
    assert snapshot(root) == before
    assert not campaign.oslock.is_held(campaign.lock_path(root, CID))


def test_conclude_only_from_measuring_and_a_repeat_is_a_noop_c43(tmp_path, capsys):
    root = tree(tmp_path)
    to_registered(root)
    capsys.readouterr()
    assert bench(root, "campaign", "conclude", CID) == 1
    assert "HB-CMP-002" in err_of(capsys)
    root2 = tree(tmp_path, "second")
    measuring(root2)
    assert bench(root2, "campaign", "conclude", CID) == 0
    assert campaign.read(root2, CID).state == "concluded"
    capsys.readouterr()
    assert bench(root2, "campaign", "conclude", CID) == 0
    assert capsys.readouterr().out.startswith("no change:")


def test_abandon_other_reason_and_terminal_states_refused_c44(tmp_path, capsys):
    root = tree(tmp_path)
    created(root)
    assert bench(root, "campaign", "abandon", CID, "--reason", "no longer needed") == 0
    assert campaign.read(root, CID).state == "abandoned"
    capsys.readouterr()
    assert bench(root, "campaign", "abandon", CID, "--reason", "no longer needed") == 0
    assert capsys.readouterr().out.startswith("no change:")
    assert bench(root, "campaign", "abandon", CID, "--reason", "another reason") == 1
    assert "HB-CMP-002" in err_of(capsys)
    root2 = tree(tmp_path, "second")
    measuring(root2)
    assert bench(root2, "campaign", "conclude", CID) == 0
    capsys.readouterr()
    assert bench(root2, "campaign", "abandon", CID, "--reason", "late") == 1
    err = err_of(capsys)
    assert "HB-CMP-002" in err and "concluded" in err


RERUNS = ["baseline", "fix", "power", "attach", "conclude", "abandon"]


def rerun_fixture(sub, root):
    """The command's argv, after the setup that lets it succeed once."""
    if sub == "baseline":
        created(root)
        return ["campaign", "baseline", CID, "--tasks", "T1"]
    baselined(root)
    if sub == "fix":
        edit_src(root, "engine.py")
        commit_all(root, "edit")
        return fix_argv(root, ENGINE)
    if sub == "power":
        return ["campaign", "power", CID, "--inputs", str(power_file(root))]
    digest = registered(root)
    if sub == "abandon":
        return ["campaign", "abandon", CID, "--reason", "done"]
    write_plan(root, "R2", prereg_hash=digest)
    if sub == "attach":
        return ["campaign", "attach", CID, "R2"]
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    return ["campaign", "conclude", CID]


@pytest.mark.parametrize("sub", RERUNS)
def test_rerun_is_a_noop_c47(tmp_path, capsys, sub):
    root = tree(tmp_path)
    argv = rerun_fixture(sub, root)
    assert bench(root, *argv) == 0
    before = ledger_path(root).read_bytes()
    capsys.readouterr()
    assert bench(root, *argv) == 0
    assert capsys.readouterr().out.startswith("no change:")
    assert ledger_path(root).read_bytes() == before
