"""A grading pass (ADR-0006, ADR-0007; design: Data model, Grading; design phase3-graders: the dispatch).

- A pass holds `grade.lock` (HB-GRD-001 when held) and writes only its own segments, one per fact, named
  by its `grading_id` (`grade-<utc>-<rand>`). It seals them all; `grading.completed` is written after the
  other facts are sealed and before the events segment is sealed, so a pass that died at any point is
  simply not completed, and views skip it. `grading.completed` records `heads` (fact -> sealed head) for
  the other facts, never events (a segment cannot carry its own head), so `bench verify` can tie them to it.
  It also records `unreadable_records` (cell_id -> reason, R-15): each graded cell whose native record was
  missing, ambiguous, or unreadable as a whole (`normalize.record_unreadable`). The pass's reading is a
  property of the pass, so it rides on the pass's own summary row: no new event kind, and none per cell.
- A grading segment of a pass that did not complete is named once, in this pass's own events segment
  (`segment.abandoned`, HB-LED-004). Nobody writes into another writer's file.
- Extractions are written once: a cell's `model_calls` and `tool_calls` are written only when no
  completed pass already holds the cell's `extraction_id` (the normaliser build hash).
- Only archived cells are graded, each exactly once per pass, from the archive alone.
- The dispatch: each cell is graded by its task's de-duplicated `graders` list, in catalog order, through `GRADERS`.
  The applicable set is every `kind: score` catalog metric of those graders, and each gets exactly one row: the
  grader's Score; NA `not built` (an unregistered grader, or a metric it did not return); NA HB-GRD-003 (it raised,
  or returned a malformed output; the traceback is the evidence); or NA `task changed since the plan` (a grader that
  reads the task, when the task is not the plan's version). A metric of a grader the task does not name has no row.
- GradedOncePerPass is enforced here: before `grading.completed`, every applicable (cell, metric) row must have been
  written exactly once and no grader may have returned a key outside its applicable set, else HB-GRD-004 and the pass
  is never completed.
- Non-integer values are decimal strings at the catalog's scale (no floats in the ledger).
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import secrets
import sys
import time
import traceback
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from harness_bench import config, ledger, oslock, profiles, tools, views
from harness_bench.errors import BenchError
from harness_bench.grade import (
    CellInput,
    GraderFn,
    Score,
    clarify,
    correctness,
    cost,
    drift,
    judge,
    process,
)
from harness_bench.plan import file_hash, load_confirmed, task_version_hash, tree_hash
from harness_bench.telemetry import Extraction, normalize

logger = logging.getLogger("harness_bench.grade")
PASS_FACTS = ("events", "model_calls", "tool_calls", "scores", "verdict_uses")  # verdict_uses: ADR-0006 Amendment 3
NOT_BUILT = "not built"
TASK_CHANGED = "task changed since the plan (version hash mismatch)"
TASK_FREE = frozenset({"cost", "process"})  # graders that never read the task, so they grade a cell whose task changed

__all__ = ["GRADERS", "PASS_FACTS", "PassResult", "applicable", "file_hash", "grader_build", "run_pass"]


# Pattern: Strategy via a registry (Pluggable Selector). One line per built grader; an unregistered one is `not built`.
GRADERS: dict[str, GraderFn] = {"correctness": correctness.grade_cell, "cost": cost.grade_cell, "judge": judge.grade_cell}


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


GRADERS["process"] = process.grade_cell  # GR-PROC p1-p3
GRADERS["clarify"] = clarify.grade_cell  # GR-CLAR l1
GRADERS["drift"] = drift.grade_cell  # GR-CODE c3
TOOL_TIMEOUT = 30  # seconds per version probe (R-59 c4)
NOT_RECORDED = "not recorded"
# Tools a grader runs beyond python and dotnet: key -> the command that prints its version (its last stdout line).
# simplify: empty until GR-CODE c6 pins Stryker.NET; its spike names the command (`dotnet-stryker`). Upgrade trigger: that pin.
PINNED_TOOLS: dict[str, list[str]] = {}


def catalog_hash(root: Path) -> str:
    """R-59 c1: plan.tree_hash over bench/metrics.yaml and every file under bench/rubrics/, paths relative to bench/."""
    bench = root / "bench"
    rubrics = [p for p in (bench / "rubrics").rglob("*") if p.is_file()] if (bench / "rubrics").is_dir() else []
    return tree_hash(bench, [bench / "metrics.yaml", *rubrics])


def _version(argv: list[str], cwd: Path) -> str:
    """The tool's version, measured now by tools.measured_version (procs' allowlisted caller); `not recorded` otherwise."""
    return tools.measured_version(argv, cwd, TOOL_TIMEOUT) or NOT_RECORDED


def tool_versions(root: Path, plan: Mapping) -> dict[str, str]:
    """R-59 c4: each tool the pass's graders run, measured once at pass start (never read from a pin, never guessed).
    dotnet is measured once per dotnet task in the plan, in its workspace, where global.json selects the SDK (D&P 9)."""
    out = {"python": sys.version.split()[0]}
    for task in sorted({c["task"] for c in plan["cells"]}):
        spec = root / "tasks" / task / "task.yaml"
        if spec.is_file() and (config.load_yaml(spec).get("oracle") or {}).get("runner") == "dotnet":
            out[f"dotnet[{task}]"] = _version(["dotnet", "--version"], root / "tasks" / task / "workspace")
    for key, argv in sorted(PINNED_TOOLS.items()):
        out[key] = _version(argv, root)
    return out


def applicable(catalog: dict, graders: list[str]) -> dict[str, dict[str, dict]]:
    """grader -> {metric id: catalog entry}: the `kind: score` metrics of `graders`, each grader once, in catalog order."""
    out: dict[str, dict[str, dict]] = {}
    for area in catalog["areas"].values():
        for m in area.get("metrics") or []:
            if m["grader"] in graders and m["kind"] == "score":
                out.setdefault(m["grader"], {})[m["id"]] = m
    return out


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


def run_pass(run_dir: Path, root: Path, judging: Mapping[str, GraderFn] | None = None) -> PassResult:
    """One grading pass. `judging` replaces registered graders for this pass only (design phase3-gateway-judges
    section 6): the in-run pass passes `judge.IN_RUN`, `bench grade --allow-model-calls` passes `judge.calling(...)`,
    and a plain `bench grade` passes nothing (the judge reads the verdict store only)."""
    plan = load_confirmed(run_dir)
    with oslock.RunLock.acquire(run_dir / "grade.lock", "HB-GRD-001"):
        return _Pass(run_dir, root, plan, judging or {}).run()


class _Pass:
    def __init__(self, run_dir: Path, root: Path, plan: dict, judging: Mapping[str, GraderFn]) -> None:
        self.run_dir, self.root, self.plan = run_dir, root, plan
        self.graders = {**GRADERS, **judging}
        self.grading_id = f"{views.GRADE_PREFIX}{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}-{secrets.token_hex(3)}"
        self.catalog = config.load_yaml(root / "bench" / "metrics.yaml")
        self.scales = _scales(self.catalog)
        self.extraction = normalize.extraction_id()
        prices_path = root / "bench" / "prices.yaml"
        self.prices_ok = file_hash(prices_path) == plan["price_list_hash"]
        self.prices = config.load_yaml(prices_path) if self.prices_ok else {}
        self.writers: dict[str, ledger.SegmentWriter] = {}
        self.unreadable: dict[str, str] = {}  # cell_id -> why its native record could not be read (R-15)
        self.advertised: dict[str, list[str]] = {}  # cell_id -> the tool ids its record advertised, when read (R-45 item 2)
        self.wanted: set[tuple[str, str]] = set()  # the applicable (cell, metric) keys of this pass
        self.written: Counter[tuple[str, str]] = Counter()  # score rows written per (cell, metric)
        self.outside: set[tuple[str, str, str]] = set()  # (cell, grader, key) a grader returned outside its applicable set

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
            usage.setdefault(r["cell_id"], []).append(views.turn_usage(r))
        archived = {e["cell_id"]: e["archive_attempt"] for e in events if e["kind"] == "cell.archived"}
        sessions = {e["cell_id"]: e["session_id"] for e in events if e["kind"] == "attempt.session_opened"}
        try:
            for fact in PASS_FACTS:
                self.writers[fact] = ledger.SegmentWriter.create(self.run_dir / fact, self.grading_id)
            for fact, report in abandoned:
                self.append("events", {"kind": "segment.abandoned", "code": "HB-LED-004", "fact": fact, "segment_id": report.segment_id,
                                       "line_count": report.lines, "head_hash": report.head_hash, "error": report.error})
            self.append("events", {"kind": "grading.started", "grading_id": self.grading_id, "catalog_version": str(self.catalog["version"]),
                                   "grader_build": grader_build(), "extraction_id": self.extraction,
                                   "catalog_hash": catalog_hash(self.root),  # R-59 c1
                                   "tool_versions": tool_versions(self.root, self.plan)})  # R-59 c4
            graded = 0
            for cell in sorted(self.plan["cells"], key=lambda c: c["cell_id"]):
                if cell["cell_id"] in archived:
                    cell_events = tuple(e for e in events if e.get("cell_id") == cell["cell_id"])
                    self._grade_cell(cell, archived[cell["cell_id"]], sessions.get(cell["cell_id"], ""), held, usage, cell_events)
                    graded += 1
            self._check_complete()
            heads = {fact: self.writers[fact].seal() for fact in PASS_FACTS if fact != "events"}
            self.append("events", {"kind": "grading.completed", "grading_id": self.grading_id, "cells_graded": graded,
                                   "heads": dict(heads),  # ruling R-2: bench verify checks each against its seal
                                   "unreadable_records": dict(sorted(self.unreadable.items())),  # R-15
                                   "tools_advertised": dict(sorted(self.advertised.items()))})  # R-45 item 2
            heads["events"] = self.writers["events"].seal()
        finally:
            for w in self.writers.values():
                w.close()
        return PassResult(self.grading_id, heads, graded, [f"{fact}/{r.segment_id}" for fact, r in abandoned])

    def _extract(self, cell: dict, folder: Path, session_id: str, held: set) -> tuple[Extraction | None, str | None, list, list]:
        """(the record as read, why there is none, its model-call rows, its tool-call rows); rows unstamped."""
        records = profiles.find_records(folder / "home", self.plan["profiles"][cell["harness"]]["record_glob"], session_id)
        if len(records) != 1:
            return None, "no native record for the session" if not records else "more than one native record for the session", [], []
        ex = profiles.READERS[cell["harness"]](records[0])
        cid = cell["cell_id"]
        model_rows = normalize.model_call_rows(self.plan["run_id"], cid, session_id, ex, self.extraction)
        tool_rows = normalize.tool_call_rows(self.plan["run_id"], cid, session_id, ex, self.extraction)
        if (cid, self.extraction) not in held:
            for row in model_rows:
                self.append("model_calls", row)
            for row in tool_rows:
                self.append("tool_calls", row)
        return ex, None, model_rows, tool_rows

    def _grade_cell(self, cell: dict, attempt: int, session_id: str, held: set, usage: dict, events: tuple) -> None:
        cid = cell["cell_id"]
        folder = self.run_dir / "archive" / cid / f"attempt-{attempt}"
        out_dir = self.run_dir / "grading" / self.grading_id / cid
        out_dir.mkdir(parents=True)
        ex, missing, model_rows, tool_rows = self._extract(cell, folder, session_id, held)
        unreadable = missing if ex is None else normalize.record_unreadable(ex)
        if unreadable is not None:
            self.unreadable[cid] = unreadable
        if ex is not None and ex.tools_advertised is not None:
            self.advertised[cid] = ex.tools_advertised
        task_dir = self.root / "tasks" / cell["task"]
        current = task_version_hash(task_dir) == cell["task_version"]  # the hidden tests must be the ones the plan named
        task = config.load_yaml(task_dir / "task.yaml") if current else {}
        # The plan freezes no `graders` yet (seam S-1), so a changed task.yaml cannot be trusted: every catalog grader
        # applies, and each one that reads the task is NA `task changed` (design: Data model, the fallback).
        names = (task.get("graders") or []) if current else [m["grader"] for a in self.catalog["areas"].values() for m in a["metrics"]]
        base = CellInput(run_dir=self.run_dir, root=self.root, plan=self.plan, cell=cell, task=task, task_dir=task_dir,
                         archive=folder, out_dir=out_dir, events=events, record_reason=unreadable, model_calls=tuple(model_rows),
                         tool_calls=tuple(tool_rows), turn_usage=tuple(usage.get(cid, [])), metrics={},
                         allow_model_calls=False,  # R-58 DR-2: only `judge.calling` (--allow-model-calls) sets it
                         extraction=ex, prices=self.prices if self.prices_ok else None, emit=self.append)
        for grader, metrics in applicable(self.catalog, names).items():
            scores = self._run_grader(grader, dataclasses.replace(base, out_dir=out_dir / grader, metrics=metrics), current)
            self.wanted.update((cid, m) for m in metrics)
            for metric in sorted(metrics):
                self._score(cell, attempt, metric, scores[metric])

    def _run_grader(self, grader: str, inp: CellInput, current: bool) -> dict[str, Score]:
        """One Score for each applicable metric of `grader` (design: the dispatch, step 3)."""
        if grader not in TASK_FREE and not current:
            return dict.fromkeys(inp.metrics, Score(None, TASK_CHANGED))
        fn = self.graders.get(grader)
        if fn is None:
            return dict.fromkeys(inp.metrics, Score(None, NOT_BUILT))
        inp.out_dir.mkdir()
        try:
            out = fn(inp)
            if not isinstance(out, Mapping):
                raise TypeError(f"grader output is a {type(out).__name__}, not a mapping")
            for metric in inp.metrics.keys() & out.keys():
                if not isinstance(out[metric], Score):
                    raise TypeError(f"{metric}: {type(out[metric]).__name__} is not a Score")
                if isinstance(out[metric].value, Decimal) and metric not in self.scales:
                    raise ValueError(f"{metric}: a Decimal for a metric with no catalog scale")
        except Exception as exc:  # any grader failure is NA for its metrics; the pass continues (F3)
            logger.exception("grade.grader_failed %s", {"grading_id": self.grading_id, "cell_id": inp.cell["cell_id"], "grader": grader})
            log = inp.out_dir / "error.log"
            log.write_text(traceback.format_exc(), encoding="utf-8")
            evidence = log.relative_to(self.run_dir).as_posix()
            return dict.fromkeys(inp.metrics, Score(None, f"HB-GRD-003 grader {grader} failed: {type(exc).__name__}", evidence))
        self.outside.update((inp.cell["cell_id"], grader, k) for k in out.keys() - inp.metrics.keys())
        return {m: out[m] if m in out else Score(None, NOT_BUILT) for m in inp.metrics}

    def _check_complete(self) -> None:
        """GradedOncePerPass (design, D&P 2 and N2): every applicable (cell, metric) row written exactly once, none extra."""
        wrong = sorted(k for k in self.wanted | self.written.keys() if self.written[k] != 1 or k not in self.wanted)
        if wrong or self.outside:
            raise BenchError("HB-GRD-004", f"pass {self.grading_id} not completed: (cell, metric) rows not written exactly once "
                                           f"{wrong}; keys outside the applicable set {sorted(self.outside)}")

    def _score(self, cell: dict, attempt: int, metric: str, score: Score) -> None:
        value = score.value
        if isinstance(value, Decimal):
            value = f"{value:.{self.scales[metric]}f}"
        self.append("scores", {"kind": "score", "run_id": self.plan["run_id"], "grading_id": self.grading_id, "cell_id": cell["cell_id"],
                               "metric_id": metric, "value": value, "reason": score.reason, "evidence": score.evidence,
                               "archive_attempt": attempt, "extraction_id": self.extraction})
        self.written[(cell["cell_id"], metric)] += 1
