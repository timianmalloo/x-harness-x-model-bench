# A2 oracle

A2 is ClarifyCodeBench `task_109`: LiveCodeBench `abc393_d` ("Swap to Gather") with the precondition
"S contains at least one 1" deleted. The original statement says "It is guaranteed that S contains at
least one 1." and carries `- S contains at least one 1.` in Constraints; the task omits both.
Licences: `../NOTICE.md`.

| File | What it is | Who reads it |
| --- | --- | --- |
| `clarifications.yaml` | The one annotated key clarification (`premise-at-least-one-1`) and its reply, verbatim from upstream; the default reply | the scripted user (W2-USER-M), the `clarify` grader |
| `heldout_questions.yaml` | 38 labelled questions for measuring the matcher: 17 labelled `premise-at-least-one-1`, 21 `default` (15 near-misses, 6 off-topic). The labelling rule is in the file | USER-D (S-04 threshold, R-39 c1); not for tuning the matcher |
| `reference/solution.py` | A correct solution (gathers 1s around median) | the discrimination proof below |
| `reference/assumes_gather_zeros.py` | A control that decided the premise wrongly (gathered 0s instead of 1s) | the discrimination proof below |
| `../tests/test_a2_hidden.py`, `../tests/a2_cases.json` | The hidden tests: 43 LiveCodeBench cases (3 public, 40 private), one unittest test each | the `correctness` grader |

## Authoring choices

- **Why task_109.** The upstream taxonomy has no "missing premise" type. The nearest is `Edge Cases`:
  "boundary or exceptional conditions are not specified, leaving behavior unclear for special inputs"
  (`clarifycodebench/taxonomy.py`). Task_109 deletes the explicit input constraint / precondition
  guaranteeing that S contains at least one 1. Without this premise, if S contains only 0s, the definition of
  contiguous 1s ($1 \le l \le r \le N$) cannot be satisfied, leaving the requirement undefined / unsolvable.
  It has K = 1, reads stdin and writes stdout, has an $O(N)$ median-gathering algorithm, and easily fits the
  15-minute budget.
- **Prompt.** The problem text is upstream's `modified_content`, byte for byte. Above it is one framing paragraph
  that names `solution.py`, stdin/stdout, the standard library, and the `ask_user` tool (R-37 condition 5). The
  framing is identical for every combo. It does not repeat upstream's "Do not guess" instruction. Whether the
  agent asks or assumes is the measured behaviour, so the prompt does not coach it.
- **The samples are withheld from the workspace.** Upstream clarifies problems without leaking answers in sample
  explanations; the sample cases are kept as hidden tests `test_public_01..03`.
- **Test runner.** LiveCodeBench's own runner times each case with `signal.alarm`, which Windows does not have, so it
  does not run on this host. `test_a2_hidden.py` ports its stdio comparison rule (strip the output, split into lines,
  strip each line, equal line count, each line equal as text or as a list of Decimals). It runs `solution.py` as a
  child process per case under LiveCodeBench's default 6 s timeout. Stdlib only.
- **Portability (ADR-0013 Amendment 1).** The workspace, tests and reference solution use portable Python standard
  library mechanisms (sys.stdin, subprocess.run, unittest) with no platform-specific APIs. Proven on Windows 11 here.
  assume: runs natively on macOS without modification; confirm by running the oracle command on a macOS host;
  breaks if platform-specific path separators or signals are introduced.

## Discrimination proof (R-7 condition 6, plan row 7)

Run on this host (Windows 11, CPython 3.14.6 via `uv run`) through the bench's own grader:
`harness_bench.grade.correctness.grade` with this task's `oracle` block, on a copy of `workspace/`. The copy was
graded as found (base), with `solution.py` replaced by `reference/solution.py`, and with it replaced by the control.
The command is the task's oracle command, `{python} -m unittest -v test_a2_hidden`, run in the grading copy
(the working copy plus `tests/`).

| Working copy | Exit | Summary | pass@1 | Partial credit | Failing tests |
| --- | --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 43 tests` · `FAILED (failures=43)` | 0 | 0 | all 43: `test_public_01..03`, `test_private_01..40` (the stub raises `NotImplementedError`) |
| reference | 0 | `Ran 43 tests` · `OK` | 1 | 1 | none |
| control: gather zeros | 1 | `Ran 43 tests` · `FAILED (failures=32)` | 0 | 11/43 | 32; fails `test_public_03` and 31 private tests (`test_private_02..06, 08, 10..15, 17, 19, 20, 22, 24..26, 28..39`) |

The tests fail on the base, pass on the reference, and reject a control that made the wrong premise assumption.
So the hidden tests measure correctness and discriminate non-conforming solutions.

To reproduce by hand, copy `workspace/` and `tests/` into one empty folder, drop in a solution as `solution.py`,
and run `python -m unittest -v test_a2_hidden` there.

## Schemas (defined here; no reader is built yet)

- `clarifications.yaml`, `schema: bench-clarifications/1`: `default_reply`; `clarifications[]` with `id`, `type`,
  `deleted_information`, `question`, `reply`. The scripted user's reply for a matched question is `reply`, verbatim;
  for anything else it is `default_reply`, verbatim (spec US-10).
- `heldout_questions.yaml`, `schema: bench-heldout-questions/1`: `questions[]` with `id`, `kind`, `expected`
  (a clarification id or `default`), `question`, and optional `transform` or `note`.
