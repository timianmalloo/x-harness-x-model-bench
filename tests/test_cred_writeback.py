"""R-SETTINGS: the Grok credential seed and write-back (ADR-0025 s7, CRED-COPY-A).

A cell seeds its credential copy from the bench credential home (the profile's `credential_home_env`), and before
`clean` deletes the copy, a changed copy is written back atomically, under an oslock on the credential home held from
seed to write-back. The profile here is a fixture: `bench/profiles/grok.yaml` is R-TRANSPORT's.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from harness_bench import oslock, profiles
from harness_bench.errors import BenchError

ENV = "HB_GROK_CRED_HOME"


def _profile() -> profiles.Profile:
    # credential.source is resolved against the credential home; credential.name is the copy inside the cell home
    return profiles.Profile("grok", "GROK_HOME", Path("auth.json"), ".grok/auth.json", ("{exe}",),
                            credential_home_env=ENV)


def _bench(tmp_path: Path, monkeypatch, token: str = "tok-1") -> Path:
    bench = tmp_path / "grok-cred"
    bench.mkdir()
    (bench / "auth.json").write_text(token, encoding="utf-8")
    monkeypatch.setenv(ENV, str(bench))
    return bench


def _launcher(tmp_path: Path, **kw) -> profiles.ProfileLauncher:
    return profiles.ProfileLauncher(_profile(), tmp_path, {}, **kw)


def _refresh(home: Path, token: str) -> None:
    """The fake harness: its refresh rotates the token in the cell's copy."""
    (home / ".grok" / "auth.json").write_text(token, encoding="utf-8")


def test_two_sequential_cells_carry_the_rotated_token_through_the_bench_home(tmp_path, monkeypatch):
    bench = _bench(tmp_path, monkeypatch)
    launcher = _launcher(tmp_path)
    for n, home in enumerate((tmp_path / "c1" / "home", tmp_path / "c2" / "home"), start=1):
        launcher.seed(home, {"model": "grok-4.7"})
        assert (home / ".grok" / "auth.json").read_text(encoding="utf-8") == f"tok-{n}"
        _refresh(home, f"tok-{n + 1}")
        launcher.clean(home)
        assert (bench / "auth.json").read_text(encoding="utf-8") == f"tok-{n + 1}"
        assert not (home / ".grok" / "auth.json").exists()
    assert sorted(p.name for p in bench.iterdir() if p.name != profiles.CRED_LOCK_NAME) == ["auth.json"]


def test_unchanged_bytes_are_not_written(tmp_path, monkeypatch):
    bench = _bench(tmp_path, monkeypatch)
    replaced = []
    real_replace = os.replace
    monkeypatch.setattr(profiles.os, "replace", lambda a, b: (replaced.append(b), real_replace(a, b)))
    launcher = _launcher(tmp_path)
    before = (bench / "auth.json").stat().st_mtime_ns
    launcher.seed(tmp_path / "home", {"model": "grok-4.7"})
    launcher.clean(tmp_path / "home")
    assert replaced == []
    assert (bench / "auth.json").stat().st_mtime_ns == before
    assert not (tmp_path / "home" / ".grok" / "auth.json").exists()


def test_the_lock_is_held_from_seed_to_write_back(tmp_path, monkeypatch):
    bench = _bench(tmp_path, monkeypatch)
    launcher = _launcher(tmp_path)
    launcher.seed(tmp_path / "home", {"model": "grok-4.7"})
    assert oslock.is_held(bench / profiles.CRED_LOCK_NAME)
    launcher.clean(tmp_path / "home")
    assert not oslock.is_held(bench / profiles.CRED_LOCK_NAME)


def test_a_second_engine_waits_on_the_lock_and_seeds_the_newest_token(tmp_path, monkeypatch):
    _bench(tmp_path, monkeypatch)
    first, second = _launcher(tmp_path), _launcher(tmp_path)
    home_a, home_b = tmp_path / "a" / "home", tmp_path / "b" / "home"
    first.seed(home_a, {"model": "grok-4.7"})
    done = threading.Event()
    thread = threading.Thread(target=lambda: (second.seed(home_b, {"model": "grok-4.7"}), done.set()))
    thread.start()
    assert not done.wait(0.5), "the second engine seeded while the first held the credential home"
    _refresh(home_a, "tok-2")
    first.clean(home_a)
    assert done.wait(10)
    thread.join()
    assert (home_b / ".grok" / "auth.json").read_text(encoding="utf-8") == "tok-2"
    second.clean(home_b)


def test_a_lock_not_released_within_the_wait_fails_the_seed_without_a_copy(tmp_path, monkeypatch):
    bench = _bench(tmp_path, monkeypatch)
    held = oslock.RunLock.acquire(bench / profiles.CRED_LOCK_NAME)
    try:
        launcher = _launcher(tmp_path, cred_lock_wait=0.2)
        started = time.monotonic()
        with pytest.raises(BenchError) as err:
            launcher.seed(tmp_path / "home", {"model": "grok-4.7"})
        assert time.monotonic() - started >= 0.2
        assert err.value.code == "HB-CELL-202"
        assert not (tmp_path / "home" / ".grok" / "auth.json").exists()
        launcher.clean(tmp_path / "home")  # the engine's finally: nothing held, nothing written
        assert (bench / "auth.json").read_text(encoding="utf-8") == "tok-1"
    finally:
        held.release()


