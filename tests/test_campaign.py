"""X-C1 proof: fold, rows, commands, names, eligibility (W1-C section 13: F, C, N, E; brief items 12, 25, 38, 40).

Each guard has a red fixture and a mutant in tests/mutations/campaign.json. Red on the skeleton by assertion.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from test_cli_campaign import (
    ARGV,
    CID,
    IDENT,
    PREREG,
    QUESTION,
    ROOT,
    attempt,
    bench,
    cdir,
    code_of,
    commit_all,
    defaults,
    git,
    ledger_path,
    make_repo,
    put,
    raw_rows,
    snapshot,
    walk_to,
)
from test_cli_campaign import append as append_row

from harness_bench import campaign, cli, identity, ledger, status

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


def test_admission_row_stores_int_and_a_bool_is_refused_f7(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "piloted")
    append_row(root, "admission.decided", admitted=1)
    assert b'"admitted":1' in ledger_path(root).read_bytes()
    before = ledger_path(root).read_bytes()
    err = attempt(campaign_append_raw, root, "admission.decided", {"task": "T2", "admitted": True, "reason": "r"})
    assert code_of(err) == "HB-CMP-003"
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

