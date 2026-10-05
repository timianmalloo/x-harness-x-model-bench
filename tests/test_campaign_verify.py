"""X-C1 proof: verify, sweep, ignore (W1-C section 13: V, S, G; brief items 27, 32).

Temp repos are real `git init` repos. Each guard has a red fixture and a mutant in tests/mutations/campaign.json.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time

import pytest
from test_cli_campaign import (
    CID,
    IDENT,
    PREREG,
    ROOT,
    attempt,
    bench,
    cdir,
    code_of,
    commit_all,
    defaults,
    git,
    ledger_path,
    make_link,
    make_repo,
    put,
    raw_rows,
    snapshot,
    walk_to,
)
from test_cli_campaign import append as append_row

from harness_bench import atomic, campaign, ledger

NONCE = "a" * 32


def errors_of(root, cid=CID):
    return [f for f in campaign.verify(root, cid) if f.level == "error"]


def temp_name(base="x.json", pid=7):
    return f"{base}.tmp-{pid}-{NONCE}"


def age(path, seconds):
    then = time.time() - seconds
    os.utime(path, (then, then))


# --- V: verify -----------------------------------------------------------------------------------------------------

def test_a_chain_break_is_named_with_its_line_v1(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "piloted")
    path = ledger_path(root)
    path.write_bytes(path.read_bytes().replace(b'"bench_commit":"f', b'"bench_commit":"e', 1))
    found = errors_of(root)
    assert found
    assert any(f.code == "HB-CMP-003" and "line 2" in f.detail for f in found)


@pytest.mark.parametrize(("folder", "obj"), [("identity", IDENT), ("prereg", PREREG), ("power", {"schema": "bench-power-inputs/1"})])
def test_name_not_hash_is_named_for_identity_prereg_power_v2(tmp_path, folder, obj):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    digest = put(root, obj, folder)
    assert errors_of(root) == []
    (cdir(root) / folder / f"{digest}.json").rename(cdir(root) / folder / f"{'0' * 64}.json")
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and f.path.endswith(f"{'0' * 64}.json") for f in found), found


DISCRIMINATION_NAME = f"{'a' * 16}-{'b' * 16}-win32.json"


def discrimination_body(task="T1", tv="a" * 64, ih="b" * 64):
    return {"schema": "bench-discrimination/1", "task": task, "task_version": tv, "identity_hash": ih, "platform": "win32"}


def tracked_world(tmp_path):
    """A committed campaign (two rows, one identity file) and one committed discrimination record; verify is clean."""
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    record = root / "bench" / "discrimination" / "T1" / DISCRIMINATION_NAME
    record.parent.mkdir(parents=True)
    record.write_bytes(ledger.canonical(discrimination_body()))
    commit_all(root, "world")
    assert errors_of(root) == []
    return root, record


def edit_identity(root, record):
    path = next((cdir(root) / "identity").glob("*.json"))
    path.write_bytes(path.read_bytes() + b" ")
    return path


def delete_identity(root, record):
    path = next((cdir(root) / "identity").glob("*.json"))
    path.unlink()
    return path


def delete_record(root, record):
    record.unlink()
    return record


def rename_record(root, record):
    target = record.with_name("renamed.json")
    record.rename(target)
    return target


def edit_record(root, record):
    record.write_bytes(ledger.canonical({**discrimination_body(), "scores": {"reference": {"m": 1}}}))
    return record


def wrong_task_record(root, record):
    other = record.with_name(f"{'c' * 16}-{'b' * 16}-win32.json")
    other.write_bytes(ledger.canonical(discrimination_body(task="T2", tv="c" * 64)))
    return other


TAMPER = [edit_identity, delete_identity, delete_record, rename_record, edit_record, wrong_task_record]


@pytest.mark.parametrize("tamper", TAMPER, ids=[t.__name__ for t in TAMPER])
def test_modified_deleted_or_renamed_committed_record_is_tampering_v3(tmp_path, tamper):
    root, record = tracked_world(tmp_path)
    touched = tamper(root, record)
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and touched.name in f.path for f in found), (tamper.__name__, found)


def test_a_rename_also_names_the_deleted_original_v3(tmp_path):
    root, record = tracked_world(tmp_path)
    rename_record(root, record)
    assert any(f.path.endswith(DISCRIMINATION_NAME) for f in errors_of(root))


def test_ledger_appends_pass_and_a_rewritten_prefix_is_refused_v4(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    git(root, "add", str(ledger_path(root).relative_to(root)))  # status "A "
    assert errors_of(root) == []
    put(root, IDENT, "identity")
    append_row(root, "baseline.recorded")  # "AM"
    assert errors_of(root) == []
    commit_all(root, "two rows")
    append_row(root, "pilot.passed")  # " M": an uncommitted append
    assert errors_of(root) == []
    git(root, "add", str(ledger_path(root).relative_to(root)))
    append_row(root, "admission.decided")  # "MM"
    assert errors_of(root) == []
    commit_all(root, "four rows")
    path = ledger_path(root)
    path.unlink()
    raw_rows(root, [("campaign.created", {"question": "rewritten"}), ("baseline.recorded", defaults("baseline.recorded")),
                    ("pilot.passed", defaults("pilot.passed")), ("admission.decided", defaults("admission.decided"))])
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and "HEAD" in f.detail for f in found), found


def test_a_committed_torn_tail_does_not_block_the_next_command_v4b(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    with ledger_path(root).open("ab") as handle:
        handle.write(b'{"kind":"pilot.pas')
    commit_all(root, "torn")
    append_row(root, "pilot.passed")  # reopen truncates the tail and records ledger.tail_repaired
    assert errors_of(root) == []
    assert campaign.read(root, CID).state == "piloted"


def test_a_committed_prefix_rewrite_is_refused_naming_the_commit_v4c(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    commit_all(root, "first")
    ledger_path(root).unlink()
    raw_rows(root, [("campaign.created", {"question": "rewritten"}), ("baseline.recorded", defaults("baseline.recorded")),
                    ("pilot.passed", defaults("pilot.passed"))])
    commit_all(root, "rewrite with a recomputed chain")
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and head[:12] in f.detail for f in found), found


def test_an_untracked_new_content_file_is_allowed_v5(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    commit_all(root, "base")
    digest = put(root, PREREG, "prereg")  # a content file no row names yet, not in HEAD
    assert (cdir(root) / "prereg" / f"{digest}.json").exists()
    assert errors_of(root) == []


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_a_leaked_temp_is_a_named_warning_not_a_failure_v6(tmp_path, capsys, kind):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    name = temp_name()
    leaked = cdir(root) / "identity" / name
    leaked.parent.mkdir(parents=True, exist_ok=True)
    if kind == "file":
        leaked.write_bytes(b"x")
    else:
        leaked.mkdir()
        (leaked / "inner.json").write_bytes(b"x")
    findings = campaign.verify(root, CID)
    warnings = [f for f in findings if f.level == "warning"]
    assert any(name in f.path or name in f.detail for f in warnings), findings
    assert [f for f in findings if f.level == "error"] == []
    capsys.readouterr()
    assert bench(root, "campaign", "verify", CID) == 0
    assert name in capsys.readouterr().err


def test_not_a_work_tree_is_refused_v8(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    raw_rows(root, [("campaign.created", defaults("campaign.created"))])
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and "work tree" in f.detail for f in found), found


V10_CASES = [
    ("identity", ["campaign.created", "baseline.recorded"], "identity_hash"),
    ("prereg", ["campaign.created", "baseline.recorded", "pilot.passed", "registered"], "prereg_hash"),
    ("power", ["campaign.created", "baseline.recorded", "power.recorded"], "input_hash"),
]


@pytest.mark.parametrize(("folder", "kinds", "field"), V10_CASES, ids=[c[0] for c in V10_CASES])
def test_a_referenced_hash_that_is_missing_is_named_v10(tmp_path, folder, kinds, field):
    root = make_repo(tmp_path)
    raw_rows(root, [(k, defaults(k)) for k in kinds])
    missing = defaults(kinds[-1])[field]
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and f"{folder}/{missing}.json" in f.detail.replace("\\", "/") for f in found), found


@pytest.mark.parametrize("flag", ["assume-unchanged", "skip-worktree"])
@pytest.mark.parametrize("target", ["ledger", "content"])
def test_assume_unchanged_and_skip_worktree_are_findings_v11(tmp_path, flag, target):
    root, _ = tracked_world(tmp_path)
    path = ledger_path(root) if target == "ledger" else next((cdir(root) / "identity").glob("*.json"))
    git(root, "update-index", f"--{flag}", str(path.relative_to(root)))
    if target == "ledger":
        raw_rows(root, [("pilot.passed", defaults("pilot.passed"))])
    else:
        path.write_bytes(path.read_bytes() + b" ")
    found = errors_of(root)
    assert any(flag in f.detail and path.name in f.path for f in found), found


def edit_gitignore_drop(line):
    def edit(root):
        gi = root / ".gitignore"
        gi.write_text("".join(f"{x}\n" for x in gi.read_text(encoding="utf-8").splitlines() if x != line), encoding="utf-8")
        return line
    return edit


def edit_gitignore_stray(root):
    with (root / ".gitignore").open("a", encoding="utf-8") as handle:
        handle.write("bench/campaigns/*/notes.txt\n")
    (cdir(root) / "notes.txt").write_text("hidden", encoding="utf-8")
    return "notes.txt"


def edit_exclude_stray(root):
    with (root / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
        handle.write("bench/campaigns/*/notes.txt\n")
    (cdir(root) / "notes.txt").write_text("hidden", encoding="utf-8")
    return "notes.txt"


V12 = [edit_gitignore_stray, edit_exclude_stray,
       *[edit_gitignore_drop(line) for line in ("bench/campaigns/**/*.tmp-*", "bench/discrimination/**/*.tmp-*", "bench/campaigns/*/campaign.lock")]]


@pytest.mark.parametrize("edit", V12, ids=["gitignore-stray", "exclude-stray", "drop-campaign-tmp", "drop-discrimination-tmp", "drop-lock"])
def test_an_ignored_stray_path_and_a_missing_gitignore_line_are_findings_v12(tmp_path, edit):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    assert errors_of(root) == []
    needle = edit(root)
    found = errors_of(root)
    assert any(f.code == "HB-CMP-003" and (needle in f.detail or needle in f.path) for f in found), found


# --- S: the sweep --------------------------------------------------------------------------------------------------

FOLDERS = ("", "identity", "prereg", "power")


def aged_temps(root, seconds):
    out = []
    for sub in FOLDERS:
        folder = cdir(root) / sub if sub else cdir(root)
        folder.mkdir(parents=True, exist_ok=True)
        temp = folder / temp_name(f"{sub or 'root'}.json")
        temp.write_bytes(b"x")
        age(temp, seconds)
        out.append(temp)
    return out


def test_an_old_temp_is_swept_under_the_lock_in_all_four_folders_s1(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    temps = aged_temps(root, 2 * campaign.TEMP_MIN_AGE_S)
    seen = []
    real = atomic.sweep_temps

    def spy(folder, lock):
        seen.append((folder, lock.held))
        return real(folder, lock)

    monkeypatch.setattr(atomic, "sweep_temps", spy)
    with campaign.session(root, CID) as s:
        swept = list(s.swept)
    assert not any(t.exists() for t in temps)
    assert sorted(swept) == sorted(temps)
    assert sorted(f for f, _ in seen) == sorted(cdir(root) / sub if sub else cdir(root) for sub in FOLDERS)
    assert seen
    assert all(held for _, held in seen)


def test_a_young_temp_keeps_its_whole_folder_s2(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    old = cdir(root) / temp_name("old.json")
    fresh = cdir(root) / temp_name("fresh.json", pid=8)
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    age(old, 2 * campaign.TEMP_MIN_AGE_S)
    with campaign.session(root, CID) as s:
        skipped = list(s.skipped)
    assert old.exists()
    assert fresh.exists()
    assert cdir(root) in skipped


def discrimination_task_dir(root):
    return root / "bench" / "discrimination" / "T1"


def test_a_linked_task_dir_is_refused_and_its_target_is_untouched_s4(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")  # the effective identity names tasks/T1
    target = tmp_path / "elsewhere"
    target.mkdir()
    leaked = target / temp_name()
    leaked.write_bytes(b"x")
    age(leaked, 2 * campaign.TEMP_MIN_AGE_S)
    make_link(discrimination_task_dir(root), target)
    before = snapshot(target.parent)

    def enter():
        with campaign.session(root, CID):
            pass

    err = attempt(enter)
    assert code_of(err) == "HB-CMP-003"
    assert "T1" in str(err)
    assert any("T1" in f.path for f in errors_of(root))
    assert snapshot(target.parent) == before


def test_a_session_never_sweeps_under_bench_discrimination_s4(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    leaked = discrimination_task_dir(root) / temp_name()
    leaked.parent.mkdir(parents=True)
    leaked.write_bytes(b"x")
    age(leaked, 2 * campaign.TEMP_MIN_AGE_S)
    with campaign.session(root, CID) as s:
        assert s.lock is not None
    assert leaked.exists()  # X-E sweeps that folder under its own lock (W0 section 4, rev 6)
    assert any(temp_name() in f.path for f in campaign.verify(root, CID) if f.level == "warning")


# --- G: the three ignore lines -------------------------------------------------------------------------------------

def test_gitignore_covers_every_temp_name_and_the_campaign_lock_g1(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    shutil.copy(ROOT / ".gitignore", root / ".gitignore")

    def ignored(rel):
        return git(root, "check-ignore", "-q", rel, check=False).returncode == 0

    nonce = temp_name("y.json", pid=3)
    must = [f"bench/campaigns/c/{temp_name('ledger.jsonl')}", f"bench/campaigns/c/identity/{nonce}", f"bench/discrimination/T1/{nonce}",
            f"bench/campaigns/c/power/z.tmp-2-{NONCE}/inner.json", f"bench/discrimination/T1/z.tmp-2-{NONCE}/inner.json",
            "bench/campaigns/c/campaign.lock"]
    must_not = ["bench/campaigns/c/identity/x.json", "bench/campaigns/c/campaign.lock.bak", "bench/campaigns/c/ledger.jsonl"]
    assert [p for p in must if not ignored(p)] == []
    assert [p for p in must_not if ignored(p)] == []


# --- item 27: lock-free readers against a writer ------------------------------------------------------------------

def test_a_temp_that_vanishes_between_listing_and_lstat_is_absent_not_a_finding(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    walk_to(root, "draft")
    leaked = cdir(root) / "power" / temp_name()
    leaked.parent.mkdir(parents=True)
    leaked.write_bytes(b"x")
    real = os.lstat

    def vanishing(path, *args, **kwargs):
        if atomic.is_temp_name(os.path.basename(os.fspath(path))):
            raise FileNotFoundError(path)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", vanishing)
    findings = campaign.verify(root, CID)
    assert [f for f in findings if f.level == "error"] == []
    assert campaign.read(root, CID).state == "draft"


def test_verify_loop_never_raises_while_a_writer_loop_sweeps_and_appends(tmp_path):
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    (cdir(root) / "power").mkdir()
    stop = threading.Event()
    seen: list = []

    def verifier():
        while True:
            try:
                seen.append(errors_of(root))
            except Exception as exc:  # noqa: BLE001  (any raise from a lock-free read is the failure this test hunts)
                seen.append(exc)
            if stop.is_set():
                return

    reader = threading.Thread(target=verifier)
    reader.start()
    try:
        for i in range(12):
            with campaign.session(root, CID) as s:
                assert s.lock is not None
                assert s.lock.held
                data = ledger.canonical({"schema": "bench-power-inputs/1", "alpha": i})
                digest = hashlib.sha256(data).hexdigest()
                atomic.create_once(cdir(root) / "power" / f"{digest}.json", data)  # the content file first, then its row
                campaign._append(s, "power.recorded", role="prior", input_hash=digest)
                atomic.sweep_temps(cdir(root) / "power", s.lock)
    finally:
        stop.set()
        reader.join(timeout=120)
    assert not reader.is_alive()
    assert seen
    assert [r for r in seen if r != []] == []
    assert len([r for r in campaign.read(root, CID).rows if r["kind"] == "power.recorded"]) == 12
