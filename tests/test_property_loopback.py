"""X-LB1: the loopback fake. `bench_check.listen()` (W0 R6-17, ADR-0018 s3, W1-L F15) and, in K2, the shape (b) path."""

import socket
import sys
import threading

import pytest

from harness_bench import errors
from harness_bench.grade import bench_check as bc

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the check runner is Windows-only (ADR-0018 s8)")


def test_hb_chk_005_is_a_run_code():
    assert "127.0.0.1" in errors.RUN_CODES["HB-CHK-005"]


def test_two_listeners_in_parallel_get_distinct_loopback_ports():
    """EV-3 parallel-port isolation (F15): port 0 per case, so two cases never collide."""
    with bc.listen() as a, bc.listen() as b:
        assert a.getsockname()[0] == b.getsockname()[0] == "127.0.0.1"
        assert a.getsockname()[1] != b.getsockname()[1]


def test_many_parallel_listeners_never_collide():
    ports, gate = [], threading.Barrier(8)

    def one():
        with bc.listen() as s:
            gate.wait(10)
            ports.append(s.getsockname()[1])
            gate.wait(10)

    threads = [threading.Thread(target=one) for _ in range(8)]
    [t.start() for t in threads]
    [t.join(20) for t in threads]
    assert len(ports) == 8 and len(set(ports)) == 8


def test_a_bind_to_any_other_address_is_refused_with_hb_chk_005_and_leaves_no_socket(monkeypatch):
    made = []
    real = socket.socket

    def spy(*a, **k):
        made.append(real(*a, **k))
        return made[-1]

    monkeypatch.setattr(bc, "_BIND", ("0.0.0.0", 0))
    monkeypatch.setattr(bc.socket, "socket", spy)
    with pytest.raises(bc.ListenerError, match="HB-CHK-005"), bc.listen():
        pass
    assert made and all(s.fileno() == -1 for s in made)


def test_the_listener_socket_is_closed_when_its_case_ends():
    with bc.listen() as s:
        port = s.getsockname()[1]
        assert s.fileno() != -1
    assert s.fileno() == -1
    with bc.listen() as again:  # the closed port is free to a fresh listener
        assert again.getsockname()[0] == "127.0.0.1"
    assert isinstance(port, int)


def test_the_listener_is_exclusive_on_its_port():
    with bc.listen() as s:
        # The option itself, not a second bind: on this host a second bind is refused even without it (option reads 0 by
        # default). win32-only, as the whole module is: SO_EXCLUSIVEADDRUSE exists only on Windows.
        assert s.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) == 1
        other = socket.socket()
        try:
            with pytest.raises(OSError):
                other.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                other.bind(s.getsockname())
        finally:
            other.close()


# ---- K2: the shape (b) path through the grader -------------------------------------------------------------------

import json
from decimal import Decimal
from pathlib import Path

from harness_bench.grade import CellInput
from harness_bench.grade import property as prop

FIX = Path(__file__).resolve().parent / "fixtures" / "property"
METRICS = {"property_check_pass": {}, "fault_suite_pass": {}, "idempotency_violations": {}}
CLIENT = {"module": "fault_client", "attr": "fetch", "kind": "callable"}


def fault(case_id="f-5xx", schedule=(503, 200), call="fetch", **kw) -> dict:
    return {"id": case_id, "kind": "fault", "schedule": list(schedule),
            "frame": {"args": ["{fake_url}/pay"], "kwargs": {}}} | ({"call": call} if call != "fetch" else {}) | kw


