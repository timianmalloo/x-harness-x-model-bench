"""X-C3b proof, the library half: the after-grading read, the status document (B-1..B-3), telemetry (T-1, T-2), the guard matrix
(C-45, C-46) and the one missing C-47 row. Helpers come from `test_cli_campaign.py` (the one home).

Expected values are typed here, never computed with the function under test (RV-TA 1).
"""

from __future__ import annotations

import json
import re

import pytest
from archived_runs import GOOD, make_root, make_run
from test_campaign_register import stmt
from test_cli_campaign import (
    ARGV,
    CID,
    QUESTION,
    STATES,
    append,
    attempt,
    bench,
    cli_rc,
    code_of,
    held_by_another_process,
    kinds,
    ledger_path,
    snapshot,
    tree,
    walk_to,
)

from harness_bench import campaign, oslock, plan
from harness_bench.grade import runner

# --- verify_for_plan and the after-grading hook (items 15 and 37) -------------------------------------------------------------


def campaign_doc(cid: str = CID) -> dict:
    return {"campaign": {"campaign_id": cid, "prereg_hash": None, "identity": {"hash": "h" * 64, "components": {}}}}


def test_verify_for_plan_says_ok_with_the_row_count_and_holds_no_lock(tmp_path, monkeypatch):
    root = tree(tmp_path)
    walk_to(root, "baselined")

    def never(*a, **k):
        raise AssertionError("verify_for_plan took a lock")

    monkeypatch.setattr(oslock.RunLock, "acquire", never)
    before = snapshot(root)
    assert campaign.verify_for_plan(root, campaign_doc()) == "campaign verify: ok (2 rows)"
    assert snapshot(root) == before


def test_verify_for_plan_ignores_a_sibling_attached_runs_grade_lock(tmp_path):
    root = tree(tmp_path)
    walk_to(root, "baselined")
    with held_by_another_process(root / "runs" / "R9" / "grade.lock"):
        assert campaign.verify_for_plan(root, campaign_doc()) == "campaign verify: ok (2 rows)"


def test_verify_for_plan_of_an_unknown_campaign_is_not_run_hb_cmp_005(tmp_path):
    root = tree(tmp_path)
    assert campaign.verify_for_plan(root, campaign_doc("nope")) == "campaign verify: not run (HB-CMP-005)"
    assert not (root / "bench" / "campaigns" / "nope").exists()


def test_verify_for_plan_raises_hb_cmp_003_naming_the_first_finding(tmp_path):
    root = tree(tmp_path)
    walk_to(root, "baselined")
    ledger_path(root).write_bytes(ledger_path(root).read_bytes()[:-9] + b"corrupted\n")
    exc = attempt(campaign.verify_for_plan, root, campaign_doc())
    assert code_of(exc) == "HB-CMP-003" and str(exc).startswith("HB-CMP-003: ")


