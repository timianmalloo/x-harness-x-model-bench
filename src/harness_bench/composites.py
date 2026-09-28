"""Composites: normalisation, area composites, and correctness-gated composites (S-08f).

Pure over a loaded Catalog; reads a file only in load_catalog.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import config
from harness_bench.stats import Measure


@dataclass(frozen=True)
class Catalog:
    version: str
    hash: str
    metrics: Mapping[str, Mapping]
    areas: Mapping[str, tuple[str, ...]]
    has_anchors: bool


def load_catalog(root: Path) -> Catalog:
    from harness_bench.grade.runner import catalog_hash

    metrics_yaml = config.load_yaml(root / "bench" / "metrics.yaml")
    version = str(metrics_yaml.get("version", ""))
    chash = catalog_hash(root)
    metrics: dict[str, Mapping] = {}
    areas: dict[str, tuple[str, ...]] = {}
    for area_id, area_data in (metrics_yaml.get("areas") or {}).items():
        m_ids = []
        for m in area_data.get("metrics") or []:
            mid = m["id"]
            metrics[mid] = m
            m_ids.append(mid)
        areas[area_id] = tuple(m_ids)
    weighted = [
        m for m in metrics.values()
        if m.get("kind") == "score" and m.get("weight", 0) > 0
    ]
    has_anchors = bool(weighted) and all(m.get("anchor") is not None for m in weighted)
    return Catalog(
        version=version,
        hash=chash,
        metrics=metrics,
        areas=areas,
        has_anchors=has_anchors,
    )


def normalise(
    metric_id: str,
    raw: Measure,
    cat: Catalog,
    pass_catalog_version: str | None = None,
    pass_catalog_hash: str | None = None,
) -> Measure:
    if pass_catalog_hash is not None and pass_catalog_hash != cat.hash:
        v = pass_catalog_version or "unknown"
        return Measure(
            None,
            f"graded under catalog {v} ({pass_catalog_hash[:12]}); the loaded catalog is {cat.version} ({cat.hash[:12]})",
        )
    if raw.value is None:
        return Measure(None, raw.reason)
    entry = cat.metrics.get(metric_id)
    if entry is None or entry.get("anchor") is None:
        return Measure(None, f"no normalisation anchor for {metric_id} in catalog {cat.version}")
    worst = Decimal(str(entry["anchor"][0]))
    best = Decimal(str(entry["anchor"][1]))
    if worst == best:
        return Measure(None, f"anchor worst == best for {metric_id}")
    x = Decimal(str(raw.value))
    t = (x - worst) / (best - worst)
    clamped_t = min(Decimal(1), max(Decimal(0), t))
    return Measure(Decimal(100) * clamped_t, None)


def area(
    scores: Mapping[str, Measure],
    area_id: str,
    cat: Catalog,
) -> tuple[Measure, tuple[tuple[str, str], ...]]:
    # RED-FIRST MUTANT: keeps NA metric's weight in the denominator
    metric_ids = cat.areas.get(area_id, ())
    included_sum = Decimal(0)
    denom = Decimal(0)
    excluded: list[tuple[str, str]] = []
    for mid in metric_ids:
        entry = cat.metrics.get(mid, {})
        if entry.get("kind") != "score" or entry.get("weight", 0) <= 0:
            continue
        weight = Decimal(str(entry.get("weight", 1)))
        denom += weight  # Bug: adds all weights unconditionally
        score = scores.get(mid)
        if score is None or score.value is None:
            reason = score.reason if score and score.reason else "not recorded"
            excluded.append((mid, reason))
        else:
            included_sum += weight * Decimal(str(score.value))
    if denom == Decimal(0) or not any(scores.get(m) and scores[m].value is not None for m in metric_ids):
        return Measure(None, f"no {area_id} metric recorded"), tuple(excluded)
    return Measure(included_sum / denom, None), tuple(excluded)


def overall(scores: Mapping[str, Measure], cat: Catalog) -> Measure:
    vals: list[Decimal] = []
    for a in cat.areas:
        m, _ = area(scores, a, cat)
        if m.value is not None:
            vals.append(m.value)
    if not vals:
        return Measure(None, "all area composites NA")
    return Measure(sum(vals, Decimal(0)) / Decimal(len(vals)), None)


def gated(scores: Mapping[str, Measure], cat: Catalog) -> Measure:
    p1 = scores.get("pass_at_1")
    if p1 is not None and p1.value is not None and Decimal(str(p1.value)) == Decimal(0):
        return Measure(Decimal(0), None)
    if p1 is None or p1.value is None:
        return Measure(None, p1.reason if p1 and p1.reason else "pass_at_1 not recorded")
    ov = overall(scores, cat)
    if ov.value is None:
        return Measure(None, ov.reason)
    return Measure(Decimal(str(p1.value)) * ov.value, None)
