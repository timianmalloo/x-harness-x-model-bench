# RW1 oracle evidence

Status of RW1: `draft`. It stays `draft` until X-J1 (the multi-turn engine) and X-J2b (the rework grader and the multi-turn
discrimination path) have joined and a real-host discrimination record reproduces the `expected` block of `task.yaml`
(W1-L 5.3, W0 rev 6.6 R6.6c). The follow-on in this tree flips `status: ready`, runs `bench discriminate RW1` and commits the
folder and the record together (W0 section 2, the order of the `ready` flip).

Provenance per row: **traced** = derived from the committed source by hand before any run; **measured (stand-in)** = then
observed through `tests/fixtures/property_tasks/rework_standin.py`, which implements W1-L 5.1/6.1 on plain text because
`_changes.product_lines`, `line_delta`, `is_test_path` and `grade/rework.py` (X-J2) have not joined. A stand-in number is
Inferred (FIXT-A), never provenance. The hidden tests ran through the task's own oracle command under CPython 3.14.6
(`sys._base_executable` of the project environment, `-S`), and the pass/fail rows below also through the real
`correctness.grade`.

## Pinned base

- repo `https://github.com/xolox/python-humanfriendly`, commit `6758ac61f906cd8528682003070a57febe4ad3cf` (MIT, `Copyright (c) 2021 Peter Odding`).
- `git rev-parse 6758ac61f906cd8528682003070a57febe4ad3cf^{tree}` printed `d25f96a3910d75bd867ee5e000d61d1b7997c402` (fresh clone, 2026-10-03).
- pin tree: `d25f96a3910d75bd867ee5e000d61d1b7997c402`
- The base used by every test is built by the engine, `workspace.task_source(tasks/RW1, ...)`, over the pinned upstream
  (`upstream_tree` + `git archive`) with `tasks/RW1/workspace/.gitkeep` overlaid. `tasks/RW1/LICENSE` is the upstream MIT text.

## Test-path classification of the base (R2-2; data, W0 rev 6.6 section 13)

`humanfriendly/tests.py` is a test path under `_changes.is_test_path(path, base_paths)`: its basename is `tests.py`. Every
other `.py` file of the base is a product path. `humanfriendly/testing.py` is a product path (its basename is `testing.py`,
not a test basename, and the base has no `tests` or `test` directory): a residual, since it is a helper that tests import, but
the rule is W0's and an edit there is counted. Today `test_base_test_layout_is_classified_as_data` checks this list against the
stand-in rule over the engine-built base. The follow-on asserts the same list through the real `is_test_path` (no `xfail`).

- test path: `humanfriendly/tests.py`
- product path: `docs/conf.py`
- product path: `humanfriendly/__init__.py`
- product path: `humanfriendly/case.py`
- product path: `humanfriendly/cli.py`
- product path: `humanfriendly/compat.py`
- product path: `humanfriendly/decorators.py`
- product path: `humanfriendly/deprecation.py`
- product path: `humanfriendly/prompts.py`
- product path: `humanfriendly/sphinx.py`
- product path: `humanfriendly/tables.py`
- product path: `humanfriendly/terminal/__init__.py`
- product path: `humanfriendly/terminal/html.py`
- product path: `humanfriendly/terminal/spinners.py`
- product path: `humanfriendly/testing.py`
- product path: `humanfriendly/text.py`
- product path: `humanfriendly/usage.py`
- product path: `setup.py`

## Solutions (overlays; assume: the final tree is base + `turn-1/` + `turn-2/`, a file in `turn-2/` replacing the same path)

Each solution ships `humanfriendly/__init__.py` only. The prompts ask for tests in `humanfriendly/tests.py`; the overlays do
not model that edit, because test paths are excluded from every RW1 metric and no hidden test reads `tests.py`. Residual: a
real agent's `tests.py` edit is invisible to the grade, as intended.

| role | turn 1 | turn 2 |
| --- | --- | --- |
| reference | a private `_MONEY_FORMATS` data row (USD), one private `_format_money` that reads symbol, decimals, position and separators from it, and `format_dollars` calling it | EUR and JPY rows, a public `format_money` calling `_format_money`, and the one line in `format_dollars` that now calls `format_money` |
| alt | a `_FORMATS` dict of dicts, `_render` with `Decimal.quantize` per code, same behaviour, different structure | the two rows, `format_money` calling `_render`, `format_dollars` calling `format_money` |
| naive | one function with the dollar sign, two decimals and rounding inline | the body moved under `if currency == 'USD':` inside a new `format_money`, one branch per code, and `format_dollars` calling it (the logic is indented one level, so every turn-1 body line is rewritten) |

## Turn-1-added product lines and the ratio (W1-L 6.1; B-RW1)

Traced by hand, then measured (stand-in). `|T1|` counts the lines of the snapshot that the base-to-snapshot diff adds or
replaces, over non-test `.py` files in `humanfriendly/*.py`; `changed` is how many of them turn 2 replaces or deletes.

