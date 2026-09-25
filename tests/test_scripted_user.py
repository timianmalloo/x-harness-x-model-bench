"""The scripted user for scenario 1 (design docs/design/phase2-scripted-user.md sections 6-8 and 12; R-37, R-39, R-51-R-53).

Test ids are the design's promise->test table (section 12). Every fixture here is this track's own: none is derived
from the held-out set (R-39 c2), which these tests never open.
"""

import hashlib
import json
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pytest

from harness_bench.scripted_user import matcher

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "scripted_user"


@dataclass(frozen=True)
class C:
    """A bare annotated question: match() needs only `id` and `question`."""
    id: str
    question: str


ORDER = C("order-ascending", "Should the output be sorted in \u201cascending\u201d order?")
SIZE = C("size-bound", "What is the maximum input size?")
TWO = (ORDER, SIZE)


# --- R-39 c4: one function, one test per rule (T-39-4-N1 ... N5): a pair it joins, a near pair it keeps apart ---

def test_t39_4_n1_nfkc_joins_compatibility_forms():
    assert matcher.normalise("\uff46\uff49\uff4e\uff44 the \uff53\uff55\uff4d") == "find the sum"  # full-width
    assert matcher.normalise("\ufb01nd") == "find"  # the fi ligature
    assert matcher.normalise("find the sum") != matcher.normalise("fund the sum")


def test_t39_4_n2_curly_quotes_become_straight():
    assert matcher.normalise("\u201cfind the sum\u201d") == matcher.normalise('"find the sum"') == '"find the sum"'
    assert matcher.normalise("\u201c\u201d\u201e\u201f") == '""""'
    assert matcher.normalise("\u2018\u2019\u201a\u201b") == "''''"
    assert matcher.normalise('"find" the sum') != matcher.normalise('find "the" sum')


def test_t39_4_n3_casefold():
    assert matcher.normalise("Does") == matcher.normalise("does") == "does"
    assert matcher.normalise("STRASSE") == matcher.normalise("stra\u00dfe") == "strasse"  # casefold, not lower
    assert matcher.normalise("does") != matcher.normalise("dose")


def test_t39_4_n4_whitespace_stripped_and_collapsed():
    assert matcher.normalise("  the  sum ") == "the sum"
    assert matcher.normalise("\tthe\n sum") == "the sum"
    assert matcher.normalise("thesum") != matcher.normalise("the sum")


def test_t39_4_n5_trailing_marks_dropped_inner_and_leading_kept():
    assert matcher.normalise("total value?") == matcher.normalise("total value") == "total value"
    assert matcher.normalise("total value ?!.") == "total value"
    assert matcher.normalise("a?b") == "a?b"
    assert matcher.normalise("?x") == "?x"
    assert matcher.normalise("a.b") != matcher.normalise("ab")


# --- T-39-3d: golden vectors. Each expected output is derived by hand from the rule table, not copied from a run ---

GOLDEN_NORMALISE = [
    ("\uff24\uff4f\uff45\uff53  \u201cFind THE Sum\u201d  mean the MAXIMUM?  ", 'does "find the sum" mean the maximum'),
    ("Stra\u00dfe?!.", "strasse"),
    ("\ufb01nd \u2018x\u2019 \u2026", "find 'x'"),  # the ellipsis is NFKC "...", then a trailing strip
    ("\u3000Tab\there\u3000", "tab here"),  # the ideographic space is NFKC " "
    ("\u2460", "1"),
    ("\u00a0x\u00a0", "x"),
    ("a?b", "a?b"),
]

GOLDEN_DECISIONS = [
    ("Should the output be sorted in \u201cascending\u201d order?", {"clarification": "order-ascending", "rung": "exact"}),
    ('should the output be sorted in "ascending" order', {"clarification": "order-ascending", "rung": "normalised"}),
    ("\uff37\uff28\uff21\uff34 is the maximum input size ?", {"clarification": "size-bound", "rung": "normalised"}),
    ("What is the minimum input size?", {"clarification": None, "rung": "none"}),
    ("Should the output be sorted in ascending order?", {"clarification": None, "rung": "none"}),
]


@pytest.mark.parametrize("text, expected", GOLDEN_NORMALISE)
def test_t39_3d_golden_normalise_vectors(text, expected):
    assert matcher.normalise(text) == expected


