"""The formal grader (design docs/design/formal-grader.md rev 2, amended by ruling R-84): six metrics for a G1
(TLA+) or G2 (Lean 4) cell. Real TLC and real `lake build` run in the default ring (D4: "no mocking the toolchain
itself in the default ring's positive fixtures"), against small fixture trees under
tests/fixtures/grade/formal/{g1,g2}/ -- each checks in well under a second once the host toolchain is warm
(S-12; this host's tla2tools.jar and elan/Lean are warmed once, outside any timed step, exactly as the design's
warm-before-clock contract requires).

R-84 c1: `_replay` (DR-FM1, the TLA+ trace-replay mechanism) is unbuilt. `grade_cell` never reaches it in a real
pass -- G1's model_conformance/model_non_vacuity always read NA "not built". The pure ratio helper
(`_g1_ratio_metric`) is exercised here only with a monkeypatched stub, proving the cascade/ratio logic ahead of
the spike, never through `grade_cell`.
"""

from __future__ import annotations

import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT

from harness_bench.grade import CellInput, Score, formal, runner

FIXTURES = ROOT / "tests" / "fixtures" / "grade" / "formal"
TIMEOUT = 120


def _skip_unless_toolchains_warmed() -> None:
    # Independent of formal.py's own warm-check functions (never `import formal` at module scope for this): a red
    # commit against a not-yet-built formal.py must fail on a real assertion inside a test, never abort collection
    # of the whole file with an AttributeError (CI-efficiency: a red commit is never a collection error).
    jar_dir = Path(os.environ["HB_TLA_JAR"]).parent if os.environ.get("HB_TLA_JAR") else (
        Path(os.environ.get("LOCALAPPDATA", "")) / "harness-bench" / "tools")
    if not jar_dir.is_dir() or not list(jar_dir.glob("tla2tools*.jar")):
        pytest.skip("tla2tools.jar not warmed on this host (HB_TLA_JAR or %LOCALAPPDATA%/harness-bench/tools)",
                    allow_module_level=True)
    elan_home = Path(os.environ["ELAN_HOME"]) if os.environ.get("ELAN_HOME") else Path.home() / ".elan"
    lake = elan_home / "bin" / ("lake.exe" if os.name == "nt" else "lake")
    if not lake.is_file():
        pytest.skip(f"Lean/elan not warmed on this host: {lake} missing", allow_module_level=True)


_skip_unless_toolchains_warmed()  # module-level: every test here needs both real toolchains


def _cell_input(tmp_path: Path, ws_src: Path, task: dict, task_extra_files: dict[str, Path] | None = None) -> CellInput:
    archive = tmp_path / "archive"
    (archive / "ws").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ws_src, archive / "ws", ignore=shutil.ignore_patterns(".git", ".lake", "lake-manifest.json"))
    task_dir = tmp_path / "task"
    task_dir.mkdir(parents=True, exist_ok=True)
    for rel, src in (task_extra_files or {}).items():
        dest = task_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copyfile(src, dest)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(
        run_dir=tmp_path, root=ROOT, plan={"parameters": {"grading_step_timeout": TIMEOUT}},
        cell={"cell_id": "c1", "task": "G1"}, task=task, task_dir=task_dir, archive=archive, out_dir=out_dir,
        events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(), metrics={},
        allow_model_calls=False, extraction=None, prices=None,
    )


def encode(score: Score) -> tuple:
    return score.value, score.reason


# --- registration ---------------------------------------------------------------------------------------------

def test_formal_is_registered_in_runner_graders():
    assert runner.GRADERS["formal"] is formal.grade_cell


# --- statement_integrity: G1 -----------------------------------------------------------------------------------

G1_REF = FIXTURES / "g1" / "reference"
G1_BOUNDS = FIXTURES / "g1" / "oracle" / "bounds.cfg"
G1_TASK = {"formal": {"tool": "tla", "statements": "fixed"}}


def _g1_task(statement_hash: str) -> dict:
    return {"formal": {"tool": "tla", "statements": "fixed", "statement_hash": statement_hash}}


def test_g1_statement_integrity_reference_matches_the_hash(tmp_path):
    from harness_bench.plan import file_hash
    expected = file_hash(G1_REF / "spec" / "Properties.tla")
    inp = _cell_input(tmp_path, G1_REF, _g1_task(expected))
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (1, None)


