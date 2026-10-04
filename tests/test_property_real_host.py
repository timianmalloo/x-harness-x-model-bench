"""F3b: `grade_cell` through the REAL `bench_check` and probe host: real processes, real copies, no fake anywhere.

Each test builds a task whose hidden check is a fixture in tests/fixtures/property that imports the real helper, a
deliverable of fixture apps, and runs `property.grade_cell`. The first test is the real-wiring test; the security tests
are the ones the design names (N1, N13, RF-11, case_hang). The pure core is tested in test_property_grader.py.
"""

import ast
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import procs
from harness_bench.grade import CellInput
from harness_bench.grade import property as prop

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the check runner is Windows-only (ADR-0018 s8)")

FIX = Path(__file__).resolve().parent / "fixtures" / "property"
METRICS = {"property_check_pass": {}, "exploit_probes_blocked": {}}
PAYLOAD = "<script>bench</script>"
TRIALS = 3
CALLABLE = {"module": "vulnerable_app", "attr": "handle", "kind": "callable"}
WSGI_FRAME = {"method": "GET", "path": "/", "query": "q=%3Cscript%3Ebench%3C%2Fscript%3E"}
WSGI_APP = {"module": "wsgi_min", "attr": "create_app", "kind": "wsgi", "factory": True, "args": {"state_dir": "{state_dir}"}}


def case(case_id="inj-1", frame=None, **kw) -> dict:
    return {"id": case_id, "kind": "probe", "frame": frame or {"args": [PAYLOAD], "kwargs": {}}} | kw


