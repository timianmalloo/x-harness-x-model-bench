"""Antigravity native record reader (ADR-0025 s6, ADR-0026). A J0 stub: the seam exists so `profiles.READERS` names
it and no wave-1 track edits `profiles.py` for it; R-READ-AGY builds the body (`init.model`, per-step usage, tool
events, thinking text from the conversation store). It may read the stream's event bodies (`init`, `step_update`, tool
events); the input event and the outcome grammar stay in `stream_driver.py` (tests/test_architecture.py)."""

from __future__ import annotations

from pathlib import Path

from harness_bench.telemetry import Extraction


def read(path: Path) -> Extraction:
    raise NotImplementedError("telemetry.agy.read is not built yet (R-READ-AGY)")
