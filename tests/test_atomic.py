"""Crash-atomic helpers (W1-B B1a): create_once, temps, sweep, make_writable, rename_with_retry."""

from __future__ import annotations

import logging
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

import pytest

from harness_bench import atomic, oslock
from harness_bench.errors import BenchError

NONCE = "0123456789abcdef0123456789abcdef"
LOG = "harness_bench.atomic"


def _temp(folder: Path, base: str, pid: str = "1", nonce: str = NONCE) -> Path:
    return folder / f"{base}.tmp-{pid}-{nonce}"


def _can_symlink(tmp_path: Path) -> bool:
    src = tmp_path / "_sym_src"
    src.write_bytes(b"x")
    dest = tmp_path / "_sym_dest"
    try:
        dest.symlink_to(src)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            return False
        raise
    dest.unlink()
    src.unlink()
    return True


def _junction_or_dirlink(link: Path, target: Path) -> None:
    if os.name == "nt":
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(link), str(target)])
        return
    link.symlink_to(target, target_is_directory=True)


def _held_lock(tmp_path: Path) -> oslock.RunLock:
    return oslock.RunLock.acquire(tmp_path / ".lock")


def test_create_once_round_trips_the_bytes_that_text_mode_corrupts(tmp_path):
    path = tmp_path / "bytes.bin"
    payload = b"a\nb\r\nc\n"
    assert atomic.create_once(path, payload) is True
    assert path.read_bytes() == payload


def test_create_once_creates_then_noops_on_equal_bytes(tmp_path, caplog):
    path = tmp_path / "once.json"
    with caplog.at_level(logging.WARNING, logger=LOG):
        assert atomic.create_once(path, b"same") is True
        assert atomic.create_once(path, b"same") is False
    assert path.read_bytes() == b"same"
    assert not any(atomic.is_temp_name(p.name) for p in tmp_path.iterdir())
    assert [r.getMessage() for r in caplog.records if r.getMessage() == "atomic.create_once"] == []


def test_create_once_refuses_different_bytes_and_keeps_the_original(tmp_path, caplog):
    path = tmp_path / "once.json"
    assert atomic.create_once(path, b"original") is True
    with caplog.at_level(logging.WARNING, logger=LOG), pytest.raises(BenchError) as ei:
        atomic.create_once(path, b"other")
    assert ei.value.code == "HB-LED-007"
    assert str(path) in ei.value.message
    assert path.read_bytes() == b"original"
    assert not any(atomic.is_temp_name(p.name) for p in tmp_path.iterdir())
    records = [r for r in caplog.records if r.getMessage() == "atomic.create_once"]
    assert len(records) == 1
    assert records[0].outcome == "conflict"
    assert records[0].error_code == "HB-LED-007"


def test_a_kill_between_write_and_link_leaves_no_final_file(tmp_path):
    path = tmp_path / "once.json"
    script = tmp_path / "kill_link.py"
    script.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "from harness_bench import atomic\n"
        "os.link = lambda *a, **k: os._exit(3)\n"
        "atomic.create_once(Path(sys.argv[1]), b'payload')\n",
        encoding="utf-8",
    )
    proc = subprocess.run([sys.executable, str(script), str(path)], check=False)
    assert proc.returncode == 3
    assert not path.exists()
    stale = atomic.stale_temps(tmp_path)
    assert len(stale) == 1 and stale[0].is_file()
    lock = _held_lock(tmp_path)
    try:
        assert atomic.create_once(path, b"payload") is True
        assert path.read_bytes() == b"payload"
        swept = atomic.sweep_temps(tmp_path, lock)
        assert stale[0] in swept
        assert not stale[0].exists()
    finally:
        lock.release()


def test_create_once_temp_names_are_unique_and_exclusive(tmp_path, monkeypatch):
    path = tmp_path / "once.json"
    opened: list[str] = []
    real_open = os.open

    def spy(name, flags, *args, **kwargs):
        opened.append(os.path.basename(name))
        return real_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy)
    assert atomic.create_once(path, b"a") is True
    path.unlink()
    assert atomic.create_once(path, b"b") is True
    temps = [n for n in opened if atomic.TEMP_RE.fullmatch(n)]
    assert len(temps) == 2 and temps[0] != temps[1]

    pid, nonce = "4242", "ab" * 16
    monkeypatch.setattr(os, "getpid", lambda: int(pid))
    monkeypatch.setattr(
        "harness_bench.atomic.uuid4",
        lambda: UUID(hex=nonce),
    )
    squat = path.with_name(f"{path.name}.tmp-{pid}-{nonce}")
    squat.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        atomic.create_once(path, b"fresh")
    assert squat.read_bytes() == b"keep"