def test_g1_statement_integrity_edited_properties_scores_0(tmp_path):
    from harness_bench.plan import file_hash
    expected = file_hash(G1_REF / "spec" / "Properties.tla")
    ws = tmp_path / "edited-ws"
    shutil.copytree(G1_REF, ws)
    text = (ws / "spec" / "Properties.tla").read_text(encoding="utf-8")
    (ws / "spec" / "Properties.tla").write_text(text.replace("AtMostOneHolder", "AtMostOneHoldeR"), encoding="utf-8")
    inp = _cell_input(tmp_path, ws, _g1_task(expected))
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (0, None)


def test_g1_statement_integrity_model_only_change_stays_1(tmp_path):  # positive control (Test Architect Minor 9)
    from harness_bench.plan import file_hash
    expected = file_hash(G1_REF / "spec" / "Properties.tla")
    ws = tmp_path / "model-changed-ws"
    shutil.copytree(G1_REF, ws)
    (ws / "spec" / "Model.tla").write_text(
        (ws / "spec" / "Model.tla").read_text(encoding="utf-8").replace("Claim(p)", "Claim(pp)").replace(
            "Claim(pp) ==", "Claim(pp) =="),
        encoding="utf-8")
    inp = _cell_input(tmp_path, ws, _g1_task(expected))
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (1, None)


def test_g1_statement_integrity_no_working_copy_is_na(tmp_path):
    inp = _cell_input(tmp_path, G1_REF, _g1_task("deadbeef"))
    shutil.rmtree(inp.archive / "ws")
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (None, "no working copy in the archive")


# --- formal_checks_clean: G1 (real TLC) ------------------------------------------------------------------------

def test_g1_formal_checks_clean_reference_is_1(tmp_path):
    inp = _cell_input(tmp_path, G1_REF, G1_TASK, {"oracle/bounds.cfg": G1_BOUNDS})
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (1, None)
    assert "5 states generated" in Path(score.evidence).read_text(encoding="utf-8")


def test_g1_formal_checks_clean_refuses_a_binary_artifact_before_invoking_tlc(tmp_path, monkeypatch):
    ws = FIXTURES / "g1" / "binary-artifact"
    inp = _cell_input(tmp_path, ws, G1_TASK, {"oracle/bounds.cfg": G1_BOUNDS})

    def _boom(*a, **k):
        raise AssertionError("TLC must never be invoked when a binary artifact is present")

    monkeypatch.setattr(formal.correctness, "run_step", _boom)
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (0, None)


def test_g1_formal_checks_clean_not_warmed_is_na(tmp_path, monkeypatch):
    monkeypatch.setenv("HB_TLA_JAR", str(tmp_path / "nope.jar"))
    inp = _cell_input(tmp_path, G1_REF, G1_TASK, {"oracle/bounds.cfg": G1_BOUNDS})
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert score.value is None and score.reason.startswith("formal toolchain not warmed: ")


def test_g1_formal_checks_clean_no_bounds_cfg_is_na(tmp_path):
    inp = _cell_input(tmp_path, G1_REF, G1_TASK)  # no oracle/bounds.cfg copied
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (None, "no oracle/bounds.cfg for this task version")


def test_g1_formal_checks_clean_no_working_copy_is_na(tmp_path):
    inp = _cell_input(tmp_path, G1_REF, G1_TASK, {"oracle/bounds.cfg": G1_BOUNDS})
    shutil.rmtree(inp.archive / "ws")
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (None, "no working copy in the archive")


# --- formal_checks_clean: the pure clean-run predicate (FM7, no real subprocess needed) --------------------------

@pytest.mark.parametrize(("returncode", "output", "clean"), [
    (0, "5 states generated, 3 distinct states found, 0 states left on queue.", True),
    (0, "Model checking completed. No error has been found.", False),  # FM7: no states-generated line -> not clean
    (1, "5 states generated, 3 distinct states found.", False),
    (0, "Invariant AtMostOneHolder is violated.\n5 states generated, 3 distinct states found.", False),
    (0, "Error: could not parse.\n5 states generated, 3 distinct states found.", False),
])
def test_tlc_clean_predicate(returncode, output, clean):
    assert formal._tlc_clean(returncode, output) is clean


