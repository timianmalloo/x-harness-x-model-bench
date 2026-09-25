"""The verdict store (design phase3-gateway-judges sections 4.3 and 9; T-GW-11, 12b, 13, 31).

Offline: every store and ledger lives under tmp_path. Model ids, run ids and session ids are fixed placeholders.
"""

import hashlib
import json
import os
import stat

import pytest

from harness_bench import ledger
from harness_bench.gateway import store

SESSION = "00000000-0000-4000-8000-000000000001"


def _inputs(**over: str) -> dict:
    return {"request_sha256": "a" * 64, "schema_sha256": "b" * 64, "model": "judge-model-a",
            "invocation_sha256": "c" * 64} | over


def _key(inputs: dict) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _entry(inputs: dict, run_id: str = "run-placeholder-1", gid: str = "grade-placeholder-1") -> dict:
    return {"format": "verdict-set/1", "key_inputs": inputs,
            "components": {"artifact_sha256": "d" * 64, "rubric_sha256": "e" * 64, "template_version": "judge-request/1",
                           "scrub_version": "scrub/1", "schema_sha256": inputs["schema_sha256"]},
            "served_models": ["judge-model-a"],
            "stored_by": {"ledger": "run", "ledger_id": run_id, "grading_or_calibration_id": gid},
            "native_session_id": SESSION, "created_utc": "2026-09-25T00:00:00Z",
            "verdicts": [{"item": 1, "score": 2, "rationale": "r"}]}


def test_t_gw_31_the_key_recomputes_from_key_inputs_and_names_the_file(tmp_path):
    inputs = _inputs()
    expected = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert store.key(inputs) == expected
    written = store.write_once(tmp_path, expected, _entry(inputs))
    assert written.state == "stored"
    entry = json.loads((tmp_path / f"{expected}.json").read_text(encoding="utf-8"))
    assert store.key(entry["key_inputs"]) == expected
    assert sorted(entry["key_inputs"]) == sorted(store.KEY_FIELDS)


@pytest.mark.parametrize("field", ["request_sha256", "schema_sha256", "model", "invocation_sha256"])
def test_t_gw_12b_each_key_input_changes_the_key_and_misses(tmp_path, field):
    base = _inputs()
    store.write_once(tmp_path, store.key(base), _entry(base))
    changed = _inputs(**{field: "judge-model-b" if field == "model" else "f" * 64})
    assert store.key(changed) != store.key(base)
    assert store.lookup(tmp_path, store.key(changed), (), ("judge-model-a", "judge-model-b"), None).state == "miss"


def test_t_gw_12b_the_key_takes_exactly_the_four_inputs():
    with pytest.raises(ValueError, match="exactly"):
        store.key({k: v for k, v in _inputs().items() if k != "model"})
    with pytest.raises(ValueError, match="exactly"):
        store.key(_inputs() | {"timeout": "180"})


def test_t_gw_11_the_first_writer_wins_and_the_loser_reads_its_entry(tmp_path):
    inputs = _inputs()
    k = store.key(inputs)
    first, second = _entry(inputs), _entry(inputs) | {"native_session_id": "00000000-0000-4000-8000-000000000002"}
    assert store.write_once(tmp_path, k, first, ("judge-model-a",)).state == "stored"
    winner_bytes = (tmp_path / f"{k}.json").read_bytes()
    lost = store.write_once(tmp_path, k, second, ("judge-model-a",))
    assert (lost.state, lost.code, lost.entry) == ("race_lost", None, first)
    assert lost.entry_sha256 == hashlib.sha256(winner_bytes).hexdigest()
    assert (tmp_path / f"{k}.json").read_bytes() == winner_bytes
    assert not os.access(tmp_path / f"{k}.json", os.W_OK)  # read-only once written
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{k}.json"]  # no tmp left behind


