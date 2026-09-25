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
import yaml

from harness_bench.errors import BenchError
from harness_bench.scripted_user import clarifications as clar
from harness_bench.scripted_user import matcher

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "scripted_user"
Z0 = FIXTURES / "clarifications.yaml"
A1 = ROOT / "tasks" / "A1" / "oracle" / "clarifications.yaml"
DEFAULT = "Decide and state your assumption."


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


# --- the clarification set (bench-clarifications/1, tasks/A1/oracle/README.md) and the responder ---

def test_loads_the_clarification_set_and_hashes_its_bytes():
    cset = clar.load(Z0)
    assert cset.sha256 == hashlib.sha256(Z0.read_bytes()).hexdigest()
    assert (cset.task, cset.default_reply) == ("Z0", DEFAULT)
    assert [c.id for c in cset.clarifications] == ["order-ascending", "size-bound"]
    assert cset.clarifications[0] == clar.Clarification("order-ascending", "Behavior", "the sort order: ascending",
                                                        ORDER.question, "Yes, ascending.")


def test_t37_r_reply_is_clarification_text_or_exact_default():
    cset = clar.load(Z0)
    assert clar.DEFAULT_REPLY == DEFAULT
    for question, reply in [(ORDER.question, "Yes, ascending."),                       # exact
                            ("what is the maximum input size", "At most 100000 items."),  # normalised
                            ("What is the minimum input size?", DEFAULT),              # none
                            ("", DEFAULT)]:                                            # invalid
        assert cset.reply_for(matcher.match(question, cset.clarifications)) == reply


A1_QUESTION = "Does “find the sum” mean we should find the maximum possible total value or any valid total value?"
A1_REPLY = "It means to find the maximum possible total value of the chosen balls."


def test_a1_annotated_question_gets_its_reply():
    cset = clar.load(A1)
    assert cset.task == "A1"
    result = matcher.match(A1_QUESTION, cset.clarifications)
    assert result == matcher.MatchResult("goal-maximum", "exact")
    assert cset.reply_for(result) == A1_REPLY
    normalised = 'does "find the sum" mean we should find the maximum possible total value or any valid total value'
    assert cset.reply_for(matcher.match(normalised, cset.clarifications)) == A1_REPLY


# Written by this track from the annotation and the rule table only; never from the held-out set (R-39 c2).
A1_NEAR_MISSES = [
    "Does “find the sum” mean we should find the minimum possible total value or any valid total value?",
    "Does “find the sum” mean we should find the maximum possible total value?",
    "Does find the sum mean we should find the maximum possible total value or any valid total value?",
    "Does “find the sums” mean we should find the maximum possible total value or any valid total value?",
    "Should we find the maximum possible total value?",
]


@pytest.mark.parametrize("question", A1_NEAR_MISSES)
def test_t39_4b_near_misses_get_default_reply(question):
    cset = clar.load(A1)
    result = matcher.match(question, cset.clarifications)
    assert result == matcher.MatchResult(None, "none")
    assert cset.reply_for(result) == DEFAULT


VALID_ITEM = {"id": "q1", "type": "Behavior", "deleted_information": "d", "question": "Is it one?", "reply": "Yes."}


def _doc(**top) -> dict:
    doc = {"schema": "bench-clarifications/1", "task": "Z1", "default_reply": DEFAULT, "clarifications": [dict(VALID_ITEM)]}
    doc.update(top)
    return doc


def _item(**fields) -> dict:
    return {**VALID_ITEM, **fields}


MALFORMED = [
    ("yaml", b"schema: [", "not UTF-8 YAML"),
    ("utf8", b"\xff\xfe", "not UTF-8 YAML"),
    ("top", yaml.safe_dump(["a"]).encode(), "expected a mapping at the top level"),
    ("schema", _doc(schema="bench-clarifications/2"), "schema must be 'bench-clarifications/1'"),
    ("default", _doc(default_reply="Decide."), "default_reply must be exactly 'Decide and state your assumption.' (R-37)"),
    ("task", _doc(task=5), "task must be a string"),
    ("missing", {k: v for k, v in _doc().items() if k != "clarifications"}, "clarifications must be a non-empty list"),
    ("empty", _doc(clarifications=[]), "clarifications must be a non-empty list"),
    ("item", _doc(clarifications=["q"]), "clarifications[0] must be a mapping"),
    ("field", _doc(clarifications=[{k: v for k, v in VALID_ITEM.items() if k != "reply"}]),
     "clarifications[0].reply must be a non-empty string"),
    ("blank", _doc(clarifications=[_item(question="")]), "clarifications[0].question must be a non-empty string"),
    ("typed", _doc(clarifications=[_item(id=7)]), "clarifications[0].id must be a non-empty string"),
    ("dup", _doc(clarifications=[_item(), _item(question="Is it two?")]), "clarifications[1].id 'q1' repeats an earlier id"),
]


def _write(tmp_path: Path, content) -> Path:
    path = tmp_path / "clarifications.yaml"
    path.write_bytes(content if isinstance(content, bytes) else yaml.safe_dump(content, allow_unicode=True).encode("utf-8"))
    return path


@pytest.mark.parametrize("case, content, reason", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_malformed_clarification_file_is_refused_with_a_code(tmp_path, case, content, reason):
    path = _write(tmp_path, content)
    with pytest.raises(BenchError) as caught:
        clar.load(path)
    assert (caught.value.code, caught.value.message) == ("HB-USR-002", f"{path}: {reason}")


@pytest.mark.parametrize("items, reason", [
    ([_item(), _item(id="q2", question="is it ONE")],
     "clarifications[1].question normalises to the same text as clarifications[0]: ambiguous"),
    ([_item(question=" ?!. ")], "clarifications[0].question is empty after normalise"),
], ids=["ambiguous", "empty-after-normalise"])
def test_t39_4c_ambiguous_clarifications_rejected(tmp_path, items, reason):
    path = _write(tmp_path, _doc(clarifications=items))
    with pytest.raises(BenchError) as caught:
        clar.load(path)
    assert (caught.value.code, caught.value.message) == ("HB-USR-002", f"{path}: {reason}")
