"""The report header's judge block (design phase3-gateway-judges sections 7.4 and 12, row s5; R-58 c1 and c2, R-62 a3,
R-63 c3, R-65 c3, R-72 item 6, R-73 item 1).

T-GW-24, 27, 29, 34 and 36. The judge pass and the calibration pass run through the real gateway with the fake judge
CLI replaying the committed placeholder record (directive D7); no real model CLI is launched and no network call is
made. The operator's identifiers are the fixed placeholders the committed records carry (`operator@example.invalid`)
or random synthetic strings (R-42).
"""

import hashlib
import importlib
import json
from decimal import Decimal
from pathlib import Path

from archived_runs import GOOD, make_run
from test_calibrate import cal_root, calibrate
from test_grade_judge import CLAUDE, FIX, ROOT, fake_calls, spawns

from harness_bench import egress, views
from harness_bench.grade import judge, runner
from harness_bench.report import html


def _module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


judges = _module("harness_bench.report.judges")
NOT_BUILT = "harness_bench.report.judges (design section 12, slice 5) is not built"
PLACEHOLDER = egress.Operator(email="operator@example.invalid", username="placeholder-user",
                              home="C:\\Users\\placeholder-user")
RECORDS = FIX / "records"


# --------------------------------------------------------------------------------------------------- T-GW-24
def _record(tmp_path: Path, rows: list[dict] | str) -> Path:
    path = tmp_path / "record.jsonl"
    text = rows if isinstance(rows, str) else "".join(json.dumps(r) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")
    return path


def _user_text(record: Path) -> str:
    return next(json.loads(line)["message"]["content"] for line in record.read_text(encoding="utf-8").splitlines()
                if json.loads(line).get("type") == "user")


def test_t_gw_24_the_claude_text_record_adds_the_account_email_and_the_native_record_adds_none():
    assert judges is not None, NOT_BUILT
    detect = judges.cli_context_classes
    text, native = RECORDS / "claude-fable-text.record.jsonl", RECORDS / "claude-fable-native.record.jsonl"
    request = hashlib.sha256(_user_text(text).encode("utf-8")).hexdigest()
    assert detect(text, PLACEHOLDER, CLAUDE, request) == ("email",)  # the session_context attachment
    assert detect(native, PLACEHOLDER, CLAUDE, request) == ()  # empty on the native-mode turn (spike GW-H)


def test_t_gw_24_a_codex_style_skill_root_is_username_and_home_path_and_a_new_row_kind_is_read_too(tmp_path):
    assert judges is not None, NOT_BUILT
    skills = _record(tmp_path, [{"type": "response_item", "payload": {"content": [
        {"text": "<skills_instructions>| root | C:\\Users\\placeholder-user\\.agents\\skills |</skills_instructions>"}]}}])
    assert judges.cli_context_classes(skills, PLACEHOLDER, "gpt-6-sol", None) == ("username", "home_path")
    novel = _record(tmp_path, [{"type": "a-row-kind-no-reader-knows", "data": {"deep": ["reach operator@example.invalid"]}}])
    assert judges.cli_context_classes(novel, PLACEHOLDER, CLAUDE, None) == ("email",)


def test_t_gw_24_the_gateways_own_request_is_subtracted_and_an_unparseable_record_is_not_recorded(tmp_path):
    assert judges is not None, NOT_BUILT
    request = "Grade this. The artifact says operator@example.invalid wrote it."
    record = _record(tmp_path, [{"type": "user", "message": {"role": "user", "content": request}}])
    digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
    assert judges.cli_context_classes(record, PLACEHOLDER, CLAUDE, digest) == ()  # the request's span, subtracted
    assert judges.cli_context_classes(record, PLACEHOLDER, CLAUDE, None) == ("email",)  # the detector can fire
    broken = _record(tmp_path, '{"type": "user"}\n{not json\n')
    assert judges.cli_context_classes(broken, PLACEHOLDER, CLAUDE, None) is None  # never "none"


# --------------------------------------------------------------------------------------------------- T-GW-27
def test_t_gw_27_the_vendor_split_is_claude_minus_gpt_per_cell_vendor_with_n():
    """An asymmetric hand table in C1's shape: 2 Anthropic cells (14 items) and 4 OpenAI cells (28 items)."""
    assert judges is not None, NOT_BUILT
    anthropic = [("anthropic", 2, 1)] * 10 + [("anthropic", 1, 1)] * 4  # +10 over 14
    openai = [("openai", 0, 2)] * 7 + [("openai", 1, 1)] * 20 + [("openai", 2, 1)]  # -14 + 1 = -13 over 28
    split = judges.vendor_split(anthropic + openai)
    assert split == {"anthropic": (Decimal("0.714"), 14), "openai": (Decimal("-0.464"), 28)}
    assert judges.split_text(split) == \
        "anthropic cells: 0.714 (n = 14) · openai cells: -0.464 (n = 28); disclosed, not a gate"


def test_t_gw_27_the_cell_vendor_is_the_profiles_vendor_never_a_model_id_prefix():
    """R-73 item 1: a Copilot cell on a claude-* id is an OpenAI-harness cell; a Claude Code cell on a gpt-* id is
    Anthropic (the profiles' `vendor:`)."""
    assert judges is not None, NOT_BUILT
    plan = {"cells": [{"cell_id": "a", "harness": "copilot", "model": "claude-opus-5-5"},
                      {"cell_id": "b", "harness": "claude-code", "model": "gpt-6-sol"}]}
    assert judges.cell_vendors(ROOT, plan) == {"a": "openai", "b": "anthropic"}


def test_t_gw_27_pairs_join_the_two_judges_verdicts_per_cell_and_item():
    assert judges is not None, NOT_BUILT
    rows = [{"cell_id": c, "item_id": f"adr_quality#{n}", "judge_or_matcher": m, "outcome": "hit", "code": None,
             "cache_key": f"{m}-{c}", "entry_sha256": "e"} for c in ("a", "b") for n in (1, 2) for m in ("x", "y")]
    rows.append({"cell_id": "c", "item_id": "adr_quality#1", "judge_or_matcher": "x", "outcome": "hit", "code": None,
                 "cache_key": "x-c", "entry_sha256": "e"})  # no second verdict: not a pair
    verdicts = {"x-a": {1: 2, 2: 0}, "y-a": {1: 1, 2: 0}, "x-b": {1: 0, 2: 2}, "y-b": {1: 2, 2: 2}, "x-c": {1: 1}}
    assert judges.pairs(rows, verdicts.get, "x", "y") == [("a", "adr_quality#1", 2, 1), ("a", "adr_quality#2", 0, 0),
                                                          ("b", "adr_quality#1", 0, 2), ("b", "adr_quality#2", 2, 2)]
    assert judges.agreement(judges.pairs(rows, verdicts.get, "x", "y")) == \
        "items judged 4 · exact 2 · within one step 3 · disagreements 1"


