"""Readiness over discrimination records (W1-E section 8). Records here are hand-built from the real key, so each defect is
one field; the wiring partner that proves a real trial's record is accepted is test_discriminate.py (T-E1c, T-E1b).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from harness_bench import discriminate, identity, readiness

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
