"""Tests for clarify grader (design docs/design/phase3-graders.md, W3-GR-CLAR slice l1).

Metrics: key_question_recall, key_question_precision, ask_vs_assume, asked_unmatched.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from harness_bench import config
from harness_bench.grade import CellInput, clarify

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "grade" / "clarify"
A1_TASK_DIR = ROOT / "tasks" / "A1"
A1_CSET_HASH = "86fee6273e75d4fad474a89e25edde6f71a676a1112169149f733e8288963e0d"
MATCHER_VERSION = "t0-c8b7e628d0c7"
ALL_METRICS = ("key_question_recall", "key_question_precision", "ask_vs_assume", "asked_unmatched")


def _make_input(tmp_path: Path, archive: Path, *, cset_hash: str = A1_CSET_HASH,
                matcher_version: str = MATCHER_VERSION, task_name: str = "A1") -> CellInput:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    clarify_metrics = {m["id"]: m for area in catalog["areas"].values() for m in area.get("metrics") or []
                       if m.get("grader") == "clarify"}
    task = config.load_yaml(A1_TASK_DIR / "task.yaml")
    plan = {
        "run_id": "test-run",
        "created_at": "2026-09-25T10:00:00",
        "tasks": {
            task_name: {
                "scripted_user": 1,
                "clarifications_path": str(A1_TASK_DIR / "oracle" / "clarifications.yaml"),
                "clarifications_sha256": cset_hash,
                "matcher_version": matcher_version,
            },
        },
    }
    cell = {"cell_id": "c1", "task": task_name, "harness": "claude-code"}
    return CellInput(
        run_dir=run_dir,
        root=ROOT,
        plan=plan,
        cell=cell,
        task=task,
        task_dir=A1_TASK_DIR,
        archive=archive,
        out_dir=out_dir,
        events=(),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics=clarify_metrics,
        allow_model_calls=False,
        extraction=None,
        prices=None,
    )


# --- (a) One call matching goal-maximum --------------------------------------------------------------------------


def test_seeded_a_single_matching_call(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_a")
    scores = clarify.grade_cell(inp)
    assert scores["key_question_recall"].value == 1
    assert scores["key_question_recall"].reason is None
    assert scores["key_question_precision"].value == 1
    assert scores["key_question_precision"].reason is None
    assert scores["ask_vs_assume"].value == 1
    assert scores["ask_vs_assume"].reason is None
    assert scores["asked_unmatched"].value == 0
    assert scores["asked_unmatched"].reason is None


# --- (b) Two calls both matching goal-maximum --------------------------------------------------------------------


def test_seeded_b_two_matching_calls(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_b")
    scores = clarify.grade_cell(inp)
    assert scores["key_question_recall"].value == 1  # never 2 (capped at distinct annotated ids)
    assert scores["key_question_recall"].reason is None
    assert scores["key_question_precision"].value == 1
    assert scores["key_question_precision"].reason is None
    assert scores["ask_vs_assume"].value == 1  # capped at 1
    assert scores["ask_vs_assume"].reason is None
    assert scores["asked_unmatched"].value == 0
    assert scores["asked_unmatched"].reason is None


# --- (c) The end row with tool_listed false gives every metric NA "tool not reached" -----------------------------


def test_seeded_c_tool_not_reached(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_c")
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "tool not reached"


# --- (d) A torn last line gives NA "scripted-user log unreadable: torn tail" ------------------------------------


def test_seeded_d_torn_tail(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_d")
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "scripted-user log unreadable: torn tail"


# --- Zero questions asked: precision is NA, ask_vs_assume is 0 ---------------------------------------------------


def test_no_question_asked_scores_ask_vs_assume_zero(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "no_questions")
    scores = clarify.grade_cell(inp)
    assert scores["key_question_recall"].value == 0
    assert scores["key_question_recall"].reason is None
    assert scores["key_question_precision"].value is None
    assert scores["key_question_precision"].reason == "no question asked"
    assert scores["ask_vs_assume"].value == 0
    assert scores["ask_vs_assume"].reason is None
    assert scores["asked_unmatched"].value == 0
    assert scores["asked_unmatched"].reason is None


# --- Common NA reasons -------------------------------------------------------------------------------------------


def test_no_scripted_user_log_is_na(tmp_path):
    empty_archive = tmp_path / "empty_archive"
    empty_archive.mkdir()
    inp = _make_input(tmp_path, empty_archive)
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "no scripted-user log"


def test_invalid_row_in_log_is_na(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "invalid_row")
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "scripted-user log unreadable: invalid row"


def test_clarification_set_changed_since_the_plan_is_na(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_a", cset_hash="0" * 64)
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "clarification set changed since the plan"


def test_matcher_version_differs_from_the_plans_is_na(tmp_path):
    inp = _make_input(tmp_path, FIXTURES / "seeded_a", matcher_version="t0-differentversion")
    scores = clarify.grade_cell(inp)
    for m in ALL_METRICS:
        assert scores[m].value is None
        assert scores[m].reason == "matcher version differs from the plan's"


# --- Reading stored decisions and never re-matching --------------------------------------------------------------


def test_reads_stored_decision_never_rematches(tmp_path):
    """A question that no matcher would match still gives recall 1 when its stored decision says goal-maximum."""
    archive = tmp_path / "stored_archive"
    archive.mkdir()
    log = archive / "scripted-user.jsonl"
    log.write_text(
        f'{{"kind":"header","schema":"bench-scripted-user-log/1","task":"A1","clarifications_sha256":"{A1_CSET_HASH}","matcher_version":"{MATCHER_VERSION}"}}\n'
        '{"kind":"initialize","client":{"name":"test"},"protocol_version":"2025-11-25"}\n'
        '{"kind":"tools_listed"}\n'
        f'{{"kind":"call","seq":1,"t":1.0,"question":"Irrelevant question that cannot match!","question_sha256":"1111","clarifications_sha256":"{A1_CSET_HASH}","matcher_version":"{MATCHER_VERSION}","decision":{{"clarification":"goal-maximum","rung":"exact"}},"reply":"reply"}}\n'
        '{"kind":"end","calls":1,"client_initialized":true,"tool_listed":true}\n',
        encoding="utf-8",
    )
    inp = _make_input(tmp_path, archive)
    scores = clarify.grade_cell(inp)
    assert scores["key_question_recall"].value == 1
    assert scores["key_question_precision"].value == 1
    assert scores["ask_vs_assume"].value == 1
    assert scores["asked_unmatched"].value == 0


def test_clarify_module_never_imports_or_calls_matcher():
    """Verify statically that clarify.py does not import the matcher module."""
    src = (ROOT / "src" / "harness_bench" / "grade" / "clarify.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "matcher" not in alias.name, f"Forbidden import of matcher: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "matcher" not in mod, f"Forbidden import from matcher: {mod}"
            for alias in node.names:
                assert "matcher" not in alias.name, f"Forbidden import of matcher: {alias.name}"


# --- Leader join fix: no guessed annotated id; ratios are decimals at the catalog scale ---------------------------


def test_a_missing_clarification_set_is_na_never_a_guessed_id(tmp_path):
    # The grader once fell back to {"goal-maximum"} when the set was missing: a guess, scored as if it were the oracle.
    inp = _make_input(tmp_path, FIXTURES / "seeded_a")
    inp.plan["tasks"]["A1"]["clarifications_path"] = str(tmp_path / "absent" / "clarifications.yaml")
    inp = dataclasses.replace(inp, task_dir=tmp_path / "absent-task")
    scores = clarify.grade_cell(inp)
    for metric in ALL_METRICS:
        assert (scores[metric].value, scores[metric].reason) == (None, "clarification set changed since the plan"), metric


def test_a_non_integer_ratio_is_a_decimal_at_the_catalog_scale(tmp_path):
    # Two annotated ids, one asked: recall 1/2. Integer division would store 0.
    cset = tmp_path / "cset" / "clarifications.yaml"
    cset.parent.mkdir()
    cset.write_bytes(b"clarifications:\n  - id: goal-maximum\n  - id: input-format\n")
    digest = hashlib.sha256(cset.read_bytes()).hexdigest()
    log = tmp_path / "log"
    log.mkdir()
    rows = [
        {"kind": "header", "schema": "bench-scripted-user-log/1", "task": "A1", "clarifications_sha256": digest,
         "matcher_version": MATCHER_VERSION, "log_source": "env"},
        {"kind": "tools_listed"},
        {"kind": "call", "seq": 1, "t": 1.0, "question": "q", "question_sha256": "0" * 64,
         "clarifications_sha256": digest, "matcher_version": MATCHER_VERSION,
         "decision": {"clarification": "goal-maximum", "rung": "t0"}, "reply": "r"},
        {"kind": "end", "calls": 1, "client_initialized": True, "tool_listed": True},
    ]
    (log / "scripted-user.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    inp = _make_input(tmp_path, log, cset_hash=digest)
    inp.plan["tasks"]["A1"]["clarifications_path"] = str(cset)
    scores = clarify.grade_cell(inp)
    assert inp.metrics["key_question_recall"]["scale"] == 4
    assert scores["key_question_recall"].value == Decimal("0.5")
    assert isinstance(scores["key_question_recall"].value, Decimal)
    assert scores["key_question_precision"].value == Decimal("1")
    assert scores["ask_vs_assume"].value == Decimal("0.5")
    assert scores["asked_unmatched"].value == 0
