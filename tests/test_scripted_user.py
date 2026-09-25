"""The scripted user for scenario 1 (design docs/design/phase2-scripted-user.md sections 6-8 and 12; R-37, R-39, R-51-R-53).

Test ids are the design's promise->test table (section 12). Every fixture here is this track's own: none is derived
from the held-out set (R-39 c2), which these tests never open.
"""

import hashlib
import io
import json
import os
import subprocess
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from harness_bench.errors import BenchError
from harness_bench.scripted_user import clarifications as clar
from harness_bench.scripted_user import log as sulog
from harness_bench.scripted_user import matcher, server

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


A1_QUESTION = "Does \u201cfind the sum\u201d mean we should find the maximum possible total value or any valid total value?"
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
    "Does \u201cfind the sum\u201d mean we should find the minimum possible total value or any valid total value?",
    "Does \u201cfind the sum\u201d mean we should find the maximum possible total value?",
    "Does find the sum mean we should find the maximum possible total value or any valid total value?",
    "Does \u201cfind the sums\u201d mean we should find the maximum possible total value or any valid total value?",
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


# --- the log (design section 8): bench-scripted-user-log/1 ---

class Clock:
    """A fake monotonic clock: each read returns the next value."""

    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def __call__(self) -> float:
        return self.values.pop(0)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_log_rows_carry_question_decision_reply_and_the_key(tmp_path):
    cset = clar.load(Z0)
    writer = sulog.LogWriter(tmp_path / "scripted-user.jsonl", clock=Clock(100.0, 112.4))
    writer.header(cset, "env")
    writer.initialize({"name": "claude-code", "version": "2.1.282"}, "2025-11-25", "2025-11-25")
    writer.tools_listed()
    result = matcher.match("what is the maximum input size", cset.clarifications)
    writer.call("what is the maximum input size", result, cset.reply_for(result), cset)
    assert _rows(tmp_path / "scripted-user.jsonl") == [
        {"kind": "header", "schema": "bench-scripted-user-log/1", "task": "Z0", "clarifications_sha256": cset.sha256,
         "matcher_version": matcher.MATCHER_VERSION, "log_source": "env"},
        {"kind": "initialize", "client": {"name": "claude-code", "version": "2.1.282"}, "protocol_version": "2025-11-25",
         "requested_protocol_version": "2025-11-25"},
        {"kind": "tools_listed"},
        {"kind": "call", "seq": 1, "t": 12.4, "question": "what is the maximum input size",
         "question_sha256": hashlib.sha256(b"what is the maximum input size").hexdigest(),
         "clarifications_sha256": cset.sha256, "matcher_version": matcher.MATCHER_VERSION,
         "decision": {"clarification": "size-bound", "rung": "normalised"}, "reply": "At most 100000 items."},
    ]


def test_an_invalid_question_row_names_its_reason_and_survives_a_lone_surrogate(tmp_path):
    cset = clar.load(Z0)
    writer = sulog.LogWriter(tmp_path / "log.jsonl", clock=Clock(0.0, 1.0))
    result = matcher.match("a\ud800b", cset.clarifications)
    writer.call("a\ud800b", result, cset.reply_for(result), cset)
    (row,) = _rows(tmp_path / "log.jsonl")
    assert (row["question"], row["invalid"], row["decision"], row["reply"]) == (
        "a\ud800b", "lone surrogate", {"clarification": None, "rung": "none"}, DEFAULT)
    assert row["question_sha256"] == hashlib.sha256(b"a\xed\xa0\x80b").hexdigest()


def test_seq_is_assigned_under_one_lock(tmp_path):
    cset = clar.load(Z0)
    writer = sulog.LogWriter(tmp_path / "log.jsonl")
    result = matcher.MatchResult(None, "none")

    def ask() -> None:
        for _ in range(25):
            writer.call("q", result, DEFAULT, cset)

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["seq"] for r in _rows(tmp_path / "log.jsonl")) == list(range(1, 201))


