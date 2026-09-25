"""The verdict store (design phase3-gateway-judges sections 4.3 and 9; T-GW-11, 12b, 13, 31).

Offline: every store and ledger lives under tmp_path. Model ids, run ids and session ids are fixed placeholders.
"""

import hashlib
import json
import os

import pytest

from harness_bench.gateway import store

SESSION = "00000000-0000-4000-8000-000000000001"


def _inputs(**over: str) -> dict:
    return {"request_sha256": "a" * 64, "schema_sha256": "b" * 64, "model": "judge-model-a",
            "invocation_sha256": "c" * 64} | over


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
