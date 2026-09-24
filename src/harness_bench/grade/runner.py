"""A grading pass (ADR-0006, ADR-0007; design: Data model, Grading).

- A pass holds `grade.lock` (HB-GRD-001 when held) and writes only its own segments, one per fact, named
  by its `grading_id` (`grade-<utc>-<rand>`). It seals them all; `grading.completed` is written after the
  other facts are sealed and before the events segment is sealed, so a pass that died at any point is
  simply not completed, and views skip it.
- A grading segment of a pass that did not complete is named once, in this pass's own events segment
  (`segment.abandoned`, HB-LED-004). Nobody writes into another writer's file.
- Extractions are written once: a cell's `model_calls` and `tool_calls` are written only when no
  completed pass already holds the cell's `extraction_id` (the normaliser build hash).
- Only archived cells are graded, each exactly once per pass, from the archive alone.
- Non-integer values are decimal strings at the catalog's scale (no floats in the ledger).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import config, ledger, oslock, profiles, views
from harness_bench.grade import correctness, cost
from harness_bench.plan import file_hash, load_confirmed, task_version_hash
from harness_bench.telemetry import Extraction, normalize

PASS_FACTS = ("events", "model_calls", "tool_calls", "scores")
METRICS = ("pass_at_1", "partial_credit", "cost_usd")  # the phase-1 graders' metrics

__all__ = ["METRICS", "PASS_FACTS", "PassResult", "file_hash", "grader_build", "run_pass"]


@dataclass
class PassResult:
    grading_id: str
    heads: dict[str, str]  # fact -> sealed head hash
    cells_graded: int
    abandoned: list[str]  # "<fact>/<segment_id>" named by this pass

    def summary(self) -> dict:
        return {"grading_id": self.grading_id, "heads": self.heads, "cells_graded": self.cells_graded}


def grader_build() -> str:
    h = hashlib.sha256()
    for f in sorted(Path(__file__).parent.glob("*.py")):
        h.update(f.name.encode() + b"\0" + f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def _scales(catalog: dict) -> dict[str, int]:
    return {m["id"]: m["scale"] for area in catalog["areas"].values() for m in area.get("metrics") or [] if "scale" in m}


def _abandoned(run_dir: Path, done: set[str], named: set[tuple[str, str]]) -> list[tuple[str, ledger.SegmentReport]]:
    out = []
    for fact in PASS_FACTS:
        for path in views.segment_paths(run_dir, fact):
            sid = path.stem
            if sid.startswith(views.GRADE_PREFIX) and sid not in done and (fact, sid) not in named:
                out.append((fact, ledger.verify_segment(path)))
    return out


def run_pass(run_dir: Path, root: Path) -> PassResult:
    plan = load_confirmed(run_dir)
    with oslock.RunLock.acquire(run_dir / "grade.lock", "HB-GRD-001"):
        return _Pass(run_dir, root, plan).run()


class _Pass:
    def __init__(self, run_dir: Path, root: Path, plan: dict) -> None:
        self.run_dir, self.root, self.plan = run_dir, root, plan
        self.grading_id = f"{views.GRADE_PREFIX}{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}-{secrets.token_hex(3)}"
        self.catalog = config.load_yaml(root / "bench" / "metrics.yaml")
        self.scales = _scales(self.catalog)
        self.extraction = normalize.extraction_id()
        prices_path = root / "bench" / "prices.yaml"
        self.prices_ok = file_hash(prices_path) == plan["price_list_hash"]
        self.prices = config.load_yaml(prices_path) if self.prices_ok else {}
        self.writers: dict[str, ledger.SegmentWriter] = {}

    def append(self, fact: str, record: dict) -> None:
        self.writers[fact].append(ledger.stamp(record))

    def run(self) -> PassResult:
        done = views.completed_passes(self.run_dir)
        events = views.rows(self.run_dir, "events")
        named = {(e["fact"], e["segment_id"]) for e in events if e["kind"] == "segment.abandoned"}
        abandoned = _abandoned(self.run_dir, done, named)
        held = {(r["cell_id"], r["extraction_id"]) for fact in ("model_calls", "tool_calls") for r in views.rows(self.run_dir, fact)}
        usage: dict[str, list[normalize.TurnUsage]] = {}
        for r in views.rows(self.run_dir, "turn_usage"):
            usage.setdefault(r["cell_id"], []).append(normalize.TurnUsage(r["model"], r["uncached_input"], r["cache_read"],
                                                                           r["cache_write"], r["output"], r["reasoning"]))
        archived = {e["cell_id"]: e["archive_attempt"] for e in events if e["kind"] == "cell.archived"}
        sessions = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
        try:
            for fact in PASS_FACTS:
                self.writers[fact] = ledger.SegmentWriter.create(self.run_dir / fact, self.grading_id)
            for fact, report in abandoned:
                self.append("events", {"kind": "segment.abandoned", "code": "HB-LED-004", "fact": fact, "segment_id": report.segment_id,
                                       "line_count": report.lines, "head_hash": report.head_hash, "error": report.error})
            self.append("events", {"kind": "grading.started", "grading_id": self.grading_id, "catalog_version": str(self.catalog["version"]),
                                   "grader_build": grader_build(), "extraction_id": self.extraction})
            graded = 0
            for cell in sorted(self.plan["cells"], key=lambda c: c["cell_id"]):
                if cell["cell_id"] in archived:
                    self._grade_cell(cell, archived[cell["cell_id"]], sessions.get(cell["cell_id"], ""), held, usage)
                    graded += 1
            heads = {fact: self.writers[fact].seal() for fact in PASS_FACTS if fact != "events"}
            self.append("events", {"kind": "grading.completed", "grading_id": self.grading_id, "cells_graded": graded})
            heads["events"] = self.writers["events"].seal()
        finally:
            for w in self.writers.values():
                w.close()
        return PassResult(self.grading_id, heads, graded, [f"{fact}/{r.segment_id}" for fact, r in abandoned])

    def _extract(self, cell: dict, folder: Path, session_id: str, held: set) -> tuple[Extraction | None, str | None]:
        records = profiles.find_records(folder / "home", self.plan["profiles"][cell["harness"]]["record_glob"], session_id)
        if len(records) != 1:
            return None, "no native record for the session" if not records else "more than one native record for the session"
        ex = profiles.READERS[cell["harness"]](records[0])
        cid = cell["cell_id"]
        if (cid, self.extraction) not in held:
            for row in normalize.model_call_rows(self.plan["run_id"], cid, session_id, ex, self.extraction):
                self.append("model_calls", row)
            for row in normalize.tool_call_rows(self.plan["run_id"], cid, session_id, ex, self.extraction):
                self.append("tool_calls", row)
        return ex, None

    def _grade_cell(self, cell: dict, attempt: int, session_id: str, held: set, usage: dict) -> None:
        cid = cell["cell_id"]
        folder = self.run_dir / "archive" / cid / f"attempt-{attempt}"
        out_dir = self.run_dir / "grading" / self.grading_id / cid
        out_dir.mkdir(parents=True)
        ex, missing = self._extract(cell, folder, session_id, held)
        task_dir = self.root / "tasks" / cell["task"]
        if task_version_hash(task_dir) != cell["task_version"]:  # the hidden tests must be the ones the plan named
            c = correctness.Result(None, None, "task changed since the plan (version hash mismatch)", "")
        else:
            oracle = config.load_yaml(task_dir / "task.yaml").get("oracle") or {}
            c = correctness.grade(folder / "ws", task_dir, oracle, out_dir, self.run_dir, self.plan["parameters"]["grading_step_timeout"])
        self._score(cell, attempt, "pass_at_1", c.passed, c.reason, c.evidence)
        self._score(cell, attempt, "partial_credit", c.partial_credit, c.reason, c.evidence)
        source = self.plan["profiles"][cell["harness"]]["usage_source"]
        if not self.prices_ok:
            value, reason, evidence = None, "price list changed since the plan (hash mismatch)", ""
        elif source == "native_record" and ex is None:
            value, reason, evidence = None, missing, ""
        else:
            totals = normalize.totals(source, ex or Extraction(), usage.get(cid, []))
            value, reason, evidence = cost.cost_usd(totals, self.prices, self.plan["created_at"][:10])
        self._score(cell, attempt, "cost_usd", value, reason, evidence)

    def _score(self, cell: dict, attempt: int, metric: str, value: int | Decimal | None, reason: str | None, evidence: str) -> None:
        if isinstance(value, Decimal):
            value = f"{value:.{self.scales[metric]}f}"
        self.append("scores", {"kind": "score", "run_id": self.plan["run_id"], "grading_id": self.grading_id, "cell_id": cell["cell_id"],
                               "metric_id": metric, "value": value, "reason": reason, "evidence": evidence,
                               "archive_attempt": attempt, "extraction_id": self.extraction})