def test_t_gw_11_a_loser_whose_winner_does_not_recompute_is_refused(tmp_path):
    inputs = _inputs()
    k = store.key(inputs)
    (tmp_path / f"{k}.json").write_text(json.dumps(_entry(_inputs(model="judge-model-z"))), encoding="utf-8")
    lost = store.write_once(tmp_path, k, _entry(inputs), ("judge-model-a",))
    assert (lost.state, lost.code, lost.entry) == ("failed", "HB-GW-005", None)


def test_t_gw_11_a_write_error_other_than_a_lost_race_is_hb_gw_001(tmp_path, monkeypatch):
    def refuse(src, dst):
        raise PermissionError("synthetic: antivirus holds the file")
    monkeypatch.setattr(store.os, "link", refuse)
    inputs = _inputs()
    failed = store.write_once(tmp_path, store.key(inputs), _entry(inputs), ("judge-model-a",))
    assert (failed.state, failed.code, failed.entry) == ("failed", "HB-GW-001", None)
    assert list(tmp_path.iterdir()) == []


def test_t_gw_11_a_tmp_older_than_24_hours_is_swept(tmp_path):
    old, new = tmp_path / ".k1.aaaa.tmp", tmp_path / ".k2.bbbb.tmp"
    old.write_bytes(b"torn")
    new.write_bytes(b"in flight")
    os.utime(old, (1_000_000.0, 1_000_000.0))
    os.utime(new, (1_000_000.0 + 23 * 3600, 1_000_000.0 + 23 * 3600))
    assert store.sweep_tmp(tmp_path, 1_000_000.0 + 24 * 3600 + 1) == [".k1.aaaa.tmp"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [".k2.bbbb.tmp"]


RUN, GID = "run-placeholder-1", "grade-placeholder-1"
ALLOWED = ("judge-model-a",)


def _ledger(run_dir, k: str, sha: str, *, outcome: str = "stored", principal: str = "gateway", seal: bool = True,
            record: bool = True, fact: str = "verdict_uses") -> None:
    """A storing pass: its verdict-use row, its gateway model_calls row and its archived judge record."""
    rows = {fact: {"kind": "verdict_use", "run_id": RUN, "grading_id": GID, "cell_id": "cellplaceholder01",
                   "item_id": "adr_quality#1", "judge_or_matcher": "judge-model-a", "outcome": outcome, "code": None,
                   "cache_key": k, "entry_sha256": sha},
            "model_calls": {"kind": "model_call", "run_id": RUN, "extraction_id": GID, "principal": principal,
                            "cell_id": None, "native_session_id": SESSION, "native_ordinal": 1, "model": "judge-model-a"}}
    for name, row in rows.items():
        with ledger.SegmentWriter.create(run_dir / name, GID) as w:
            w.append(row)
            if seal:
                w.seal()
    if record:
        folder = run_dir / "grading" / GID / "gateway" / k[:16]
        folder.mkdir(parents=True)
        (folder / "record.jsonl").write_text('{"type":"placeholder"}\n', encoding="utf-8")


def _stored(tmp_path, **ledger_args):
    """A store entry and its storing run under one known runs/ root: (store root, runs root, key, entry, sha)."""
    root, runs = tmp_path / "cache" / "verdicts", tmp_path / "wt1" / "runs"
    inputs = _inputs()
    k, entry = _key(inputs), _entry(inputs)
    data = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()  # written here, not by the store
    root.mkdir(parents=True)
    (root / f"{k}.json").write_bytes(data)
    os.chmod(root / f"{k}.json", stat.S_IREAD)
    sha = hashlib.sha256(data).hexdigest()
    _ledger(runs / RUN, k, sha, **ledger_args)
    return root, runs, k, entry, sha


def _rewrite(path, change) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_t_gw_13_a_hit_is_accepted_only_with_its_sealed_storing_row(tmp_path):
    root, runs, k, entry, sha = _stored(tmp_path)
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("hit", None, entry, sha)
    assert store.lookup(root, "0" * 64, (runs,), ALLOWED, None) == store.Found("miss")


@pytest.mark.parametrize(("name", "ledger_args"), [
    ("no storing row with this entry's hash", {"outcome": "hit"}),
    ("no gateway model_calls row", {"principal": "cellplaceholder01"}),
    ("storing segments not sealed", {"seal": False}),
    ("no archived judge record", {"record": False}),
])
def test_t_gw_13_a_planted_entry_without_matching_provenance_is_hb_gw_005(tmp_path, name, ledger_args):
    root, runs, k, _, sha = _stored(tmp_path, **ledger_args)
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("failed", "HB-GW-005")
    assert hashlib.sha256((root / f"{k}.json").read_bytes()).hexdigest() == sha  # kept for inspection


def test_t_gw_13_an_edited_entry_is_refused_and_verify_warns(tmp_path):
    root, runs, k, _, sha = _stored(tmp_path)
    _rewrite(root / f"{k}.json", lambda e: e["verdicts"][0].update(score=0))
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("failed", "HB-GW-005")
    refs = [{"cache_key": k, "entry_sha256": sha}, {"cache_key": "1" * 64, "entry_sha256": sha}]
    assert store.verify_entries(root, refs) == [f"{k}: changed since stored", f"{'1' * 64}: missing"]


@pytest.mark.parametrize(("name", "change"), [
    ("key inputs do not recompute the name", lambda e: e["key_inputs"].update(model="judge-model-b")),
    ("served model not allowed", lambda e: e.update(served_models=["judge-model-q"])),
    ("stored_by outside the known roots", lambda e: e["stored_by"].update(ledger_id="../wt1/runs/" + RUN)),
    ("not a verdict set", lambda e: e.update(format="verdict-set/0")),
])
def test_t_gw_13_an_entry_that_fails_the_check_is_hb_gw_005(tmp_path, name, change):
    root, runs, k, _, _ = _stored(tmp_path)
    _rewrite(root / f"{k}.json", change)
    # re-point the storing row at the edited bytes, so only the named defect is left
    folder = runs / RUN
    for fact in ("verdict_uses", "model_calls"):
        (folder / fact / f"{GID}.jsonl").unlink()
    (folder / "grading").rename(tmp_path / "old-grading")
    _ledger(folder, k, hashlib.sha256((root / f"{k}.json").read_bytes()).hexdigest())
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("failed", "HB-GW-005")


def test_t_gw_13_a_forged_chain_is_hb_gw_005(tmp_path):
    root, runs, k, _, _ = _stored(tmp_path)
    seg = runs / RUN / "verdict_uses" / f"{GID}.jsonl"
    seg.write_bytes(seg.read_bytes().replace(b'"cellplaceholder01"', b'"cellplaceholder02"'))
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("failed", "HB-GW-005")


def test_t_gw_13_a_pruned_storing_ledger_orphans_the_entry_and_this_runs_own_row_accepts_it(tmp_path):
    root, runs, k, entry, sha = _stored(tmp_path)
    own = tmp_path / "wt2" / "runs" / "run-placeholder-2"
    own.parent.mkdir(parents=True)
    (runs / RUN).rename(own)  # the storing run is gone from every known root; this run holds an earlier row
    assert store.lookup(root, k, (runs,), ALLOWED, None) == store.Found("orphaned")
    assert store.lookup(root, k, (runs,), ALLOWED, tmp_path / "run-without-the-row") == store.Found("orphaned")
    assert store.lookup(root, k, (runs,), ALLOWED, own) == store.Found("hit", None, entry, sha)
    moved = store.move_orphan(root, k, "20260925T000000Z")
    assert moved == root / "orphaned" / f"{k}.20260925T000000Z.json"
    assert hashlib.sha256(moved.read_bytes()).hexdigest() == sha and not (root / f"{k}.json").exists()
