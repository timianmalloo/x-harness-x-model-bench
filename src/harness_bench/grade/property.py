"""Property grader (ADR-0018, ADR-0019): property_check_pass and the property-tagged metrics.

Design: docs/design/eval-property-grader.md (W1-F rev 3); seams: docs/design/eval-seam-contracts.md (W0 rev 6.9).
This module holds the pure core first (F2): `at_scale`, `check_segment`, the result-line validator, the ordered
outcome table `_classify` (W0 section 3, rows 1-7: the first match decides) and the scoring of an accepted run.
F3a adds the check runner (the handshake of design 5.3) and `grade_cell` (design 5.2); the probe host and
`bench_check` (F3b) is its own module, run only in the check process.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from harness_bench import config, host, procs
from harness_bench.grade import CellInput, Score, _changes, _env, correctness
from harness_bench.plan import tree_hash

__all__ = ["Classification", "Facts", "at_scale", "check_seed", "check_segment", "grade_cell", "parse_result", "run_check",
           "score_run"]

MAX_RESULT_BYTES = 64 * 1024
ACK = b"\x06"
BENCH_CHECK = Path(__file__).with_name("bench_check.py")  # copied into every check copy
PROPERTY_SUSPEND_GAP_S = 60.0  # the host-sleep gap of a phase span (design 5.2 step 3)
_STORE = 4 * MAX_RESULT_BYTES  # stdout kept for the document count; beyond it bytes are counted, never stored
_ENTRY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.py")
_CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_APP_KINDS = frozenset({"callable", "wsgi"})
PROBE_OUTCOMES = frozenset({"blocked", "exploited", "timeout"})
DELIVERABLES = frozenset({"ran", "did not build", "did not start"})


@dataclass(frozen=True)
class Classification:
    row: int  # W0 section 3's row (1-7); every precedence test asserts it
    code: str | None  # HB-CHK-00n, or None for rows 6 and 7
    reason: str | None  # the NA reason (rows 1-5) or the deliverable text (row 6)


@dataclass(frozen=True)
class Facts:
    """What `_classify` reads. The defaults are an honest, clean run."""

    tests_suspended: bool = False
    check_suspended: bool = False
    bound_fired: bool = False
    hash_before: str = "h"
    hash_after: str = "h"
    alone_at_arrival: bool = True  # the first-byte job view was exactly the check
    documents: int = 1
    trailing_bytes: int = 0
    exit_before_line: bool = False  # exit_ft <= first_byte_ft
    has_line: bool = True
    exit_code: int | None = 0
    line_valid: bool = True  # the row-5 verdict of `parse_result`
    deliverable: str = "ran"


_DEVICES = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$",
                      *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10)),
                      "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"})


def check_segment(kind: str, name: str, rx: re.Pattern[str]) -> None:
    """Refuse a name that cannot be one safe path segment on Windows (W0 rev 6 R6-2, rev 6.1; callers: this module's
    `cases.json` writer, X-E, X-C). Raises ValueError naming the kind, the name and the rule broken."""
    if not rx.fullmatch(name):
        raise ValueError(f"{kind} {name!r}: does not match {rx.pattern}")
    if ":" in name or name.endswith((".", " ")):
        raise ValueError(f"{kind} {name!r}: contains ':' or ends in '.' or a space")
    if name.split(".")[0].rstrip(" ").casefold() in _DEVICES:
        raise ValueError(f"{kind} {name!r}: its stem is a Windows device name")


def at_scale(value, scale: int | None):
    """The one normaliser (W0 section 2). `scale` None: a JSON int (bool refused). Else a Decimal quantised half-even,
    or, from a check, a string with exactly `scale` decimals; `"1.0"`, `1` and `1.0` are refused."""
    if scale is None:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise ValueError(f"at_scale: {value!r} is not a JSON int")
    if isinstance(value, Decimal):
        return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_EVEN)
    if isinstance(value, str) and re.fullmatch(rf"-?\d+\.\d{{{scale}}}", value):
        return Decimal(value)
    raise ValueError(f"at_scale: {value!r} is not a string with exactly {scale} decimals")


def parse_result(line: bytes, declared: list[str], allowed_measures: frozenset[str], scales: dict[str, int | None]) -> dict:
    """The check's one line as a document, or ValueError naming what is wrong (outcome row 5, HB-CHK-001)."""
    raw = line.removesuffix(b"\n")
    if len(raw) > MAX_RESULT_BYTES:
        raise ValueError(f"result line over {MAX_RESULT_BYTES} bytes")
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ValueError("result line is not JSON") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema", "deliverable", "cases", "measures"}:
        raise ValueError("result line is not the four-key document")
    if doc["schema"] != "bench-check-result/1":
        raise ValueError(f"unknown schema {doc['schema']!r}")
    if doc["deliverable"] not in DELIVERABLES:
        raise ValueError(f"deliverable {doc['deliverable']!r} outside its set")
    cases = doc["cases"]
    if not isinstance(cases, list):
        raise ValueError("cases is not a list")  # noqa: TRY004 - one error type for every malformed shape
    if doc["deliverable"] != "ran":
        if cases:
            raise ValueError("cases must be empty unless the deliverable ran")
    else:
        for c in cases:
            ok = (isinstance(c, dict) and set(c) == {"id", "outcome", "duration_ms"} and c["outcome"] in PROBE_OUTCOMES
                  and isinstance(c["duration_ms"], int) and not isinstance(c["duration_ms"], bool) and c["duration_ms"] >= 0)
            if not ok:
                raise ValueError(f"malformed case {c!r}")
        ids = [c["id"] for c in cases]
        if sorted(ids, key=str) != sorted(declared):
            raise ValueError(f"case ids {ids} are not the declared {declared}, each exactly once")
    measures = doc["measures"]
    if not isinstance(measures, dict) or not measures.keys() <= allowed_measures:
        raise ValueError(f"measures keys outside the non-derivable set {sorted(allowed_measures)}")
    for key, value in measures.items():
        at_scale(value, scales.get(key))
    return doc


