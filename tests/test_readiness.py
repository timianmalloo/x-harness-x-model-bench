"""Readiness over discrimination records (W1-E section 8). Records here are hand-built from the real key, so each defect is
one field; the wiring partner that proves a real trial's record is accepted is test_discriminate.py (T-E1c, T-E1b).
"""

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from harness_bench import discriminate, identity, readiness
from harness_bench.errors import BenchError

_spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)  # type: ignore[union-attr]
TASK = "DISC-P"
PROBE = {"deliverable": "ran", "cases": {"p-1": "blocked", "p-2": "blocked"}, "hosts_ready": 2}
PROBE_NAIVE = {"deliverable": "ran", "cases": {"p-1": "exploited", "p-2": "exploited"}, "hosts_ready": 2}


def build(root: Path, mutate=None, *, name: str | None = None) -> Path:
    """Write a correct record for DISC-P at the current key, after `mutate(body)`; `name` overrides the file stem."""
    tv, ih = discriminate.record_key(root, TASK)
    body = {"schema": "bench-discrimination/1", "task": TASK, "task_version": tv, "identity_hash": ih, "platform": sys.platform,
            "scores": {"reference": {"pass_at_1": 1, "partial_credit": "1.0000", "property_check_pass": 1, "exploit_probes_blocked": "1.0000"},
                       "naive": {"pass_at_1": 1, "partial_credit": "1.0000", "property_check_pass": 0, "exploit_probes_blocked": "0.0000"}},
            "expected": {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "1.0000"},
                         "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.0000"}},
            "probe": {"reference": copy.deepcopy(PROBE), "naive": copy.deepcopy(PROBE_NAIVE)}, "readiness_failures": []}
    if mutate:
        mutate(body)
    folder = root / "bench" / "discrimination" / TASK
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (f"{name}.json" if name else discriminate.record_path(root, TASK).name)
    path.write_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    return path


def codes(root: Path, **kw) -> list[str]:
    return [f.code for f in readiness.record_failures(root, TASK, **kw)]


@pytest.fixture
def root(tmp_path):
    r = mt.make_root(tmp_path)
    mt.install(r, "disc_p")
    return r


def _set(path: str, value):
    def edit(body):
        node = body
        *parents, leaf = path.split(".")
        for key in parents:
            node = node[key]
        node[leaf] = value
    return edit


def test_a_correct_record_is_accepted(root):
    build(root)
    assert codes(root) == []


def test_no_record_is_hb_rdy_001_and_a_stale_one_is_named(root):
    assert codes(root) == ["HB-RDY-001"]
    build(root, name=f"{'f' * 16}-{'e' * 16}-{sys.platform}")
    failures = readiness.record_failures(root, TASK)
    assert [f.code for f in failures] == ["HB-RDY-001"]
    assert "f" * 16 in failures[0].detail


@pytest.mark.parametrize(("label", "mutate", "code", "needle"), [
    ("reference primary 0", _set("scores.reference.property_check_pass", 0), "HB-RDY-003", "property_check_pass"),
    ("reference secondary differs", _set("scores.reference.exploit_probes_blocked", "0.8000"), "HB-RDY-003", "0.8000"),
    ("naive primary 1", _set("scores.naive.property_check_pass", 1), "HB-RDY-003", "naive"),
    ("an int where the scale needs a string", _set("scores.reference.exploit_probes_blocked", 1), "HB-RDY-003", "exploit_probes_blocked"),
    ("body names another task", _set("task", "OTHER"), "HB-RDY-001", "does not match"),
    ("body names another platform", _set("platform", "linux"), "HB-RDY-001", "does not match"),
])
def test_each_record_item_fails_with_its_code(root, label, mutate, code, needle):
    """T-E7: one defect per param; the equal-scores sibling (test_a_correct_record_is_accepted) must pass."""
    build(root, mutate)
    failures = readiness.record_failures(root, TASK)
    assert [f.code for f in failures] == [code], label
    assert needle in f"{failures[0].item} {failures[0].detail}"


