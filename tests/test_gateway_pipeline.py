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
