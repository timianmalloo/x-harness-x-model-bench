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

from harness_bench import cli, ledger
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


def test_a_run_completed_naming_the_wrong_events_head_is_exit_5(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    complete_run(run_dir, events_head=ledger.genesis("forged"))
    code, _, err = _verify(capsys, tmp_path)
    assert code == 5 and "HB-LED-002: events/engine-1" in err


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
