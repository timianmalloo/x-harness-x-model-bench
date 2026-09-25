"""One judge lookup through the offline pipeline (design phase3-gateway-judges sections 6-9; T-GW-04, T-GW-30).

Offline: the backend is `ReplayBackend` (recorded stdout, no process, no socket); the store and ledgers live under
tmp_path. Operator identifiers and canaries are random synthetic strings made here at run time (R-42).
"""

import hashlib
import json
from secrets import token_hex

from harness_bench import egress
from harness_bench.gateway import backend as gw_backend
from harness_bench.gateway import pipeline, request, scrub

SESSION = "00000000-0000-4000-8000-000000000001"
JUDGE = pipeline.Judge(model="judge-model-a", invocation_sha256="c" * 64, allowed_models=("judge-model-a",))
ENTRIES = (*scrub.FAMILY_WORDS, "harness-placeholder", "combo-placeholder")
INPUTS = pipeline.Inputs(preamble="No mechanical oracle applies.", rubric="1. Names the structure.\n2. States costs.\n",
                         items=2, artifacts=(("docs/architecture.md", b"# Queue\nA heap, drafted with Claude.\n"),))
GOOD = {"items": [{"item": 1, "score": 2, "rationale": "named"}, {"item": 2, "score": 1, "rationale": "partial"}]}


def _operator() -> egress.Operator:
    return egress.Operator(email=f"op-{token_hex(6)}@example.invalid", username=f"u{token_hex(5)}",
                           home=f"C:\\Users\\u{token_hex(5)}")


def _ctx(tmp_path, **over) -> pipeline.Context:
    fields = {"store": tmp_path / "cache" / "verdicts", "known_roots": (tmp_path / "runs",), "own_run": None,
              "stored_by": {"ledger": "run", "ledger_id": "run-placeholder-1",
                            "grading_or_calibration_id": "grade-placeholder-1"},
              "denylist": ENTRIES, "allow_model_calls": True, "operator": _operator()}
    return pipeline.Context(**(fields | over))


def _stdout(answer: object, models: tuple[str, ...] = ("judge-model-a",)) -> str:
    return json.dumps({"type": "result", "result": json.dumps(answer), "session_id": SESSION,
                       "modelUsage": {m: {} for m in models}})


def _replay(inputs: pipeline.Inputs, answer: object = GOOD) -> gw_backend.ReplayBackend:
    rendered = request.render(inputs.preamble, inputs.rubric, inputs.items, inputs.artifacts, ENTRIES)
    digest = hashlib.sha256(rendered.text.encode("utf-8")).hexdigest()
    return gw_backend.ReplayBackend({digest: _stdout(answer)})


def test_t_gw_04_the_scan_is_independent_of_the_scrub(tmp_path, monkeypatch):
    replay = _replay(INPUTS)
    monkeypatch.setattr(scrub, "scrub", lambda text, entries: text)  # a scrub that leaves "Claude" in
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), replay)
    assert (result.outcome, result.code, result.verdicts) == ("failed", "HB-GW-004", None)
    assert replay.received == []  # 0 spawns: nothing reached the backend


class RacingBackend:
    """A second pass stores the same key while this call is in flight (design section 9.2)."""

    def __init__(self, inner: gw_backend.ReplayBackend, store_root, winner: dict) -> None:
        self.inner, self.store_root, self.winner = inner, store_root, winner
        self.received = inner.received

    def judge(self, request_text: str) -> gw_backend.Reply:
        k = pipeline.store.key(self.winner["key_inputs"])
        self.store_root.mkdir(parents=True, exist_ok=True)
        (self.store_root / f"{k}.json").write_text(json.dumps(self.winner), encoding="utf-8")
        return self.inner.judge(request_text)


