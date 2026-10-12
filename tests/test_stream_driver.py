"""stream_driver (ADR-0025 s3): Antigravity's stream-json, multi-turn in one process, on agy 1.3.3 streams.

Every stream here is a recorded 1.3.3 session (or built from recorded lines; `fixtures/agy/stream/provenance.json`)
replayed by `fixtures/agy/stream/replay.py`, spawned through `procs` exactly as the engine spawns a cell.
"""

import inspect
import json
import os
import sys
from pathlib import Path

import pytest
from test_driver import _Tap

from harness_bench import engine, procs, stream_driver
from harness_bench.driver import TurnResult
from harness_bench.errors import Cause

STREAMS = Path(__file__).parent / "fixtures" / "agy" / "stream"
REPLAY = STREAMS / "replay.py"

# ADR-0025 s3, the outcome table: (stream, turns sent, row).
TABLE = [
    ("success.ndjson", 1, "completed"),
    ("two-turn.ndjson", 2, "completed"),
    ("denial.ndjson", 1, "blocked"),
    ("denial-tool-error.ndjson", 1, "blocked"),
    ("tool-error-streak.ndjson", 1, "ended"),
    ("unknown-event.ndjson", 1, "protocol"),
]


def outcome_row(result: TurnResult, records: list) -> str:
    """The ADR-0025 s3 row a stream-driver run lands in."""
    if result.cause is Cause.blocked_denied:
        return "blocked"
    if result.cause is stream_driver.STREAK_CAUSE and "NATIVE_ERROR_STREAK_CAP" in result.detail:
        return "ended"
    if result.cause is Cause.protocol:
        return "protocol"
    if result.cause is None and records and all(r is not None for r in records):
        return "completed" if all(r.stop_reason == "end_turn" for r in records) else "incomplete"
    return f"other: {result.cause} {result.detail}"


def drive(tmp_path: Path, stream: Path, turns: int, tap: bool = False):
    """open_session, then up to `turns` send_turn calls as engine._attempt makes them: (result, records, home, cell)."""
    ws, home = tmp_path / "ws", tmp_path / "home"
    ws.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    cell = procs.spawn([sys.executable, str(REPLAY), str(stream)], cwd=str(ws), env=dict(os.environ))
    if tap:
        cell.proc.stdin = _Tap(cell.proc.stdin)
    result, records, barrier = TurnResult(), [], []
    try:
        session = stream_driver.open_session(cell, ws, None, 10.0, None, result, [], None)
        assert session is not None, result.detail
        assert session.channel.cell is cell and isinstance(session.channel.cell, procs.CellProcess)
        try:
            for n in range(1, turns + 1):
                rec = stream_driver.send_turn(session, f"prompt {n}", lambda sid, n=n: barrier.append(n), n)
                records.append(rec)
                if rec is None or rec.stop_reason != "end_turn":
                    break
        finally:
            session.close()
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    return result, records, home, cell


def _derived(tmp_path: Path, name: str, edit) -> Path:
    """A test-local variant of a recorded stream: `edit(event)` returns the event to keep (changed or not)."""
    lines = [edit(json.loads(line)) for line in (STREAMS / name).read_bytes().splitlines()]
    path = tmp_path / f"derived-{name}"
    path.write_bytes(b"".join(json.dumps(e, separators=(",", ":")).encode() + b"\n" for e in lines))
    return path


@pytest.mark.parametrize(("name", "turns", "row"), TABLE, ids=[t[0] for t in TABLE])
def test_each_outcome_row_on_a_recorded_stream(tmp_path, name, turns, row):
    result, records, _, _ = drive(tmp_path, STREAMS / name, turns)
    assert outcome_row(result, records) == row


def test_a_result_that_is_not_success_is_incomplete(tmp_path):  # the table's second row (no recorded 1.3.3 failure)
    def fail(event):
        if event.get("event") == "result":
            event["result"]["status"] = "CANCELLED"
        return event

    result, records, _, _ = drive(tmp_path, _derived(tmp_path, "success.ndjson", fail), 1)
    assert outcome_row(result, records) == "incomplete"
    assert records[0].stop_reason == "CANCELLED" and result.cause is None  # the engine classifies a stop reason


@pytest.mark.parametrize("name", ["denial.ndjson", "denial-tool-error.ndjson"])
def test_a_denial_is_never_a_success(tmp_path, name):
    result, records, _, _ = drive(tmp_path, STREAMS / name, 1)
    assert result.cause is Cause.blocked_denied and result.cause.code == "HB-CELL-203"
    assert records == [None] and result.turns == []  # no turn record, so no cell.turn_ended "end_turn"
    assert result.stop_reason != "end_turn"


def test_a_tool_error_that_is_not_a_permission_check_is_counted_and_the_turn_goes_on(tmp_path):
    result, records, _, _ = drive(tmp_path, STREAMS / "two-turn.ndjson", 2)  # turn 1 holds a view_file ERROR step
    assert result.cause is None and [r.stop_reason for r in records] == ["end_turn", "end_turn"]