# --- statement_integrity / formal_checks_clean: G2 (real lake + lean) --------------------------------------------

G2_REF = FIXTURES / "g2" / "reference"
G2_TASK = {"formal": {"tool": "lean", "statements": "fixed", "theorem_names": ["total_cons"]}}


def _g2_ws(tmp_path: Path, proofs_src: Path) -> Path:
    ws = tmp_path / "g2-ws"
    (ws / "Proofs").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(proofs_src, ws / "Proofs", ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    return ws


def test_g2_statement_integrity_reference_matches_the_hash(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    # Re-derive the expected digest the same way the grader does, then assert equality end to end.
    inp = _cell_input(tmp_path, ws, G2_TASK)
    lake, _ = formal._warm_lake(ROOT)
    staging, files = formal._statement_material(ws / "Proofs", ["total_cons"], lake, formal.correctness._env(), TIMEOUT, inp.out_dir / "probe2")
    from harness_bench.plan import tree_hash
    expected = tree_hash(staging, files)
    inp2 = _cell_input(tmp_path / "real", ws, {"formal": {**G2_TASK["formal"], "statement_hash": expected}})
    assert encode(formal.statement_integrity(inp2, TIMEOUT)) == (1, None)


def test_g2_statement_integrity_proof_body_rewritten_signature_same_stays_1(tmp_path):  # Simplifier Major 1 / TA 3+7
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    lake, _ = formal._warm_lake(ROOT)
    inp0 = _cell_input(tmp_path / "base", ws, G2_TASK)
    staging, files = formal._statement_material(ws / "Proofs", ["total_cons"], lake, formal.correctness._env(), TIMEOUT, inp0.out_dir / "s")
    from harness_bench.plan import tree_hash
    expected = tree_hash(staging, files)
    # Rewrite the proof body only (rfl -> an equivalent tactic); the signature is untouched.
    stmt = ws / "Proofs" / "Statements.lean"
    stmt.write_text(stmt.read_text(encoding="utf-8").replace(":= by\n  rfl", ":= by\n  simp [total]"), encoding="utf-8")
    inp = _cell_input(tmp_path, ws, {"formal": {**G2_TASK["formal"], "statement_hash": expected}})
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (1, None)


def test_g2_statement_integrity_no_theorem_names_is_na(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, {"formal": {"tool": "lean", "statements": "fixed"}})
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (None, "formal.theorem_names not recorded for this task version")


def test_g2_statement_integrity_agent_statements_not_applicable(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, {"formal": {"tool": "lean", "statements": "agent", "theorem_names": ["total_cons"]}})
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (None, "formal.statements: agent — statement integrity not applicable")


# --- the real task G2's own statement_hash must be reproducible by the grader (grid-3 2026-10-01 CI-class) -------
#
# tasks/G2's formal.statement_hash was computed by a bespoke, unreproducible procedure (recorded only in
# oracle/README.md S6: a synthetic per-theorem hash entry labelled "Proofs/Statements.lean::<name>", content
# captured via `#check @<name>` -- the fully-explicit ∀ rendering, evidence.md §2), never through
# `_statement_material`/`plan.tree_hash`, the project's one sanctioned hashing recipe (G12, formal-grader.md:53)
# -- and a synthetic label containing `::` can never be a real Windows filename `tree_hash` could hash a real
# Path for anyway. Every G2 cell in grid-3 (276-cell run, grading grade-20261001T210800-579e4f) scored
# statement_integrity 0 "given statements edited (statement_hash mismatch)" identically across all 3 models x
# pack on/off x 2 reps, independent of what any agent did to the statements, because the stored hash could
# never match what the real grader computes. This test pins the real task's stored hash against what
# `_statement_material` actually produces, so a future re-authoring that reintroduces an out-of-band recipe
# fails here rather than silently zeroing an entire task's statement_integrity column again.

G2_REAL = ROOT / "tasks" / "G2"


def _g2_real_task() -> dict:
    from harness_bench import config
    return config.load_yaml(G2_REAL / "task.yaml")


def test_g2_real_task_statement_hash_matches_what_the_grader_computes(tmp_path):
    task = _g2_real_task()
    names = task["formal"]["theorem_names"]
    lake, reason = formal._warm_lake(ROOT)
    assert lake is not None, reason
    staging, files = formal._statement_material(
        G2_REAL / "workspace" / "Proofs", names, lake, formal.correctness._env(), TIMEOUT, tmp_path / "probe")
    assert staging is not None, files  # files holds the NA reason on failure
    from harness_bench.plan import tree_hash
    computed = tree_hash(staging, files)
    assert computed == task["formal"]["statement_hash"]


def test_g2_real_oracle_reference_scores_clean_against_the_real_task(tmp_path):
    task = _g2_real_task()
    ws = _g2_ws(tmp_path, G2_REAL / "oracle" / "reference" / "Proofs")
    inp = _cell_input(tmp_path, ws, task)
    assert encode(formal.statement_integrity(inp, TIMEOUT)) == (1, None)
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (1, None)


def test_g2_formal_checks_clean_reference_is_1(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (1, None)


@pytest.mark.parametrize("variant", ["sorry", "native_decide", "eval_effect"])
def test_g2_formal_checks_clean_seeded_variants_score_0(tmp_path, variant):
    ws = _g2_ws(tmp_path, FIXTURES / "g2" / variant / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (0, None)


def test_g2_formal_checks_clean_refuses_a_binary_artifact_before_invoking_lake(tmp_path, monkeypatch):
    ws = _g2_ws(tmp_path, FIXTURES / "g2" / "binary-artifact" / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)

    def _boom(*a, **k):
        raise AssertionError("lake must never be invoked when a binary artifact is present")

    monkeypatch.setattr(formal.correctness, "run_step", _boom)
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (0, None)


def _add_lake_build_output(proofs: Path) -> None:
    """Fakes what a real `lake build` leaves behind in `Proofs/`, added AFTER the archive copy (never before
    -- `_cell_input`'s own `shutil.copytree` already strips `.lake`/`lake-manifest.json` on the way into
    `archive/ws`, the same filter `_grading_copy` applies on the way into the disposable build copy, so
    adding these before that copy would make the scan never see them and the test would pass for the wrong
    reason)."""
    (proofs / ".lake" / "build" / "ir").mkdir(parents=True)
    (proofs / ".lake" / "build" / "ir" / "Fold.c").write_bytes(b"// generated by lake build\n")
    (proofs / ".lake" / "build" / "lib").mkdir(parents=True)
    (proofs / ".lake" / "build" / "lib" / "Fold.olean").write_bytes(b"\x00\x01\x02")
    (proofs / "lake-manifest.json").write_text("{}", encoding="utf-8")


def test_g2_formal_checks_clean_lake_build_output_is_not_a_binary_artifact(tmp_path):
    """tasks/G2/prompt.md:28 requires the agent to `lake build` in Proofs/, which always creates `.lake/`
    (compiled `.olean`/`.c` under it) and `lake-manifest.json` -- Lake's own, unavoidable build output, never
    something the agent chose to commit. `_grading_copy`'s own build copy already strips exactly these names
    before `lake build` runs there, so a smuggled binary under `.lake/` can never reach the graded build; the
    archive-reading scan must not penalise what it can never actually risk (grid-3 2026-10-02: every one of
    the 12 real G2 cells scored formal_checks_clean 0 for exactly this)."""
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    _add_lake_build_output(inp.archive / "ws" / "Proofs")
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (1, None)


@pytest.mark.parametrize("stray", ["x.olean", "foo.so"])
def test_g2_formal_checks_clean_a_stray_binary_outside_lake_still_fails(tmp_path, stray):
    """The `.lake`/`lake-manifest.json` exemption is narrow: a binary the agent put anywhere else in
    `Proofs/` -- including beside a genuine `.lake/` build-output tree -- must still fail (0), never read
    as "inside an ignored name" by accident."""
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    _add_lake_build_output(inp.archive / "ws" / "Proofs")
    (inp.archive / "ws" / "Proofs" / stray).write_bytes(b"\x00\x01\x02")
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (0, None)


def test_g2_formal_checks_clean_edited_manifest_never_reaches_lake_build(tmp_path, monkeypatch):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    (ws / "Proofs" / "lakefile.toml").write_text(
        (ws / "Proofs" / "lakefile.toml").read_text(encoding="utf-8") + '\n[[require]]\nname = "evil"\ngit = "https://example.invalid/evil"\n',
        encoding="utf-8")
    inp = _cell_input(tmp_path, ws, G2_TASK, {"Proofs": G2_REF / "Proofs"})  # the task's frozen copy, for the byte check
    calls = []
    monkeypatch.setattr(formal.correctness, "run_step", lambda argv, *a, **k: calls.append(argv) or (_ for _ in ()).throw(AssertionError("lake build must not run")))
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert (score.value, score.reason) == (0, None)
    assert calls == []


def test_g2_formal_checks_clean_not_warmed_is_na(tmp_path, monkeypatch):
    monkeypatch.setenv("ELAN_HOME", str(tmp_path / "no-elan"))
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    score = formal.formal_checks_clean(inp, TIMEOUT)
    assert score.value is None and score.reason.startswith("formal toolchain not warmed: ")


def test_g2_formal_checks_clean_no_fold_lean_is_na(tmp_path):
    ws = tmp_path / "empty-ws"
    (ws / "Proofs").mkdir(parents=True)
    inp = _cell_input(tmp_path, ws, G2_TASK)
    assert encode(formal.formal_checks_clean(inp, TIMEOUT)) == (None, "no Proofs/Fold.lean in the working copy")


# --- model_conformance / model_non_vacuity: G1 always NA "not built" (R-84 c1) -----------------------------------

def test_g1_model_conformance_and_non_vacuity_are_not_built_in_a_real_pass(tmp_path):
    from harness_bench.plan import file_hash
    expected = file_hash(G1_REF / "spec" / "Properties.tla")
    inp = _cell_input(tmp_path, G1_REF, _g1_task(expected))
    out = formal.grade_cell(dataclass_replace(inp, metrics={"model_conformance": {}, "model_non_vacuity": {}, "formal_checks_clean": {}, "statement_integrity": {}}))
    assert encode(out["model_conformance"]) == (None, formal.NOT_BUILT)
    assert encode(out["model_non_vacuity"]) == (None, formal.NOT_BUILT)


def dataclass_replace(inp: CellInput, **kw) -> CellInput:
    import dataclasses
    return dataclasses.replace(inp, **kw)


def test_g2_model_conformance_is_always_na():
    # no real ws needed: the NA is unconditional for tool=lean
    from dataclasses import replace as _r
    base = CellInput(run_dir=Path("."), root=ROOT, plan={"parameters": {"grading_step_timeout": TIMEOUT}},
                     cell={"cell_id": "c"}, task=G2_TASK, task_dir=Path("."), archive=Path("."), out_dir=Path("."),
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(), metrics={},
                     allow_model_calls=False, extraction=None, prices=None)
    out = formal.grade_cell(_r(base, metrics={"model_conformance": {}}))
    assert encode(out["model_conformance"]) == (None, "formal.tool lean: no runtime trace to replay (Lean proofs are static)")


# --- model_non_vacuity: G2 real (a second `lake build` against the bug-seeded fold) -------------------------------

def test_g2_model_non_vacuity_reference_proofs_fail_on_the_buggy_fold(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK, {"oracle/fold-buggy/Fold.lean": FIXTURES / "g2" / "buggy-fold" / "Fold.lean"})
    assert encode(formal._g2_model_non_vacuity(inp, TIMEOUT)) == (1, None)


def test_g2_model_non_vacuity_no_buggy_fold_asset_is_na(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK)
    assert encode(formal._g2_model_non_vacuity(inp, TIMEOUT)) == (None, "no oracle/fold-buggy/Fold.lean for this task version")


def test_g2_model_non_vacuity_out_dir_created_when_work_root_differs_from_out_dir(tmp_path):
    """ADR-0013 Amendment 2 (grading-copy relocation, 7ca97d83): a real pass's `work_root` sits
    outside the repository, in a different tree than `out_dir` (runner.py:309,327,329). This test
    file's own `_cell_input` helper leaves `work_root` at its `None` default, under which `work_dir`
    (`inp.work_root or inp.out_dir`) happens to equal `out_dir`, so `_grading_copy`'s `copytree` into
    `work_dir/"proofs"` silently creates `out_dir` as a side effect -- masking that `_g2_model_non_vacuity`
    never creates `out_dir` itself (unlike `_g1_formal_checks_clean`/`_g2_formal_checks_clean`, which both
    call `out_dir.mkdir(parents=True, exist_ok=True)`). With `work_root` genuinely distinct, as every
    real grid-3 pass has it, that side effect is gone and `_write_log(out_dir, ...)` must FileNotFoundError
    unless `out_dir` is created explicitly (grid-3 2026-10-01, G2.copilot-sol.pack-on.r2, HB-GRD-003)."""
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, G2_TASK, {"oracle/fold-buggy/Fold.lean": FIXTURES / "g2" / "buggy-fold" / "Fold.lean"})
    inp = dataclass_replace(inp, work_root=tmp_path / "work-root-outside")
    assert encode(formal._g2_model_non_vacuity(inp, TIMEOUT)) == (1, None)


# --- the _replay seam: test-only (R-84 c1) -------------------------------------------------------------------

def test_replay_raises_not_implemented_when_unstubbed():
    with pytest.raises(NotImplementedError):
        formal._replay(Path("m.tla"), Path("t.json"), 30, Path("."))


def test_g1_ratio_metric_computes_the_ratio_against_a_stub_replay(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "spec").mkdir(parents=True)
    task_dir = tmp_path / "task"
    (task_dir / "oracle" / "traces" / "real").mkdir(parents=True)
    for i in range(3):
        (task_dir / "oracle" / "traces" / "real" / f"t{i}.json").write_text("[]", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    inp = CellInput(run_dir=tmp_path, root=ROOT, plan={"parameters": {"grading_step_timeout": TIMEOUT}},
                    cell={"cell_id": "c"}, task={}, task_dir=task_dir, archive=ws.parent, out_dir=out_dir,
                    events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(), metrics={},
                    allow_model_calls=False, extraction=None, prices=None)

    def stub_replay(model, trace, timeout, out_dir):
        accepted = trace.name != "t1.json"  # one of the three traces diverges
        return formal.ReplayResult(accepted, str(trace), None if accepted else 7)

    score = formal._g1_ratio_metric(inp, "traces/real/*.json", True, stub_replay)
    assert score.value == Decimal(2) / Decimal(3)
    assert score.reason is None
    assert "t1.json:7" in score.evidence


def test_g1_ratio_metric_no_traces_is_na(tmp_path):
    ws = tmp_path / "ws"
    (ws / "spec").mkdir(parents=True)
    task_dir = tmp_path / "task"
    (task_dir / "oracle").mkdir(parents=True)
    inp = CellInput(run_dir=tmp_path, root=ROOT, plan={"parameters": {"grading_step_timeout": TIMEOUT}},
                    cell={"cell_id": "c"}, task={}, task_dir=task_dir, archive=ws.parent, out_dir=tmp_path / "out",
                    events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(), metrics={},
                    allow_model_calls=False, extraction=None, prices=None)
    (tmp_path / "out").mkdir()
    score = formal._g1_ratio_metric(inp, "traces/real/*.json", True, formal._replay)
    assert encode(score) == (None, "no recorded traces for this task version")


# --- the cascade (statement_integrity gates the other metrics; US-32) ----------------------------------------

def test_cascade_g1_edited_statement_gates_checks_and_replay_metrics_but_not_bugs(tmp_path):
    ws = tmp_path / "edited-ws"
    shutil.copytree(FIXTURES / "g1" / "bugs" / "ws", ws)
    shutil.copytree(G1_REF / "spec", ws / "spec")
    (ws / "spec" / "Properties.tla").write_text(
        (ws / "spec" / "Properties.tla").read_text(encoding="utf-8").replace("AtMostOneHolder", "AtMostOneHoldeR"),
        encoding="utf-8")
    inp = _cell_input(tmp_path, ws, _g1_task("deadbeef"), {
        "oracle/bounds.cfg": G1_BOUNDS, "oracle/bugfix/Fold.py": FIXTURES / "g1" / "bugs" / "oracle" / "bugfix" / "Fold.py"})
    inp = dataclass_replace(inp, metrics={m: {} for m in
                            ("statement_integrity", "formal_checks_clean", "model_conformance", "model_non_vacuity",
                             "bugs_confirmed", "bug_claim_precision")})
    out = formal.grade_cell(inp)
    for m in ("formal_checks_clean", "model_conformance", "model_non_vacuity"):
        assert encode(out[m]) == (None, "given statements edited (statement_hash mismatch)"), m
    assert encode(out["bugs_confirmed"]) == (1, None)  # unaffected by the cascade (the non-cascading pair, US-32)
    assert encode(out["bug_claim_precision"]) == (Decimal(1), None)


def test_cascade_g2_edited_statement_gates_checks_and_non_vacuity_only(tmp_path):
    ws = _g2_ws(tmp_path, G2_REF / "Proofs")
    inp = _cell_input(tmp_path, ws, {"formal": {**G2_TASK["formal"], "statement_hash": "deadbeef"}})
    inp = dataclass_replace(inp, metrics={m: {} for m in
                            ("statement_integrity", "formal_checks_clean", "model_non_vacuity", "model_conformance")})
    out = formal.grade_cell(inp)
    assert encode(out["statement_integrity"]) == (0, None)
    for m in ("formal_checks_clean", "model_non_vacuity"):
        assert encode(out[m]) == (None, "given statements edited (statement_hash mismatch)"), m
    # model_conformance is NA regardless, for its own (non-cascade) reason:
    assert encode(out["model_conformance"]) == (None, "formal.tool lean: no runtime trace to replay (Lean proofs are static)")


# --- bugs_confirmed / bug_claim_precision: DR-FM2's mechanical table (R-84), G1 only, real pytest -----------------

G1_BUGS_WS = FIXTURES / "g1" / "bugs" / "ws"
G1_BUGFIX = FIXTURES / "g1" / "bugs" / "oracle" / "bugfix" / "Fold.py"


def _bugs_input(tmp_path: Path, bugs_md: str) -> CellInput:
    ws = tmp_path / "ws"
    shutil.copytree(G1_BUGS_WS, ws)
    (ws / "BUGS.md").write_text(bugs_md, encoding="utf-8")
    inp = _cell_input(tmp_path, ws, G1_TASK, {"oracle/bugfix/Fold.py": G1_BUGFIX})
    return inp


CORRECT = "## seeded\n\nTest: tests/test_bug.py::test_at_most_one_holder\n"


def test_bugs_confirmed_one_correct_claim(tmp_path):
    inp = _bugs_input(tmp_path, CORRECT)
    assert encode(formal.bugs_confirmed(inp, TIMEOUT)) == (1, None)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal(1), None)


def test_bug_claim_precision_correct_plus_false_claim_is_half(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(G1_BUGS_WS, ws)
    (ws / "tests" / "test_false.py").write_text(
        "from coord_core import fold\n\n\ndef test_false_claim():\n    assert fold([]) is True\n", encoding="utf-8")
    bugs = CORRECT + "\n## false\n\nTest: tests/test_false.py::test_false_claim\n"
    (ws / "BUGS.md").write_text(bugs, encoding="utf-8")
    inp = _cell_input(tmp_path, ws, G1_TASK, {"oracle/bugfix/Fold.py": G1_BUGFIX})
    assert encode(formal.bugs_confirmed(inp, TIMEOUT)) == (1, None)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal("0.5"), None)


def test_bugs_confirmed_only_false_claim_is_0(tmp_path):  # N > 0 but confirmed == 0: not "any claim at all"
    ws = tmp_path / "ws"
    shutil.copytree(G1_BUGS_WS, ws)
    (ws / "tests" / "test_false.py").write_text(
        "from coord_core import fold\n\n\ndef test_false_claim():\n    assert fold([]) is True\n", encoding="utf-8")
    (ws / "BUGS.md").write_text("## false\n\nTest: tests/test_false.py::test_false_claim\n", encoding="utf-8")
    inp = _cell_input(tmp_path, ws, G1_TASK, {"oracle/bugfix/Fold.py": G1_BUGFIX})
    assert encode(formal.bugs_confirmed(inp, TIMEOUT)) == (0, None)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal(0), None)


def test_bug_claim_precision_correct_plus_no_test_line_is_half(tmp_path):  # R-84: moved fixture (was 1.0000)
    bugs = CORRECT + "\n## vague\n\nNo test named here.\n"
    inp = _bugs_input(tmp_path, bugs)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal("0.5"), None)


def test_bug_claim_precision_correct_plus_path_traversal_is_half(tmp_path):  # R-84: moved fixture (was 1.0000)
    bugs = CORRECT + "\n## evil\n\nTest: ../../../evil.py::pwn\n"
    inp = _bugs_input(tmp_path, bugs)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal("0.5"), None)