def _classify(facts: Facts) -> Classification:
    """W0 section 3's seven rows as an ordered table: the first that holds decides (not a handler chain)."""
    if facts.tests_suspended or facts.check_suspended:
        return Classification(1, "HB-CHK-004", "host suspended")
    if facts.bound_fired:
        return Classification(2, "HB-CHK-003", "check exceeded its bound")
    if facts.hash_after != facts.hash_before:
        return Classification(3, "HB-CHK-002", "invalid (check tampered)")
    expected_exit = 0 if (facts.line_valid and facts.alone_at_arrival) else 3  # accepted -> acknowledged -> 0; refused -> 3
    if (not facts.alone_at_arrival or facts.documents != 1 or facts.trailing_bytes > 0 or facts.exit_before_line
            or not facts.has_line or facts.exit_code != expected_exit):
        return Classification(4, "HB-CHK-002", "invalid (check tampered)")
    if not facts.line_valid:
        return Classification(5, "HB-CHK-001", "check output invalid")
    if facts.deliverable in ("did not build", "did not start"):
        return Classification(6, None, facts.deliverable)
    return Classification(7, None, None)


def score_run(cls: Classification, hidden_tests: Score, outcomes: list[str]) -> dict[str, Score]:
    """The narrowed security metrics of one classified run (design 5.7). Rows 1-5: NA for every metric, whatever the
    hidden tests said. Row 6: the primary is a measured 0. Row 7: Kleene logic over the hidden tests and the cases."""
    if cls.row <= 5:
        na = Score(None, cls.reason)
        return {"property_check_pass": na, "exploit_probes_blocked": na}
    if cls.row == 6:
        return {"property_check_pass": Score(0, None), "exploit_probes_blocked": Score(None, cls.reason)}
    blocked = sum(o == "blocked" for o in outcomes)
    all_blocked = blocked == len(outcomes)
    if hidden_tests.value == 0 or not all_blocked:
        primary = Score(0, None)
    elif hidden_tests.value is None:
        primary = Score(None, hidden_tests.reason)
    else:
        primary = Score(1, None)
    if not outcomes:
        secondary = Score(None, "no probe case declared")
    else:
        secondary = Score(at_scale(Decimal(blocked) / Decimal(len(outcomes)), 4), None)
    return {"property_check_pass": primary, "exploit_probes_blocked": secondary}


# --- the check runner: the grader side of the handshake (design 5.3; spike E1-S3, SP-F2) -------------------------------


