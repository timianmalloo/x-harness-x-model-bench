"""Red-first tests for `report.pack_improvement` slices S3 and S4 (design pack-improvement-section.md
section 11; R-85). Each test is named after the PI-T id it implements or extends (R-85 condition 2's
"class of test" over the four new NA paths).
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import views
from harness_bench.report import pack_improvement as pi
from harness_bench.telemetry import ToolInput

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "pack_improvement"


def _cell(cid, combo, pack, validity="valid", tokens=None, tokens_reason="not graded"):
    na = views.Measure(None, "not graded")
    return views.CellView(
        cell_id=cid, label=f"X1.{combo}.pack-{pack}.r1", combo=combo, pack=pack, harness="claude-code",
        model="claude-sonnet-5", outcome="completed", cause=None, code=None, validity=validity,
        validity_code=None, wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na, tokens=tokens,
        tokens_reason=tokens_reason,
    )


# ---------------------------------------------------------------------------------------------------
# PI-T3: pairing
# ---------------------------------------------------------------------------------------------------


def test_pi_t3_pairs_exclude_a_cell_whose_other_arm_is_invalid():
    on = _cell("a-on", "codex-sol", "on")
    off = _cell("a-off", "codex-sol", "off", validity="invalid (build mismatch)")
    plan_by_id = {"a-on": {"task": "X1", "rep": 1}, "a-off": {"task": "X1", "rep": 1}}
    assert pi.pairs([on, off], plan_by_id) == []


def test_pi_t3_pairs_include_a_complete_valid_pair():
    on = _cell("a-on", "codex-sol", "on")
    off = _cell("a-off", "codex-sol", "off")
    plan_by_id = {"a-on": {"task": "X1", "rep": 1}, "a-off": {"task": "X1", "rep": 1}}
    result = pi.pairs([on, off], plan_by_id)
    assert len(result) == 1
    assert result[0].task == "X1" and result[0].combo == "codex-sol" and result[0].rep == 1
    assert result[0].on is on and result[0].off is off


# ---------------------------------------------------------------------------------------------------
# PI-T4: cost NA propagation (also covers the "blast radius" and "no extra tokens" NA paths, R-85 c2)
# ---------------------------------------------------------------------------------------------------


def _tokens(uncached: int) -> dict:
    return {"claude-sonnet-5": {"uncached_input": uncached, "cache_read": 0, "cache_write": 0, "output": 0}}


def test_pi_t4_tokens_none_gives_ratio_na_with_tokens_reason_and_median_uses_other_pairs():
    na_pair = pi.Pair(
        task="X1", combo="c", rep=1,
        on=_cell("1-on", "c", "on", tokens=None, tokens_reason="the native record misses calls (token source acp_turn)"),
        off=_cell("1-off", "c", "off", tokens=_tokens(100)),
    )
    ok_pair = pi.Pair(
        task="X1", combo="c", rep=2,
        on=_cell("2-on", "c", "on", tokens=_tokens(200)),
        off=_cell("2-off", "c", "off", tokens=_tokens(100)),
    )
    na_ratio = pi.tokens_ratio(na_pair)
    assert na_ratio.value is None
    assert na_ratio.reason == "the native record misses calls (token source acp_turn)"

    ok_ratio = pi.tokens_ratio(ok_pair)
    assert ok_ratio.value == Decimal(2)

    median, above, n = pi.median_ratio([na_ratio, ok_ratio])
    assert n == 1  # the NA pair is dropped, never read as 0 or 1
    assert above == 1
    assert median.value == Decimal(2)


def test_pi_t4_modeled_share_is_na_no_extra_tokens_when_on_did_not_exceed_off():
    share = pi.modeled_share(Decimal(500), calls_on_sum=10, tokens_on_sum=1000, tokens_off_sum=1200)
    assert share.value is None
    assert share.reason == pi.NA_NO_EXTRA_TOKENS


def test_pi_t4_modeled_share_caps_at_one():
    share = pi.modeled_share(Decimal(10_000), calls_on_sum=10, tokens_on_sum=2000, tokens_off_sum=1000)
    assert share.value == Decimal(1)


def test_pi_t4_blast_radius_unreadable_cascades_to_test_first_and_stopped_without_product_and_diverted(tmp_path):
    """R-85 item 1: product_write is NA when blast_radius is None, so test_first,
    stopped_without_product and diverted_delivery are NA "blast radius not readable" -- never a
    guessed False or a zero."""
    calls = (ToolInput(1, "Write", ("src/a.py",), None, True),)
    assert pi.test_first(calls, None) == views.Measure(None, pi.NA_BLAST_RADIUS)
    result = pi.stopped_without_product(
        outcome="completed", stop_reason="end_turn", pass_at_1=0, calls=calls, blast_radius=None
    )
    assert result == views.Measure(None, pi.NA_BLAST_RADIUS)
    diverted = pi.diverted_delivery(tmp_path, tmp_path / "ws", None)
    assert diverted == views.Measure(None, pi.NA_BLAST_RADIUS)


# ---------------------------------------------------------------------------------------------------
# PI-T7: classification reads paths, never call content
# ---------------------------------------------------------------------------------------------------


def test_pi_t7_test_first_uses_write_target_paths_only():
    """A source write whose *command text* mentions `tests/` (the closest thing `ToolInput` carries
    to "content") is not classified as a test_write -- only the write-target path is examined
    (design section 4.3's own table)."""
    call = ToolInput(1, "Write", ("src/solution.py",), "echo tests/ done", True)
    assert "test_write" not in pi.classify(call, ["src/solution.py"])
    assert "product_write" in pi.classify(call, ["src/solution.py"])


def test_pi_t7_test_first_orders_test_write_before_product_write():
    # D1's own shape (tasks/D1/task.yaml:35): blast_radius names both the product and "tests/**".
    blast_radius = ["solution.py", "tests/**"]
    calls = (
        ToolInput(1, "Write", ("tests/test_solution.py",), None, True),
        ToolInput(2, "Write", ("solution.py",), None, True),
    )
    assert pi.test_first(calls, blast_radius) == views.Measure(True)

    reversed_calls = (
        ToolInput(1, "Write", ("solution.py",), None, True),
        ToolInput(2, "Write", ("tests/test_solution.py",), None, True),
    )
    assert pi.test_first(reversed_calls, blast_radius) == views.Measure(False)


def test_pi_t7_test_first_na_when_blast_radius_has_no_test_path():
    calls = (ToolInput(1, "Write", ("solution.py",), None, True),)
    assert pi.test_first(calls, ["solution.py"]) == views.Measure(None, pi.NA_NO_TEST_PATH)


# ---------------------------------------------------------------------------------------------------
# PI-T8: diverted_delivery / sibling worktrees
# ---------------------------------------------------------------------------------------------------


def _make_sibling(attempt_dir: Path, name: str, gitdir_target: str | None) -> Path:
    sibling = attempt_dir / name
    sibling.mkdir(parents=True)
    if gitdir_target is not None:
        (sibling / ".git").write_text(f"gitdir: {gitdir_target}\n", encoding="utf-8")
    return sibling


def test_pi_t8_diverted_delivery_true_for_a_differing_blast_radius_file_in_a_real_sibling_worktree(tmp_path):
    attempt = tmp_path / "attempt-1"
    ws = attempt / "ws"
    ws.mkdir(parents=True)
    (ws / "solution.py").write_bytes(b"A")
    sibling = _make_sibling(attempt, "wt1", "/some/path/ws/.git/worktrees/wt1")
    (sibling / "solution.py").write_bytes(b"B")

    assert pi.worktree_left(attempt) is True
    result = pi.diverted_delivery(attempt, ws, ["solution.py"])
    assert result == views.Measure(True)


def test_pi_t8_diverted_delivery_false_when_sibling_files_equal_ws(tmp_path):
    attempt = tmp_path / "attempt-1"
    ws = attempt / "ws"
    ws.mkdir(parents=True)
    (ws / "solution.py").write_bytes(b"A")
    sibling = _make_sibling(attempt, "wt1", "/some/path/ws/.git/worktrees/wt1")
    (sibling / "solution.py").write_bytes(b"A")

    assert pi.diverted_delivery(attempt, ws, ["solution.py"]) == views.Measure(False)


def test_pi_t8_diverted_delivery_matches_a_nested_double_star_blast_radius_pattern(tmp_path):
    """Real grid-1-cc regression (S5 hand-off): a `src/**` blast radius (F1's own shape,
    `tasks/F1/task.yaml`) must still catch a file several directories deep -- `Path.glob("src/**")`
    alone finds only directories, never the leaf files, at every depth below the first."""
    attempt = tmp_path / "attempt-1"
    ws = attempt / "ws"
    (ws / "src" / "a" / "b").mkdir(parents=True)
    (ws / "src" / "a" / "b" / "deep.cs").write_bytes(b"A")
    sibling = _make_sibling(attempt, "wt1", "/some/path/ws/.git/worktrees/wt1")
    (sibling / "src" / "a" / "b").mkdir(parents=True)
    (sibling / "src" / "a" / "b" / "deep.cs").write_bytes(b"B")

    assert pi.diverted_delivery(attempt, ws, ["src/**"]) == views.Measure(True)


def test_pi_t8_a_directory_without_a_git_file_is_not_a_sibling_worktree(tmp_path):
    attempt = tmp_path / "attempt-1"
    ws = attempt / "ws"
    ws.mkdir(parents=True)
    (ws / "solution.py").write_bytes(b"A")
    home = attempt / "home"
    home.mkdir()
    (home / "solution.py").write_bytes(b"different, but home is not a worktree")
    plain = attempt / "scripted-user.jsonl"  # not even a directory
    plain.write_text("x", encoding="utf-8")

    assert pi.sibling_worktrees(attempt) == []
    assert pi.diverted_delivery(attempt, ws, ["solution.py"]) == views.Measure(False)


# ---------------------------------------------------------------------------------------------------
# PK-03: pack_files_written, read from a real (redacted) drift.log (format pinned against
# `grade/drift.py:125,139`'s own writer, R-85 hand-off).
# ---------------------------------------------------------------------------------------------------


def test_pk_03_pack_files_written_counts_outside_pack_write_lines_only():
    result = pi.pack_files_written(FIX / "drift-pack-files.log")
    assert result.value == pi.PackFilesWritten(files=2, lines=16)  # .agents/artifacts.yml (+15) + log (+1)


def test_pk_03_pack_files_written_is_na_when_the_evidence_key_is_absent():
    assert pi.pack_files_written(None) == views.Measure(None, pi.NA_NO_DRIFT_GRADER)


def test_pk_03_pack_files_written_is_a_real_zero_when_nothing_matches(tmp_path):
    empty = tmp_path / "drift.log"
    empty.write_text("added\tsrc/a.py\tinside\t+1 -0\t\n", encoding="utf-8")
    assert pi.pack_files_written(empty).value == pi.PackFilesWritten(files=0, lines=0)


# ---------------------------------------------------------------------------------------------------
# 4.6: same_failure_both_arms / judge_not_recorded / inconclusive_reasons
# ---------------------------------------------------------------------------------------------------


def test_same_failure_both_arms_reads_unittest_and_xunit_fail_lines():
    unittest_names = pi.failing_test_names(FIX / "oracle-unittest-fail.log")
    assert unittest_names == frozenset({"test_b1_hidden.HiddenSpec.test_spec_required_sections"})
    xunit_names = pi.failing_test_names(FIX / "oracle-xunit-fail.log")
    assert xunit_names == frozenset({
        "WingSpineHiddenTests.RectangularWingMatchesItsClosedForms",
        "WingSpineHiddenTests.EveryDerivationRejectsANullWing",
    })


def test_failing_test_names_is_none_when_unreadable_or_no_match(tmp_path):
    assert pi.failing_test_names(None) is None
    missing = tmp_path / "nope.log"
    assert pi.failing_test_names(missing) is None
    no_fail = tmp_path / "clean.log"
    no_fail.write_text("$ dotnet test\nexit 0\n", encoding="utf-8")
    assert pi.failing_test_names(no_fail) is None


def test_same_failure_both_arms_true_when_every_failing_cell_shares_the_set():
    s = frozenset({"WingSpineHiddenTests.RectangularWingMatchesItsClosedForms"})
    assert pi.same_failure_both_arms([s, s, s]) is True


def test_same_failure_both_arms_false_on_a_differing_set_or_unreadable_entry():
    a = frozenset({"a"})
    b = frozenset({"b"})
    assert pi.same_failure_both_arms([a, b]) is False
    assert pi.same_failure_both_arms([a, None]) is False  # unreadable: skipped, never guessed
    assert pi.same_failure_both_arms([]) is False  # no failing cell


_CATALOG = {
    "areas": {
        "rigor": {"metrics": [
            {"id": "honest_completion_claims", "source": ["J"], "grader": "judge"},
            {"id": "verification_before_done", "source": ["D"], "grader": "rigor"},
        ]},
        "drift": {"metrics": [{"id": "goal_drift_slope", "source": ["J"], "grader": "judge"}]},
    }
}


def test_judge_sourced_metric_ids_reads_the_source_list():
    assert pi.judge_sourced_metric_ids(_CATALOG) == frozenset({"honest_completion_claims", "goal_drift_slope"})


def test_judge_not_recorded_true_when_every_named_judge_metric_is_na():
    assert pi.judge_not_recorded(["judge"], _CATALOG, frozenset()) is True
    assert pi.judge_not_recorded(["judge"], _CATALOG, frozenset({"honest_completion_claims"})) is False


def test_judge_not_recorded_false_when_the_task_names_no_judge_sourced_metric():
    assert pi.judge_not_recorded(["rigor"], _CATALOG, frozenset()) is False


def test_inconclusive_reasons_collects_every_reason_that_applies():
    assert pi.inconclusive_reasons(
        passes_on=4, passes_off=4, n_pairs=4, same_failure=True, judge_not_recorded_=True, no_mapped_metric=False,
    ) == ("saturated", "same failure both arms", "judge not recorded")
    assert pi.inconclusive_reasons(
        passes_on=0, passes_off=0, n_pairs=2, same_failure=False, judge_not_recorded_=False, no_mapped_metric=True,
    ) == ("floor", "few pairs", "no mapped metric")
    assert pi.inconclusive_reasons(
        passes_on=2, passes_off=1, n_pairs=5, same_failure=False, judge_not_recorded_=False, no_mapped_metric=False,
    ) == ()


# ---------------------------------------------------------------------------------------------------
# PI-T9: stopped_without_product
# ---------------------------------------------------------------------------------------------------


def test_pi_t9_stopped_without_product_fires_on_end_turn_pass_zero_and_no_product_write():
    result = pi.stopped_without_product(
        outcome="completed", stop_reason="end_turn", pass_at_1=0, calls=(), blast_radius=["solution.py"]
    )
    assert result == views.Measure(True)


def test_pi_t9_one_product_write_turns_it_off():
    calls = (ToolInput(1, "Write", ("solution.py",), None, True),)
    result = pi.stopped_without_product(
        outcome="completed", stop_reason="end_turn", pass_at_1=0, calls=calls, blast_radius=["solution.py"]
    )
    assert result == views.Measure(False)


def test_pi_t9_a_product_write_from_a_sub_agent_record_also_turns_it_off():
    """"sub-agents included" (design 4.4): the caller composes the main session's calls with each
    sub-agent record's calls before calling this function, so a sub-agent write must count the same
    as a main-session write -- this proves the function itself does not special-case ordinal 1."""
    calls = (
        ToolInput(1, "Read", ("README.md",), None, False),
        ToolInput(7, "Write", ("solution.py",), None, True),  # a later ordinal, as a composed sub-agent call would be
    )
    result = pi.stopped_without_product(
        outcome="completed", stop_reason="end_turn", pass_at_1=0, calls=calls, blast_radius=["solution.py"]
    )
    assert result == views.Measure(False)


@pytest.mark.parametrize(
    ("outcome", "stop_reason", "pass_at_1"),
    [("completed", "tool_use", 0), ("completed", "end_turn", 1), ("timed_out", "end_turn", 0)],
)
def test_pi_t9_does_not_fire_outside_its_exact_condition(outcome, stop_reason, pass_at_1):
    result = pi.stopped_without_product(
        outcome=outcome, stop_reason=stop_reason, pass_at_1=pass_at_1, calls=(), blast_radius=["solution.py"]
    )
    assert result == views.Measure(False)


# ---------------------------------------------------------------------------------------------------
# PI-T13: first_call_input NA reasons
# ---------------------------------------------------------------------------------------------------


def _model_call_row(model, native_ordinal, start, uncached=10, cache_read=0, cache_write=0):
    return {"model": model, "native_ordinal": native_ordinal, "start": start, "uncached_input": uncached,
            "cache_read": cache_read, "cache_write": cache_write}


def test_pi_t13_copilot_first_call_is_na_with_session_totals():
    result = pi.first_call_input(
        usage_source="native_record", harness="copilot", auxiliary_models=(),
        model_call_rows=[_model_call_row("gpt-6-sol", 1, "2026-01-01T00:00:00Z")],
    )
    assert result == views.Measure(None, pi.SESSION_TOTALS)


def test_pi_t13_acp_turn_profile_is_na_with_acp_misses_calls():
    result = pi.first_call_input(
        usage_source="acp_turn", harness="claude-code", auxiliary_models=(),
        model_call_rows=[_model_call_row("claude-sonnet-5", 1, "2026-01-01T00:00:00Z")],
    )
    assert result == views.Measure(None, pi.ACP_MISSES_CALLS)


def test_pi_t13_earliest_non_auxiliary_call_wins():
    rows = [
        _model_call_row("haiku-aux", 1, "2026-01-01T00:00:00Z", uncached=999),  # auxiliary: skipped
        _model_call_row("claude-sonnet-5", 2, "2026-01-01T00:00:01Z", uncached=40, cache_read=10),
        _model_call_row("claude-sonnet-5", 3, "2026-01-01T00:00:02Z", uncached=1000),
    ]
    result = pi.first_call_input(
        usage_source="native_record", harness="claude-code", auxiliary_models=("haiku-aux",), model_call_rows=rows
    )
    assert result.value == Decimal(50)


# ---------------------------------------------------------------------------------------------------
# PI-T10: value/waste/harm/neutral/inconclusive rule order
# ---------------------------------------------------------------------------------------------------


def _group(**kw) -> pi.GroupClassInput:
    base = {
        "passes_on": 3, "passes_off": 3, "n_pairs": 3, "n_ratio_valid": 3,
        "median_token_ratio": Decimal("1.0"), "holm_p": Decimal("1.0"),
        "harm_indicator": False, "quality_lo_positive": False,
    }
    base.update(kw)
    return pi.GroupClassInput(**base)


def test_pi_t10_few_pairs_is_inconclusive_even_when_harm_conditions_also_hold():
    g = _group(n_pairs=1, passes_on=0, passes_off=1, holm_p=Decimal("0.01"))
    cls, _ = pi.classify_group(g)
    assert cls == "inconclusive"


def test_pi_t10_every_pair_ratio_na_is_inconclusive():
    g = _group(n_ratio_valid=0, median_token_ratio=None)
    cls, _ = pi.classify_group(g)
    assert cls == "inconclusive"


def test_pi_t10_harm_by_significant_holm_p():
    g = _group(passes_on=1, passes_off=3, holm_p=Decimal("0.01"))
    assert pi.classify_group(g)[0] == "harm"


def test_pi_t10_harm_by_indicator_without_significance():
    g = _group(passes_on=1, passes_off=3, holm_p=Decimal("0.9"), harm_indicator=True)
    assert pi.classify_group(g)[0] == "harm"


def test_pi_t10_value_by_significant_holm_p():
    g = _group(passes_on=3, passes_off=1, holm_p=Decimal("0.01"))
    assert pi.classify_group(g)[0] == "value"


def test_pi_t10_value_by_quality_interval_even_without_a_pass_gap():
    g = _group(passes_on=3, passes_off=3, quality_lo_positive=True)
    assert pi.classify_group(g)[0] == "value"


def test_pi_t10_waste_by_median_token_ratio():
    g = _group(median_token_ratio=Decimal("1.5"))
    assert pi.classify_group(g)[0] == "waste"


def test_pi_t10_neutral_otherwise():
    g = _group(median_token_ratio=Decimal("1.0"))
    assert pi.classify_group(g)[0] == "neutral"


def test_pi_t10_value_rule_beats_waste_rule_order():
    """Rule order (design 4.5): value (rule 3) is checked before waste (rule 4), so a group that
    would independently qualify as both is reported as value."""
    g = _group(passes_on=3, passes_off=1, holm_p=Decimal("0.01"), median_token_ratio=Decimal("2.0"))
    assert pi.classify_group(g)[0] == "value"


def test_pi_t10_ceiling_off_flag_is_reported_alongside_the_class():
    g = _group(passes_on=3, passes_off=3, median_token_ratio=Decimal("2.0"))
    cls, is_ceiling_off = pi.classify_group(g)
    assert cls == "waste"
    assert is_ceiling_off is True


# ---------------------------------------------------------------------------------------------------
# saturated / floor / ceiling_off -- R-85's renamed, exact-equality predicates
# ---------------------------------------------------------------------------------------------------


def test_r85_saturated_and_floor_are_exact_not_a_percentage_band():
    # 3 of 4 is 75% -- nowhere near the old 95%/5% band, and still not exact equality.
    assert pi.saturated(passes_on=3, passes_off=4, n_pairs=4) is False
    assert pi.floor(passes_on=3, passes_off=4, n_pairs=4) is False
    assert pi.saturated(passes_on=4, passes_off=4, n_pairs=4) is True
    assert pi.floor(passes_on=0, passes_off=0, n_pairs=4) is True


def test_r85_ceiling_off_is_the_off_arm_alone():
    assert pi.ceiling_off(passes_off=4, n_pairs=4) is True
    assert pi.ceiling_off(passes_off=3, n_pairs=4) is False


# ---------------------------------------------------------------------------------------------------
# PI-T11: verdict rules
# ---------------------------------------------------------------------------------------------------


def test_pi_t11_a_miss_indicator_beats_a_hit_metric():
    v = pi.VerdictInput(metric_lo_positive=True, harm_fired=True)
    assert pi.verdict(v) == ("miss", None)


def test_pi_t11_metric_hi_negative_alone_is_a_miss():
    v = pi.VerdictInput(metric_hi_negative=True)
    assert pi.verdict(v) == ("miss", None)


def test_pi_t11_hit_when_metric_lo_positive_and_no_miss():
    v = pi.VerdictInput(metric_lo_positive=True)
    assert pi.verdict(v) == ("hit", None)


def test_pi_t11_process_only_needs_both_thresholds():
    both = pi.VerdictInput(on_share=Decimal("0.9"), off_share=Decimal("0.1"))
    assert pi.verdict(both)[0] == "process only"

    only_on = pi.VerdictInput(on_share=Decimal("0.9"), off_share=Decimal("0.5"))
    assert pi.verdict(only_on)[0] == "inconclusive"

    only_off = pi.VerdictInput(on_share=Decimal("0.5"), off_share=Decimal("0.1"))
    assert pi.verdict(only_off)[0] == "inconclusive"


def test_pi_t11_inconclusive_carries_its_reason_when_nothing_decides():
    v = pi.VerdictInput(inconclusive_reason="no task exercises it")
    assert pi.verdict(v) == ("inconclusive", "no task exercises it")


# ---------------------------------------------------------------------------------------------------
# PI-T12: findings ranking
# ---------------------------------------------------------------------------------------------------


def _finding(code, failed_pairs=0, extra_tokens=0, count=1) -> pi.Finding:
    return pi.Finding(
        code=code, title=code, count=count, failed_pairs=failed_pairs, extra_tokens=extra_tokens,
        evidence_cell_ids=(), pack_area="test", confidence="Verified",
    )


def test_pi_t12_ranking_is_stable_under_input_shuffles():
    findings = [
        _finding("PK-01", failed_pairs=5, extra_tokens=100),
        _finding("PK-02", failed_pairs=5, extra_tokens=200),
        _finding("PK-03", failed_pairs=3, extra_tokens=999),
        _finding("PK-07", failed_pairs=5, extra_tokens=100),  # ties PK-01 on both numbers; code breaks the tie
    ]
    expected = [f.code for f in pi.rank_findings(findings)]
    assert expected == ["PK-02", "PK-01", "PK-07", "PK-03"]

    import random

    shuffled = list(findings)
    rng = random.Random(20260930)
    for _ in range(5):
        rng.shuffle(shuffled)
        assert [f.code for f in pi.rank_findings(shuffled)] == expected


def test_pi_t12_a_zero_count_finding_is_not_rendered():
    findings = [_finding("PK-01", failed_pairs=5, count=0), _finding("PK-02", failed_pairs=1, count=1)]
    assert [f.code for f in pi.rank_findings(findings)] == ["PK-02"]


# ---------------------------------------------------------------------------------------------------
# DR-PI-3 (R-85): PACK_PATHS coverage derived from INSTALL.md's deployment-map tables and
# pack-doctor.py:733-734 -- never from a hand-made fixture manifest (CI6: a fixture copy cannot
# drift, so a test over it cannot fail).
# ---------------------------------------------------------------------------------------------------

_INSTALL_MD = ROOT / "docs" / "ai-forward-pack" / "INSTALL.md"
_PACK_DOCTOR = ROOT / "docs" / "ai-forward-pack" / "scripts" / "pack-doctor.py"
_BACKTICK = re.compile(r"`([^`]+)`")
# The deployment-map tables (main table, then the Grok-, Antigravity- and Codex-specific surface
# tables) -- scanned per-line so a triple-backtick code fence elsewhere in the file can never shift
# backtick pairing across the whole document (verified: a whole-file scan mis-pairs after the file's
# earlier fenced examples and silently finds zero `.github/...` tokens -- checked, not assumed).
_DEPLOYMENT_TABLE_LINE_RANGES = ((251, 267), (408, 413), (428, 433), (447, 455))
_SURFACE_ROOTS = (".claude/", ".github/", ".agents/", ".grok/", "docs/", "AGENTS.md")
# Two bare-root mentions the tables use generically ("`.claude/`" as "the whole client config dir",
# "`docs/`" as "the repo's own docs tree") rather than as a specific pack-content surface -- design
# section 4.3's PACK_PATHS itemises the specific sub-surfaces of `.claude/` and scopes `docs/` to
# `docs/ai-forward-pack/` only, so these two generic roots are not part of what PACK_PATHS covers.
_GENERIC_ROOTS = {".claude/", "docs/"}


def _install_md_surface_prefixes() -> set[str]:
    lines = _INSTALL_MD.read_text(encoding="utf-8").splitlines()
    prefixes: set[str] = set()
    for lo, hi in _DEPLOYMENT_TABLE_LINE_RANGES:
        for line in lines[lo - 1 : hi]:
            if not line.startswith("|"):
                continue
            for tok in _BACKTICK.findall(line):
                if tok != "AGENTS.md" and not any(tok.startswith(root) for root in _SURFACE_ROOTS):
                    continue
                if tok == "AGENTS.md":
                    prefixes.add(tok)
                    continue
                cut = re.split(r"[<*]", tok, maxsplit=1)[0]
                if cut != tok:  # had a `<name>` or `*` placeholder: the directory up to it is the surface
                    prefixes.add(cut)
                elif tok.endswith("/"):  # a bare directory reference
                    prefixes.add(tok)
                # else: a single concrete file (e.g. `.claude/settings.json`) -- not a surface prefix
    return prefixes - _GENERIC_ROOTS


def _pack_doctor_surface_prefixes() -> set[str]:
    lines = _PACK_DOCTOR.read_text(encoding="utf-8").splitlines()
    targets = lines[732:734]  # pack-doctor.py:733-734, 1-indexed, cited verbatim by R-85 DR-PI-3
    prefixes: set[str] = set()
    for line in targets:
        for tok in re.findall(r'"([^"]+)"', line):
            if "/" in tok:
                prefixes.add(tok if tok.endswith("/") else tok + "/")
    return prefixes


def test_dr_pi_3_pack_paths_covers_install_md_and_pack_doctor_surfaces():
    expected = _install_md_surface_prefixes() | _pack_doctor_surface_prefixes()
    assert expected, "the derivation itself found nothing -- a change to INSTALL.md's table shape broke the scan"
    uncovered = [
        prefix for prefix in expected
        if prefix != "AGENTS.md" and not any(prefix.startswith(p) for p in pi.PACK_PATHS)
    ]
    assert uncovered == []
    assert "AGENTS.md" in pi.PACK_PATHS