def test_campaign_verify_runs_after_a_campaign_pass(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    doc = json.loads((run_dir / "plan.json").read_text(encoding="utf-8")) | campaign_doc()
    doc["plan_hash"] = plan.plan_hash(doc)
    (run_dir / "plan.json").write_text(json.dumps(doc), encoding="utf-8")
    seen = {}

    def record(root_, plan_doc):
        seen.update(held=oslock.is_held(run_dir / "grade.lock"), cid=plan_doc["campaign"]["campaign_id"])
        return "campaign verify: ok (7 rows)"

    monkeypatch.setattr(campaign, "verify_for_plan", record)
    monkeypatch.setattr(runner._Pass, "run", lambda self: "RESULT")
    assert runner.run_pass(run_dir, root) == "RESULT"
    assert seen == {"held": False, "cid": CID}  # after the `with` block: grade.lock is released
    assert "campaign verify: ok (7 rows)" in capsys.readouterr().out


def test_the_hook_skips_a_plan_with_no_campaign_block_and_a_raising_hook_leaves_the_pass_done(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    plain = make_run(root, tmp_path / "a", {"a": GOOD})
    calls = []
    monkeypatch.setattr(campaign, "verify_for_plan", lambda *a: calls.append(a) or "x")
    monkeypatch.setattr(runner._Pass, "run", lambda self: "RESULT")
    assert runner.run_pass(plain, root) == "RESULT" and calls == []
    block = make_run(root, tmp_path / "b", {"a": GOOD})
    doc = json.loads((block / "plan.json").read_text(encoding="utf-8")) | campaign_doc()
    doc["plan_hash"] = plan.plan_hash(doc)
    (block / "plan.json").write_text(json.dumps(doc), encoding="utf-8")
    ran = []
    monkeypatch.setattr(runner._Pass, "run", lambda self: ran.append(1) or "RESULT")

    def broken(*a):
        raise campaign.BenchError("HB-CMP-003", "ledger is torn. Restore it with git.")

    monkeypatch.setattr(campaign, "verify_for_plan", broken)
    assert code_of(attempt(runner.run_pass, block, root)) == "HB-CMP-003"
    assert ran == [1]  # the pass itself completed before the hook ran


# --- B-1..B-3: bench-campaign-status/1 -------------------------------------------------------------------------------------------


def test_status_json_is_schema_bound_b1(tmp_path):
    root = tree(tmp_path)
    walk_to(root, "registered")
    doc = campaign.status_doc(root, CID)
    assert doc["schema"] == "bench-campaign-status/1" and doc["campaign_id"] == CID and doc["state"] == "registered"
    assert campaign.parse_status(campaign.to_json(doc)) == doc
    for broken in ({**doc, "extra": 1}, {k: v for k, v in doc.items() if k != "next"}, {**doc, "state": "sleeping"},
                   {**doc, "next": "dance"}, {**doc, "schema": "bench-campaign-status/2"}):
        with pytest.raises(ValueError):
            campaign.parse_status(json.dumps(broken))


def test_status_json_carries_no_free_text_b2(tmp_path):
    root = tree(tmp_path)
    walk_to(root, "piloted")
    append(root, "admission.decided", task="T1", admitted=0, reason="REASON-WORDS-HERE")
    append(root, "abandoned", reason="ABANDON-WORDS-HERE")
    text = campaign.to_json(campaign.status_doc(root, CID))
    assert QUESTION not in text and "REASON-WORDS-HERE" not in text and "ABANDON-WORDS-HERE" not in text
    assert json.loads(text)["excluded_tasks"] == ["T1"] and '"question"' not in text and '"reason"' not in text


NEXT = {"draft": "baseline", "baselined": "pilot", "piloted": "power", "registered": "attach", "measuring": "conclude", "concluded": "none"}


@pytest.mark.parametrize("state", list(NEXT))
def test_status_next_token_follows_state_b3(tmp_path, state):
    root = tree(tmp_path)
    walk_to(root, state)
    assert campaign.status_doc(root, CID)["next"] == NEXT[state]


def test_next_after_a_final_power_in_piloted_is_register_and_abandoned_is_none_b3(tmp_path):
    root = tree(tmp_path)
    walk_to(root, "piloted")
    append(root, "power.recorded", role="final")
    assert campaign.status_doc(root, CID)["next"] == "register"
    append(root, "abandoned")
    assert campaign.status_doc(root, CID)["next"] == "none"


def test_status_json_through_the_cli_prints_the_document_only(tmp_path, capsys):
    root = tree(tmp_path)
    walk_to(root, "baselined")
    capsys.readouterr()
    assert bench(root, "campaign", "status", CID, "--json") == 0
    out = capsys.readouterr().out
    assert campaign.parse_status(out)["state"] == "baselined" and out.count("\n") == 1


# --- T-1, T-2: telemetry (one record per command; an absent phase is absent, never 0) ---------------------------------------------

FIELDS = {"command", "campaign_id", "state_before", "state_after", "outcome", "code", "rows", "duration_ms"}


def command_records(caplog):
    return [r for r in caplog.records if r.name == "harness_bench.campaign" and r.getMessage() == "campaign.command"]


def test_one_log_record_per_command_with_the_declared_fields_t1(tmp_path, caplog):
    root = tree(tmp_path)
    caplog.set_level("INFO", logger="harness_bench.campaign")
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0  # a no-op
    assert bench(root, "campaign", "conclude", CID) == 1  # refused: not measuring
    first, again, refused = command_records(caplog)
    for record in (first, again, refused):
        assert FIELDS <= set(vars(record)), sorted(FIELDS - set(vars(record)))
    assert (first.command, first.outcome, first.code, first.state_before, first.state_after, first.rows) == ("create", "ok", None, "none", "draft", 1)
    assert (again.outcome, again.code) == ("noop", None)
    assert (refused.command, refused.outcome, refused.code) == ("conclude", "refused", "HB-CMP-002")
    for record in (first, again, refused):
        assert isinstance(record.duration_ms, int) and record.duration_ms >= 0
    assert {"lock_wait_ms", "verify_ms", "sweep_ms", "swept"} <= set(vars(again))  # a write command ran every phase


def test_a_phase_that_did_not_run_is_absent_never_zero_t2(tmp_path, caplog):
    root = tree(tmp_path)
    walk_to(root, "baselined")
    caplog.set_level("INFO", logger="harness_bench.campaign")
    assert bench(root, "campaign", "status", CID) == 0
    (status_record,) = command_records(caplog)
    assert "lock_wait_ms" not in vars(status_record) and "sweep_ms" not in vars(status_record)  # a lock-free read
    caplog.clear()
    with held_by_another_process(campaign.lock_path(root, CID)):
        assert bench(root, "campaign", "conclude", CID) == 1
    (probe_record,) = command_records(caplog)
    assert probe_record.code == "HB-CMP-001" and "verify_ms" not in vars(probe_record) and "sweep_ms" not in vars(probe_record)


# --- C-45, C-46: the (command, state) guard matrix and the refusal copy ------------------------------------------------------------

REFUSED = {  # command -> {state: expected code}: only the cells the guards of `campaign.py` refuse (read at the turn)
    "fix": {"draft": "HB-CMP-002", "concluded": "HB-CMP-002", "abandoned": "HB-CMP-002"},
    "power": {"draft": "HB-CMP-002", "measuring": "HB-CMP-009", "concluded": "HB-CMP-002", "abandoned": "HB-CMP-002"},
    "attach": {s: "HB-CMP-002" for s in ("draft", "baselined", "piloted", "concluded", "abandoned")},
    "pilot attach": {s: "HB-CMP-002" for s in ("draft", "registered", "measuring", "concluded", "abandoned")},
    "pilot pass": {s: "HB-CMP-002" for s in ("draft", "registered", "measuring", "concluded", "abandoned")},
    "admit": {s: "HB-CMP-002" for s in ("draft", "baselined", "registered", "measuring", "concluded", "abandoned")},
    "register": {"draft": "HB-CMP-002"},  # the preview is a read in every other state (it writes nothing); its confirm path is C-33/C-35
    "conclude": {s: "HB-CMP-002" for s in ("draft", "baselined", "piloted", "registered", "abandoned")},
    "abandon": {"concluded": "HB-CMP-002"},
}
MATRIX_STATES = (*STATES, "abandoned")


def argv_of(command: str, root) -> list[str]:
    options = ARGV[command] if command != "register" else ["--prereg", str(stmt(root)[0])]
    return ["campaign", *command.split(), CID, *options]


@pytest.fixture(scope="module")
def matrix_results(tmp_path_factory):
    out = {}
    for state in MATRIX_STATES:
        root = tree(tmp_path_factory.mktemp(state.replace(" ", "-")))
        walk_to(root, "baselined" if state == "abandoned" else state)
        if state == "abandoned":
            append(root, "abandoned")
        cells = {}
        for command, states in REFUSED.items():
            if state in states:
                before = ledger_path(root).read_bytes()
                import contextlib
                import io

                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = cli_rc(["--root", str(root), *argv_of(command, root)])
                cells[command] = (rc, err.getvalue().strip(), ledger_path(root).read_bytes() == before)
        out[state] = cells
    return out


@pytest.mark.parametrize("state", MATRIX_STATES)
def test_state_guard_matrix_c45(matrix_results, state):
    for command, (rc, err, unchanged) in matrix_results[state].items():
        assert rc == 1 and err.startswith(REFUSED[command][state] + ":") and unchanged, (command, state, rc, err)


@pytest.mark.parametrize("state", MATRIX_STATES)
def test_every_refusal_names_item_cause_action_c46(matrix_results, state):
    for command, (_, err, _) in matrix_results[state].items():
        assert re.fullmatch(r"HB-[A-Z]+-\d{3}: .+\. .+\.", err.splitlines()[0]), (command, state, err)
        assert state in err or state == "abandoned" or "frozen" in err, (command, state, err)  # names the item: the state it refused in


def test_create_rerun_is_a_noop_c47(tmp_path, capsys):
    root = tree(tmp_path)
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    before = ledger_path(root).read_bytes()
    capsys.readouterr()
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0
    assert capsys.readouterr().out.startswith("no change:") and ledger_path(root).read_bytes() == before
    assert kinds(root) == ["campaign.created"]
