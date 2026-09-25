# A1 oracle

A1 is ClarifyCodeBench `task_199`: LiveCodeBench `abc396_c` ("Buy Balls") with the objective deleted. The
original statement says "find the **maximum possible** sum"; the task says "find the sum". Licences: `../NOTICE.md`.

| File | What it is | Who reads it |
| --- | --- | --- |
| `clarifications.yaml` | The one annotated key clarification (`goal-maximum`) and its reply, verbatim from upstream; the default reply | the scripted user (W2-USER-M), the `clarify` grader |
| `heldout_questions.yaml` | 38 labelled questions for measuring the matcher: 17 labelled `goal-maximum`, 21 `default` (15 near-misses, 6 off-topic). The labelling rule is in the file | USER-D (S-04 threshold, R-39 c1); not for tuning the matcher |
| `reference/solution.py` | A correct solution (maximum total) | the discrimination proof below |
| `reference/assumes_any_total.py` | A control that decided the goal wrongly ("any valid total": prints 0, the empty choice) | the discrimination proof below |
| `../tests/test_a1_hidden.py`, `../tests/a1_cases.json` | The hidden tests: 43 LiveCodeBench cases (3 public, 40 private), one unittest test each | the `correctness` grader |

## Authoring choices

- **Why task_199.** The upstream taxonomy has no "missing goal" type. The nearest is `Behavior`: "the required
  function, objective, or side effect is underspecified" (`clarifycodebench/taxonomy.py`). Of the 25 tasks whose only
  type is `Behavior`, task_199 deletes exactly the objective word, has K = 1, reads stdin and writes stdout, and is
  an ABC C problem, so it fits the 15-minute budget. Other candidates of the same shape: task_220 (`abc396_d`),
  task_272 (`abc397_b`), task_305 (`abc399_c`).
- **Prompt.** The problem text is upstream's `modified_content`, byte for byte. Above it is one framing paragraph
  that names `solution.py`, stdin/stdout, the standard library, and the `ask_user` tool (R-37 condition 5). The
  framing is identical for every combo. It does not repeat upstream's "Do not guess" instruction. Whether the
  agent asks or assumes is the measured behaviour, so the prompt does not coach it.
- **The samples are withheld from the workspace.** The original samples say "which is the maximum" and their outputs
  reveal the objective. They are hidden tests `test_public_01..03`.
- **Test runner.** LiveCodeBench's own runner times each case with `signal.alarm`, which Windows does not have, so it
  does not run on this host. `test_a1_hidden.py` ports its stdio comparison rule (strip the
  output, split into lines, strip each line, equal line count, each line equal as text or as a list of Decimals). It
  runs `solution.py` as a child process per case under LiveCodeBench's default 6 s timeout. Stdlib only.

## Discrimination proof (R-7 condition 6, plan row 7)

Run on this host (Windows 11, CPython 3.14.6 via `uv run`) through the bench's own grader:
`harness_bench.grade.correctness.grade` with this task's `oracle` block, on a copy of `workspace/`. The copy was
graded as found (base), with `solution.py` replaced by `reference/solution.py`, and with it replaced by the control.
The command is the task's oracle command, `{python} -m unittest -v test_a1_hidden`, run in the grading copy
(the working copy plus `tests/`).

| Working copy | Exit | Summary | pass@1 | Partial credit | Failing tests |
| --- | --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 43 tests` · `FAILED (failures=43)` | 0 | 0 | all 43: `test_public_01..03`, `test_private_01..40` (the stub raises `NotImplementedError`) |
| reference | 0 | `Ran 43 tests` · `OK` | 1 | 1 | none |
| control: goal decided wrongly | 1 | `Ran 43 tests` · `FAILED (failures=38)` | 0 | 5/43 | 38; it passes only `test_public_03`, `test_private_03`, `test_private_08`, `test_private_10`, `test_private_40`, whose answer is 0 |

The tests fail on the base, pass on the reference, and reject a solution that guessed the goal wrongly. So the
hidden tests measure whether the deleted goal was recovered, not only whether the program runs.

To reproduce by hand, copy `workspace/` and `tests/` into one empty folder, drop in a solution as `solution.py`,
and run `python -m unittest -v test_a1_hidden` there.

## Schemas (defined here; no reader is built yet)

- `clarifications.yaml`, `schema: bench-clarifications/1`: `default_reply`; `clarifications[]` with `id`, `type`,
  `deleted_information`, `question`, `reply`. The scripted user's reply for a matched question is `reply`, verbatim;
  for anything else it is `default_reply`, verbatim (spec US-10).
- `heldout_questions.yaml`, `schema: bench-heldout-questions/1`: `questions[]` with `id`, `kind`, `expected`
  (a clarification id or `default`), `question`, and optional `transform` or `note`.
