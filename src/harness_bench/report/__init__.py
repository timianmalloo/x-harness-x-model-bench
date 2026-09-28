"""Reports over the views (design: UI & interaction design): the CLI table and the static HTML page.

The formatters here are the one definition of how a value reads on every surface. A value that was not
measured reads `NA (<reason>)`, never 0, 0% or $0 (US-27). Numbers carry their unit.
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

import yaml

from harness_bench import config
from harness_bench.errors import BenchError
from harness_bench.views import Measure

# N5 (ruling R-5, Coordinator seam request): Codex 0.156 cells reach the operator's own skill roots
# (finding N5, unfixed, disclosed). Every surface that names a combo or cell flags a Codex one with
# this text; no operator path or skill name is named here, only the flag and where the evidence is.
N5_FLAG = "user-config exposed (N5)"
N5_EVIDENCE = "docs/notes/spike-n5-codex-skill-roots.md, the US-13 canary"


def has_codex_cell(plan: dict) -> bool:
    return any(c.get("harness") == "codex" for c in plan.get("cells", []))


def flag_if_codex(text: str, harness: str) -> str:
    return f"{text} ({N5_FLAG})" if harness == "codex" else text


# R-36(a) (ruling R-36, spike R1.4: "account-level context survives every isolation ... the login, not
# a file"). An account-level connector's tool descriptions reach every Claude Code cell's context, pack on
# or off; the allowlist already denies calling them (fail closed, verified per cell). Every surface that
# names a Claude Code combo or cell flags it with this text; no connector name is named here, only the
# flag and where the evidence is (R-6 condition 4, by reference).
R36_FLAG = "account context (R1.4)"
R36_EVIDENCE = "docs/notes/spike-isolation-permissions.md, the US-13 canary"


def has_claude_code_cell(plan: dict) -> bool:
    return any(c.get("harness") == "claude-code" for c in plan.get("cells", []))


def flag_if_claude_code(text: str, harness: str) -> str:
    return f"{text} ({R36_FLAG})" if harness == "claude-code" else text


def na(m: Measure) -> str:
    return f"NA ({m.reason})"


def rate(m: Measure) -> str:
    return na(m) if m.value is None else f"{Decimal(m.value):.2f}"


def tokens(m: Measure) -> str:
    return na(m) if m.value is None else f"{round(Decimal(m.value)):,} tok"


def seconds(m: Measure) -> str:
    return na(m) if m.value is None else f"{Decimal(m.value) / 1000:.1f} s"


def millis(m: Measure) -> str:
    return na(m) if m.value is None else f"{round(Decimal(m.value)):,} ms"


def usd(m: Measure) -> str:
    return na(m) if m.value is None else f"${Decimal(m.value):.6f}"


def cell_tokens(totals: dict[str, dict[str, int]] | None, reason: str | None) -> str:
    if not totals:
        return f"NA ({reason})"
    return f"{sum(sum(b.values()) for b in totals.values()):,} tok"


HARNESS_LABEL = {"claude-code": "Claude Code", "codex": "Codex", "copilot": "Copilot"}


def context_window(harness: str, tag: str | None) -> str:
    """R-32: the harness's disclosed context-window tag, or "not recorded" when none was recorded."""
    if not tag:
        return "not recorded"
    return f"{HARNESS_LABEL.get(harness, harness)} cells ran with the {tag.upper()} context window"


# R-75 c4/c6 and R-76 c2. The header rows sit with Probe versions; both surfaces read these formatters.
_FAILING_LINE = re.compile(r"^initial_failing_tests: (.*)$", re.MULTILINE)


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _allowance_findings(root: Path | None) -> list[dict]:
    if root is None:
        return []
    findings = _load_yaml(root / "bench" / "regrade-allowed-findings.yaml").get("findings") or []
    return [row for row in findings if isinstance(row, dict)]


def _format_gate_allowance(findings: list[dict]) -> str:
    groups: dict[tuple[str, str, str, str], list[str]] = {}
    for row in findings:
        key = (str(row.get("run", "")), str(row.get("ruling", "")), str(row.get("class", "")), str(row.get("path", "")))
        cell = str(row.get("cell", ""))
        groups.setdefault(key, []).append(f"{cell[:4]}..." if len(cell) > 4 else cell)
    parts = []
    for (run, ruling, klass, path), cells in groups.items():
        n = len(cells)
        word = "error" if n == 1 else "errors"
        parts.append(f"{run} criterion 7 - {n} verify {word} allowed "
                     f"({ruling}, {klass}; {path} of {', '.join(cells)}; not read by any grader)")
    return "; ".join(parts)


def gate_allowance(root: Path | None) -> str:
    """R-76 c2. ``none`` when the allowance file is absent or has no entries."""
    findings = _allowance_findings(root)
    if not findings:
        return "none"
    return _format_gate_allowance(findings)


# R-77 item 3. The run's minimum is the baseline only if some Stryker cell added no red test.
# assume: at least one Stryker cell in the run added no red test; confirmed by the TRX diff of Conditions 4; if false, the flag under-reports by the smallest added count, never over-reports.
_FLAKE_BAND = 1  # R-75 c6, unchanged: a cell above the run's minimum by more than this is flagged


