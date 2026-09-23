"""Archive, verify, then delete (US-19; ADR-0006 archive commitment; ADR-0010 no link following)."""

import os
import subprocess
from pathlib import Path

import pytest

from harness_bench import archive
from harness_bench.errors import BenchError


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
    cell = _cell(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("do not copy", encoding="utf-8")
    link = cell / "ws" / "escape"
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, check=False)
    if made.returncode != 0:
        pytest.skip("cannot create a junction here")
    result = archive.archive_cell(cell, tmp_path / "a", attempt=1, exclude_names=set())
    rows = {r["path"]: r for r in result.rows}
    assert rows["ws/escape"]["kind"] == "link" and rows["ws/escape"]["link_target"]
    assert "ws/escape/secret.txt" not in rows
    assert not (result.folder / "ws" / "escape" / "secret.txt").exists()


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
