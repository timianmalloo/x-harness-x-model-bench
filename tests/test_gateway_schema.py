"""Answer validation against the one schema file (design phase3-gateway-judges section 8.3 step 4; T-GW-05)."""

import hashlib
import json

import pytest

from harness_bench.gateway import schema


def _answer(*items: tuple[int, object]) -> dict:
    return {"items": [{"item": i, "score": s, "rationale": "because"} for i, s in items]}


def test_t_gw_05_a_valid_answer_passes_and_the_schema_hash_is_the_files():
    assert schema.validate(_answer((1, 2), (2, 0)), 2) == []
    assert schema.schema_sha256() == hashlib.sha256(schema.SCHEMA_PATH.read_bytes()).hexdigest()


@pytest.mark.parametrize(("answer", "problems"), [
    (_answer((1, 2)), ["$.items: items [2] missing"]),
    ({"items": [{"item": 1, "score": 2, "rationale": "r", "extra": 1}, {"item": 2, "score": 0, "rationale": "r"}]},
     ["$.items[0]: unexpected key 'extra'"]),
    (_answer((1, 3), (2, 0)), ["$.items[0].score: 3 not in [0, 1, 2]"]),
    (_answer((1, True), (2, 0)), ["$.items[0].score: not an integer"]),
    (_answer((1, 2), (1, 1), (2, 0)), ["$.items: item 1 repeated"]),
    ({"items": [{"item": 1, "score": 2, "rationale": "r" * 2001}, {"item": 2, "score": 0, "rationale": "r"}]},
     ["$.items[0].rationale: longer than 2000"]),
    (_answer((1, 2), (2, 0), (3, 1)), ["$.items: item 3 not in 1..2"]),
    ({"items": [{"item": 1, "score": 2}, {"item": 2, "score": 0, "rationale": "r"}]}, ["$.items[0]: 'rationale' missing"]),
    ([], ["$: not an object"]),
    ({"items": []}, ["$.items: fewer than 1 items", "$.items: items [1, 2] missing"]),
])
def test_t_gw_05_each_malformed_answer_is_named(answer, problems):
    assert schema.validate(answer, 2) == problems


def test_t_gw_05_the_validator_reads_the_schema_file(tmp_path, monkeypatch):
    copy = json.loads(schema.SCHEMA_PATH.read_text(encoding="utf-8"))
    copy["properties"]["items"]["items"]["properties"]["rationale"]["maxLength"] = 5
    (tmp_path / "s.json").write_text(json.dumps(copy), encoding="utf-8")
    monkeypatch.setattr(schema, "SCHEMA_PATH", tmp_path / "s.json")
    assert schema.validate(_answer((1, 2)), 1) == ["$.items[0].rationale: longer than 5"]