def test_bug_claim_precision_correct_plus_option_like_test_ref_is_half(tmp_path):
    bugs = CORRECT + "\n## evil2\n\nTest: -p some_plugin\n"
    inp = _bugs_input(tmp_path, bugs)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (Decimal("0.5"), None)


def test_bugs_confirmed_no_bugs_md_is_0_never_na(tmp_path):  # R-84: refuses the design's NA for this
    ws = tmp_path / "ws"
    shutil.copytree(G1_BUGS_WS, ws)
    (ws / "BUGS.md").unlink()
    inp = _cell_input(tmp_path, ws, G1_TASK, {"oracle/bugfix/Fold.py": G1_BUGFIX})
    assert encode(formal.bugs_confirmed(inp, TIMEOUT)) == (0, None)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (None, "no BUGS.md in the working copy")


def test_bugs_confirmed_empty_bugs_md_is_0_never_na(tmp_path):
    inp = _bugs_input(tmp_path, "# Reported bugs\n\nnone yet\n")
    assert encode(formal.bugs_confirmed(inp, TIMEOUT)) == (0, None)
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (None, "no BUGS.md in the working copy")


def test_bugs_confirmed_g2_is_always_na():
    base = CellInput(run_dir=Path("."), root=ROOT, plan={"parameters": {"grading_step_timeout": TIMEOUT}},
                     cell={"cell_id": "c"}, task=G2_TASK, task_dir=Path("."), archive=Path("."), out_dir=Path("."),
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(), metrics={},
                     allow_model_calls=False, extraction=None, prices=None)
    assert encode(formal.bugs_confirmed(base, TIMEOUT)) == (None, formal.G2_NO_BUG_ARTIFACT)
    assert encode(formal.bug_claim_precision(base, TIMEOUT)) == (None, formal.G2_NO_BUG_ARTIFACT)


