"""Scenario 7 (formalize and find bugs): grade a TLA+ model or Lean 4 proof as six separate scores.

Design: docs/design/formal-grader.md (revision 2), amended by ruling R-84 (docs/notes/rulings.md).

Metrics: formal_checks_clean, statement_integrity, model_conformance, model_non_vacuity,
bugs_confirmed, bug_claim_precision.
- checks: TLC completes within the oracle's bounds with no violation (G1); `lake build` clean and
  `#print axioms` shows only propext, Classical.choice, Quot.sound, plus a lexical scan for
  elaboration-time side effects `#print axioms` cannot see (G2). A pre-invocation binary-artifact
  scan refuses to invoke either toolchain when the agent's own directory holds anything but the
  allowed plain-text extensions (TLC's `.class`-override mechanism; an unpinned Lean manifest).
- statement integrity: the given statements/fold hash to `formal.statement_hash` (G2's hash is the
  Lean elaborator's own `#check` rendering of each named declaration's type, never a hand-rolled
  parse).
- model_conformance / model_non_vacuity (G1): recorded real/bug-seeded fold traces replayed
  against the agent's model. **R-84 c1: the trace-replay mechanism (`_replay`) is unspiked
  (DR-FM1). In a real grading pass these two G1 metrics are NA "not built"; `_replay` and the pure
  ratio helpers below are exercised by tests only, never by `grade_cell` outside a test.**
- model_non_vacuity (G2): a second `lake build`, the given fold swapped for its bug-seeded variant;
  `1` iff the agent's own proofs then fail to build (they genuinely depend on the fold's semantics).
- bugs_confirmed / bug_claim_precision: DR-FM2's mechanical table (R-84) decides each `BUGS.md`
  entry from a validated `Test:` reference run against the real fold and, if it fails there, against
  the seed's reference fix -- never from whether the claim matches the seeded bug by name.

Toolchain invocation: only through `correctness.run_step` (D3 import lint, G6/G10) -- `formal.py`
is not on the `procs` allowlist and never will be. Every argv element is grader-generated or
validated against a closed pattern before use (STRIDE, design "Adversarial analysis").
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from harness_bench.grade import CellInput, Score, correctness
from harness_bench.plan import file_hash, tree_hash

NOT_BUILT = "not built"  # R-84 c1: the literal reason a real pass reads for the two unspiked G1 metrics
TLA = "tla"
LEAN = "lean"
NO_WORKING_COPY = "no working copy in the archive"
NOT_WARMED = "formal toolchain not warmed: {reason}"
GIVEN_EDITED = "given statements edited (statement_hash mismatch)"
NO_BUGS_MD = "no BUGS.md in the working copy"

# --- G1 (TLA+): warm-before-clock and the binary-artifact scan -----------------------------------------------------

_G1_SPEC_ALLOWED_EXTS = {".tla", ".cfg", ".tex"}
_G2_PROOF_ALLOWED_EXTS = {".lean"}
_G2_PROOF_ALLOWED_NAMES = {"lakefile.toml", "lean-toolchain", ".gitignore"}
_STATES_LINE = re.compile(r"^\d[\d,]* states? generated,\s*[\d,]+ distinct states? found", re.MULTILINE)


def _artifact_offender(root: Path, allowed_exts: set[str], allowed_names: set[str]) -> str | None:
    """The first (sorted) file under `root` whose suffix/name is not allowed, or None. `root` missing is not this
    check's concern (the caller's own 'no working copy' / 'no ... in the working copy' NA covers that)."""
    if not root.is_dir():
        return None
    offenders = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() not in allowed_exts and p.name not in allowed_names
    )
    return offenders[0] if offenders else None


def _check_models_pins(root: Path):
    """`tools/check_models.py`'s module object, loaded by path (it is a script, not a package member) so its
    TLA_VERSION/JAR_URL/JAR_SHA256 pin is read once, never duplicated (G7/G12's "one hashing/one pin" rule)."""
    spec = importlib.util.spec_from_file_location("check_models", root / "tools" / "check_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _warm_tla_jar(root: Path) -> tuple[Path | None, str | None]:
    """(jar path, None) when a warm, sha256-verified tla2tools.jar is present at HB_TLA_JAR or the host cache;
    (None, reason) otherwise. Never downloads (S-12's warm-before-clock fix)."""
    pins = _check_models_pins(root)
    configured = os.environ.get("HB_TLA_JAR")
    jar = Path(configured) if configured else (
        Path(os.environ.get("LOCALAPPDATA", "")) / "harness-bench" / "tools" / f"tla2tools-{pins.TLA_VERSION}.jar")
    if not jar.is_file():
        return None, f"{jar} missing"
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != pins.JAR_SHA256:
        return None, f"{jar} sha256 mismatch"
    return jar, None


def _elan_home() -> Path:
    configured = os.environ.get("ELAN_HOME")
    return Path(configured) if configured else Path.home() / ".elan"


def _lake_exe(elan_home: Path) -> Path:
    return elan_home / "bin" / ("lake.exe" if os.name == "nt" else "lake")


def _warm_lake(root: Path) -> tuple[Path | None, str | None]:
    """(lake exe path, None) when the pinned elan/Lean toolchain is installed on this host; (None, reason)
    otherwise. Never installs (mirrors _warm_tla_jar's warm-before-clock contract for Lean)."""
    lake = _lake_exe(_elan_home())
    if not lake.is_file():
        return None, f"{lake} missing (elan/Lean toolchain not installed)"
    return lake, None


# --- G1 (TLA+): formal_checks_clean ---------------------------------------------------------------------------

def _tlc_clean(returncode: int, output: str) -> bool:
    """The clean-run predicate (FM7): exit 0, no 'violated', no 'Error:', AND TLC's own states-generated line is
    present -- a run with the wrong cwd (or that otherwise silently did nothing) is never read as clean merely
    because nothing errored."""
    return returncode == 0 and "violated" not in output and "Error:" not in output and bool(_STATES_LINE.search(output))


def _g1_formal_checks_clean(inp: CellInput, timeout: float) -> Score:
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    spec_dir = ws / "spec"
    offender = _artifact_offender(spec_dir, _G1_SPEC_ALLOWED_EXTS, set())
    out_dir = inp.out_dir / "checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    if offender is not None:
        return Score(0, None, _write_log(out_dir, "artifact-scan.log", f"unexpected binary artifact in spec/: {offender}\n"))
    bounds = inp.task_dir / "oracle" / "bounds.cfg"
    if not bounds.is_file():
        return Score(None, "no oracle/bounds.cfg for this task version")
    if not (spec_dir / "Model.tla").is_file():
        return Score(None, "no spec/Model.tla in the working copy")
    jar, reason = _warm_tla_jar(inp.root)
    if jar is None:
        return Score(None, NOT_WARMED.format(reason=reason))
    cfg = spec_dir / "Model.cfg"  # the grader always (re)writes this from the oracle's bounds -- never agent-authored
    cfg.write_text(bounds.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        argv = ["java", "-XX:+UseParallelGC", "-XX:MaxRAMPercentage=75", "-cp", str(jar), "tlc2.TLC",
                "-workers", "auto", "-metadir", str(out_dir / "meta"), "-config", "Model.cfg", "Model.tla"]
        done = correctness.run_step(argv, spec_dir, correctness._env(), timeout)
    finally:
        cfg.unlink(missing_ok=True)
    output = done.stdout + done.stderr
    log = _write_log(out_dir, "tlc.log", f"$ {' '.join(argv)}\nexit {done.returncode}\n{output}")
    if done.timed_out:
        return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s", log)
    return Score(int(_tlc_clean(done.returncode, output)), None, log)


def _write_log(out_dir: Path, name: str, text: str) -> str:
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# --- G2 (Lean): the lexical scan and the elaborator calls -----------------------------------------------------

_LEAN_BLOCK_COMMENT = re.compile(r"/-.*?-/", re.DOTALL)
_LEAN_LINE_COMMENT = re.compile(r"--[^\n]*")
_LEAN_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
_LEAN_BANNED = ("sorry", "admit", "native_decide", "initialize", "run_cmd", "unsafe")  # \b-bounded identifiers
_LEAN_BANNED_SYMBOLS = ("#eval", "@[extern")  # matched literally (not identifier-bounded)


def _strip_lean_noise(text: str) -> str:
    """Comments and string literals blanked out (never counted) before the lexical scan (FM6/FM14)."""
    return _LEAN_STRING.sub('""', _LEAN_LINE_COMMENT.sub("", _LEAN_BLOCK_COMMENT.sub(" ", text)))


def _lexical_hit(text: str) -> str | None:
    stripped = _strip_lean_noise(text)
    for token in _LEAN_BANNED:
        if re.search(rf"(?<![\w.']){re.escape(token)}(?![\w'])", stripped):
            return token
    for token in _LEAN_BANNED_SYMBOLS:
        if token in stripped:
            return token
    return None


class ReplayResult(NamedTuple):
    """One `_replay` call's outcome (DR-FM1's seam)."""

    accepted: bool
    log: str
    divergent_line: int | None = None


def _replay(model_or_proof: Path, trace: Path, timeout: float, out_dir: Path) -> ReplayResult:
    """DR-FM1: the TLA+ trace-replay mechanism is unspiked. `grade_cell` never calls this in a real pass (R-84 c1);
    it exists so a test can monkeypatch it and exercise the ratio/NA-cascade logic ahead of the spike."""
    raise NotImplementedError("DR-FM1: the trace-replay mechanism is unspiked (docs/notes/rulings.md R-84)")


def _g1_ratio_metric(inp: CellInput, glob: str, expect_accept: bool, replay) -> Score:
    """model_conformance (expect_accept=True, real traces) / model_non_vacuity (expect_accept=False, bug-seeded
    variants) for G1 -- test-only per R-84 c1: `grade_cell` never reaches this with the real (unbuilt) `_replay`."""
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    traces = sorted((inp.task_dir / "oracle").glob(glob))
    if not traces:
        return Score(None, "no recorded traces for this task version" if expect_accept else
                     "no bug-seeded traces for this task version")
    model = ws / "spec" / "Model.tla"
    matched = 0
    log_lines = []
    first_divergence = None
    for trace in traces:
        result = replay(model, trace, inp.plan["parameters"]["grading_step_timeout"], inp.out_dir)
        ok = result.accepted if expect_accept else not result.accepted
        matched += int(ok)
        log_lines.append(f"{trace.name}: accepted={result.accepted}\n")
        if not ok and first_divergence is None:
            first_divergence = f"{result.log}:{result.divergent_line}" if result.divergent_line else result.log
    evidence_log = _write_log(inp.out_dir, "conformance.log" if expect_accept else "non_vacuity.log", "".join(log_lines))
    return Score(Decimal(matched) / Decimal(len(traces)), None, first_divergence or evidence_log)


def _g2_model_non_vacuity(inp: CellInput, timeout: float) -> Score:
    """G2: 1 iff the agent's proofs fail to build against the bug-seeded fold (they genuinely depend on its
    semantics); 0 if they still build clean (vacuous)."""
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    buggy = inp.task_dir / "oracle" / "fold-buggy" / "Fold.lean"
    if not buggy.is_file():
        return Score(None, "no oracle/fold-buggy/Fold.lean for this task version")
    lake, reason = _warm_lake(inp.root)
    if lake is None:
        return Score(None, NOT_WARMED.format(reason=reason))
    out_dir = inp.out_dir / "non_vacuity"
    work_dir = (inp.work_root or inp.out_dir) / "non_vacuity"  # ADR-0013: outside the repository in a real pass
    with _grading_copy(ws / "Proofs", work_dir / "proofs") as proofs:
        (proofs / "Fold.lean").write_bytes(buggy.read_bytes())  # the swap: agent's own files untouched
        done = correctness.run_step([str(lake), "build"], proofs, correctness._env(), timeout)
        log = _write_log(out_dir, "lake-buggy-fold.log", f"exit {done.returncode}\n{done.stdout}\n{done.stderr}")
        if done.timed_out:
            return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s", log)
        return Score(int(done.returncode != 0), None, log)


class _GradingCopy:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def _grading_copy(src: Path, dest: Path) -> _GradingCopy:
    """A disposable copy of `src` at `dest` (never the archive), git-free and build-output-free."""
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", ".lake", "lake-manifest.json"))
    return _GradingCopy(dest)


def _lake_env_lean(lake: Path, cwd: Path, script: Path, env: dict, timeout: float):
    return correctness.run_step([str(lake), "env", "lean", str(script)], cwd, env, timeout)


def _statement_material(proofs: Path, theorem_names: list[str], lake: Path, env: dict, timeout: float,
                         out_dir: Path, work_dir: Path | None = None) -> tuple[Path, list[Path]] | tuple[None, str]:
    """Materialize the four real files `statement_integrity`/`formal_checks_clean`'s G2 hash and axiom checks share:
    a staging copy of Fold.lean/lakefile.toml/lean-toolchain plus the elaborator's own `#check` rendering of every
    name in `theorem_names`, written to a real file (never a synthesized in-memory string). Returns
    (staging dir, [the four Paths]) or (None, an NA reason). `work_dir` (default `out_dir`) is where the disposable
    build copy lands -- outside the repository in a real pass (ADR-0013); `out_dir` keeps the staged evidence."""
    for name, rel in (("Proofs/Fold.lean", "Fold.lean"), ("lakefile.toml", "lakefile.toml"), ("lean-toolchain", "lean-toolchain")):
        if not (proofs / rel).is_file():
            return None, f"no {name} in the working copy"
    # A grading copy, never the archive (`ws` stays immutable): `lake env lean --run`'s import resolution needs the
    # project already built (oleans present), so this builds once in a disposable copy before the elaborator call.
    with _grading_copy(proofs, (work_dir or out_dir) / "build") as copy:
        built = correctness.run_step([str(lake), "build"], copy, env, timeout)
        if built.timed_out:
            return None, "HB-GRD-002 grading step timeout"
        if built.returncode != 0:
            return None, "Proofs/** does not build (statement elaboration unavailable)"
        script = out_dir / "_check.lean"
        script.write_text("import Statements\n" + "".join(f"#check {n}\n" for n in theorem_names), encoding="utf-8")
        done = _lake_env_lean(lake, copy, script, env, timeout)
        if done.timed_out:
            return None, "HB-GRD-002 grading step timeout"
        if done.returncode != 0:
            return None, "a name in formal.theorem_names is not a declaration in Proofs/Statements.lean"
        staging = out_dir / "stmt"
        staging.mkdir(parents=True, exist_ok=True)
        for rel in ("Fold.lean", "lakefile.toml", "lean-toolchain"):
            shutil.copyfile(copy / rel, staging / rel)
        (staging / "check.out").write_text(done.stdout, encoding="utf-8")
    files = [staging / "Fold.lean", staging / "lakefile.toml", staging / "lean-toolchain", staging / "check.out"]
    return staging, files


# --- statement_integrity ---------------------------------------------------------------------------------------

def _g1_statement_integrity(inp: CellInput) -> Score:
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    expected = (inp.task.get("formal") or {}).get("statement_hash")
    return Score(int(file_hash(ws / "spec" / "Properties.tla") == expected), None)


def _g2_statement_integrity(inp: CellInput, timeout: float) -> Score:
    formal = (inp.task.get("formal") or {})
    if formal.get("statements") == "agent":
        return Score(None, "formal.statements: agent — statement integrity not applicable")
    names = formal.get("theorem_names")
    if not names:
        return Score(None, "formal.theorem_names not recorded for this task version")
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    lake, reason = _warm_lake(inp.root)
    if lake is None:
        return Score(None, NOT_WARMED.format(reason=reason))
    out_dir = inp.out_dir / "statement_integrity"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = (inp.work_root or inp.out_dir) / "statement_integrity"  # ADR-0013: outside the repository in a real pass
    staging, result = _statement_material(ws / "Proofs", names, lake, correctness._env(), timeout, out_dir, work_dir)
    if staging is None:
        return Score(None, result)
    digest = tree_hash(staging, result)
    expected = formal.get("statement_hash")
    return Score(int(digest == expected), None)


def statement_integrity(inp: CellInput, timeout: float) -> Score:
    tool = (inp.task.get("formal") or {}).get("tool")
    if tool == LEAN:
        return _g2_statement_integrity(inp, timeout)
    return _g1_statement_integrity(inp)


# --- formal_checks_clean (G2) -----------------------------------------------------------------------------------

def _g2_formal_checks_clean(inp: CellInput, timeout: float) -> Score:
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    proofs_src = ws / "Proofs"
    if not (proofs_src / "Fold.lean").is_file():
        return Score(None, "no Proofs/Fold.lean in the working copy")
    offender = _artifact_offender(proofs_src, _G2_PROOF_ALLOWED_EXTS, _G2_PROOF_ALLOWED_NAMES)
    out_dir = inp.out_dir / "checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    if offender is not None:
        return Score(0, None, _write_log(out_dir, "artifact-scan.log", f"unexpected artifact in Proofs/: {offender}\n"))
    formal = (inp.task.get("formal") or {})
    task_dir_proofs = inp.task_dir / "Proofs" if (inp.task_dir / "Proofs" / "lakefile.toml").is_file() else None
    if task_dir_proofs is not None:
        for name in ("lakefile.toml", "lean-toolchain"):
            if file_hash(proofs_src / name) != file_hash(task_dir_proofs / name):
                return Score(0, None, _write_log(out_dir, "manifest.log", f"{name} does not match the task's frozen copy\n"))
    lake, reason = _warm_lake(inp.root)
    if lake is None:
        return Score(None, NOT_WARMED.format(reason=reason))
    lexical_hits = []
    for lean_file in sorted(proofs_src.rglob("*.lean")):
        hit = _lexical_hit(lean_file.read_text(encoding="utf-8", errors="replace"))
        if hit is not None:
            lexical_hits.append((lean_file.relative_to(proofs_src).as_posix(), hit))
    work_dir = (inp.work_root or inp.out_dir) / "checks"  # ADR-0013: outside the repository in a real pass
    with _grading_copy(proofs_src, work_dir / "proofs") as proofs:
        done = correctness.run_step([str(lake), "build"], proofs, correctness._env(), timeout)
        log = _write_log(out_dir, "lake.log", f"exit {done.returncode}\n{done.stdout}\n{done.stderr}")
        if done.timed_out:
            return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s", log)
        if done.returncode != 0:
            return Score(0, None, log)
        if lexical_hits:
            evidence = _write_log(out_dir, "lexical.log", "".join(f"{f}: {t}\n" for f, t in lexical_hits))
            return Score(0, None, evidence)
        names = formal.get("theorem_names") or []
        for name in names:
            script = out_dir / f"_axioms_{name}.lean"
            script.write_text(f"import Statements\n#print axioms {name}\n", encoding="utf-8")
            axiom_done = _lake_env_lean(lake, proofs, script, correctness._env(), timeout)
            axiom_log = axiom_done.stdout + axiom_done.stderr
            if axiom_done.timed_out:
                return Score(None, f"HB-GRD-002 grading step timeout after {timeout:g} s", log)
            if axiom_done.returncode != 0 or not _axioms_clean(axiom_log):
                evidence = _write_log(out_dir, f"axioms-{name}.log", axiom_log)
                return Score(0, None, evidence)
    return Score(1, None, log)


_ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def _axioms_clean(output: str) -> bool:
    """True iff `#print axioms` reported no axioms, or only the three standard ones (never sorryAx, never a
    custom axiom)."""
    if "does not depend on any axioms" in output:
        return True
    match = re.search(r"depends on axioms:\s*\[([^\]]*)\]", output)
    if not match:
        return False
    used = {a.strip() for a in match.group(1).split(",") if a.strip()}
    return used <= _ALLOWED_AXIOMS


def formal_checks_clean(inp: CellInput, timeout: float) -> Score:
    tool = (inp.task.get("formal") or {}).get("tool")
    if tool == LEAN:
        return _g2_formal_checks_clean(inp, timeout)
    if tool == TLA:
        return _g1_formal_checks_clean(inp, timeout)
    return Score(None, f"formal.tool {tool!r} not in ('tla', 'lean')")


# --- bugs_confirmed / bug_claim_precision (DR-FM2, G1 only) ------------------------------------------------------

_BUG_HEADING = re.compile(r"^## .*$", re.MULTILINE)
_BUG_TEST_REF = re.compile(r"^Test:\s*(.+?)\s*$", re.MULTILINE)
G2_NO_BUG_ARTIFACT = "no bug-report artifact defined for this task (not a bug-narrative task)"


@dataclass(frozen=True)
class _Entry:
    ref: str | None  # None when the claim's section has no Test: line at all (DR-FM2 row 1)
    valid_path: Path | None  # the resolved test file, or None when there is no ref, or it failed validation


def _bug_entries(bugs_md: str, ws: Path) -> list[_Entry]:
    """One `_Entry` per `## <slug>` claim heading (DR-FM2's schema), whether or not it names a `Test:` line."""
    headings = list(_BUG_HEADING.finditer(bugs_md))
    out = []
    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(bugs_md)
        section = bugs_md[m.end():end]
        found = _BUG_TEST_REF.search(section)
        ref = found.group(1) if found else None
        out.append(_Entry(ref, _validate_test_ref(ref, ws) if ref else None))
    return out


def _validate_test_ref(ref: str, ws: Path) -> Path | None:
    """The test file `Path` for a safe `tests/<file>::<function>` node id; None on any validation failure (Security
    & Identity Architect Blocker 1) -- checked before any argv is built, never passed to `run_step` when None."""
    if not ref or ref.startswith("-"):
        return None
    file_part, sep, func = ref.partition("::")
    if not sep or not func or "::" in func:
        return None
    parts = Path(file_part).parts
    if not parts or ".." in parts or Path(file_part).is_absolute():
        return None
    try:
        resolved = (ws / file_part).resolve()
        resolved.relative_to((ws / "tests").resolve())
    except (ValueError, OSError):
        return None
    return ws / file_part


def _pytest_node_run(node_id: str, ws: Path, timeout: float, out_dir: Path, tag: str) -> bool | None:
    """True/False (passed/failed) from one real pytest run of `node_id` in `ws`; None on a timeout (the caller
    reads that as the shared HB-GRD-002 NA, not a table row)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"{tag}.xml"
    argv = [sys.executable, "-m", "pytest", "-q", node_id, f"--junitxml={report}"]
    done = correctness.run_step(argv, ws, correctness._env(), timeout)
    _write_log(out_dir, f"{tag}.log", f"$ {' '.join(argv)}\nexit {done.returncode}\n{done.stdout}\n{done.stderr}")
    if done.timed_out:
        return None
    parsed = correctness.parse_pytest(report) if report.is_file() else None
    total, passed = parsed if parsed else (0, 0)
    return bool(total) and passed == total


def _entry_outcome(entry: _Entry, ws: Path, bugfix: Path, timeout: float, out_dir: Path, tag: str) -> str:
    """'in_not_confirmed' | 'confirmed' | 'excluded' (DR-FM2's mechanical table, R-84)."""
    if entry.valid_path is None or not entry.valid_path.is_file():
        return "in_not_confirmed"
    real = _pytest_node_run(f"{entry.ref}", ws, timeout, out_dir, f"{tag}-real")
    if real is None:
        return "in_not_confirmed"  # a timeout on the real-fold run is not evidence of a fix (never a silent kill)
    if real:  # the test passes on the real, unmodified fold: a refuted claim
        return "in_not_confirmed"
    original = (ws / "coord_core.py").read_bytes()
    (ws / "coord_core.py").write_bytes(bugfix.read_bytes())
    try:
        fixed = _pytest_node_run(f"{entry.ref}", ws, timeout, out_dir, f"{tag}-fix")
    finally:
        (ws / "coord_core.py").write_bytes(original)
    if fixed is None:
        return "in_not_confirmed"
    return "confirmed" if fixed else "excluded"


def _bug_confirmation(inp: CellInput, timeout: float) -> tuple[int | None, str | None, int, int, str]:
    """(bugs_confirmed value, NA reason, N, confirmed, evidence) computed once, shared by both metrics."""
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return None, NO_WORKING_COPY, 0, 0, ""
    bugs_md = ws / "BUGS.md"
    out_dir = inp.out_dir / "bugs"
    if not bugs_md.is_file():
        return 0, None, 0, 0, ""  # R-84: no BUGS.md is a measurement (the bug was not found), never NA
    entries = _bug_entries(bugs_md.read_text(encoding="utf-8"), ws)
    if not entries:
        return 0, None, 0, 0, ""
    bugfix = inp.task_dir / "oracle" / "bugfix" / "Fold.py"
    n = confirmed = 0
    lines = []
    for i, entry in enumerate(entries):
        outcome = _entry_outcome(entry, ws, bugfix, timeout, out_dir, f"entry{i}")
        lines.append(f"{entry.ref}: {outcome}\n")
        if outcome != "excluded":
            n += 1
        if outcome == "confirmed":
            confirmed += 1
    evidence = _write_log(out_dir, "table.log", "".join(lines)) if lines else ""
    return int(confirmed > 0), None, n, confirmed, evidence


def bugs_confirmed(inp: CellInput, timeout: float) -> Score:
    if (inp.task.get("formal") or {}).get("tool") == LEAN:
        return Score(None, G2_NO_BUG_ARTIFACT)
    value, reason, _n, _confirmed, evidence = _bug_confirmation(inp, timeout)
    return Score(value, reason, evidence)


def bug_claim_precision(inp: CellInput, timeout: float) -> Score:
    if (inp.task.get("formal") or {}).get("tool") == LEAN:
        return Score(None, G2_NO_BUG_ARTIFACT)
    ws = inp.archive / "ws"
    if not ws.is_dir():
        return Score(None, NO_WORKING_COPY)
    if not (ws / "BUGS.md").is_file():
        return Score(None, NO_BUGS_MD)
    _value, _reason, n, confirmed, evidence = _bug_confirmation(inp, timeout)
    if n == 0:
        return Score(None, NO_BUGS_MD)
    return Score(Decimal(confirmed) / Decimal(n), None, evidence)


# --- the cascade (statement_integrity gates the other metrics, per task type; US-32) ------------------------------

_G1_CASCADE = ("formal_checks_clean", "model_conformance", "model_non_vacuity")
_G2_CASCADE = ("formal_checks_clean", "model_non_vacuity")


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """The applicable subset of the six `formal`-grader metrics for one G1 or G2 cell (inp.metrics)."""
    tool = (inp.task.get("formal") or {}).get("tool")
    timeout = inp.plan["parameters"]["grading_step_timeout"]
    if tool not in (TLA, LEAN):  # a task with no (or an invalid) formal.tool: every metric is this one NA, never 0
        reason = f"formal.tool {tool!r} not in ('tla', 'lean')"
        return {m: Score(None, reason) for m in inp.metrics}
    integrity = statement_integrity(inp, timeout)
    out: dict[str, Score] = {}
    if "statement_integrity" in inp.metrics:
        out["statement_integrity"] = integrity
    cascaded = integrity.value == 0
    cascade_set = _G1_CASCADE if tool == TLA else _G2_CASCADE
    for metric in cascade_set:
        if metric not in inp.metrics:
            continue
        if cascaded:
            out[metric] = Score(None, GIVEN_EDITED)
        elif metric == "formal_checks_clean":
            out[metric] = formal_checks_clean(inp, timeout)
        elif metric == "model_conformance":
            out[metric] = Score(None, NOT_BUILT) if tool == TLA else Score(
                None, "formal.tool lean: no runtime trace to replay (Lean proofs are static)")
        elif metric == "model_non_vacuity":
            out[metric] = Score(None, NOT_BUILT) if tool == TLA else _g2_model_non_vacuity(inp, timeout)
    if "model_conformance" in inp.metrics and "model_conformance" not in out:
        out["model_conformance"] = Score(None, NOT_BUILT) if tool == TLA else Score(
            None, "formal.tool lean: no runtime trace to replay (Lean proofs are static)")
    if "bugs_confirmed" in inp.metrics:
        out["bugs_confirmed"] = bugs_confirmed(inp, timeout)
    if "bug_claim_precision" in inp.metrics:
        out["bug_claim_precision"] = bug_claim_precision(inp, timeout)
    return out
