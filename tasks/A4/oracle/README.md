# A4 Oracle

A4 is the authored task for Scenario 1 ("Specify from an ambiguous prompt") on the cfd-bench P0 domain: "Make the wing definition reusable across runs". The prompt is deliberately underspecified; the scripted user answers the 5 key clarification dimensions from `clarifications.yaml`.

| File | What it is | Who reads it |
| --- | --- | --- |
| `clarifications.yaml` | The 5 annotated key clarifications (persistence vs sharing, format, versioning, validation, scope) and default reply | The scripted user (`scripted_user`), the `clarify` grader |
| `heldout_questions.yaml` | 39 labelled questions measuring matcher precision and recall across all 5 dimensions | Scripted user test suites and evaluation |
| `rubric.md` | 10-item judge rubric scoring the specification against the 5 clarifications and /specify DoD | The LLM `judge` grader |
| `evidence.md` | Detailed discrimination proof, test run logs, and execution times | The auditor / verification pass |
| `reference/docs/specs/reusable-wing-definition.md` | Complete three-layer reference specification (`/specify` conformant) | Discrimination proof, judge reference |
| `reference/controls/assumes_cloud_sharing.md` | Negative control specification assuming cloud REST service rather than local persistence | Discrimination proof negative control |
| `../tests/test_a4_hidden.py` | 8 hidden unittest assertions checking file presence, required sections, clarification coverage, and Gherkin ACs | The `correctness` grader |

## Authoring choices

- **Underspecified requirement:** The prompt is the exact one-line prompt from the authored-task inventory: "Make the wing definition reusable across runs". In Scenario 1, the prompt does not specify whether "reusable across runs" means local file persistence or networked cloud sharing, what serialization format is expected, whether schema versioning is required, how validation is performed, or whether derived quantities should be stored.
- **5 Clarifications:** Grounded in the cfd-bench P0 domain conventions (`docs/proposals/build-phasing-plan.html` and P0 spine code):
  1. *persistence vs sharing:* Local file on disk, not remote/cloud network sharing.
  2. *format:* Structured JSON format.
  3. *versioning:* Explicit format identifier (`cfd-wing/1`) for fail-closed schema evolution.
  4. *validation:* Fail-closed validation enforcing wing invariants (stations >= 2, root on centreline, increasing span, positive chord).
  5. *scope:* Only core wing geometry definition (stations); derived quantities are never persisted (derived on the fly).
- **Workspace:** Contains the P0 spine code (`src/CfdBench.Core/`: `CfdBench.Core.csproj`, `Domain/Station.cs`, `Domain/Wing.cs`, `Derivations/WingDerivations.cs`, `Units/Quantities.cs`).
- **Hidden tests:** Python stdlib `unittest` in `tests/test_a4_hidden.py`. Checks structural existence of `docs/specs/reusable-wing-definition.md`, all 7 required `/specify` sections, the 5 clarification dimensions, and Gherkin Given/When/Then syntax.

## Discrimination proof

Evaluated on Windows 11 (CPython 3.14.6 via `uv run`):

| Working copy | Exit | Summary | pass@1 | Failing tests |
| --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 8 tests in 0.002s` · `FAILED (failures=8)` | 0 | all 8 (spec file does not exist) |
| reference (`reference/`) | 0 | `Ran 8 tests in 0.009s` · `OK` | 1 | none (0) |
| control (`assumes_cloud_sharing.md`) | 1 | `Ran 8 tests in 0.003s` · `FAILED (failures=7)` | 0 | 7/8 (only `test_spec_file_present` passes) |

The hidden tests fail on the base workspace, pass on the reference specification, and reject a specification that made wrong assumptions.

## Portability (ADR-0013 Amendment 1)

The oracle command invokes Python directly using forward slashes:
`command: ["{python}", "-m", "unittest", "-v", "test_a4_hidden"]`
It does not invoke `cmd.exe` or any shell. All paths in tests and references use forward slashes or `pathlib.Path`.
Proven on Windows.
assume: runs identically on macOS / Linux using Python 3 standard library; confirm by running on a macOS runner in cross-platform CI.

## Budget and Headroom

- Budget: 15 minutes (900 s).
- Reference solution test run: 0.009 s.
- Headroom: > 99.99%.