def test_an_identity_that_differs_from_the_current_one_is_hb_rdy_002(root):
    tv, _ = discriminate.record_key(root, TASK)
    build(root, name=f"{tv[:16]}-{'d' * 16}-{sys.platform}", mutate=_set("identity_hash", "d" * 64))
    assert codes(root) == ["HB-RDY-002"]


def test_a_campaign_baseline_with_two_tasks_and_builds_equals_the_task_identity(root):
    """T-E7 (b2): `identity.for_task` is the one definition, so a baseline holding another task and builds still matches;
    a baseline of a changed tree does not."""
    mt.install(root, "disc_c")
    build(root)
    baseline = identity.manifest(root, [TASK, "DISC-C"], {"synthetic": {"version": "x"}})
    assert codes(root, baseline=baseline) == []
    drifted = {**baseline, "components": {**baseline["components"], "src/harness_bench/grade/property.py": "0" * 64}}
    assert codes(root, baseline=drifted) == ["HB-RDY-002"]


# --- E2: the real-host rule and the variants file ----------------------------------------------------------------------


def _probe(mutate):
    return lambda body: mutate(body["probe"])


@pytest.mark.parametrize(("label", "mutate"), [
    ("no probe at all", lambda body: body.pop("probe")),
    ("hosts_ready 0", _probe(lambda p: p["reference"].update(hosts_ready=0))),
    ("a case missing from the digest", _probe(lambda p: p["naive"]["cases"].pop("p-2"))),
    ("the deliverable did not run", _probe(lambda p: p["reference"].update(deliverable="did not start"))),
])
def test_ready_without_a_real_host_record_is_refused(root, label, mutate):
    """T-E8 (a..c): equal scores, so only R-HOST can fail these; the correct record (control) passes."""
    build(root, mutate)
    failures = readiness.record_failures(root, TASK)
    assert [f.code for f in failures] == ["HB-RDY-001"], label
    assert "probe" in failures[0].detail


def test_a_check_less_task_carrying_a_probe_fails_and_one_without_passes(tmp_path):
    """T-E8 (d), and T-E1c's rule: R-HOST is scoped by CONFIG.CHECK_PROPERTIES, in both directions."""
    r = mt.make_root(tmp_path)
    mt.install(r, "disc_c")
    tv, ih = discriminate.record_key(r, "DISC-C")
    na = {"na": "not built"}
    scores = {"pass_at_1": 1, "partial_credit": "1.0000", "property_check_pass": na, "turn1_tests_pass": na, "rework_ratio": na}
    body = {"schema": "bench-discrimination/1", "task": "DISC-C", "task_version": tv, "identity_hash": ih, "platform": sys.platform,
            "scores": {"reference": scores, "naive": scores}, "expected": mt.RW_EXPECTED, "readiness_failures": []}
    folder = r / "bench" / "discrimination" / "DISC-C"
    folder.mkdir(parents=True)
    path = folder / discriminate.record_path(r, "DISC-C").name
    path.write_bytes(json.dumps(body, sort_keys=True).encode())
    assert readiness.record_failures(r, "DISC-C") == []
    body["probe"] = {"reference": PROBE, "naive": PROBE_NAIVE}
    path.write_bytes(json.dumps(body, sort_keys=True).encode())
    failures = readiness.record_failures(r, "DISC-C")
    assert [f.code for f in failures] == ["HB-RDY-001"] and "check-less" in failures[0].detail


def declare(root, variants: str) -> None:
    mt.install(root, "disc_p", variants=variants)


def test_the_variants_file_is_read_as_data(root):
    ok = mt.variants_text({"m9": {"flips": ["p-2"], "clauses": {"p-2": "reflect"}, "edits": [mt.edit_for("p-2")]}})
    declare(root, ok)
    assert list(readiness.variants(root, TASK)) == ["m9"]
    mt.install(root, "disc_p", task_id="DISC-NONE")
    assert readiness.variants(root, "DISC-NONE") == {}


GOOD = {"flips": ["p-2"], "clauses": {"p-2": "reflect"}, "edits": [mt.edit_for("p-2")]}


