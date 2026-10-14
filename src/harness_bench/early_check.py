"""`bench status <run> --check-ended`: an early, read-only validity check over the cells a run has ended so far.

The grading pass judges validity only at the end of `bench run`, so a misconfigured run (a setting the harness does not
serve, an out-of-profile tool) was found only after every cell had run. This check answers the same question after the
first cells end, while the run is live:

- An ended cell is one the engine archived (`cell.archived`), the set a grading pass reads.
- Its native record is read by `runner.read_record`, the grading pass's own reader (the archived attempt, the session's
  sub-agent records, the plan's frozen profile).
- It is judged by `views._cell_view`, the one definition every report reads (HB-VAL-002 model, HB-VAL-008 out-of-profile
  tool, HB-VAL-010 served effort or context, HB-VAL-011 a setting no source records, in the view's priority order). The
  rows reach it in memory under a pass id that is never written, so no rule is restated here.
- Nothing is written: no ledger segment, event, fact, lock or grading folder.

The result is provisional: the grading pass at the end of the run is the record.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from harness_bench import views
from harness_bench.grade import runner
from harness_bench.plan import load_confirmed
from harness_bench.telemetry import normalize

SCHEMA = "bench-early-check/1"
MISMATCH_CODES = ("HB-VAL-002", "HB-VAL-008", "HB-VAL-010")  # the codes that stop a misconfigured run early
WARNING_CODES = ("HB-VAL-009", "HB-VAL-011")  # shown on the cell's line; they do not change its validity
_PASS_ID = "early-check"  # the in-memory pass id; never a segment name (a real pass is `grade-...`)
_SCORE = "early_check"  # the one in-memory score row that names the extraction for `_cell_view`


@dataclass(frozen=True)
class CellCheck:
    cell_id: str
    label: str
    validity: str
    code: str | None
    warnings: tuple[tuple[str, str], ...]  # (code, message), WARNING_CODES only


@dataclass(frozen=True)
class EarlyCheck:
    run_id: str
    planned: int
    cells: tuple[CellCheck, ...]  # the ended cells, in plan order

    @property
    def totals(self) -> dict[str, int]:
        """Ended cells per validity code, `ok` for a cell with none (the grading pass's per-cell count)."""
        return dict(Counter(c.code or "ok" for c in self.cells))

    @property
    def mismatch(self) -> bool:
        return any(c.code in MISMATCH_CODES for c in self.cells)


def _judge(plan: dict, cell: dict, events: list[dict], usage: list[dict], folder: Path, session_id: str,
           extraction: str) -> views.CellView:
    read = runner.read_record(plan, cell, folder, session_id, extraction)
    cid = cell["cell_id"]
    completed = {"kind": "grading.completed", "grading_id": _PASS_ID,
                 "unreadable_records": {cid: read.unreadable} if read.unreadable is not None else {},
                 "tools_advertised": {cid: read.ex.tools_advertised}
                 if read.ex is not None and read.ex.tools_advertised is not None else {}}
    facts = {"events": [*events, completed], "model_calls": read.model_rows, "tool_calls": read.tool_rows,
             "turn_usage": usage, "served": read.streams.get("served", []),
             "scores": [{"grading_id": _PASS_ID, "cell_id": cid, "metric_id": _SCORE, "extraction_id": extraction,
                         "value": None, "reason": "early check"}]}
    return views._cell_view(plan, cell, facts, _PASS_ID)


def check(run_dir: Path) -> EarlyCheck:
    """Judge every archived cell of the run as the grading pass would, in memory."""
    plan = load_confirmed(run_dir)
    events = views.rows(run_dir, "events")
    usage = views.rows(run_dir, "turn_usage")
    archived = {e["cell_id"]: e["archive_attempt"] for e in events if e["kind"] == "cell.archived"}
    sessions = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
    extraction = normalize.extraction_id()
    out = []
    for cell in plan["cells"]:
        cid = cell["cell_id"]
        if cid not in archived:
            continue
        view = _judge(plan, cell, [e for e in events if e.get("cell_id") == cid], [r for r in usage if r["cell_id"] == cid],
                      run_dir / "archive" / cid / f"attempt-{archived[cid]}", sessions.get(cid, ""), extraction)
        out.append(CellCheck(cid, view.label, view.validity, view.validity_code,
                             tuple((w.code, w.message) for w in view.warnings if w.code in WARNING_CODES)))
    return EarlyCheck(plan["run_id"], len(plan["cells"]), tuple(out))


def _line(c: CellCheck) -> str:
    parts = [f"{c.code} {c.validity}"] if c.code else ([] if c.validity == "valid" else [c.validity])
    parts += [f"{code} {message}" for code, message in c.warnings]
    return f"{c.label}: {'; '.join(parts) or 'ok'}"


def text(result: EarlyCheck) -> str:
    totals = result.totals
    order = (["ok"] if "ok" in totals else []) + sorted(k for k in totals if k != "ok")
    summary = ", ".join(f"{k} {totals[k]}" for k in order) or "none ended yet"
    return "".join(f"{_line(c)}\n" for c in result.cells) + f"ended {len(result.cells)} of {result.planned} cells: {summary}\n"


def to_json(result: EarlyCheck) -> str:
    return json.dumps({"schema": SCHEMA, "run_id": result.run_id, "planned": result.planned, "ended": len(result.cells),
                       "cells": [{"cell_id": c.cell_id, "label": c.label, "validity": c.validity, "code": c.code,
                                  "warnings": [{"code": code, "message": m} for code, m in c.warnings]}
                                 for c in result.cells],
                       "totals": result.totals, "mismatch": result.mismatch}, sort_keys=True, separators=(",", ":"))
