"""Archive, verify, then delete (US-19; ADR-0006 archive commitment; ADR-0010 no link following)."""

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from harness_bench import archive, atomic, oslock
from harness_bench.errors import BenchError


def test_snapshot_cancel_between_files_sweeps_the_failed_publish(tmp_path, monkeypatch):
    cell = _cell(tmp_path)
    dest = tmp_path / "run/archive/c"
    cancel = threading.Event()
    copied = []
    real = archive._copy_hashed

    def cancel_after_file(src, dst):
        result = real(src, dst)
        copied.append(src.name)
        cancel.set()
        return result

    monkeypatch.setattr(archive, "_copy_hashed", cancel_after_file)
    with pytest.raises(InterruptedError):
        archive.snapshot_cell(cell, dest, 1, set(), cancel)
    assert len(copied) == 1
    assert not (dest / "turn-1").exists()
    assert atomic.stale_temps(dest) == []


def test_snapshot_sweep_refuses_another_runs_held_lock(tmp_path):
    cell = _cell(tmp_path)
    dest = tmp_path / "run/archive/c"
    dest.mkdir(parents=True)
    orphan = dest / "turn-1.tmp-123-12345678901234567890123456789012"
    orphan.mkdir()
    lock = oslock.RunLock.acquire(tmp_path / "other-run/.lock")
    try:
        with pytest.raises(ValueError, match="this run's lock"):
            archive.snapshot_cell(cell, dest, 1, set(), run_lock=lock)
        assert orphan.is_dir()
        assert not (dest / "turn-1").exists()
    finally:
        lock.release()


def _cell(tmp_path) -> Path:
    cell = tmp_path / "cell"
    (cell / "ws" / "src").mkdir(parents=True)
    (cell / "ws" / "src" / "slug.py").write_text("def slugify(t): return t\n", encoding="utf-8")
    (cell / "ws" / "answer.txt").write_bytes(b"42\r\n")
    (cell / "home" / "projects" / "x").mkdir(parents=True)
    (cell / "home" / "projects" / "x" / "s.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")
    (cell / "home" / ".credentials.json").write_text('{"token":"secret"}', encoding="utf-8")
    (cell / "home" / "auth.json").write_text('{"k":"v"}', encoding="utf-8")
    return cell


def test_archive_copies_every_file_but_credentials_and_commits_a_hash(tmp_path):
    cell = _cell(tmp_path)
    result = archive.archive_cell(cell, tmp_path / "archive" / "c1", attempt=1, exclude_names={".credentials.json", "auth.json"})
    paths = {r["path"] for r in result.rows}
    assert paths == {"ws/src/slug.py", "ws/answer.txt", "home/projects/x/s.jsonl"}
    assert (tmp_path / "archive" / "c1" / "attempt-1" / "ws" / "answer.txt").read_bytes() == b"42\r\n"
    assert not (tmp_path / "archive" / "c1" / "attempt-1" / "home" / ".credentials.json").exists()
    assert len(result.archive_hash) == 64
    assert all(r["archive_attempt"] == 1 and r["kind"] == "file" and len(r["sha256"]) == 64 for r in result.rows)


def test_the_archive_hash_is_a_commitment_over_the_rows(tmp_path):  # T-LED-archive-hash
    result = archive.archive_cell(_cell(tmp_path), tmp_path / "a", attempt=1, exclude_names=set())
    assert archive.archive_hash(result.rows) == result.archive_hash
    tampered = [dict(r) for r in result.rows]
    tampered[0]["size"] += 1
    assert archive.archive_hash(tampered) != result.archive_hash


def test_verify_detects_a_changed_archived_file(tmp_path):
    result = archive.archive_cell(_cell(tmp_path), tmp_path / "a", attempt=1, exclude_names=set())
    archive.verify(result.folder, result.rows)
    (result.folder / "ws" / "answer.txt").write_bytes(b"41\r\n")
    with pytest.raises(BenchError) as e:
        archive.verify(result.folder, result.rows)
    assert e.value.code == "HB-LED-005"


