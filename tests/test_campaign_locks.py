"""X-C1 proof: locks, sessions and the path chain (W1-C section 13: L-3, L-4, L-5, L-8; brief items 26, 41).

The cross-process cases use a real second OS process (`held_by_another_process`). L-1, L-2, L-6, L-7, L-9 are C2's.
"""

from __future__ import annotations

import os
import shutil
import time

import pytest
from test_cli_campaign import (
    CID,
    QUESTION,
    attempt,
    bench,
    cdir,
    code_of,
    held_by_another_process,
    ledger_path,
    make_link,
    make_repo,
    snapshot,
    walk_to,
)

from harness_bench import campaign, oslock
from harness_bench.errors import BenchError

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
