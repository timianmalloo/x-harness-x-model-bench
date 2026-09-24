"""Phase-1 exit: the real walking skeleton (design: E2E). X1 x {cc-sonnet, codex-sol} x {on, off} x 1.

Runs the real `bench` CLI with the pinned builds, the operator's subscription logins and real model calls,
then asserts the design's exit list. Workstation only (marked native and credentials).
"""

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import pytest

from harness_bench import cli, host, plan, profiles, views

pytestmark = [pytest.mark.native, pytest.mark.credentials]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def kept(clean_parent):
    """A clean-ancestry folder the test removes as its own last step, so a failed run stays on disk as evidence.
    (A fixture teardown would run after a failure too, which is how two failed runs lost their evidence.)"""
    folder = clean_parent / f"e2e-{int(time.time())}"
    folder.mkdir(parents=True)
    return folder


def test_the_walking_skeleton_runs_end_to_end(kept):
    tools_dir = ROOT / ".tools" / "harness"  # installed by the e2e conftest
    runs, cells = kept / "runs", kept / "cells"
    rid = kept.name
    common = ["--root", str(ROOT), "--runs", str(runs), "--cells-root", str(cells), "--tools-dir", str(tools_dir)]
    timings = {}

    started = time.monotonic()
    assert cli.main([*common, "plan", "--matrix", str(ROOT / "bench" / "matrix.phase1.yaml"), "--run-id", rid, "--confirm"]) == 0
    timings["plan_s"] = time.monotonic() - started
    started = time.monotonic()
    assert cli.main([*common, "run", rid]) == 0  # runs every cell, then grades
    timings["run_s"] = time.monotonic() - started
    run_dir = runs / rid
    p = plan.load_confirmed(run_dir)
    view = views.load(run_dir)
    events = views.rows(run_dir, "events")

    # 4 cells terminal, each with an outcome
    assert len(view.cells) == 4 and all(c.outcome in ("completed", "timed_out", "failed") for c in view.cells), \
        [(c.label, c.outcome, c.cause) for c in view.cells]

    # US-10: the prompt the agent received is the plan's, byte for byte
    sessions = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
    for c in view.cells:
        prof = p["profiles"][c.harness]
        home = run_dir / "archive" / c.cell_id / "attempt-1" / "home"
        (record,) = profiles.find_records(home, prof["record_glob"], sessions[c.cell_id])
        received = profiles.READERS[c.harness](record).first_user_text or ""
        assert hashlib.sha256(received.encode("utf-8")).hexdigest() == p["tasks"]["X1"]["prompt_sha256"], c.label

    # US-11: a served model with at least one call, and no model mismatch
    assert all(c.validity == "valid" for c in view.cells), [(c.label, c.validity, c.validity_code) for c in view.cells]

    # US-12: the executed build is the planned build
    for e in events:
        if e["kind"] == "attempt.process_started":
            assert e["build_sha256"] == p["builds"][e["harness"]]["sha256"]

    # US-14: zero permission requests
    outcomes = [e for e in events if e["kind"] == "cell.outcome"]
    assert [o["permission_requests"] for o in outcomes] == [0, 0, 0, 0]

    # bench verify passes (ledger chains and seals, archive hashes and bytes: US-19)
    assert cli.main([*common, "verify", rid]) == 0

    # the re-grade gives byte-identical canonical exports (US-26)
    first = views.export(view)
    assert cli.main([*common, "grade", rid]) == 0
    assert views.export(views.load(run_dir)) == first

    # the CLI table and report.html render offline
    assert cli.main([*common, "report", rid]) == 0
    page = (run_dir / "report.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://|<script|@import|url\(|<link", page)

    # no process remains in any cell job
    for e in events:
        if e["kind"] == "attempt.process_started":
            assert not host.process_alive(e["pid"], e["created_at"])

    # teardown removes the run's working copies
    assert cli.main([*common, "teardown", rid]) == 0
    assert not (cells / rid).exists()

    # measured, not modelled: what a phase-1 run cost in time, per cell (instrumentation)
    for c in view.cells:
        timings[c.label] = {"outcome": c.outcome, "wall_ms": c.wall_ms.value, "tokens": c.tokens,
                            "pass_at_1": c.scores.get("pass_at_1", views.Measure(None)).value}
    (ROOT / "docs" / "proof").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "proof" / "phase1-e2e-last.json").write_text(json.dumps({"run_id": rid, **timings}, indent=2, default=str),
                                                                  encoding="utf-8")
    shutil.rmtree(kept, ignore_errors=True)  # the last step: every assertion above passed, so the evidence is not needed