def test_bug_claim_precision_no_working_copy_is_na(tmp_path):
    inp = _bugs_input(tmp_path, CORRECT)
    shutil.rmtree(inp.archive / "ws")
    assert encode(formal.bug_claim_precision(inp, TIMEOUT)) == (None, "no working copy in the archive")


# --- lexical scan and axiom predicate: pure-function unit tests (D1, no subprocess) -------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("theorem t : True := by sorry", "sorry"),
    ("-- sorry is mentioned only in a comment\ntheorem t : True := trivial", None),
    ('def s : String := "contains sorry as text"\n', None),
    ("theorem t : True := by native_decide", "native_decide"),
    ("#eval 1 + 1", "#eval"),
    ("@[extern \"foo\"] def f : Nat := 0", "@[extern"),
    ("def ok : Nat := 1", None),
])
def test_lexical_hit(text, expected):
    assert formal._lexical_hit(text) == expected


@pytest.mark.parametrize(("output", "clean"), [
    ("'t' does not depend on any axioms", True),
    ("'t' depends on axioms: [propext, Quot.sound]", True),
    ("'t' depends on axioms: [propext, Classical.choice, Quot.sound]", True),
    ("'t' depends on axioms: [sorryAx]", False),
    ("'t' depends on axioms: [myCustomAxiom]", False),
    ("garbage, no recognisable line", False),
])
def test_axioms_clean(output, clean):
    assert formal._axioms_clean(output) is clean


# --- Test: reference validation: pure-function unit tests (Security & Identity Architect Blocker 1) ---------------

@pytest.mark.parametrize(("ref", "valid"), [
    ("tests/test_bug.py::test_a", True),
    ("../../../evil.py::pwn", False),
    ("-p some_plugin", False),
    ("tests/test_bug.py", False),  # no ::
    ("/abs/path.py::f", False),
    ("tests/../../../evil.py::pwn", False),
])
def test_validate_test_ref(tmp_path, ref, valid):
    ws = tmp_path / "ws"
    (ws / "tests").mkdir(parents=True)
    (ws / "tests" / "test_bug.py").write_text("", encoding="utf-8")
    result = formal._validate_test_ref(ref, ws)
    assert (result is not None) is valid