- reference |T1| = 16: one `__all__` entry, three lines of the data (`_MONEY_FORMATS = {`, the USD row, `}`), ten lines of `_format_money`, the `def format_dollars` line and its `return`. Turn 2 replaces one of them: the `return _format_money(amount, 'USD')` line. 1/16 = 0.0625.
- naive |T1| = 7: one `__all__` entry, the `def`, and five body lines (`value`, `text`, `if`, two `return`). Turn 2 re-indents the five body lines (they now sit under `if currency == 'USD':`), so five are replaced, the `def format_dollars` line and the `__all__` entry survive. 5/7 = 0.7143.
- alt |T1| = 17, 1 changed, 0.0588 (below the ceiling).

- ratio reference: t1=16 changed=1 ratio=0.0625
- ratio naive: t1=7 changed=5 ratio=0.7143
- ratio alt: t1=17 changed=1 ratio=0.0588

Design targets: reference at most 0.1000 (met, 0.0625), naive at least 0.6000 (met, 0.7143), ceiling 0.3000. The naive loses on
the ratio clause alone: it passes all ten hidden tests. EV-4 through the engine is shown in the follow-on.

## Hidden tests (10) and the real grader

| solution | turn 1 on the snapshot | turn 1 and 2 on the final tree |
| --- | --- | --- |
| base (no change) | fails (no `format_dollars`) | fails |
| stub (a unique sentinel from `format_dollars` and `format_money`) | 5 of 5 fail on an assertion | 10 of 10 fail on an assertion |
| reference, naive, alt | 5 of 5 pass | 10 of 10 pass |

`correctness.grade` returned `passed=1` for each of the three solutions on both trees and `passed=0` (`partial_credit` 0) on
the base. Where the design's T1-3 used a string `'2.675'`, the committed test uses `Decimal('2.675')`: with a string in both
T1-3 and T1-4, a wrong app that mishandled strings would turn two tests red, and T1-4 carries the string case alone.

## Wrong apps (11)

Each is the final reference tree with one substitution; `oracle/wrong_apps.py` declares the exact set of tests it turns red,
each by an assertion failure. A substitution that touches a rule several tests share turns all of them red (for example
`wa-nosep` removes the separator, which T1-1, T1-2, T2-1, T2-2 and T2-4 all read); the declared set says so.

## Variants (6)

`oracle/variants.py` is W0's one `VARIANTS` literal. For this check-less task `flips` lists metric ids whose observed value
differs from the reference's.

| variant | what it does | flips | deciding clause |
| --- | --- | --- | --- |
| `ratiohigh` | turn 2 nests `_format_money`'s body under `if code in ...`, rewriting its turn-1 lines | `property_check_pass`, `rework_ratio` | `ratio` |
| `t1regress` | turn 2 inserts `amount = round(float(amount), 2)`, which breaks T1-3 only (a pure insertion: the ratio is unchanged) | `property_check_pass` | `turn1` |
| `t2short` | turn 2 reverted: the final tree is the snapshot | `property_check_pass`, `rework_ratio` | `tests` |
| `duplicate` | `format_money` carries its own copy of the logic and `format_dollars` is untouched | `property_check_pass`, `rework_ratio` | `tests` (T2-5 only) |
| `deaddelegate` | `format_dollars` calls `format_money`, discards the result and returns its old value | `property_check_pass`, `rework_ratio` | `tests` (T2-5 only) |
| `padturn1` | turn 1 and turn 2 both carry 20 dead lines in `format_dollars` | `rework_ratio` | none: it passes |

**R-W1 (named residual, reported with every rework result).** `padturn1` passes with a ratio (1/36 = 0.0278) below the
reference's (0.0625): padding turn 1 with dead lines grows the denominator. The ratio sees only turn-1 lines that turn 2
changes or deletes, so insertion-only work scores 0. The three defences are tests: the sentinel delegation test (T2-5, which
`deaddelegate` and `duplicate` fail), and the named variant that records the hole.

## Deviations from W1-L rev 2, each found by running

1. T1-3 uses `Decimal('2.675')`, not the string `'2.675'` (see above).
2. The variants edit the turn-2 file wherever possible, since the final tree is base + `turn-1/` + `turn-2/` and a turn-2 file
   replaces the turn-1 file whole.
3. The latent-term scan covers `prompt.md` only. `turns/2.md` must say `format_money(amount, currency)`, which contains
   `currency`, a latent term; W1-L 6.2's turn-2 shape does the same.

## Seeded-disagreement fixture (R2-4)

`tests/fixtures/property_tasks/rw1_seeded_disagreement.json` is a discrimination result whose reference `rework_ratio`
(`0.5000`) disagrees with `expected` (`0.0625`). Today a test proves only that it is a true disagreement on one named metric.
In the follow-on, X-J2b's multi-turn path feeds it to readiness and asserts HB-RDY-003 names the metric, the expected and the
observed value (W1-E T-E11, T-E12).

## What the follow-on needs

X-J1 and X-J2b joined; X-J2a's `_changes` functions joined (the stand-in file is then deleted and the tests call the real
functions); `status: ready`; `bench discriminate RW1` run on the real host through the multi-turn path; the record committed
with the folder; the `expected` values re-read against the record (they are Inferred until then, blocking item B-RW1).