HEADER = {"kind": "header", "schema": "bench-scripted-user-log/1", "task": "Z0"}
INIT = {"kind": "initialize", "client": None, "protocol_version": "2025-06-18", "requested_protocol_version": None}
LISTED = {"kind": "tools_listed"}
CALL = {"kind": "call", "seq": 1}


@pytest.mark.parametrize("rows, end", [
    ([HEADER, INIT, LISTED, CALL],
     {"kind": "end", "calls": 1, "client_initialized": True, "tool_listed": True}),
    ([HEADER, INIT, LISTED],
     {"kind": "end", "calls": 0, "client_initialized": True, "tool_listed": True, "note": "no question asked"}),
    ([HEADER, INIT],
     {"kind": "end", "calls": 0, "client_initialized": True, "tool_listed": False, "note": "tool not reached"}),
    ([HEADER],
     {"kind": "end", "calls": 0, "client_initialized": False, "tool_listed": False, "note": "tool not reached"}),
], ids=["asked", "no-question-asked", "initialized-not-listed", "not-reached"])
def test_end_row_separates_asked_nothing_from_could_not_ask(rows, end):
    assert sulog.end_row(rows, torn_tail=False) == end


def test_end_row_records_a_torn_tail():
    assert sulog.end_row([HEADER, INIT, LISTED], torn_tail=True)["torn_tail"] is True
    assert "torn_tail" not in sulog.end_row([HEADER, INIT, LISTED], torn_tail=False)


def test_a_torn_last_line_is_not_a_row():
    assert sulog.read_rows('{"kind":"header"}\n{"kind":"ca') == ([{"kind": "header"}], True)
    assert sulog.read_rows('{"kind":"header"}\n{"kind":"call"}') == ([{"kind": "header"}], True)  # no newline yet
    assert sulog.read_rows('{"kind":"header"}\n') == ([{"kind": "header"}], False)
    assert sulog.read_rows("") == ([], False)


def test_a_corrupt_middle_line_is_refused():
    with pytest.raises(BenchError) as caught:
        sulog.read_rows('{"kind":"header"}\nnot json\n{"kind":"call"}\n')
    assert (caught.value.code, caught.value.message) == ("HB-USR-002", "scripted-user log line 2 is not a JSON object")


def test_close_log_appends_the_end_row(tmp_path):
    path = tmp_path / "scripted-user.jsonl"
    before = "".join(json.dumps(r) + "\n" for r in (HEADER, INIT, LISTED))
    path.write_text(before, encoding="utf-8")
    end = sulog.close_log(path, header={"kind": "header", "task": "from-plan"})
    assert end["note"] == "no question asked"
    assert path.read_text(encoding="utf-8").startswith(before)
    assert _rows(path)[-1] == end


def test_close_log_never_leaves_the_file_absent_or_empty(tmp_path):
    path = tmp_path / "scripted-user.jsonl"
    end = sulog.close_log(path, header={"kind": "header", "task": "from-plan"})
    assert _rows(path) == [{"kind": "header", "task": "from-plan"}, end]
    assert end == {"kind": "end", "calls": 0, "client_initialized": False, "tool_listed": False, "note": "tool not reached"}


def test_close_log_drops_a_torn_tail_and_writes_a_missing_header_first(tmp_path):
    path = tmp_path / "scripted-user.jsonl"
    path.write_text(json.dumps(INIT) + "\n" + '{"kind":"ca', encoding="utf-8")
    end = sulog.close_log(path, header={"kind": "header", "task": "from-plan"})
    assert _rows(path) == [{"kind": "header", "task": "from-plan"}, INIT, end]
    assert end["torn_tail"] is True


# --- T-39-3b: a re-grade under the same matcher version reads the stored decision and never re-matches ---

