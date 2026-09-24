"""`bench verify` against tampered ledgers (ADR-0006; ruling R-2; design: Exposed contracts, exit 5 = integrity).

Every probe drives the CLI (`harness_bench.cli.main`) and reads the exit code, the way an operator would.
- A completed grading pass records `heads` for its other facts in `grading.completed`; a completed run records
  `segment_heads` (and the in-run pass's summary) in `run.completed`. A missing, unsealed or mismatched segment
  under either is HB-LED-002, exit 5.
- A `grading.completed` without `heads` (written before R-2) verifies with a warning, never an error.
"""

import json
import shutil
from pathlib import Path

import pytest
from archived_runs import GOOD, complete_run, make_root, make_run
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_bench import archive, cli, ledger, views
from harness_bench.grade import runner

GOLDEN = Path(__file__).parent / "fixtures" / "ledger"
PASS_FACTS = ("model_calls", "tool_calls", "scores")


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _verify(capsys, tmp_path, run_id="r1"):
    code = cli.main(["--root", str(tmp_path), "--runs", str(tmp_path / "runs"), "verify", run_id])
    out, err = capsys.readouterr()
    return code, out, err


def _cut(path: Path, lines: int = 2) -> None:
    """Drop the last `lines` lines: for a sealed segment, its seal and last row."""
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:-lines]))


# --- a completed grading pass: grading.completed.heads -----------------------------------------------


@pytest.mark.parametrize("fact", PASS_FACTS)
def test_cutting_the_seal_and_last_row_of_a_completed_pass_is_exit_5(capsys, root, tmp_path, fact):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    assert _verify(capsys, tmp_path)[0] == 0
    _cut(run_dir / fact / f"{done.grading_id}.jsonl")
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002" in err and f"{fact}/{done.grading_id}" in err


@pytest.mark.parametrize("fact", PASS_FACTS)
def test_deleting_a_completed_pass_fact_segment_is_exit_5(capsys, root, tmp_path, fact):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    (run_dir / fact / f"{done.grading_id}.jsonl").unlink()
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002" in err and f"{fact}/{done.grading_id}" in err


# --- a completed run: run.completed.segment_heads and its in-run pass --------------------------------


@pytest.mark.parametrize("fact", ["turn_usage", "archive_files"])
def test_cutting_or_deleting_a_completed_run_segment_is_exit_5(capsys, root, tmp_path, fact):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    complete_run(run_dir)
    assert _verify(capsys, tmp_path)[0] == 0
    seg = run_dir / fact / "engine-1.jsonl"
    original = seg.read_bytes()
    _cut(seg, 1)  # the seal only: the rows still chain, the segment reads as unsealed
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and f"HB-LED-002: {fact}/engine-1" in err
    seg.write_bytes(original)
    seg.unlink()
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and f"HB-LED-002: {fact}/engine-1" in err