def test_links_are_recorded_never_followed(tmp_path):
    """The link mechanism differs by host (a Windows NTFS junction has no POSIX equivalent), but the
    behaviour under test -- archive.archive_cell records a link and never walks into it -- is the same
    cross-platform recipe (archive.py's `_is_link`: `path.is_symlink() or is_junction()`). On Windows this
    keeps the original `mklink /J` junction; on POSIX (macos-latest CI, ADR-0013 Amendment 1) a directory
    symlink is the equivalent escape a cell's working copy could contain, so `os.symlink` proves the same
    guarantee there."""
    cell = _cell(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("do not copy", encoding="utf-8")
    link = cell / "ws" / "escape"
    if sys.platform == "win32":
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if made.returncode != 0:
            pytest.skip("cannot create a junction here")
    else:
        os.symlink(outside, link, target_is_directory=True)
    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    rows = {r["path"]: r for r in result.rows}
    assert rows["ws/escape"]["kind"] == "link" and rows["ws/escape"]["link_target"]
    assert "ws/escape/secret.txt" not in rows
    assert not (result.folder / "ws" / "escape" / "secret.txt").exists()


@pytest.mark.native  # T-ARC-locked measures a Windows-only mechanism (mandatory file locking / sharing
# violation): opening a file for read blocks `shutil.rmtree` deleting it on Windows, but not on POSIX,
# where an open-but-unlinked file's data simply outlives the unlink until the last fd closes and rmtree
# itself succeeds -- there is no POSIX mirror of this guarantee to write (ADR-0013 Amendment 1, macOS port).
def test_delete_only_after_verification_and_retry_on_a_held_file(tmp_path):  # T-ARC-locked
    cell = _cell(tmp_path)
    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    held = (cell / "ws" / "answer.txt").open("rb")  # a Windows sharing violation
    try:
        assert not archive.delete_after_verify(cell, result.folder, result.rows, retries=2, wait=0.05)
        assert cell.exists()
    finally:
        held.close()
    assert archive.delete_after_verify(cell, result.folder, result.rows, retries=2, wait=0.05)
    assert not cell.exists()


def test_delete_is_refused_when_the_archive_does_not_verify(tmp_path):
    cell = _cell(tmp_path)
    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    os.remove(result.folder / "ws" / "answer.txt")
    with pytest.raises(BenchError):
        archive.delete_after_verify(cell, result.folder, result.rows)
    assert cell.exists()


def test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds(tmp_path):
    cell = _cell(tmp_path)
    dest_root = tmp_path / "archive" / "c1"
    final = dest_root / "attempt-1"
    script = tmp_path / "kill_archive.py"
    script.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "from harness_bench import archive\n"
        "calls = 0\n"
        "real_copy = archive._copy_hashed\n"
        "def bad_copy(src, dest):\n"
        "    global calls\n"
        "    calls += 1\n"
        "    if calls == 3:\n"
        "        os._exit(3)\n"
        "    return real_copy(src, dest)\n"
        "archive._copy_hashed = bad_copy\n"
        "cell_dir = Path(sys.argv[1])\n"
        "dest_root = Path(sys.argv[2])\n"
        "archive.archive_cell(cell_dir, dest_root, attempt=1, exclude_names=set())\n",
        encoding="utf-8",
    )
    proc = subprocess.run([sys.executable, str(script), str(cell), str(dest_root)], check=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert proc.returncode == 3
    assert not final.exists()
    stale = atomic.stale_temps(dest_root)
    assert len(stale) == 1 and stale[0].is_dir()
    lock = oslock.RunLock.acquire(dest_root / ".lock")
    try:
        swept = atomic.sweep_temps(dest_root, lock)
        assert stale[0] in swept and not stale[0].exists()
        result = archive.archive_cell(cell, dest_root, attempt=1, exclude_names=set())
        assert final.exists()
        archive.verify(result.folder, result.rows)
    finally:
        lock.release()


def test_a_corrupted_copy_fails_verification_before_the_rename(tmp_path, monkeypatch):
    cell = _cell(tmp_path)
    dest_root = tmp_path / "archive" / "c1"
    real_copy = archive._copy_hashed

    def corrupt_copy(src: Path, dest: Path) -> tuple[int, str]:
        size, h = real_copy(src, dest)
        if dest.is_file() and dest.stat().st_size > 0:
            b = dest.read_bytes()
            flipped = bytes([b[0] ^ 0xFF]) + b[1:]
            dest.write_bytes(flipped)
        return size, h

    monkeypatch.setattr(archive, "_copy_hashed", corrupt_copy)
    with pytest.raises(BenchError) as exc:
        archive.archive_cell(cell, dest_root, attempt=1, exclude_names=set())
    assert exc.value.code == "HB-LED-005"
    assert not (dest_root / "attempt-1").exists()


@pytest.mark.parametrize("scenario", ["extra_file", "missing_file", "link_file", "empty_dir"])
def test_verify_rejects_an_extra_file_and_a_missing_file(tmp_path, scenario):
    cell = _cell(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "link_target.txt").write_text("outside", encoding="utf-8")
    link = cell / "ws" / "escape"
    if sys.platform == "win32":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, check=False,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        os.symlink(outside, link, target_is_directory=True)

    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    folder = result.folder
    rows = result.rows

    if scenario == "extra_file":
        (folder / "extra.txt").write_bytes(b"extra")
        with pytest.raises(BenchError) as exc:
            archive.verify(folder, rows)
        assert exc.value.code == "HB-LED-005"
    elif scenario == "missing_file":
        (folder / "ws" / "answer.txt").unlink()
        with pytest.raises(BenchError) as exc:
            archive.verify(folder, rows)
        assert exc.value.code == "HB-LED-005"
    elif scenario == "link_file":
        (folder / "ws" / "escape").write_bytes(b"file_at_link")
        with pytest.raises(BenchError) as exc:
            archive.verify(folder, rows)
        assert exc.value.code == "HB-LED-005"
    elif scenario == "empty_dir":
        (folder / "empty_dir").mkdir()
        archive.verify(folder, rows)


def test_archive_cell_refuses_when_a_complete_archive_exists(tmp_path):
    cell = _cell(tmp_path)
    dest_root = tmp_path / "archive" / "c1"
    archive.archive_cell(cell, dest_root, attempt=1, exclude_names=set())
    answer_path = dest_root / "attempt-1" / "ws" / "answer.txt"
    original_bytes = answer_path.read_bytes()
    with pytest.raises(BenchError) as exc:
        archive.archive_cell(cell, dest_root, attempt=1, exclude_names=set())
    assert exc.value.code == "HB-USR-002"
    assert answer_path.read_bytes() == original_bytes


def test_attempt_dirs_ignores_a_leaked_temp_sibling(tmp_path):
    run_dir = tmp_path / "run"
    cell_archive = run_dir / "archive" / "cell-1"
    cell_archive.mkdir(parents=True)
    a1 = cell_archive / "attempt-1"
    a2 = cell_archive / "attempt-2"
    a1.mkdir()
    a2.mkdir()
    leaked = cell_archive / "attempt-1.tmp-123-12345678901234567890123456789012"
    leaked.mkdir()
    got = archive.attempt_dirs(run_dir, "cell-1")
    assert got == [a1, a2]


def test_a_file_added_after_verify_is_caught_by_delete_after_verify(tmp_path):
    cell = _cell(tmp_path)
    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    (result.folder / "planted.txt").write_bytes(b"tamper")
    with pytest.raises(BenchError) as exc:
        archive.delete_after_verify(cell, result.folder, result.rows)
    assert exc.value.code == "HB-LED-005"
    assert cell.exists()


def test_the_judge_artifact_text_survives_a_leaked_archive_temp(tmp_path):
    from harness_bench.report import judges

    run_dir = tmp_path / "run"
    cell_archive = run_dir / "archive" / "cell-1"
    attempt = cell_archive / "attempt-1"
    (attempt / "ws").mkdir(parents=True)
    (attempt / "ws" / "out.txt").write_text("artifact-content", encoding="utf-8")
    leaked = cell_archive / "attempt-1.tmp-999-0123456789abcdef0123456789abcdef"
    leaked.mkdir()
    try:
        text = judges._artifact_text(run_dir, "cell-1", "out.txt")
    except ValueError as err:
        text = f"raised ValueError: {err}"
    assert text == "artifact-content"


def test_the_engine_archive_goes_through_publish_dir(base, monkeypatch):
    from test_engine import FakeLauncher, _plan, _run

    from harness_bench import atomic

    calls: list[Path] = []
    real_publish = atomic.publish_dir

    def spy_publish(final, fill, verify):
        calls.append(final)
        return real_publish(final, fill, verify)

    monkeypatch.setattr(atomic, "publish_dir", spy_publish)
    p = _plan(n_cells=2)
    summary, _, _ = _run(base, p, FakeLauncher({}))
    assert summary.exit_code == 0
    assert len(calls) == len(p["cells"])
    for final in calls:
        assert final.is_dir()


def test_bench_verify_passes_a_run_archived_by_the_atomic_path(tmp_path):
    import shutil

    import archived_runs as ar

    from harness_bench import ledger, views

    root = ar.make_root(tmp_path / "root")
    cell_dir = tmp_path / "cell1"
    (cell_dir / "ws").mkdir(parents=True)
    (cell_dir / "ws" / "slug.py").write_text(ar.GOOD, encoding="utf-8")
    (cell_dir / "home" / "sessions" / "2026" / "09").mkdir(parents=True)
    shutil.copy(ar.FIX / "native" / "codex" / "ok.jsonl", cell_dir / "home" / "sessions" / "2026" / "09" / "rollout-2026-09-23-sess-c1.jsonl")

    run_dir = ar.make_run(root, tmp_path / "runs", {"c1": None}, archived=set())
    res = archive.archive_cell(cell_dir, run_dir / "archive" / "c1", attempt=1, exclude_names=set())
    with ledger.SegmentWriter.reopen(run_dir / "events" / "engine-1.jsonl") as ev, \
            ledger.SegmentWriter.reopen(run_dir / "archive_files" / "engine-1.jsonl") as af:
        for row in res.rows:
            af.append({"kind": "archive_file", "run_id": "r1", "cell_id": "c1", **row})
        ev.append({"kind": "cell.archived", "cell_id": "c1", "archive_attempt": 1, "archive_hash": res.archive_hash})

    findings = views.verify(run_dir)
    errors = [f for f in findings if f.level == "error"]
    assert errors == []

