"""The AI summaries, offline (design phase4-report.md section 8, slice R7; ruling R-81 DR-R-4..6).

Named red-first tests (brief R7 Done when): test_zero_rule_matrix (5 cases), test_number_precision_table,
test_manifest_recomputed_from_captured_payload (+2 mutation refusals), test_summaries_refuse_while_run_live
(fixture live-run). Plus the two `summary_records` invariants (a rewrite fails; a published row with a
failing claim cannot be constructed) and the DR-R-4 sampling / per-excerpt egress / states coverage.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run

from harness_bench import board as board_mod
from harness_bench import cli, egress, oslock, stats, views
from harness_bench.errors import BenchError
from harness_bench.gateway import backend as gw_backend
from harness_bench.grade import runner
from harness_bench.report import summaries as s


def _iv(point, lo, hi, n=8, reason=None):
    conv = lambda x: Decimal(str(x)) if x is not None else None
    return stats.Interval(conv(point), conv(lo), conv(hi), n, reason)


def _measure(value, reason=None):
    return stats.Measure(Decimal(str(value)) if value is not None else None, reason)


def _cell(cell_id, combo, pack, task="X1", rep=1, p1=None):
    scores = {} if p1 is None else {"pass_at_1": _measure(p1)}
    return views.CellView(
        cell_id=cell_id, task=task, rep=rep, label=f"{task}.{combo}.pack-{pack}.r{rep}", combo=combo, arm=pack, harness="claude-code",
        model="claude-opus-5-5", outcome="completed", cause=None, code=None, validity="valid", validity_code=None,
        wall_ms=_measure(2000), model_ms=_measure(1000), tool_ms=_measure(0), idle_ms=_measure(0), tokens=None,
        tokens_reason=None, scores=scores,
    )


def _board(rows=None, pe_rows=None):
    rows = rows or [board_mod.BoardRow(
        combo="cc-opus", pack="on", harness="claude-code", model="claude-opus-5-5", n_cells=6, n_valid=6,
        pass_at_1=_iv(0.667, 0.33, 1.0), gated=_iv(44.53, 20.0, 60.0), pass_at_k=_measure(1), pass_hat_k=_measure(1),
        rank="1", rank_reason=None, tokens=_measure(1000), wall_ms=_measure(2000),
        cost_usd=_measure(None, "no price list entry"), cost_of_pass=_measure(None, "no price list entry"),
    )]
    pe_rows = pe_rows if pe_rows is not None else [
        board_mod.PackEffectRow(combo="cc-opus", measure="pass_at_1", delta=_iv(-0.33, -0.67, 0.00), label=None)]
    pe = board_mod.PackEffect(status=None, excluded_tasks=(), rows=pe_rows)
    return board_mod.Board(run_id="r1", catalog_version="0.5", params=stats.Params(seed=1, resamples=2000),
                           primary="gated", primary_reason=None, rows=rows, pack_effect=pe)


def _view(cells=None):
    cells = cells if cells is not None else [_cell("a", "cc-opus", "on", p1=0.667)]
    return views.RunView(run_id="r1", plan={"pack": {"revision": 92}}, completed=True, grading_id="grade-1",
                         catalog_version="0.5", cells=cells)


OPERATOR = egress.Operator(email=None, username="op", home="/home/op")  # machine-path-ok: operator-home redaction input


# --------------------------------------------------------------------------------- the summary_records fact
def test_summary_records_rewrite_fails(tmp_path):
    """The first invariant (design section 4): the fact is written only through `ledger`, so a rewritten
    row is detected, not silently accepted -- the same tamper-evidence every other ledger fact carries."""
    run_dir = tmp_path / "r1"
    row = s.Row(run_id="r1", pass_id="grade-1", kind="ranking", model="m", manifest=({"id": "a", "sha256": "0" * 64},),
               manifest_sha256="x" * 64, request_sha256="y" * 64, template_version="summary-request/1",
               schema_sha256="z" * 64, outcome="not_published", failing_claims=({"id": 0, "rule": "number check"},))
    s.append(run_dir, row)
    s.append(run_dir, row)
    assert len(s.read_records(run_dir)) == 2

    path = run_dir / s.FACT / f"{s.SEGMENT_ID}.jsonl"
    lines = path.read_bytes().split(b"\n")
    lines[0] = lines[0].replace(b'"outcome":"not_published"', b'"outcome":"published"')  # rewrite the first row
    path.write_bytes(b"\n".join(lines))

    with pytest.raises(BenchError) as exc:
        s.read_records(run_dir)
    assert exc.value.code == "HB-LED-002"


def test_a_concurrent_writer_is_refused_not_raced(tmp_path):
    """D&P Architect review (R7): a second `bench report --summaries` process for the same run is refused
    (HB-SUM-002) while the first holds the write lock, rather than both reopening the segment and racing
    `SegmentWriter.append` -- which would break the whole segment's hash chain, not only the new row."""
    run_dir = tmp_path / "r1"
    row = s.Row(run_id="r1", pass_id="grade-1", kind="ranking", model="m", manifest=(), manifest_sha256="x" * 64,
               request_sha256="y" * 64, template_version="summary-request/1", schema_sha256="z" * 64,
               outcome="backend_unavailable")
    lock = oslock.RunLock.acquire(run_dir / s.FACT / ".lock", "HB-SUM-002")
    try:
        with pytest.raises(BenchError) as exc:
            s.append(run_dir, row)
    finally:
        lock.release()
    assert exc.value.code == "HB-SUM-002"
    s.append(run_dir, row)  # the lock is free again: a later, non-concurrent write succeeds
    assert len(s.read_records(run_dir)) == 1