def test_the_in_run_pass_cannot_be_turned_into_an_abandoned_one(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    complete_run(run_dir, grading=done.summary())
    assert _verify(capsys, tmp_path)[0] == 0
    _cut(run_dir / "events" / f"{done.grading_id}.jsonl")  # its seal and grading.completed: it now reads as abandoned
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and f"events/{done.grading_id}" in err


def test_cutting_the_seal_after_run_completed_is_exit_5(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    complete_run(run_dir)
    _cut(run_dir / "events" / "engine-1.jsonl", 1)
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002: events/engine-1" in err


def test_a_malformed_heads_record_is_exit_5_not_a_crash(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    complete_run(run_dir, grading={"grading_id": "grade-x", "heads": ["scores"]})
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "heads is not a fact -> head map" in err


def test_a_sound_completed_run_with_long_cell_ids_verifies(capsys, root, tmp_path):  # ids compared by value
    run_dir = make_run(root, tmp_path, {"cell-alpha-0001": GOOD, "cell-bravo-0002": GOOD})
    complete_run(run_dir, grading=runner.run_pass(run_dir, root).summary())
    assert _verify(capsys, tmp_path) == (0, "verify: ok\n", "")


def test_archives_are_not_checked_against_a_ledger_whose_heads_fail(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    (run_dir / "scores" / f"{done.grading_id}.jsonl").unlink()
    (run_dir / "archive" / "a" / "attempt-1" / "ws" / "slug.py").write_text("tampered", encoding="utf-8")
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and err == f"HB-LED-002: scores/{done.grading_id}: missing, but grading.completed in events/{done.grading_id} records its head\n"


@pytest.mark.parametrize("forged", ["0" * 64, "f" * 64])  # a wrong head sorting below, or above, the true one
def test_a_recorded_head_that_does_not_match_is_exit_5(capsys, root, tmp_path, forged):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    complete_run(run_dir, grading={"grading_id": done.grading_id, "heads": {**done.heads, "scores": forged}})
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and f"HB-LED-002: scores/{done.grading_id}: head does not match the one run.completed" in err


def test_a_duplicate_outcome_is_an_integrity_finding_not_a_crash(capsys, root, tmp_path):  # HB-LED-003
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.outcome", "cell_id": "a", "outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"})
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and err.startswith("HB-LED-003: a second cell.outcome for cell a")


def test_each_archive_attempt_is_checked_against_its_own_rows(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    shutil.copytree(run_dir / "archive" / "a" / "attempt-1", run_dir / "archive" / "a" / "attempt-300")  # past the small-int cache
    rows = [{k: v for k, v in r.items() if k not in ledger.CHAIN_FIELDS} | {"archive_attempt": 300}
            for r in ledger.read_segment(run_dir / "archive_files" / "engine-1.jsonl")]
    with ledger.SegmentWriter.create(run_dir / "archive_files", "engine-2") as af:
        for r in rows:
            af.append(r)
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.archived", "cell_id": "a", "archive_attempt": 300, "archive_hash": archive.archive_hash(rows)})
    assert _verify(capsys, tmp_path) == (0, "verify: ok\n", "")


@pytest.mark.parametrize("forged", ["0" * 64, "f" * 64])
def test_an_archive_hash_mismatch_is_found_whichever_way_it_sorts(capsys, root, tmp_path, monkeypatch, forged):
    make_run(root, tmp_path, {"a": GOOD, "b": GOOD})
    monkeypatch.setattr(views.archive, "archive_hash", lambda rows: forged)
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and err.count("archive_hash does not match") == 2  # every cell is checked, not only the first


def test_a_run_completed_naming_the_wrong_events_head_is_exit_5(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    complete_run(run_dir, events_head=ledger.genesis("forged"))
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002: events/engine-1" in err


# --- D2: any byte change, cut or insert in a completed run is detected ------------------------------------


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("completed")
    run_dir = make_run(make_root(tmp), tmp, {"a": GOOD})
    complete_run(run_dir)
    return run_dir


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_any_change_to_a_completed_run_ledger_is_detected(tmp_path_factory, completed_run, data):
    run_dir = tmp_path_factory.mktemp("tamper") / "r1"
    shutil.copytree(completed_run, run_dir)
    seg = run_dir / data.draw(st.sampled_from(["events", "turn_usage", "archive_files"])) / "engine-1.jsonl"
    raw = seg.read_bytes()
    op = data.draw(st.sampled_from(["byte", "cut", "insert"]))
    i = data.draw(st.integers(min_value=0, max_value=len(raw) - (0 if op == "insert" else 1)))
    if op == "byte":
        tampered = raw[:i] + bytes([data.draw(st.integers(0, 255).filter(lambda b: b != raw[i]))]) + raw[i + 1:]
    elif op == "cut":
        tampered = raw[:i] + raw[data.draw(st.integers(min_value=i + 1, max_value=len(raw))):]
    else:
        tampered = raw[:i] + data.draw(st.binary(min_size=1, max_size=40)) + raw[i:]
    seg.write_bytes(tampered)
    errors = [f for f in views.verify(run_dir) if f.level == "error"]
    # detected: an integrity error, or the run no longer reads as completed (cut back to before run.completed)
    assert errors or not any(e["kind"] == "run.completed" for e in views.rows(run_dir, "events"))


# --- D6 golden ledgers ----------------------------------------------------------------------------------


def _golden(tmp_path: Path, name: str, tampered: bool = False) -> tuple[Path, dict]:
    src = GOLDEN / name
    run_dir = tmp_path / "runs" / "r1"
    shutil.copytree(src / "run", run_dir)
    if tampered:
        shutil.copytree(src / "tampered", run_dir, dirs_exist_ok=True)
    return run_dir, json.loads((src / "expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["c44dd2b-no-heads", "heads"])
def test_a_golden_ledger_keeps_its_hashes_and_row_counts(tmp_path, name):
    run_dir, expected = _golden(tmp_path, name)
    got = {}
    for key in expected["segments"]:
        report = ledger.verify_segment(run_dir / key)
        got[key] = {"head_hash": report.head_hash, "rows": report.lines, "sealed": report.sealed, "error": report.error}
    assert got == {k: {"head_hash": v["head_hash"], "rows": v["rows"], "sealed": v["sealed"], "error": None}
                   for k, v in expected["segments"].items()}
    kinds = {key.split("/")[0] for key in expected["segments"]}
    assert kinds == {"events", "turn_usage", "archive_files", "model_calls", "tool_calls", "scores"}  # every row type


def test_the_ledger_written_before_heads_verifies_with_a_warning(capsys, tmp_path):  # R-2: warning, never an error
    _, expected = _golden(tmp_path, "c44dd2b-no-heads")
    code, out, err = _verify(capsys, tmp_path)
    assert code == 0 and out.endswith("verify: ok\n")
    for gid in (expected["in_run_pass"], expected["later_pass"]):
        assert f"events/{gid}: grading.completed records no heads" in err and "(warning)" in err


def test_the_ledger_written_with_heads_verifies_clean(capsys, tmp_path):
    run_dir, expected = _golden(tmp_path, "heads")
    completed = ledger.read_segment(run_dir / "events" / f"{expected['later_pass']}.jsonl")[-1]
    assert completed["kind"] == "grading.completed" and set(completed["heads"]) == {"model_calls", "tool_calls", "scores"}
    assert _verify(capsys, tmp_path) == (0, "verify: ok\n", "")


@pytest.mark.parametrize("name", ["c44dd2b-no-heads", "heads"])
def test_a_tampered_golden_ledger_is_exit_5(capsys, tmp_path, name):
    _, expected = _golden(tmp_path, name, tampered=True)
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002" in err and expected["tampered"].split(":")[0].removesuffix(".jsonl") in err


# --- a later pass cannot be rolled back into an abandoned one (Test Architect N1) ------------------------
# The honest runner seals a pass's events segment only after `grading.completed` (grade/runner.py), so a
# sealed `events/grade-*` segment without that row was cut back and re-sealed: HB-LED-002, exit 5.


def test_a_later_pass_cut_before_grading_completed_and_resealed_is_exit_5(capsys, tmp_path):
    run_dir, expected = _golden(tmp_path, "heads")
    later = expected["later_pass"]
    seg = run_dir / "events" / f"{later}.jsonl"
    _cut(seg)  # its seal and grading.completed
    w = ledger.SegmentWriter.reopen(seg)
    w.seal()
    w.close()
    assert later not in views.completed_passes(run_dir)  # the views would fall back to the in-run pass
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and f"HB-LED-002: events/{later}: sealed, but holds no grading.completed" in err


def _interrupt_at(monkeypatch, point: str, seen: list) -> None:
    """Make the next pass verify the ledger at `point`, as it stands mid-pass, then die there."""

    def probe_and_die(run_dir: Path) -> None:
        seen.append(views.verify(run_dir))
        raise OSError(f"interrupted at {point}")

    if point == "grading a cell":
        monkeypatch.setattr(runner._Pass, "_grade_cell", lambda self, *a: probe_and_die(self.run_dir))
    elif point == "before grading.completed":  # every other fact is sealed by now
        real_append = runner._Pass.append

        def append(self, fact, record):
            if record["kind"] == "grading.completed":
                probe_and_die(self.run_dir)
            real_append(self, fact, record)

        monkeypatch.setattr(runner._Pass, "append", append)
    else:  # "before the events seal": grading.completed is written, the seal is not
        real_seal = ledger.SegmentWriter.seal

        def seal(self):
            if self.path.parent.name == "events" and self.segment_id.startswith(views.GRADE_PREFIX):
                probe_and_die(self.path.parent.parent)
            return real_seal(self)

        monkeypatch.setattr(ledger.SegmentWriter, "seal", seal)


@pytest.mark.parametrize("point", ["grading a cell", "before grading.completed", "before the events seal"])
def test_an_in_progress_or_interrupted_pass_is_a_warning_never_an_error(capsys, root, tmp_path, monkeypatch, point):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    seen: list = []
    _interrupt_at(monkeypatch, point, seen)
    with pytest.raises(OSError, match=point):
        runner.run_pass(run_dir, root)
    monkeypatch.undo()
    [gid] = [p.stem for p in views.segment_paths(run_dir, "events") if p.stem.startswith(views.GRADE_PREFIX)]
    assert not ledger.verify_segment(run_dir / "events" / f"{gid}.jsonl").sealed  # an unfinished pass is never sealed
    [in_progress] = seen
    assert [f for f in in_progress if f.level == "error"] == []
    code, _, err = _verify(capsys, tmp_path)
    assert code == 0 and f"HB-LED-004: events/{gid}: abandoned grading segment, skipped by views (warning)" in err
    runner.run_pass(run_dir, root)  # the next pass names it and completes
    assert _verify(capsys, tmp_path)[0] == 0