def _path(name: str, tmp_path, monkeypatch) -> tuple[pipeline.Result, list[str]]:
    """Drive one named path of sections 6-9; return its result and what reached the backend."""
    ctx, inputs, replay = _ctx(tmp_path), INPUTS, _replay(INPUTS)
    if name == "stored":
        pass
    elif name == "hit":
        pipeline.run(JUDGE, inputs, ctx, replay)
        store_dir = ctx.store
        k = next(store_dir.glob("*.json")).stem
        sha = hashlib.sha256((store_dir / f"{k}.json").read_bytes()).hexdigest()
        _storing_ledger(tmp_path / "runs" / "run-placeholder-1", k, sha)
        replay.received.clear()
    elif name == "over the bound":
        inputs = pipeline.Inputs(INPUTS.preamble, INPUTS.rubric, 2, (("docs/architecture.md", b"a" * 65_537),))
    elif name == "not UTF-8":
        inputs = pipeline.Inputs(INPUTS.preamble, INPUTS.rubric, 2, (("docs/architecture.md", b"\xff\xfe"),))
    elif name == "scan hit in operator text":
        inputs = pipeline.Inputs(INPUTS.preamble, "1. Written for Claude.\n", 1, INPUTS.artifacts)
    elif name == "miss without --allow-model-calls":
        ctx = _ctx(tmp_path, allow_model_calls=False)
    elif name == "withheld by egress":
        canary = f"CANARY-{token_hex(8)}"
        inputs = pipeline.Inputs(INPUTS.preamble, INPUTS.rubric, 2, (("docs/architecture.md", canary.encode()),))
        replay, ctx = _replay(inputs), _ctx(tmp_path, canaries=(canary,))
    elif name == "backend down":
        replay = gw_backend.ReplayBackend({}, down=True)
    elif name == "answer fails the schema":
        replay = _replay(INPUTS, {"items": [{"item": 1, "score": 3, "rationale": "r"}]})
    elif name == "stdout not readable":
        rendered = request.render(INPUTS.preamble, INPUTS.rubric, 2, INPUTS.artifacts, ENTRIES)
        replay = gw_backend.ReplayBackend({hashlib.sha256(rendered.text.encode()).hexdigest(): "not json"})
    elif name == "served another model":
        rendered = request.render(INPUTS.preamble, INPUTS.rubric, 2, INPUTS.artifacts, ENTRIES)
        replay = gw_backend.ReplayBackend({hashlib.sha256(rendered.text.encode()).hexdigest():
                                           _stdout(GOOD, ("judge-model-q",))})
    elif name == "store write error":
        def refuse(src, dst):
            raise PermissionError("synthetic")
        monkeypatch.setattr(pipeline.store.os, "link", refuse)
    elif name == "planted entry":
        pipeline.run(JUDGE, inputs, ctx, replay)  # stored; its named ledger exists and verifies, with no row for it
        _storing_ledger(tmp_path / "runs" / "run-placeholder-1", "0" * 64, "0" * 64)
        replay.received.clear()
    elif name == "race lost":
        rendered = request.render(INPUTS.preamble, INPUTS.rubric, 2, INPUTS.artifacts, ENTRIES)
        inputs_key = {"request_sha256": hashlib.sha256(rendered.text.encode()).hexdigest(),
                      "schema_sha256": pipeline.schema.schema_sha256(), "model": "judge-model-a",
                      "invocation_sha256": "c" * 64}
        winner = {"format": "verdict-set/1", "key_inputs": inputs_key, "served_models": ["judge-model-a"],
                  "verdicts": GOOD["items"], "native_session_id": SESSION}
        replay = RacingBackend(replay, ctx.store, winner)
    result = pipeline.run(JUDGE, inputs, ctx, replay)
    return result, list(replay.received)


def _storing_ledger(run_dir, k: str, sha: str) -> None:
    from harness_bench import ledger
    rows = {"verdict_uses": {"kind": "verdict_use", "outcome": "stored", "cache_key": k, "entry_sha256": sha},
            "model_calls": {"kind": "model_call", "principal": "gateway", "native_session_id": SESSION}}
    for fact, row in rows.items():
        with ledger.SegmentWriter.create(run_dir / fact, "grade-placeholder-1") as w:
            w.append(row)
            w.seal()
    folder = run_dir / "grading" / "grade-placeholder-1" / "gateway" / k[:16]
    folder.mkdir(parents=True)
    (folder / "record.jsonl").write_text("{}\n", encoding="utf-8")


# Every path of sections 6-9 that slice 1 can reach, and the one (outcome, code) it maps to (design section 4.1).
PATHS = {
    "stored": ("stored", None),
    "hit": ("hit", None),
    "race lost": ("race_lost", None),
    "miss without --allow-model-calls": ("not_allowed", None),
    "over the bound": ("failed", "HB-GW-008"),
    "not UTF-8": ("failed", "HB-GW-008"),
    "scan hit in operator text": ("failed", "HB-GW-004"),
    "withheld by egress": ("failed", "HB-GW-009"),
    "backend down": ("failed", "HB-GW-001"),
    "answer fails the schema": ("failed", "HB-GW-002"),
    "stdout not readable": ("failed", "HB-GW-002"),
    "served another model": ("failed", "HB-GW-003"),
    "store write error": ("failed", "HB-GW-001"),
    "planted entry": ("failed", "HB-GW-005"),
}
SENT = {"stored", "race lost", "backend down", "answer fails the schema", "stdout not readable", "served another model",
        "store write error"}


def test_t_gw_30_every_path_maps_to_exactly_one_outcome_and_code(tmp_path, monkeypatch):
    seen = {}
    for n, name in enumerate(PATHS):
        with monkeypatch.context() as m:
            result, received = _path(name, tmp_path / str(n), m)
        seen[name] = (result.outcome, result.code)
        assert (len(received) == 1) == (name in SENT), name  # nothing is sent on a path that stops before release
        recorded = result.outcome in ("hit", "stored", "race_lost")
        assert (result.verdicts is not None) == recorded, name  # NOT_RECORDED carries no verdict, never a 0
        assert (result.cache_key is not None, result.entry_sha256 is not None) == (recorded, recorded), name
    assert seen == PATHS
    assert {code for _, code in PATHS.values() if code} <= set(pipeline.CODES)
    assert set(pipeline.CODES) == {f"HB-GW-{n:03d}" for n in range(1, 12)}


def test_t_gw_30_a_recorded_result_carries_the_validated_verdicts(tmp_path):
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), _replay(INPUTS))
    assert result.verdicts == tuple(GOOD["items"])
    entry = json.loads((tmp_path / "cache" / "verdicts" / f"{result.cache_key}.json").read_text(encoding="utf-8"))
    assert entry["key_inputs"]["model"] == "judge-model-a"
    assert entry["stored_by"] == {"ledger": "run", "ledger_id": "run-placeholder-1",
                                  "grading_or_calibration_id": "grade-placeholder-1"}
    assert entry["components"]["scrub_version"] == scrub.SCRUB_VERSION
    assert hashlib.sha256((tmp_path / "cache" / "verdicts" / f"{result.cache_key}.json").read_bytes()).hexdigest() \
        == result.entry_sha256
