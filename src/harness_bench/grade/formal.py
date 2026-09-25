"""Scenario 7 (formalize and find bugs): grade a TLA+ model or Lean 4 proof as four separate scores.

Metrics: formal_checks_clean, statement_integrity, model_conformance, model_non_vacuity,
bugs_confirmed, bug_claim_precision.
- checks: `lake build` clean and `#print axioms` shows only propext, Classical.choice, Quot.sound
  (no sorry, admit, custom axiom or native_decide); TLC completes within the declared bounds.
- statement integrity: given statements and properties hash to formal.statement_hash.
- fidelity: recorded traces of the real code replay against the model; bug-seeded variants are rejected.
- yield: a reported bug counts only when a failing test reproduces it on the real code.
Method: SysMoBench's staged grading (syntax, runtime, conformance, invariants) and Verina's
separate code / spec / proof scores. Spec: S-08g (docs/specs/README.md).
"""

from collections.abc import Mapping

from harness_bench.grade import CellInput, Score


def grade_cell(inp: CellInput) -> Mapping[str, Score]:  # not registered in runner.GRADERS: NA "not built"
    raise NotImplementedError("grade.formal is not built yet; spec S-08g in docs/specs/README.md")