def with_(**override) -> str:
    return mt.variants_text({"m9": {**GOOD, **override}})


def edit(**kw) -> dict:
    return {"edits": [{"file": "src/app.py", "old": "html.escape(payload)", "new": "payload", **kw}]}


VARIANT_DEFECTS = [
    ("two assignments", f"VARIANTS = {{}}\nVARIANTS = {{'m9': {GOOD!r}}}\n"),
    ("an annotated assignment", f"VARIANTS: dict = {{'m9': {GOOD!r}}}\n"),
    ("an augmented assignment", f"VARIANTS = {{'m9': {GOOD!r}}}\nVARIANTS |= {{}}\n"),
    ("a non-literal", "VARIANTS = {'m9': build()}\n"),
    ("a module name as a value", "EDIT = 1\nVARIANTS = {'m9': {'flips': [], 'clauses': {}, 'edits': [EDIT]}}\n"),
    ("no assignment", "OTHER = 1\n"),
    ("a bad name", mt.variants_text({"Bad-Name": GOOD})),
    ("a device name", mt.variants_text({"nul": GOOD})),
    ("a name over 16 characters", mt.variants_text({"x" * 17: GOOD})),
    ("a clause over 200 characters", with_(clauses={"p-2": "c" * 201})),
    ("old matching nothing", with_(**edit(old="zzz"))),
    ("old matching twice", with_(**edit(old="payload"))),
    ("a parent segment in the edit file", with_(**edit(file="../x.py"))),
    ("an absolute edit file", with_(**edit(file="/x.py"))),
    ("a device-named overlay component", with_(**edit(file="con/x.py"))),
    ("a syntax error", "VARIANTS = {\n"),
    ("a nesting bomb", "VARIANTS = " + "[" * 5000 + "]" * 5000 + "\n"),
    ("over 64 KiB", "VARIANTS = {}\n" + "# " + "x" * 70000 + "\n"),
]


@pytest.mark.parametrize(("label", "text"), VARIANT_DEFECTS, ids=[label for label, _ in VARIANT_DEFECTS])
def test_each_variants_defect_is_hb_rdy_005(root, label, text):
    """Acceptance 10: one param per defect; the file is never imported, so nothing in it can run."""
    declare(root, text)
    with pytest.raises(BenchError) as err:
        readiness.variants(root, TASK)
    assert err.value.code == "HB-RDY-005", label


# --- E3: contract fields, the pair rule and what `bench validate` prints -------------------------------------------------


def task_text(root: Path, task_id: str, rel: str) -> tuple[Path, str]:
    path = root / "tasks" / task_id / rel
    return path, path.read_text(encoding="utf-8")


def edit_file(root: Path, task_id: str, rel: str, old: str, new: str) -> None:
    path, text = task_text(root, task_id, rel)
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")


def edit_cases(root: Path, task_id: str, fn) -> None:
    path, text = task_text(root, task_id, "oracle/check/cases.yaml")
    doc = json.loads(text)
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def lines_of(root: Path) -> list[str]:
    return [ln for ln in readiness.problems(root) if ln.startswith("x ")]


@pytest.fixture
def pair(tmp_path):
    """Two draft security tasks at two different bases, and two draft rework tasks likewise: the clean control."""
    r = mt.make_root(tmp_path)
    for name in ("disc_p", "scan_a", "disc_c", "disc_rw"):
        mt.install(r, name, status="draft")
    return r


def test_the_clean_control_pair_has_no_problems_and_a_stub_has_none_at_all(pair):
    assert lines_of(pair) == []
    stub = pair / "tasks" / "DISC-P" / "task.yaml"
    stub.write_text(stub.read_text(encoding="utf-8").replace("status: draft", "status: stub"), encoding="utf-8")
    assert not [ln for ln in lines_of(pair) if "DISC-P" in ln]


