# A3 oracle

A3 is ClarifyCodeBench `task_254`: LiveCodeBench `abc397_c` ("Variety Split Easy") with the ambiguous term "counts". The
original statement says "find the maximum possible sum of the **varieties** of those subarrays" and "the number of
**distinct** integers in ..."; the task says "find the maximum possible sum of the **counts** in those subarrays" and
"the **count of integers** in ...". Licences: `../NOTICE.md`.

| File | What it is | Who reads it |
| --- | --- | --- |
| `clarifications.yaml` | The one annotated key clarification (`term-counts`) and its reply, verbatim from upstream; the default reply | the scripted user (W2-USER-M), the `clarify` grader |
| `heldout_questions.yaml` | 38 labelled questions for measuring the matcher: 17 labelled `term-counts`, 21 `default` (15 near-misses, 6 off-topic). The labelling rule is in the file | USER-D (S-04 threshold, R-39 c1); not for tuning the matcher |
| `reference/solution.py` | A correct solution (distinct integer counts) | the discrimination proof below |
| `reference/assumes_total_elements.py` | A control that decided the term wrongly ("counts" = total elements: prints N) | the discrimination proof below |
| `../tests/test_a3_hidden.py`, `../tests/a3_cases.json` | The hidden tests: 42 LiveCodeBench cases (2 public, 40 private), one unittest test each | the `correctness` grader |

## Authoring choices

- **Why task_254.** The upstream taxonomy defines `Terminology`: "A domain term, action, or state is undefined,
  overloaded, or open to multiple interpretations" (`clarifycodebench/taxonomy.py`). Of the candidate tasks whose
  only type is `Terminology`, task_254 features an ambiguous term ("counts" / "count of integers") with two natural
  readings that yield different outputs (count of distinct values vs total cardinality/length), has K = 1, reads
  stdin and writes stdout, and is an ABC C problem ($O(N)$ prefix/suffix frequency array), fitting the 15-minute budget
  with ample headroom.
- **Prompt.** The problem text is upstream's `modified_content`, byte for byte. Above it is one framing paragraph
  that names `solution.py`, stdin/stdout, the standard library, and the `ask_user` tool (R-37 condition 5). The
  framing is identical for every combo. It does not repeat upstream's "Do not guess" instruction. Whether the
  agent asks or assumes is the measured behaviour, so the prompt does not coach it.
- **The samples are withheld from the workspace.** The second original sample input has $N = 10$ and output $8$, which
  immediately reveals that "counts" cannot mean total element count (which would always sum to $10$). They are hidden
  tests `test_public_01..02`.
- **Test runner and platform portability.** LiveCodeBench's own runner times each case with `signal.alarm`, which
  Windows does not have. `test_a3_hidden.py` ports its stdio comparison rule (strip the output, split into lines,
  strip each line, equal line count, each line equal as text or as a list of Decimals). It runs `solution.py` as a
  child process per case under LiveCodeBench's default 6 s timeout using standard library only.
  Portable paths and tools ensure the task runs natively on both Windows and macOS (ADR-0013 Amendment 1).
  *assume: runs natively on macOS; what would confirm it: running `python -m unittest -v test_a3_hidden` on macOS under Python 3.10+; what breaks if it is false: Python stdlib subprocess or unittest behavior would diverge on macOS.*

## Discrimination proof (R-7 condition 6, plan row 7)

Run on this host (Windows 11, CPython 3.14.6 via `uv run`) through the bench's own grader:
`harness_bench.grade.correctness.grade` with this task's `oracle` block, on a copy of `workspace/`. The copy was
graded as found (base), with `solution.py` replaced by `reference/solution.py`, and with it replaced by the control.
The command is the task's oracle command, `{python} -m unittest -v test_a3_hidden`, run in the grading copy
(the working copy plus `tests/`).

| Working copy | Exit | Summary | pass@1 | Partial credit | Failing tests |
| --- | --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 42 tests` · `FAILED (failures=42)` | 0 | 0 | all 42: `test_public_01..02`, `test_private_01..40` (the stub raises `NotImplementedError`) |
| reference | 0 | `Ran 42 tests` · `OK` | 1 | 1 | none |
| control: counts decided as total elements | 1 | `Ran 42 tests` · `FAILED (failures=29)` | 0 | 13/42 | 29: `test_public_02` and 28 private tests; passes only 13 tests (`test_public_01`, `test_private_07`, `test_private_09`, `test_private_12`, `test_private_13`, `test_private_18`, `test_private_22`, `test_private_23`, `test_private_25`, `test_private_31`, `test_private_33`, `test_private_34`, `test_private_38`) where distinct count equals $N$ |

The tests fail on the base, pass on the reference, and reject a solution that resolved the ambiguous term wrongly. So the
hidden tests measure whether the intended term reading was recovered, not only whether the program runs.

To reproduce by hand, copy `workspace/` and `tests/` into one empty folder, drop in a solution as `solution.py`,
and run `python -m unittest -v test_a3_hidden` there.

## Schemas (defined here; no reader is built yet)

- `clarifications.yaml`, `schema: bench-clarifications/1`: `default_reply`; `clarifications[]` with `id`, `type`,
  `deleted_information`, `question`, `reply`. The scripted user's reply for a matched question is `reply`, verbatim;
  for anything else it is `default_reply`, verbatim (spec US-10).
- `heldout_questions.yaml`, `schema: bench-heldout-questions/1`: `questions[]` with `id`, `kind`, `expected`
  (a clarification id or `default`), `question`, and optional `transform` or `note`.
