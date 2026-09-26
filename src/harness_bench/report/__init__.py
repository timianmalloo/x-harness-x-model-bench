"""Reports over the views (design: UI & interaction design): the CLI table and the static HTML page.

The formatters here are the one definition of how a value reads on every surface. A value that was not
measured reads `NA (<reason>)`, never 0, 0% or $0 (US-27). Numbers carry their unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

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


@dataclass(frozen=True)
class _Baseline:
    low: int
    high: int
    flake_band: int
    note: str


def _d1_baseline(root: Path | None) -> _Baseline | None:
    if root is None:
        return None
    band = ((_load_yaml(root / "bench" / "task-baselines.yaml").get("tasks") or {}).get("D1") or {}).get(
        "initial_failing_tests") or {}
    try:
        return _Baseline(int(band["low"]), int(band["high"]), int(band["flake_band"]), str(band["note"]))
    except (KeyError, TypeError, ValueError):
        return None


def has_d1_cell(plan: dict) -> bool:
    return any(c.get("task") == "D1" for c in plan.get("cells", []))


def disclosure_rows(root: Path | None, plan: dict) -> list[tuple[str, str]]:
    """Header rows: the gate allowance always, the D1 red baseline only when the run has a D1 cell."""
    rows = [("Gate allowance", gate_allowance(root))]
    if not has_d1_cell(plan):
        return rows
    base = _d1_baseline(root)
    if base is None:
        rows.append(("D1 baseline red tests", "not recorded"))
    else:
        rows.append(("D1 baseline red tests", f"{base.low}-{base.high} ({base.note})"))
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


def mutation_score_text(measure: Measure, failing: str, high: int | None, band: int | None) -> str:
    """The score with its failing-test count beside it. Above high + flake_band the score is not shown."""
    score = na(measure) if measure.value is None else f"{Decimal(measure.value):.4f}"
    try:
        n = int(failing)
    except (TypeError, ValueError):
        return f"{score} ({failing})"
    if high is not None and band is not None:
        limit = high + band
        if n > limit:
            return "red tests added"
    return f"{score} ({n})"


def d1_mutation_values(root: Path | None, run_dir: Path | None, view) -> dict[str, str]:
    """cell_id -> the D1 mutation_score as the report shows it."""
    base = _d1_baseline(root)
    tasks = {c.get("cell_id"): c.get("task") for c in view.plan.get("cells", [])}
    high = base.high if base else None
    band = base.flake_band if base else None
    out = {}
    for cell in view.cells:
        if tasks.get(cell.cell_id) != "D1" or "mutation_score" not in cell.scores:
            continue
        failing = initial_failing_tests(run_dir, cell.evidence.get("mutation_score"))
        out[cell.cell_id] = mutation_score_text(cell.scores["mutation_score"], failing, high, band)
    return out