def test_published_row_requires_passing_claims():
    """The second invariant (design section 4): a `published` row with a failing claim cannot be
    constructed -- `Row.__post_init__` refuses it directly, not merely a caller that happens not to."""
    with pytest.raises(ValueError, match="failing claim"):
        s.Row(run_id="r1", pass_id="grade-1", kind="ranking", model="m", manifest=(), manifest_sha256="x" * 64,
             request_sha256="y" * 64, template_version="summary-request/1", schema_sha256="z" * 64,
             outcome="published", failing_claims=({"id": 0, "rule": "number check"},))


# ------------------------------------------------------------------------------------------- DR-R-4 sampling
def test_sample_pack_on_cells_is_deterministic_and_capped():
    cells = [
        _cell("on-1", "c1", "on", rep=1, p1=1.0), _cell("off-1", "c1", "off", rep=1, p1=0.0),  # discordant
        _cell("on-2", "c1", "on", rep=2, p1=1.0), _cell("off-2", "c1", "off", rep=2, p1=1.0),  # concordant
        _cell("on-3", "c1", "on", rep=3, p1=0.0), _cell("off-3", "c1", "off", rep=3, p1=1.0),  # discordant
        _cell("on-4", "c1", "on", rep=4, p1=1.0), _cell("off-4", "c1", "off", rep=4, p1=0.0),  # discordant, 3rd (capped)
        _cell("on-5", "c2", "on", rep=1, p1=1.0), _cell("off-5", "c2", "off", rep=1, p1=0.0),  # a second combo
    ]
    view = _view(cells)
    chosen = s.sample_pack_on_cells(view)
    assert chosen == ("on-1", "on-3", "on-5")  # c1: 2 of its 3 discordant cells, by cell id; c2: its one