@dataclass(frozen=True)
class CheckRun:
    """What one check run showed, as facts. `_classify` decides; nothing here is a verdict."""

    stdout: bytes  # stored prefix, at most `_STORE` bytes
    has_line: bool
    documents: int
    trailing_bytes: int
    alone_at_arrival: bool
    job_view: str  # "alone", "not alone" or "query failed" (evidence only)
    exit_before_line: bool
    exit_code: int | None  # None: killed at the bound
    bound_fired: bool
    acked: bool
    document: dict | None  # the validated document, or None
    invalid: str | None  # why the line failed `validate`, or None


class _Stdout(threading.Thread):
    """Drains the check's stdout from the start so the writer never blocks; keeps `_STORE` bytes, counts the rest."""

    def __init__(self, cp: procs.CellProcess) -> None:
        super().__init__(daemon=True)
        self.cp, self.buf, self.total, self.lock = cp, bytearray(), 0, threading.Lock()
        self.first_ft: int | None = None
        self.view: frozenset[int] | None = None  # None: the job query raised (read as not alone)
        self.ready = threading.Event()  # a newline, an oversized prefix or EOF

    def run(self) -> None:
        stream = self.cp.proc.stdout
        try:
            while chunk := stream.read1(65536):
                if self.first_ft is None:  # the first byte: stamp the clock, then look at the job (design 5.3 step 2)
                    self.first_ft = procs.now_filetime()
                    try:
                        self.view = frozenset(self.cp.job.pids())
                    except Exception:  # noqa: BLE001 - any failed query is "not alone" (fail closed, G5)
                        self.view = None
                with self.lock:
                    self.total += len(chunk)
                    self.buf += chunk[: max(0, _STORE - len(self.buf))]
                    if b"\n" in self.buf or len(self.buf) > MAX_RESULT_BYTES:
                        self.ready.set()
        except (OSError, ValueError):
            pass  # the pipe was closed under us at the end of a run
        finally:
            self.ready.set()

    def snapshot(self) -> tuple[bytes, int]:
        with self.lock:
            return bytes(self.buf), self.total


def _split(stored: bytes, total: int) -> tuple[bool, bytes, int, int]:
    """(has_line, first line, document count, trailing bytes after it). A prefix with no newline is a line only when it
    is already over the cap (it can never become a valid one); a short one is a write cut off."""
    i = stored.find(b"\n")
    if i < 0:
        if len(stored) > MAX_RESULT_BYTES:
            return True, stored[: MAX_RESULT_BYTES + 2], 1, total - MAX_RESULT_BYTES - 2
        return False, b"", 0, 0
    rest = stored[i + 1:]
    return True, stored[: i + 1], 1 + len([x for x in rest.split(b"\n") if x]), total - (i + 1)


