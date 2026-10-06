"""bench discriminate through the real engine, archiver and grading pass (W1-E; R-98). Nothing of the path is faked.

Each trial is one run of the real `engine.Engine` with the real `SyntheticLauncher` (a real agent process), the real
working-copy builder and the real `runner.run_pass`. Fixtures come from `tests/fixtures/property_tasks/make_task.py`.
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from clean_parent import CLEAN_PARENT

from harness_bench import archive, discriminate, oslock, readiness
from harness_bench.errors import BenchError
from harness_bench.grade import _env

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the grader and its host are Windows-only (ADR-0018 s8)")
_spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)  # type: ignore[union-attr]
TASK = "DISC-C"


def trial(base: Path, root: Path, task: str = TASK) -> discriminate.Result:
    return discriminate.run(root, task, runs=base / "runs", cells_root=base / "cells")


def new_root(base: Path, name: str = "disc_c", **tweak) -> Path:
    root = mt.make_root(base)
    mt.install(root, name, **tweak)
    return root


def run_folders(base: Path) -> set[str]:
    runs = base / "runs"
    return {p.name for p in runs.iterdir() if p.is_dir()} if runs.is_dir() else set()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def got(first):
    """The shared trial's outcome, asserted first so a red run fails on this line and not on a missing attribute."""
    base, root, result = first
    assert result.outcome == "written", result
    return base, root, result


@pytest.fixture(scope="module")
def first():
    """One real trial of disc_c, shared by the tests that only read its outcome."""
    base = CLEAN_PARENT / uuid.uuid4().hex  # cells cannot be built under the operator's profile (HB-PRE-002)
    base.mkdir(parents=True)
    try:
        root = new_root(base)
        yield base, root, trial(base, root)
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def test_a_check_less_property_task_discriminates_without_a_host(first):
    """T-E1c: the real engine and grader; no `probe` key for a check-less property; readiness raises no item."""
    _base, root, result = got(first)
    assert result.record_path.exists()
    body = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert "probe" not in body
    assert body["scores"]["reference"]["pass_at_1"] == 1
    assert body["scores"]["naive"]["pass_at_1"] == 0
    assert [ln for ln in readiness.problems(root) if not ln.startswith("note:") and "HB-RDY-007" not in ln] == []