# ---------------------------------------------------------------------------------------------- the zero rule
@pytest.mark.parametrize("kind,delta,text,ok", [
    ("effect", (-0.33, -0.67, 0.00), "the pack lowered cc-opus's pass@1 [-0.67, 0.00]", False),  # crosses: effect fails
    ("effect", (-0.50, -0.70, -0.30), "the pack lowered cc-opus's pass@1 [-0.70, -0.30]", True),  # clear: passes
    ("no_effect", (-0.33, -0.67, 0.00), "no detectable effect on cc-opus [-0.67, 0.00]", True),  # crosses: passes
    ("no_effect", (-0.50, -0.70, -0.30), "no detectable effect on cc-opus [-0.70, -0.30]", False),  # clear: fails
    ("observation", (-0.50, -0.70, -0.30), "cc-opus's pack effect is negative", False),  # no [lo, hi] printed: fails
])
def test_zero_rule_matrix(kind, delta, text, ok):
    resolved = {"pack:cc-opus|pass_at_1": s.Resolved(_iv(*delta), 2, True, "combo")}
    claim = {"kind": kind, "text": text, "refs": ["pack:cc-opus|pass_at_1"]}
    assert s._zero_rule_ok(claim, resolved) is ok


# -------------------------------------------------------------------------------------------- the number check
@pytest.mark.parametrize("text,cited_decimals,cited,ok", [
    ("about 0.67", 2, 0.667, True),
    ("about 0.68", 2, 0.667, False),
    ("about 44.5", 1, 44.53, True),
    ("about 67%", 2, 0.67, True),
    ("about −0.33", 1, -0.33, True),   # unicode minus
    ("about -0.33", 1, -0.33, True),        # ASCII hyphen
    ("about 0.33", 1, -0.33, False),        # sign mismatch
])
def test_number_precision_table(text, cited_decimals, cited, ok):
    resolved = [s.Resolved(s._PointLike(Decimal(str(cited))), cited_decimals, False, "combo")]
    assert s._numbers_ok(text, resolved) is ok


def test_number_check_a_number_equal_only_to_an_uncited_result_fails():
    cited = s.Resolved(s._PointLike(Decimal("0.50")), 2, False, "combo")
    assert not s._numbers_ok("about 0.90", [cited])  # 0.90 matches nothing cited


def test_one_failing_claim_makes_the_whole_summary_not_published():
    b, view = _board(), _view()
    answer = {"claims": [
        {"text": "cc-opus scored 0.67 [board:cc-opus|on|pass_at_1]", "kind": "observation",
         "refs": ["board:cc-opus|on|pass_at_1"]},
        {"text": "cc-opus scored 0.99", "kind": "observation", "refs": ["board:cc-opus|on|pass_at_1"]},  # wrong number
    ]}
    result = s.claim_check(answer, b, view)
    assert not result.ok
    assert result.failing[0].index == 1


# --------------------------------------------------------------------------- US-42 c1: the manifest recompute
def test_manifest_recomputed_from_captured_payload():
    b, view = _board(), _view()
    built = s.build_ranking_request(view, b)
    assert s.manifest_matches(built.manifest, built.rendered.text)


def test_manifest_check_refuses_when_an_export_byte_changed_after_the_manifest_was_built():
    b, view = _board(), _view()
    built = s.build_ranking_request(view, b)
    tampered = tuple({**e, "sha256": "0" * 64} if e["id"] == "board-export" else e for e in built.manifest)
    assert not s.manifest_matches(tampered, built.rendered.text)


def test_manifest_check_refuses_when_a_payload_segment_is_absent_from_the_manifest():
    b, view = _board(), _view()
    built = s.build_ranking_request(view, b)
    short = tuple(e for e in built.manifest if e["id"] != "header-facts")
    assert not s.manifest_matches(short, built.rendered.text)


