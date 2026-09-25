"""The verdict store (design phase3-gateway-judges sections 4.3 and 9; T-GW-11, 12b, 13, 31).

Offline: every store and ledger lives under tmp_path. Model ids, run ids and session ids are fixed placeholders.
"""

import hashlib
import json

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