def run(tmp_path, cases, *, app=CLIENT, files=("fault_client.py",), bounds=4000, interface="loopback", extra=None):
    task = tmp_path / "task"
    (task / "oracle" / "check").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "tests" / "test_hidden.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n", encoding="utf-8")
    (task / "oracle" / "check" / "check.py").write_bytes((FIX / "fault_check.py").read_bytes())
    spec = {"schema": "bench-check-cases/1", "entry": "check.py", "interface": interface,
            "bounds_ms": {"in-process": 2000, "loopback": bounds}, "app": app, "toolchain": ["python"], "env": [],
            "cases": cases} | (extra or {})
    (task / "oracle" / "check" / "cases.yaml").write_text(json.dumps(spec), encoding="utf-8")
    run_dir = tmp_path / "run"
    ws = run_dir / "archive" / "ws"
    ws.mkdir(parents=True)
    for name in files:
        (ws / name).write_bytes((FIX / name).read_bytes())
    out = run_dir / "grading" / "g" / "c" / "property"
    out.mkdir(parents=True)
    t = {"property": {"name": "resilience"},
         "oracle": {"runner": "unittest", "command": ["{python}", "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]}}
    inp = CellInput(run_dir=run_dir, root=tmp_path, plan={"parameters": {"grading_step_timeout": 60}},
                    cell={"cell_id": "c", "task": "RS1", "task_version": "tv"}, task=t, task_dir=task,
                    archive=run_dir / "archive", out_dir=out, events=(), record_reason=None, model_calls=(), tool_calls=(),
                    turn_usage=(), metrics=METRICS, allow_model_calls=False, extraction=None, prices=None,
                    work_root=tmp_path / "work")
    return inp, prop.grade_cell(inp)


def result(inp) -> dict:
    return json.loads((inp.out_dir / "check" / "check.stdout").read_text(encoding="utf-8"))


def seen(inp, case_id) -> dict:
    return json.loads((inp.out_dir / "check" / f"fault-{case_id}.json").read_text(encoding="utf-8"))


def vals(scores) -> dict:
    return {k: (v.value, v.reason) for k, v in scores.items()}


def test_resilience_is_a_strategy_and_the_keys_match_property_names():
    from harness_bench import config
    assert list(prop.STRATEGIES) == list(config.PROPERTY_NAMES)


def test_a_503_then_200_fake_passes_end_to_end_with_the_measured_span_and_request_count(tmp_path):
    inp, s = run(tmp_path, [fault()])
    assert vals(s) == {"property_check_pass": (1, None), "fault_suite_pass": (Decimal("1.0000"), None),
                       "idempotency_violations": (0, None)}
    doc = result(inp)
    assert [c["outcome"] for c in doc["cases"]] == ["passed"]
    assert 300 <= doc["cases"][0]["duration_ms"] < 3000  # the client's retry pause is inside the span
    assert seen(inp, "f-5xx")["requests"] == 2  # one 503, one 200, never a re-run


def test_a_client_that_never_calls_the_fake_scores_failed_whatever_it_returns(tmp_path):
    """The pass rule reads the fake's counters, not only the deliverable's answer (a fixture X-RS copies)."""
    inp, s = run(tmp_path, [fault()], app=CLIENT | {"module": "lazy_client"}, files=("lazy_client.py",))
    assert (seen(inp, "f-5xx")["requests"], seen(inp, "f-5xx")["effects"]) == (0, 0)
    assert [c["outcome"] for c in result(inp)["cases"]] == ["failed"]
    assert vals(s)["property_check_pass"] == (0, None)


def test_fake_url_is_substituted_per_case_with_that_cases_own_port(tmp_path):
    inp, s = run(tmp_path, [fault("a-1"), fault("a-2")])
    assert vals(s)["fault_suite_pass"] == (Decimal("1.0000"), None)
    assert seen(inp, "a-1")["requests"] == seen(inp, "a-2")["requests"] == 2  # each fake saw only its own client


def test_duration_ms_excludes_host_start(tmp_path):
    inp, _ = run(tmp_path, [fault(schedule=(200,))], app=CLIENT | {"module": "slow_client"},
                 files=("fault_client.py", "slow_client.py"))
    start_ms = json.loads((inp.out_dir / "check" / "hosts.jsonl").read_text(encoding="utf-8").splitlines()[0])["start_ms"]
    dur = result(inp)["cases"][0]["duration_ms"]
    assert start_ms >= 1000 and dur < 700


def test_duration_ms_is_the_probe_host_call_alone_not_the_checks_other_work(tmp_path):
    inp, _ = run(tmp_path, [fault(schedule=(200,), settle_ms=900)])
    assert result(inp)["cases"][0]["duration_ms"] < 600


def test_a_hang_is_a_measured_timeout_never_a_rerun_and_the_effective_bound_is_the_lower(tmp_path):
    app = CLIENT | {"attr": "hang"}
    inp, s = run(tmp_path, [fault(schedule=(200,), bound_ms=60000)], app=app, bounds=700)  # loopback bound is the lower
    doc = result(inp)
    assert [c["outcome"] for c in doc["cases"]] == ["timeout"]
    assert doc["cases"][0]["duration_ms"] < 2500
    assert vals(s)["property_check_pass"] == (0, None) and vals(s)["fault_suite_pass"][0] == Decimal("0.0000")
    assert seen(inp, "f-5xx")["requests"] == 0


def test_a_case_bound_below_the_interface_bound_wins(tmp_path):
    inp, _ = run(tmp_path, [fault(schedule=(200,), bound_ms=600)], app=CLIENT | {"attr": "hang"}, bounds=60000)
    assert [c["outcome"] for c in result(inp)["cases"]] == ["timeout"]
    assert result(inp)["cases"][0]["duration_ms"] < 3000


def test_one_failed_case_fails_the_primary_and_scores_the_share(tmp_path):
    inp, s = run(tmp_path, [fault("ok-1"), fault("bad-1", schedule=(500,))])
    assert vals(s)["property_check_pass"] == (0, None)
    assert vals(s)["fault_suite_pass"] == (Decimal("0.5000"), None)
    assert [c["outcome"] for c in result(inp)["cases"]] == ["passed", "failed"]


def test_idempotency_violations_is_the_measure_the_check_reports(tmp_path):
    _, s = run(tmp_path, [fault("dup-1", schedule=(200,), call="twice")], app=CLIENT | {"attr": "twice"})
    assert vals(s)["idempotency_violations"] == (1, None)


@pytest.mark.parametrize("extra", [
    {"deliverable": {"start": "serve.py", "config": "c.json"}},  # shape (a): the deliverable listens, not built
])
def test_shape_a_and_a_probe_case_on_loopback_are_not_built(tmp_path, extra):
    _, s = run(tmp_path, [fault()], extra=extra)
    assert set(vals(s).values()) == {(None, "not built")}


def test_a_probe_case_on_loopback_is_not_built(tmp_path):
    _, s = run(tmp_path, [fault() | {"kind": "probe"}])
    assert set(vals(s).values()) == {(None, "not built")}


# --- K3 (a): readiness's exactly-one-shape rule (W0 s3, HB-RDY-005) ---------------------------------------------------------

_APP = {"kind": "callable", "module": "client.py", "factory": "make", "args": [], "paths": []}


def _readiness_items(spec):
    from harness_bench import readiness

    out = []
    readiness._case_failures({"entry": "check.py", "cases": [{"id": "c-1"}]} | spec, lambda item, detail, code="HB-RDY-005": out.append((item, detail, code)))
    return [(i, d, c) for i, d, c in out if i == "cases.yaml interface"]


def test_loopback_shape_b_alone_is_accepted():
    assert _readiness_items({"interface": "loopback", "app": _APP, "deliverable": {"build": ["x"]}}) == []


def test_loopback_with_both_shapes_is_refused_as_not_exactly_one():
    (_item, detail, code), = _readiness_items({"interface": "loopback", "app": _APP, "deliverable": {"start": ["s"], "config": "c.json"}})
    assert code == "HB-RDY-005" and "exactly one" in detail


def test_loopback_with_neither_shape_is_refused_as_not_exactly_one():
    (_item, detail, code), = _readiness_items({"interface": "loopback"})
    assert code == "HB-RDY-005" and "exactly one" in detail


def test_loopback_shape_a_stays_not_built():
    (_item, detail, code), = _readiness_items({"interface": "loopback", "deliverable": {"start": ["s"], "config": "c.json"}})
    assert code == "HB-RDY-005" and "not built" in detail


# --- K3 (b): the four property.json pointers and property_evidence reading them ---------------------------------------------

def test_property_json_names_the_four_evidence_pointers_relative_to_the_run_dir(tmp_path):
    inp, _ = run(tmp_path, [fault()])
    check = json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))["check"]
    base = (inp.out_dir / "check").relative_to(inp.run_dir).as_posix()
    assert {k: check[k] for k in ("deliverable", "cases", "hosts", "clauses")} == {
        "deliverable": f"{base}/check.stdout", "cases": f"{base}/check.stdout", "hosts": f"{base}/hosts.jsonl", "clauses": None}


def test_property_evidence_reads_what_the_pointers_name_and_fails_closed_on_an_absent_one(tmp_path):
    from harness_bench import readiness

    inp, _ = run(tmp_path, [fault()])
    pointer = (inp.out_dir / "property.json").relative_to(inp.run_dir).as_posix()
    got = readiness.property_evidence(inp.run_dir, pointer)
    assert got["cases"] == {"f-5xx": "passed"} and got["hosts_ready"] == 1 and got["clauses"] is None
    doc = json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))
    del doc["check"]["hosts"]
    (inp.out_dir / "property.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="check.hosts"):
        readiness.property_evidence(inp.run_dir, pointer)


# --- K4: an RS-shaped fixture through `bench discriminate` with the loopback check, no discriminate.py change ------------------

def test_an_rs_shaped_loopback_task_discriminates_and_gets_a_record():
    import importlib.util
    import shutil
    import uuid

    from clean_parent import CLEAN_PARENT

    from harness_bench import archive, discriminate

    spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
    mt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt)
    base = CLEAN_PARENT / uuid.uuid4().hex
    base.mkdir(parents=True)
    try:
        root = mt.make_root(base)
        mt.install(root, "disc_rs")
        result = discriminate.run(root, "DISC-RS", runs=base / "runs", cells_root=base / "cells")
        assert result.outcome == "written", result
        body = json.loads(result.record_path.read_text(encoding="utf-8"))
        assert body["scores"]["reference"]["property_check_pass"] == 1 and body["scores"]["naive"]["property_check_pass"] == 0
        assert body["probe"]["reference"]["cases"] == {"f-5xx": "passed"} and body["probe"]["naive"]["cases"] == {"f-5xx": "failed"}
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)