# ------------------------------------------------------------------------------------- DR-R-6: per-excerpt egress
def test_a_planted_canary_in_a_sampled_excerpt_is_withheld_and_listed_in_the_manifest(tmp_path):
    cells = [_cell("on-1", "c1", "on", p1=1.0), _cell("off-1", "c1", "off", p1=0.0)]
    view = _view(cells)
    run_dir = tmp_path / "r1"
    (run_dir / "archive" / "on-1" / "attempt-1").mkdir(parents=True)
    (run_dir / "archive" / "on-1" / "attempt-1" / "final.log").write_text(
        f"the answer used {egress.CANARIES[0]}", encoding="utf-8")
    b = _board()
    built = s.build_pack_request(view, b, run_dir, OPERATOR, canaries=egress.CANARIES)
    assert built.withheld_excerpts and built.withheld_excerpts[0]["cell_id"] == "on-1"
    entry = next(e for e in built.manifest if e["id"] == "excerpt-on-1")
    assert entry.get("withheld") == egress.WITHHELD


# ------------------------------------------------------------------------------------------------- the states
def test_state_for_none_wait_stale_and_published():
    row = s.Row(run_id="r1", pass_id="g1", kind="ranking", model="m", manifest=({"id": "a", "sha256": "s"},),
               manifest_sha256="deadbeef", request_sha256="r" * 64, template_version="summary-request/1",
               schema_sha256="z" * 64, outcome="published", claims=({"text": "x", "kind": "observation", "refs": ["r1"]},))
    assert s.state_for(None, None) == "S-NONE"
    assert s.state_for(row, "deadbeef") == "S-PUB"
    assert s.state_for(row, "not-the-same-digest") == "S-STALE"

    wait_row = s.Row(run_id="r1", pass_id="g1", kind="ranking", model="m", manifest=(), manifest_sha256="x" * 64,
                     request_sha256="y" * 64, template_version="summary-request/1", schema_sha256="z" * 64,
                     outcome="backend_unavailable")
    assert s.state_for(wait_row, "x" * 64) == "S-WAIT"


# ---------------------------------------------------------------------------------- end to end: generate()
def _replay(request_text: str, tmp_path: Path, answer: dict, harness: str = "claude-code") -> gw_backend.ReplayBackend:
    digest = __import__("hashlib").sha256(request_text.encode("utf-8")).hexdigest()
    record = tmp_path / "native.jsonl"
    record.write_text("{}\n", encoding="utf-8")
    stdout = json.dumps({"result": json.dumps(answer)})
    return gw_backend.ReplayBackend({digest: gw_backend.Recorded(stdout, record, harness)}, tmp_path / "archive")


def test_generate_publishes_a_valid_ranking_answer(tmp_path):
    b, view = _board(), _view()
    run_dir = tmp_path / "r1"
    built = s.build_ranking_request(view, b)
    answer = {"claims": [{"text": "cc-opus scored 0.67", "kind": "observation", "refs": ["board:cc-opus|on|pass_at_1"]}]}
    backend = _replay(built.rendered.text, tmp_path, answer)
    row = s.generate("ranking", run_dir, view, b, backend, operator=OPERATOR)
    assert row.outcome == "published"
    assert s.latest_row(run_dir, "r1", "ranking").outcome == "published"


def test_generate_is_backend_unavailable_with_no_recorded_reply(tmp_path):
    b, view = _board(), _view()
    run_dir = tmp_path / "r1"
    backend = gw_backend.ReplayBackend({}, tmp_path / "archive")
    row = s.generate("ranking", run_dir, view, b, backend, operator=OPERATOR)
    assert row.outcome == "backend_unavailable"


# ------------------------------------------------------------------------------------------------ DR-R-5 (CLI)
def test_summaries_refuse_while_run_live(tmp_path):
    """fixture `live-run`: `bench report --summaries` refuses before doing anything else while a run is
    live, exiting with the named HB-SUM-001 code (design's error table, ruling R-81 condition 3)."""
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, combos={"a": "c1"})
    runner.run_pass(run_dir, root)
    lock = oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-005")
    try:
        code = cli.main(["--root", str(root), "--runs", str(run_dir.parent), "report", "r1", "--summaries"])
    finally:
        lock.release()
    assert code == cli.INVALID
    assert s.read_records(run_dir) == []  # refused before any generation attempt