def run_check(argv: list[str], cwd: Path, env: dict[str, str], bound: float, stderr_path: Path,
              validate: Callable[[bytes], dict]) -> CheckRun:
    """Spawn the check detached in its own job and run the handshake. Accept the first line only when `validate`
    passes and the job held exactly the check at the first byte; then send 0x06. Stdin is closed on every path, so a
    refusal is EOF and the check exits 3 at once. `bound` is seconds for the whole run. Never raises for a check fault."""
    deadline = time.monotonic() + bound
    document: dict | None = None
    invalid: str | None = None
    acked = bound_fired = False
    exit_code: int | None = None
    exit_ft: int | None = None
    with stderr_path.open("wb") as err:
        cp = procs.spawn(argv, cwd, env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, console=False)
        reader = _Stdout(cp)
        try:
            reader.start()
            got_line = reader.ready.wait(max(0.0, deadline - time.monotonic()))
            try:
                stored, total = reader.snapshot()
                has_line, line, _, _ = _split(stored, total)
                if got_line and has_line:
                    try:
                        document = validate(line)
                    except ValueError as exc:
                        invalid = str(exc)
                    if document is not None and reader.view == frozenset({cp.pid}):
                        cp.proc.stdin.write(ACK)
                        cp.proc.stdin.flush()
                        acked = True
            except OSError:
                pass  # the check is already gone; its exit status says what that means
            finally:
                try:
                    cp.proc.stdin.close()  # every path: EOF without the byte is a refusal
                except OSError:
                    pass
            if got_line:
                try:
                    exit_code = cp.wait(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
            bound_fired = exit_code is None
            if not bound_fired:
                try:
                    exit_ft = cp.exit_time()
                except OSError:
                    exit_ft = None
            cp.terminate_and_confirm(procs._KILL_GRACE)
            reader.join(procs._KILL_GRACE)
        finally:
            cp.close()
    stored, total = reader.snapshot()
    has_line, line, documents, trailing = _split(stored, total)
    if has_line and document is None and invalid is None:
        try:
            document = validate(line)
        except ValueError as exc:
            invalid = str(exc)
    before = reader.first_ft is not None and not bound_fired and (exit_ft is None or exit_ft <= reader.first_ft)
    view = "query failed" if reader.view is None else "alone" if reader.view == frozenset({cp.pid}) else "not alone"
    return CheckRun(stored, has_line, documents, trailing, view == "alone", view, before, exit_code, bound_fired, acked,
                    document, invalid)


# --- grade_cell (design 5.2) ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GradeContext:
    """The grader-side context of one run (not `bench_check.Context`, the check-side one)."""

    timeout: float  # the plan's grading_step_timeout; bounds each phase separately


def check_seed(task_version: str, cell_id: str) -> int:
    return int(hashlib.sha256(f"{task_version}|{cell_id}|property_check_pass".encode()).hexdigest()[:16], 16)


def _sleep_detector() -> host.SleepDetector:
    return host.SleepDetector(PROPERTY_SUSPEND_GAP_S)


class _Span:
    """One phase's span: a fresh SleepDetector made at start and read once at the end (design 5.2 step 3)."""

    def __init__(self, phase: str) -> None:
        self.phase, self.detector, self.t0 = phase, _sleep_detector(), time.monotonic()
        self.start_ok = host.unbiased_seconds() is not None

    def end(self) -> dict:
        return {"phase": self.phase, "wall_ms": round((time.monotonic() - self.t0) * 1000),
                "suspended": bool(self.detector.slept()),
                "unbiased_ok": self.start_ok and host.unbiased_seconds() is not None}


class NotBuilt(Exception):
    """A task declares something E1 does not build (design 4): every metric is NA `not built`."""


def _load_cases(task_dir: Path) -> dict:
    """The task's cases.yaml, validated. ValueError names the rule broken (the runner's HB-GRD-003 NA); NotBuilt for
    what E1 does not build."""
    spec = config.load_yaml(task_dir / "oracle" / "check" / "cases.yaml")
    if spec.get("schema") != "bench-check-cases/1":
        raise ValueError(f"cases.yaml schema {spec.get('schema')!r} is not bench-check-cases/1")
    entry = spec.get("entry", "")
    if not isinstance(entry, str):
        raise ValueError("cases.yaml entry is not a string")  # noqa: TRY004 - one error type for every malformed shape
    check_segment("entry", entry, _ENTRY)
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases.yaml declares no cases")
    for c in cases:
        check_segment("case id", str(c.get("id")), _CASE_ID)
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("cases.yaml repeats a case id")
    for name in spec.get("env") or []:
        if name not in _env.TOOLCHAIN_ENV and not name.startswith(_env.CHECK_PREFIX):
            raise ValueError(f"cases.yaml env {name!r} is neither a toolchain name nor HB_CHECK_*")
    if spec.get("interface") != "in-process" or any(c.get("kind") != "probe" for c in cases) \
            or (spec.get("app") or {}).get("kind") not in _APP_KINDS:
        raise NotBuilt
    return spec


def _tree_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink())