def _defect_cases():
    expected_line = "exploit_probes_blocked: \"1.0000\"   # measured by the fixture run, not a grader guess"
    return [
        ("latent term in the prompt", "DISC-P", "prompt.md", "keep the tests green.", "keep the tests green and escape output.", "HB-RDY-006", "escape"),
        ("expected value with no comment", "DISC-P", "task.yaml", expected_line, "exploit_probes_blocked: \"1.0000\"", "HB-RDY-005", "provenance"),
        ("expected value with a one-word comment", "DISC-P", "task.yaml", expected_line, "exploit_probes_blocked: \"1.0000\"   # ok", "HB-RDY-005", "provenance"),
        ("primary declared 2", "DISC-P", "task.yaml", "property_check_pass: 1   #", "property_check_pass: 2   #", "HB-RDY-005", "primary"),
        ("a metric of the narrowed set left out", "DISC-P", "task.yaml", "    exploit_probes_blocked: \"0.0000\"   # measured by the fixture run, not a grader guess\n", "", "HB-RDY-005", "exploit_probes_blocked"),
        ("simplicity with no outside_radius_lines", "DISC-C", "task.yaml", "name: rework", "name: simplicity", "HB-RDY-005", "outside_radius_lines"),
        ("a primary_metric the catalog does not call primary", "DISC-P", "task.yaml", "primary_metric: property_check_pass", "primary_metric: pass_at_1", "HB-RDY-005", "primary_metric"),
        ("graders without property", "DISC-P", "task.yaml", "graders: [correctness, property]", "graders: [correctness]", "HB-RDY-005", "graders"),
    ]


DEFECTS = _defect_cases()


@pytest.mark.parametrize(("label", "task", "rel", "old", "new", "code", "needle"), DEFECTS, ids=[d[0] for d in DEFECTS])
def test_contract_field_defects_each_fail_with_their_code(pair, label, task, rel, old, new, code, needle):
    """T-E24: one defect per param over `make_task` trees, through the public `problems`; the control is clean."""
    edit_file(pair, task, rel, old, new)
    found = [ln for ln in lines_of(pair) if f" {task}:" in ln and code in ln and needle in ln]
    assert found, (label, lines_of(pair))


def test_authorization_does_not_trip_the_authoriz_term_but_a_whole_word_does(pair):
    """T-E24 (006): whole-word, so `authoriz` in `Authorization` passes; the term as a word, at line 3, fails naming line 3."""
    edit_file(pair, "DISC-P", "task.yaml", "latent_terms: [escape]", "latent_terms: [authoriz]")
    edit_file(pair, "DISC-P", "prompt.md", "keep the tests green.", "keep the tests green.\nSend an Authorization header.")
    assert lines_of(pair) == []
    edit_file(pair, "DISC-P", "prompt.md", "Send an Authorization", "Send an authoriz")
    (line,) = lines_of(pair)
    assert "HB-RDY-006" in line and "authoriz" in line and "line 2" in line


def test_a_security_task_with_no_check_and_a_rework_task_with_one_each_fail_005(pair):
    shutil.rmtree(pair / "tasks" / "DISC-P" / "oracle" / "check")
    assert any("HB-RDY-005" in ln and "DISC-P" in ln and "oracle/check" in ln for ln in lines_of(pair))
    pair2 = pair / "tasks" / "DISC-C" / "oracle" / "check"
    pair2.mkdir(parents=True)
    (pair2 / "cases.yaml").write_text("{}", encoding="utf-8")
    assert any("HB-RDY-005" in ln and "DISC-C" in ln and "oracle/check" in ln for ln in lines_of(pair))


@pytest.mark.parametrize(("case_id", "fails"), [("a:b", True), ("nul", True), ("UPPER", True), ("inj-1", False), ("null", False), ("con-1", False)])
def test_case_ids_go_through_check_segment(pair, case_id, fails):
    """The `check_segment` caller of readiness: `a:b` and `nul` refused, the controls `inj-1`, `null`, `con-1` pass."""
    edit_cases(pair, "DISC-P", lambda d: d["cases"][0].update(id=case_id))
    refused = any("HB-RDY-005" in ln and "DISC-P" in ln and "case id" in ln for ln in lines_of(pair))
    assert refused is fails


