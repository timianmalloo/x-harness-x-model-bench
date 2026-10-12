"""`bench report --cost-compare` (ADR-0027): what each harness spends on the same tasks, for an external reader.

The contract only (R-CONTRACT-FACTS): the `CostCompare` dataclasses and the `build`/`render`/`cli_main` signatures.
`build(views) -> CostCompare` is pure and reads only the views and the report derivations (ADR-0026 s4);
`render(CostCompare) -> str`; `cli_main` writes the page through `report.publish`. Every per-combo row carries its
`SeriesKey`, whose `transport` is a plan fact shown beside the row's numbers (ADR-0027 s0, Ruling 120). A value a
stream does not carry is a `Measure` with its `not recorded` reason, never a 0. Tokens only: no price (Ruling 115).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from harness_bench.views import Measure, RunView

# ADR-0027 s0: ACP, a native stream (ADR-0025), or Copilot `-p` behind the local adapter (ADR-0028).
TRANSPORTS = ("acp", "native stream", "copilot -p (local adapter)")
# ADR-0027 s3: the kiviat's axes, each normalised over all series so toggling a series never rescales.
KIVIAT_AXES = ("token economy", "speed", "request economy", "tool-call economy", "clean cells", "edit orientation",
               "read orientation", "hidden checks passed")


@dataclass(frozen=True)
class SeriesKey:
    """One series is exactly one (combo, arm); `transport` is one of TRANSPORTS, from the plan."""
    combo: str
    harness: str
    model: str
    arm: str
    transport: str


@dataclass(frozen=True)
class ComboRow:
    """Sections 1-3: requested and served effort and context, and the per-cell cost measures."""
    series: SeriesKey
    cells: int
    effort_requested: str
    effort_served: Measure
    context_requested: str | int
    context_served: Measure  # the served window, shown beside every per-combo number where it differs from 1M
    tokens_per_cell: Measure
    tokens_by_bucket: Mapping[str, Measure]
    wall_ms: Measure
    requests_per_cell: Measure
    tool_calls_per_cell: Measure


@dataclass(frozen=True)
class ReasoningRow:
    """Reasoning: counts, volumes and source kinds; excerpts only with `--excerpts` (each at most 280 characters,
    at most three per harness; an email- or UUID-shaped excerpt is dropped and counted)."""
    series: SeriesKey
    tokens_per_cell: Measure
    tokens_per_request: Measure
    visible_chars: Measure
    source_kinds: tuple[str, ...]
    excerpts: tuple[str, ...]
    excerpts_dropped: int


@dataclass(frozen=True)
class ContextCurve:
    """The per-request context curve: the median cell, with the min-max band, per request index."""
    series: SeriesKey
    served_window: Measure
    median: tuple[int, ...]
    low: tuple[int, ...]
    high: tuple[int, ...]


@dataclass(frozen=True)
class PromptComposition:
    """Prompt composition from `prompt_parts`: characters per part kind, and the instruction files sent."""
    series: SeriesKey
    chars_by_part: Mapping[str, Measure]
    instruction_files: Measure


@dataclass(frozen=True)
class ToolPhaseRow:
    """Tool phases (explore, edit, verify, other) per cell, and the bytes the tools returned."""
    series: SeriesKey
    explore: Measure
    edit: Measure
    verify: Measure
    other: Measure
    bytes_returned: Measure


@dataclass(frozen=True)
class TimeAnatomyRow:
    """Time anatomy: native model time, the ACP-arrival estimate as its own labelled measure, tool, hook, idle."""
    series: SeriesKey
    model_ms: Measure
    model_ms_acp_estimate: Measure
    tool_ms: Measure
    hook_ms: Measure
    idle_ms: Measure


@dataclass(frozen=True)
class DriftRow:
    """Drift three ways plus attention drift, with the out-of-scope paths listed."""
    series: SeriesKey
    machine_lines: Measure
    task_implied_lines: Measure
    discretionary_lines: Measure
    attention_drift: Measure
    out_of_scope_paths: tuple[str, ...]


@dataclass(frozen=True)
class KiviatSeries:
    """One kiviat series: axis (KIVIAT_AXES) -> its value normalised over all series; None = not recorded."""
    series: SeriesKey
    axes: Mapping[str, str | None]  # decimal strings, as the ledger writes non-integers


@dataclass(frozen=True)
class CostCompare:
    runs: tuple[str, ...]
    catalog_version: str | None
    excerpts: bool  # ADR-0027 s0: off by default on this external page
    combos: tuple[ComboRow, ...]
    reasoning: tuple[ReasoningRow, ...]
    context: tuple[ContextCurve, ...]
    prompt_composition: tuple[PromptComposition, ...]
    tool_phases: tuple[ToolPhaseRow, ...]
    time_anatomy: tuple[TimeAnatomyRow, ...]
    drift: tuple[DriftRow, ...]
    kiviat: tuple[KiviatSeries, ...]


def build(views: Sequence[RunView]) -> CostCompare:
    """Pure: every number from the views and the ADR-0026 s4 derivations (R-DERIV builds it)."""
    raise NotImplementedError("cost_compare.build: R-DERIV")


def render(cc: CostCompare) -> str:
    """The page's HTML (R-REPORT-R builds it)."""
    raise NotImplementedError("cost_compare.render: R-REPORT-R")


def cli_main(argv: Sequence[str]) -> int:
    """`bench report --cost-compare RUN [RUN ...] --out PATH [--open] [--excerpts]`, written through `publish`."""
    raise NotImplementedError("cost_compare.cli_main: R-DERIV")