def test_an_unset_credential_home_is_refused_at_seed(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    with pytest.raises(BenchError) as err:
        _launcher(tmp_path).seed(tmp_path / "home", {"model": "grok-4.7"})
    assert err.value.code == "HB-USR-002" and ENV in err.value.message


# --- the credential pool (ADR-0025 s7 Am. 2026-10-13): the variable names several homes, joined by os.pathsep -------

def _pool(tmp_path: Path, monkeypatch, *names: str) -> list[Path]:
    homes = []
    for name in names:
        home = tmp_path / name
        home.mkdir()
        (home / "auth.json").write_text(f"{name}-1", encoding="utf-8")
        homes.append(home)
    monkeypatch.setenv(ENV, os.pathsep.join(str(h) for h in homes))
    return homes


def test_two_concurrent_cells_take_different_homes_and_each_writes_back_to_its_own(tmp_path, monkeypatch):
    a, b = _pool(tmp_path, monkeypatch, "pool-a", "pool-b")
    launcher = _launcher(tmp_path, cred_lock_wait=0.2)
    one, two = tmp_path / "c1" / "home", tmp_path / "c2" / "home"
    launcher.seed(one, {"model": "grok-4.7"})
    launcher.seed(two, {"model": "grok-4.7"})  # the first cell still holds its home: no wait, the second home
    assert (one / ".grok" / "auth.json").read_text(encoding="utf-8") == "pool-a-1"
    assert (two / ".grok" / "auth.json").read_text(encoding="utf-8") == "pool-b-1"
    assert oslock.is_held(a / profiles.CRED_LOCK_NAME) and oslock.is_held(b / profiles.CRED_LOCK_NAME)
    _refresh(one, "pool-a-2")
    _refresh(two, "pool-b-2")
    launcher.clean(two)  # out of seed order: each copy goes back to the home it came from
    launcher.clean(one)
    assert (a / "auth.json").read_text(encoding="utf-8") == "pool-a-2"
    assert (b / "auth.json").read_text(encoding="utf-8") == "pool-b-2"
    assert not oslock.is_held(a / profiles.CRED_LOCK_NAME) and not oslock.is_held(b / profiles.CRED_LOCK_NAME)


def test_a_seeded_cell_records_the_credential_file_it_came_from_and_clean_removes_the_record(tmp_path, monkeypatch):
    """Resume (a dead cell's leftover copy) writes back to the recorded file, never to the profile's relative source
    (`auth.json`, which would land in the bench's cwd). The record is a path, kept out of the archive like the copy."""
    _a, b = _pool(tmp_path, monkeypatch, "pool-a", "pool-b")
    launcher = _launcher(tmp_path, cred_lock_wait=0.2)
    launcher.seed(tmp_path / "c1" / "home", {"model": "grok-4.7"})
    two = tmp_path / "c2" / "home"
    launcher.seed(two, {"model": "grok-4.7"})
    marker = two / profiles.CRED_SOURCE_MARKER
    assert Path(marker.read_text(encoding="utf-8")) == (b / "auth.json").resolve()
    assert profiles.CRED_SOURCE_MARKER in launcher.credential_names  # excluded from the cell archive
    launcher.clean(two)
    assert not marker.exists()


def test_a_held_home_is_skipped_without_waiting(tmp_path, monkeypatch):
    a, _ = _pool(tmp_path, monkeypatch, "pool-a", "pool-b")
    held = oslock.RunLock.acquire(a / profiles.CRED_LOCK_NAME)
    try:
        launcher = _launcher(tmp_path, cred_lock_wait=1.0)  # a wait on the held home fails the seed (HB-CELL-202)
        launcher.seed(tmp_path / "home", {"model": "grok-4.7"})
        assert (tmp_path / "home" / ".grok" / "auth.json").read_text(encoding="utf-8") == "pool-b-1"
        launcher.clean(tmp_path / "home")
    finally:
        held.release()


def test_a_cell_waits_while_every_home_is_held_and_takes_the_first_one_freed(tmp_path, monkeypatch):
    a, b = _pool(tmp_path, monkeypatch, "pool-a", "pool-b")
    held_a, held_b = oslock.RunLock.acquire(a / profiles.CRED_LOCK_NAME), oslock.RunLock.acquire(b / profiles.CRED_LOCK_NAME)
    try:
        launcher = _launcher(tmp_path)
        done = threading.Event()
        thread = threading.Thread(target=lambda: (launcher.seed(tmp_path / "home", {"model": "grok-4.7"}), done.set()))
        thread.start()
        assert not done.wait(0.5), "a cell seeded while every home of the pool was held"
        held_b.release()  # the second home frees first
        assert done.wait(10)
        thread.join()
        assert (tmp_path / "home" / ".grok" / "auth.json").read_text(encoding="utf-8") == "pool-b-1"
        launcher.clean(tmp_path / "home")
    finally:
        held_a.release()
        held_b.release()


def test_a_profile_without_a_credential_home_is_unchanged(tmp_path):
    source = tmp_path / "auth.json"
    source.write_text("tok", encoding="utf-8")
    p = profiles.Profile("codex", "CODEX_HOME", source, "auth.json", ("{exe}",))
    launcher = profiles.ProfileLauncher(p, tmp_path, {})
    launcher.seed(tmp_path / "home", {"model": "m"})
    (tmp_path / "home" / "auth.json").write_text("tok-2", encoding="utf-8")
    launcher.clean(tmp_path / "home")
    assert source.read_text(encoding="utf-8") == "tok"  # no write-back for a copied login (CRED-COPY-A)
    assert not (tmp_path / "home" / "auth.json").exists()