def _stored_call(question: str, decision: dict, cset, version: str = matcher.MATCHER_VERSION) -> dict:
    return {"kind": "call", "seq": 1, "question": question, "question_sha256": matcher.question_sha256(question),
            "clarifications_sha256": cset.sha256, "matcher_version": version, "decision": decision}


def test_t39_3b_regrade_reads_stored_decisions():
    cset = clar.load(Z0)
    # A stored decision the current table would not make: only a read of the store can return it.
    stored = {"clarification": "order-ascending", "rung": "exact"}
    store = sulog.stored_decisions([HEADER, _stored_call("What is the minimum input size?", stored, cset)])
    assert store == {matcher.cache_key("What is the minimum input size?", cset.sha256): stored}
    assert sulog.decide("What is the minimum input size?", cset, store) == stored


def test_t39_3b_another_matcher_version_is_a_new_decision_under_its_own_key():
    cset = clar.load(Z0)
    stored = {"clarification": "order-ascending", "rung": "exact"}
    store = sulog.stored_decisions([_stored_call("What is the minimum input size?", stored, cset, "t0-older")])
    assert sulog.decide("What is the minimum input size?", cset, store) == {"clarification": None, "rung": "none"}


def test_two_stored_decisions_for_one_key_are_refused():
    cset = clar.load(Z0)
    rows = [_stored_call("q", {"clarification": None, "rung": "none"}, cset),
            {**_stored_call("q", {"clarification": "size-bound", "rung": "exact"}, cset), "seq": 2}]
    with pytest.raises(BenchError) as caught:
        sulog.stored_decisions(rows)
    assert (caught.value.code, caught.value.message) == ("HB-USR-002", "call seq 2: a second decision for one match key")


# --- the stdio MCP server (design section 6, R-37, R-51) ---

def _server(tmp_path: Path, clock=None) -> tuple[server.Server, Path]:
    path = tmp_path / "scripted-user.jsonl"
    writer = sulog.LogWriter(path, clock=clock) if clock else sulog.LogWriter(path)
    return server.Server(clar.load(Z0), writer), path


def _request(rid: int, method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "method": method, **({"params": params} if params is not None else {})}


def _ask(rid: int, arguments) -> dict:
    return _request(rid, "tools/call", {"name": "ask_user", "arguments": arguments})


