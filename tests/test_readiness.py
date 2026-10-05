"""Readiness over discrimination records (W1-E section 8). Records here are hand-built from the real key, so each defect is
one field; the wiring partner that proves a real trial's record is accepted is test_discriminate.py (T-E1c, T-E1b).
"""

import importlib.util
import json
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
            "probe": {"reference": PROBE, "naive": PROBE_NAIVE}, "readiness_failures": []}
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
