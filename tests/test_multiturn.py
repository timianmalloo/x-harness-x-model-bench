"""W1-J K3: real engine, driver, archive, plan, replay and readers.

Only tests/fake_acp_agent.py substitutes for the adapter. J1a fixes the shared
cell clock; future groups are strict-xfailed only after their assertion reds
have been observed. Test ids in names map directly to W1-J section 11.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run
from test_cli import _pack_repo
from test_driver import _spawn
from test_engine import FakeLauncher, _build_workspace, _events, _plan
from test_lifecycle_conformance import GOOD as LIF_GOOD
from test_plan import _matrix2, _plan2
from test_tools import _fake_tree

from harness_bench import (
    archive,
    cli,
    driver,
    engine,
    ledger,
    lifecycle,
    plan,
    status,
    views,
)
from harness_bench.errors import BenchError, Cause
from harness_bench.telemetry import claude_code, normalize


def usage(n):
    return [{"model": "fake-model", "token_count": {"inputTokens": n, "outputTokens": 0,
             "cachedInputTokens": 0, "cachedWriteTokens": 0, "reasoningOutputTokens": 0}}]


class CellClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


def run_cell(tmp_path, per_turn=None, budget=60, on_row=None, **fake):
    """The actual engine with injected logical time; no real delay is needed."""
    p = _plan(1, budget=budget, parallelism=1)
    p["profiles"] = {"fake": {"usage_source": FakeLauncher.usage_source, "vendor": "fake", "auxiliary_models": []}}
    p["tasks"]["X1"]["turns"] = [{"n": 2, "prompt": "Repair it.\n", "sha256": hashlib.sha256(b"Repair it.\n").hexdigest()}]
    log = tmp_path / "prompts.jsonl"
    cfg = {"prompts_log": str(log), "model": "fake-model",
           "per_turn": per_turn or [{"files": {"a.txt": "1"}}, {"files": {"a.txt": "2"}}], **fake}
    launcher = FakeLauncher({p["cells"][0]["label"]: cfg})
    clock = CellClock()
    config = engine.EngineConfig(tmp_path / "runs" / p["run_id"], tmp_path / "cells", {"fake": launcher},
                                 _build_workspace, None, loop_interval=0.01, clock=clock)
    p["plan_hash"] = plan.plan_hash(p)
    plan.confirm(config.run_dir, p)

    class ObservedEngine(engine.Engine):
        def _after_append(self, row):
            super()._after_append(row)
            if on_row:
                on_row(self, row, clock)

    e = ObservedEngine(p, config)
    # Same bounded worker helper as existing engine tests; run this instance.
    box = {}

    def target():
        box["summary"] = e.run()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(120)
    assert not thread.is_alive(), "multi-turn engine did not finish"
    assert "summary" in box, "multi-turn engine raised before producing a summary"
    events = _events(config.run_dir)
    return box["summary"], events, config, log, e


def row(events, kind, turn=None):
    return next((r for r in events if r["kind"] == kind and (turn is None or r.get("turn", 1) == turn)), {})


@pytest.mark.xfail(strict=True, reason="J1d: full replay after J1b loop and J1c snapshots")
def test_t_eng_1_order_snapshot_and_one_session(tmp_path):
    _, events, cfg, log, _ = run_cell(tmp_path)
    kinds = [r["kind"] for r in events if r["kind"] in {"cell.prompt_sent", "cell.turn_ended", "cell.turn_snapshot_archived"}]
    assert kinds == ["cell.prompt_sent", "cell.turn_ended", "cell.turn_snapshot_archived", "cell.prompt_sent", "cell.turn_ended"]
    cid = cfg.run_dir.joinpath("archive").iterdir().__next__().name
    snapshot = archive.snapshot_folder(cfg.run_dir, cid, 1) / "ws" / "a.txt"
    assert snapshot.is_file() and snapshot.read_text(encoding="utf-8") == "1"
    assert (cfg.run_dir / "archive" / cid / "attempt-1/ws/a.txt").read_text(encoding="utf-8") == "2"
    logged = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert sum(r["kind"] == "session/new" for r in logged) == 1
    assert [r["n"] for r in logged if r["kind"] == "session/prompt"] == [1, 2]
    assert logged[-1] == {"kind": "eof"}
    lifecycle.replay(events, parallelism=1)


def test_t_eng_2_one_budget_across_turns(tmp_path):
    def advance(e, r, clock):
        if r["kind"] == "cell.prompt_sent" and r.get("turn") == 2:
            # The first turn consumes six logical seconds. The second barrier
            # is followed by the budget check at twelve, before releasing it.
            clock.now = 12
            e._check_budgets(clock.now)

    # Clock 6 is observed at the second prompt's durable bookkeeping.
    original = engine.Engine._after_append

    def first_six(self, r):
        if r["kind"] == "cell.prompt_sent" and r.get("turn") == 2:
            self.clock.now = 6
        original(self, r)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(engine.Engine, "_after_append", first_six)
        summary, events, _, _, _ = run_cell(tmp_path, budget=10, on_row=advance)
    assert row(events, "cell.prompt_sent", 2), "turn 2 must reach its durable barrier"
    outcome = next(iter(summary.outcomes.values()))
    assert outcome["outcome"] == "timed_out", outcome


@pytest.mark.parametrize("source", ["acp_turn", "native_record"])
@pytest.mark.xfail(strict=True, reason="J1b: sum usage across returned turns")
def test_t_eng_4_usage_sums_every_turn(tmp_path, source):
    per_turn = [{"usage": usage(n), "native_usage": {"input_tokens": n, "output_tokens": 0,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                "acp_usage": {"inputTokens": n, "outputTokens": 0, "cachedReadTokens": 0, "cachedWriteTokens": 0}}
                for n in (5, 7)]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FakeLauncher, "usage_source", source)
        _, _, cfg, _, _ = run_cell(tmp_path, per_turn)
    rows = views.rows(cfg.run_dir, "turn_usage")
    outcome = row(_events(cfg.run_dir), "cell.outcome")
    cid, sid = outcome["cell_id"], outcome["session_id"]
    native = next((cfg.run_dir / "archive" / cid / "attempt-1/home").rglob("*.jsonl"))
    extraction = claude_code.read(native)
    assert sum(c.uncached_input for c in extraction.model_calls) == 12
    gid = "j1-crosscheck"
    with ledger.SegmentWriter.create(cfg.run_dir / "model_calls", f"grade-{gid}") as writer:
        for call in normalize.model_call_rows(cfg.run_dir.name, cid, sid, extraction, "j1-native"):
            writer.append(call)
        writer.seal()
    with ledger.SegmentWriter.create(cfg.run_dir / "scores", f"grade-{gid}") as writer:
        writer.append({"kind": "score", "run_id": cfg.run_dir.name, "grading_id": gid, "cell_id": cid,
                       "metric_id": "usage", "extraction_id": "j1-native", "value": 1, "reason": None})
        writer.seal()
    with ledger.SegmentWriter.create(cfg.run_dir / "events", f"grade-{gid}") as writer:
        writer.append(ledger.stamp({"kind": "grading.started", "grading_id": gid, "catalog_version": "0.7"}))
        writer.append(ledger.stamp({"kind": "grading.completed", "grading_id": gid}))
        writer.seal()
    with pytest.MonkeyPatch.context() as patch:
        # This fixture adapter reports complete ACP totals like Copilot. The
        # real extractor, ledger and view cross-check remain in use.
        patch.setattr(views, "ACP_TOTAL_HARNESSES", (*views.ACP_TOTAL_HARNESSES, "fake"))
        view = views.load(cfg.run_dir)
        assert view.grading_id == gid
        assert sum(r["uncached_input"] for r in rows) == 12, rows
        assert not [f for c in view.cells for f in c.warnings if f.code == "HB-VAL-005"]
    assert not [f for f in views.verify(cfg.run_dir) if f.code == "HB-VAL-005"]


@pytest.mark.xfail(strict=True, reason="J1c: snapshot precedes turn-two suspend")
def test_t_eng_5_suspend_during_turn_two_keeps_snapshot(tmp_path):
    def suspend(e, r, clock):
        if r["kind"] == "cell.prompt_sent" and r.get("turn") == 2:
            e._kill(e.active[r["cell_id"]], "host_suspended")

    summary, events, _, _, _ = run_cell(tmp_path, on_row=suspend)
    assert row(events, "cell.turn_snapshot_archived", 1), "snapshot must precede the suspend gap"
    assert next(iter(summary.outcomes.values()))["cause"] == "host_suspended"


@pytest.mark.xfail(strict=True, reason="J1b: only end_turn continues; record stopping turns")
def test_t_eng_6_only_end_turn_continues(tmp_path):
    _, events, _, _, _ = run_cell(tmp_path, [{"stop_reason": "max_tokens"}, {"stop_reason": "end_turn"}])
    assert not row(events, "cell.prompt_sent", 2), "max_tokens must not send turn 2"
    ended = row(events, "cell.turn_ended", 1)
    assert (ended.get("stop_reason"), ended.get("next")) == ("max_tokens", "stop")
    assert not row(events, "cell.turn_snapshot_archived")


@pytest.mark.xfail(strict=True, reason="J1c: cancel-aware snapshot step")
def test_t_eng_7_budget_cancel_during_copy_never_sends_next(tmp_path, monkeypatch):
    def cancelled_copy(self, a, cell, cell_dir, turn, launcher, cp):
        self._kill(a, "timeout")
        return False

    monkeypatch.setattr(engine.Engine, "_snapshot_turn", cancelled_copy)
    summary, events, cfg, _, _ = run_cell(tmp_path)
    assert not row(events, "cell.prompt_sent", 2), "snapshot cancellation must stop the next send"
    assert not row(events, "cell.turn_snapshot_archived")
    assert not list((cfg.run_dir / "archive").glob("*/turn-1"))
    assert not list((cfg.run_dir / "archive").glob("*/*.tmp-*"))
    assert next(iter(summary.outcomes.values()))["outcome"] == "timed_out"


@pytest.mark.parametrize(("config", "cause"), [({"mode": "eof_mid_turn"}, "adapter_crash"),
                                                ({"prompt_error": "not authenticated"}, "blocked_auth")])
@pytest.mark.xfail(strict=True, reason="J1c: preserve snapshot on turn-two error")
def test_t_eng_8_9_failed_second_turn_keeps_snapshot(tmp_path, config, cause):
    summary, events, _, _, _ = run_cell(tmp_path, [{}, config])
    assert row(events, "cell.turn_snapshot_archived", 1), "a failed second turn must retain snapshot 1"
    assert not row(events, "cell.turn_ended", 2)
    assert next(iter(summary.outcomes.values()))["cause"] == cause


@pytest.mark.xfail(strict=True, reason="J1b: write returned turn before cancel decision")
def test_t_eng_10_returned_turn_is_recorded_before_cancel(tmp_path, monkeypatch):
    observed = {}
    def cancel(e, r, clock):
        if r["kind"] == "attempt.process_started":
            observed["engine"] = e

    send = driver.send_turn

    def returned(*args, **kwargs):
        rec = send(*args, **kwargs)
        if rec is not None and rec.turn == 1:
            e = observed["engine"]
            e._kill(next(iter(e.active.values())), "stop")
        return rec

    monkeypatch.setattr(driver, "send_turn", returned)

    _, events, _, _, _ = run_cell(tmp_path, on_row=cancel)
    ended = row(events, "cell.turn_ended", 1)
    assert ended, "a returned response must be recorded before a cancel decision"
    assert ended.get("usage") is not None
    assert ended.get("next") == "cancel"
    assert not row(events, "cell.prompt_sent", 2)


@pytest.mark.xfail(strict=True, reason="J1b: per-turn records carry total agent time")
def test_t_eng_11_outcome_last_turn_and_total_agent_time(tmp_path):
    summary, events, _, _, _ = run_cell(tmp_path)
    ended = [r for r in events if r["kind"] == "cell.turn_ended"]
    assert len(ended) == 2, "agent time requires every returned turn"
    assert sum(r["turn_seconds"] for r in ended) >= ended[-1]["turn_seconds"]
    assert next(iter(summary.outcomes.values()))["turn_ms"] == int(ended[-1]["turn_seconds"] * 1000)


@pytest.mark.xfail(strict=True, reason="J1b: one handshake per session")
def test_t_drv_1_one_handshake_for_two_prompts(tmp_path):
    log = tmp_path / "prompts.jsonl"
    cp = _spawn(tmp_path, prompts_log=str(log))
    session = None
    try:
        session = driver.open_session(cp, tmp_path, None, 10)
        assert session is not None
        assert driver.send_turn(session, "one", lambda sid: None, 1) is not None
        assert driver.send_turn(session, "two", lambda sid: None, 2) is not None
        session.close()
        cp.wait(timeout=10)
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert sum(r["kind"] == "session/new" for r in rows) == 1, rows
        assert [r.get("prompt") for r in rows if r["kind"] == "session/prompt"] == ["one", "two"]
        assert rows[-1] == {"kind": "eof"}
    finally:
        cp.terminate_and_confirm(timeout=10)
        cp.close()


@pytest.mark.xfail(strict=True, reason="J1b: idempotent Session.close")
def test_t_drv_2_close_is_idempotent_and_closed_send_has_cause(tmp_path):
    cp = _spawn(tmp_path)
    try:
        session = driver.open_session(cp, tmp_path, None, 10)
        assert session is not None
        error = None
        try:
            session.close()
            session.close()
        except ValueError as exc:
            error = exc
        assert error is None, "Session.close must close stdin exactly once"
        assert driver.send_turn(session, "unsent", lambda sid: None, 1) is None
        assert session.result.cause is not None
    finally:
        cp.terminate_and_confirm(timeout=10)
        cp.close()


@pytest.mark.parametrize("fake", ["ok", "eof_mid_turn"])
def test_t_drv_1_wrapper_keeps_single_turn_failure_semantics(tmp_path, fake):
    cp = _spawn(tmp_path, fake=fake)
    try:
        result = driver.run_turn(cp, tmp_path, "one", None, 10, lambda sid: None)
        assert (result.stop_reason, result.cause) == (("end_turn", None) if fake == "ok" else (None, Cause.adapter_crash))
    finally:
        cp.terminate_and_confirm(timeout=10)
        cp.close()


def test_k1_native_record_contains_both_turns_without_duplicate_message_ids(tmp_path):
    records = [{"usage": usage(n), "native_usage": {"input_tokens": n, "output_tokens": 0,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}} for n in (5, 7)]
    _, events, cfg, _, _ = run_cell(tmp_path, records)
    cid = row(events, "cell.outcome")["cell_id"]
    native = next((cfg.run_dir / "archive" / cid / "attempt-1/home").rglob("*.jsonl"))
    extraction = claude_code.read(native)
    assert sum(call.uncached_input for call in extraction.model_calls) == 12, extraction.model_calls


def make_cell(tmp_path):
    cell = tmp_path / "cell"
    (cell / "ws").mkdir(parents=True)
    (cell / "home").mkdir()
    (cell / "ws/a.txt").write_text("one", encoding="utf-8")
    (cell / "ws/b.txt").write_text("two", encoding="utf-8")
    (cell / "ws/.credentials.json").write_text("secret", encoding="utf-8")
    (cell / "home/record.jsonl").write_text("native", encoding="utf-8")
    return cell


@pytest.mark.xfail(strict=True, reason="J1c: publish_dir and failed-copy temp cleanup")
def test_t_snap_1_failed_copy_never_publishes_final(tmp_path, monkeypatch):
    cell = make_cell(tmp_path)
    dest = tmp_path / "run/archive/c"
    original = archive._sha

    def fail(path):
        if path.name == "b.txt":
            raise PermissionError("source locked")
        return original(path)

    monkeypatch.setattr(archive, "_sha", fail)
    try:
        archive.snapshot_cell(cell, dest, 1, {".credentials.json"})
    except OSError:
        pass
    assert not (dest / "turn-1").exists(), "failed copy must leave no complete-looking final name"
    assert not list(dest.glob("*.tmp-*"))
    monkeypatch.setattr(archive, "_sha", original)
    assert archive.snapshot_cell(cell, dest, 1, {".credentials.json"}).folder.is_dir()


@pytest.mark.xfail(strict=True, reason="J1c: verify and refuse planted snapshots")
def test_t_snap_2_planted_snapshot_is_refused_without_merge(tmp_path):
    cell = make_cell(tmp_path)
    dest = tmp_path / "run/archive/c"
    (dest / "turn-1").mkdir(parents=True)
    (dest / "turn-1/stray").write_text("keep", encoding="utf-8")
    code = None
    try:
        archive.snapshot_cell(cell, dest, 1, set())
    except (BenchError, FileExistsError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
    assert code == "HB-LED-008", code
    assert (dest / "turn-1/stray").read_text(encoding="utf-8") == "keep"


@pytest.mark.xfail(strict=True, reason="J1c: append only missing rows; compare present rows")
def test_t_snap_3_only_missing_rows_are_returned_and_conflicts_use_folder_code(tmp_path):
    (tmp_path / "ws").mkdir()
    (tmp_path / "ws/a").write_bytes(b"a")
    (tmp_path / "ws/b").write_bytes(b"bb")
    rows = [{"path": "ws/a", "kind": "file", "size": 1, "sha256": hashlib.sha256(b"a").hexdigest(), "link_target": ""},
            {"path": "ws/b", "kind": "file", "size": 2, "sha256": hashlib.sha256(b"bb").hexdigest(), "link_target": ""}]
    assert archive.append_missing_rows(tmp_path, rows, rows[:1], "HB-LED-008") == rows[1:]
    for code in ("HB-LED-008", "HB-LED-005"):
        raised = None
        try:
            archive.append_missing_rows(tmp_path, rows, [{**rows[0], "size": 99}], code)
        except BenchError as exc:
            raised = exc.code
        assert raised == code


@pytest.mark.xfail(strict=True, reason="J1c: ws-only snapshot with credential exclusions")
def test_t_snap_4_snapshot_copies_ws_only_and_excludes_credentials(tmp_path):
    result = archive.snapshot_cell(make_cell(tmp_path), tmp_path / "run/archive/c", 1, {".credentials.json"})
    assert not (result.folder / "home").exists(), "snapshots must exclude home"
    assert not (result.folder / "ws/.credentials.json").exists()
    assert {r["path"] for r in result.rows} == {"ws/a.txt", "ws/b.txt"}


@pytest.mark.parametrize("option", ["helper", "daemon_after_update"])
@pytest.mark.xfail(strict=True, reason="J1c: first-update baseline and snapshot process gauges")
def test_t_snap_5_baseline_measured_at_first_update(tmp_path, option):
    _, events, _, _, _ = run_cell(tmp_path, [{option: True}, {}])
    ended = row(events, "cell.turn_ended", 1)
    assert ended.get("job_active_baseline") is not None, "baseline must be recorded, never inferred as zero"
    snapshot = row(events, "cell.turn_snapshot_archived", 1)
    assert snapshot.get("job_active_processes") is not None
    if option == "helper":
        assert snapshot["job_active_processes"] == ended["job_active_baseline"]
    else:
        assert snapshot["job_active_processes"] > ended["job_active_baseline"]
    assert "job_active_after" in snapshot and "copy_retries" in snapshot


@pytest.mark.xfail(strict=True, reason="J1c: bounded source-read retries then Cause.archive")
def test_t_snap_6_locked_source_exhausts_bounded_retry(tmp_path, monkeypatch):
    calls = []

    def locked(*args, **kwargs):
        calls.append(1)
        raise PermissionError("exclusive source handle")

    monkeypatch.setattr(archive, "snapshot_cell", locked)
    summary, events, _, _, _ = run_cell(tmp_path)
    assert next(iter(summary.outcomes.values()))["code"] == "HB-CELL-117"
    assert len(calls) == 3
    assert not row(events, "cell.prompt_sent", 2)


@pytest.mark.xfail(strict=True, reason="J1c: same-attempt snapshot row recovery")
def test_t_snap_3_engine_completes_partial_snapshot_rows_on_retry(tmp_path, monkeypatch):
    record = engine.Engine.record
    appended = []
    failed = []

    def partial(self, fact, r):
        if fact == "archive_files" and r.get("snapshot") == "turn-1":
            if appended and not failed:
                failed.append(True)
                raise OSError("transient snapshot row append")
            appended.append(r["path"])
        return record(self, fact, r)

    monkeypatch.setattr(engine.Engine, "record", partial)
    _, events, cfg, _, _ = run_cell(tmp_path)
    assert row(events, "cell.turn_snapshot_archived", 1), "retry must commit a partially recorded snapshot"
    rows = [r for r in views.rows(cfg.run_dir, "archive_files") if r.get("snapshot") == "turn-1"]
    assert failed and len({r["path"] for r in rows}) == len(rows) >= 2
    assert not [f for f in views.verify(cfg.run_dir) if f.level == "error"]


@pytest.mark.xfail(strict=True, reason="J1c: snapshot links recorded without following")
def test_t_snap_7_link_is_a_row_never_a_copy(tmp_path):
    cell = make_cell(tmp_path)
    sentinel = tmp_path / "outside"
    sentinel.mkdir()
    (sentinel / "secret.txt").write_text("outside", encoding="utf-8")
    link_path = cell / "ws/link"
    if sys.platform == "win32":
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link_path), str(sentinel)], capture_output=True, check=False)
        assert made.returncode == 0, made.stderr
    else:
        os.symlink(sentinel, link_path, target_is_directory=True)
    result = archive.snapshot_cell(cell, tmp_path / "run/archive/c", 1, {".credentials.json"})
    link = next((r for r in result.rows if r["path"] == "ws/link"), {})
    assert link.get("kind") == "link", link
    assert not (result.folder / "ws/link/secret.txt").exists()


def snapshot_run(tmp_path, event=True, duplicate=True):
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    folder = archive.snapshot_folder(run_dir, "a", 1)
    (folder / "ws").mkdir(parents=True)
    path = "ws/slug.py" if duplicate else "ws/first.py"
    (folder / path).write_text("first", encoding="utf-8")
    files = [{"kind": "file", "run_id": "r1", "cell_id": "a", "archive_attempt": 1,
              "snapshot": "turn-1", "path": path, "size": 5, "sha256": hashlib.sha256(b"first").hexdigest(), "link_target": ""}]
    with ledger.SegmentWriter.create(run_dir / "archive_files", "engine-2") as writer:
        for r in files:
            writer.append(r)
    if event:
        with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as writer:
            writer.append({"kind": "cell.turn_snapshot_archived", "cell_id": "a", "turn": 1,
                           "snapshot_hash": archive.archive_hash(files), "files": 1, "bytes": 5,
                           "duration_ms": 0, "job_active_processes": 1, "job_active_after": 1, "copy_retries": 0})
    return run_dir, folder, files


@pytest.mark.xfail(strict=True, reason="J1d: snapshot-aware archive_files key")
def test_t_ver_1_snapshot_and_final_may_share_path(tmp_path):
    run_dir, _, _ = snapshot_run(tmp_path)
    assert views.verify(run_dir) == []


@pytest.mark.parametrize("damage", ["file", "hash", "files", "bytes", "empty"])
@pytest.mark.xfail(strict=True, reason="J1d: verify snapshot bytes, hash, counts and presence")
def test_t_ver_2_snapshot_corruption_is_hb_led_008(tmp_path, damage):
    run_dir, folder, _ = snapshot_run(tmp_path, event=False, duplicate=False)
    if damage == "file":
        (folder / "ws/first.py").write_text("wrong", encoding="utf-8")
    if damage == "empty":
        # Remove only our own sealed snapshot segment; the final segment stays.
        (run_dir / "archive_files/engine-2.jsonl").unlink()
    r = {"kind": "cell.turn_snapshot_archived", "cell_id": "a", "turn": 1,
         "snapshot_hash": archive.archive_hash(views.rows(run_dir, "archive_files")[-1:]), "files": 1, "bytes": 5}
    if damage == "hash":
        r["snapshot_hash"] = "f" * 64
    elif damage in {"files", "bytes"}:
        r[damage] = 99
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as writer:
        writer.append(r)
    findings = views.verify(run_dir)
    assert "HB-LED-008" in {f.code for f in findings}, findings


@pytest.mark.xfail(strict=True, reason="J1d: filter final archive rows through snapshot_of")
def test_t_ver_4_final_hash_ignores_snapshot_rows(tmp_path):
    run_dir, _, _ = snapshot_run(tmp_path)
    findings = views.verify(run_dir)
    assert not [f for f in findings if f.code in {"HB-LED-003", "HB-LED-005"}], findings


def test_t_ver_5_final_writer_omits_snapshot(tmp_path):
    _, _, cfg, _, _ = run_cell(tmp_path)
    rows = views.rows(cfg.run_dir, "archive_files")
    assert rows and all("snapshot" not in r for r in rows if r.get("snapshot", "final") == "final")
    fixed = [{"path": "ws/a", "kind": "file", "size": 1, "sha256": "a" * 64, "link_target": ""}]
    assert archive.archive_hash(fixed) == "1d36b04e8c1076dce870825ba8ce33da50915674573f17129bbc7f42e4454b89"


@pytest.mark.xfail(strict=True, reason="J1d: snapshots committed by events, not rows")
def test_t_ver_6_live_snapshot_rows_without_event_are_ignored(tmp_path):
    run_dir, _, _ = snapshot_run(tmp_path, event=False)
    assert views.verify(run_dir) == []


def test_t_ver_7_final_spellings_share_hash_and_duplicate_key(tmp_path):
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    r = views.rows(run_dir, "archive_files")[0]
    explicit = {**r, "snapshot": "final"}
    assert archive.archive_hash([r]) == archive.archive_hash([explicit])
    with ledger.SegmentWriter.create(run_dir / "archive_files", "engine-2") as writer:
        writer.append({k: v for k, v in explicit.items() if k not in {"seq", "hash", "prev_hash", "recorded_at", "mono_ns"}})
    assert "HB-LED-003" in {f.code for f in views.verify(run_dir)}


def replay_error(events):
    try:
        lifecycle.replay(events, parallelism=1)
    except lifecycle.ConformanceError as exc:
        return str(exc)
    return None


def turn_row(kind, n, **fields):
    return {"kind": kind, "cell_id": "a", "turn": n, **fields}


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.xfail(strict=True, reason="J1d: turn-keyed lifecycle replay")
def test_t_lif_1_valid_turn_streams(count):
    prefix = LIF_GOOD[:5]
    turns = [turn_row("cell.prompt_sent", 1), turn_row("cell.turn_ended", 1, stop_reason="end_turn", next="snapshot" if count == 2 else "final")]
    if count == 2:
        turns += [turn_row("cell.turn_snapshot_archived", 1), turn_row("cell.prompt_sent", 2), turn_row("cell.turn_ended", 2)]
    assert replay_error(prefix + turns + LIF_GOOD[6:]) is None


@pytest.mark.parametrize(("tail", "rule"), [
    ([turn_row("cell.prompt_sent", 1), turn_row("cell.turn_ended", 1), turn_row("cell.turn_snapshot_archived", 1),
      turn_row("cell.prompt_sent", 2), turn_row("cell.prompt_sent", 2)], "PromptOncePerTurn"),
    ([turn_row("cell.prompt_sent", 1), turn_row("cell.turn_ended", 1), turn_row("cell.prompt_sent", 2)], "SnapshotBeforeNextTurn"),
    ([turn_row("cell.prompt_sent", 1), turn_row("cell.turn_snapshot_archived", 1)], "SnapshotAfterTurnEnd"),
    ([turn_row("cell.prompt_sent", 1), turn_row("cell.turn_ended", 2)], "turn_ended follows its prompt_sent"),
])
@pytest.mark.xfail(strict=True, reason="J1d: named per-turn lifecycle rules")
def test_t_lif_2_each_rule_names_its_own_violation(tail, rule):
    error = replay_error(LIF_GOOD[:5] + tail)
    assert error is not None and rule in error, error


@pytest.mark.parametrize(("waiting", "code", "valid"), [
    pytest.param(False, "HB-CELL-119", False, marks=pytest.mark.xfail(strict=True, reason="J1d: CrashedTurnPredicate rejects 119 mid-turn")),
    pytest.param(True, "HB-CELL-118", False, marks=pytest.mark.xfail(strict=True, reason="J1d: CrashedTurnPredicate rejects 118 between turns")),
    (False, "HB-CELL-118", True),  # green on arrival; never fake a red
    pytest.param(True, "HB-CELL-119", True, marks=pytest.mark.xfail(strict=True, reason="J1d: accept between-turns snapshot stream")),
])
def test_t_lif_3_crashed_turn_predicate(waiting, code, valid):
    turns = [turn_row("cell.prompt_sent", 1)]
    if waiting:
        turns += [turn_row("cell.turn_ended", 1), turn_row("cell.turn_snapshot_archived", 1)]
    outcome = {**LIF_GOOD[7], "code": code}
    error = replay_error(LIF_GOOD[:5] + turns + [LIF_GOOD[6], outcome])
    assert (error is None) if valid else (error is not None and "CrashedTurnPredicate" in error), error


def task_root(tmp_path):
    root = tmp_path / "root"
    shutil.copytree(Path(__file__).resolve().parents[1] / "tasks/X1", root / "tasks/X1")
    shutil.copytree(Path(__file__).resolve().parents[1] / "bench", root / "bench")
    turns = root / "tasks/X1/turns"
    turns.mkdir(exist_ok=True)
    (turns / "2.md").write_bytes(b"Fix it.\r\n")
    return root, turns


@pytest.mark.xfail(strict=True, reason="J1d: normalized turn hashes checked on confirmed plan load")
def test_t_plan_1_turn_text_hash_is_normalized_and_confirmed(tmp_path):
    root, _ = task_root(tmp_path)
    body = _plan2(tmp_path, root=root)
    turns = body["tasks"]["X1"].get("turns", [])
    assert turns == [{"n": 2, "prompt": "Fix it.\n", "sha256": hashlib.sha256(b"Fix it.\n").hexdigest()}], turns
    turns[0]["prompt"] = "tampered\n"
    body["plan_hash"] = plan.plan_hash(body)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "plan.json").write_text(json.dumps(body), encoding="utf-8")
    caught = None
    try:
        plan.load_confirmed(run_dir)
    except BenchError as exc:
        caught = exc.code
    assert caught == "HB-LED-002", "a rehashed plan must still validate its embedded turn hash"


@pytest.mark.xfail(strict=True, reason="J1d: at most one extra turn")
def test_t_plan_2_more_than_one_extra_turn_is_refused(tmp_path):
    root, turns = task_root(tmp_path)
    (turns / "3.md").write_text("third", encoding="utf-8")
    caught = None
    try:
        _plan2(tmp_path, root=root)
    except BenchError as exc:
        caught = exc.code
    assert caught is not None, "at most two total turns are allowed"


def test_t_status_1_first_prompt_matches_engine_budget_clock(tmp_path):
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("b",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as writer:
        for kind in ("cell.launch_intent", "attempt.process_started", "attempt.session_opened"):
            writer.append({"kind": kind, "cell_id": "b"})
        writer.append({"kind": "cell.prompt_sent", "cell_id": "b", "turn": 1, "recorded_at": "2026-09-23T11:54:00Z"})
        writer.append({"kind": "cell.prompt_sent", "cell_id": "b", "turn": 2, "recorded_at": "2026-09-23T11:58:12Z"})
    observed = status.build(run_dir, now=datetime(2026, 9, 23, 12, tzinfo=UTC)).running[0]
    assert observed.elapsed_s >= 0.7 * observed.budget_s, observed
    clock = CellClock()
    cfg = engine.EngineConfig(run_dir, tmp_path / "cells", {}, None, None, clock=clock)
    e = engine.Engine({"parameters": {}, "trace_id": "a" * 32}, cfg)
    active = engine._Active({"cell_id": "b"}, threading.Thread())
    e.active["b"] = active
    e._after_append({"kind": "cell.prompt_sent", "cell_id": "b", "turn": 1})
    clock.now = 252
    e._after_append({"kind": "cell.prompt_sent", "cell_id": "b", "turn": 2})
    clock.now = 360
    assert observed.elapsed_s == clock.now - active.prompt_mono == 360
    assert observed.killing


@pytest.mark.xfail(strict=True, reason="J1d: end-to-end CLI wiring after J1b/J1c")
def test_t_wire_1_real_cli_plan_and_run_carries_turns(tmp_path, monkeypatch):
    root, _ = task_root(tmp_path)
    (root / "bench/task-freeze.yaml").unlink(missing_ok=True)
    matrix = _matrix2()
    matrix.update(repetitions=20)
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    tools_dir = _fake_tree(tmp_path / "tools")
    pack_source = tmp_path / "ai-forward"
    commit = _pack_repo(pack_source, with_pack_apply=True)
    runs = tmp_path / "runs"
    args = ["--root", str(root), "--runs", str(runs), "--tools-dir", str(tools_dir),
            "--cells-root", str(tmp_path / "cells")]
    assert cli.main([*args, "plan", "--matrix", str(matrix_path), "--run-id", "wire", "--arm",
                     f"candidate={pack_source}@{commit}", "--confirm"]) == 0
    frozen = plan.load_confirmed(runs / "wire")
    behaviours = {c["label"]: {"prompts_log": str(tmp_path / f"wire-{c['cell_id']}.jsonl"),
                             "per_turn": [{"files": {"a.txt": "1"}}, {"files": {"a.txt": "2"}}]}
                  for c in frozen["cells"]}
    monkeypatch.setattr(cli.profiles, "ProfileLauncher", lambda *a: FakeLauncher(behaviours))
    monkeypatch.setattr(cli.preflight, "check", lambda *a: None)
    # The real workspace builder and CLI plan/run remain on the path. Grading
    # is not part of this wiring assertion, so remove this fixture's graders.
    monkeypatch.setattr(cli.runner, "run_pass", lambda *a, **k: type("Pass", (), {"summary": lambda self: {}})())
    assert cli.main([*args, "run", "wire"]) == 0
    cid = frozen["cells"][0]["cell_id"]
    assert archive.snapshot_folder(runs / "wire", cid, 1).is_dir(), "CLI must carry turns into snapshotting"
    prompts = [json.loads(s) for s in (tmp_path / f"wire-{cid}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["n"] for r in prompts if r["kind"] == "session/prompt"] == [1, 2]
