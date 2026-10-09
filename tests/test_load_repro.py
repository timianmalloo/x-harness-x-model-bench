"""tools/load_repro.py: a counted loop that records a node's failure rate and the stage of each failure (FLAKE-A)."""

import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location("load_repro", Path(__file__).resolve().parents[1] / "tools" / "load_repro.py")
load_repro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_repro)

PLAIN = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]  # the loop is under test, not xdist

FIXTURE = '''
import pytest

COUNTER = {counter!r}


def _bump():
    with open(COUNTER, "a", encoding="utf-8") as fh:
        fh.write("x")
    with open(COUNTER, encoding="utf-8") as fh:
        return len(fh.read())


@pytest.fixture
def seeded():
    n = _bump()
    if n == 4:
        raise RuntimeError("seeded setup failure")
    yield n
    if n == 5:
        raise RuntimeError("seeded teardown failure")


def test_flaky(seeded):
    assert seeded != 2, "seeded call failure"
'''


def test_the_seeded_flaky_node_is_measured_with_each_failures_stage(tmp_path):
    """Runs 2, 4 and 5 of 6 fail, at call, setup and teardown; the record says so and the rate is 3/6."""
    (tmp_path / "test_seeded.py").write_text(FIXTURE.format(counter=str(tmp_path / "counter.txt")), encoding="utf-8")
    out = tmp_path / "record.json"
    load_repro.run_repro("test_seeded.py::test_flaky", 6, out, prefix=PLAIN, cwd=tmp_path)
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["node"] == "test_seeded.py::test_flaky" and rec["n"] == 6
    assert rec["failures"] == 3 and rec["rate"] == 0.5
    assert [(f["run"], f["stage"]) for f in rec["failure_list"]] == [(2, "call"), (4, "setup"), (5, "teardown")]
    assert "seeded call failure" in rec["failure_list"][0]["first_error"]
    assert len(rec["wall_s"]) == 6 and rec["base_sha"]


def test_a_run_with_no_result_for_the_node_is_a_failure_never_a_pass(tmp_path):
    (tmp_path / "test_seeded.py").write_text("def test_other():\n    pass\n", encoding="utf-8")
    out = tmp_path / "record.json"
    load_repro.run_repro("test_seeded.py::test_missing", 2, out, prefix=PLAIN, cwd=tmp_path)
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["failures"] == 2 and rec["rate"] == 1.0
    assert {f["stage"] for f in rec["failure_list"]} == {"no result"}