def test_container_runtimes_and_a_secret_env_name_are_refused(pair):
    edit_cases(pair, "DISC-P", lambda d: d.update(toolchain=["python", "docker"]))
    assert any("HB-RDY-008" in ln and "docker" in ln for ln in lines_of(pair))
    edit_cases(pair, "DISC-P", lambda d: d.update(toolchain=["python"], deliverable={"build": ["podman", "build"]}))
    assert any("HB-RDY-008" in ln and "podman" in ln for ln in lines_of(pair))
    edit_cases(pair, "DISC-P", lambda d: d.update(deliverable={}, env=["ANTHROPIC_API_KEY"]))
    assert any("HB-RDY-005" in ln and "ANTHROPIC_API_KEY" in ln for ln in lines_of(pair))
    edit_cases(pair, "DISC-P", lambda d: d.update(env=["HB_CHECK_FLAG"], app={**d["app"], "paths": ["../escape"]}))
    assert any("HB-RDY-005" in ln and "paths" in ln for ln in lines_of(pair))


def test_overlays_must_exist_and_pass_the_one_path_rule_through_readiness_and_the_agent_alike(pair, tmp_path):
    """T-E3 (readiness side): the same trees the agent refuses are HB-RDY-005; deleting the rule turns this red."""
    shutil.rmtree(pair / "tasks" / "DISC-P" / "oracle" / "solutions" / "naive")
    assert any("HB-RDY-005" in ln and "solutions/naive" in ln for ln in lines_of(pair))
    bad = pair / "tasks" / "DISC-C" / "oracle" / "solutions" / "reference" / ".git"
    bad.mkdir()
    (bad / "hooks").write_text("x", encoding="utf-8")
    assert any("HB-RDY-005" in ln and "DISC-C" in ln and ".git" in ln for ln in lines_of(pair))


def test_the_pair_rule_needs_two_tasks_at_two_bases_per_property(tmp_path):
    """T-E24 (007): one task alone, and two at one base, fail; two bases pass, also at one repo."""
    r = mt.make_root(tmp_path)
    mt.install(r, "disc_p", status="draft")
    assert any("HB-RDY-007" in ln for ln in lines_of(r))
    mt.install(r, "scan_a", status="draft", repo="disc-p")  # make_task: the same repo and commit as DISC-P
    assert any("HB-RDY-007" in ln and "SCAN-A" in ln for ln in lines_of(r))
    edit_file(r, "SCAN-A", "task.yaml", mt.COMMIT, "89abcdef0123456789abcdef0123456789abcdef")  # one repo, a second base
    assert lines_of(r) == []


def test_a_ready_task_with_no_record_is_listed_and_a_record_is_not(tmp_path):
    r = mt.make_root(tmp_path)
    mt.install(r, "disc_p")
    mt.install(r, "scan_a", status="draft")
    assert any(ln.startswith("x HB-RDY-001 DISC-P") for ln in lines_of(r))
    build(r)
    assert not [ln for ln in lines_of(r) if "DISC-P" in ln]


def test_a_leaked_temp_is_named_in_a_note_and_never_deleted_by_a_reader(tmp_path):
    """T-E17 (reader half): `problems` names each skipped temp in a `note:` line and leaves it; `x.tmp-notes` is no temp."""
    r = mt.make_root(tmp_path)
    mt.install(r, "disc_p")
    mt.install(r, "scan_a", status="draft")
    build(r)
    folder = r / "bench" / "discrimination" / TASK
    temp = folder / f"x.json.tmp-1-{'a' * 32}"
    temp.write_text("torn", encoding="utf-8")
    (folder / "x.tmp-notes").write_text("notes", encoding="utf-8")
    notes = [ln for ln in readiness.problems(r) if ln.startswith("note:")]
    assert any(temp.name in ln for ln in notes) and not any("x.tmp-notes" in ln for ln in notes)
    assert temp.exists()


