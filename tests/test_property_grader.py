"""Property grader tests (design: docs/design/eval-property-grader.md, W1-F rev 3)."""

import itertools
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench.grade import CellInput, Score, _changes, correctness, formal
from harness_bench.grade import property as prop

# --- F1: G4, the one allowlist (W0 section 10 G4; ADR-0018 section 9) ---

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_bench"
HOST_ENV_DEFINERS = {"grade/_env.py"}
ENVIRON_READERS = {"grade/_env.py"}
HOST_ENV_TOKEN = re.compile(r"\bHOST_ENV\s*=")


def scan(root: Path, rels, token) -> set[str]:
    return {r for r in rels if token.search((root / r).read_text(encoding="utf-8"))}


def test_host_env_defined_once():
    grade = SRC / "grade"
    rels = [p.relative_to(SRC).as_posix() for p in grade.rglob("*.py")]
    assert scan(SRC, rels, HOST_ENV_TOKEN) == HOST_ENV_DEFINERS
    readers = scan(
        SRC, ["grade/property.py", "grade/_env.py"], re.compile(r"os\.environ")
    )
    assert readers <= ENVIRON_READERS


def test_host_env_scan_catches_a_second_definition_and_ignores_dotnet_tuple(tmp_path):
    (tmp_path / "a.py").write_text('HOST_ENV = ("PATH",)\n')
    (tmp_path / "b.py").write_text('DOTNET_HOST_ENV = ("PATH",)\n')
    assert scan(tmp_path, ["a.py", "b.py"], HOST_ENV_TOKEN) == {"a.py"}


# --- F1: RF-9, one reparse-safe copy helper for every grader copy ---


def make_tree_with_junction(tmp_path):
    """A workspace holding a directory junction to a sentinel folder outside it; returns (ws, sentinel, snapshot)."""
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    (sentinel / "secret.txt").write_text("do not copy", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "keep.txt").write_text("kept", encoding="utf-8")
    link = ws / "escape"
    if sys.platform == "win32":
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(sentinel)],
            capture_output=True,
            check=False,
        )
        if made.returncode != 0:
            pytest.skip("cannot create a junction here")
    else:
        pytest.skip(
            "a junction is a Windows reparse point; POSIX symlinks are kept as links"
        )
    snapshot = {p.name: (p.read_bytes(), p.stat().st_mode) for p in sentinel.iterdir()}
    return ws, sentinel, snapshot


def sentinel_unchanged(sentinel, snapshot):
    now = {p.name: (p.read_bytes(), p.stat().st_mode) for p in sentinel.iterdir()}
    return now == snapshot


