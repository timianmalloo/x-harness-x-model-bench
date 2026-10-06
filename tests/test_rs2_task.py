"""Tests for the resilience task RS2 (structlog, a batching log shipper; W1-L rev 2 section 9.3, Erratum 1; X-RS, E4).

One-time authoring proofs, not a push ring: the base is built through the engine's own `workspace.task_source` (a cached
upstream clone), the hidden tests run through the real `correctness.grade` (W1-L assume A3: a loopback socket in the
grading copy), and `check.py` runs through the real `property.run_check` and the real `bench_check` probe host with a
real `bench_check.listen` (X-LB1) and the real `property.parse_result` with `FAULT_OUTCOMES`.

The variants reader below applies W0 section 2's rules locally (X-E's `read_variants` is not in `src/`).
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import ring_cache

from harness_bench import config
from harness_bench.grade import _env, correctness
from harness_bench.grade import property as prop

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "RS2"
FILE = "src/structlog/shipper.py"
HIDDEN = frozenset({
    "test_processor_returns_event_dict_unchanged_and_buffers_a_copy", "test_flush_returns_the_accepted_count_and_empties_the_buffer",
    "test_a_refused_batch_raises_ship_error", "test_an_empty_buffer_sends_nothing",
    "test_records_are_sent_in_the_order_they_were_buffered"})
CASES = ["g-5xx-burst", "g-5xx-persistent", "g-slow-first", "g-hang", "g-lost-response", "g-4xx", "g-lost-then-grow", "g-ordering"]
# The independent oracle for the variants (K1's re-trace, hand-traced before any run): flipped case -> deciding clause.
PREDICTED = {
    "noretry": {"g-5xx-burst": "effect"},
    "notimeout": {"g-hang": "time", "g-slow-first": "time"},
    "retry5": {"g-5xx-persistent": "requests", "g-hang": "requests", "g-lost-then-grow": "requests", "g-ordering": "requests"},
    "batchidattempt": {"g-lost-response": "effect", "g-lost-then-grow": "effect", "g-slow-first": "effect"},
    "clearearly": {"g-5xx-persistent": "result", "g-lost-then-grow": "result", "g-ordering": "result"},
    "requeuetail": {"g-lost-then-grow": "result", "g-ordering": "result"},
    "retry4xx": {"g-4xx": "requests"},
    "growid": {"g-lost-then-grow": "result"},
}
STUB = (
    "class ShipError(Exception):\n    pass\n\n\nclass HttpShipper:\n    def __init__(self, base_url):\n        pass\n\n"
    '    def processor(self, logger, name, event_dict):\n        return "RS2-STUB-SENTINEL"\n\n'
    '    def flush(self):\n        return "RS2-STUB-SENTINEL"\n')
WORK = Path(tempfile.mkdtemp(prefix="rs2-"))
_counter = iter(range(10**6))
_checks: dict[str, dict] = {}


def teardown_module(module):
    shutil.rmtree(WORK, ignore_errors=True)


@pytest.fixture(scope="session")
def base() -> Path:
    try:
        return ring_cache.cached_base(TASK, "rs2")
    except Exception as exc:  # noqa: BLE001 - an unreachable upstream skips, unless the ring is required
        import os
        if os.environ.get("HB_REQUIRE_RS_BASE") == "1":
            pytest.fail(f"HB_REQUIRE_RS_BASE=1 but the RS2 base cannot be built: {exc}")
        pytest.skip(f"cannot build the RS2 base from the pinned upstream: {exc}")


def overlay(role: str) -> dict[str, str]:
    root = TASK / "oracle" / "solutions" / role
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}


def tree_with(base: Path, files: dict[str, str]) -> Path:
    ws = WORK / f"ws-{next(_counter)}"
    shutil.copytree(base, ws, ignore=shutil.ignore_patterns(".git"))
    for rel, text in files.items():
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return ws


# ---- the variant and wrong-app readers (W0 section 2 rules, applied locally until X-E's reader joins) -----------------

VARIANT_NAME = re.compile(r"^[a-z0-9]{1,16}$")


def read_literal(path: Path, name: str) -> dict:
    """Exactly one top-level `name = <literal>` assignment, read with ast.literal_eval; the file is never executed."""
    text = path.read_text(encoding="utf-8")
    assert len(text.encode()) <= 64 * 1024, f"{path.name} is over 64 KiB"
    assigns = [n for n in ast.parse(text).body if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))]
    assert len(assigns) == 1 and isinstance(assigns[0], ast.Assign), f"{path.name} needs exactly one plain top-level assignment"
    assert [t.id for t in assigns[0].targets] == [name]
    return ast.literal_eval(assigns[0].value)


def variant_problems(variants: dict, reference: dict[str, str]) -> list[str]:
    problems = []
    for name, spec in variants.items():
        if not VARIANT_NAME.match(name):
            problems.append(f"{name}: name outside ^[a-z0-9]{{1,16}}$")
        if set(spec) != {"flips", "clauses", "edits"}:
            problems.append(f"{name}: keys {sorted(spec)}")
            continue
        for edit in spec["edits"]:
            if set(edit) != {"file", "old", "new"}:
                problems.append(f"{name}: edit keys {sorted(edit)}")
            elif edit["old"] == "":
                if edit["file"] in reference:
                    problems.append(f"{name}: create form on a file the reference overlay holds: {edit['file']}")
            elif edit["file"] not in reference:
                problems.append(f"{name}: {edit['file']} is not in the reference overlay")
            elif reference[edit["file"]].count(edit["old"]) != 1:
                problems.append(f"{name}: old text occurs {reference[edit['file']].count(edit['old'])} times in {edit['file']}")
    return problems


def apply_edits(reference: dict[str, str], spec: dict) -> dict[str, str]:
    files = dict(reference)
    for edit in spec["edits"]:
        files[edit["file"]] = edit["new"] if edit["old"] == "" else files[edit["file"]].replace(edit["old"], edit["new"])
    return files


# ---- the hidden tests through the real correctness grader -----------------------------------------------------------

def hidden_run(base: Path, files: dict[str, str]):
    """(Result, passed ids, failed ids, errored ids) of the hidden tests on base + `files`, via `correctness.grade`."""
    ws = tree_with(base, files)
    out = WORK / f"out-{next(_counter)}"
    out.mkdir()
    result = correctness.grade(ws, TASK, config.load_yaml(TASK / "task.yaml")["oracle"], out, WORK, 180,
                               work_dir=WORK / f"w-{next(_counter)}")
    log = (out / "oracle.log").read_text(encoding="utf-8")
    seen = {}
    for chunk in re.split(r"^(?=test_\w+ \()", log, flags=re.MULTILINE):  # a warning may sit between a name and its status
        head, states = re.match(r"(test_\w+) \(", chunk), re.findall(r"(?:\.\.\. |^)(ok|FAIL|ERROR)\s*$", chunk, re.MULTILINE)
        if head and states:
            seen[head.group(1)] = states[-1]
    return (result, frozenset(k for k, v in seen.items() if v == "ok"), frozenset(k for k, v in seen.items() if v == "FAIL"),
            frozenset(k for k, v in seen.items() if v == "ERROR"))


# ---- the check through the real run_check and probe host, with the real listener --------------------------------

def check_run(base: Path, name: str, files: dict[str, str]) -> dict:
    """{'outcomes': {case: outcome}, 'ms': {case: duration_ms}, 'clauses': {case: clause}, 'measures': {...}, 'calls': {...}}."""
    if name in _checks:
        return _checks[name]
    run = WORK / f"c{next(_counter)}"
    deliverable = run / "deliverable"
    shutil.copytree(tree_with(base, files), deliverable)
    check_dir = run / "check"
    shutil.copytree(TASK / "oracle" / "check", check_dir, ignore=shutil.ignore_patterns("__pycache__"))
    (check_dir / "bench_check.py").write_bytes(prop.BENCH_CHECK.read_bytes())
    spec = config.load_yaml(TASK / "oracle" / "check" / "cases.yaml")
    (check_dir / "cases.json").write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    evidence = run / "evidence"
    import sys
    argv = [sys._base_executable, "-S", "check/check.py", "--deliverable", str(deliverable.resolve()),
            "--cases", "check/cases.json", "--seed", "1", "--evidence", str(evidence.resolve())]
    evidence.mkdir()
    got = prop.run_check(argv, run, _env.grading_env([]), 90.0, run / "stderr.txt",
                        lambda line: prop.parse_result(line, [str(c["id"]) for c in spec["cases"]], prop._FAULT_MEASURES,
                                                       {"idempotency_violations": None}, prop.FAULT_OUTCOMES))
    stderr = (run / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    assert got.document is not None, (got.invalid, got.exit_code, stderr[-800:])
    doc = got.document
    clauses_file = evidence / "clauses.json"
    out = {"outcomes": {c["id"]: c["outcome"] for c in doc["cases"]}, "ms": {c["id"]: c["duration_ms"] for c in doc["cases"]},
           "clauses": json.loads(clauses_file.read_text(encoding="utf-8")), "measures": doc["measures"],
           "calls": json.loads((evidence / "rs2-calls.json").read_text(encoding="utf-8"))}
    _checks[name] = out
    return out


def flipped(got: dict) -> dict[str, str]:
    return {c: got["clauses"][c] for c, o in got["outcomes"].items() if o != "passed"}


# ---- text checks ----------------------------------------------------------------------------------------------------

def test_prompt_has_no_latent_term():
    terms = config.load_yaml(TASK / "task.yaml")["property"]["latent_terms"]
    prompt = (TASK / "prompt.md").read_text(encoding="utf-8").lower()
    assert [t for t in terms if str(t).lower() in prompt] == []
    assert "3 seconds" in prompt and "at most 3 requests" in prompt  # the numbers are in the prompt, the mechanisms are not


def test_fault_contract_is_one_literal_in_task_and_cases():
    cases = config.load_yaml(TASK / "oracle" / "check" / "cases.yaml")
    task = config.load_yaml(TASK / "task.yaml")
    assert cases["fault_contract"] == task["property"]["fault_contract"] == {"timeout_ms": 3000, "tolerance_ms": 500, "max_retries": 2}
    assert [c["id"] for c in cases["cases"]] == CASES
    assert all(c["kind"] == "fault" for c in cases["cases"]) and cases["interface"] == "loopback"
    waiting = {c["id"] for c in cases["cases"] if c.get("bound_ms") == 4500}
    assert waiting == {"g-slow-first", "g-hang"}


def test_variants_load_by_literal_eval_and_obey_the_edit_rules():
    variants = read_literal(TASK / "oracle" / "variants.py", "VARIANTS")
    assert set(variants) == set(PREDICTED), "R2-1 names: no v-, no hyphen"
    assert variant_problems(variants, overlay("reference")) == []
    for name, spec in variants.items():
        assert spec["clauses"] == PREDICTED[name] and sorted(spec["flips"]) == sorted(PREDICTED[name]), name
    reference = overlay("reference")
    bad = {
        "v-noretry": {"flips": [], "clauses": {}, "edits": []},
        "twice": {"flips": [], "clauses": {}, "edits": [{"file": FILE, "old": "\n", "new": "x"}]},
        "create": {"flips": [], "clauses": {}, "edits": [{"file": FILE, "old": "", "new": "x"}]},
        "absent": {"flips": [], "clauses": {}, "edits": [{"file": "nope.py", "old": "x", "new": "y"}]},
        "extra": {"flips": [], "clauses": {}, "edits": [], "note": "x"},
    }
    assert len(variant_problems(bad, reference)) == 5
    scratch = WORK / "lit.py"
    scratch.write_text("VARIANTS = {}\nVARIANTS = {}\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        read_literal(scratch, "VARIANTS")


# ---- the hidden tests -----------------------------------------------------------------------------------------------

def test_rs2_stub_fails_every_hidden_test(base):
    """R2-7: the sentinel stub turns every hidden test red, by assertion (so its loopback server also ran in the grading copy)."""
    result, passed, failed, errored = hidden_run(base, {FILE: STUB})
    assert (passed, errored) == (frozenset(), frozenset()), (passed, errored)
    assert failed == HIDDEN
    assert result.passed == 0 and result.partial_credit == Decimal(0)


def test_hidden_tests_pass_on_reference_naive_and_alt(base):
    """W1-L assume A3: hidden tests use loopback sockets in the grading copy, through the real correctness grader."""
    for role in ("reference", "naive", "alt"):
        result, passed, failed, errored = hidden_run(base, overlay(role))
        assert (passed, failed, errored) == (HIDDEN, frozenset(), frozenset()), (role, failed, errored)
        assert result.passed == 1


def test_each_wrong_app_turns_exactly_its_reds_red(base):
    declared = read_literal(TASK / "oracle" / "wrong_apps.py", "WRONG_APPS")
    reference = overlay("reference")
    assert set().union(*(set(w["reds"]) for w in declared.values())) == HIDDEN  # every hidden test has a wrong app
    for name, wrong in declared.items():
        files = apply_edits(reference, wrong)
        assert files != reference, f"{name} carries no edit"
        _, passed, failed, errored = hidden_run(base, files)
        assert errored == frozenset(), (name, errored)  # an assertion, never an import or runtime error
        assert failed == frozenset(wrong["reds"]), (name, failed)
        assert passed == HIDDEN - failed


# ---- the fault cases ------------------------------------------------------------------------------------------------

def test_reference_passes_every_case_and_alt_agrees(base):
    for role in ("reference", "alt"):
        got = check_run(base, role, overlay(role))
        assert got["outcomes"] == dict.fromkeys(CASES, "passed"), (role, got["outcomes"], got["clauses"])
        assert got["measures"] == {"idempotency_violations": 0}


def test_naive_passes_four_of_eight(base):
    got = check_run(base, "naive", overlay("naive"))
    passing = sorted(c for c, o in got["outcomes"].items() if o == "passed")
    assert passing == ["g-4xx", "g-5xx-persistent", "g-lost-response", "g-ordering"], got["outcomes"]
    assert len(passing) / len(CASES) == pytest.approx(0.5, abs=0.0001)


def test_each_variant_passes_the_hidden_tests_and_flips_exactly_its_cases_and_clause(base):
    variants = read_literal(TASK / "oracle" / "variants.py", "VARIANTS")
    reference = overlay("reference")
    for name, spec in variants.items():
        files = apply_edits(reference, spec)
        assert files != reference, f"{name} carries no edit"
        result, passed, failed, errored = hidden_run(base, files)
        assert (passed, failed, errored, result.passed) == (HIDDEN, frozenset(), frozenset(), 1), (name, failed, errored)
        got = check_run(base, name, files)
        assert flipped(got) == PREDICTED[name], (name, got["outcomes"], got["clauses"], got["calls"])


def test_every_case_has_a_flipping_variant_and_batchidattempt_counts_two_violations(base):
    assert {c for flips in PREDICTED.values() for c in flips} == set(CASES)
    assert check_run(base, "batchidattempt", apply_edits(overlay("reference"), read_literal(TASK / "oracle" / "variants.py", "VARIANTS")["batchidattempt"]))[
        "measures"] == {"idempotency_violations": 10}


def test_a_delivery_that_reapplies_records_counts_one_not_one_per_record(base):
    """CR47-8: idempotency_violations counts deliveries. The naive's one re-send on g-lost-then-grow re-applies r1 and r2: 1, not 2."""
    got = check_run(base, "naive", overlay("naive"))
    assert got["measures"] == {"idempotency_violations": 1}