def test_create_once_refuses_a_non_regular_existing_path(tmp_path):
    path = tmp_path / "folder"
    path.mkdir()
    with pytest.raises(Exception) as ei:
        atomic.create_once(path, b"x")
    assert isinstance(ei.value, BenchError)
    assert ei.value.code == "HB-LED-007"
    assert "not a regular file" in ei.value.message
    assert path.is_dir()
    assert not any(atomic.is_temp_name(p.name) for p in tmp_path.iterdir() if p != path)


def test_create_once_refuses_a_symlink_existing_path(tmp_path):
    if not _can_symlink(tmp_path):
        pytest.skip("winerror 1314: no symlink right")
    target = tmp_path / "real"
    target.write_bytes(b"keep-me")
    path = tmp_path / "once.json"
    path.symlink_to(target)
    with pytest.raises(BenchError) as ei:
        atomic.create_once(path, b"x")
    assert ei.value.code == "HB-LED-007"
    assert target.read_bytes() == b"keep-me"


def test_create_once_refuses_a_file_swapped_in_before_the_link(tmp_path, monkeypatch):
    path = tmp_path / "once.json"
    other = tmp_path / "premade"
    other.write_bytes(b"premade-bytes")
    real_link = os.link

    def swap(src, dst, **kwargs):
        real_link(other, dst)

    monkeypatch.setattr(os, "link", swap)
    with pytest.raises(BenchError) as ei:
        atomic.create_once(path, b"written")
    assert ei.value.code == "HB-LED-007"
    assert not path.exists()
    assert other.read_bytes() == b"premade-bytes"
    assert not any(atomic.TEMP_RE.fullmatch(p.name) for p in tmp_path.iterdir())


@pytest.mark.parametrize("step", ["fsync", "link_eperm", "link_missing"])
def test_create_once_leaves_no_temp_and_propagates_when_a_step_fails(tmp_path, monkeypatch, step):
    path = tmp_path / "once.json"
    boom: OSError
    if step == "fsync":
        boom = OSError(28, "No space left on device")
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(boom))
    elif step == "link_eperm":
        boom = OSError(1, "Operation not permitted")
        monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(boom))
    else:
        boom = FileNotFoundError("link target vanished")
        monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(boom))
    with pytest.raises(OSError) as ei:
        atomic.create_once(path, b"data")
    assert ei.value is boom
    assert not path.exists()
    assert [p for p in tmp_path.iterdir() if atomic.TEMP_RE.fullmatch(p.name)] == []


