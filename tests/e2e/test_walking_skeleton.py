"""Phase-1 and wave-1 exits: the real walking skeleton (design: E2E).

Runs the real `bench` CLI with the pinned builds, the operator's subscription logins and real model calls,
then asserts the design's exit list. Workstation only (marked native and credentials).
"""

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import pytest

from harness_bench import archive, cli, host, plan, profiles, views, workspace
from harness_bench.telemetry import copilot

pytestmark = [pytest.mark.native, pytest.mark.credentials]
ROOT = Path(__file__).resolve().parents[2]
MATRICES = ("bench/matrix.phase1.yaml", "bench/matrix.wave1.yaml")


@pytest.fixture
def kept(clean_parent, matrix_id):
    """A clean-ancestry folder the test removes as its own last step, so a failed run stays on disk as evidence.
    (A fixture teardown would run after a failure too, which is how two failed runs lost their evidence.)"""
    folder = clean_parent / f"e2e-{matrix_id}-{int(time.time())}"
    folder.mkdir(parents=True)
    return folder


@pytest.mark.parametrize("matrix_id,matrix_path", [("phase1", MATRICES[0]), ("wave1", MATRICES[1])], ids=["phase1", "wave1"])
def test_the_walking_skeleton_runs_end_to_end(kept, matrix_id, matrix_path, capsys):
    if matrix_id == "wave1" and not os.environ.get("HB_PACK_SOURCE"):
        pytest.fail("wave1 needs HB_PACK_SOURCE: the pack-on cells must run a named pack revision (>= 95), never a default")
    tools_dir = ROOT / ".tools" / "harness"  # installed by the e2e conftest
    runs, cells = kept / "runs", kept / "cells"
    rid = kept.name
    common = ["--root", str(ROOT), "--runs", str(runs), "--cells-root", str(cells), "--tools-dir", str(tools_dir)]
    timings = {}

    started = time.monotonic()
    plan_args = [*common, "plan", "--matrix", str(ROOT / matrix_path), "--run-id", rid, "--confirm"]
    if os.environ.get("HB_PACK_SOURCE"):
        plan_args.extend(("--pack-source", os.environ["HB_PACK_SOURCE"]))
    assert cli.main(plan_args) == 0
    timings["plan_s"] = time.monotonic() - started
    started = time.monotonic()
    assert cli.main([*common, "run", rid]) == 0  # runs every cell, then grades
    timings["run_s"] = time.monotonic() - started
    run_dir = runs / rid
    p = plan.load_confirmed(run_dir)
    view = views.load(run_dir)
    events = views.rows(run_dir, "events")

    # Every planned cell is terminal and has an outcome.
    expected_cells = 4 if matrix_id == "phase1" else 6
    assert len(view.cells) == expected_cells and all(c.outcome in ("completed", "timed_out", "failed") for c in view.cells), \
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
    starts = [e for e in events if e["kind"] == "attempt.process_started"]
    assert {e["cell_id"] for e in starts} == {c.cell_id for c in view.cells}
    for e in starts:
        assert e["build_sha256"] == p["builds"][e["harness"]]["sha256"]

    # US-14: zero permission requests
    outcomes = [e for e in events if e["kind"] == "cell.outcome"]
    assert len(outcomes) == expected_cells
    assert [o["permission_requests"] for o in outcomes] == [0] * expected_cells

    if matrix_id == "wave1":
        assert p["pack"]["revision"] >= 95, p["pack"]  # revision 92's failing hook denied every Copilot tool call (R-27)
        tool_rows = views.rows(run_dir, "tool_calls")
        for cell in (c for c in view.cells if c.harness == "copilot"):
            assert copilot.us14_valid([r for r in tool_rows if r["cell_id"] == cell.cell_id]), cell.label
        # the plan's Copilot instruction datum: pack-on loads the pack's instruction files, pack-off loads none (R-16)
        copilot_cells = [c for c in p["cells"] if c["harness"] == "copilot"]
        assert {c["pack"] for c in copilot_cells} == {"on", "off"}, copilot_cells
        for c in copilot_cells:
            assert (c["instruction_count"] > 0) if c["pack"] == "on" else (c["instruction_count"] == 0), \
                (c["label"], c["pack"], c["instruction_count"])
        # W1-ACP (f), the ledger half: every cell's terminal outcome records last_update_ms (null means not recorded)
        assert all(o.get("last_update_ms") is not None for o in outcomes), \
            [(o["cell_id"], o.get("last_update_ms")) for o in outcomes]

    # bench verify passes (ledger chains and seals, archive hashes and bytes: US-19)
    capsys.readouterr()
    assert cli.main([*common, "verify", rid]) == 0
    assert "verify: ok" in capsys.readouterr().out

    # the re-grade gives byte-identical canonical exports (US-26)
    first = views.export(view)
    assert cli.main([*common, "grade", rid]) == 0
    assert views.export(views.load(run_dir)) == first
    capsys.readouterr()
    assert cli.main([*common, "verify", rid]) == 0  # R-2: the later pass's heads verify on real data (Test Architect N6)
    assert "verify: ok" in capsys.readouterr().out

    # the CLI table and report.html render offline
    assert cli.main([*common, "report", rid]) == 0
    page = (run_dir / "report.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://|<script|@import|url\(|<link", page)
    if os.environ.get("HB_PACK_SOURCE"):
        source = Path(os.environ["HB_PACK_SOURCE"]).resolve()
        assert Path(p["pack"]["source"]) == source
        assert p["pack"]["revision"] == workspace.pack_revision(source)
        assert f"<dt>Pack revision</dt><dd>{p['pack']['revision']}</dd>" in page
        assert f"<dt>Pack commit</dt><dd>{p['pack']['commit']}</dd>" in page

    # no process remains in any cell job
    for e in starts:
        assert not host.process_alive(e["pid"], e["created_at"])

    # teardown removes the run's working copies
    assert cli.main([*common, "teardown", rid]) == 0
    assert not (cells / rid).exists()

    # measured, not modelled: what a phase-1 run cost in time, per cell (instrumentation)
    for c in view.cells:
        timings[c.label] = {"outcome": c.outcome, "wall_ms": c.wall_ms.value, "tokens": c.tokens,
                            "pass_at_1": c.scores.get("pass_at_1", views.Measure(None)).value}
    (ROOT / "docs" / "proof").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "proof" / f"{matrix_id}-e2e-last.json").write_text(
        json.dumps({"run_id": rid, **timings}, indent=2, default=str), encoding="utf-8")
    # the last step: every assertion above passed, so the evidence is not needed. Not ignore_errors: a file the
    # run left open or read-only is a leak, and it fails here (T9: the race's tmp folder, the engine.log handler)
    shutil.rmtree(kept, onexc=archive.make_writable)
    assert not kept.exists()