def test_synthetic_environment_and_record_leak_scan(first, monkeypatch, tmp_path):
    """R2-3 (T-E1a's allowlist, canary and leak assertions, moved here by name; only the `exists()` assertion retired)."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "HB_CLAUDE_OAUTH_TOKEN", "HB_TEST_UNLISTED_SECRET"):
        monkeypatch.setenv(name, "BENCHCANARY-secret")
    launcher = discriminate.SyntheticLauncher({"synthetic-reference": tmp_path / "ov"})
    _argv, env = launcher.argv_env({"combo": "synthetic-reference"}, tmp_path / "home", "00-trace-00")
    assert set(env) == set(_env.grading_env()) | {"HB_SYNTH_OVERLAY", "TRACEPARENT"}
    assert not {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "HB_CLAUDE_OAUTH_TOKEN", "HB_TEST_UNLISTED_SECRET"} & set(env)
    base, _root, result = got(first)
    texts = [result.record_path.read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in (base / "runs").rglob("discrimination-link.json")]
    assert len(texts) == 2, "the trial wrote one record and one link"
    user = os.environ.get("USERNAME", "")
    for text in texts:
        assert "BENCHCANARY-" not in text
        assert not re.search(r"[A-Za-z]:[\\/]", text), "no absolute path"
        assert not user or user.lower() not in text.lower()


def test_overlay_lands_in_the_engine_built_working_copy_and_deletes_nothing(first):
    """T-E2: the archived tree is the engine-built working copy (keep.txt from the base) with the overlay on top."""
    base, _root, result = got(first)
    archives = list((base / "runs" / result.run_id / "archive").glob("*/attempt-1/ws"))
    assert len(archives) == 2
    contents = sorted((ws / "app.py").read_text(encoding="utf-8") for ws in archives)
    assert contents == sorted([mt.DOUBLE_REF, mt.DOUBLE_NAIVE])
    assert all((ws / "keep.txt").read_text(encoding="utf-8") == "keep me\n" for ws in archives)


def test_record_body_is_a_pure_function_of_its_key(first):
    """Acceptance 5: the key set, and no clock, duration, pid, path, run id or grading id anywhere in key or value."""
    base, _root, result = got(first)
    body = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert set(body) == {"schema", "task", "task_version", "identity_hash", "platform", "scores", "expected", "readiness_failures"}
    flat = json.dumps(body)
    assert result.run_id not in flat and "grading-" not in flat and "duration" not in flat
    link = json.loads(next((base / "runs" / result.run_id).glob("discrimination-link.json")).read_text(encoding="utf-8"))
    assert link["run_id"] == result.run_id
    assert link["record_sha256"] == digest(result.record_path)
    assert link["record_stem"] == result.record_path.stem


def test_retry_at_an_unchanged_key_is_a_confirmation(base):
    """T-E4 / acceptance 4: a second trial in another run folder writes equal bytes and is `confirmed`, never HB-LED-007."""
    root = new_root(base)
    one = trial(base, root)
    assert one.outcome == "written"
    before = digest(one.record_path)
    two = trial(base, root)
    assert (one.outcome, two.outcome) == ("written", "confirmed")
    assert two.record_path == one.record_path and digest(two.record_path) == before
    assert two.run_id != one.run_id
    assert len(list((base / "runs").glob("*/discrimination-link.json"))) == 2


def test_no_link_after_hb_rdy_010(base):
    """T-E5a/b (R-98 conditions 1 and 2): a differing re-run raises HB-RDY-010 naming the first differing path and both
    values, leaves the stored bytes alone, and the failed run folder holds no link."""
    root = new_root(base, "disc_flaky", counter=str(base / "counter.txt"))
    one = trial(base, root, "DISC-FLAKY")
    assert one.outcome == "written"
    before = digest(one.record_path)
    seen = run_folders(base)
    with pytest.raises(BenchError) as err:
        trial(base, root, "DISC-FLAKY")
    assert err.value.code == "HB-RDY-010"
    assert re.search(r"scores\.reference\.\w+", str(err.value))
    assert digest(one.record_path) == before
    (failed,) = run_folders(base) - seen
    assert not (base / "runs" / failed / "discrimination-link.json").exists()


def test_two_discriminate_calls_exactly_one_proceeds(base):
    """T-E20: the test holds the task's lock itself; the call is refused before it plans, so no run folder exists."""
    root = new_root(base)
    lock = base / "runs" / f".discriminate-{TASK}.lock"
    with oslock.RunLock.acquire(lock, "HB-RUN-005"), pytest.raises(BenchError) as err:
        trial(base, root)
    assert err.value.code == "HB-RUN-005"
    assert run_folders(base) == set()


def test_an_incomplete_engine_run_writes_no_record_and_names_the_cell(base, monkeypatch):
    """T-E21: an agent that exits non-zero fails its cell; nothing is written and the error names the cell."""
    bad = base / "bad_agent.py"
    bad.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(discriminate, "AGENT", bad)
    root = new_root(base)
    with pytest.raises(BenchError) as err:
        trial(base, root)
    assert err.value.code == "HB-RDY-011" and f"{TASK}.synthetic-" in str(err.value)
    assert not (root / "bench" / "discrimination").exists() or not list((root / "bench" / "discrimination").rglob("*.json"))
    assert not list((base / "runs").rglob("discrimination-link.json"))


def test_a_leaked_temp_is_swept_before_the_write_and_never_by_a_reader(base):
    """T-E17: the writer sweeps `<name>.tmp-*` temps (files and folders) under its lock; a non-temp name survives."""
    root = new_root(base)
    folder = root / "bench" / "discrimination" / TASK
    folder.mkdir(parents=True)
    leaked = folder / f"x.json.tmp-1-{'a' * 32}"
    leaked.write_text("torn", encoding="utf-8")
    leaked_dir = folder / f"y.json.tmp-2-{'b' * 32}"
    leaked_dir.mkdir()
    keep = folder / "x.tmp-notes"
    keep.write_text("notes", encoding="utf-8")
    result = trial(base, root)
    assert result.outcome == "written"
    assert result.record_path.exists()
    assert not leaked.exists() and not leaked_dir.exists() and keep.exists()


