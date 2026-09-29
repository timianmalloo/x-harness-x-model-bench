# B3 oracle

B3 is the operator-authored substitute for the SpecBench row (R-7 c2, R-82 DR-W5-1): a scenario-2
primer-to-spec task on cfd-bench's **P1** phase paragraph ("Estimator, validated"), reusing B1's
source pin (`cfd-bench` `496a0a8ca2fae9026927167a8f3e5da0a53f2233`) and the same vendored file
(`docs/proposals/build-phasing-plan.html`, byte-identical to B1's copy, sha256
`af55c60d8e0c76c77e76a4e6b54d650bd3bdbd45cf63d3de79a8fdf1a4313b43`).

Reference spec: `reference/docs/specs/p1-estimator-validated.md`. It is not in the workspace.

`rubric.md` is the judge rubric for the /specify definition of done named in `task.yaml`.
`evidence.md` records the fail-on-base, pass-on-reference, and per-control unittest runs.

Hidden tests are `../tests/test_b3_hidden.py`, overlaid by the correctness grader
(`runner: unittest`). Two checks are structural (`test_spec_file_present`,
`test_spec_required_sections`) — file exists, required headings have non-empty bodies. They do not
score the prose; the judge does.

The other two checks are **decided-content checks**, each targeting one fact the P1 paragraph
states and `prompt.md` restates, not a generic on-topic keyword (A4's finding: a single keyword
any on-topic text would contain measures nothing):

- `test_validation_is_against_real_experimental_data` — the primer's own point (section 03, P1
  "Contents": *"validation against DTIC ADA032272 — real towing-tank lift and drag for NACA
  16-309 and 64A309"*) is that the closed-form chain is checked against **real experimental
  data**, not against itself. A spec that validates via a CFD-computed or self-consistency
  reference instead has dropped the one fact that makes validation here worth a phase gate.
- `test_section_catalog_detects_selig_and_lednicer` — the primer names *"the Selig/Lednicer
  format detection that a defect already taught us to need"*. A spec that supports only one
  format, or pushes format identification onto the caller, has dropped the defect-taught
  requirement.

Each check pairs a **positive** assertion (the decided content is present, as a proximity regex
over the specific facts named — DTIC ADA032272 with both NACA section ids; Selig with Lednicer
with detection) with a **negative** assertion scoped to the "In scope" half of the In scope / Out
of scope section only, so a decision correctly named as an explicit non-goal never trips it, but a
spec that puts the wrong decision *in scope* does (A5's pattern, applied here per R-82 condition 1
rather than B2's uncommitted-wrong-answer shape).

## Controls (A5's pattern)

Per R-82 condition 1, each decided-content check has a control under `reference/controls/` — a
complete specification meeting every item except the one named — so the check's failure is proven
to isolate its own fact, not a shared keyword:

| Control | What it decides wrongly | Fails only |
| --- | --- | --- |
| `control_synthetic_validation.md` | Validates the closed-form chain with a self-consistency check against an internally generated CFD-computed reference, instead of DTIC ADA032272's real towing-tank data for NACA 16-309 and 64A309. Every other decided fact (Selig/Lednicer detection, structural sections) is correct. | `test_validation_is_against_real_experimental_data` |
| `control_single_format.md` | Restricts the section catalog to Selig format only, with the caller required to pre-convert any other layout, instead of automatic Selig/Lednicer detection. Every other decided fact (DTIC ADA032272 validation on NACA 16-309/64A309, structural sections) is correct. | `test_section_catalog_detects_selig_and_lednicer` |

## Discrimination proof

Evaluated on Windows 11 (CPython 3.12.10 via `python`), running the task's own oracle command,
`{python} -m unittest -v test_b3_hidden`, in a grading copy (`workspace/` plus `tests/`), with
`docs/specs/p1-estimator-validated.md` replaced by each working copy in turn. Full command
transcripts are in `evidence.md`.

| Working copy | Exit | Summary | pass@1 | Failing tests |
| --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 4 tests` · `FAILED (failures=4)` | 0 | all 4 (spec file does not exist) |
| reference (`reference/docs/specs/p1-estimator-validated.md`) | 0 | `Ran 4 tests` · `OK` | 1 | none |
| control: validation → self-consistency/CFD-computed | 1 | `Ran 4 tests` · `FAILED (failures=1)` | 0 | `test_validation_is_against_real_experimental_data` only |
| control: format → Selig only, caller pre-converts | 1 | `Ran 4 tests` · `FAILED (failures=1)` | 0 | `test_section_catalog_detects_selig_and_lednicer` only |

The hidden tests fail on the base, pass on the reference, and — for both decided-content checks —
reject a plausible wrong answer that decided that one dimension wrongly while getting every other
item right; each control fails **only** the check for the dimension it got wrong (verified by name
above, not just by count).

To reproduce by hand: copy `workspace/` and `tests/` into one empty folder, drop in a spec as
`docs/specs/p1-estimator-validated.md` (the reference, or either control), and run
`python -m unittest -v test_b3_hidden` there.

## Portability (ADR-0013 Amendment 1)

The oracle command invokes Python directly using forward slashes:
`command: ["{python}", "-m", "unittest", "-v", "test_b3_hidden"]`. It does not invoke `cmd.exe` or
any shell (task D2's shape). All paths in the hidden tests use `pathlib.Path` with forward-slash
literals (`docs/specs/p1-estimator-validated.md`). Proven on Windows.
assume: runs identically on macOS/Linux using the Python 3 standard library (`pathlib`, `unittest`,
`re`); confirm by running the same command on a macOS/Linux runner in cross-platform CI. If false,
the likely failure mode is a locale/encoding difference in `Path.read_text(encoding="utf-8")`, not
the path syntax itself — the same residual B1/B2 already carry. Not measured here (no
macOS/Linux host in this worktree).

## Budget and headroom

- Budget: 20 minutes (1,200 s), matching `bench/bom.yaml`.
- Reference test suite execution time: 0.001 s (measured, see `evidence.md`).
- Headroom: > 99.99%.