def _hidden_check(inp: CellInput, ctx: GradeContext) -> dict[str, Score]:
    spec = _load_cases(inp.task_dir)
    if not BENCH_CHECK.is_file():
        raise NotBuilt
    work = (inp.work_root or inp.out_dir) / "property"
    run = work / "check-run"
    evid = inp.out_dir / "check"
    evid.mkdir(parents=True, exist_ok=True)
    (inp.out_dir / "tests").mkdir(parents=True, exist_ok=True)
    spans: list[dict] = []
    try:
        span = _Span("tests")
        c = correctness.grade(inp.archive / "ws", inp.task_dir, inp.task.get("oracle") or {}, inp.out_dir / "tests",
                              inp.run_dir, ctx.timeout, work / "tests")
        spans.append(span.end())
        hidden = Score(c.passed, c.reason)
        span = _Span("check")
        skipped = _changes.copy_tree(inp.archive / "ws", run / "deliverable", ignore=_changes.BUILD_OUTPUT)
        check_dir = run / "check"
        _changes.copy_tree(inp.task_dir / "oracle" / "check", check_dir, ignore=("__pycache__",))
        (check_dir / BENCH_CHECK.name).write_bytes(BENCH_CHECK.read_bytes())
        (check_dir / "cases.json").write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
        hash_before = tree_hash(check_dir, _tree_files(check_dir))  # last, after every file is in place
        declared = [str(c["id"]) for c in spec["cases"]]
        seed = check_seed(inp.cell["task_version"], inp.cell["cell_id"])
        argv = [sys._base_executable, "-S", f"check/{spec['entry']}", "--deliverable", str((run / "deliverable").resolve()),
                "--cases", "check/cases.json", "--seed", str(seed), "--evidence", str(evid.resolve())]
        env = _env.grading_env([n for n in spec.get("env") or [] if n in _env.TOOLCHAIN_ENV])
        got = run_check(argv, run, env, ctx.timeout, evid / "check.stderr",
                        lambda line: parse_result(line, declared, frozenset(), {}))
        hash_after = tree_hash(check_dir, _tree_files(check_dir))
        spans.append(span.end())
    finally:
        if run.exists():
            _changes.remove_tree(run)
    stderr = evid / "check.stderr"
    if stderr.is_file() and stderr.stat().st_size > MAX_RESULT_BYTES:
        with stderr.open("r+b") as f:
            f.truncate(MAX_RESULT_BYTES)
    (evid / "check.stdout").write_bytes(got.stdout[:MAX_RESULT_BYTES])
    facts = Facts(tests_suspended=spans[0]["suspended"], check_suspended=spans[1]["suspended"], bound_fired=got.bound_fired,
                  hash_before=hash_before, hash_after=hash_after, alone_at_arrival=got.alone_at_arrival,
                  documents=got.documents, trailing_bytes=got.trailing_bytes, exit_before_line=got.exit_before_line,
                  has_line=got.has_line, exit_code=got.exit_code, line_valid=got.document is not None,
                  deliverable=got.document["deliverable"] if got.document else "ran")
    cls = _classify(facts)
    outcomes = [c["outcome"] for c in got.document["cases"]] if got.document and cls.row == 7 else []
    pointer = (inp.out_dir / "property.json").relative_to(inp.run_dir).as_posix()
    scores = {k: dataclasses.replace(v, evidence=pointer) for k, v in score_run(cls, hidden, outcomes).items()}
    evidence = {"schema": "bench-property-evidence/1", "row": cls.row, "code": cls.code, "reason": cls.reason, "seed": seed,
                "hidden_tests_pass": {"value": hidden.value, "reason": hidden.reason}, "spans": spans,
                "check": {"job_view": got.job_view, "acked": got.acked, "exit_code": got.exit_code,
                          "documents": got.documents, "trailing_bytes": got.trailing_bytes, "bound_fired": got.bound_fired,
                          "invalid": got.invalid, "hash_before": hash_before, "hash_after": hash_after,
                          "copy": {"skipped_reparse_points": skipped}},
                "outcomes": outcomes}
    (inp.out_dir / "property.json").write_text(json.dumps(evidence, sort_keys=True, indent=1), encoding="utf-8")
    return scores


def hidden_tests(inp: CellInput, tree: Path, label: str, overlay: Mapping[str, Path] | None = None) -> Score:
    return Score(None, "stub")


STRATEGIES: dict[str, Callable[[CellInput, GradeContext], dict[str, Score]]] = {"security": _hidden_check}


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """property_check_pass and exploit_probes_blocked from the hidden tests and the hidden check (design 5.2)."""
    na = Score(None, "not built")
    keys = list(inp.metrics)
    strategy = STRATEGIES.get(((inp.task.get("property") or {}).get("name")) or "")
    if sys.platform != "win32" or strategy is None:
        return dict.fromkeys(keys, na)
    try:
        scores = strategy(inp, GradeContext(inp.plan["parameters"]["grading_step_timeout"]))
    except NotBuilt:
        return dict.fromkeys(keys, na)
    return {k: scores.get(k, na) for k in keys}