# --- E2: the real probe host ----------------------------------------------------------------------------------------


def record_of(result) -> dict:
    return json.loads(result.record_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hosted():
    """One real trial of disc_p (a callable security task with a real check), shared by the host-read tests."""
    base = CLEAN_PARENT / uuid.uuid4().hex
    base.mkdir(parents=True)
    try:
        root = new_root(base, "disc_p")
        yield base, root, trial(base, root, "DISC-P")
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def got_host(hosted):
    base, root, result = hosted
    assert result.outcome == "written", result
    return base, root, result


def grading_of(base: Path, result) -> tuple[Path, str]:
    run_dir = base / "runs" / result.run_id
    return run_dir, json.loads((run_dir / "discrimination-link.json").read_text(encoding="utf-8"))["grading_id"]


def test_a_real_deliverable_through_the_real_probe_host_to_a_record(hosted):
    """T-E1b (the required end-to-end test): the real probe host spawned by the real grader, no stub."""
    _base, root, result = got_host(hosted)
    body = record_of(result)
    assert body["scores"]["reference"]["property_check_pass"] == 1
    assert body["scores"]["naive"]["property_check_pass"] == 0
    probe = body.get("probe", {})
    assert probe.get("reference") == {"deliverable": "ran", "cases": {"p-1": "blocked", "p-2": "blocked"}, "hosts_ready": 2}
    assert probe.get("naive", {}).get("cases") == {"p-1": "exploited", "p-2": "exploited"}
    assert readiness.record_failures(root, "DISC-P") == []


def test_unbiased_failures_lists_cells_and_raises_with_the_reason_when_unreadable(hosted, base):
    """T-E14: over a real graded run; the copy is edited, never the shared run."""
    run_dir, gid = grading_of(hosted[0], got_host(hosted)[2])
    assert readiness.unbiased_failures(run_dir, gid) == []
    copy = base / "copy"
    shutil.copytree(run_dir, copy)
    target = next(copy.glob(f"grading/{gid}/*/property/property.json"))
    doc = json.loads(target.read_text(encoding="utf-8"))
    doc["spans"][0]["unbiased_ok"] = False
    target.write_text(json.dumps(doc), encoding="utf-8")
    assert readiness.unbiased_failures(copy, gid) == [target.parent.parent.name]
    shutil.rmtree(copy / "scores")
    with pytest.raises(BenchError) as err:
        readiness.unbiased_failures(copy, gid)
    assert err.value.code == "HB-USR-002" and "scores" in str(err.value)


def test_hidden_test_disagreements_states_and_reasons(hosted, base):
    """T-E15: agree, disagree, not comparable, and raise (a property.json gone for a cell with a recorded value)."""
    run_dir, gid = grading_of(hosted[0], got_host(hosted)[2])
    assert readiness.hidden_test_disagreements(run_dir, gid) == []
    copy = base / "copy"
    shutil.copytree(run_dir, copy)
    files = sorted(copy.glob(f"grading/{gid}/*/property/property.json"))
    cell = files[0].parent.parent.name
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    original = doc["hidden_tests_pass"]["value"]
    doc["hidden_tests_pass"]["value"] = 0 if original == 1 else 1
    files[0].write_text(json.dumps(doc), encoding="utf-8")
    assert readiness.hidden_test_disagreements(copy, gid) == [cell]
    doc["hidden_tests_pass"]["value"] = None
    files[0].write_text(json.dumps(doc), encoding="utf-8")
    assert readiness.hidden_test_disagreements(copy, gid) == []
    assert readiness.comparable_cells(copy, gid) == ([], [cell])
    files[0].unlink()
    with pytest.raises(BenchError) as err:
        readiness.hidden_test_disagreements(copy, gid)
    assert err.value.code == "HB-USR-002" and cell in str(err.value)


def test_discriminate_fails_the_trial_on_a_hidden_test_disagreement(base):
    """T-E16: hidden tests that flip between the correctness pass and the property pass are a flaky oracle."""
    root = new_root(base, "disc_p", hidden=mt.HIDDEN_COUNTER.format(counter=str(base / "tests-counter.txt")))
    with pytest.raises(BenchError) as err:
        trial(base, root, "DISC-P")
    assert err.value.code == "HB-RDY-011" and "disagree" in str(err.value)
    assert not list((root / "bench" / "discrimination").rglob("*.json"))


@pytest.mark.parametrize(("name", "task", "items"), [
    ("scan_a", "SCAN-A", {("reference", "property_check_pass"), ("reference", "exploit_probes_blocked")}),
    ("scan_a_secondary", "SCAN-B", {("reference", "exploit_probes_blocked")}),
])
def test_scan_a_fixture_fails_naming_metric_expected_observed(base, name, task, items):
    """T-E10: the reference's mandated build output flips the scan probe; the secondary-only sibling fails on it alone."""
    root = new_root(base, name)
    result = trial(base, root, task)
    assert result.outcome == "written"
    failures = readiness.record_failures(root, task)
    assert {(f.detail.split()[0], f.item) for f in failures} == items
    assert all(f.code == "HB-RDY-003" for f in failures)
    by = {f.item: f.detail for f in failures}
    if name == "scan_a":
        assert by["exploit_probes_blocked"] == "reference expected 1.0000, observed 0.8000"
        assert by["property_check_pass"] == "reference expected 1, observed 0"
    else:
        assert by["exploit_probes_blocked"] == "reference expected 0.9000, observed 1.0000"
    assert record_of(result)["readiness_failures"] == sorted(f"HB-RDY-003: {f.item}" for f in failures)


VARIANT_FLIPS = {"m9": {"flips": ["p-2"], "clauses": {"p-2": "reflect"}, "edits": [mt.edit_for("p-2")]},
                 "m8": {"flips": ["p-1"], "clauses": {"p-1": "echo"}, "edits": [mt.edit_for("p-1")]}}


def test_variant_trial_runs_on_the_real_host_compares_flips_and_never_executes_the_file(base):
    """T-E11: variants are cells of the same run; the file is read as data (its module body would write the sentinel)."""
    sentinel = base / "sentinel.txt"
    root = new_root(base, "disc_p", variants=mt.variants_text(VARIANT_FLIPS, sentinel))
    result = trial(base, root, "DISC-P")
    assert result.outcome == "written"
    body = record_of(result)
    variants = body.get("variants", {})
    assert variants.get("m9", {}).get("flips") == ["p-2"] and variants.get("m8", {}).get("flips") == ["p-1"]
    assert variants.get("m9", {}).get("clauses") == {"p-2": "reflect"}
    assert variants.get("m9", {}).get("hidden_tests_pass") == 1 and variants.get("m9", {}).get("deliverable") == "ran"
    assert not sentinel.exists(), "variants.py was executed"
    assert body["readiness_failures"] == [] and readiness.record_failures(root, "DISC-P") == []


def test_a_variant_whose_flips_differ_from_the_declared_ones_is_hb_rdy_003(base):
    """T-E11 wrong_flip: declared p-1, observed p-2: the record is written and readiness names variant and case."""
    wrong = {"m9": {"flips": ["p-1"], "clauses": {"p-1": "echo"}, "edits": [mt.edit_for("p-2")]}}
    root = new_root(base, "disc_p", variants=mt.variants_text(wrong))
    assert trial(base, root, "DISC-P").outcome == "written"
    failures = readiness.record_failures(root, "DISC-P")
    assert [(f.code, f.item) for f in failures] == [("HB-RDY-003", "m9")]
    failure = failures[0]
    assert "p-1" in failure.detail and "p-2" in failure.detail


def test_a_crash_variant_is_rejected_not_counted_as_a_flip(base):
    """T-E12: a variant whose every call raises fails its hidden tests, so declaring it a flip cannot make it pass."""
    crash = {"crash": {"flips": ["p-1", "p-2"], "clauses": {"p-1": "echo", "p-2": "reflect"},
                       "edits": [{"file": "src/app.py", "old": mt.ESCAPE, "new": "1 / 0"}]}}
    root = new_root(base, "disc_p", variants=mt.variants_text(crash))
    assert trial(base, root, "DISC-P").outcome == "written"
    failures = readiness.record_failures(root, "DISC-P")
    assert failures
    assert all(f.code == "HB-RDY-003" and f.item == "crash" for f in failures)
    assert any("hidden tests" in f.detail for f in failures)


def test_a_timeout_trial_writes_no_record_and_the_clean_retry_succeeds(base):
    """T-E13 / R2-1: a load-driven `timeout` is HB-RDY-011, never a record; the retry is `written`, never HB-RDY-010."""
    cases = mt._cases(["p-1", "p-2"], bound_ms={"p-1": 1000})
    root = new_root(base, "disc_p", naive={"src/app.py": mt.handle_slow_first(base / "slow.txt")}, cases=cases)
    with pytest.raises(BenchError) as err:
        trial(base, root, "DISC-P")
    assert err.value.code == "HB-RDY-011" and "timeout" in str(err.value)
    assert not list((root / "bench" / "discrimination").rglob("*.json"))
    assert not list((base / "runs").rglob("discrimination-link.json"))
    second = trial(base, root, "DISC-P")
    assert second.outcome == "written"


@pytest.mark.parametrize("reason", ["invalid (check tampered)", "check exceeded its bound", "host suspended", "check output invalid"])
def test_a_check_or_host_fault_in_the_scores_is_untrustworthy_unless_expected_declares_it(reason):
    """T-E13 (the push form, over hand-built scores): each HB-CHK NA is an item; an NA equal to `expected` is exempt."""
    scores = {"reference": {"property_check_pass": {"na": reason}}, "naive": {"property_check_pass": 0}}
    assert len(discriminate._untrustworthy(scores, {})) == 1
    assert discriminate._untrustworthy(scores, {"reference": {"property_check_pass": {"na": reason}}}) == []


def test_an_na_reason_outside_the_closed_set_is_untrustworthy():
    """Rev 6.3: a reason with text no closed set names could differ between honest trials, so it never reaches a record."""
    scores = {"reference": {"property_check_pass": {"na": "HB-GRD-002 grading step timeout after 60 s"}}}
    assert len(discriminate._untrustworthy(scores, {})) == 1


def test_a_record_that_appears_mid_trial_is_untrustworthy_and_not_written(base, monkeypatch):
    """T-E22 / R2-7: bytes forged at the final key during the trial are left alone: HB-RDY-011, not HB-LED-007, no link."""
    root = new_root(base)
    forged = readiness.record_path(root, TASK)
    real = discriminate.runner.run_pass

    def forge_then_grade(*args, **kwargs):
        forged.parent.mkdir(parents=True, exist_ok=True)
        forged.write_bytes(b'{"forged":true}')
        return real(*args, **kwargs)

    monkeypatch.setattr(discriminate.runner, "run_pass", forge_then_grade)
    with pytest.raises(BenchError) as err:
        trial(base, root)
    assert err.value.code == "HB-RDY-011" and "appeared" in str(err.value)
    assert forged.read_bytes() == b'{"forged":true}'
    assert not list((base / "runs").rglob("discrimination-link.json"))


def test_the_sweep_is_pinned_to_its_own_tasks_lock(base):
    """Acceptance 13 / RV-SEC: another task's held lock is refused for this folder (atomic does not know the pairing)."""
    folder = base / "disc"
    folder.mkdir()
    with oslock.RunLock.acquire(base / "runs" / ".discriminate-OTHER.lock", "HB-RUN-005") as wrong, \
            pytest.raises(ValueError, match="does not guard"):
        discriminate._sweep(TASK, folder, wrong)
    with oslock.RunLock.acquire(base / "runs" / f".discriminate-{TASK}.lock", "HB-RUN-005") as right:
        assert discriminate._sweep(TASK, folder, right) == []


# --- E3: reconciliation, telemetry, the reader table, the grep rules ------------------------------------------------


def clone_state(source_base: Path, dest: Path) -> Path:
    """The runs folder and repository root of a finished trial, copied so a test can break the copy and not the original."""
    shutil.copytree(source_base / "runs", dest / "runs")
    shutil.copytree(source_base / "repo", dest / "repo")
    return dest / "repo"


def notes_and_failures(root: Path, base: Path) -> tuple[list[str], list[str]]:
    lines = readiness.problems(root, runs=base / "runs")
    # a lone task in the fixture repository trips the pair rule (007), which these tests are not about
    return [ln for ln in lines if ln.startswith("note:")], [ln for ln in lines if ln.startswith("x ") and "HB-RDY-007" not in ln]


def plan_edit(run_dir: Path, edit) -> None:
    from harness_bench import plan

    doc = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    edit(doc)
    doc["plan_hash"] = plan.plan_hash(doc)
    (run_dir / "plan.json").write_text(json.dumps(doc), encoding="utf-8")


def drop_pass(run_dir: Path) -> None:
    for seg in (run_dir / "events").glob("grade-*.jsonl"):
        seg.unlink()


def rewrite_record(record: Path, link: Path, edit) -> None:
    """Change the record's body, then make the link carry the new hash, so only the run comparison can object."""
    body = json.loads(record.read_text(encoding="utf-8"))
    edit(body)
    data = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    record.write_bytes(data)
    doc = json.loads(link.read_text(encoding="utf-8"))
    doc["record_sha256"] = hashlib.sha256(data).hexdigest()
    link.write_text(json.dumps(doc), encoding="utf-8")


REASONS = [
    ("no link", lambda run, rec, link: link.unlink(), "no link"),
    ("run folder absent", lambda run, rec, link: link.write_text(json.dumps({**json.loads(link.read_text(encoding="utf-8")),
                                                                              "run_id": "gone"}), encoding="utf-8"), "run folder absent"),
    ("no completed grading pass", lambda run, rec, link: drop_pass(run), "no completed grading pass"),
    ("record hash differs from the link", lambda run, rec, link: rec.write_bytes(rec.read_bytes() + b"\n"),
     "record hash differs from the link"),
    ("run is not a discrimination run", lambda run, rec, link: plan_edit(run, lambda d: d.update(kind="measurement")),
     "run is not a discrimination run"),
    ("run task version differs", lambda run, rec, link: plan_edit(run, lambda d: d["tasks"][TASK].update(version_hash="0" * 64)),
     "run task version differs"),
    ("run combos are not the synthetic ones", lambda run, rec, link: plan_edit(run, lambda d: d["cells"][0].update(combo="other")),
     "run combos are not the synthetic ones"),
]


@pytest.mark.parametrize(("label", "break_it", "reason"), REASONS, ids=[r[0] for r in REASONS])
def test_reconciliation_reasons_never_fail_and_never_pass(first, base, label, break_it, reason):
    """T-E6 (one case per reason of the closed set): `reconciled: no (<reason>)` is a note; it neither fails nor counts."""
    src_base, _root, result = got(first)
    root = clone_state(src_base, base)
    run_dir = base / "runs" / result.run_id
    break_it(run_dir, root / "bench" / "discrimination" / TASK / result.record_path.name, run_dir / "discrimination-link.json")
    notes, failures = notes_and_failures(root, base)
    assert f"note: {TASK}: reconciled: no ({reason})" in notes, label
    assert failures == []


def test_a_reconciled_record_prints_yes_and_a_score_difference_is_hb_rdy_004(first, base):
    """T-E6: the matching run reconciles; a recorded score that the run's grading pass does not hold fails HB-RDY-004."""
    src_base, _root, result = got(first)
    root = clone_state(src_base, base)
    notes, failures = notes_and_failures(root, base)
    assert notes == [f"note: {TASK}: reconciled: yes"] and failures == []
    record = root / "bench" / "discrimination" / TASK / result.record_path.name
    rewrite_record(record, base / "runs" / result.run_id / "discrimination-link.json",
                   lambda body: body["scores"]["reference"].update(partial_credit="0.5000"))
    notes, failures = notes_and_failures(root, base)
    assert failures == [f"x HB-RDY-004 {TASK}: partial_credit: copy 0.5000, run 1.0000"]
    assert notes == []


def test_a_forged_probe_outcome_fails_hb_rdy_004_when_its_run_exists(hosted, base):
    """SR-E3 fixture: the record says the naive role was blocked on p-1; the run's property.json says exploited."""
    src_base, _root, result = got_host(hosted)
    root = clone_state(src_base, base)
    record = root / "bench" / "discrimination" / "DISC-P" / result.record_path.name
    rewrite_record(record, base / "runs" / result.run_id / "discrimination-link.json",
                   lambda body: body["probe"]["naive"]["cases"].update({"p-1": "blocked"}))
    failures = [ln for ln in readiness.problems(root, runs=base / "runs") if ln.startswith("x ")]
    assert any("HB-RDY-004" in ln and "probe.naive.cases.p-1" in ln for ln in failures), failures


def test_readiness_recomputes_the_stored_failure_list(hosted, base):
    """T-E18: a record whose stored `readiness_failures` is empty, with a wrong score, is still refused."""
    src_base, _root, result = got_host(hosted)
    root = clone_state(src_base, base)
    record = root / "bench" / "discrimination" / "DISC-P" / result.record_path.name
    body = json.loads(record.read_text(encoding="utf-8"))
    body["scores"]["reference"]["property_check_pass"] = 0
    record.write_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    assert body["readiness_failures"] == []
    assert [f.code for f in readiness.record_failures(root, "DISC-P")] == ["HB-RDY-003"]


def events(run_dir: Path, name: str) -> list[dict]:
    rows = [json.loads(line) for line in (run_dir / "engine.log").read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["event"] == name]


def test_discriminate_emits_started_and_finished_with_measured_fields(first):
    """Acceptance 14 (IO): fields are measured on the normal path; the link carries the same timings."""
    base, _root, result = got(first)
    run_dir = base / "runs" / result.run_id
    started, finished = events(run_dir, "discriminate.started"), events(run_dir, "discriminate.finished")
    assert len(started) == 1 and len(finished) == 1
    started, finished = started[0], finished[0]
    assert started["detail"] == "task=DISC-C cells=2"
    assert re.fullmatch(r"outcome=written plan_ms=\d+ engine_ms=\d+ grade_ms=\d+ compare_ms=\d+ write_ms=\d+ cells=2", finished["detail"])
    assert finished["error_code"] is None
    link = json.loads((run_dir / "discrimination-link.json").read_text(encoding="utf-8"))
    assert set(link["timings"]) == {"plan_ms", "engine_ms", "grade_ms", "compare_ms", "write_ms"}
    assert all(isinstance(v, int) for v in link["timings"].values())


def test_a_failed_trial_logs_null_for_what_it_never_reached(base, monkeypatch):
    """Acceptance 14: `null`, never 0, for a field that was not recorded; the error code rides in `error_code`."""
    bad = base / "bad_agent.py"
    bad.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(discriminate, "AGENT", bad)
    root = new_root(base)
    with pytest.raises(BenchError):
        trial(base, root)
    (run_dir,) = [p for p in (base / "runs").iterdir() if p.is_dir()]
    finished = events(run_dir, "discriminate.finished")
    assert len(finished) == 1
    finished = finished[0]
    assert finished["error_code"] == "HB-RDY-011"
    assert re.fullmatch(r"outcome=failed-engine plan_ms=\d+ engine_ms=\d+ grade_ms=\w+ compare_ms=null write_ms=null cells=2", finished["detail"])


def test_every_reader_of_a_stored_plan_is_in_the_reader_table():
    """T-E19 / R2-4: a new `load_confirmed` or `plan.json` reader under src/ fails here until it is added to the table.
    Direct readers only: `report/pack_improvement.py` reads `RunView.plan`, which `views.py` loads, so it is transitive and
    deliberately not listed; the refusals of a discrimination run themselves join at X-INT (owners X-C, X-A1)."""
    src = Path(__file__).resolve().parents[1] / "src" / "harness_bench"
    found = set()
    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        if rel == "plan.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "load_confirmed(" in text or '"plan.json"' in text:
            found.add(rel)
    assert found == {"cli.py", "grade/runner.py", "status.py", "views.py", "readiness.py", "campaign.py", "resume.py"}


def test_no_option_a_branch_and_no_hand_rolled_identity_or_matrix_validation_in_the_three_modules():
    """Acceptance 4 and 12 (greps): the record compare is `create_once`'s bytes or the field-naming diff after unequal
    bytes; the matrix is built in memory; `readiness.py` drops no `builds/*` key itself."""
    src = Path(__file__).resolve().parents[1] / "src" / "harness_bench"
    import ast

    def literals(name: str) -> list[str]:
        """String literals that are code, not docstrings."""
        tree = ast.parse((src / name).read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef)
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]

    texts = {n: (src / n).read_text(encoding="utf-8") for n in ("discriminate.py", "readiness.py", "synthetic_agent.py")}
    code = "\n".join(texts.values())
    assert "validate_matrix" not in code.replace("`validate_matrix`", "") and "config.HARNESSES" not in code
    assert not [s for s in literals("readiness.py") if "builds/" in s or s == "builds"]
    assert "os.environ" not in texts["discriminate.py"].replace("`os.environ`", "")
    assert re.findall(r"\w*subset\w*", texts["readiness.py"] + texts["discriminate.py"]) == ["subset"], "only the matrix key"


BLOAT = {"file": "turn-2/app.py", "old": "    sym, dec = RATES[cur]\n    return f'{sym}{amount:.{dec}f}'\n",
         "new": "    entry = RATES[cur]\n    prefix = entry[0]\n    digits = entry[1]\n    return f'{prefix}{amount:.{digits}f}'\n"}

def turns_variant(declared_clause: str) -> dict:
    """A turn-2 rewrite that keeps both turns' hidden tests green and pushes rework_ratio over the 0.3 ceiling."""
    return {"vratio": {"flips": ["property_check_pass", "rework_ratio"], "clauses": {"property_check_pass": declared_clause},
                        "edits": [BLOAT]}}


def test_a_check_less_variant_declaring_the_clause_property_json_records_is_compared_and_clean(base):
    """X-FIXD (W1-E s7 (4'), SR-E3 2): the rework strategy decided on the ratio clause; the declared one equals it."""
    root = new_root(base, "disc_turns_v", variants=mt.variants_text(turns_variant("ratio")))
    result = trial(base, root, "DISC-T")
    assert result.outcome == "written"
    rec = record_of(result)["variants"]["vratio"]
    assert rec["clauses"] == {"property_check_pass": "ratio"}
    assert rec["hidden_tests_pass"] == 1
    assert [f for f in readiness.record_failures(root, "DISC-T") if f.code == "HB-RDY-003"] == []


def test_a_check_less_variant_declaring_a_different_clause_is_hb_rdy_003_on_assertion_4(base):
    """X-FIXD: property.json says ratio, the variant declares turn1: the clause is UNDECLARED and (4) names the variant."""
    root = new_root(base, "disc_turns_v", variants=mt.variants_text(turns_variant("turn1")))
    result = trial(base, root, "DISC-T")
    assert result.outcome == "written"
    assert record_of(result)["variants"]["vratio"]["clauses"] == {"property_check_pass": discriminate.UNDECLARED}
    failures = [f for f in readiness.record_failures(root, "DISC-T") if f.code == "HB-RDY-003" and f.item == "vratio"]
    assert len(failures) == 1 and "(4)" in failures[0].detail


def test_a_check_less_variant_declaring_a_clause_where_property_json_has_no_strategy_is_hb_rdy_011(base):
    """X-FIXD: DISC-C has no turns, so its rework section is never written; a declared clause cannot be confirmed."""
    one = {"vnone": {"flips": [], "clauses": {"property_check_pass": "ratio"},
                      "edits": [{"file": "app.py", "old": "x * 2", "new": "2 * x"}]}}
    root = new_root(base, "disc_c", variants=mt.variants_text(one))
    with pytest.raises(BenchError) as exc:
        trial(base, root)
    assert exc.value.code == "HB-RDY-011" and "variant vnone" in exc.value.message and "SR-E3" not in exc.value.message


def test_a_check_less_trial_fails_on_a_hidden_test_disagreement(base, monkeypatch):
    """SHAPE-A row 4 (R-90 condition 3): the double-run item runs for a check-less task too, not only a check-based one."""
    root = new_root(base)
    real = readiness.comparable_cells
    monkeypatch.setattr(readiness, "comparable_cells", lambda run_dir, gid: ([sorted(readiness._rows(run_dir, gid))[0]], real(run_dir, gid)[1]))
    with pytest.raises(BenchError) as err:
        trial(base, root)
    assert err.value.code == "HB-RDY-011"
    assert "hidden tests disagree with pass_at_1 in" in str(err.value)