def test_t37_0_server_lists_exactly_ask_user(tmp_path):
    srv, path = _server(tmp_path)
    init = srv.handle(_request(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                                 "clientInfo": {"name": "codex", "version": "0.156.0"}}))
    assert init == {"jsonrpc": "2.0", "id": 1, "result": {
        "protocolVersion": "2025-11-25", "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "scripted_user", "version": matcher.MATCHER_VERSION}}}
    listed = srv.handle(_request(2, "tools/list"))
    assert [t["name"] for t in listed["result"]["tools"]] == ["ask_user"]
    assert listed["result"]["tools"][0]["inputSchema"] == {
        "type": "object", "properties": {"question": {"type": "string", "description": "The question for the user."}},
        "required": ["question"]}
    for method in ("resources/list", "prompts/list", "server/discover"):
        assert srv.handle(_request(3, method))["error"]["code"] == -32601
    assert srv.handle(_ask(4, {"question": "q"}) | {"params": {"name": "other", "arguments": {}}})["error"]["code"] == -32602
    assert srv.handle(_request(5, "ping")) == {"jsonrpc": "2.0", "id": 5, "result": {}}
    assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert [r["kind"] for r in _rows(path)] == ["initialize", "tools_listed"]  # the refused tool call wrote no row


def test_t37_r_server_replies_with_the_clarification_text_or_the_exact_default(tmp_path):
    srv, _ = _server(tmp_path)
    for rid, question, text in [(1, ORDER.question, "Yes, ascending."), (2, "Is the order stable?", DEFAULT)]:
        assert srv.handle(_ask(rid, {"question": question})) == {
            "jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}], "isError": False}}


@pytest.mark.parametrize("arguments, reason", [
    ({"question": 42}, "not a string"),
    ({}, "not a string"),
    (None, "not a string"),
    ({"question": ""}, "empty"),
    ({"question": " ? "}, "empty after normalise"),
    ({"question": "a\ud800b"}, "lone surrogate"),
], ids=["number", "missing", "no-arguments", "empty", "empty-after-normalise", "lone-surrogate"])
def test_t37_6a_invalid_question_gets_default_and_is_logged(tmp_path, arguments, reason):
    srv, path = _server(tmp_path)
    out = srv.handle(_ask(1, arguments))
    assert out["result"] == {"content": [{"type": "text", "text": DEFAULT}], "isError": False}
    (row,) = _rows(path)
    assert (row["invalid"], row["decision"], row["reply"]) == (reason, {"clarification": None, "rung": "none"}, DEFAULT)


@pytest.mark.parametrize("requested, answered", [
    ("2025-11-25", "2025-11-25"),
    ("2025-06-18", "2025-06-18"),
    ("2024-11-05", "2025-11-25"),
    (None, "2025-11-25"),
])
def test_t37_6b_protocol_version_negotiation(tmp_path, requested, answered):
    srv, path = _server(tmp_path)
    params = {"protocolVersion": requested} if requested else {}
    assert srv.handle(_request(1, "initialize", params))["result"]["protocolVersion"] == answered
    assert _rows(path)[0] == {"kind": "initialize", "client": None, "protocol_version": answered,
                              "requested_protocol_version": requested}


class SpyOut:
    """An output stream that records, at each send, how many log rows are already on disk."""

    def __init__(self, log: Path) -> None:
        self.log, self.sent = log, []

    def write(self, data: bytes) -> None:
        self.sent.append((json.loads(data), len(_rows(self.log))))

    def flush(self) -> None:
        pass


def test_t37_4a_log_row_per_call_before_reply(tmp_path):
    srv, path = _server(tmp_path)
    lines = [json.dumps(_ask(1, {"question": ORDER.question})), "not json", "[1]", "",
             json.dumps(_ask(2, {"question": "Anything else?"}))]
    out = SpyOut(path)
    server.serve(srv, io.BytesIO(("\n".join(lines) + "\n").encode()), out)
    assert [(msg["id"], rows_on_disk) for msg, rows_on_disk in out.sent] == [(1, 1), (2, 2)]
    assert [(r["seq"], r["reply"]) for r in _rows(path)] == [(1, "Yes, ascending."), (2, DEFAULT)]


def test_entry_is_the_acp_stdio_shape_without_type(tmp_path):
    log_path = tmp_path / "scripted-user.jsonl"
    assert server.entry(Z0, log_path, python="C:/py/python.exe") == {
        "name": "scripted_user", "command": "C:/py/python.exe",
        "args": ["-m", "harness_bench.scripted_user.server", str(Z0), str(log_path)],
        "env": [{"name": "SCRIPTED_USER_LOG", "value": str(log_path)}]}


@pytest.mark.parametrize("items, reason", [
    ([_item(), _item(id="q2", question="IS IT ONE")],
     "clarifications[1].question normalises to the same text as clarifications[0]: ambiguous"),
    ([_item(question="?")], "clarifications[0].question is empty after normalise"),
], ids=["ambiguous", "empty-after-normalise"])
def test_t37_6c_server_refuses_ambiguous_or_empty_clarifications(tmp_path, monkeypatch, items, reason):
    monkeypatch.delenv("SCRIPTED_USER_LOG", raising=False)
    bad, log_path = _write(tmp_path, _doc(clarifications=items)), tmp_path / "scripted-user.jsonl"
    out = io.BytesIO()
    assert server.main([str(bad), str(log_path)], io.BytesIO(json.dumps(_request(1, "initialize")).encode() + b"\n"), out) == 2
    assert out.getvalue() == b""  # never answers, so the tool is never listed: "tool not reached"
    assert _rows(log_path) == [{"kind": "refused", "code": "HB-USR-002", "message": f"{bad}: {reason}"}]


def test_server_refuses_a_missing_clarification_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SCRIPTED_USER_LOG", raising=False)
    missing, log_path = tmp_path / "absent.yaml", tmp_path / "scripted-user.jsonl"
    assert server.main([str(missing), str(log_path)], io.BytesIO(b""), io.BytesIO()) == 2
    assert _rows(log_path) == [{"kind": "refused", "code": "HB-USR-002", "message": f"{missing}: cannot be read"}]


def test_server_refuses_when_this_python_gives_another_matcher_version(tmp_path, monkeypatch):
    monkeypatch.delenv("SCRIPTED_USER_LOG", raising=False)
    monkeypatch.setattr(matcher.unicodedata, "unidata_version", "0.0.0")
    other = matcher.compute_matcher_version()
    log_path = tmp_path / "scripted-user.jsonl"
    assert server.main([str(Z0), str(log_path)], io.BytesIO(b""), io.BytesIO()) == 2
    assert _rows(log_path) == [{"kind": "refused", "code": "HB-USR-002", "message":
                                f"matcher_version mismatch: this Python gives {other}, the committed constant is "
                                f"{matcher.MATCHER_VERSION}"}]


def test_server_usage_needs_exactly_two_arguments(tmp_path):
    assert server.main([str(Z0)], io.BytesIO(b""), io.BytesIO()) == 2


def test_the_log_argument_is_the_fallback_for_the_env(tmp_path, monkeypatch):
    env_log, arg_log = tmp_path / "env.jsonl", tmp_path / "arg.jsonl"
    monkeypatch.setenv("SCRIPTED_USER_LOG", str(env_log))
    assert server.main([str(Z0), str(arg_log)], io.BytesIO(b""), io.BytesIO()) == 0
    monkeypatch.delenv("SCRIPTED_USER_LOG")
    assert server.main([str(Z0), str(arg_log)], io.BytesIO(b""), io.BytesIO()) == 0
    assert [r["log_source"] for r in _rows(env_log)] == ["env"]
    assert [r["log_source"] for r in _rows(arg_log)] == ["arg"]


def test_stdio_server_over_pipes(tmp_path):
    """Offline: the module the bench launches (server.entry), driven over real pipes with one exchange per line."""
    log_path = tmp_path / "scripted-user.jsonl"
    spec = server.entry(Z0, log_path)
    env = {**os.environ, **{e["name"]: e["value"] for e in spec["env"]}}
    messages = [
        _request(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "pipe-test", "version": "1"}}),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        _request(2, "tools/list"),
        _ask(3, {"question": "what is the MAXIMUM input size"}),
    ]
    proc = subprocess.Popen([spec["command"], *spec["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=tmp_path)
    stdout, stderr = proc.communicate("".join(json.dumps(m) + "\n" for m in messages).encode(), timeout=60)
    assert (proc.returncode, stderr) == (0, b"")
    replies = [json.loads(line) for line in stdout.decode().splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert [t["name"] for t in replies[1]["result"]["tools"]] == ["ask_user"]
    assert replies[2]["result"] == {"content": [{"type": "text", "text": "At most 100000 items."}], "isError": False}
    rows = _rows(log_path)
    assert [r["kind"] for r in rows] == ["header", "initialize", "tools_listed", "call"]
    assert (rows[0]["log_source"], rows[0]["clarifications_sha256"]) == ("env", hashlib.sha256(Z0.read_bytes()).hexdigest())
    assert rows[1]["client"] == {"name": "pipe-test", "version": "1"}
    assert (rows[3]["question"], rows[3]["decision"], rows[3]["reply"]) == (
        "what is the MAXIMUM input size", {"clarification": "size-bound", "rung": "normalised"}, "At most 100000 items.")
    assert sulog.close_log(log_path, header={}) == {"kind": "end", "calls": 1, "client_initialized": True,
                                                    "tool_listed": True}
