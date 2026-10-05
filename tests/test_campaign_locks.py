"""X-C1 proof: locks, sessions and the path chain (W1-C section 13: L-3, L-4, L-5, L-8; brief items 26, 41).

The cross-process cases use a real second OS process (`held_by_another_process`). L-1, L-2, L-6, L-7, L-9 are C2's.
"""

from __future__ import annotations

import ast
import json
import multiprocessing
import os
import shutil
import time
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run
from test_cli_campaign import (
    CID,
    QUESTION,
    attached,
    attempt,
    bench,
    cdir,
    code_of,
    held_by_another_process,
    ledger_path,
    make_link,
    make_repo,
    snapshot,
    tree,
    walk_to,
)

from harness_bench import campaign, oslock, plan
from harness_bench.errors import BenchError
from harness_bench.grade import runner

NONCE = "a" * 32


def lock_file(root):
    return campaign.lock_path(root, CID)


def enter(root, cid=CID, **kwargs):
    with campaign.session(root, cid, **kwargs):
        pass


def test_a_held_campaign_lock_refuses_with_hb_cmp_001_and_sweeps_nothing_l3(tmp_path, capsys):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    temp = cdir(root) / f"x.json.tmp-1-{NONCE}"
    temp.write_bytes(b"x")
    then = time.time() - 2 * campaign.TEMP_MIN_AGE_S
    os.utime(temp, (then, then))
    before = ledger_path(root).read_bytes()
    with held_by_another_process(lock_file(root)):
        assert code_of(attempt(enter, root)) == "HB-CMP-001"
        capsys.readouterr()
        assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 1
        assert "HB-CMP-001" in capsys.readouterr().err
        assert temp.exists()  # item 26: the refused command swept nothing
    assert ledger_path(root).read_bytes() == before


def corrupt_the_chain(root):
    path = ledger_path(root)
    path.write_bytes(path.read_bytes().replace(QUESTION.encode(), b"does the pack hexp", 1))


