"""Grok native record reader (ADR-0025 s5, ADR-0026). A J0 stub: the seam exists so `profiles.READERS` names it and
no wave-1 track edits `profiles.py` for it; R-READ-GROK builds the body (served settings, reasoning rows, prompt parts,
per-turn usage, tool calls with `TOOL_CLASS` for HB-VAL-008)."""

from __future__ import annotations

from pathlib import Path

from harness_bench.telemetry import Extraction


def read(path: Path) -> Extraction:
    raise NotImplementedError("telemetry.grok.read is not built yet (R-READ-GROK)")