def test_create_once_returns_true_when_the_temp_unlink_fails(tmp_path, monkeypatch, caplog):
    path = tmp_path / "once.json"
    real_unlink = os.unlink
    failed: list[Path] = []

    def flaky(name, *args, **kwargs):
        p = Path(name)
        if not failed and atomic.TEMP_RE.fullmatch(p.name):
            failed.append(p)
            raise PermissionError(13, "Access is denied")
        return real_unlink(name, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", flaky)
    with caplog.at_level(logging.WARNING, logger=LOG):
        assert atomic.create_once(path, b"kept") is True
    assert path.read_bytes() == b"kept"
    leaked = [r for r in caplog.records if r.getMessage() == "atomic.temp_leaked"]
    assert len(leaked) == 1
    assert failed[0].name in leaked[0].path
    lock = _held_lock(tmp_path)
    try:
        swept = atomic.sweep_temps(tmp_path, lock)
        assert failed[0] in swept or not failed[0].exists()
    finally:
        lock.release()


def test_stale_temps_lists_every_strict_temp_in_the_folder(tmp_path):
    folder = tmp_path / "records"
    folder.mkdir()
    known = _temp(folder, "deadbeef.json", pid="12")
    known.write_bytes(b"orphan")
    nested = _temp(folder, "attempt-1", pid="3")
    nested.mkdir()
    notes = folder / "records.tmp-notes"
    notes.write_bytes(b"user")
    short = folder / f"x.tmp-1-{NONCE[:-1]}"
    short.write_bytes(b"short")
    (folder / "final").write_bytes(b"keep")
    names = {p.name for p in atomic.stale_temps(folder)}
    assert known.name in names
    assert nested.name in names
    assert notes.name not in names
    assert short.name not in names
    assert "final" not in names
    assert atomic.is_temp_name(known.name)
    assert atomic.is_temp_name(nested.name)
    assert not atomic.is_temp_name(notes.name)
    assert not atomic.is_temp_name(short.name)
    assert not atomic.is_temp_name(f"{known.name}\n")
    assert not atomic.is_temp_name("final")


def test_sweep_temps_lists_a_temp_whose_base_no_caller_knows(tmp_path):
    folder = tmp_path / "campaign"
    folder.mkdir()
    unknown = _temp(folder, "cafebabe.json")
    unknown.write_bytes(b"in-flight")
    lock = _held_lock(tmp_path)
    try:
        assert unknown in atomic.stale_temps(folder)
        swept = atomic.sweep_temps(folder, lock)
        assert unknown in swept
        assert not unknown.exists()
    finally:
        lock.release()


def test_sweep_temps_skips_a_vanished_entry(tmp_path, monkeypatch):
    folder = tmp_path / "campaign"
    folder.mkdir()
    ghost = _temp(folder, "gone.json")
    ghost.write_bytes(b"x")
    real = atomic.stale_temps

    def listing(path):
        found = real(path)
        for p in found:
            p.unlink()
        return found

    monkeypatch.setattr(atomic, "stale_temps", listing)
    lock = _held_lock(tmp_path)
    try:
        assert atomic.sweep_temps(folder, lock) == []
    finally:
        lock.release()


def test_sweep_temps_unlinks_reparse_points_without_recursing(tmp_path, caplog):
    folder = tmp_path / "camp"
    folder.mkdir()
    sentinel_dir = tmp_path / "outside"
    sentinel_dir.mkdir()
    sentinel = sentinel_dir / "keep.txt"
    sentinel.write_bytes(b"alive")
    junction = _temp(folder, "junc")
    _junction_or_dirlink(junction, sentinel_dir)
    ro_dir = _temp(folder, "rodir", pid="2")
    ro_dir.mkdir()
    ro_file = ro_dir / "ro.txt"
    ro_file.write_bytes(b"ro")
    ro_file.chmod(0o444)
    lock = _held_lock(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger=LOG):
            swept = atomic.sweep_temps(folder, lock)
        assert junction in swept and not junction.exists()
        assert sentinel.exists() and sentinel.read_bytes() == b"alive"
        assert ro_dir in swept and not ro_dir.exists()
        records = [r for r in caplog.records if r.getMessage() == "atomic.temp_swept"]
        kinds = {Path(r.path).name: r.kind for r in records}
        assert kinds[junction.name] == "link"
        assert kinds[ro_dir.name] == "dir"
    finally:
        lock.release()


def test_sweep_temps_unlinks_a_symlink_inside_a_temp_folder(tmp_path, caplog):
    if not _can_symlink(tmp_path):
        pytest.skip("winerror 1314: no symlink right")
    folder = tmp_path / "camp"
    folder.mkdir()
    sentinel = tmp_path / "outside.txt"
    sentinel.write_bytes(b"alive")
    tree = _temp(folder, "tree")
    tree.mkdir()
    (tree / "inner").symlink_to(sentinel)
    lock = _held_lock(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger=LOG):
            atomic.sweep_temps(folder, lock)
        assert not tree.exists()
        assert sentinel.read_bytes() == b"alive"
    finally:
        lock.release()


def test_sweep_temps_raises_when_a_temp_cannot_be_removed(tmp_path, monkeypatch):
    folder = tmp_path / "camp"
    folder.mkdir()
    first = _temp(folder, "a.json", pid="1")
    second = _temp(folder, "b.json", pid="2")
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    real = os.unlink

    def boom(name, *args, **kwargs):
        if Path(name) == first:
            raise OSError(13, "Access is denied")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", boom)
    lock = _held_lock(tmp_path)
    try:
        with pytest.raises(OSError):
            atomic.sweep_temps(folder, lock)
        assert second.exists()
    finally:
        lock.release()


def test_sweep_temps_removes_temps_only_while_the_lock_is_held(tmp_path):
    folder = tmp_path / "camp"
    folder.mkdir()
    temp = _temp(folder, "x.json")
    temp.write_bytes(b"x")
    lock = _held_lock(tmp_path)
    try:
        assert temp in atomic.sweep_temps(folder, lock)
        assert not temp.exists()
        temp.write_bytes(b"x")
    finally:
        lock.release()
    assert lock.held is False
    with pytest.raises(ValueError, match="writer lock"):
        atomic.sweep_temps(folder, lock)
    assert temp.exists()


def test_sweep_temps_refuses_a_released_lock_while_another_process_holds_the_file(tmp_path):
    folder = tmp_path / "camp"
    folder.mkdir()
    temp = _temp(folder, "unknown.json")
    temp.write_bytes(b"in-flight")
    lock_path = tmp_path / "campaign.lock"
    lock_a = oslock.RunLock.acquire(lock_path)
    lock_a.release()
    assert lock_a.held is False
    src = str(oslock.__file__).rsplit("harness_bench", 1)[0]
    code = (
        f"import sys,time;sys.path.insert(0,{src!r});from harness_bench import oslock;"
        f"l=oslock.RunLock.acquire(__import__('pathlib').Path({str(lock_path)!r}));"
        f"print('held',flush=True);time.sleep(600)"
    )
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(ValueError, match="writer lock"):
            atomic.sweep_temps(folder, lock_a)
        assert temp.exists()
    finally:
        holder.kill()
        holder.wait()


@pytest.mark.parametrize("case", ["twice", "always", "exists"])
def test_a_rename_refused_n_times(tmp_path, monkeypatch, case):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.write_bytes(b"x")
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    real = os.rename
    n = {"calls": 0}

    def flaky(a, b):
        n["calls"] += 1
        if case == "twice":
            if n["calls"] <= 2:
                raise PermissionError(13, "Access is denied")
            return real(a, b)
        if case == "always":
            raise PermissionError(13, "Access is denied")
        raise FileExistsError(17, "File exists")

    monkeypatch.setattr(os, "rename", flaky)
    if case == "twice":
        try:
            retries = atomic.rename_with_retry(src, dst)
        except PermissionError:
            retries = -1
        assert retries == 2
        assert dst.read_bytes() == b"x"
        assert sleeps == list(atomic.RENAME_BACKOFF[:2])
        return
    if case == "always":
        with pytest.raises(PermissionError):
            atomic.rename_with_retry(src, dst)
        assert n["calls"] == len(atomic.RENAME_BACKOFF)
        assert not dst.exists() and src.exists()
        assert sleeps == list(atomic.RENAME_BACKOFF[:-1])
        return
    with pytest.raises(FileExistsError):
        atomic.rename_with_retry(src, dst)
    assert n["calls"] == 1
    assert sleeps == []


def test_make_writable_adds_write_bit_keeping_other_bits(tmp_path, monkeypatch):
    path = tmp_path / "ro"
    path.write_bytes(b"x")
    path.chmod(0o444)
    modes: list[int] = []
    real_chmod = os.chmod

    def spy(p, mode):
        modes.append(mode)
        return real_chmod(p, mode)

    monkeypatch.setattr(os, "chmod", spy)
    atomic.make_writable(lambda p: None, path, None)
    assert modes and modes[0] != stat.S_IWRITE
    assert modes[0] & stat.S_IWUSR
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode & stat.S_IWUSR


def test_make_writable_does_not_chmod_through_a_link(tmp_path):
    if not _can_symlink(tmp_path):
        pytest.skip("winerror 1314: no symlink right")
    sentinel = tmp_path / "target"
    sentinel.write_bytes(b"x")
    sentinel.chmod(0o444)
    before = stat.S_IMODE(os.lstat(sentinel).st_mode)
    link = tmp_path / "link"
    link.symlink_to(sentinel)
    atomic.make_writable(os.unlink, link, None)
    assert not link.exists()
    assert stat.S_IMODE(os.lstat(sentinel).st_mode) == before
    assert not (before & stat.S_IWUSR)


def test_the_posix_job_does_not_skip_the_symlink_variants(tmp_path):
    if os.name != "posix":
        pytest.skip("Windows: symlink variants skip only on winerror 1314")
    assert _can_symlink(tmp_path)


def test_posix_flag_default_follows_the_platform():
    assert atomic._POSIX == (os.name == "posix")