def test_the_lock_is_held_inside_and_released_on_every_path_l4(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    path = lock_file(root)

    with campaign.session(root, CID) as s:
        assert s.lock is not None
        assert s.lock.held
        assert oslock.is_held(path)
    assert not oslock.is_held(path)

    def boom():
        with campaign.session(root, CID) as s:
            assert s.lock is not None
            assert s.lock.held
            raise RuntimeError("forced")

    assert isinstance(attempt(boom), RuntimeError)
    assert not oslock.is_held(path)

    def illegal():
        with campaign.session(root, CID) as s:
            assert s.lock is not None
            assert s.lock.held
            campaign._append(s, "concluded")

    assert code_of(attempt(illegal)) == "HB-CMP-002"
    assert not oslock.is_held(path)

    corrupt_the_chain(root)
    assert code_of(attempt(enter, root)) == "HB-CMP-003"
    assert not oslock.is_held(path)


@pytest.mark.parametrize("shape", ["folder", "link"])
def test_a_lock_that_is_a_folder_or_a_link_is_refused_naming_it_l5(tmp_path, shape):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    target = tmp_path / "somewhere"
    target.mkdir()
    lock_file(root).unlink()  # the session that built the campaign left a plain lock file
    if shape == "folder":
        lock_file(root).mkdir()
    else:
        make_link(lock_file(root), target)
    before = snapshot(tmp_path)
    err = attempt(enter, root)
    assert code_of(err) == "HB-CMP-003", err
    assert "campaign.lock" in str(err)
    assert any("campaign.lock" in f.path for f in campaign.verify(root, CID) if f.level == "error")
    assert snapshot(tmp_path) == before


def link_ledger(root, cid):
    moved = root.parent / "moved-ledger.jsonl"
    shutil.move(ledger_path(root), moved)
    try:
        ledger_path(root).symlink_to(moved)
    except OSError as exc:
        pytest.skip(f"file symlinks need a privilege this host lacks ({exc}); the POSIX job runs this case")


def link_folder(name):
    def make(root, cid):
        moved = root.parent / f"moved-{name}"
        shutil.move(cdir(root) / name, moved)
        make_link(cdir(root) / name, moved)
    return make


def link_campaign_dir(root, cid):
    moved = root.parent / "moved-campaign"
    shutil.move(cdir(root), moved)
    make_link(cdir(root), moved)


def link_task_dir(root, cid):
    target = root.parent / "moved-task"
    target.mkdir()
    make_link(root / "bench" / "discrimination" / "T1", target)


L8 = [("ledger", link_ledger, "ledger.jsonl"), ("identity", link_folder("identity"), "identity"),
      ("campaign folder", link_campaign_dir, CID), ("discrimination task", link_task_dir, "T1")]


@pytest.mark.parametrize(("label", "make", "needle"), L8, ids=[c[0] for c in L8])
def test_links_and_junctions_in_the_path_chain_are_refused_l8(tmp_path, label, make, needle):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    make(root, CID)
    found = [f for f in campaign.verify(root, CID) if f.level == "error"]
    assert any(f.code == "HB-CMP-003" and needle in f.path for f in found), (label, found)
    err = attempt(enter, root)
    assert code_of(err) == "HB-CMP-003", (label, err)
    assert needle in str(err)


# --- item 41: the sweep pairs this campaign's lock with this campaign's four folders --------------------------------

PAIRED = ("", "identity", "prereg", "power")


def aged_temp_in(folder):
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / f"k.json.tmp-1-{NONCE}"
    temp.write_bytes(b"x")
    then = time.time() - 2 * campaign.TEMP_MIN_AGE_S
    os.utime(temp, (then, then))
    return temp


@pytest.mark.parametrize("sub", PAIRED, ids=["root", "identity", "prereg", "power"])
def test_sweep_refuses_a_lock_that_does_not_guard_the_folder_item41(tmp_path, sub):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    folder = cdir(root) / sub if sub else cdir(root)
    temp = aged_temp_in(folder)
    with oslock.RunLock.acquire(tmp_path / "another-folders.lock", "HB-CMP-001") as other:
        assert other.held
        err = attempt(campaign.sweep_folder, cdir(root), folder, other)
        assert isinstance(err, ValueError), err
        assert temp.exists()
    with oslock.RunLock.acquire(lock_file(root), "HB-CMP-001") as right:
        swept, skipped = campaign.sweep_folder(cdir(root), folder, right)
    assert swept == [temp]
    assert skipped == []
    assert not temp.exists()


def test_sweep_refuses_a_folder_that_is_not_one_of_the_four_item41(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    stray = cdir(root) / "elsewhere"
    temp = aged_temp_in(stray)
    with oslock.RunLock.acquire(lock_file(root), "HB-CMP-001") as right:
        err = attempt(campaign.sweep_folder, cdir(root), stray, right)
    assert isinstance(err, ValueError), err
    assert temp.exists()


def test_an_unknown_campaign_names_the_item_and_an_action_n1(tmp_path):
    root = make_repo(tmp_path)
    err = attempt(enter, root, "nope")
    assert isinstance(err, BenchError)
    assert code_of(err) == "HB-CMP-005"
    assert "nope" in str(err)


# === C2a: the handshake, both sides (L-1, L-2, L-6, L-7, L-9; the grading-side probe of Coordinator #23 gap (a)) ===

RACES = 4
LOCK_ROOT = Path(__file__).resolve().parents[1]


def _campaign_side(root, barrier, queue):
    """The campaign side of the pair: `session` (own `campaign.lock`, then the attached runs' locks), `between` on the barrier."""
    try:
        with campaign.session(Path(root), CID, between=lambda: barrier.wait(timeout=10)):
            queue.put({"proceeded": True, "code": None})
    except BenchError as exc:
        queue.put({"proceeded": False, "code": exc.code})
    except Exception as exc:  # noqa: BLE001  (reported to the parent as an error, never as a refusal)
        queue.put({"proceeded": False, "code": None, "error": repr(exc)})


def _grade_side(root, barrier, queue):
    """The grading side, written as `grade/runner.py` calls it: own `grade.lock`, then the campaign lock."""
    try:
        lock = oslock.acquire_then_probe(Path(root) / "runs" / "R2" / "grade.lock", "HB-GRD-001",
                                         [(campaign.lock_path(Path(root), CID), "HB-GRD-007")], between=lambda: barrier.wait(timeout=10))
        lock.release()
        queue.put({"proceeded": True, "code": None})
    except BenchError as exc:
        queue.put({"proceeded": False, "code": exc.code})
    except Exception as exc:  # noqa: BLE001
        queue.put({"proceeded": False, "code": None, "error": repr(exc)})


def _conclude_side(root, barrier, queue):
    try:
        with campaign.session(Path(root), CID, run_locks=True, between=lambda: barrier.wait(timeout=10)) as s:
            campaign._append(s, "concluded")
            queue.put({"proceeded": True, "code": None})
    except BenchError as exc:
        queue.put({"proceeded": False, "code": exc.code})
    except Exception as exc:  # noqa: BLE001
        queue.put({"proceeded": False, "code": None, "error": repr(exc)})


def _run_side(root, doc_text, barrier, queue):
    """The run side: the run lock first, then `run_side_check` (what the engine does through `campaign_check=`)."""
    lock = oslock.RunLock.acquire(Path(root) / "runs" / "R2" / ".lock", "HB-RUN-005")
    try:
        barrier.wait(timeout=10)
        campaign.run_side_check(Path(root), json.loads(doc_text), "R2")
        queue.put({"proceeded": True, "code": None})
    except BenchError as exc:
        queue.put({"proceeded": False, "code": exc.code})
    except Exception as exc:  # noqa: BLE001
        queue.put({"proceeded": False, "code": None, "error": repr(exc)})
    finally:
        lock.release()


def race(left, right, args_left, args_right):
    """Two OS processes on one barrier; their two results. A hung or dead side fails the test, never hangs it (60 s, `terminate()`)."""
    ctx = multiprocessing.get_context("spawn")
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    procs = [ctx.Process(target=left, args=(*args_left, barrier, queue)), ctx.Process(target=right, args=(*args_right, barrier, queue))]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(60)
    for proc in procs:
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
    assert [proc.exitcode for proc in procs] == [0, 0]
    return [queue.get(timeout=5), queue.get(timeout=5)]


def test_the_campaign_and_the_grading_side_never_both_proceed_l1(tmp_path):
    """Barrier races between the two operations of each side: both may refuse, one may proceed after the other refused, never both.
    The swapped order (probe, then acquire) lets both proceed in every race, so this test fails on M-L1."""
    root = tree(tmp_path)
    attached(root)
    before = ledger_path(root).read_bytes()
    for _ in range(RACES):
        results = race(_campaign_side, _grade_side, (str(root),), (str(root),))
        assert all("error" not in item for item in results), results
        assert not (results[0]["proceeded"] and results[1]["proceeded"]), results
        for item in results:
            assert item["proceeded"] or item["code"] in {"HB-CMP-004", "HB-GRD-007"}, item
    assert ledger_path(root).read_bytes() == before


def test_a_conclusion_and_a_run_start_never_both_proceed_l9(tmp_path):
    for index in range(2):
        root = tree(tmp_path, f"race{index}")
        doc = attached(root)
        results = race(_conclude_side, _run_side, (str(root),), (str(root), json.dumps(doc)))
        assert all("error" not in item for item in results), results
        assert not (results[0]["proceeded"] and results[1]["proceeded"]), results
        assert (campaign.read(root, CID).state == "concluded") == results[0]["proceeded"]


def test_a_command_is_refused_while_a_campaign_run_is_graded_l2(tmp_path, capsys):
    root = tree(tmp_path)
    attached(root)
    before = snapshot(cdir(root))
    with held_by_another_process(root / "runs" / "R2" / "grade.lock"):
        capsys.readouterr()
        assert bench(root, "campaign", "abandon", CID, "--reason", "x") == 1
        err = capsys.readouterr().err
    assert "HB-CMP-004" in err and "grade.lock" in err and "R2" in err
    assert snapshot(cdir(root)) == before
    assert not oslock.is_held(campaign.lock_path(root, CID))


def test_the_probe_set_is_the_attached_runs_plus_the_argument_only_l6(tmp_path):
    root = tree(tmp_path)
    attached(root)  # R2 is attached
    unrelated = root / "runs" / "R9" / "grade.lock"
    unrelated.parent.mkdir(parents=True)
    with held_by_another_process(unrelated):
        assert attempt(enter, root) is None  # an unrelated run's grading does not block
    with held_by_another_process(root / "runs" / "R2" / "grade.lock"):
        assert code_of(attempt(enter, root)) == "HB-CMP-004"  # an attached run's does
    with held_by_another_process(root / "runs" / "R2" / ".lock"):
        assert attempt(enter, root) is None  # only conclude and abandon (`run_locks`) probe the run lock
        assert code_of(attempt(enter, root, run_locks=True)) == "HB-CMP-004"
    argument = root / "runs" / "R5" / "grade.lock"
    argument.parent.mkdir(parents=True)
    with held_by_another_process(argument):
        assert code_of(attempt(enter, root, others_extra=[(argument, "HB-CMP-004")])) == "HB-CMP-004"  # the command's own run argument


def lock_pair_calls(source: str) -> dict:
    """The `acquire_then_probe` calls whose third argument is a sequence of entries (a name, list or comprehension), and every plain
    `.acquire(...)` call that names `grade.lock`."""
    calls, plain = [], []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr == "acquire_then_probe" and len(node.args) >= 3 and isinstance(node.args[2], (ast.Name, ast.List, ast.ListComp, ast.BinOp)):
            calls.append(node.lineno)
        if node.func.attr == "acquire" and "grade.lock" in ast.unparse(node):
            plain.append(node.lineno)
    return {"calls": calls, "plain": plain}


def test_both_sides_call_the_same_helper_with_a_set_l7():
    plain_runner = 'def run_pass(run_dir):\n    with oslock.RunLock.acquire(run_dir / "grade.lock", "HB-GRD-001"):\n        pass\n'
    by_probe = 'def run_pass(run_dir, other):\n    if oslock.is_held(other):\n        raise X\n    oslock.RunLock.acquire(run_dir / "grade.lock")\n'
    assert lock_pair_calls(plain_runner) == {"calls": [], "plain": [2]}  # the red fixtures: a runner that never calls the helper
    assert lock_pair_calls(by_probe) == {"calls": [], "plain": [4]}
    src = LOCK_ROOT / "src" / "harness_bench"
    for module in ("campaign.py", "grade/runner.py"):
        found = lock_pair_calls((src / module).read_text(encoding="utf-8"))
        assert found["calls"] and not found["plain"], (module, found)


def campaign_plan(root, run_dir):
    doc = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    doc["campaign"] = {"campaign_id": CID, "prereg_hash": None, "identity": {"hash": "h" * 64, "components": {}}}
    doc["plan_hash"] = plan.plan_hash(doc)
    (run_dir / "plan.json").write_text(json.dumps(doc), encoding="utf-8")


def test_grading_side_probes_campaign_lock_only_for_a_campaign_plan(tmp_path):
    root = make_root(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with_block = make_run(root, tmp_path / "a", {"a": GOOD})
    campaign_plan(root, with_block)
    with held_by_another_process(campaign.lock_path(root, CID)):
        exc = attempt(runner.run_pass, with_block, root)
    assert code_of(exc) == "HB-GRD-007"
    assert not list((with_block / "events").glob("grade-*.jsonl")), "a refused pass wrote a grading row"
    shutil.rmtree(root / "bench" / "campaigns")  # the holder's own folder; the next pass must create nothing here
    without_block = make_run(root, tmp_path / "b", {"a": GOOD})
    result = runner.run_pass(without_block, root)
    assert result.grading_id.startswith("grade-")
    assert not (root / "bench" / "campaigns").exists()