@pytest.mark.parametrize("question, decision", GOLDEN_DECISIONS)
def test_t39_3d_golden_decision_vectors(question, decision):
    assert matcher.match(question, TWO).decision() == decision


# --- T-39-3a: matcher_version is the hash of the table and its Unicode data ---

def _independent_version() -> str:
    canonical = json.dumps({"tiers": list(matcher.TIERS), "rules": list(matcher.RULES),
                            "unidata_version": unicodedata.unidata_version},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "t0-" + hashlib.sha256(canonical.encode("ascii")).hexdigest()[:12]


def test_t39_3a_matcher_version_constant_matches_table():
    assert matcher.MATCHER_VERSION == _independent_version()
    assert matcher.compute_matcher_version() == matcher.MATCHER_VERSION
    assert unicodedata.unidata_version in matcher.canonical()


def test_t39_3a_matcher_version_moves_with_the_unicode_data(monkeypatch):
    monkeypatch.setattr(matcher.unicodedata, "unidata_version", "0.0.0")
    assert matcher.compute_matcher_version() != matcher.MATCHER_VERSION


# --- T-39-0: exact, then normalised, then the default; nothing fuzzy ---

def test_t39_0_tiers_exact_normalised_default_only():
    assert matcher.match(SIZE.question, TWO) == matcher.MatchResult("size-bound", "exact")
    assert matcher.match("what is the MAXIMUM input size", TWO) == matcher.MatchResult("size-bound", "normalised")
    for near in ("What is the maximum input sizes?",          # one letter more
                 "What is the maximum input",                 # a prefix
                 "So, what is the maximum input size?",       # a superstring
                 "What's the maximum input size?"):           # a contraction
        assert matcher.match(near, TWO) == matcher.MatchResult(None, "none")
    assert matcher.TIERS == ("exact", "normalised", "none")


def test_t39_0_a_normalised_match_needs_exactly_one_clarification():
    twins = (C("a", "Is it A?"), C("b", "is it a"))  # the loader refuses this set; match() still never picks one
    assert matcher.match("IS IT A", twins) == matcher.MatchResult(None, "none")
    assert matcher.match("Is it A?", twins) == matcher.MatchResult("a", "exact")


# --- section 6: invalid questions (the matcher's half of T-37-6a) ---

@pytest.mark.parametrize("question, reason", [
    (42, "not a string"),
    (None, "not a string"),
    ("", "empty"),
    ("  ?! ", "empty after normalise"),
    ("a\ud800b", "lone surrogate"),
])
def test_t37_6a_invalid_questions_match_nothing(question, reason):
    assert matcher.invalid_reason(question) == reason
    assert matcher.match(question, TWO) == matcher.MatchResult(None, "none", reason)


def test_valid_question_has_no_invalid_reason():
    assert matcher.invalid_reason("What is the maximum input size?") is None


# --- section 7.3: the hashes and the cache key (R-53) ---

def test_question_hash_is_utf8_with_surrogatepass():
    assert matcher.question_sha256("find") == hashlib.sha256(b"find").hexdigest()
    assert matcher.question_sha256("a\ud800b") == hashlib.sha256(b"a\xed\xa0\x80b").hexdigest()


def test_cache_key_is_question_hash_set_hash_and_matcher_version():
    assert matcher.cache_key("find", "c" * 64) == (hashlib.sha256(b"find").hexdigest(), "c" * 64, matcher.MATCHER_VERSION)
    assert matcher.cache_key("find", "c" * 64, "t0-other")[2] == "t0-other"


# --- T-39-2 (R-39 c2): the held-out set is not the matcher author's ---

def _commits(pathspec: str) -> set[str]:
    out = subprocess.run(["git", "log", "--format=%H", "--", pathspec], cwd=ROOT, capture_output=True, text=True,
                         check=True, timeout=60).stdout
    return set(out.split())


def test_t39_2_no_commit_touches_matcher_and_heldout():
    matcher_commits = _commits("src/harness_bench/scripted_user")
    assert matcher_commits  # the path has history, so an empty intersection is evidence
    assert matcher_commits & _commits(":(glob)tasks/*/oracle/heldout_questions.yaml") == set()