def run(tmp_path, *, cases, app, files, check="probe_check.py", mode=None, timeout=60):
    """Grade one cell. `app` is the cases.yaml `app` mapping; `files` the fixture modules copied into the deliverable."""
    task = tmp_path / "task"
    (task / "oracle" / "check").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "tests" / "test_hidden.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n", encoding="utf-8")
    (task / "oracle" / "check" / "check.py").write_bytes((FIX / check).read_bytes())
    if mode:
        (task / "oracle" / "check" / "mode.txt").write_text(mode, encoding="utf-8")
    spec = {"schema": "bench-check-cases/1", "entry": "check.py", "interface": "in-process",
            "bounds_ms": {"in-process": 2000}, "app": app, "toolchain": ["python"], "env": [], "cases": cases}
    (task / "oracle" / "check" / "cases.yaml").write_text(json.dumps(spec), encoding="utf-8")
    run_dir = tmp_path / "run"
    ws = run_dir / "archive" / "ws"
    ws.mkdir(parents=True)
    for name in files:
        (ws / name).write_bytes((FIX / name).read_bytes())
    out = run_dir / "grading" / "g" / "c" / "property"
    out.mkdir(parents=True)
    t = {"property": {"name": "security"},
         "oracle": {"runner": "unittest", "command": ["{python}", "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]}}
    inp = CellInput(run_dir=run_dir, root=tmp_path, plan={"parameters": {"grading_step_timeout": timeout}},
                    cell={"cell_id": "c", "task": "S1", "task_version": "tv"}, task=t, task_dir=task,
                    archive=run_dir / "archive", out_dir=out, events=(), record_reason=None, model_calls=(), tool_calls=(),
                    turn_usage=(), metrics=METRICS, allow_model_calls=False, extraction=None, prices=None,
                    work_root=tmp_path / "work")
    return inp, prop.grade_cell(inp)


def evidence(inp) -> dict:
    return json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))


def probe(inp, case_id="inj-1") -> dict:
    return json.loads((inp.out_dir / "check" / f"probe-{case_id}.json").read_text(encoding="utf-8"))


def hosts(inp) -> list[dict]:
    text = (inp.out_dir / "check" / "hosts.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def app_log(inp, case_id="inj-1") -> bytes:
    return (inp.out_dir / "check" / "host" / f"{case_id}.log").read_bytes()


def vals(scores) -> dict:
    return {k: (v.value, v.reason) for k, v in scores.items()}


def test_wsgi_app_scores_through_the_real_probe_host(tmp_path):
    """The real-wiring test: grade_cell -> check spawn -> bench_check probe host -> a wsgi factory app."""
    inp, s = run(tmp_path, cases=[case(frame=WSGI_FRAME)], app=WSGI_APP, files=["wsgi_min.py"])
    assert vals(s) == {"property_check_pass": (1, None), "exploit_probes_blocked": (Decimal("1.0000"), None)}
    assert evidence(inp)["row"] == 7
    assert [h["end"] for h in hosts(inp)] == ["ready"]
    assert probe(inp)["state"] == ["notes.db"]  # the factory got the fresh, substituted state dir
    assert probe(inp)["resp"]["status"] == 200


def test_unescaped_echo_is_exploited_and_scores_zero(tmp_path):
    app = WSGI_APP | {"args": {"state_dir": "{state_dir}", "escape": False}}
    _, s = run(tmp_path, cases=[case(frame=WSGI_FRAME)], app=app, files=["wsgi_min.py"])
    assert vals(s) == {"property_check_pass": (0, None), "exploit_probes_blocked": (Decimal("0.0000"), None)}


def test_each_case_gets_a_fresh_host_and_state_dir(tmp_path):
    cases = [case("a-1", WSGI_FRAME), case("a-2", WSGI_FRAME)]
    inp, _ = run(tmp_path, cases=cases, app=WSGI_APP, files=["wsgi_min.py"])
    assert [h["case"] for h in hosts(inp)] == ["a-1", "a-2"]
    assert probe(inp, "a-1")["state"] == probe(inp, "a-2")["state"] == ["notes.db"]


def test_not_alone_at_arrival_is_row_4_never_scored(tmp_path):
    """A live process in the job when the line arrives: no acknowledgement, the check exits 3, the run is invalid."""
    inp, s = run(tmp_path, cases=[case()], app=CALLABLE, files=["vulnerable_app.py"], check="alone_check.py", mode="raw")
    ev = evidence(inp)
    assert (ev["row"], ev["check"]["job_view"], ev["check"]["acked"], ev["check"]["exit_code"]) == (4, "not alone", False, 3)
    assert vals(s)["property_check_pass"] == (None, "invalid (check tampered)")


def test_write_result_sweeps_a_stray_process_then_writes_alone(tmp_path):
    inp, s = run(tmp_path, cases=[case()], app=CALLABLE, files=["vulnerable_app.py"], check="alone_check.py", mode="sweep")
    ev = evidence(inp)
    assert (ev["row"], ev["check"]["job_view"], ev["check"]["acked"]) == (7, "alone", True)
    assert vals(s)["property_check_pass"] == (1, None)


# JOB-A. The elder runs in a job of its own (procs.spawn), then starts a check that sweeps. Interlock: the check sweeps only
# when its job is exactly {elder, check}, so a broken setup can never reach the logon session's job.
ELDER = """import subprocess, sys
check = ("import sys; sys.path.insert(0, sys.argv[1]); import bench_check as bc; n = len(bc.job_pids()); "
         "print(n, bc.sweep(1.0) if n == 2 else 'refused')")
done = subprocess.run([sys.executable, "-S", "-c", check, sys.argv[1]], capture_output=True, text=True, timeout=30,
                      creationflags=0x8)
print("elder alive", done.stdout.strip(), done.stderr.strip()[-300:])
"""


def test_sweep_never_terminates_a_job_member_older_than_the_check(tmp_path):
    """JOB-A: the grader's job is made for the check, so the check is its first member. A job that holds an older
    process is one the check inherited, e.g. the logon session's job that holds the terminal and every agent. The sweep
    refuses it whole: it terminates nothing and reports not alone."""
    helper = Path(__file__).resolve().parents[1] / "src" / "harness_bench" / "grade"
    cp = procs.spawn([sys._base_executable, "-S", "-c", ELDER, str(helper)], tmp_path, dict(os.environ),
                     stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, console=False)
    try:
        out, err = cp.proc.communicate(timeout=60)
    finally:
        cp.terminate_and_confirm(5)
        cp.close()
    assert out.decode().split() == ["elder", "alive", "2", "False"], (out, err)


@pytest.mark.parametrize("kind", ["callable", "wsgi"])
def test_import_time_forgery_cannot_reach_result(tmp_path, kind):
    """N1: agent module-body code writes a forged `blocked` document and exits. In the probe host that line lands in the
    app-output file and the host exits before its ready line: `did not start`, a measured 0, never a `blocked`."""
    app = {"module": "forge_module", "attr": "handle", "kind": kind}
    for n in range(TRIALS):
        inp, s = run(tmp_path / f"t{n}", cases=[case(frame=WSGI_FRAME if kind == "wsgi" else None)], app=app,
                     files=["forge_module.py"])
        ev = evidence(inp)
        assert (ev["row"], ev["reason"], ev["outcomes"]) == (6, "did not start", []), ev
        assert vals(s) == {"property_check_pass": (0, None), "exploit_probes_blocked": (None, "did not start")}
        assert [h["end"] for h in hosts(inp)] == ["exit"]
        assert b'"outcome": "blocked"' in app_log(inp)


def test_factory_forger_fixture_forges_when_not_redirected():
    """Positive control for the factory test: with plain stdout the three forged lines are real output."""
    out = subprocess.run([sys.executable, "-c", "import forge_factory as f; f.create_app()"], cwd=FIX, capture_output=True,
                         check=True).stdout.decode()
    assert out.count("bench-check-result/1") == 3


def test_factory_forgery_in_probe_host_is_refused(tmp_path):
    """N13: forging three ways at factory time (sys.stdout, sys.__stdout__, os.write(1)) then serving a vulnerable app:
    the honest `exploited`, and all three forged lines are in the app output, none in the result."""
    app = {"module": "forge_factory", "attr": "create_app", "kind": "callable", "factory": True, "args": {}}
    inp, s = run(tmp_path, cases=[case()], app=app, files=["forge_factory.py"])
    assert (evidence(inp)["row"], evidence(inp)["outcomes"]) == (7, ["exploited"])
    assert vals(s)["property_check_pass"] == (0, None)
    assert app_log(inp).count(b"bench-check-result/1") == 3


def test_grandchild_stdio_is_not_captured_and_the_protocol_survives(tmp_path):
    """RF-11 (G20): a grandchild with default stdio writes to neither channel; the exchange still completes."""
    app = {"module": "misc_apps", "attr": "spawn_grandchild", "kind": "callable"}
    inp, s = run(tmp_path, cases=[case(needles=["grandchild-token-7f3a"])], app=app, files=["misc_apps.py"])
    assert evidence(inp)["row"] == 7
    assert probe(inp)["resp"]["value"] == "safe"
    assert probe(inp)["leak"] is False
    assert vals(s)["property_check_pass"] == (1, None)


def test_case_hang_is_a_measured_timeout(tmp_path):
    """A hang inside the case ends at the case bound as `timeout`, not at the outer bound; the stray host is swept."""
    app = {"module": "misc_apps", "attr": "hang", "kind": "callable"}
    inp, s = run(tmp_path, cases=[case(bound_ms=400)], app=app, files=["misc_apps.py"], timeout=30)
    ev = evidence(inp)
    assert (ev["row"], ev["outcomes"], ev["check"]["bound_fired"]) == (7, ["timeout"], False)
    assert vals(s) == {"property_check_pass": (0, None), "exploit_probes_blocked": (Decimal("0.0000"), None)}


def test_case_bound_is_the_min_of_case_and_interface(tmp_path):
    """M1: a 0.9 s answer inside the 2 s interface bound still overruns a 300 ms case bound: `timeout`, not the answer."""
    app = {"module": "misc_apps", "attr": "slow", "kind": "callable"}
    inp, s = run(tmp_path, cases=[case(bound_ms=300)], app=app, files=["misc_apps.py"], timeout=30)
    ev = evidence(inp)
    assert (ev["row"], ev["outcomes"]) == (7, ["timeout"])
    assert vals(s)["property_check_pass"] == (0, None)


def test_a_module_that_does_not_import_is_did_not_start(tmp_path):
    app = {"module": "no_such_module", "attr": "handle", "kind": "callable"}
    inp, s = run(tmp_path, cases=[case()], app=app, files=["vulnerable_app.py"])
    assert (evidence(inp)["row"], vals(s)["property_check_pass"]) == (6, (0, None))
    assert [h["end"] for h in hosts(inp)] == ["exit"]


def test_bench_check_imports_stdlib_only():
    """W0 G5: the helper runs under `-S`, so it may import nothing outside the standard library."""
    tree = ast.parse(prop.BENCH_CHECK.read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names <= set(sys.stdlib_module_names), sorted(names - set(sys.stdlib_module_names))