def has_d1_cell(plan: dict) -> bool:
    return any(c.get("task") == "D1" for c in plan.get("cells", []))


def d1_baseline_text(run_dir: Path | None, view) -> str:
    """The header value: min-max over the run's own Stryker cells, or not derived when fewer than two."""
    counts = _d1_failing_counts(run_dir, view)
    n = len(counts)
    if n < 2:  # fewer than two Stryker cells: not derived, never 0 and never a task constant (R-77 item 1)
        return f"not derived ({n} {'cell' if n == 1 else 'cells'})"
    low, high = min(counts), max(counts)
    text = f"{low}-{high} over {n} cells (derived from this run, R-77)"
    spread = high - low
    if spread > _FLAKE_BAND:
        text += f" - baseline unstable within run (spread {spread})"
    return text


def disclosure_rows(
    root: Path | None,
    plan: dict,
    run_dir: Path | None = None,
    view=None,
    board_obj=None,
    params=None,
) -> list[tuple[str, str]]:
    """Header rows: gate allowance, D1 red baseline if D1, primary measure and statistics."""
    rows = [("Gate allowance", gate_allowance(root))]
    if has_d1_cell(plan) and view is not None:
        rows.append(("D1 baseline red tests", d1_baseline_text(run_dir, view)))

    if board_obj is None and view is not None and getattr(view, "grading_id", None) is not None:
        from harness_bench import board, composites

        r = root if root is not None else (config.repo_root() if (config.repo_root() / "bench" / "metrics.yaml").is_file() else None)
        cat = None
        if r is not None and (r / "bench" / "metrics.yaml").is_file():
            try:
                cat = composites.load_catalog(r)
            except (BenchError, OSError, KeyError, ValueError):
                cat = None
        if cat is None:
            cat = composites.Catalog(
                version=getattr(view, "catalog_version", None) or "0.4",
                hash="",
                metrics={},
                areas={},
                has_anchors=False,
            )
        try:
            board_obj = board.build(view, cat, params=params)
        except (BenchError, OSError, KeyError, ValueError):
            board_obj = None

    if board_obj is not None:
        from harness_bench.stats import METHOD

        if board_obj.primary == "pass_at_1":
            primary_text = f"pass@1 ({board_obj.primary_reason})" if board_obj.primary_reason else "pass@1"
            ranked_on = primary_text
        else:
            primary_text = "gated"
            ranked_on = "correctness-gated composite"
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        stat_text = (
            f"{METHOD}, {board_obj.params.resamples} resamples, "
            f"seed {board_obj.params.seed}, resampled by task then repetition, "
            f"Python {py_ver} random stream; ranked on {ranked_on}"
        )
        rows.append(("primary measure", primary_text))
        rows.append(("statistics", stat_text))

    return rows


def initial_failing_tests(run_dir: Path | None, evidence: str | None) -> str:
    """The ``initial_failing_tests`` line in the score's evidence log, or ``not recorded``."""
    if not run_dir or not evidence:
        return "not recorded"
    try:
        text = (run_dir / evidence).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "not recorded"
    match = _FAILING_LINE.search(text)
    if match is None:
        return "not recorded"
    return match.group(1).strip()


def _d1_failing_counts(run_dir: Path | None, view) -> list[int]:
    """initial_failing_tests of this run's D1 cells whose mutation_score has a value. NA cells are excluded."""
    tasks = {c.get("cell_id"): c.get("task") for c in view.plan.get("cells", [])}
    counts = []
    for cell in view.cells:
        measure = cell.scores.get("mutation_score")
        if tasks.get(cell.cell_id) != "D1" or measure is None or measure.value is None:
            continue
        try:
            counts.append(int(initial_failing_tests(run_dir, cell.evidence.get("mutation_score"))))
        except (TypeError, ValueError):
            continue
    return counts


def mutation_score_text(measure: Measure, failing: str, baseline: int | None, derived: bool) -> str:
    """The score with its failing-test count. Above the run's minimum + flake band the score is not shown.

    With fewer than two Stryker cells the baseline is not derived and no cell is flagged (``not checked``).
    """
    score = na(measure) if measure.value is None else f"{Decimal(measure.value):.4f}"
    try:
        n = int(failing)
    except (TypeError, ValueError):
        suffix = "" if derived else " - not checked"
        return f"{score} ({failing}){suffix}"
    if not derived:
        return f"{score} ({n}) - not checked"
    if baseline is not None and n > baseline + _FLAKE_BAND:
        return "red tests added"
    return f"{score} ({n})"


def d1_mutation_values(root: Path | None, run_dir: Path | None, view) -> dict[str, str]:
    """cell_id -> the D1 mutation_score as the report shows it. ``root`` is unused: the baseline is the run's."""
    del root
    counts = _d1_failing_counts(run_dir, view)
    derived = len(counts) >= 2
    baseline = min(counts) if derived else None
    tasks = {c.get("cell_id"): c.get("task") for c in view.plan.get("cells", [])}
    out = {}
    for cell in view.cells:
        if tasks.get(cell.cell_id) != "D1" or "mutation_score" not in cell.scores:
            continue
        failing = initial_failing_tests(run_dir, cell.evidence.get("mutation_score"))
        out[cell.cell_id] = mutation_score_text(cell.scores["mutation_score"], failing, baseline, derived)
    return out
