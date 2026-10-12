"""The shared tool-phase classifier and the carry-until-compaction rule (ADR-0026 s4), one definition each.

The contract only (R-CONTRACT-FACTS); R-DERIV moves the classifier here from `report.pack_improvement`, whose
existing categories are then computed from the same function. The phase rule: `edit` for an edit-class tool or a
write; `verify` for a command matching VERIFY_COMMANDS; `explore` for read, search and list tools and other
commands before the first edit; `other` for the rest.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from harness_bench.telemetry import ToolInput

PHASES = ("explore", "edit", "verify", "other")
VERIFY_COMMANDS = ("pytest", "tox", "ruff", "mypy", "pyright", "unittest")  # the declared test and lint patterns


def phases(calls: Sequence[ToolInput]) -> tuple[str, ...]:
    """One phase (PHASES) per call, in native order; the sequence decides `explore` (before the first edit)."""
    raise NotImplementedError("tool_phases.phases: R-DERIV")


def carry_until_compaction(entered: Sequence[int], compacted_before: Collection[int]) -> tuple[int, ...]:
    """Per request index i, the amount still carried in the context: everything that `entered` at or before i,
    counted again on each later request until a compaction (`compacted_before` holds the request indices a
    compaction precedes), which drops what entered before it."""
    raise NotImplementedError("tool_phases.carry_until_compaction: R-DERIV")