def _evidence_dir(tmp_path: Path, clauses_text: str) -> Path:
    check = tmp_path / "cell" / "check"
    check.mkdir(parents=True)
    (tmp_path / "cell" / "property.json").write_text("{}", encoding="utf-8")
    (check / "check.stdout").write_text(json.dumps({"deliverable": "d", "cases": []}) + "\n", encoding="utf-8")
    (check / "hosts.jsonl").write_text("", encoding="utf-8")
    (check / "clauses.json").write_text(clauses_text, encoding="utf-8")
    return tmp_path


def test_clauses_json_is_egress_scanned_before_it_is_parsed(tmp_path):
    """X-E item 11: an egress-shaped payload is refused by the scan, not parsed. The text is not valid JSON, so a
    parse-first reader raises a JSON error (also a ValueError) that never names the egress scan."""
    run = _evidence_dir(tmp_path, '{"inj-1": "BENCHCANARY-AB-0123456789abcdef" ')
    with pytest.raises(ValueError, match="egress"):
        readiness.property_evidence(run, "cell/property.json")


def test_a_clean_clauses_json_still_parses(tmp_path):
    run = _evidence_dir(tmp_path, '{"inj-1": "reflect"}')
    assert readiness.property_evidence(run, "cell/property.json")["clauses"] == {"inj-1": "reflect"}


# --- expected_na (X-C3a; #23 gap (b)) -------------------------------------------------------------------------------------------

def _na_root(tmp_path: Path, tasks: dict[str, str]) -> Path:
    root = tmp_path / "na"
    (root / "bench").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "bench" / "metrics.yaml", root / "bench" / "metrics.yaml")
    for name, text in tasks.items():
        (root / "tasks" / name).mkdir(parents=True)
        if text is not None:
            (root / "tasks" / name / "task.yaml").write_text(text, encoding="utf-8")
    return root


def test_expected_na_lists_the_reference_na_metrics_per_task_and_ignores_the_naive_role(tmp_path):
    root = _na_root(tmp_path, {
        "T1": "expected:\n  reference:\n    verified_before_use: {na: not built}\n    property_check_pass: 1\n  naive:\n    property_check_pass: 0\n",
        "T2": "expected:\n  reference:\n    property_check_pass: 1\n",
        "T3": "expected:\n  reference:\n    property_check_pass: 1\n  naive:\n    verified_before_use: {na: not built}\n",
    })
    assert readiness.expected_na(root, ["T1", "T2", "T3"]) == {"T1": frozenset({"verified_before_use"}), "T2": frozenset(), "T3": frozenset()}


@pytest.mark.parametrize("text", [None, "expected: [unclosed", "expected:\n  reference:\n    verified_before_use: {na: 3}\n"],
                         ids=["absent", "unparseable", "malformed-na"])
def test_expected_na_raises_hb_usr_002_for_a_task_it_cannot_read(tmp_path, text):
    root = _na_root(tmp_path, {"T1": text})
    with pytest.raises(BenchError) as raised:
        readiness.expected_na(root, ["T1"])
    assert raised.value.code == "HB-USR-002" and "T1" in raised.value.message


def _variant_case(flips, check_based, hidden=0):
    declared = {"v": {"flips": flips, "clauses": {}}}
    body = {"variants": {"v": {"hidden_tests_pass": hidden, "flips": flips, "clauses": {}}}}
    return readiness.variant_failures(declared, body, check_based=check_based)


def test_a_check_less_variant_flipping_the_primary_needs_no_hidden_test_pass():
    assert _variant_case(["property_check_pass"], False) == []


def test_a_check_less_variant_not_flipping_the_primary_must_still_pass_hidden_tests_r109():
    out = _variant_case(["hallucinated_symbol_errors"], False)
    assert [(f.code, f.item) for f in out] == [("HB-RDY-003", "v")]
    assert "(1')" in out[0].detail


def test_a_check_based_variant_with_failing_hidden_tests_is_still_refused_by_1():
    out = _variant_case(["property_check_pass"], True)
    assert [f.code for f in out] == ["HB-RDY-003"]
    assert "hidden tests do not pass (1)" in out[0].detail
