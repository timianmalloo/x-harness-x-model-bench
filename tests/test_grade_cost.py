"""The cost grader (design docs/design/phase3-cost.md; seam C-1). cost_usd's own tests stay in tests/test_grade.py
(unchanged behaviour, moved verbatim); this file covers the five cell-grain efficiency metrics this slice decides,
plus `compactions`, each on a synthetic seeded `CellInput`.
"""

from decimal import Decimal
from pathlib import Path

from harness_bench import config
from harness_bench.grade import CellInput, Score
from harness_bench.grade.cost import grade_cell
from harness_bench.telemetry import Extraction, MissingField, ModelCall
from harness_bench.telemetry.normalize import TurnUsage

PLAN = {"profiles": {"codex": {"usage_source": "native_record"}, "claude-code": {"usage_source": "acp_turn"}},
        "created_at": "2026-09-20T00:00:00"}
NEW = ("tokens_per_minute", "output_tokens_per_turn", "cache_hit_ratio", "cache_write_amplification", "context_growth")


_UNSET = object()  # distinguishes "no extraction given" (defaults to empty) from "extraction=None" (no native record)


def ci(harness="codex", model_calls=(), turn_usage=(), extraction=_UNSET, record_reason=None) -> CellInput:
    """A synthetic per-cell input: only the fields `cost.grade_cell` reads are given real values. The default
    extraction is empty (a record that was read but carries no calls); pass `extraction=None` (with a
    `record_reason`) for the no-native-record case, which the real runner always pairs with a reason."""
    if extraction is _UNSET:
        extraction = Extraction()
    return CellInput(run_dir=Path("."), root=Path("."), plan=PLAN, cell={"harness": harness}, task={}, task_dir=Path("."),
                     archive=Path("."), out_dir=Path("."), events=(), record_reason=record_reason,
                     model_calls=tuple(model_calls), tool_calls=(), turn_usage=tuple(turn_usage), metrics={},
                     allow_model_calls=False, extraction=extraction, prices={})


def call(uncached_input=0, cache_read=0, cache_write=0, output=0, native_ordinal=1, model="m", **kw) -> ModelCall:
    return ModelCall(native_ordinal=native_ordinal, model=model, uncached_input=uncached_input, cache_read=cache_read,
                     cache_write=cache_write, output=output, reasoning=None, **kw)


def row(uncached_input=0, cache_read=0, cache_write=0, output=0, requests=1, start=None, end=None,
        native_ordinal=1, model="m") -> dict:
    """One `model_calls` ledger row, the shape `normalize.model_call_rows` writes."""
    return {"native_ordinal": native_ordinal, "model": model, "uncached_input": uncached_input, "cache_read": cache_read,
            "cache_write": cache_write, "output": output, "reasoning": None, "requests": requests, "start": start,
            "end": end}


def test_compactions_is_always_na_no_signal_on_any_harness():
    scores = grade_cell(ci())
    assert scores["compactions"] == Score(None, "no compaction signal recorded by any harness")


# --- the shared na-gate (_totals_or_na): every one of the five new metrics propagates it ---------------------------


def test_no_usage_at_all_is_na_for_every_new_metric():
    scores = grade_cell(ci(extraction=Extraction()))
    assert {m: scores[m] for m in NEW} == {m: Score(None, "no usage recorded") for m in NEW}


def test_no_native_record_propagates_its_reason():
    scores = grade_cell(ci(extraction=None, record_reason="no native record for the session"))
    assert {m: scores[m] for m in NEW} == {m: Score(None, "no native record for the session") for m in NEW}


def test_a_missing_usage_field_names_hb_tel_001():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10)], missing=[MissingField(1, "cachedReadTokens")])
    scores = grade_cell(ci(extraction=ex))
    reason = "HB-TEL-001 native-record fields missing: cachedReadTokens"
    assert {m: scores[m] for m in NEW} == {m: Score(None, reason) for m in NEW}


def test_a_truncated_native_record_is_na_with_its_reason():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10)], truncated=True)
    scores = grade_cell(ci(extraction=ex, record_reason="native record truncated at the size bound"))
    assert {m: scores[m] for m in NEW} == {m: Score(None, "native record truncated at the size bound") for m in NEW}


# --- tokens_per_minute -----------------------------------------------------------------------------------------


def test_tokens_per_minute_is_total_tokens_over_busy_minutes():
    ex = Extraction(model_calls=[call(uncached_input=1000, output=200, native_ordinal=1),
                                 call(uncached_input=500, cache_read=100, output=300, native_ordinal=2)])
    calls = [row(uncached_input=1000, output=200, start="2026-01-01T00:00:00", end="2026-01-01T00:00:30"),
            row(uncached_input=500, cache_read=100, output=300, start="2026-01-01T00:00:40", end="2026-01-01T00:01:10")]
    scores = grade_cell(ci(extraction=ex, model_calls=calls))
    assert scores["tokens_per_minute"] == Score(2100, None)  # 2100 tokens over two disjoint 30s spans = 1 minute


