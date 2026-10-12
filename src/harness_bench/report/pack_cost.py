"""`bench report --pack-cost` (ADR-0029): where the AI-Forward pack's tokens go, for the pack owner.

The contract only (R-CONTRACT-FACTS): the `PackCost` dataclasses and the `build`/`render`/`cli_main` signatures.
`build(views) -> PackCost` is pure and defines no derivation of its own (tool phases, bytes, carry until compaction
and the per-request input series come from `report.tool_phases` and `report.context_growth`). Pack-on and pack-off
cells pair by (harness, task, batch); every figure is per harness, a per-pair median with its range, never pooled.
Each harness row carries its `transport` (Ruling 120). Tokens only: no price (Ruling 115).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from harness_bench.views import Measure, RunView

# ADR-0029 s3: the decomposition of the pack-on minus pack-off token delta per pair; `residual` is shown, never spread.
TERMS = ("fixed_prefix", "extra_requests", "pack_reads", "skill_loads", "hooks", "reasoning_output", "residual")
# ADR-0029 s4: the class of a pack file, by its path and frontmatter; `unclassified` when the pack source is not read.
COMPONENTS = ("always_applied_instruction", "scoped_instruction", "agents_md", "skill", "persona", "hook",
              "knowledge_doc", "other", "unclassified")


@dataclass(frozen=True)
class Term:
    """One decomposition term for one harness: the per-pair median with its range, and its label (Verified, Inferred,
    or a `not recorded` reason; ADR-0029 s3's label column)."""
    name: str  # one of TERMS
    median: Measure
    low: Measure
    high: Measure
    label: str


@dataclass(frozen=True)
class HarnessDecomposition:
    harness: str
    transport: str  # a plan fact (cost_compare.TRANSPORTS)
    pairs: int
    delta_total: Measure
    terms: tuple[Term, ...]  # in TERMS order


@dataclass(frozen=True)
class PackFile:
    """One file of the pack: the pack-on base tree minus the pack-off base tree, for the bound pack revision."""
    path: str
    component: str  # one of COMPONENTS


@dataclass(frozen=True)
class ComponentCost:
    component: str
    harness: str
    tokens_per_cell: Measure


@dataclass(frozen=True)
class TopFile:
    path: str
    component: str
    harness: str
    tokens_per_cell: Measure
    requests_carried: Measure
    delivery: str  # telemetry.DELIVERIES


@dataclass(frozen=True)
class Candidate:
    """A rule-based tuning candidate with its figure; it never claims an effect it did not measure (ADR-0029 s5)."""
    rule: str
    harness: str
    figure: str
    threshold: str  # the module constant it crossed, shown on the page
    lever: str


@dataclass(frozen=True)
class PackCost:
    runs: tuple[str, ...]
    pack_source: str  # e.g. `C:/Projects/ai-forward@<sha>`, from the plan's `arms` block
    pack_source_reason: str | None  # `not recorded: pack source not readable`, or None
    harnesses: tuple[HarnessDecomposition, ...]
    components: tuple[PackFile, ...]
    component_costs: tuple[ComponentCost, ...]
    top_files: tuple[TopFile, ...]
    candidates: tuple[Candidate, ...]
    thresholds: Mapping[str, str]


def build(views: Sequence[RunView]) -> PackCost:
    """Pure: the decomposition, the component map and the candidates (R-PACKCOST builds it)."""
    raise NotImplementedError("pack_cost.build: R-PACKCOST")


def render(pc: PackCost, analysis_html: str | None = None) -> str:
    """The page's HTML; `analysis_html` is the analyst section, absent without `--analysis`."""
    raise NotImplementedError("pack_cost.render: R-PACKCOST")


def cli_main(argv: Sequence[str]) -> int:
    """`bench report --pack-cost RUN [RUN ...] --out PATH [--analysis MD] [--open]`, written through `publish`."""
    raise NotImplementedError("pack_cost.cli_main: R-PACKCOST")
