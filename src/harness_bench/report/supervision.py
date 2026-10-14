"""SV1's report-time facts for the lean summary (ADR-0023 Amendment 2; tasks/README.md, "The supervision task").

Two sources, both read at report time and never stored:
- the `SV1-MEASURES` JSON line the hidden tests print into the cell's `oracle.log` (the correctness grader's evidence,
  `CellView.evidence["pass_at_1"]`): status_checks, early_checks, min_gap_s, finished_seen, report, reported_checks;
- the native-record check the working tree cannot make (plan row B6): a check that reads `job-run/` directly, or
  computes the elapsed time from `job-run/state.json`, leaves no line in job.py's status log. So the cell's tool
  calls (`ToolInput`, through `tool_phases.cell_trace`) are counted: those whose command runs `job.py status`, and
  those whose command or paths name `job-run` directly.

A harness with no tool-input reader, or a cell with no readable record, gives None with the reason, never 0.
`lean.build` stays pure: the CLI passes these facts in through `BatchInput.supervision`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from harness_bench import lean
from harness_bench.report import tool_phases
from harness_bench.telemetry import ToolInput
from harness_bench.views import CellView, RunView

STATUS_CALL = re.compile(r"\bjob\.py[\"']?\s+status\b")  # `python job.py status`, `python .\job.py status`
JOB_RUN = "job-run"  # the job's own folder: a command or path naming it bypasses job.py


def job_calls(calls: Sequence[ToolInput]) -> tuple[int, int]:
    """(tool calls whose command runs `job.py status`, tool calls whose command or paths name `job-run`). A compound
    command that does both counts once in each."""
    status = sum(1 for c in calls if c.command and STATUS_CALL.search(c.command))
    direct = sum(1 for c in calls if JOB_RUN in (c.command or "") or any(JOB_RUN in p for p in c.paths))
    return status, direct


def parse_measures(text: str, task: str) -> tuple[dict | None, str | None]:
    """The one `<task>-MEASURES` JSON object in an oracle log, or None with the reason."""
    prefix = f"{task}-MEASURES "
    lines = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(lines) != 1:
        return None, f"no {task}-MEASURES line in oracle.log" if not lines else f"{len(lines)} {task}-MEASURES lines"
    try:
        value = json.loads(lines[0])
    except ValueError:
        value = None
    return (value, None) if isinstance(value, dict) else (None, f"the {task}-MEASURES line is not a JSON object")


def _measures(view: RunView, cell: CellView) -> tuple[dict | None, str | None]:
    evidence = cell.evidence.get("pass_at_1")
    if not evidence or view.run_dir is None:
        score = cell.scores.get("pass_at_1")
        return None, (score.reason if score is not None and score.reason else "no oracle.log (not graded)")
    try:
        text = (view.run_dir / evidence).read_text(encoding="utf-8")
    except OSError:
        return None, "oracle.log unreadable"
    return parse_measures(text, cell.task)


def _calls(view: RunView, cell: CellView) -> tuple[int | None, int | None, str | None]:
    if cell.harness not in tool_phases.TRACE_READERS:
        return None, None, f"no tool-input reader for {cell.harness}"
    trace = (tool_phases.cell_trace(view.run_dir, view, cell, tool_phases.main_session(view, cell))
             if view.run_dir is not None else None)
    if trace is None:
        return None, None, "no native record in the archive"
    return (*job_calls(trace.calls), None)


def facts(view: RunView) -> dict[str, lean.SupervisionFacts]:
    """Every stated-requirement cell's facts (`lean.stated_tasks`), by the run's own cell id."""
    stated = lean.stated_tasks(view.plan)
    return {cell.cell_id: lean.SupervisionFacts(*_measures(view, cell), *_calls(view, cell))
            for cell in view.cells if cell.task in stated}
