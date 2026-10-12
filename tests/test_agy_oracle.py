"""The pack's agy adapter is the stream driver's oracle, not its dependency (ADR-0025 s4, Ruling 119 DR-AGY-REUSE).

`coord_transport.run_session("agy", ...)`, its public entry point, and `stream_driver` read the same replayed agy
1.3.3 stream and must land in the same ADR-0025 s3 outcome row. A pack update that changes the grammar turns this red.
coord_transport is pack-managed and is imported only here, from its file; its `sys.path` insert is undone after.
"""

import functools
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from test_stream_driver import REPLAY, STREAMS, TABLE, _derived, drive, outcome_row

SCRIPT = Path(__file__).resolve().parent.parent / "docs" / "ai-forward-pack" / "scripts" / "coord_transport.py"
ORACLE_ROWS = {"complete": "completed", "incomplete": "incomplete", "native_tool_error_limit": "ended",
               "protocol_error": "protocol"}


@functools.cache
def coord_transport():
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("coord_transport_oracle", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved  # its import-time sys.path[0] insert stays out of every later import
    return module


def oracle_row(stream: Path, turns: int, cwd: Path) -> str:
    result = coord_transport().run_session(
        "agy", [sys.executable, str(REPLAY), str(stream)], str(cwd), dict(os.environ),
        [f"prompt {n}" for n in range(1, turns + 1)], 60, 1 << 20, lambda event: None, lambda: False)
    if result["outcome"] == "blocked" and result["code"] == "permission_denied":
        return "blocked"
    return ORACLE_ROWS.get(result["code"], f"other: {result['outcome']} {result['code']}")


def _incomplete(event):
    if event.get("event") == "result":
        event["result"]["status"] = "CANCELLED"
    return event


@pytest.mark.parametrize(("name", "turns", "row"), [*TABLE, ("incomplete", 1, "incomplete")],
                         ids=[t[0] for t in TABLE] + ["incomplete"])
def test_the_oracle_and_the_stream_driver_give_the_same_row(tmp_path, name, turns, row):
    stream = _derived(tmp_path, "success.ndjson", _incomplete) if name == "incomplete" else STREAMS / name
    oracle_cwd = tmp_path / "oracle"
    oracle_cwd.mkdir()
    oracle = oracle_row(stream, turns, oracle_cwd)
    result, records, _, _ = drive(tmp_path, stream, turns)
    assert (oracle, outcome_row(result, records)) == (row, row)