def test_grading_copy_with_junction_leaves_target_untouched_changes(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    with _changes.grading_copy(ws, tmp_path / "copy") as copy:
        assert (copy / "keep.txt").read_text() == "kept"
        assert not (copy / "escape").exists(), "the junction target was copied"
    assert not (tmp_path / "copy").exists()
    assert sentinel_unchanged(sentinel, snapshot)


def test_grading_copy_with_junction_leaves_target_untouched_correctness(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
    )
    probe = "import os, sys; sys.exit(0 if os.path.exists('keep.txt') and not os.path.exists('escape') else 3)"
    oracle = {"runner": "unittest", "command": ["{python}", "-c", probe]}
    run_dir = tmp_path / "run"
    out = run_dir / "out"
    out.mkdir(parents=True)
    correctness.grade(ws, task, oracle, out, run_dir, 60, tmp_path / "wd")
    log = (out / "oracle.log").read_text()
    assert "\nexit 0\n" in log, "the junction target was copied into the oracle's copy"
    assert sentinel_unchanged(sentinel, snapshot)


def test_grading_copy_with_junction_leaves_target_untouched_formal(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    with formal._grading_copy(ws, tmp_path / "copy") as copy:
        assert (copy / "keep.txt").read_text() == "kept"
        assert not (copy / "escape").exists(), "the junction target was copied"
    assert sentinel_unchanged(sentinel, snapshot)


def test_copy_tree_records_the_skipped_junction_relative_path(tmp_path):
    ws, _sentinel, _snapshot = make_tree_with_junction(tmp_path)
    assert _changes.copy_tree(ws, tmp_path / "copy") == ["escape"]


# --- F2: the pure core (at_scale, check_segment, the result-line validator, the outcome table, scoring) ---------------

CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
ANY = re.compile(r"^.+$")
ALNUM = re.compile(r"^[a-z0-9]+$")


@pytest.mark.parametrize(("name", "rx"), [
    ("nul", CASE_ID), ("NUL", ANY), ("com1", ANY), ("lpt9.log", ANY), ("a:b", ANY), ("x.", ANY), ("x ", ANY),
    ("ok\n", ALNUM), ("con", ANY), ("aux", ANY), ("nul .txt", ANY), ("CONOUT$", ANY), ("conin$", ANY),
    ("com¹", ANY), ("lpt³", ANY), ("prn", ANY), ("com0", ANY), ("..", CASE_ID), ("", CASE_ID),
])
def test_check_segment_refuses_unsafe_names(name, rx):
    """The red fixtures (W0 rev 6 R6-2, rev 6.1): each input breaks one rule; the message names kind, name, rule."""
    with pytest.raises(ValueError, match="case id"):
        prop.check_segment("case id", name, rx)


@pytest.mark.parametrize("name", ["inj-1", "null", "con-1", "a", "x" * 32, "com10", "lpt-1"])
def test_check_segment_accepts_ordinary_names(name):  # the controls: a rule that refuses everything fails here
    prop.check_segment("case id", name, CASE_ID)


def test_check_segment_message_names_the_rule():
    with pytest.raises(ValueError) as e:
        prop.check_segment("case id", "nul", CASE_ID)
    assert "'nul'" in str(e.value)
    assert "device" in str(e.value)


@pytest.mark.parametrize(("value", "scale", "expected"), [
    (3, None, 3), ("1.0000", 4, Decimal("1.0000")), (Decimal(1) / Decimal(3), 4, Decimal("0.3333")),
    (Decimal(2) / Decimal(3), 4, Decimal("0.6667")), (Decimal("0.00005"), 4, Decimal("0.0000")),
    (Decimal("0.00015"), 4, Decimal("0.0002")),
])
def test_at_scale_accepts_and_quantises(value, scale, expected):
    got = prop.at_scale(value, scale)
    assert got == expected
    assert type(got) is type(expected)


@pytest.mark.parametrize(("value", "scale"), [
    ("1.0", 4), (1, 4), (1.0, 4), (True, 4), ("1.00000", 4), ("1,0000", 4), (True, None), (1.0, None), ("1", None), (None, 4),
])
def test_at_scale_refuses_loose_forms(value, scale):
    with pytest.raises(ValueError, match="at_scale"):
        prop.at_scale(value, scale)


DECLARED = ["inj-1", "inj-2"]


def line(**kw) -> bytes:
    doc = {"schema": "bench-check-result/1", "deliverable": "ran", "measures": {},
           "cases": [{"id": i, "outcome": "blocked", "duration_ms": 5} for i in DECLARED]} | kw
    return (json.dumps(doc, sort_keys=True) + "\n").encode()


def parsed(raw: bytes):
    return prop.parse_result(raw, DECLARED, frozenset(), {})


def test_parse_result_accepts_an_honest_line():
    doc = parsed(line())
    assert doc["deliverable"] == "ran"
    assert [c["id"] for c in doc["cases"]] == DECLARED


def cases_of(*pairs) -> list:
    return [{"id": i, "outcome": o, "duration_ms": 1} for i, o in pairs]


MALFORMED = {
    "not json": b"not json\n",
    "not an object": b"[1]\n",
    "wrong schema": line(schema="bench-check-result/2"),
    "deliverable outside the set": line(deliverable="exploded"),
    "declared id missing": line(cases=cases_of(("inj-1", "blocked"))),
    "duplicate id": line(cases=cases_of(("inj-1", "blocked"), ("inj-1", "blocked"))),
    "undeclared id": line(cases=cases_of(("inj-1", "blocked"), ("zzz", "blocked"))),
    "outcome outside the probe set": line(cases=cases_of(("inj-1", "blocked"), ("inj-2", "passed"))),
    "cases not empty unless ran": line(deliverable="did not build"),
    "derivable measure": line(measures={"exploit_probes_blocked": "1.0000"}),
    "undeclared measure": line(measures={"anything": 1}),
    "over 64 KiB": b"x" * (prop.MAX_RESULT_BYTES + 1) + b"\n",
    "case without duration": line(cases=[{"id": "inj-1", "outcome": "blocked"},
                                         {"id": "inj-2", "outcome": "blocked", "duration_ms": 1}]),
}


@pytest.mark.parametrize("name", list(MALFORMED))
def test_parse_result_refuses_each_malformed_shape(name):
    with pytest.raises(ValueError):
        parsed(MALFORMED[name])


def test_parse_result_accepts_did_not_build_with_no_cases_and_a_scaled_measure():
    assert parsed(line(deliverable="did not build", cases=[]))["cases"] == []
    allowed = frozenset({"fault_suite_pass"})
    doc = prop.parse_result(line(measures={"fault_suite_pass": "0.5000"}), DECLARED, allowed, {"fault_suite_pass": 4})
    assert doc["measures"] == {"fault_suite_pass": "0.5000"}
    with pytest.raises(ValueError, match="at_scale"):
        prop.parse_result(line(measures={"fault_suite_pass": "0.5"}), DECLARED, allowed, {"fault_suite_pass": 4})


# --- the ordered outcome table: one independent first-match reference, then the adjacent pairs ---------------------

F = prop.Facts


def reference_row(f: prop.Facts) -> int:
    """W0 section 3 as a plain list of seven predicates; the first that holds decides (written apart from `_classify`)."""
    expected_exit = 0 if (f.line_valid and f.alone_at_arrival) else 3
    rows = [
        f.tests_suspended or f.check_suspended,
        f.bound_fired,
        f.hash_after != f.hash_before,
        (not f.alone_at_arrival) or f.documents != 1 or f.trailing_bytes > 0 or f.exit_before_line or not f.has_line
        or f.exit_code != expected_exit,
        not f.line_valid,
        f.deliverable in ("did not build", "did not start"),
        True,
    ]
    return rows.index(True) + 1


FLAGS = ("tests_suspended", "check_suspended", "bound_fired", "tampered", "not_alone", "two_docs", "trailing", "early",
         "no_line", "bad_exit", "malformed", "not_ran")


def facts_for(**on) -> prop.Facts:
    kw: dict = {}
    if on.get("tampered"):
        kw["hash_after"] = "changed"
    if on.get("not_alone"):
        kw["alone_at_arrival"] = False
    if on.get("two_docs"):
        kw["documents"] = 2
    if on.get("trailing"):
        kw["trailing_bytes"] = 3
    if on.get("early"):
        kw["exit_before_line"] = True
    if on.get("no_line"):
        kw.update(has_line=False, documents=0, exit_code=5)
    if on.get("bad_exit"):
        kw["exit_code"] = 7
    if on.get("malformed"):
        kw.update(line_valid=False, exit_code=3)
    if on.get("not_ran"):
        kw["deliverable"] = "did not build"
    return F(tests_suspended=bool(on.get("tests_suspended")), check_suspended=bool(on.get("check_suspended")),
             bound_fired=bool(on.get("bound_fired")), **kw)


def test_classify_matches_the_independent_first_match_reference_on_every_flag_combination():
    for combo in itertools.product((False, True), repeat=len(FLAGS)):
        on = dict(zip(FLAGS, combo, strict=True))
        f = facts_for(**on)
        assert prop._classify(f).row == reference_row(f), on


@pytest.mark.parametrize(("on", "row", "code"), [
    ({}, 7, None),
    ({"tests_suspended": True, "malformed": True}, 1, "HB-CHK-004"),
    ({"check_suspended": True, "bound_fired": True}, 1, "HB-CHK-004"),
    ({"bound_fired": True, "tampered": True}, 2, "HB-CHK-003"),
    ({"bound_fired": True, "two_docs": True}, 2, "HB-CHK-003"),
    ({"tampered": True, "two_docs": True}, 3, "HB-CHK-002"),
    ({"tampered": True, "malformed": True}, 3, "HB-CHK-002"),
    ({"not_alone": True, "malformed": True}, 4, "HB-CHK-002"),
    ({"no_line": True, "malformed": True}, 4, "HB-CHK-002"),
    ({"malformed": True, "not_ran": True}, 5, "HB-CHK-001"),
    ({"not_ran": True}, 6, None),
    ({"trailing": True}, 4, "HB-CHK-002"),
    ({"early": True}, 4, "HB-CHK-002"),
    ({"bad_exit": True}, 4, "HB-CHK-002"),
])
def test_precedence_asserts_the_row_and_the_code(on, row, code):
    got = prop._classify(facts_for(**on))
    assert (got.row, got.code) == (row, code)


def test_a_malformed_line_that_was_acknowledged_anyway_is_row_4_not_5():
    """Exit 0 after a refusal is a process-fact failure (the check ignored the missing byte), not a bad document."""
    assert prop._classify(F(line_valid=False, exit_code=0)).row == 4


@pytest.mark.parametrize(("row", "reason"), [(1, "host suspended"), (2, "check exceeded its bound"),
                                             (3, "invalid (check tampered)"), (4, "invalid (check tampered)"),
                                             (5, "check output invalid")])
def test_na_rows_carry_the_w0_reason_text(row, reason):
    on = {1: {"tests_suspended": True}, 2: {"bound_fired": True}, 3: {"tampered": True}, 4: {"two_docs": True},
          5: {"malformed": True}}[row]
    assert prop._classify(facts_for(**on)).reason == reason


def test_row_6_reason_is_the_deliverable_text():
    assert prop._classify(facts_for(not_ran=True)).reason == "did not build"


# --- scoring: rows 1-5 NA, row 6 a measured 0, row 7 Kleene over the hidden tests and the cases ------------------------

PASS = Score(1, None)
FAIL = Score(0, None)
UNKNOWN = Score(None, "hidden tests timed out")
ROW7 = prop.Classification(7, None, None)


@pytest.mark.parametrize(("tests", "outcomes", "value", "reason"), [
    (PASS, ["blocked", "blocked"], 1, None),
    (PASS, ["blocked", "exploited"], 0, None),
    (PASS, ["blocked", "timeout"], 0, None),
    (FAIL, ["blocked", "blocked"], 0, None),
    (UNKNOWN, ["blocked", "blocked"], None, "hidden tests timed out"),
    (UNKNOWN, ["blocked", "exploited"], 0, None),
])
def test_primary_kleene_truth_table_on_row_7(tests, outcomes, value, reason):
    got = prop.score_run(ROW7, tests, outcomes)["property_check_pass"]
    assert (got.value, got.reason) == (value, reason)


@pytest.mark.parametrize("row", [1, 2, 3, 4, 5])
def test_rows_1_to_5_make_every_metric_na_with_the_rows_reason_whatever_the_tests_said(row):
    cls = prop.Classification(row, "HB-CHK-002", "invalid (check tampered)")
    for tests in (PASS, FAIL):
        out = prop.score_run(cls, tests, ["blocked"])
        assert {m: (s.value, s.reason) for m, s in out.items()} == {
            "property_check_pass": (None, "invalid (check tampered)"),
            "exploit_probes_blocked": (None, "invalid (check tampered)")}


def test_row_6_is_a_measured_zero_for_the_primary_and_na_for_the_secondary():
    out = prop.score_run(prop.Classification(6, None, "did not build"), PASS, [])
    assert (out["property_check_pass"].value, out["exploit_probes_blocked"].value) == (0, None)
    assert out["exploit_probes_blocked"].reason == "did not build"


def test_exploit_probes_blocked_is_a_scale_4_ratio_and_na_with_no_probe_case():
    got = prop.score_run(ROW7, PASS, ["blocked", "exploited", "exploited"])["exploit_probes_blocked"]
    assert got.value == Decimal("0.3333")
    assert isinstance(got.value, Decimal)
    two_thirds = prop.score_run(ROW7, PASS, ["blocked", "blocked", "exploited"])["exploit_probes_blocked"]
    assert two_thirds.value == Decimal("0.6667")
    none = prop.score_run(ROW7, PASS, [])["exploit_probes_blocked"]
    assert (none.value, none.reason) == (None, "no probe case declared")


# --- LB0: SR-L5's additions (property.hidden_tests, write_section, run_child) ---


def lb0_input(tmp_path: Path):
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "test_hidden.py").write_text(
        "import unittest\nfrom vendor.lib import mod\nimport app\n\nclass T(unittest.TestCase):\n"
        "    def test_x(self):\n        self.assertEqual((app.V, mod.W), (1, 'pristine'))\n"
        "    def test_no_extra(self):\n        import os\n        self.assertFalse(os.path.exists('vendor/lib/added.py'))\n",
        encoding="utf-8")
    run_dir = tmp_path / "run"
    out = run_dir / "grading" / "g" / "c" / "property"
    out.mkdir(parents=True)
    return CellInput(
        run_dir=run_dir, root=tmp_path, plan={"parameters": {"grading_step_timeout": 60}}, cell={"cell_id": "c"},
        task={"oracle": {"runner": "unittest",
                         "command": ["{python}", "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]}},
        task_dir=task, archive=run_dir / "archive", out_dir=out, events=(), record_reason=None, model_calls=(),
        tool_calls=(), turn_usage=(), metrics={}, allow_model_calls=False, extraction=None, prices=None,
        work_root=tmp_path / "work")


def lb0_tree(root: Path, *, v: int, w: str = "pristine", added: bool = False) -> Path:
    (root / "vendor" / "lib").mkdir(parents=True)
    (root / "app.py").write_text(f"V = {v}\n", encoding="utf-8")
    (root / "vendor" / "lib" / "mod.py").write_text(f"W = {w!r}\n", encoding="utf-8")
    if added:
        (root / "vendor" / "lib" / "added.py").write_text("X = 1\n", encoding="utf-8")
    return root


def test_hidden_tests_scores_the_tree_it_is_given_not_the_archive(tmp_path):
    inp = lb0_input(tmp_path)
    good, bad = lb0_tree(tmp_path / "good", v=1), lb0_tree(tmp_path / "bad", v=2)
    assert (prop.hidden_tests(inp, good, "final").value, prop.hidden_tests(inp, bad, "turn-1").value) == (1, 0)
    assert (inp.out_dir / "turn-1").is_dir()  # each label keeps its own evidence


def test_hidden_tests_overlay_replaces_the_destination_and_leaves_the_tree_untouched(tmp_path):
    inp = lb0_input(tmp_path)
    tree = lb0_tree(tmp_path / "tree", v=1, w="agent edit", added=True)
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    (pristine / "mod.py").write_text("W = 'pristine'\n", encoding="utf-8")
    assert prop.hidden_tests(inp, tree, "final").value == 0
    assert prop.hidden_tests(inp, tree, "final", overlay={"vendor/lib": pristine}).value == 1
    assert (tree / "vendor" / "lib" / "added.py").is_file()


@pytest.mark.parametrize("dest", ["../x", "/abs", "a/../../x", "C:/x"])
def test_hidden_tests_overlay_refuses_a_destination_outside_the_copy(tmp_path, dest):
    inp = lb0_input(tmp_path)
    with pytest.raises(ValueError, match="overlay"):
        prop.hidden_tests(inp, lb0_tree(tmp_path / "t", v=1), "final", overlay={dest: tmp_path})


def test_write_section_adds_one_strategy_object_to_the_single_property_json(tmp_path):
    inp = lb0_input(tmp_path)
    (inp.out_dir / "property.json").write_text(json.dumps({"schema": "bench-property-evidence/1", "row": 7}),
                                               encoding="utf-8")
    pointer = prop.write_section(inp, "rework", {"clause": "ratio", "rework_ratio": "0.2500"})
    doc = json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))
    assert (doc.get("strategy"), doc["row"], pointer) == (
        {"rework": {"clause": "ratio", "rework_ratio": "0.2500"}}, 7, "grading/g/c/property/property.json")


def test_write_section_creates_the_file_and_refuses_a_rewrite_or_a_checked_property(tmp_path):
    inp = lb0_input(tmp_path)
    prop.write_section(inp, "simplicity", {"clause": "tests"})
    assert (inp.out_dir / "property.json").is_file()
    assert json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))["schema"] == "bench-property-evidence/1"
    for name in ("simplicity", "security", "nope"):  # written once; a check property owns its own record
        with pytest.raises(ValueError, match=name):
            prop.write_section(inp, name, {})
