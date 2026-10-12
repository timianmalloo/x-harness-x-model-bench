"""The Antigravity stream-json protocol module (ADR-0025 s1, s3). A J0 stub: `engine.protocol_module` picks this module
for a profile with `transport: agy-stream`, and it exposes exactly `driver.open_session` and `driver.send_turn`'s
parameters and return types, so `engine._attempt` passes the same arguments to either. R-TRANSPORT builds the body.

The architecture rule (tests/test_architecture.py) makes this the only module holding the stream's input event and its
outcome grammar, as `driver.py` is the only one holding ACP's method names.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from harness_bench.driver import Session, TurnRecord, TurnResult
from harness_bench.procs import CellProcess


def open_session(cell: CellProcess, cwd: Path, mode: str | None, handshake_timeout: float,
                 model: str | None = None, result: TurnResult | None = None,
                 mcp_servers: list[dict] | None = None, cancel: threading.Event | None = None) -> Session | None:
    raise NotImplementedError("stream_driver.open_session is not built yet (R-TRANSPORT)")


def send_turn(session: Session, prompt: str, before_send: Callable[[str | None], None], turn: int,
              on_first_update: Callable[[], None] | None = None) -> TurnRecord | None:
    raise NotImplementedError("stream_driver.send_turn is not built yet (R-TRANSPORT)")
