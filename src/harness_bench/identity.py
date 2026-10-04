"""Engine classification and catalog identity (W1-D, dispatch D1).

One class per source file, keyed relative to src/harness_bench/. The manifest
and launch recheck are dispatch D2.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

# Pattern: Table-driven classification (ADR-0017 Amendment 1; W0 §9).
# Explicit file keys keep a new file red until its class is reviewed.
CLASSES: Mapping[str, Literal["run", "grade"]] = {
    "__init__.py": "run",
    "archive.py": "run",
    "cli.py": "run",
    "config.py": "run",
    "driver.py": "run",
    "engine.py": "run",
    "errors.py": "run",
    "gitsafe.py": "run",
    "host.py": "run",
    "ledger.py": "run",
    "lifecycle.py": "run",
    "oslock.py": "run",
    "plan.py": "run",
    "preflight.py": "run",
    "procs.py": "run",
    "profiles.py": "run",
    "tools.py": "run",
    "workspace.py": "run",
    "scripted_user/__init__.py": "run",
    "scripted_user/clarifications.py": "run",
    "scripted_user/log.py": "run",
    "scripted_user/matcher.py": "run",
    "scripted_user/server.py": "run",
    "telemetry/__init__.py": "run",
    "telemetry/claude_code.py": "run",
    "telemetry/codex.py": "run",
    "telemetry/copilot.py": "run",
    "telemetry/normalize.py": "run",
    "board.py": "grade",
    "composites.py": "grade",
    "egress.py": "grade",
    "stats.py": "grade",
    "status.py": "grade",
    "views.py": "grade",
    "gateway/__init__.py": "grade",
    "gateway/backend.py": "grade",
    "gateway/calibration.py": "grade",
    "gateway/pipeline.py": "grade",
    "gateway/request.py": "grade",
    "gateway/schema.py": "grade",
    "gateway/scrub.py": "grade",
    "gateway/store.py": "grade",
    "gateway/schemas/summary-claims.v1.json": "grade",
    "gateway/schemas/verdict-set.v1.json": "grade",
    "grade/__init__.py": "grade",
    "grade/_changes.py": "grade",
    "grade/architecture.py": "grade",
    "grade/clarify.py": "grade",
    "grade/coordination.py": "grade",
    "grade/correctness.py": "grade",
    "grade/cost.py": "grade",
    "grade/drift.py": "grade",
    "grade/formal.py": "grade",
    "grade/judge.py": "grade",
    "grade/mutation.py": "grade",
    "grade/process.py": "grade",
    "grade/rigor.py": "grade",
    "grade/runner.py": "grade",
    "report/__init__.py": "grade",
    "report/cli_table.py": "grade",
    "report/context_growth.py": "grade",
    "report/credentials.py": "grade",
    "report/html.py": "grade",
    "report/html_builder.py": "grade",
    "report/judges.py": "grade",
    "report/model.py": "grade",
    "report/pack_improvement.py": "grade",
    "report/summaries.py": "grade",
    "report/assets/report.js": "grade",
    # W0 §9 includes these future phase modules and the two landed D1/F0 modules.
    "atomic.py": "run",
    "identity.py": "run",
    "resume.py": "run",
    "campaign.py": "grade",
    "power.py": "grade",
    "verdicts.py": "grade",
    "gates.py": "grade",
    "discriminate.py": "grade",
    "readiness.py": "grade",
    "synthetic_agent.py": "grade",
    "grade/property.py": "grade",
    "grade/bench_check.py": "grade",
    "grade/_env.py": "grade",
    "report/campaign_section.py": "grade",
    "grade/rework.py": "grade",
    "alarm.py": "grade",
    "grade/noguess.py": "grade",
    "grade/diffstats.py": "grade",
}

# Explicitly retired on landing; stale() prevents a landed key lingering here.
PLANNED: frozenset[str] = frozenset({
    "resume.py", "campaign.py", "power.py", "verdicts.py", "gates.py",
    "discriminate.py", "readiness.py", "synthetic_agent.py", "grade/bench_check.py",
    "report/campaign_section.py", "grade/rework.py", "alarm.py",
    "grade/noguess.py", "grade/diffstats.py",
})

# R-94 condition 3: exactly three validate-time edges, not cell-path imports.
RUN_IMPORTS_GRADE_ALLOWED: Mapping[tuple[str, str], str] = {
    ("config.py", "egress.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
    ("config.py", "gateway/backend.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
    ("config.py", "gateway/scrub.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
}


def catalog_hash(root: Path) -> str:
    """R-59 c1: tree_hash over metrics.yaml and rubrics/, relative to bench/."""
    from harness_bench.plan import tree_hash

    bench = root / "bench"
    rubrics = [p for p in (bench / "rubrics").rglob("*") if p.is_file()] if (bench / "rubrics").is_dir() else []
    return tree_hash(bench, [bench / "metrics.yaml", *rubrics])


def _source_files(root: Path) -> set[str]:
    src = root / "src" / "harness_bench"
    return {p.relative_to(src).as_posix() for p in src.rglob("*")
            if p.is_file() and "__pycache__" not in p.relative_to(src).parts}


def unclassed(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return disk files without a class; root is the repository root."""
    return sorted(_source_files(root) - classes.keys())


def stale(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return ghost class entries and planned entries that have landed."""
    files = _source_files(root)
    return sorted((classes.keys() - files - planned) | (files & planned))