def test_a_line_over_8_mib_is_a_protocol_failure(tmp_path):
    lines = (STREAMS / "success.ndjson").read_bytes().splitlines(keepends=True)
    step = json.loads(lines[2])
    step["step_update"]["text_delta"] = "x" * (9 << 20)
    stream = tmp_path / "huge.ndjson"
    stream.write_bytes(lines[0] + lines[1] + json.dumps(step).encode() + b"\n" + lines[-1])
    result, records, _, _ = drive(tmp_path, stream, 1)
    assert outcome_row(result, records) == "protocol" and "8 MiB" in result.detail


def test_bad_json_is_a_protocol_failure(tmp_path):
    lines = (STREAMS / "success.ndjson").read_bytes().splitlines(keepends=True)
    stream = tmp_path / "bad.ndjson"
    stream.write_bytes(lines[0] + b"{not json\n" + b"".join(lines[1:]))
    result, records, _, _ = drive(tmp_path, stream, 1)
    assert outcome_row(result, records) == "protocol"


def test_the_session_reports_what_the_stream_says(tmp_path):
    result, records, _, cell = drive(tmp_path, STREAMS / "two-turn.ndjson", 2, tap=True)
    events = [json.loads(line) for line in (STREAMS / "two-turn.ndjson").read_bytes().splitlines()]
    assert result.session_id == events[0]["conversation_id"]
    assert result.permission_mode_effective == "request-review"  # init.permission_mode, verbatim (R-34)
    assert result.updates == sum(e["event"] == "step_update" for e in events)
    assert [r.usage for r in records] == [{"usage": e["result"]["usage"], "meta": None} for e in events
                                          if e["event"] == "result"]
    assert result.prompt_sent and len(result.turns) == 2
    sent = [json.loads(line) for line in bytes(cell.proc.stdin.data).splitlines()]
    assert sent == [{"event": "user", "message": {"role": "user", "content": f"prompt {n}"}} for n in (1, 2)]


def test_the_stream_is_teed_verbatim_with_one_read_time_per_line(tmp_path):
    _, _, home, _ = drive(tmp_path, STREAMS / "two-turn.ndjson", 2)
    raw = (STREAMS / "two-turn.ndjson").read_bytes()
    assert (home / stream_driver.STREAM_RECORD).read_bytes() == raw
    times, reason = stream_driver.read_times(home / stream_driver.STREAM_RECORD)
    assert reason is None and len(times) == len(raw.splitlines()) and times == sorted(times)


def test_a_sidecar_count_mismatch_gives_not_recorded(tmp_path):
    _, _, home, _ = drive(tmp_path, STREAMS / "two-turn.ndjson", 2)
    sidecar = home / stream_driver.TIMES_RECORD
    sidecar.write_bytes(b"".join(sidecar.read_bytes().splitlines(keepends=True)[:-1]))
    times, reason = stream_driver.read_times(home / stream_driver.STREAM_RECORD)
    assert times is None and reason.startswith("not recorded: ")
    sidecar.unlink()
    assert stream_driver.read_times(home / stream_driver.STREAM_RECORD)[0] is None


def test_the_streak_cap_is_the_oracles():
    from test_agy_oracle import coord_transport

    assert stream_driver.NATIVE_ERROR_STREAK_CAP == coord_transport().NATIVE_ERROR_STREAK_CAP == 5


def test_the_stream_driver_never_spawns_and_keeps_the_driver_signatures():
    """It drives the CellProcess the engine spawned through procs (drive() asserts the session holds it)."""
    source = inspect.getsource(stream_driver)
    assert "subprocess" not in source and "Popen" not in source
    from harness_bench import driver

    for name in ("open_session", "send_turn"):
        assert inspect.signature(getattr(stream_driver, name)).parameters.keys() == \
            inspect.signature(getattr(driver, name)).parameters.keys()


def test_the_cell_home_is_beside_the_worktree_as_the_engine_lays_it_out():
    """The tee lands in cwd.parent / "home" (stream_driver.cell_home): the engine's own layout line."""
    assert 'home, ws = cell_dir / "home", cell_dir / "ws"' in inspect.getsource(engine.Engine)
    assert stream_driver.cell_home(Path("C:/runs/c1/ws")) == Path("C:/runs/c1/home")


def test_unsupported_launch_inputs_fail_closed(tmp_path):
    for kwargs in ({"mode": "agent"}, {"model": "gemini-3.8-flash-high"}, {"mcp_servers": [{"name": "x"}]}):
        result = TurnResult()
        args = {"mode": None, "model": None, "mcp_servers": [], **kwargs}
        session = stream_driver.open_session(None, tmp_path / "ws", args["mode"], 1.0, args["model"], result,
                                             args["mcp_servers"], None)
        assert session is None and result.cause is Cause.adapter_crash and "agy-stream" in result.detail
    result = TurnResult()
    assert stream_driver.open_session(None, tmp_path / "ws", None, 1.0, None, result, [], None,
                                      session_meta={"thinking": {"display": "summarized"}}) is None
    assert result.cause is Cause.adapter_crash
