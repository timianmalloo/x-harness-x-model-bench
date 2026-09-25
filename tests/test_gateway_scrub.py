"""The blinding scrub and scan (design phase3-gateway-judges section 7.3, US-35 c1; T-GW-03).

Offline and pure. Every harness, model and combo id below is a synthetic placeholder except the family words,
which the design names.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench.gateway import scrub

ENTRIES = (*scrub.FAMILY_WORDS, "claude-code", "claude code", "gpt-6-sol", "cc-opus", "Synthetic Pack Marker")
FRAGMENTS = (*ENTRIES, "Claud", "laude", "Claudette", "GPTs", "opuses", "gpt-6-solver", "Pack", "Marker", " ", "\n",
             "-", "_", ".", "a", "7", "\u200b", "\u200d", "\u2060", "\ufeff", "\u00ad", "\uff23\uff4c\uff41\uff55\uff44\uff45",
             "e\u0301", "[redacted]")


@settings(max_examples=400, deadline=None)
@given(st.lists(st.sampled_from(FRAGMENTS), max_size=24).map("".join))
def test_t_gw_03_the_scan_of_scrub_x_finds_nothing(text):
    assert scrub.scan(scrub.scrub(text, ENTRIES), ENTRIES) == ()


def test_t_gw_03_hits_near_misses_and_zero_width_characters():
    assert scrub.scan("written by Claude and gpt-6-sol", ENTRIES) == ("Claude", "gpt-6-sol")
    assert scrub.scrub("written by Claude and gpt-6-sol", ENTRIES) == "written by [redacted] and [redacted]"
    assert scrub.scrub("the claude-code harness, CLAUDE_CODE", ENTRIES) == "the [redacted] harness, [redacted]_CODE"
    # whole words only: a near-miss is neither redacted nor reported
    assert scrub.scrub("Claudette's GPTs and gpt-6-solver", ENTRIES) == "Claudette's GPTs and gpt-6-solver"
    assert scrub.scan("Claudette's GPTs and gpt-6-solver", ENTRIES) == ()
    # zero-width and format characters, and full-width letters, do not hide an entry
    assert scrub.scan("Cl\u200baude and O\u00adpus", ENTRIES) == ("Claude", "Opus")
    assert scrub.scrub("Cl\u200baude, \uff23\uff4c\uff41\uff55\uff44\uff45", ENTRIES) == "[redacted], [redacted]"
    # a space inside an entry matches any run of whitespace (a line split does not hide it)
    assert scrub.scan("synthetic  pack\nmarker", ENTRIES) == ("Synthetic Pack Marker",)
    assert scrub.scrub("a Synthetic\tPack Marker.", ENTRIES) == "a [redacted]."


def test_the_denylist_is_the_pack_markers_harnesses_models_combos_and_family_words(tmp_path):
    (tmp_path / "bench" / "profiles").mkdir(parents=True)
    (tmp_path / "bench" / "pack-markers.txt").write_text("Synthetic Pack Marker\n\n", encoding="utf-8")
    (tmp_path / "bench" / "profiles" / "one.yaml").write_text("harness: harness-one\n", encoding="utf-8")
    (tmp_path / "bench" / "prices.yaml").write_text("entries:\n  - {model: model-alpha-1}\n", encoding="utf-8")
    plan = {"matrix": {"combos": [{"id": "combo-x", "harness": "harness-two", "model": "model-beta-2"}]}}
    assert scrub.denylist(tmp_path, plan) == tuple(sorted({
        *scrub.FAMILY_WORDS, "Synthetic Pack Marker", "harness-one", "harness one", "harness-two", "harness two",
        "model-alpha-1", "model-beta-2", "combo-x"}))