def test_tokens_per_minute_is_na_for_an_acp_turn_harness_even_with_usable_calls():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10, start="2026-01-01T00:00:00", end="2026-01-01T00:00:10")])
    scores = grade_cell(ci(harness="claude-code", extraction=ex, turn_usage=[TurnUsage("m", 100, 0, 0, 10, 0)]))
    assert scores["tokens_per_minute"] == Score(None, "the native record misses calls (token source acp_turn)")


def test_tokens_per_minute_is_na_with_no_model_call_span():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10)])  # tokens exist; no start/end recorded
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=100, output=10)]))
    assert scores["tokens_per_minute"] == Score(None, "no model call time recorded")


# --- output_tokens_per_turn -------------------------------------------------------------------------------------


def test_output_tokens_per_turn_is_output_over_requests():
    ex = Extraction(model_calls=[call(uncached_input=1000, output=400)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=1000, output=400, requests=4)]))
    assert scores["output_tokens_per_turn"] == Score(100, None)  # 400 output tokens / 4 requests


def test_output_tokens_per_turn_is_na_when_a_row_requests_is_zero():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=100, output=10, requests=0)]))
    assert scores["output_tokens_per_turn"] == Score(None, "not recorded")


# --- cache_hit_ratio ---------------------------------------------------------------------------------------------


def test_cache_hit_ratio_is_reads_over_reads_plus_uncached():
    ex = Extraction(model_calls=[call(uncached_input=100, cache_read=300, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=100, cache_read=300, output=10)]))
    assert scores["cache_hit_ratio"] == Score(Decimal("75.0000"), None)  # 300 / (100 + 300) * 100


def test_cache_hit_ratio_is_na_with_no_input_tokens():
    ex = Extraction(model_calls=[call(output=50)])  # output only: no uncached_input, no cache_read
    scores = grade_cell(ci(extraction=ex, model_calls=[row(output=50)]))
    assert scores["cache_hit_ratio"] == Score(None, "no input tokens recorded")


# --- cache_write_amplification ----------------------------------------------------------------------------------


def test_cache_write_amplification_is_writes_over_reads():
    ex = Extraction(model_calls=[call(cache_read=200, cache_write=50, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(cache_read=200, cache_write=50, output=10)]))
    assert scores["cache_write_amplification"] == Score(Decimal("25.0000"), None)  # 50 / 200 * 100


def test_cache_write_amplification_is_na_with_no_cache_activity():
    ex = Extraction(model_calls=[call(uncached_input=100, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=100, output=10)]))
    assert scores["cache_write_amplification"] == Score(None, "no cache activity recorded")


def test_cache_write_amplification_is_na_with_writes_but_no_reads():
    ex = Extraction(model_calls=[call(cache_write=40, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(cache_write=40, output=10)]))
    assert scores["cache_write_amplification"] == Score(None, "no cache reads recorded")


# --- context_growth (peak) --------------------------------------------------------------------------------------


def test_context_growth_is_the_largest_single_call():
    ex = Extraction(model_calls=[call(output=10), call(output=10, native_ordinal=2)])
    calls = [row(uncached_input=200, cache_read=100, cache_write=200, output=10),  # 500
            row(uncached_input=400, cache_write=300, output=10)]  # 700
    scores = grade_cell(ci(extraction=ex, model_calls=calls))
    assert scores["context_growth"] == Score(700, None)


def test_context_growth_is_na_for_an_acp_turn_harness():
    ex = Extraction(model_calls=[call(uncached_input=900, output=10)])
    scores = grade_cell(ci(harness="claude-code", extraction=ex, turn_usage=[TurnUsage("m", 900, 0, 0, 10, 0)]))
    assert scores["context_growth"] == Score(None, "the native record misses calls (token source acp_turn)")


def test_cache_percentages_keep_four_places_at_real_cache_rates():
    # An integer percent read 100 for every harness at the measured rates (a Copilot cell: 787795 reads, 27 uncached),
    # hiding the very difference the benchmark compares. The catalog gives both metrics scale 4.
    ex = Extraction(model_calls=[call(uncached_input=27, cache_read=787795, cache_write=102909, output=10)])
    scores = grade_cell(ci(extraction=ex, model_calls=[row(uncached_input=27, cache_read=787795, cache_write=102909,
                                                               output=10)]))
    assert scores["cache_hit_ratio"] == Score(Decimal("99.9966"), None)
    assert scores["cache_write_amplification"] == Score(Decimal("13.0629"), None)
    catalog = config.load_yaml(Path(__file__).resolve().parents[1] / "bench" / "metrics.yaml")
    scales = {m["id"]: m.get("scale") for a in catalog["areas"].values() for m in a.get("metrics") or []}
    assert (scales["cache_hit_ratio"], scales["cache_write_amplification"]) == (4, 4)
