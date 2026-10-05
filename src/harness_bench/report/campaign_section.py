"""Report section 3 (X-H2; W1-H design section 6): the campaign block, the property verdicts or the ring check,
the legend, the exclusions block with the R-93 line, and the validity line.

SKELETON: final signatures, neutral wrong values.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from harness_bench import campaign, power
from harness_bench.report import html_builder, model

log = logging.getLogger("harness_bench.report.campaign_section")

PROPERTY_VERDICTS = "property-verdicts"
REGRESSION_CHECK = "regression-check"
DOMINATES_EMPTY = "No arm dominates another."


@dataclass(frozen=True)
class CampaignInput:
    """What `bench report` binds for a campaign run (fixture points 1-4 of the brief)."""

    state: campaign.CampaignState
    prereg: Mapping
    power_inputs: Mapping
    power_result: Mapping[str, power.PowerResult]
    eligibility: campaign.Eligibility
    expected_na: Mapping[str, frozenset[str]]
    read_disagreements: Callable[[], Sequence[str]]


@dataclass(frozen=True)
class Built:
    section: model.Section
    header_block: html_builder.Html
    validity_line: html_builder.Html


def build(view, campaign_obj: CampaignInput) -> Built:
    empty = html_builder.el("section", {"id": "unimplemented"})
    return Built(model.Section("unimplemented", "Unimplemented", empty), html_builder.el("div"), html_builder.el("p"))
